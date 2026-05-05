//! audio/mod.rs — Capture microphone I2S + codec ES7210
//!
//! Matériel (Waveshare ESP32-S3-Touch-LCD-1.85C-BOX v2)
//! ┌─────────────────────────────────────────────────────────┐
//! │  ES7210 ADC (microphone)  I2C addr 0x40                 │
//! │  ES8311 DAC (speaker)     I2C addr 0x18                 │
//! │  I2S bus partagé :                                      │
//! │    BCK  = IO48                                          │
//! │    LRCK = IO38                                          │
//! │    DOUT = IO47  (ESP32 → ES8311 DAC → HP)               │
//! │    DIN  = IO39  (ES7210 ADC mic → ESP32)                │
//! │    MCLK = IO2                                           │
//! │  PA_EN  = IO15  (HIGH = amplificateur activé)           │
//! └─────────────────────────────────────────────────────────┘

use anyhow::Result;
use esp_idf_hal::{
    delay::FreeRtos,
    gpio::{InputPin, OutputPin},
    i2s::{
        config::{Config, DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdGpioConfig, StdSlotConfig},
        I2s, I2sDriver, I2sRx,
    },
};
use esp_idf_sys::*;
use log::info;

// ── GPIO pinout (référence schéma, ne pas modifier) ─────────────────────────
pub const GPIO_PA_EN: i32 = 15;  // Amplificateur speaker (HIGH = on)

// ── Paramètres audio ────────────────────────────────────────────────────────
pub const SAMPLE_RATE_HZ: u32   = 16_000;
pub const CAPTURE_MS:     u32   = 3_000;
/// Frames stéréo (L+R × 16 bits = 4 bytes/frame)
pub const CAPTURE_FRAMES: usize = (SAMPLE_RATE_HZ as usize) * (CAPTURE_MS as usize / 1000);
/// Bytes bruts stéréo
pub const CAPTURE_BYTES:  usize = CAPTURE_FRAMES * 4;

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

// ── ES7210 (ADC microphone) ──────────────────────────────────────────────────
const ES7210_ADDR: u8 = 0x40;

/// Init ES7210 : 16 kHz, 16 bits, I2S standard, mode slave, gain 36 dB.
/// Séquence basée sur le driver espressif/es7210 (ESP-ADF).
const ES7210_SEQ: &[(u8, u8)] = &[
    (0x00, 0xFF), // Reset logiciel (délai 10 ms géré après)
    (0x01, 0x30), // CLK ADC1+ADC2 ON
    (0x02, 0x00), // MCLK depuis broche, diviseur bypass
    (0x03, 0x00), // LRCLK divider bypass
    (0x06, 0x00), // PDM OFF (mic analogique)
    (0x07, 0x20), // MCLK non inversé
    (0x11, 0x00), // I2S std, 16 bits, slave
    (0x12, 0x00), // Port 2 normal
    (0x40, 0xC3), // ADC3+ADC4 enable
    (0x41, 0xC3), // ADC1+ADC2 enable
    (0x42, 0x08), // MIC bias 2.87 V
    (0x43, 0x0C), // ADC1 PGA 36 dB
    (0x44, 0x0C), // ADC2 PGA 36 dB
    (0x4B, 0x50), // Volume numérique L
    (0x4C, 0x50), // Volume numérique R
];

fn es7210_init() -> Result<()> {
    info!("[AUDIO] Init ES7210 0x{:02X}", ES7210_ADDR);
    for &(reg, val) in ES7210_SEQ {
        i2c_write_reg(ES7210_ADDR, reg, val)?;
        if reg == 0x00 { FreeRtos::delay_ms(10); }
    }
    info!("[AUDIO] ES7210 OK");
    Ok(())
}

// ── ES8311 (DAC speaker) ─────────────────────────────────────────────────────
const ES8311_ADDR: u8 = 0x18;

/// Init minimale ES8311 pour lecture TTS (16 kHz, 16 bits, slave).
const ES8311_SEQ: &[(u8, u8)] = &[
    (0x00, 0x1F), (0x01, 0x30), (0x02, 0x00),
    (0x03, 0x10), (0x04, 0x10), (0x05, 0x00),
    (0x06, 0x00), (0x32, 0xBF), (0x44, 0x08),
    (0x45, 0x00), (0x46, 0x0C),
];

fn es8311_init() -> Result<()> {
    info!("[AUDIO] Init ES8311 0x{:02X}", ES8311_ADDR);
    for &(reg, val) in ES8311_SEQ {
        i2c_write_reg(ES8311_ADDR, reg, val)?;
        if reg == 0x00 { FreeRtos::delay_ms(10); }
    }
    pa_disable();
    info!("[AUDIO] ES8311 OK");
    Ok(())
}

pub fn pa_enable()  { unsafe { gpio_set_level(GPIO_PA_EN, 1); } }
pub fn pa_disable() { unsafe { gpio_set_level(GPIO_PA_EN, 0); } }

fn pa_gpio_init() {
    unsafe {
        gpio_reset_pin(GPIO_PA_EN);
        let cfg = gpio_config_t {
            pin_bit_mask: 1u64 << GPIO_PA_EN,
            mode: gpio_mode_t_GPIO_MODE_OUTPUT,
            pull_up_en: gpio_pullup_t_GPIO_PULLUP_DISABLE,
            pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        gpio_config(&cfg);
        gpio_set_level(GPIO_PA_EN, 0);
    }
}

/// Initialise les codecs audio (ES7210 + ES8311 + GPIO PA).
/// Appeler une seule fois, après LcdDisplay::new() (I2C déjà actif).
pub fn audio_init() -> Result<()> {
    pa_gpio_init();
    es7210_init()?;
    es8311_init()?;
    Ok(())
}

// ── MicCapture : capture I2S haut-niveau ────────────────────────────────────

/// Driver I2S RX pour la capture microphone (ES7210 ADC).
///
/// Créer une seule fois dans `main()` et réutiliser à chaque cycle READY.
pub struct MicCapture<'d> {
    driver: I2sDriver<'d, I2sRx>,
}

impl<'d> MicCapture<'d> {
    /// Initialise le périphérique I2S0 en mode RX stéréo 16 kHz.
    ///
    /// Pins :
    ///   bck  = IO48, ws = IO38, din = IO39, mclk = IO2
    pub fn new<I2SP: I2s + 'd>(
        i2s: I2SP,
        bck:  impl InputPin + OutputPin + 'd,
        ws:   impl InputPin + OutputPin + 'd,
        din:  impl InputPin + 'd,
        mclk: impl InputPin + OutputPin + 'd,
    ) -> Result<Self> {
        let cfg = StdConfig::new(
            Config::default(),
            StdClkConfig::from_sample_rate_hz(SAMPLE_RATE_HZ),
            StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Stereo),
            StdGpioConfig::default(),
        );
        let driver = I2sDriver::<I2sRx>::new_std_rx(i2s, &cfg, bck, din, Some(mclk), ws)
            .map_err(|e| anyhow::anyhow!("I2S init: {:?}", e))?;
        info!("[AUDIO] I2S RX initialisé (16 kHz, stéréo)");
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

        self.driver.rx_enable().map_err(|e| anyhow::anyhow!("rx_enable: {:?}", e))?;

        while total < CAPTURE_BYTES {
            let end = (total + CHUNK).min(CAPTURE_BYTES);
            match self.driver.read(&mut stereo[total..end], u32::MAX) {
                Ok(n) if n > 0 => total += n,
                Ok(_) => break,
                Err(e) => {
                    log::warn!("[AUDIO] I2S read err: {:?}", e);
                    break;
                }
            }
        }

        self.driver.rx_disable().map_err(|e| anyhow::anyhow!("rx_disable: {:?}", e))?;
        info!("[AUDIO] {} bytes stéréo bruts", total);

        // Extraction canal gauche (bytes 0-1 de chaque frame L+R de 4 bytes)
        let frames = total / 4;
        let mut mono = Vec::with_capacity(frames * 2);
        for i in 0..frames {
            mono.push(stereo[i * 4]);
            mono.push(stereo[i * 4 + 1]);
        }
        info!("[AUDIO] PCM mono : {} bytes", mono.len());
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
