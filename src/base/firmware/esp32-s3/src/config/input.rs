#![allow(dead_code)]

use esp_idf_sys::{i2c_port_t, i2c_port_t_I2C_NUM_0, TickType_t};

pub const BOOT_BUTTON_GPIO: i32 = 0;
pub const LONG_PRESS_RESET_MS: u32 = 3_000;
pub const LONG_PRESS_POLL_MS: u32 = 50;

pub const CST816S_I2C_ADDR: u8 = 0x15;
pub const CST816S_DATA_REG: u8 = 0x02;
pub const CST816S_CHIP_ID_REG: u8 = 0xA7;
pub const CST816S_SLEEP_REG: u8 = 0xFE;
pub const TOUCH_I2C_PORT: i2c_port_t = i2c_port_t_I2C_NUM_0;
pub const TOUCH_I2C_TIMEOUT_TICKS: TickType_t = 100;
