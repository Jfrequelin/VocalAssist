#![allow(dead_code)]

//! audio/mod.rs — Capture microphone I2S + codec ES7210
//!
//! Matériel (Waveshare ESP32-S3-Touch-LCD-1.85C-BOX)
//! ┌─────────────────────────────────────────────────────────┐
//! │  ES7210 ADC (microphone)  I2C addr 0x40                 │
//! │  ES8311 DAC (speaker)     I2C addr 0x18                 │
//! │  NS4150B ampli Class D    PA_CTRL = IO15                │
//! │    IO15 HIGH = ampli ON, IO15 LOW = shutdown             │
//! │  TCA9554PWR I/O expander  I2C addr 0x20                 │
//! │  I2C bus : SDA=IO11  SCL=IO10                           │
//! │  I2S bus (speaker) :                                    │
//! │    MCLK = IO02  (généré par ESP32)                      │
//! │    BCK  = IO48                                          │
//! │    LRCK = IO38                                          │
//! │    DIN  = IO47  (ESP32 → ES8311 DAC → haut-parleur)     │
//! └─────────────────────────────────────────────────────────┘

use anyhow::Result;
use esp_idf_hal::{
    delay::FreeRtos,
    gpio::{InputPin, OutputPin},
    i2s::{
        config::{Config, DataBitWidth, Role, SlotMode, StdClkConfig, StdConfig, StdGpioConfig, StdSlotConfig},
        I2s, I2sBiDir, I2sDriver,
    },
};
use esp_idf_sys::*;
use log::info;
use std::sync::{Arc, Mutex};
use std::thread;
use crate::buffers::AudioRingBuffer;
use crate::config::audio::{
    CAPTURE_BYTES, CAPTURE_MAX_MS, CAPTURE_MS,
    VAD_MIN_VOICE_MS, VAD_SILENCE_STOP_MS, VAD_VOICE_THRESHOLD,
    PLAYBACK_GAIN,
    PLAYBACK_MAX_ADAPTIVE_GAIN, PLAYBACK_TARGET_PEAK, PLAYBACK_TIMEOUT_TICKS,
    READ_TIMEOUT_TICKS, SAMPLE_RATE_HZ, TEST_TONE_HZ,
};

// ── GPIO pinout (schéma officiel Waveshare ESP32-S3-Touch-LCD-1.85C-BOX) ─────────
// I2C  : SDA=IO11   SCL=IO10
// I2S  : MCLK=IO02  BCK=IO48  LRCK=IO38  DIN(DAC)=IO47
// Ampli: PA_CTRL=IO15  HIGH=ON  LOW=Shutdown (NS4150B Class D)
// Expander: TCA9554PWR @I2C 0x20  (EXIO1=TP_RST, EXIO2=LCD_RST, ...)

// ── I2C helpers (bus I2C0 déjà initialisé par LcdDisplay) ───────────────────

fn i2c_write_reg(dev_addr: u8, reg: u8, val: u8) -> Result<()> {
    let buf = [reg, val];
    let ret = unsafe {
        i2c_master_write_to_device(
            i2c_port_t_I2C_NUM_0,
            dev_addr,
            buf.as_ptr(),
            buf.len(),
            100,
        )
    };
    if ret != ESP_OK {
        anyhow::bail!("I2C 0x{:02X} reg 0x{:02X}: err {}", dev_addr, reg, ret);
    }
    Ok(())
}

fn i2c_read_reg(dev_addr: u8, reg: u8) -> Result<u8> {
    let mut out = [0u8; 1];
    let ret = unsafe {
        i2c_master_write_read_device(
            i2c_port_t_I2C_NUM_0,
            dev_addr,
            &reg,
            1,
            out.as_mut_ptr(),
            out.len(),
            100,
        )
    };
    if ret != ESP_OK {
        anyhow::bail!("I2C RD 0x{:02X} reg 0x{:02X}: err {}", dev_addr, reg, ret);
    }
    Ok(out[0])
}

fn i2c_probe_reg0(dev_addr: u8) -> bool {
    i2c_read_reg(dev_addr, 0x00).is_ok()
}

fn i2c_log_bus_presence() {
    // Adresses importantes pour cette carte (audio + touch/RTC/expander)
    const KNOWN_ADDRS: &[u8] = &[0x15, 0x18, 0x20, 0x40, 0x51];
    for &addr in KNOWN_ADDRS {
        info!(
            "[AUDIO][I2C] probe 0x{:02X}: {}",
            addr,
            if i2c_probe_reg0(addr) { "present" } else { "absent" }
        );
    }

    // Scan global pour diagnostiquer une éventuelle variante matérielle différente.
    let mut found = 0u32;
    for addr in 0x08u8..=0x77u8 {
        if i2c_probe_reg0(addr) {
            found += 1;
            info!("[AUDIO][I2C] found device @ 0x{:02X}", addr);
        }
    }
    info!("[AUDIO][I2C] scan done: {} devices", found);
}

// ── ES7210 (ADC microphone) ──────────────────────────────────────────────────
const ES7210_ADDR: u8 = 0x40;

/// Init ES7210 : 16 kHz, 16 bits, I2S standard, mode slave, gain 36 dB.
/// Séquence issue du driver officiel ESP-ADF v2.7 (espressif/esp-adf).
///
/// Différences critiques vs l'ancienne séquence incorrecte :
/// - 0x00=0x41 obligatoire pour sortir du reset (sans ça tout chip reste en reset)
/// - 0x11=0x60 pour 16-bit (bits[7:5]=011), pas 0x0C (qui encode 24-bit)
/// - 0x40=0x43 pour analog init (pas 0xC3)
/// - 0x41/0x42=0x70 pour MIC bias 2.87V (pas 0xC3/0x08)
/// - Registres HPF (0x20-0x23) et timing (0x09, 0x0A) ajoutés
/// - MIC power regs 0x47-0x4A et LRCK divider (0x04, 0x05) ajoutés
/// - 0x43/0x44 : bit4=1 active l'ADC, bits[3:0]=0x0D = gain 36dB
/// - 0x01=0x00 à la fin pour activer tous les clocks (start)
const ES7210_SEQ: &[(u8, u8)] = &[
    // 1. Reset logiciel (délai 10ms géré dans es7210_init après cet octet)
    (0x00, 0xFF),
    // 2. *** SORTIR DU RESET *** — sans ça le chip ignore toutes les écritures !
    (0x00, 0x41),
    // 3. Désactiver tous les clocks pendant la configuration
    (0x01, 0x3F),
    // 4. Timing des cycles d'état (chip state / power-on cycle)
    (0x09, 0x30),
    (0x0A, 0x30),
    // 5. Filtres HPF (High-Pass Filter) ADC1/2 et ADC3/4
    (0x23, 0x2A),
    (0x22, 0x0A),
    (0x20, 0x0A),
    (0x21, 0x2A),
    // 6. Analog init : vdda=3.3V, VMID=5kΩ, power off ADC3/4 (mode slave = défaut)
    (0x40, 0x43),
    (0x41, 0x70), // MIC1/2 bias = 2.87V
    (0x42, 0x70), // MIC3/4 bias = 2.87V
    (0x07, 0x20), // OSR = 32
    // 7. MAINCLK : clear state, puis configuration pour MCLK=4.096MHz / LRCK=16kHz
    //    adc_div=0x01 | doubler<<6=0x40 | dll<<7=0x80 = 0xC1
    (0x02, 0xC1),
    (0x04, 0x01), // LRCK divider high : 4096000 / 16000 = 256 → high=0x01
    (0x05, 0x00), // LRCK divider low  : 256 → low=0x00
    // 8. Power-up global (power-down reg → 0x00)
    (0x06, 0x00),
    (0x47, 0x08), // MIC1 power ON
    (0x48, 0x08), // MIC2 power ON
    (0x49, 0x08), // MIC3 power (init même si non utilisé)
    (0x4A, 0x08), // MIC4 power (idem)
    // 9. MIC select MIC1+MIC2 : power off all, puis activer sélectivement
    (0x4B, 0xFF), // Power off MIC1/2 temporairement
    (0x4C, 0xFF), // Power off MIC3/4
    //    Enable ADC1/2 clocks : 0x3F & ~0x0B = 0x34 (clear bits 0,1,3)
    (0x01, 0x34),
    (0x4B, 0x00), // Power ON MIC1/2
    //    ADC1 : enable (bit4=1) + gain 36dB (0x0D) = 0x1D
    (0x43, 0x1D),
    //    ADC2 : enable (bit4=1) + gain 36dB (0x0D) = 0x1D
    (0x44, 0x1D),
    // 10. Format audio : 16-bit word length (bits[7:5]=011=0x60) + I2S standard (bits[1:0]=00)
    (0x11, 0x60),
    // 11. Start : activer tous les clocks (reg 0x01 = 0x00)
    (0x01, 0x00),
];

/// Lecture et affichage des registres ES7210 clés pour valider l'init.
fn es7210_dump_registers() {
    info!("[AUDIO] === ES7210 register dump ===");
    let key_regs: &[(u8, &str)] = &[
        (0x00, "RESET  "), (0x01, "CLK_ON "), (0x02, "MCLK   "),
        (0x06, "PDM_CTL"), (0x07, "MCLK_NI"), (0x11, "SDP1   "),
        (0x40, "ADC34EN"), (0x41, "ADC12EN"), (0x42, "MICBIAS"),
        (0x43, "PGA_CH1"), (0x44, "PGA_CH2"), (0x4B, "VOL_L  "), (0x4C, "VOL_R  "),
    ];
    for &(reg, name) in key_regs {
        match i2c_read_reg(ES7210_ADDR, reg) {
            Ok(v)  => info!("[AUDIO] ES7210 [0x{:02X}] {} = 0x{:02X}", reg, name, v),
            Err(_) => log::warn!("[AUDIO] ES7210 [0x{:02X}] {} = ERR", reg, name),
        }
    }
    // Vérification basique : chip absent si reg 0x01 reste 0xFF après reset
    if let Ok(v) = i2c_read_reg(ES7210_ADDR, 0x01) {
        if v == 0xFF {
            log::error!("[AUDIO] ES7210 reg 0x01 = 0xFF — chip absent ou bus I2C KO");
        }
    }
    info!("[AUDIO] === fin dump ES7210 ===");
}

fn es7210_init() -> Result<()> {
    info!("[AUDIO] Init ES7210 0x{:02X}", ES7210_ADDR);
    let mut prev_reg = 0xFFu8;
    for &(reg, val) in ES7210_SEQ {
        i2c_write_reg(ES7210_ADDR, reg, val)?;
        // Délai après reset (0xFF) pour laisser le chip se stabiliser avant 0x41
        if reg == 0x00 && val == 0xFF && prev_reg != 0x00 {
            FreeRtos::delay_ms(10);
        }
        prev_reg = reg;
    }
    es7210_dump_registers();
    info!("[AUDIO] ES7210 OK");
    Ok(())
}

/// Affiche les registres ES7210 pour diagnostic post-MCLK.
/// La séquence d'init complète (incluant les registres de format et de gain) est
/// maintenant dans ES7210_SEQ / es7210_init(). Cette fonction n'écrit plus de
/// registres — elle sert uniquement à vérifier l'état après démarrage I2S.
pub fn es7210_reconfigure() {
    info!("[AUDIO] ES7210 diagnostic post-init...");
    es7210_dump_registers();
    info!("[AUDIO] ES7210 diagnostic done");
}

// ── ES8311 (DAC speaker) ─────────────────────────────────────────────────────
const ES8311_ADDR: u8 = 0x18;

const ES8311_REG_RESET: u8 = 0x00;
const ES8311_REG_CLKMGR1: u8 = 0x01;
const ES8311_REG_CLKMGR2: u8 = 0x02;
const ES8311_REG_CLKMGR3: u8 = 0x03;
const ES8311_REG_CLKMGR4: u8 = 0x04;
const ES8311_REG_CLKMGR5: u8 = 0x05;
const ES8311_REG_CLKMGR6: u8 = 0x06;
const ES8311_REG_CLKMGR7: u8 = 0x07;
const ES8311_REG_CLKMGR8: u8 = 0x08;
const ES8311_REG_SDPIN: u8 = 0x09;
const ES8311_REG_SDPOUT: u8 = 0x0A;
const ES8311_REG_SYSTEM0D: u8 = 0x0D;
const ES8311_REG_SYSTEM0E: u8 = 0x0E;
const ES8311_REG_SYSTEM10: u8 = 0x10;
const ES8311_REG_SYSTEM11: u8 = 0x11;
const ES8311_REG_SYSTEM12: u8 = 0x12;
const ES8311_REG_SYSTEM13: u8 = 0x13;
const ES8311_REG_SYSTEM14: u8 = 0x14;
const ES8311_REG_ADC15: u8 = 0x15;
const ES8311_REG_ADC16: u8 = 0x16;
const ES8311_REG_ADC17: u8 = 0x17;
const ES8311_REG_ADC1C: u8 = 0x1C;
const ES8311_REG_DAC31: u8 = 0x31;
const ES8311_REG_DAC32: u8 = 0x32;
const ES8311_REG_DAC37: u8 = 0x37;
const ES8311_REG_GPIO44: u8 = 0x44;
const ES8311_REG_GP45: u8 = 0x45;

const ES8311_DAC_VOLUME_DB_0: u8 = 0xBF;

/// Init ES8311 (sequence inspiree ESP-ADF pour 16 kHz, 16 bits, I2S slave).
const ES8311_SEQ: &[(u8, u8)] = &[
    // Robustesse I2C (ecriture en double recommandee par ESP-ADF)
    (ES8311_REG_GPIO44, 0x08),
    (ES8311_REG_GPIO44, 0x08),
    // Sequence d'init de base codec
    (ES8311_REG_CLKMGR1, 0x30),
    (ES8311_REG_CLKMGR2, 0x00),
    (ES8311_REG_CLKMGR3, 0x10),
    (ES8311_REG_ADC16, 0x24),
    (ES8311_REG_CLKMGR4, 0x10),
    (ES8311_REG_CLKMGR5, 0x00),
    (ES8311_SYSTEM0B, 0x00),
    (ES8311_SYSTEM0C, 0x00),
    (ES8311_REG_SYSTEM10, 0x1F),
    (ES8311_REG_SYSTEM11, 0x7F),
    // Mode esclave I2S
    (ES8311_REG_RESET, 0x80),
    (ES8311_REG_RESET, 0x00),
    // CLKMGR1: use_mclk=true (MCLK pin externe), clocks internes actifs, pas d'inversion MCLK.
    // Aligné avec la config sw3Dan (force_master + MCLK externe x256).
    (ES8311_REG_CLKMGR1, 0x3F),
    (ES8311_REG_CLKMGR1, 0x3F),
    // Coefficients sw3Dan pour { mclk=4096000, rate=16000 } :
    // pre_div=1, pre_mult=1 → REG02 = (1-1)<<5 | 1<<3 = 0x08
    // fs_mode=0, adc_osr=0x10 → REG03=0x10
    // dac_osr=0x20 → REG04=0x20
    // adc_div=1, dac_div=1 → REG05=0x00
    // BCLK_DIV = round(4096000 / (16000×16×2)) = 8 → champ=8-1=7 → REG06=0x07
    // lrck_h=0x00, lrck_l=0xFF → LRCK=4096000/256=16000 Hz ✓
    (ES8311_REG_CLKMGR2, 0x08),
    (ES8311_REG_CLKMGR5, 0x00),
    (ES8311_REG_CLKMGR3, 0x10),
    (ES8311_REG_CLKMGR4, 0x20),
    (ES8311_REG_CLKMGR7, 0x00),
    (ES8311_REG_CLKMGR8, 0xFF),
    // CLKMGR6=0x07 : BCLK_DIV=8 (4096000/8=512000 Hz = 16000×16×2) → champ=div-1=7
    (ES8311_REG_CLKMGR6, 0x07),
    // Interface I2S standard, 16 bits
    (ES8311_REG_SDPIN, 0x0C),
    (ES8311_REG_SDPOUT, 0x0C),
];

const ES8311_SYSTEM0B: u8 = 0x0B;
const ES8311_SYSTEM0C: u8 = 0x0C;

fn es8311_config_playback_path() -> Result<()> {
    // ES8311 = Slave (MSC=0, bit6=0). ESP32 I2S Controller génère MCLK/BCLK/LRCLK.
    // REG00 bit7=1 (power-on), bit6=0 (slave) → 0x80
    let mut reg00 = i2c_read_reg(ES8311_ADDR, ES8311_REG_RESET)?;
    reg00 = (reg00 & !0x40) | 0x80; // power-on, MSC=0
    i2c_write_reg(ES8311_ADDR, ES8311_REG_RESET, reg00)?;

    // Format I2S 16-bit (SDPIN/SDPOUT=0x0C) + chemin DAC explicite.
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SDPIN, 0x0C)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SDPOUT, 0x0C)?;

    // Séquence de power-up alignée sur le composant sw3Dan.
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SYSTEM0D, 0x01)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SYSTEM0E, 0x02)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SYSTEM12, 0x00)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SYSTEM13, 0x10)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_SYSTEM14, 0x1A)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_ADC15, 0x40)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_ADC16, 0x24)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_ADC17, 0xBF)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_ADC1C, 0x6A)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_DAC37, 0x08)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_GP45, 0x00)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_GPIO44, 0x58)?;

    // Unmute DAC + volume 0 dB
    let dac31 = i2c_read_reg(ES8311_ADDR, ES8311_REG_DAC31)? & 0x9F;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_DAC31, dac31)?;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_DAC32, ES8311_DAC_VOLUME_DB_0)?;

    // Re-écrit REG00 pour conserver power-on, MSC=0 (slave).
    let mut reg00_po = i2c_read_reg(ES8311_ADDR, ES8311_REG_RESET)?;
    reg00_po = (reg00_po & !0x40) | 0x80;
    i2c_write_reg(ES8311_ADDR, ES8311_REG_RESET, reg00_po)?;
    Ok(())
}

fn es8311_log_state(tag: &str) {
    match (
        i2c_read_reg(ES8311_ADDR, ES8311_REG_DAC31),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_DAC32),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_GPIO44),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_SYSTEM13),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_SDPIN),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_CLKMGR1),
        i2c_read_reg(ES8311_ADDR, ES8311_REG_RESET),
    ) {
        (Ok(r31), Ok(r32), Ok(r44), Ok(r13), Ok(r09), Ok(r01), Ok(r00)) => {
            info!(
                "[AUDIO] ES8311 {}: r00=0x{:02X}(msc={}) r01(clk)=0x{:02X} r31=0x{:02X} mute={}, r32=0x{:02X}, r44=0x{:02X}, r13=0x{:02X}, r09=0x{:02X}",
                tag,
                r00,
                ((r00 & 0x40) != 0) as u8,
                r01,
                r31,
                ((r31 & 0x60) != 0) as u8,
                r32,
                r44,
                r13,
                r09
            );
        }
        _ => {
            log::warn!("[AUDIO] ES8311 {}: lecture registres impossible", tag);
        }
    }
}

/// Dump complet des registres ES8311 pour validation hardware.
/// Lit tous les registres 0x00..=0x4A et affiche les blocs significatifs.
fn es8311_dump_registers() {
    info!("[AUDIO] === ES8311 register dump ===");

    // Lire tous les registres 0x00 à 0x4A en une passe
    let mut regs = [0u8; 0x4B];
    let mut any_fail = false;
    for addr in 0x00u8..=0x4Au8 {
        match i2c_read_reg(ES8311_ADDR, addr) {
            Ok(v) => regs[addr as usize] = v,
            Err(_) => {
                log::warn!("[AUDIO] ES8311 dump: erreur lecture reg 0x{:02X}", addr);
                any_fail = true;
            }
        }
    }

    if any_fail {
        log::warn!("[AUDIO] ES8311 dump incomplet — verifier adresse I2C 0x{:02X}", ES8311_ADDR);
        return;
    }

    // Bloc Reset / ID
    info!("[AUDIO] [00] RESET   =0x{:02X}  (chip_id attendu: 0x00 apres reset)", regs[0x00]);

    // Bloc Clock Manager
    info!("[AUDIO] [01] CLKMGR1 =0x{:02X}  (bit7=1:BCLK src, bit6=0:MCLK, bits5-0:div)", regs[0x01]);
    info!("[AUDIO] [02] CLKMGR2 =0x{:02X}  (MCLK pre-divider)", regs[0x02]);
    info!("[AUDIO] [03] CLKMGR3 =0x{:02X}  (ADC OSR)", regs[0x03]);
    info!("[AUDIO] [04] CLKMGR4 =0x{:02X}  (DAC OSR)", regs[0x04]);
    info!("[AUDIO] [05] CLKMGR5 =0x{:02X}  (ADC divider)", regs[0x05]);
    info!("[AUDIO] [06] CLKMGR6 =0x{:02X}  (BCLK divider MCLK->BCLK)", regs[0x06]);
    info!("[AUDIO] [07] CLKMGR7 =0x{:02X}  (LRCK H divider)", regs[0x07]);
    info!("[AUDIO] [08] CLKMGR8 =0x{:02X}  (LRCK L divider)", regs[0x08]);

    // Bloc SDP (Serial Data Port)
    info!("[AUDIO] [09] SDPIN   =0x{:02X}  (DAC iface: fmt bits1-0, len bits4-2)", regs[0x09]);
    info!("[AUDIO] [0A] SDPOUT  =0x{:02X}  (ADC iface)", regs[0x0A]);

    // Bloc System
    info!("[AUDIO] [0D] SYS0D   =0x{:02X}  (powerdown control)", regs[0x0D]);
    info!("[AUDIO] [0E] SYS0E   =0x{:02X}  (analog power)", regs[0x0E]);
    info!("[AUDIO] [0F] SYS0F   =0x{:02X}", regs[0x0F]);
    info!("[AUDIO] [10] SYS10   =0x{:02X}  (ref/bias)", regs[0x10]);
    info!("[AUDIO] [11] SYS11   =0x{:02X}  (HP drv)", regs[0x11]);
    info!("[AUDIO] [12] SYS12   =0x{:02X}  (DAC mono/stereo)", regs[0x12]);
    info!("[AUDIO] [13] SYS13   =0x{:02X}  (HP bias/output)", regs[0x13]);
    info!("[AUDIO] [14] SYS14   =0x{:02X}  (HP amp ctrl)", regs[0x14]);

    // Bloc ADC
    info!("[AUDIO] [15] ADC15   =0x{:02X}  (ADC ctrl)", regs[0x15]);
    info!("[AUDIO] [16] ADC16   =0x{:02X}  (ADC volume)", regs[0x16]);
    info!("[AUDIO] [17] ADC17   =0x{:02X}  (ADC eq/filter)", regs[0x17]);

    // Bloc DAC
    info!("[AUDIO] [31] DAC31   =0x{:02X}  (DAC ctrl: bits6-5=mute)", regs[0x31]);
    info!("[AUDIO] [32] DAC32   =0x{:02X}  (DAC volume: 0xBF=0dB)", regs[0x32]);
    info!("[AUDIO] [37] DAC37   =0x{:02X}  (DAC offset)", regs[0x37]);

    // Bloc GPIO
    info!("[AUDIO] [44] GPIO44  =0x{:02X}  (GPIO/IRQ cfg: 0x58=normal)", regs[0x44]);
    info!("[AUDIO] [45] GP45    =0x{:02X}  (GPIO output)", regs[0x45]);

    // Diagnostic: chip présent ? Si tous registres = 0x00 ou 0xFF = pas de chip
    let all_zero = regs[0x01..=0x10].iter().all(|&v| v == 0x00);
    let all_ff   = regs[0x01..=0x10].iter().all(|&v| v == 0xFF);
    if all_zero || all_ff {
        log::error!("[AUDIO] ES8311 ABSENT ou bus I2C non fonctionnel (tous regs = 0x{:02X})", regs[0x01]);
    } else {
        info!("[AUDIO] ES8311 detecte et repond sur I2C 0x{:02X}", ES8311_ADDR);
    }
    info!("[AUDIO] === fin dump ES8311 ===");
}

fn es8311_init() -> Result<()> {
    info!("[AUDIO] Init ES8311 0x{:02X}", ES8311_ADDR);
    for &(reg, val) in ES8311_SEQ {
        i2c_write_reg(ES8311_ADDR, reg, val)?;
        if reg == ES8311_REG_RESET { FreeRtos::delay_ms(10); }
    }
    es8311_config_playback_path()?;
    es8311_log_state("post-init");
    es8311_dump_registers();
    info!("[AUDIO] ES8311 OK");
    Ok(())
}

/// Initialise les codecs audio (ES7210 + ES8311).
/// Appeler une seule fois, après LcdDisplay::new() (I2C déjà actif).
pub fn audio_init() -> Result<()> {
    // IO15 = PA_CTRL = NS4150B SD (amplificateur Class D)
    // HIGH = Normal operation (ampli actif), LOW = Shutdown (silence garanti)
    // NE PAS toucher GPIO12 (MCLK I2S) ni GPIO13 (BCLK I2S)
    unsafe {
        let pa_cfg = gpio_config_t {
            pin_bit_mask: 1u64 << 15,
            mode: gpio_mode_t_GPIO_MODE_OUTPUT,
            pull_up_en: gpio_pullup_t_GPIO_PULLUP_DISABLE,
            pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        gpio_config(&pa_cfg);
        gpio_set_level(15, 1); // HIGH → NS4150B SD=H → ampli ON
    }
    info!("[AUDIO] GPIO15=HIGH (PA_CTRL NS4150B ON)");
    i2c_log_bus_presence();
    es7210_init()?;
    es8311_init()?;
    Ok(())
}

// ── MicCapture : capture I2S haut-niveau ────────────────────────────────────

/// Driver I2S RX pour la capture microphone (ES7210 ADC).
///
/// Créer une seule fois dans `main()` et réutiliser à chaque cycle READY.
pub struct MicCapture<'d> {
    driver: I2sDriver<'d, I2sBiDir>,
}

impl<'d> MicCapture<'d> {
    /// Initialise le périphérique I2S0 en mode RX stéréo 16 kHz.
    ///
    /// Pins (schéma Waveshare BOX) :
    ///   mclk = IO02, bck = IO48, ws = IO38, dout(DAC) = IO47, pa_ctrl = IO15
    pub fn new<I2SP: I2s + 'd>(
        i2s: I2SP,
        bck:  impl InputPin + OutputPin + 'd,
        ws:   impl InputPin + OutputPin + 'd,
        din:  impl InputPin + 'd,
        dout: impl OutputPin + 'd,
        mclk: impl InputPin + OutputPin + 'd,
    ) -> Result<Self> {
        let cfg = StdConfig::new(
            // ESP32 = I2S Controller : génère MCLK, BCLK, LRCLK.
            // ES8311 = Slave (MSC=0) : reçoit les clocks depuis l'ESP32.
            Config::default().role(Role::Controller),
            StdClkConfig::from_sample_rate_hz(SAMPLE_RATE_HZ),
            StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Stereo),
            StdGpioConfig::default(),
        );
        let driver = I2sDriver::<I2sBiDir>::new_std_bidir(i2s, &cfg, bck, din, dout, Some(mclk), ws)
            .map_err(|e| anyhow::anyhow!("I2S init: {:?}", e))?;
        info!("[AUDIO] I2S RX/TX initialisé (16 kHz, stéréo)");
        Ok(Self { driver })
    }

    /// Capture CAPTURE_MS ms d'audio.
    ///
    /// Retourne les bytes PCM16LE **mono** (canal gauche = mic 1).
    /// Taille = CAPTURE_FRAMES × 2 bytes ≈ 96 KB à 16 kHz / 3 s.
    pub fn capture(&mut self) -> Result<Vec<u8>> {
        info!("[AUDIO] Capture {} ms…", CAPTURE_MS);
        let mut stereo = vec![0u8; CAPTURE_BYTES];
        let mut total  = 0usize;
        const CHUNK: usize = 1024;
        let t0_us = unsafe { esp_timer_get_time() } as u64;
        let silence = [0u8; CHUNK];

        // En mode bidirectionnel, activer TX avant RX stabilise la génération
        // d'horloge I2S (BCLK/LRCK) pour l'ADC ES7210 en mode esclave.
        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable(capture): {:?}", e))?;
        self.driver.rx_enable().map_err(|e| anyhow::anyhow!("rx_enable: {:?}", e))?;

        {
            let (mut rx, mut tx) = self.driver.split();

            // ── VAD : arrêt anticipé dès silence après voix ───────────────────
            // chunk = 1024 bytes stéréo = 256 frames = 16 ms à 16 kHz
            const CHUNK_MS: u32 = (CHUNK as u32 / 4) * 1000 / 16_000; // ≈ 16 ms
            let vad_min_chunks  = (VAD_MIN_VOICE_MS  / CHUNK_MS).max(1) as usize;
            let vad_stop_chunks = (VAD_SILENCE_STOP_MS / CHUNK_MS).max(1) as usize;
            let mut voice_chunks   = 0usize; // chunks consécutifs au-dessus du seuil (cumulatif)
            let mut silence_chunks = 0usize; // chunks silencieux consécutifs APRÈS voix détectée

            while total < CAPTURE_BYTES {
                let now_us = unsafe { esp_timer_get_time() } as u64;
                if now_us.saturating_sub(t0_us) > CAPTURE_MAX_MS * 1000 {
                    log::warn!("[AUDIO] Timeout capture: {} ms", (now_us - t0_us) / 1000);
                    break;
                }

                let end = (total + CHUNK).min(CAPTURE_BYTES);
                let chunk_len = end - total;

                // Fournit un flux TX silencieux pour maintenir l'horloge partagée I2S.
                if let Err(e) = tx.write_all(&silence[..chunk_len], READ_TIMEOUT_TICKS) {
                    log::warn!("[AUDIO] I2S tx clock feed err: {:?}", e);
                    break;
                }

                match rx.read(&mut stereo[total..end], READ_TIMEOUT_TICKS) {
                    Ok(n) if n > 0 => {
                        // Calcul du peak du chunk pour VAD
                        let frames_in_chunk = n / 4;
                        let mut chunk_peak: i32 = 0;
                        for i in 0..frames_in_chunk {
                            let base = total + i * 4;
                            let l = i16::from_le_bytes([stereo[base], stereo[base + 1]]) as i32;
                            let r = i16::from_le_bytes([stereo[base + 2], stereo[base + 3]]) as i32;
                            let p = l.abs().max(r.abs());
                            if p > chunk_peak { chunk_peak = p; }
                        }

                        if chunk_peak >= VAD_VOICE_THRESHOLD {
                            voice_chunks += 1;
                            silence_chunks = 0;
                        } else {
                            silence_chunks += 1;
                        }

                        // Arrêt anticipé : voix suffisante + silence long
                        if voice_chunks >= vad_min_chunks && silence_chunks >= vad_stop_chunks {
                            total += n;
                            let elapsed_ms = (now_us.saturating_sub(t0_us) / 1000) as u32;
                            info!("[AUDIO] VAD: arrêt anticipé à {}ms (voice={} silence={} chunks)",
                                elapsed_ms, voice_chunks, silence_chunks);
                            break;
                        }

                        total += n;
                    }
                    Ok(_) => break,
                    Err(e) => {
                        log::warn!("[AUDIO] I2S read err: {:?}", e);
                        break;
                    }
                }
            }
        }

        self.driver.rx_disable().map_err(|e| anyhow::anyhow!("rx_disable: {:?}", e))?;
        self.driver.tx_disable().map_err(|e| anyhow::anyhow!("tx_disable(capture): {:?}", e))?;
        stereo.truncate(total);
        info!("[AUDIO] {} bytes stéréo bruts", total);

        // Hex dump des 32 premiers bytes bruts : si tout est 0x00, le problème est
        // hardware (pin GPIO39 non connectée ou ES7210 ne sort pas de données I2S).
        if total >= 32 {
            info!(
                "[AUDIO] RAW[0..32]: \
                {:02X}{:02X}{:02X}{:02X} {:02X}{:02X}{:02X}{:02X} \
                {:02X}{:02X}{:02X}{:02X} {:02X}{:02X}{:02X}{:02X} \
                {:02X}{:02X}{:02X}{:02X} {:02X}{:02X}{:02X}{:02X} \
                {:02X}{:02X}{:02X}{:02X} {:02X}{:02X}{:02X}{:02X}",
                stereo[0],stereo[1],stereo[2],stereo[3],
                stereo[4],stereo[5],stereo[6],stereo[7],
                stereo[8],stereo[9],stereo[10],stereo[11],
                stereo[12],stereo[13],stereo[14],stereo[15],
                stereo[16],stereo[17],stereo[18],stereo[19],
                stereo[20],stereo[21],stereo[22],stereo[23],
                stereo[24],stereo[25],stereo[26],stereo[27],
                stereo[28],stereo[29],stereo[30],stereo[31],
            );
        }

        // Auto-détection du canal actif (L ou R) : ES7210 peut câbler le mic
        // sur l'un ou l'autre selon la révision PCB de la carte Waveshare.
        // Frame I2S PCM16LE = [L_lo, L_hi, R_lo, R_hi] (4 bytes)
        let frames = total / 4;
        let mut peak_l: i32 = 0;
        let mut peak_r: i32 = 0;
        for i in 0..frames {
            let l = i16::from_le_bytes([stereo[i * 4], stereo[i * 4 + 1]]) as i32;
            let r = i16::from_le_bytes([stereo[i * 4 + 2], stereo[i * 4 + 3]]) as i32;
            if l.abs() > peak_l { peak_l = l.abs(); }
            if r.abs() > peak_r { peak_r = r.abs(); }
        }
        // Choisir le canal avec le plus de signal. Si les deux sont nuls → L par défaut.
        let use_right = peak_r > peak_l;
        info!(
            "[AUDIO] Canal L peak={} R peak={} → canal choisi: {}",
            peak_l, peak_r,
            if use_right { "R" } else { "L" }
        );

        let mut mono = Vec::with_capacity(frames * 2);
        for i in 0..frames {
            if use_right {
                mono.push(stereo[i * 4 + 2]);
                mono.push(stereo[i * 4 + 3]);
            } else {
                mono.push(stereo[i * 4]);
                mono.push(stereo[i * 4 + 1]);
            }
        }
        info!("[AUDIO] PCM mono : {} bytes", mono.len());
        Ok(mono)
    }

    /// Capture `ms` millisecondes d'audio brut en stéréo PCM16LE.
    ///
    /// Retourne les bytes **stéréo** interleaved [L_lo, L_hi, R_lo, R_hi, …]
    /// sans conversion mono. Utile pour diagnostiquer quel canal transporte le signal.
    /// Taille retournée = ms × SAMPLE_RATE_HZ / 1000 × 4 bytes/frame.
    pub fn capture_raw_stereo(&mut self, ms: u32) -> Result<Vec<u8>> {
        let target_bytes = ((ms as usize) * (SAMPLE_RATE_HZ as usize) / 1000) * 4;
        let timeout_us: u64 = (ms as u64 + 500) * 1000; // +500ms marge
        const CHUNK: usize = 512;
        let silence = [0u8; CHUNK];
        let mut stereo = vec![0u8; target_bytes];
        let mut total = 0usize;

        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable(raw): {:?}", e))?;
        self.driver.rx_enable().map_err(|e| anyhow::anyhow!("rx_enable(raw): {:?}", e))?;

        let t0_us = unsafe { esp_timer_get_time() } as u64;
        {
            let (mut rx, mut tx) = self.driver.split();
            while total < target_bytes {
                if unsafe { esp_timer_get_time() } as u64 - t0_us > timeout_us {
                    break;
                }
                let end = (total + CHUNK).min(target_bytes);
                let chunk_len = end - total;
                if tx.write_all(&silence[..chunk_len], READ_TIMEOUT_TICKS).is_err() {
                    break;
                }
                match rx.read(&mut stereo[total..end], READ_TIMEOUT_TICKS) {
                    Ok(n) if n > 0 => total += n,
                    _ => break,
                }
            }
        }

        self.driver.rx_disable().map_err(|e| anyhow::anyhow!("rx_disable(raw): {:?}", e))?;
        self.driver.tx_disable().map_err(|e| anyhow::anyhow!("tx_disable(raw): {:?}", e))?;
        stereo.truncate(total);
        Ok(stereo)
    }

    /// Capture CAPTURE_MS ms d'audio directement dans un AudioRingBuffer.
    ///
    /// Utile pour écrire continuellement dans un buffer circulaire sans accumuler
    /// la totalité en mémoire. Le ring buffer empêche de déborder et gère FIFO.
    /// Active l'I2S (TX+RX) de façon permanente — à appeler une seule fois.
    ///
    /// Permet d'utiliser `read_stereo_chunk` en boucle sans jamais couper MCLK.
    /// L'ES7210 en mode slave perd sa synchro si MCLK s'arrête entre deux captures.
    pub fn start_continuous(&mut self) -> Result<()> {
        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable(cont): {:?}", e))?;
        self.driver.rx_enable().map_err(|e| anyhow::anyhow!("rx_enable(cont): {:?}", e))?;
        Ok(())
    }

    /// Lit exactement `ms` ms de données stéréo brutes sans activer/désactiver l'I2S.
    ///
    /// Prérequis : `start_continuous()` doit avoir été appelé avant.
    pub fn read_stereo_chunk(&mut self, ms: u32) -> Result<Vec<u8>> {
        let target_bytes = ((ms as usize) * (SAMPLE_RATE_HZ as usize) / 1000) * 4;
        let timeout_us: u64 = (ms as u64 + 500) * 1000;
        const CHUNK: usize = 512;
        let silence = [0u8; CHUNK];
        let mut stereo = vec![0u8; target_bytes];
        let mut total = 0usize;
        let t0_us = unsafe { esp_timer_get_time() } as u64;
        {
            let (mut rx, mut tx) = self.driver.split();
            while total < target_bytes {
                if unsafe { esp_timer_get_time() } as u64 - t0_us > timeout_us {
                    break;
                }
                let end = (total + CHUNK).min(target_bytes);
                let chunk_len = end - total;
                if tx.write_all(&silence[..chunk_len], READ_TIMEOUT_TICKS).is_err() {
                    break;
                }
                match rx.read(&mut stereo[total..end], READ_TIMEOUT_TICKS) {
                    Ok(n) if n > 0 => total += n,
                    _ => break,
                }
            }
        }
        stereo.truncate(total);
        Ok(stereo)
    }

    pub fn capture_to_ring_buffer(&mut self, ring: &mut AudioRingBuffer) -> Result<()> {
        info!("[AUDIO] Capture vers ring buffer {} ms…", CAPTURE_MS);
        let mut stereo = vec![0u8; CAPTURE_BYTES];
        let mut total  = 0usize;
        const CHUNK: usize = 512;
        let t0_us = unsafe { esp_timer_get_time() } as u64;
        let silence = [0u8; CHUNK];

        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable(ring): {:?}", e))?;
        self.driver.rx_enable().map_err(|e| anyhow::anyhow!("rx_enable(ring): {:?}", e))?;

        {
            let (mut rx, mut tx) = self.driver.split();

            while total < CAPTURE_BYTES {
                let now_us = unsafe { esp_timer_get_time() } as u64;
                if now_us.saturating_sub(t0_us) > CAPTURE_MAX_MS * 1000 {
                    log::warn!("[AUDIO] Ring buffer capture timeout: {} ms", (now_us - t0_us) / 1000);
                    break;
                }

                let end = (total + CHUNK).min(CAPTURE_BYTES);
                let chunk_len = end - total;

                if let Err(e) = tx.write_all(&silence[..chunk_len], READ_TIMEOUT_TICKS) {
                    log::warn!("[AUDIO] I2S tx clock feed err (ring): {:?}", e);
                    break;
                }

                match rx.read(&mut stereo[total..end], READ_TIMEOUT_TICKS) {
                    Ok(n) if n > 0 => {
                        // Écrire directement dans le ring buffer (conversion mono L+R→L)
                        for i in 0..n {
                            if i % 4 < 2 {  // Garder que les 2 premiers bytes (canal gauche)
                                let _ = ring.write(&stereo[total + i..=total + i]);
                            }
                        }
                        total += n;
                    },
                    Ok(_) => break,
                    Err(e) => {
                        log::warn!("[AUDIO] I2S read err (ring): {:?}", e);
                        break;
                    }
                }
            }
        }

        self.driver.rx_disable().map_err(|e| anyhow::anyhow!("rx_disable(ring): {:?}", e))?;
        self.driver.tx_disable().map_err(|e| anyhow::anyhow!("tx_disable(ring): {:?}", e))?;
        info!("[AUDIO] Ring buffer: {} bytes stéréo → {} bytes mono disponibles", total, ring.available());
        Ok(())
    }

    /// Lit un flux PCM16LE mono 16 kHz sur le haut-parleur via ES8311.
    ///
    /// Le bus I2S est en stéréo: on duplique chaque sample mono sur L/R.
    pub fn play_pcm_mono(&mut self, pcm_mono: &[u8]) -> Result<()> {
        if pcm_mono.is_empty() {
            return Ok(());
        }

        // Auto-gain: si le signal est faible, on augmente le gain dynamiquement
        // tout en saturant proprement en i16 pour éviter les débordements.
        let mut peak = 0i32;
        for sample in pcm_mono.chunks_exact(2) {
            let s = i16::from_le_bytes([sample[0], sample[1]]) as i32;
            let a = s.abs();
            if a > peak {
                peak = a;
            }
        }
        let adaptive_gain = if peak > 0 {
            (PLAYBACK_TARGET_PEAK / peak)
                .clamp(1, PLAYBACK_MAX_ADAPTIVE_GAIN)
        } else {
            1
        };
        let total_gain = (PLAYBACK_GAIN * adaptive_gain).clamp(1, 8);
        info!(
            "[AUDIO] Playback peak={} adaptive_gain={} total_gain={}",
            peak, adaptive_gain, total_gain
        );

        let mut stereo = Vec::with_capacity((pcm_mono.len() / 2) * 4);
        for sample in pcm_mono.chunks_exact(2) {
            let s = i16::from_le_bytes([sample[0], sample[1]]);
            // Garde une marge de tête pour limiter la distorsion perceptible.
            let boosted = (s as i32 * total_gain)
                .clamp(-28_000, 28_000) as i16;
            let b = boosted.to_le_bytes();
            stereo.extend_from_slice(&b); // L
            stereo.extend_from_slice(&b); // R
        }

        info!("[AUDIO] Lecture {} bytes mono ({} bytes stéréo)", pcm_mono.len(), stereo.len());
        es8311_config_playback_path()?;
        es8311_log_state("pre-playback");
        // Pas de GPIO PA sur cette carte (GPIO_PWR_CTRL=-1, ampli toujours alimenté).
        // GPIO1 est le MUTE (HIGH=muet) — ne jamais l'activer pendant la lecture.
        FreeRtos::delay_ms(10);

        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable: {:?}", e))?;
        self.driver
            .write_all(&stereo, PLAYBACK_TIMEOUT_TICKS)
            .map_err(|e| anyhow::anyhow!("write_all: {:?}", e))?;

        // Laisse le dernier buffer sortir sur I2S avant de couper TX.
        FreeRtos::delay_ms(120);
        self.driver.tx_disable().map_err(|e| anyhow::anyhow!("tx_disable: {:?}", e))?;
        Ok(())
    }

    /// Génère un bip carré local (diagnostic speaker) sans dépendre du serveur.
    pub fn play_test_tone(&mut self, duration_ms: u32) -> Result<()> {
        let samples = ((SAMPLE_RATE_HZ as u64) * (duration_ms as u64) / 1000) as usize;
        if samples == 0 {
            return Ok(());
        }

        let period = (SAMPLE_RATE_HZ / TEST_TONE_HZ).max(2) as usize;
        let half = (period / 2).max(1);
        let mut pcm = Vec::with_capacity(samples * 2);

        for i in 0..samples {
            let v: i16 = if (i % period) < half { 12000 } else { -12000 };
            pcm.extend_from_slice(&v.to_le_bytes());
        }

        info!("[AUDIO] Test tone {} Hz, {} ms", TEST_TONE_HZ, duration_ms);
        self.play_pcm_mono(&pcm)
    }
}

/// Handle pour la lecture audio asynchrone (dans un thread FreeRTOS).
/// 
/// Permet de faire attendre la fin de la lecture sans bloquer le main thread.
pub type AudioPlayHandle = std::thread::JoinHandle<Result<()>>;

/// Wrapper pour rendre MicCapture thread-safe et permettre la lecture asynchrone.
/// 
/// Enveloppe MicCapture dans Arc<Mutex<>> pour permettre l'accès concurrent.
pub struct MicCaptureAsync {
    inner: Arc<Mutex<MicCapture<'static>>>,
}

impl MicCaptureAsync {
    /// Crée un wrapper async autour d'une capture MicCapture existante.
    pub fn new(mic: MicCapture<'static>) -> Self {
        Self {
            inner: Arc::new(Mutex::new(mic)),
        }
    }

    /// Capture audio (bloquant, mais court - quelques secondes).
    pub fn capture(&self) -> Result<Vec<u8>> {
        let mut mic = self.inner.lock().unwrap();
        mic.capture()
    }

    /// Lecture PCM mono asynchrone dans un thread FreeRTOS.
    /// 
    /// Retourne immédiatement avec un handle. Appelle `join()` pour attendre la fin.
    pub fn play_pcm_mono_async(&self, pcm_mono: Vec<u8>) -> Result<AudioPlayHandle> {
        let inner = self.inner.clone();
        
        let handle = thread::Builder::new()
            .stack_size(8192)
            .spawn(move || {
                let mut mic = inner.lock().unwrap();
                mic.play_pcm_mono(&pcm_mono)
            })?;
        
        Ok(handle)
    }

    /// Lecture tone de test asynchrone.
    pub fn play_test_tone_async(&self, duration_ms: u32) -> Result<AudioPlayHandle> {
        let inner = self.inner.clone();
        
        let handle = thread::Builder::new()
            .stack_size(8192)
            .spawn(move || {
                let mut mic = inner.lock().unwrap();
                mic.play_test_tone(duration_ms)
            })?;
        
        Ok(handle)
    }

    /// Capture une fenêtre audio courte (`ms` ms) et retourne du PCM16LE mono.
    ///
    /// Utilisée pour la détection de mot de déclenchement (wake word) : capture
    /// sans VAD, courte durée, canal actif sélectionné automatiquement.
    pub fn capture_window_mono(&self, ms: u32) -> Result<Vec<u8>> {
        let mut mic = self.inner.lock().unwrap();
        let stereo = mic.capture_raw_stereo(ms)?;
        let frames = stereo.len() / 4;
        if frames == 0 { return Ok(Vec::new()); }

        // Sélectionner le canal avec le plus de signal (même logique que capture())
        let mut peak_l: i32 = 0;
        let mut peak_r: i32 = 0;
        for i in 0..frames {
            let l = i16::from_le_bytes([stereo[i * 4], stereo[i * 4 + 1]]) as i32;
            let r = i16::from_le_bytes([stereo[i * 4 + 2], stereo[i * 4 + 3]]) as i32;
            if l.abs() > peak_l { peak_l = l.abs(); }
            if r.abs() > peak_r { peak_r = r.abs(); }
        }
        let use_right = peak_r > peak_l;

        let mut mono = Vec::with_capacity(frames * 2);
        for i in 0..frames {
            if use_right {
                mono.push(stereo[i * 4 + 2]);
                mono.push(stereo[i * 4 + 3]);
            } else {
                mono.push(stereo[i * 4]);
                mono.push(stereo[i * 4 + 1]);
            }
        }
        Ok(mono)
    }
}

// ── Encodage Base64 (RFC 4648) ───────────────────────────────────────────────

const B64: &[u8; 64] =
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Encode `data` en Base64 standard (RFC 4648 avec padding '=').
pub fn base64_encode(data: &[u8]) -> String {
    let mut out = String::with_capacity(((data.len() + 2) / 3) * 4);
    for chunk in data.chunks(3) {
        let b0 = chunk[0];
        let b1 = *chunk.get(1).unwrap_or(&0);
        let b2 = *chunk.get(2).unwrap_or(&0);
        let v  = ((b0 as u32) << 16) | ((b1 as u32) << 8) | (b2 as u32);
        out.push(B64[(v >> 18) as usize] as char);
        out.push(B64[((v >> 12) & 0x3F) as usize] as char);
        out.push(if chunk.len() > 1 { B64[((v >> 6) & 0x3F) as usize] as char } else { '=' });
        out.push(if chunk.len() > 2 { B64[(v & 0x3F) as usize] as char } else { '=' });
    }
    out
}

/// Décode du Base64 RFC 4648 (avec ou sans padding). Ignore les espaces.
pub fn base64_decode(input: &str) -> Result<Vec<u8>> {
    fn map(c: u8) -> Option<u8> {
        match c {
            b'A'..=b'Z' => Some(c - b'A'),
            b'a'..=b'z' => Some(c - b'a' + 26),
            b'0'..=b'9' => Some(c - b'0' + 52),
            b'+' => Some(62),
            b'/' => Some(63),
            _ => None,
        }
    }

    let cleaned: Vec<u8> = input
        .bytes()
        .filter(|b| !b" \n\r\t".contains(b))
        .collect();

    if cleaned.is_empty() {
        return Ok(Vec::new());
    }
    if cleaned.len() % 4 != 0 {
        anyhow::bail!("base64 longueur invalide");
    }

    let mut out = Vec::with_capacity((cleaned.len() / 4) * 3);
    for chunk in cleaned.chunks_exact(4) {
        let c0 = chunk[0];
        let c1 = chunk[1];
        let c2 = chunk[2];
        let c3 = chunk[3];

        let v0 = map(c0).ok_or_else(|| anyhow::anyhow!("base64 invalide"))? as u32;
        let v1 = map(c1).ok_or_else(|| anyhow::anyhow!("base64 invalide"))? as u32;
        let v2 = if c2 == b'=' { 0 } else { map(c2).ok_or_else(|| anyhow::anyhow!("base64 invalide"))? as u32 };
        let v3 = if c3 == b'=' { 0 } else { map(c3).ok_or_else(|| anyhow::anyhow!("base64 invalide"))? as u32 };

        let n = (v0 << 18) | (v1 << 12) | (v2 << 6) | v3;
        out.push(((n >> 16) & 0xFF) as u8);
        if c2 != b'=' {
            out.push(((n >> 8) & 0xFF) as u8);
        }
        if c3 != b'=' {
            out.push((n & 0xFF) as u8);
        }
    }
    Ok(out)
}
