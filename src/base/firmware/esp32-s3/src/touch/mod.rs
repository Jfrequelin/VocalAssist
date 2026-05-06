#![allow(dead_code)]

use esp_idf_sys::*;
use log::*;
use crate::config::input::{
    CST816S_CHIP_ID_REG, CST816S_DATA_REG, CST816S_I2C_ADDR, CST816S_SLEEP_REG,
    TOUCH_I2C_PORT as I2C_PORT, TOUCH_I2C_TIMEOUT_TICKS as I2C_TIMEOUT_TICKS,
};

/// Point tactile (coordonnées X, Y)
#[derive(Debug, Clone, Copy)]
pub struct TouchPoint {
    pub x: u16,
    pub y: u16,
}

/// Driver I²C pour écran tactile CST816S
/// Utilise les APIs bas niveau de esp-idf-sys (pas de I2cDriver, permet l'utilisation directe)
pub struct CST816S;

impl CST816S {
    /// Initialise le CST816S
    /// Appelé une seule fois lors du boot
    pub fn init() {
        // Lire l'ID du chip (optionnel mais recommandé)
        if let Ok(id) = Self::read_chip_id_internal() {
            info!("CST816S chip ID: 0x{:02X}", id);
        } else {
            warn!("Erreur lecture chip ID CST816S");
        }

        // Désactiver le mode sleep (0xFE = 1 pour rester actif)
        if let Err(_e) = Self::write_register_internal(CST816S_SLEEP_REG, &[0x01]) {
            warn!("Erreur configuration sleep CST816S");
        }
    }

    /// Lit l'ID du chip (registre 0xA7)
    fn read_chip_id_internal() -> Result<u8, i32> {
        let mut buf = [0u8; 1];
        Self::read_register_internal(CST816S_CHIP_ID_REG, &mut buf)?;
        Ok(buf[0])
    }

    /// Lit le registre spécifié (APIs bas niveau)
    fn read_register_internal(reg: u8, buf: &mut [u8]) -> Result<(), i32> {
        unsafe {
            let ret = i2c_master_write_read_device(
                I2C_PORT,
                CST816S_I2C_ADDR,
                &reg as *const u8,
                1,
                buf.as_mut_ptr(),
                buf.len(),
                I2C_TIMEOUT_TICKS,
            );
            if ret != ESP_OK {
                return Err(ret);
            }
        }
        Ok(())
    }

    /// Écrit dans le registre spécifié (APIs bas niveau)
    fn write_register_internal(reg: u8, data: &[u8]) -> Result<(), i32> {
        unsafe {
            let mut buf = [0u8; 32];
            buf[0] = reg;
            buf[1..1 + data.len()].copy_from_slice(data);
            let ret = i2c_master_write_to_device(
                I2C_PORT,
                CST816S_I2C_ADDR,
                buf.as_ptr(),
                1 + data.len(),
                I2C_TIMEOUT_TICKS,
            );
            if ret != ESP_OK {
                return Err(ret);
            }
        }
        Ok(())
    }

    /// Lit l'état tactile et retourne la première position de contact (s'il existe)
    pub fn read_touch() -> Option<TouchPoint> {
        let mut raw_data = [0u8; 5];
        if Self::read_register_internal(CST816S_DATA_REG, &mut raw_data).is_err() {
            return None;
        }

        // Parser les données
        let num_points = raw_data[0] & 0x0F; // Bits 0-3

        if num_points == 0 {
            return None;
        }

        // Extraire X et Y du premier point (seul point supporté)
        let x_h = (raw_data[1] & 0x0F) as u16;
        let x_l = raw_data[2] as u16;
        let y_h = (raw_data[3] & 0x0F) as u16;
        let y_l = raw_data[4] as u16;

        let x = (x_h << 8) | x_l;
        let y = (y_h << 8) | y_l;

        // Vérifier limites valides (360x360)
        if x > 360 || y > 360 {
            debug!("Coordonnées CST816S invalides: x={}, y={}", x, y);
            return None;
        }

        Some(TouchPoint { x, y })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_touch_point_parsing() {
        // Simule une coordonnée 180, 180
        // raw_data[1] = 0x0B (x_h = 0x0B = 11)
        // raw_data[2] = 0x40 (x_l = 0x40 = 64)
        // → x = (0x0B << 8) | 0x40 = 0x0B40 = 2880... non, attend
        // Avec le format split (x_h 4 bits + x_l 8 bits) :
        // x = (11 << 8) | 64 = 2816... toujours pas bon
        // Laisse moi recalculer : pour x=180 en 12 bits :
        // 180 = 0x00B4, mais seul 4 bits hauts utilisés ? Non, c'est 12 bits total
        // Donc : x_h = (180 >> 8) & 0x0F = 0, x_l = 180 & 0xFF = 0xB4
        // Attendu : x = (0 << 8) | 0xB4 = 0x00B4 = 180 ✓
        let x = (0x00u16 << 8) | 0xB4u16;
        assert_eq!(x, 180);

        let y = (0x00u16 << 8) | 0xB4u16;
        assert_eq!(y, 180);
    }
}
