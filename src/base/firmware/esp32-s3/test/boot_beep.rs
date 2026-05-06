use anyhow::Result;
use esp_idf_hal::{
    delay::FreeRtos,
    peripherals::Peripherals,
};
use esp_idf_sys::*;
use log::info;

#[path = "../src/audio/mod.rs"]
mod audio;
#[path = "../src/buffers.rs"]
mod buffers;
#[path = "../src/config/mod.rs"]
mod config;

const I2C_PORT: i2c_port_t = i2c_port_t_I2C_NUM_0;
const I2C_SPEED_HZ: u32 = 400_000;
const I2C_TIMEOUT_TICKS: TickType_t = 100;

const TP_SCL: i32 = 10;
const TP_SDA: i32 = 11;
// IO15 = PA_CTRL = NS4150B SD (HIGH=ampli ON, LOW=shutdown) — schéma Waveshare
const GPIO_PA_CTRL: i32 = 15;
// I2S speaker (schéma Waveshare BOX) :
//   IO02=MCLK  IO48=BCK  IO38=LRCK  IO47=DIN(DAC)  IO15=PA_CTRL

// TCA9554PWR (8-bit I/O expander) register map
// Pins : EXIO_PIN1..EXIO_PIN8 = bits 0..7
const TCA9554_INPUT_REG:  u8 = 0x00;  // read-only
const TCA9554_OUTPUT_REG: u8 = 0x01;
// reg 0x02 = polarity (non utilisé)
const TCA9554_CONFIG_REG: u8 = 0x03;  // 1=input, 0=output

// Pins TCA9554 (bit = pin-1)
const EXIO_TP_RST:  u8 = 0;  // EXIO_PIN1 = bit 0 = touch reset
const EXIO_LCD_RST: u8 = 1;  // EXIO_PIN2 = bit 1 = LCD reset
// NS4150B SD = GPIO1 direct (pas via TCA9554 sur BOX)
// GPIO1 HIGH = ampli ON, LOW = ampli shutdown

unsafe fn tca9554_write_reg(addr: u8, reg: u8, value: u8) -> Result<()> {
    let buf = [reg, value];
    let ret = i2c_master_write_to_device(
        I2C_PORT,
        addr,
        buf.as_ptr(),
        buf.len(),
        I2C_TIMEOUT_TICKS,
    );
    if ret != ESP_OK {
        anyhow::bail!("TCA9554 write reg 0x{:02X} failed: {}", reg, ret);
    }
    Ok(())
}

unsafe fn tca9554_read_reg(addr: u8, reg: u8) -> Result<u8> {
    let mut out = [0u8; 1];
    let ret = i2c_master_write_read_device(
        I2C_PORT,
        addr,
        &reg,
        1,
        out.as_mut_ptr(),
        out.len(),
        I2C_TIMEOUT_TICKS,
    );
    if ret != ESP_OK {
        anyhow::bail!("TCA9554 read reg 0x{:02X} failed: {}", reg, ret);
    }
    Ok(out[0])
}

unsafe fn init_i2c_and_expander() -> Result<u8> {
    let i2c_conf = i2c_config_t {
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

    let ret = i2c_param_config(I2C_PORT, &i2c_conf);
    if ret != ESP_OK {
        anyhow::bail!("i2c_param_config failed: {}", ret);
    }

    let ret = i2c_driver_install(I2C_PORT, i2c_mode_t_I2C_MODE_MASTER, 0, 0, 0);
    if ret != ESP_OK && ret != ESP_ERR_INVALID_STATE {
        anyhow::bail!("i2c_driver_install failed: {}", ret);
    }

    let mut expander_addr: Option<u8> = None;
    for addr in 0x20u8..=0x27u8 {
        let probe = [TCA9554_INPUT_REG];
        let mut v = [0u8; 1];
        let probe_ret = i2c_master_write_read_device(
            I2C_PORT,
            addr,
            probe.as_ptr(),
            probe.len(),
            v.as_mut_ptr(),
            v.len(),
            I2C_TIMEOUT_TICKS,
        );
        if probe_ret == ESP_OK {
            expander_addr = Some(addr);
            break;
        }
    }

    let Some(addr) = expander_addr else {
        anyhow::bail!("TCA9554 not found on I2C (0x20..0x27)");
    };

    // Configurer tous les pins en output (0 = output dans TCA9554)
    tca9554_write_reg(addr, TCA9554_CONFIG_REG, 0x00)?;

    // Reset séquence : TP_RST et LCD_RST LOW puis HIGH
    let mut out = tca9554_read_reg(addr, TCA9554_OUTPUT_REG)?;
    out &= !(1u8 << EXIO_TP_RST);
    out &= !(1u8 << EXIO_LCD_RST);
    tca9554_write_reg(addr, TCA9554_OUTPUT_REG, out)?;
    FreeRtos::delay_ms(20);

    // Remettre tous les pins en HIGH après reset
    out |= 1u8 << EXIO_TP_RST;
    out |= 1u8 << EXIO_LCD_RST;
    out |= 1u8 << 2;  // EXIO_PIN3
    out |= 1u8 << 3;  // EXIO_PIN4
    out |= 1u8 << 4;  // EXIO_PIN5
    out |= 1u8 << 5;  // EXIO_PIN6
    out |= 1u8 << 6;  // EXIO_PIN7
    out |= 1u8 << 7;  // EXIO_PIN8
    tca9554_write_reg(addr, TCA9554_OUTPUT_REG, out)?;
    FreeRtos::delay_ms(120);

    info!("[TEST-BEEP] TCA9554 detecte @0x{:02X} | tous pins HIGH", addr);
    Ok(addr)
}

unsafe fn set_pa_ctrl(level: i32) -> Result<()> {
    let cfg = gpio_config_t {
        pin_bit_mask: 1u64 << GPIO_PA_CTRL,
        mode: gpio_mode_t_GPIO_MODE_OUTPUT,
        pull_up_en: gpio_pullup_t_GPIO_PULLUP_DISABLE,
        pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
        intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
    };
    gpio_config(&cfg);
    gpio_set_level(GPIO_PA_CTRL, level as u32);
    Ok(())
}

unsafe fn set_exio_audio_mask(addr: u8, mask: u8) -> Result<()> {
    let mut out = tca9554_read_reg(addr, TCA9554_OUTPUT_REG)?;

    // Garder TP_RST et LCD_RST au niveau haut pour ne pas perturber la carte.
    out |= 1u8 << EXIO_TP_RST;
    out |= 1u8 << EXIO_LCD_RST;

    // EXIO_PIN3..EXIO_PIN8 (bits 2..7) pilotés par mask
    if (mask & 0b000001) != 0 { out |= 1u8 << 2; } else { out &= !(1u8 << 2); }
    if (mask & 0b000010) != 0 { out |= 1u8 << 3; } else { out &= !(1u8 << 3); }
    if (mask & 0b000100) != 0 { out |= 1u8 << 4; } else { out &= !(1u8 << 4); }
    if (mask & 0b001000) != 0 { out |= 1u8 << 5; } else { out &= !(1u8 << 5); }
    if (mask & 0b010000) != 0 { out |= 1u8 << 6; } else { out &= !(1u8 << 6); }
    if (mask & 0b100000) != 0 { out |= 1u8 << 7; } else { out &= !(1u8 << 7); }

    tca9554_write_reg(addr, TCA9554_OUTPUT_REG, out)?;
    Ok(())
}

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("[TEST-BEEP] boot");

    let peripherals = Peripherals::take()?;

    // Init I2C + TCA9555 : active NS4150B via P1.0=HIGH
    let expander_addr = unsafe { init_i2c_and_expander()? };

    // Init ES8311 DAC (I2S Controller, ES8311 Slave)
    audio::audio_init()?;

    info!("[TEST-BEEP] I2S pins schema: MCLK=2 BCK=48 LRCK=38 DOUT=47 PA_CTRL=15");

    // I2S speaker — pinout schéma Waveshare BOX :
    //   BCK=IO48  LRCK=IO38  DIN(mic)=non câblé  DOUT(DAC)=IO47  MCLK=IO02
    let mut mic = audio::MicCapture::new(
        peripherals.i2s0,
        peripherals.pins.gpio48,  // BCK
        peripherals.pins.gpio38,  // LRCK
        peripherals.pins.gpio4,   // DIN mic — placeholder non câblé (GPIO4 libre, test speaker seulement)
        peripherals.pins.gpio47,  // DOUT → ES8311 DAC
        peripherals.pins.gpio2,   // MCLK
    )?;

    // IO15 = PA_CTRL = NS4150B SD (amplificateur Class D)
    // HIGH = Normal operation (ampli actif), LOW = Shutdown (silence garanti)
    unsafe {
        set_pa_ctrl(1)?;  // GPIO15=HIGH → NS4150B SD=H → ampli ON
    }

    // Tous les EXIO HIGH (rôle exact inconnu sauf TP/LCD reset déjà faits)
    unsafe {
        set_exio_audio_mask(expander_addr, 0b111111)?;
    }

    info!("[TEST-BEEP] GPIO1=HIGH (NS4150B ON) + EXIO ALL HIGH — debut boucle bip");

    let mut even = true;
    loop {
        let freq = if even { 440 } else { 880 };
        info!("[TEST-BEEP] bip {}Hz", freq);
        mic.play_test_tone(1_000)?;
        even = !even;
        FreeRtos::delay_ms(500);
    }
}
