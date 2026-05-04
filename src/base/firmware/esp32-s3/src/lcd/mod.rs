/// lcd/mod.rs — Driver LCD ST77916 QSPI + touch CST816S (stub)
///
/// Carte : Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN
/// LCD   : 360×360, QSPI 4-bit, contrôleur ST77916
/// Touch : CST816S, I²C (stub pour l'instant)
///
/// Pins réels (source : démo officielle Waveshare ESP-IDF) :
///   QSPI : SCK=40, DATA0=46, DATA1=45, DATA2=42, DATA3=41, CS=21, BL=5
///   RST  : -1 (géré par TCA9554PWR GPIO expander I²C interne)
///   Touch CST816S : SDA=11, SCL=10, INT=4, RST=-1, addr=0x15
///
/// Protocole QSPI ST77916 :
///   Write cmd  : opcode 0x02 → commande = (0x02<<24)|(cmd<<8)
///   Write color: opcode 0x32 → commande = (0x32<<24)|(0x2C<<8) pour RAMWR

pub mod ui;

use anyhow::Result;
use esp_idf_hal::delay::FreeRtos;
use esp_idf_sys::*;
use log::{info, warn};
use crate::touch::CST816S;

pub const LCD_W: u16 = 360;
pub const LCD_H: u16 = 360;

// Couleurs RGB565
pub const COLOR_BLACK:  u16 = 0x0000;
pub const COLOR_WHITE:  u16 = 0xFFFF;
pub const COLOR_GREEN:  u16 = 0x07E0;
pub const COLOR_RED:    u16 = 0xF800;
pub const COLOR_BLUE:   u16 = 0x001F;
pub const COLOR_GRAY:   u16 = 0x8410;
pub const COLOR_ORANGE: u16 = 0xFD20;

// Opcodes QSPI ST77916
const OPCODE_WRITE_CMD:   u32 = 0x02;
const OPCODE_READ_CMD:    u32 = 0x0B;
const OPCODE_WRITE_COLOR: u32 = 0x32;
const LCD_CMD_RAMWR:      u8  = 0x2C;
const LCD_CMD_RAMWRC:     u8  = 0x3C;

// Pins QSPI LCD (Waveshare officiel)
const LCD_SCK:   i32 = 40;
const LCD_DATA0: i32 = 46;  // mosi
const LCD_DATA1: i32 = 45;
const LCD_DATA2: i32 = 42;
const LCD_DATA3: i32 = 41;
const LCD_CS:    i32 = 21;
const LCD_BL:    i32 = 5;
const LCD_TE:    i32 = 18;
const TP_INT:    i32 = 4;
const TP_SCL:    i32 = 10;
const TP_SDA:    i32 = 11;

// RST via GPIO expander I²C TCA9554PWR
const EXIO_TP_RST: u8 = 1;   // Extend IO1
const EXIO_LCD_RST: u8 = 2;  // Extend IO2

const I2C_PORT: i2c_port_t = i2c_port_t_I2C_NUM_0;
const I2C_SPEED_HZ: u32 = 400_000;
const I2C_TIMEOUT_TICKS: TickType_t = 100;

// TCA9554 registers
const TCA9554_REG_INPUT: u8 = 0x00;
const TCA9554_REG_OUTPUT: u8 = 0x01;
const TCA9554_REG_CONFIG: u8 = 0x03;

// SPI2_HOST = 1
const SPI_HOST_ID: spi_host_device_t = spi_host_device_t_SPI2_HOST;

// Résultat d'un toucher
pub use crate::touch::TouchPoint;

/// Pilote LCD ST77916 QSPI 4-bit
pub struct LcdDisplay {
    io: esp_lcd_panel_io_handle_t,
}

impl LcdDisplay {
    /// Initialise le LCD ST77916 via QSPI et affiche l'écran en bleu.
    pub fn new() -> Result<Self> {
        unsafe { Self::init_qspi() }
    }

    unsafe fn init_qspi() -> Result<Self> {
        // 0. Touch I2C + reset lines via TCA9554 (Extend IO1/2)
        Self::init_touch_i2c_and_reset_lines()?;

        // 1. Rétroéclairage ON (GPIO 5)
        let bl_mask: u64 = 1u64 << LCD_BL;
        let bl_cfg = gpio_config_t {
            pin_bit_mask: bl_mask,
            mode: gpio_mode_t_GPIO_MODE_OUTPUT,
            pull_up_en: gpio_pullup_t_GPIO_PULLUP_DISABLE,
            pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        gpio_config(&bl_cfg);
        gpio_set_level(LCD_BL, 1);

        // TP_INT (IO4) en entrée, aligné avec le schéma
        let tp_int_cfg = gpio_config_t {
            pin_bit_mask: 1u64 << TP_INT,
            mode: gpio_mode_t_GPIO_MODE_INPUT,
            pull_up_en: gpio_pullup_t_GPIO_PULLUP_ENABLE,
            pull_down_en: gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        gpio_config(&tp_int_cfg);

        // LCD_TE est routé sur IO18 (lecture TE non utilisée pour l'instant)
        let _ = LCD_TE;

        // 2. Bus SPI QSPI (DATA0=46, DATA1=45, SCK=40, DATA2=42, DATA3=41)
        let bus_cfg = spi_bus_config_t {
            flags: SPICOMMON_BUSFLAG_MASTER,
            sclk_io_num: LCD_SCK,
            data4_io_num: -1,
            data5_io_num: -1,
            data6_io_num: -1,
            data7_io_num: -1,
            __bindgen_anon_1: spi_bus_config_t__bindgen_ty_1 { mosi_io_num: LCD_DATA0 },
            __bindgen_anon_2: spi_bus_config_t__bindgen_ty_2 { miso_io_num: LCD_DATA1 },
            __bindgen_anon_3: spi_bus_config_t__bindgen_ty_3 { quadwp_io_num: LCD_DATA2 },
            __bindgen_anon_4: spi_bus_config_t__bindgen_ty_4 { quadhd_io_num: LCD_DATA3 },
            max_transfer_sz: (LCD_W as i32) * (LCD_H as i32) * 2,
            ..Default::default()
        };
        let ret = spi_bus_initialize(SPI_HOST_ID, &bus_cfg, spi_common_dma_t_SPI_DMA_CH_AUTO);
        if ret != ESP_OK {
            anyhow::bail!("spi_bus_initialize failed: {}", ret);
        }

        // 3. Panel IO QSPI — mode quad, cmd 32 bits, param 8 bits
        let mut io: esp_lcd_panel_io_handle_t = core::ptr::null_mut();
        let mut io_cfg = esp_lcd_panel_io_spi_config_t {
            cs_gpio_num: LCD_CS,
            dc_gpio_num: -1,
            spi_mode: 0,
            pclk_hz: 40_000_000,
            trans_queue_depth: 10,
            on_color_trans_done: None,
            user_ctx: core::ptr::null_mut(),
            lcd_cmd_bits: 32,
            lcd_param_bits: 8,
            flags: Default::default(),
        };
        io_cfg.flags.set_quad_mode(1);

        let ret = esp_lcd_new_panel_io_spi(SPI_HOST_ID as _, &io_cfg, &mut io);
        if ret != ESP_OK {
            anyhow::bail!("esp_lcd_new_panel_io_spi failed: {}", ret);
        }

        let mut lcd = LcdDisplay { io };

        // 4. Software reset + 120 ms
        lcd.send_cmd(0x01, &[])?;
        FreeRtos::delay_ms(120);

        // 5. MADCTL + COLMOD RGB565
        // Try MADCTL = 0x00 (standard mode)
        lcd.send_cmd(0x36, &[0x00])?;
        lcd.send_cmd(0x3A, &[0x55])?;

        // 6. Lecture registre ID (0x04) et choix strict de la séquence vendor.
        let panel_id = match lcd.read_cmd_4(0x04) {
            Ok(id) => {
                info!(
                    "ST77916 reg 0x04: {:02X} {:02X} {:02X} {:02X}",
                    id[0], id[1], id[2], id[3]
                );
                id
            }
            Err(e) => {
                warn!("Lecture reg 0x04 impossible (fallback default): {e}");
                [0x00, 0x7F, 0x7F, 0x7F]
            }
        };
        lcd.st77916_vendor_init(panel_id)?;

        // 7. DISPON supplémentaire par sécurité
        lcd.send_cmd(0x29, &[])?;

        // 8. Écran bleu pour valider
        lcd.fill(COLOR_BLUE)?;

        info!("LCD ST77916 QSPI initialisé ({}×{})", LCD_W, LCD_H);
        Ok(lcd)
    }

    unsafe fn init_touch_i2c_and_reset_lines() -> Result<()> {
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

        // Cherche le TCA9554 sur l'intervalle standard 0x20..0x27
        let mut expander_addr: Option<u8> = None;
        for addr in 0x20u8..=0x27u8 {
            let probe = [TCA9554_REG_INPUT];
            let mut v = [0u8; 1];
            let ret = i2c_master_write_read_device(
                I2C_PORT,
                addr,
                probe.as_ptr(),
                probe.len(),
                v.as_mut_ptr(),
                v.len(),
                I2C_TIMEOUT_TICKS,
            );
            if ret == ESP_OK {
                expander_addr = Some(addr);
                break;
            }
        }

        let Some(addr) = expander_addr else {
            anyhow::bail!("TCA9554 not found on I2C (0x20..0x27)");
        };

        // Place EXIO1/EXIO2 en sortie et pulse reset bas -> haut
        let mut cfg = Self::tca9554_read_reg(addr, TCA9554_REG_CONFIG)?;
        cfg &= !(1u8 << EXIO_TP_RST);
        cfg &= !(1u8 << EXIO_LCD_RST);
        Self::tca9554_write_reg(addr, TCA9554_REG_CONFIG, cfg)?;

        let mut out = Self::tca9554_read_reg(addr, TCA9554_REG_OUTPUT)?;
        out &= !(1u8 << EXIO_TP_RST);
        out &= !(1u8 << EXIO_LCD_RST);
        Self::tca9554_write_reg(addr, TCA9554_REG_OUTPUT, out)?;
        FreeRtos::delay_ms(20);

        out |= 1u8 << EXIO_TP_RST;
        out |= 1u8 << EXIO_LCD_RST;
        Self::tca9554_write_reg(addr, TCA9554_REG_OUTPUT, out)?;
        FreeRtos::delay_ms(120);

        info!("TCA9554 détecté @0x{:02X}, TP_RST=EXIO1 et LCD_RST=EXIO2 appliqués", addr);
        Ok(())
    }

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
        let mut value = [0u8; 1];
        let reg_sel = [reg];
        let ret = i2c_master_write_read_device(
            I2C_PORT,
            addr,
            reg_sel.as_ptr(),
            reg_sel.len(),
            value.as_mut_ptr(),
            value.len(),
            I2C_TIMEOUT_TICKS,
        );
        if ret != ESP_OK {
            anyhow::bail!("TCA9554 read reg 0x{:02X} failed: {}", reg, ret);
        }
        Ok(value[0])
    }

    // ----------------------------------------------------------------
    // Envoi commande / pixels (QSPI)
    // ----------------------------------------------------------------

    fn send_cmd(&self, cmd: u8, data: &[u8]) -> Result<()> {
        // Encodage QSPI : (opcode_cmd << 24) | (cmd << 8)
        let qcmd = (OPCODE_WRITE_CMD << 24) | ((cmd as u32) << 8);
        let ret = unsafe {
            esp_lcd_panel_io_tx_param(
                self.io,
                qcmd as i32,
                if data.is_empty() { core::ptr::null() } else { data.as_ptr() as *const _ },
                data.len(),
            )
        };
        if ret != ESP_OK {
            anyhow::bail!("send_cmd 0x{:02X} failed: {}", cmd, ret);
        }
        Ok(())
    }

    fn read_cmd_4(&self, cmd: u8) -> Result<[u8; 4]> {
        // Encodage QSPI lecture : (opcode_read << 24) | (cmd << 8)
        let qcmd = (OPCODE_READ_CMD << 24) | ((cmd as u32) << 8);
        let mut out = [0u8; 4];
        let ret = unsafe {
            esp_lcd_panel_io_rx_param(
                self.io,
                qcmd as i32,
                out.as_mut_ptr() as *mut _,
                out.len(),
            )
        };
        if ret != ESP_OK {
            anyhow::bail!("read_cmd_4 0x{:02X} failed: {}", cmd, ret);
        }
        Ok(out)
    }

    /// Envoie des pixels bruts RGB565 big-endian pour la fenêtre déjà définie.
    /// `continue_write=false` utilise RAMWR (début), puis RAMWRC (continue) sinon.
    fn send_pixels(&self, data: &[u8], continue_write: bool) -> Result<()> {
        let ram_cmd = if continue_write { LCD_CMD_RAMWRC } else { LCD_CMD_RAMWR };
        // Use OPCODE_WRITE_COLOR (0x32) for pixel data after RAMWR command
        let qcmd = (OPCODE_WRITE_COLOR << 24) | ((ram_cmd as u32) << 8);
        let ret = unsafe {
            esp_lcd_panel_io_tx_color(
                self.io,
                qcmd as i32,
                data.as_ptr() as *const _,
                data.len(),
            )
        };
        if ret != ESP_OK {
            anyhow::bail!("send_pixels failed: {}", ret);
        }
        Ok(())
    }

    /// Synchronise la file des transferts couleur (tx_color asynchrone).
    /// Envoie un NOP (cmd=0x00) pour forcer l'attente de fin des tx_color en cours.
    fn wait_color_done(&self) -> Result<()> {
        // (OPCODE_WRITE_CMD<<24)|(0x00<<8) = 0x02000000 = NOP valide en QSPI
        let nop_qcmd = (OPCODE_WRITE_CMD << 24) as i32;
        let ret = unsafe { esp_lcd_panel_io_tx_param(self.io, nop_qcmd, core::ptr::null(), 0) };
        if ret != ESP_OK {
            anyhow::bail!("wait_color_done failed: {}", ret);
        }
        Ok(())
    }

    // ----------------------------------------------------------------
    // Fenêtre d'adresse + remplissage
    // ----------------------------------------------------------------

    fn set_window(&self, x0: u16, y0: u16, x1: u16, y1: u16) -> Result<()> {
        // CASET: Column Address Set (0x2A)
        self.send_cmd(0x2A, &[
            (x0 >> 8) as u8, (x0 & 0xFF) as u8,
            (x1 >> 8) as u8, (x1 & 0xFF) as u8,
        ])?;
        // RASET: Row Address Set (0x2B)
        self.send_cmd(0x2B, &[
            (y0 >> 8) as u8, (y0 & 0xFF) as u8,
            (y1 >> 8) as u8, (y1 & 0xFF) as u8,
        ])?;
        Ok(())
    }

    /// Remplit un rectangle avec une couleur RGB565.
    /// Une ligne à la fois : set_window(1 ligne) + UN seul send_pixels (RAMWR).
    /// Ceci évite les multiples RAMWR sur la même fenêtre (RAMWR remet le curseur à (x0,y0)).
    pub fn fill_rect(&mut self, x: u16, y: u16, w: u16, h: u16, color: u16) -> Result<()> {
        if w == 0 || h == 0 { return Ok(()); }
        let hi = (color >> 8) as u8;
        let lo = color as u8;
        let row_bytes = w as usize * 2;
        let mut row_buf = vec![0u8; row_bytes];
        for i in (0..row_bytes).step_by(2) {
            row_buf[i]     = hi;
            row_buf[i + 1] = lo;
        }
        let x1 = x + w - 1;
        for row in 0..h {
            let y_row = y + row;
            self.set_window(x, y_row, x1, y_row)?;
            self.send_pixels(&row_buf, false)?;  // RAMWR unique par ligne
        }
        self.wait_color_done()?;
        Ok(())
    }

    /// Efface tout l'écran avec la couleur donnée.
    pub fn fill(&mut self, color: u16) -> Result<()> {
        self.fill_rect(0, 0, LCD_W, LCD_H, color)
    }

    /// Dessine un bandeau coloré sur toute la largeur.
    pub fn draw_banner(&mut self, y: u16, h: u16, color: u16) -> Result<()> {
        self.fill_rect(0, y, LCD_W, h, color)
    }

    // ----------------------------------------------------------------
    // Touch CST816S
    // ----------------------------------------------------------------
    pub fn read_touch(&mut self) -> Option<TouchPoint> {
        CST816S::read_touch()
    }

    // ----------------------------------------------------------------
    // Séquence d'init vendor ST77916 (source : Waveshare ESP-IDF demo)
    // vendor_specific_init_default — commandes non commentées
    // ----------------------------------------------------------------

    fn st77916_vendor_init(&mut self, panel_id: [u8; 4]) -> Result<()> {
        #[rustfmt::skip]
        let seq_new: &[(u8, &[u8], u32)] = &[
            (0xF0, &[0x28], 0), (0xF2, &[0x28], 0), (0x73, &[0xF0], 0),
            (0x7C, &[0xD1], 0), (0x83, &[0xE0], 0), (0x84, &[0x61], 0),
            (0xF2, &[0x82], 0), (0xF0, &[0x00], 0), (0xF0, &[0x01], 0),
            (0xF1, &[0x01], 0),
            (0xB0, &[0x56], 0), (0xB1, &[0x4D], 0), (0xB2, &[0x24], 0),
            (0xB4, &[0x87], 0), (0xB5, &[0x44], 0), (0xB6, &[0x8B], 0),
            (0xB7, &[0x40], 0), (0xB8, &[0x86], 0), (0xBA, &[0x00], 0),
            (0xBB, &[0x08], 0), (0xBC, &[0x08], 0), (0xBD, &[0x00], 0),
            (0xC0, &[0x80], 0), (0xC1, &[0x10], 0), (0xC2, &[0x37], 0),
            (0xC3, &[0x80], 0), (0xC4, &[0x10], 0), (0xC5, &[0x37], 0),
            (0xC6, &[0xA9], 0), (0xC7, &[0x41], 0), (0xC8, &[0x01], 0),
            (0xC9, &[0xA9], 0), (0xCA, &[0x41], 0), (0xCB, &[0x01], 0),
            (0xD0, &[0x91], 0), (0xD1, &[0x68], 0), (0xD2, &[0x68], 0),
            (0xF5, &[0x00, 0xA5], 0), (0xDD, &[0x4F], 0), (0xDE, &[0x4F], 0),
            (0xF1, &[0x10], 0), (0xF0, &[0x00], 0), (0xF0, &[0x02], 0),
            (0xE0, &[0xF0,0x0A,0x10,0x09,0x09,0x36,0x35,0x33,0x4A,0x29,0x15,0x15,0x2E,0x34], 0),
            (0xE1, &[0xF0,0x0A,0x0F,0x08,0x08,0x05,0x34,0x33,0x4A,0x39,0x15,0x15,0x2D,0x33], 0),
            (0xF0, &[0x10], 0), (0xF3, &[0x10], 0),
            (0xE0, &[0x07], 0), (0xE1, &[0x00], 0), (0xE2, &[0x00], 0),
            (0xE3, &[0x00], 0), (0xE4, &[0xE0], 0), (0xE5, &[0x06], 0),
            (0xE6, &[0x21], 0), (0xE7, &[0x01], 0), (0xE8, &[0x05], 0),
            (0xE9, &[0x02], 0), (0xEA, &[0xDA], 0), (0xEB, &[0x00], 0),
            (0xEC, &[0x00], 0), (0xED, &[0x0F], 0), (0xEE, &[0x00], 0),
            (0xEF, &[0x00], 0), (0xF8, &[0x00], 0), (0xF9, &[0x00], 0),
            (0xFA, &[0x00], 0), (0xFB, &[0x00], 0), (0xFC, &[0x00], 0),
            (0xFD, &[0x00], 0), (0xFE, &[0x00], 0), (0xFF, &[0x00], 0),
            (0x60, &[0x40], 0), (0x61, &[0x04], 0), (0x62, &[0x00], 0),
            (0x63, &[0x42], 0), (0x64, &[0xD9], 0), (0x65, &[0x00], 0),
            (0x66, &[0x00], 0), (0x67, &[0x00], 0), (0x68, &[0x00], 0),
            (0x69, &[0x00], 0), (0x6A, &[0x00], 0), (0x6B, &[0x00], 0),
            (0x70, &[0x40], 0), (0x71, &[0x03], 0), (0x72, &[0x00], 0),
            (0x73, &[0x42], 0), (0x74, &[0xD8], 0), (0x75, &[0x00], 0),
            (0x76, &[0x00], 0), (0x77, &[0x00], 0), (0x78, &[0x00], 0),
            (0x79, &[0x00], 0), (0x7A, &[0x00], 0), (0x7B, &[0x00], 0),
            (0x80, &[0x48], 0), (0x81, &[0x00], 0), (0x82, &[0x06], 0),
            (0x83, &[0x02], 0), (0x84, &[0xD6], 0), (0x85, &[0x04], 0),
            (0x86, &[0x00], 0), (0x87, &[0x00], 0), (0x88, &[0x48], 0),
            (0x89, &[0x00], 0), (0x8A, &[0x08], 0), (0x8B, &[0x02], 0),
            (0x8C, &[0xD8], 0), (0x8D, &[0x04], 0), (0x8E, &[0x00], 0),
            (0x8F, &[0x00], 0), (0x90, &[0x48], 0), (0x91, &[0x00], 0),
            (0x92, &[0x0A], 0), (0x93, &[0x02], 0), (0x94, &[0xDA], 0),
            (0x95, &[0x04], 0), (0x96, &[0x00], 0), (0x97, &[0x00], 0),
            (0x98, &[0x48], 0), (0x99, &[0x00], 0), (0x9A, &[0x0C], 0),
            (0x9B, &[0x02], 0), (0x9C, &[0xDC], 0), (0x9D, &[0x04], 0),
            (0x9E, &[0x00], 0), (0x9F, &[0x00], 0), (0xA0, &[0x48], 0),
            (0xA1, &[0x00], 0), (0xA2, &[0x05], 0), (0xA3, &[0x02], 0),
            (0xA4, &[0xD5], 0), (0xA5, &[0x04], 0), (0xA6, &[0x00], 0),
            (0xA7, &[0x00], 0), (0xA8, &[0x48], 0), (0xA9, &[0x00], 0),
            (0xAA, &[0x07], 0), (0xAB, &[0x02], 0), (0xAC, &[0xD7], 0),
            (0xAD, &[0x04], 0), (0xAE, &[0x00], 0), (0xAF, &[0x00], 0),
            (0xB0, &[0x48], 0), (0xB1, &[0x00], 0), (0xB2, &[0x09], 0),
            (0xB3, &[0x02], 0), (0xB4, &[0xD9], 0), (0xB5, &[0x04], 0),
            (0xB6, &[0x00], 0), (0xB7, &[0x00], 0), (0xB8, &[0x48], 0),
            (0xB9, &[0x00], 0), (0xBA, &[0x0B], 0), (0xBB, &[0x02], 0),
            (0xBC, &[0xDB], 0), (0xBD, &[0x04], 0), (0xBE, &[0x00], 0),
            (0xBF, &[0x00], 0), (0xC0, &[0x10], 0), (0xC1, &[0x47], 0),
            (0xC2, &[0x56], 0), (0xC3, &[0x65], 0), (0xC4, &[0x74], 0),
            (0xC5, &[0x88], 0), (0xC6, &[0x99], 0), (0xC7, &[0x01], 0),
            (0xC8, &[0xBB], 0), (0xC9, &[0xAA], 0), (0xD0, &[0x10], 0),
            (0xD1, &[0x47], 0), (0xD2, &[0x56], 0), (0xD3, &[0x65], 0),
            (0xD4, &[0x74], 0), (0xD5, &[0x88], 0), (0xD6, &[0x99], 0),
            (0xD7, &[0x01], 0), (0xD8, &[0xBB], 0), (0xD9, &[0xAA], 0),
            (0xF3, &[0x01], 0), (0xF0, &[0x00], 0),
            (0x21, &[0x00], 0), (0x11, &[0x00], 120), (0x29, &[0x00], 0),
        ];

        #[rustfmt::skip]
        let seq_default: &[(u8, &[u8], u32)] = &[
            // cmd, data, delay_ms
            (0xF0, &[0x28], 0), (0xF2, &[0x28], 0),
            (0x7C, &[0xD1], 0), (0x83, &[0xE0], 0), (0x84, &[0x61], 0),
            (0xF2, &[0x82], 0), (0xF0, &[0x00], 0), (0xF0, &[0x01], 0),
            (0xF1, &[0x01], 0),
            (0xB0, &[0x49], 0), (0xB1, &[0x4A], 0), (0xB2, &[0x1F], 0),
            (0xB4, &[0x46], 0), (0xB5, &[0x34], 0), (0xB6, &[0xD5], 0),
            (0xB7, &[0x30], 0), (0xB8, &[0x04], 0), (0xBA, &[0x00], 0),
            (0xBB, &[0x08], 0), (0xBC, &[0x08], 0), (0xBD, &[0x00], 0),
            (0xC0, &[0x80], 0), (0xC1, &[0x10], 0), (0xC2, &[0x37], 0),
            (0xC3, &[0x80], 0), (0xC4, &[0x10], 0), (0xC5, &[0x37], 0),
            (0xC6, &[0xA9], 0), (0xC7, &[0x41], 0), (0xC8, &[0x01], 0),
            (0xC9, &[0xA9], 0), (0xCA, &[0x41], 0), (0xCB, &[0x01], 0),
            (0xD0, &[0x91], 0), (0xD1, &[0x68], 0), (0xD2, &[0x68], 0),
            (0xF5, &[0x00, 0xA5], 0),
            (0xF1, &[0x10], 0), (0xF0, &[0x00], 0), (0xF0, &[0x02], 0),
            (0xE0, &[0x70,0x09,0x12,0x0C,0x0B,0x27,0x38,0x54,0x4E,0x19,0x15,0x15,0x2C,0x2F], 0),
            (0xE1, &[0x70,0x08,0x11,0x0C,0x0B,0x27,0x38,0x43,0x4C,0x18,0x14,0x14,0x2B,0x2D], 0),
            (0xF0, &[0x10], 0), (0xF3, &[0x10], 0),
            (0xE0, &[0x08], 0), (0xE1, &[0x00], 0), (0xE2, &[0x0B], 0),
            (0xE3, &[0x00], 0), (0xE4, &[0xE0], 0), (0xE5, &[0x06], 0),
            (0xE6, &[0x21], 0), (0xE7, &[0x00], 0), (0xE8, &[0x05], 0),
            (0xE9, &[0x82], 0), (0xEA, &[0xDF], 0), (0xEB, &[0x89], 0),
            (0xEC, &[0x20], 0), (0xED, &[0x14], 0), (0xEE, &[0xFF], 0),
            (0xEF, &[0x00], 0), (0xF8, &[0xFF], 0), (0xF9, &[0x00], 0),
            (0xFA, &[0x00], 0), (0xFB, &[0x30], 0), (0xFC, &[0x00], 0),
            (0xFD, &[0x00], 0), (0xFE, &[0x00], 0), (0xFF, &[0x00], 0),
            (0x60, &[0x42], 0), (0x61, &[0xE0], 0), (0x62, &[0x40], 0),
            (0x63, &[0x40], 0), (0x64, &[0x02], 0), (0x65, &[0x00], 0),
            (0x66, &[0x40], 0), (0x67, &[0x03], 0), (0x68, &[0x00], 0),
            (0x69, &[0x00], 0), (0x6A, &[0x00], 0), (0x6B, &[0x00], 0),
            (0x70, &[0x42], 0), (0x71, &[0xE0], 0), (0x72, &[0x40], 0),
            (0x73, &[0x40], 0), (0x74, &[0x02], 0), (0x75, &[0x00], 0),
            (0x76, &[0x40], 0), (0x77, &[0x03], 0), (0x78, &[0x00], 0),
            (0x79, &[0x00], 0), (0x7A, &[0x00], 0), (0x7B, &[0x00], 0),
            (0x80, &[0x38], 0), (0x81, &[0x00], 0), (0x82, &[0x04], 0),
            (0x83, &[0x02], 0), (0x84, &[0xDC], 0), (0x85, &[0x00], 0),
            (0x86, &[0x00], 0), (0x87, &[0x00], 0), (0x88, &[0x38], 0),
            (0x89, &[0x00], 0), (0x8A, &[0x06], 0), (0x8B, &[0x02], 0),
            (0x8C, &[0xDE], 0), (0x8D, &[0x00], 0), (0x8E, &[0x00], 0),
            (0x8F, &[0x00], 0), (0x90, &[0x38], 0), (0x91, &[0x00], 0),
            (0x92, &[0x08], 0), (0x93, &[0x02], 0), (0x94, &[0xE0], 0),
            (0x95, &[0x00], 0), (0x96, &[0x00], 0), (0x97, &[0x00], 0),
            (0x98, &[0x38], 0), (0x99, &[0x00], 0), (0x9A, &[0x0A], 0),
            (0x9B, &[0x02], 0), (0x9C, &[0xE2], 0), (0x9D, &[0x00], 0),
            (0x9E, &[0x00], 0), (0x9F, &[0x00], 0), (0xA0, &[0x38], 0),
            (0xA1, &[0x00], 0), (0xA2, &[0x03], 0), (0xA3, &[0x02], 0),
            (0xA4, &[0xDB], 0), (0xA5, &[0x00], 0), (0xA6, &[0x00], 0),
            (0xA7, &[0x00], 0), (0xA8, &[0x38], 0), (0xA9, &[0x00], 0),
            (0xAA, &[0x05], 0), (0xAB, &[0x02], 0), (0xAC, &[0xDD], 0),
            (0xAD, &[0x00], 0), (0xAE, &[0x00], 0), (0xAF, &[0x00], 0),
            (0xB0, &[0x38], 0), (0xB1, &[0x00], 0), (0xB2, &[0x07], 0),
            (0xB3, &[0x02], 0), (0xB4, &[0xDF], 0), (0xB5, &[0x00], 0),
            (0xB6, &[0x00], 0), (0xB7, &[0x00], 0), (0xB8, &[0x38], 0),
            (0xB9, &[0x00], 0), (0xBA, &[0x09], 0), (0xBB, &[0x02], 0),
            (0xBC, &[0xE1], 0), (0xBD, &[0x00], 0), (0xBE, &[0x00], 0),
            (0xBF, &[0x00], 0), (0xC0, &[0x22], 0), (0xC1, &[0xAA], 0),
            (0xC2, &[0x65], 0), (0xC3, &[0x74], 0), (0xC4, &[0x47], 0),
            (0xC5, &[0x56], 0), (0xC6, &[0x00], 0), (0xC7, &[0x88], 0),
            (0xC8, &[0x99], 0), (0xC9, &[0x33], 0), (0xD0, &[0x11], 0),
            (0xD1, &[0xAA], 0), (0xD2, &[0x65], 0), (0xD3, &[0x74], 0),
            (0xD4, &[0x47], 0), (0xD5, &[0x56], 0), (0xD6, &[0x00], 0),
            (0xD7, &[0x88], 0), (0xD8, &[0x99], 0), (0xD9, &[0x33], 0),
            (0xF3, &[0x01], 0), (0xF0, &[0x00], 0),
            (0x21, &[], 0),     // INVON
            (0x11, &[], 120),   // SLPOUT + 120 ms
            (0x29, &[], 0),     // DISPON
        ];

        let seq = if panel_id == [0x00, 0x7F, 0x7F, 0x7F] {
            info!(
                "ST77916: ID {:02X} {:02X} {:02X} {:02X} → vendor_specific_init_default",
                panel_id[0], panel_id[1], panel_id[2], panel_id[3]
            );
            seq_default
        } else {
            info!(
                "ST77916: ID {:02X} {:02X} {:02X} {:02X} → vendor_specific_init_new (optimized)",
                panel_id[0], panel_id[1], panel_id[2], panel_id[3]
            );
            seq_new
        };

        for &(cmd, data, delay_ms) in seq {
            self.send_cmd(cmd, data)?;
            if delay_ms > 0 {
                FreeRtos::delay_ms(delay_ms);
            }
        }
        Ok(())
    }
}

// ----------------------------------------------------------------
// embedded-graphics DrawTarget — permet Text, Rectangle, etc.
// ----------------------------------------------------------------

use embedded_graphics::{
    draw_target::DrawTarget,
    geometry::{Dimensions, Point, Size},
    pixelcolor::{Rgb565, RgbColor},
    primitives::Rectangle as EgRect,
    Pixel,
};

impl Dimensions for LcdDisplay {
    fn bounding_box(&self) -> EgRect {
        EgRect::new(Point::zero(), Size::new(LCD_W as u32, LCD_H as u32))
    }
}

impl DrawTarget for LcdDisplay {
    type Color = Rgb565;
    type Error = anyhow::Error;

    fn draw_iter<I>(&mut self, pixels: I) -> Result<(), Self::Error>
    where
        I: IntoIterator<Item = Pixel<Rgb565>>,
    {
        for Pixel(coord, color) in pixels {
            if coord.x >= 0 && coord.y >= 0
                && (coord.x as u16) < LCD_W
                && (coord.y as u16) < LCD_H
            {
                let raw = rgb565_raw(color);
                self.fill_rect(coord.x as u16, coord.y as u16, 1, 1, raw)?;
            }
        }
        Ok(())
    }

    fn fill_solid(&mut self, area: &EgRect, color: Rgb565) -> Result<(), Self::Error> {
        let x = area.top_left.x.max(0) as u16;
        let y = area.top_left.y.max(0) as u16;
        let w = (area.size.width as u16).min(LCD_W.saturating_sub(x));
        let h = (area.size.height as u16).min(LCD_H.saturating_sub(y));
        self.fill_rect(x, y, w, h, rgb565_raw(color))
    }

    fn fill_contiguous<I>(&mut self, area: &EgRect, colors: I) -> Result<(), Self::Error>
    where
        I: IntoIterator<Item = Rgb565>,
    {
        let x0 = area.top_left.x.max(0) as u16;
        let y0 = area.top_left.y.max(0) as u16;
        let x1 = ((area.top_left.x + area.size.width as i32 - 1).min(LCD_W as i32 - 1)) as u16;
        let y1 = ((area.top_left.y + area.size.height as i32 - 1).min(LCD_H as i32 - 1)) as u16;
        if x0 > x1 || y0 > y1 { return Ok(()); }

        let pixel_count = ((x1 - x0 + 1) as usize) * ((y1 - y0 + 1) as usize);

        // Collecte TOUS les pixels dans un buffer unique, puis UN SEUL send_pixels (RAMWR).
        // Plusieurs appels send_pixels sur la même fenêtre = RAMWR remet le curseur à (x0,y0).
        let mut buf = vec![0u8; pixel_count * 2];
        let mut idx = 0usize;
        for color in colors.into_iter().take(pixel_count) {
            let raw = rgb565_raw(color);
            buf[idx]     = (raw >> 8) as u8;
            buf[idx + 1] = raw as u8;
            idx += 2;
        }
        self.set_window(x0, y0, x1, y1)?;
        if idx > 0 {
            self.send_pixels(&buf[..idx], false)?;  // RAMWR unique pour toute la zone
        }
        self.wait_color_done()?;
        Ok(())
    }
}

#[inline(always)]
fn rgb565_raw(c: Rgb565) -> u16 {
    ((c.r() as u16) << 11) | ((c.g() as u16) << 5) | (c.b() as u16)
}
