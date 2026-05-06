//! test-beep/src/main.rs — Firmware de diagnostic matériel Waveshare ESP32-S3-Touch-LCD-1.85C-BOX
//!
//! Totalement autonome : aucune dépendance vers le firmware principal.
//! Initialise les codecs ES7210/ES8311 et le haut-parleur, puis joue un bip 440 Hz en boucle.
//!
//! Flash : cargo +esp build --target xtensa-esp32s3-espidf && espflash flash ...

use anyhow::Result;
use esp_idf_hal::{
    delay::FreeRtos,
    gpio::{InputPin, OutputPin},
    i2s::{
        config::{
            Config, DataBitWidth, Role, SlotMode, StdClkConfig, StdConfig, StdGpioConfig,
            StdSlotConfig,
        },
        I2s, I2sBiDir, I2sDriver,
    },
    peripherals::Peripherals,
};
use esp_idf_sys::*;
use log::info;

// ── Constantes hardware Waveshare BOX ───────────────────────────────────────
const I2C_PORT: i2c_port_t = i2c_port_t_I2C_NUM_0;
const I2C_SPEED_HZ: u32 = 400_000;
const I2C_TIMEOUT_TICKS: TickType_t = 100;
const TP_SCL: i32 = 10;
const TP_SDA: i32 = 11;
const GPIO_PA_CTRL: i32 = 15; // NS4150B SD — HIGH = ampli ON

// TCA9554 registers
const TCA9554_OUTPUT_REG: u8 = 0x01;
const TCA9554_CONFIG_REG: u8 = 0x03;

// TCA9554 EXIO pins (bits dans le registre output)
const EXIO_TP_RST: u8 = 0;  // bit 0 = EXIO_PIN1
const EXIO_LCD_RST: u8 = 1; // bit 1 = EXIO_PIN2

// Audio
const SAMPLE_RATE_HZ: u32 = 16_000;
const PLAYBACK_TIMEOUT_TICKS: u32 = 5_000;
const TEST_TONE_HZ: u32 = 440;
const TEST_TONE_VOLUME: i16 = 12_000;

// ── I2C helpers ──────────────────────────────────────────────────────────────

unsafe fn i2c_init() -> Result<()> {
    let conf = i2c_config_t {
        mode: i2c_mode_t_I2C_MODE_MASTER,
        sda_io_num: TP_SDA,
        scl_io_num: TP_SCL,
        sda_pullup_en: true,
        scl_pullup_en: true,
        __bindgen_anon_1: i2c_config_t__bindgen_ty_1 {
            master: i2c_config_t__bindgen_ty_1__bindgen_ty_1 {
                clk_speed: I2C_SPEED_HZ,
            },
        },
        clk_flags: 0,
    };
    let r = i2c_param_config(I2C_PORT, &conf);
    if r != ESP_OK {
        anyhow::bail!("i2c_param_config: {}", r);
    }
    let r = i2c_driver_install(I2C_PORT, i2c_mode_t_I2C_MODE_MASTER, 0, 0, 0);
    if r != ESP_OK && r != ESP_ERR_INVALID_STATE {
        anyhow::bail!("i2c_driver_install: {}", r);
    }
    Ok(())
}

fn i2c_write_reg(dev: u8, reg: u8, val: u8) -> Result<()> {
    let buf = [reg, val];
    let r = unsafe {
        i2c_master_write_to_device(I2C_PORT, dev, buf.as_ptr(), buf.len(), I2C_TIMEOUT_TICKS)
    };
    if r != ESP_OK {
        anyhow::bail!("I2C write 0x{:02X} reg=0x{:02X} err={}", dev, reg, r);
    }
    Ok(())
}

fn i2c_read_reg(dev: u8, reg: u8) -> Result<u8> {
    let mut out = [0u8; 1];
    let r = unsafe {
        i2c_master_write_read_device(
            I2C_PORT,
            dev,
            &reg,
            1,
            out.as_mut_ptr(),
            1,
            I2C_TIMEOUT_TICKS,
        )
    };
    if r != ESP_OK {
        anyhow::bail!("I2C read 0x{:02X} reg=0x{:02X} err={}", dev, reg, r);
    }
    Ok(out[0])
}

// ── TCA9554 (GPIO expander) ──────────────────────────────────────────────────

fn tca9554_find_and_init() -> Result<u8> {
    let mut addr_found: Option<u8> = None;
    for addr in 0x20u8..=0x27u8 {
        if i2c_read_reg(addr, 0x00).is_ok() {
            addr_found = Some(addr);
            break;
        }
    }
    let addr = addr_found.ok_or_else(|| anyhow::anyhow!("TCA9554 introuvable sur I2C (0x20..0x27)"))?;

    // Tous les pins en sortie
    i2c_write_reg(addr, TCA9554_CONFIG_REG, 0x00)?;

    // Reset TP et LCD (LOW), puis tout à HIGH
    let mut out = i2c_read_reg(addr, TCA9554_OUTPUT_REG)?;
    out &= !(1u8 << EXIO_TP_RST);
    out &= !(1u8 << EXIO_LCD_RST);
    i2c_write_reg(addr, TCA9554_OUTPUT_REG, out)?;
    FreeRtos::delay_ms(20);
    i2c_write_reg(addr, TCA9554_OUTPUT_REG, 0xFF)?;
    FreeRtos::delay_ms(120);

    info!("[TEST-BEEP] TCA9554 @0x{:02X} — tous pins HIGH", addr);
    Ok(addr)
}

// ── ES7210 (ADC microphone) ──────────────────────────────────────────────────

const ES7210_ADDR: u8 = 0x40;
const ES7210_SEQ: &[(u8, u8)] = &[
    (0x00, 0xFF),
    (0x01, 0x30),
    (0x02, 0x00),
    (0x03, 0x00),
    (0x06, 0x00),
    (0x07, 0x20),
    (0x11, 0x00),
    (0x12, 0x00),
    (0x40, 0xC3),
    (0x41, 0xC3),
    (0x42, 0x08),
    (0x43, 0x0C),
    (0x44, 0x0C),
    (0x4B, 0x50),
    (0x4C, 0x50),
];

fn es7210_init() -> Result<()> {
    info!("[TEST-BEEP] Init ES7210 @0x{:02X}", ES7210_ADDR);
    for &(reg, val) in ES7210_SEQ {
        i2c_write_reg(ES7210_ADDR, reg, val)?;
        if reg == 0x00 {
            FreeRtos::delay_ms(10);
        }
    }
    info!("[TEST-BEEP] ES7210 OK");
    Ok(())
}

// ── ES8311 (DAC speaker) ─────────────────────────────────────────────────────

const ES8311_ADDR: u8 = 0x18;

const ES8311_SEQ: &[(u8, u8)] = &[
    (0x44, 0x08), (0x44, 0x08),
    (0x01, 0x30), (0x02, 0x00), (0x03, 0x10), (0x16, 0x24),
    (0x04, 0x10), (0x05, 0x00),
    (0x0B, 0x00), (0x0C, 0x00),
    (0x10, 0x1F), (0x11, 0x7F),
    (0x00, 0x80), (0x00, 0x00),
    (0x01, 0x3F), (0x01, 0x3F),
    (0x02, 0x08), (0x05, 0x00), (0x03, 0x10), (0x04, 0x20),
    (0x07, 0x00), (0x08, 0xFF), (0x06, 0x07),
    (0x09, 0x0C), (0x0A, 0x0C),
];

fn es8311_init() -> Result<()> {
    info!("[TEST-BEEP] Init ES8311 @0x{:02X}", ES8311_ADDR);
    for &(reg, val) in ES8311_SEQ {
        i2c_write_reg(ES8311_ADDR, reg, val)?;
        if reg == 0x00 {
            FreeRtos::delay_ms(10);
        }
    }
    // Unmute DAC, volume 0 dB
    i2c_write_reg(ES8311_ADDR, 0x0D, 0x01)?;
    i2c_write_reg(ES8311_ADDR, 0x0E, 0x02)?;
    i2c_write_reg(ES8311_ADDR, 0x12, 0x00)?;
    i2c_write_reg(ES8311_ADDR, 0x13, 0x10)?;
    i2c_write_reg(ES8311_ADDR, 0x14, 0x1A)?;
    i2c_write_reg(ES8311_ADDR, 0x37, 0x08)?;
    i2c_write_reg(ES8311_ADDR, 0x45, 0x00)?;
    i2c_write_reg(ES8311_ADDR, 0x44, 0x58)?;
    let dac31 = i2c_read_reg(ES8311_ADDR, 0x31)? & 0x9F;
    i2c_write_reg(ES8311_ADDR, 0x31, dac31)?;
    i2c_write_reg(ES8311_ADDR, 0x32, 0xBF)?; // 0 dB
    let reg00 = (i2c_read_reg(ES8311_ADDR, 0x00)? & !0x40) | 0x80;
    i2c_write_reg(ES8311_ADDR, 0x00, reg00)?;
    info!("[TEST-BEEP] ES8311 OK");
    Ok(())
}

// ── I2S / haut-parleur ───────────────────────────────────────────────────────

struct Speaker<'d> {
    driver: I2sDriver<'d, I2sBiDir>,
}

impl<'d> Speaker<'d> {
    fn new<I2SP: I2s + 'd>(
        i2s: I2SP,
        bck: impl InputPin + OutputPin + 'd,
        ws: impl InputPin + OutputPin + 'd,
        din: impl InputPin + 'd,
        dout: impl OutputPin + 'd,
        mclk: impl InputPin + OutputPin + 'd,
    ) -> Result<Self> {
        let cfg = StdConfig::new(
            Config::default().role(Role::Controller),
            StdClkConfig::from_sample_rate_hz(SAMPLE_RATE_HZ),
            StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Stereo),
            StdGpioConfig::default(),
        );
        let driver = I2sDriver::<I2sBiDir>::new_std_bidir(i2s, &cfg, bck, din, dout, Some(mclk), ws)
            .map_err(|e| anyhow::anyhow!("I2S init: {:?}", e))?;
        info!("[TEST-BEEP] I2S initialisé (16 kHz stéréo)");
        Ok(Self { driver })
    }

    fn play_pcm_mono(&mut self, pcm_mono: &[u8]) -> Result<()> {
        if pcm_mono.is_empty() {
            return Ok(());
        }
        let mut stereo = Vec::with_capacity((pcm_mono.len() / 2) * 4);
        for chunk in pcm_mono.chunks_exact(2) {
            let s = i16::from_le_bytes([chunk[0], chunk[1]]);
            let b = s.to_le_bytes();
            stereo.extend_from_slice(&b); // L
            stereo.extend_from_slice(&b); // R
        }
        self.driver.tx_enable().map_err(|e| anyhow::anyhow!("tx_enable: {:?}", e))?;
        self.driver
            .write_all(&stereo, PLAYBACK_TIMEOUT_TICKS)
            .map_err(|e| anyhow::anyhow!("write_all: {:?}", e))?;
        FreeRtos::delay_ms(120);
        self.driver.tx_disable().map_err(|e| anyhow::anyhow!("tx_disable: {:?}", e))?;
        Ok(())
    }

    fn play_tone(&mut self, freq_hz: u32, duration_ms: u32) -> Result<()> {
        let samples = ((SAMPLE_RATE_HZ as u64) * (duration_ms as u64) / 1000) as usize;
        if samples == 0 {
            return Ok(());
        }
        let period = (SAMPLE_RATE_HZ / freq_hz).max(2) as usize;
        let half = (period / 2).max(1);
        let mut pcm = Vec::with_capacity(samples * 2);
        for i in 0..samples {
            let v: i16 = if (i % period) < half { TEST_TONE_VOLUME } else { -TEST_TONE_VOLUME };
            pcm.extend_from_slice(&v.to_le_bytes());
        }
        info!("[TEST-BEEP] bip {} Hz, {} ms", freq_hz, duration_ms);
        self.play_pcm_mono(&pcm)
    }
}

// ── Entrée principale ────────────────────────────────────────────────────────

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("[TEST-BEEP] démarrage");

    let peripherals = Peripherals::take()?;

    // Init I2C + GPIO expander
    unsafe { i2c_init()? };
    let _expander = tca9554_find_and_init()?;

    // Init codecs audio
    es7210_init()?;
    es8311_init()?;

    // Ampli ON : GPIO15 HIGH → NS4150B SD=H → haut-parleur actif
    unsafe {
        let pa_cfg = gpio_config_t {
            pin_bit_mask: 1u64 << GPIO_PA_CTRL,
            mode: gpio_mode_t_GPIO_MODE_OUTPUT,
            pull_up_en: gpio_pullup_t_GPIO_PULLUP_DISABLE,
            pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        gpio_config(&pa_cfg);
        gpio_set_level(GPIO_PA_CTRL, 1);
    }
    info!("[TEST-BEEP] GPIO{}=HIGH (PA_CTRL NS4150B ON)", GPIO_PA_CTRL);

    // Init I2S
    let mut speaker = Speaker::new(
        peripherals.i2s0,
        peripherals.pins.gpio48, // BCK
        peripherals.pins.gpio38, // LRCK
        peripherals.pins.gpio4,  // DIN placeholder (non câblé — test speaker uniquement)
        peripherals.pins.gpio47, // DOUT → ES8311
        peripherals.pins.gpio2,  // MCLK
    )?;

    info!("[TEST-BEEP] début boucle bips 440 Hz / 880 Hz");
    let mut toggle = true;
    loop {
        let freq = if toggle { 440 } else { 880 };
        speaker.play_tone(freq, 1_000)?;
        toggle = !toggle;
        FreeRtos::delay_ms(500);
    }
}
