#![allow(dead_code)]

use esp_idf_sys::{i2c_port_t, i2c_port_t_I2C_NUM_0, TickType_t};

pub const LCD_W: u16 = 360;
pub const LCD_H: u16 = 360;

pub const COLOR_BLACK: u16 = 0x0000;
pub const COLOR_WHITE: u16 = 0xFFFF;
pub const COLOR_GREEN: u16 = 0x07E0;
pub const COLOR_RED: u16 = 0xF800;
pub const COLOR_BLUE: u16 = 0x001F;
pub const COLOR_GRAY: u16 = 0x8410;
pub const COLOR_ORANGE: u16 = 0xFD20;

pub const OPCODE_WRITE_CMD: u32 = 0x02;
pub const OPCODE_READ_CMD: u32 = 0x0B;
pub const OPCODE_WRITE_COLOR: u32 = 0x32;
pub const LCD_CMD_RAMWR: u8 = 0x2C;
pub const LCD_CMD_RAMWRC: u8 = 0x3C;

pub const LCD_SCK: i32 = 40;
pub const LCD_DATA0: i32 = 46;
pub const LCD_DATA1: i32 = 45;
pub const LCD_DATA2: i32 = 42;
pub const LCD_DATA3: i32 = 41;
pub const LCD_CS: i32 = 21;
pub const LCD_BL: i32 = 5;
pub const LCD_TE: i32 = 18;

pub const TP_INT: i32 = 4;
pub const TP_SCL: i32 = 10;
pub const TP_SDA: i32 = 11;

pub const EXIO_TP_RST: u8 = 1;
pub const EXIO_LCD_RST: u8 = 2;

pub const I2C_PORT: i2c_port_t = i2c_port_t_I2C_NUM_0;
pub const I2C_SPEED_HZ: u32 = 400_000;
pub const I2C_TIMEOUT_TICKS: TickType_t = 100;

pub const TCA9554_REG_INPUT: u8 = 0x00;
pub const TCA9554_REG_OUTPUT: u8 = 0x01;
pub const TCA9554_REG_CONFIG: u8 = 0x03;
