//! HAL storage — carte TF/SD (FAT32).
//!
//! # Cible matérielle
//! Slot TF/SD connecté via bus SDIO ou SPI dédié.
//! Signaux schéma : `SD_CLK`, `SD_CMD`, `SD_D0..D3` (SDIO) ou `SD_CS`, `SD_MOSI`,
//! `SD_MISO`, `SD_SCK` (SPI fallback).
//!
//! # Règles importantes
//! - La fonctionnalité vocale ne doit **jamais** dépendre de la présence de la carte.
//! - Fallback propre si carte absente ou non reconnue : loguer et continuer.
//! - Format attendu : FAT32.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::storage::{StorageHal, StorageConfig};
//! use edge_base::hal::HalDevice;
//!
//! let mut sd = StorageHal::new(StorageConfig::default());
//! sd.open().unwrap();
//! if sd.is_card_present() {
//!     sd.append_log(b"boot ok\n").unwrap();
//! }
//! sd.close();
//! ```

use core::str;

use super::{HalDevice, HalError, HalReader, HalTextReader, HalTextWriter, HalWriter, IoBuffer, TextBuffer};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique stockage.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StorageConfig {
    /// Capacité maximale du buffer d'écriture embarqué (octets).
    pub write_buffer_size: u16,
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self {
            write_buffer_size: 512,
        }
    }
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de la carte TF/SD.
///
/// Sur ESP32-S3 : `esp_vfs_fat_sdmmc_mount()` + API POSIX via VFS.
/// En simulation (`std`) : `card_present` contrôlable, `append_log` no-op.
pub struct StorageHal {
    config: StorageConfig,
    ready: bool,
    card_present: bool,
    simulated_file: IoBuffer,
    read_cursor: usize,
}

impl StorageHal {
    /// Crée une nouvelle instance.
    pub fn new(config: StorageConfig) -> Self {
        Self {
            config,
            ready: false,
            card_present: false,
            simulated_file: IoBuffer::new(),
            read_cursor: 0,
        }
    }

    /// Retourne `true` si une carte est détectée et montée.
    pub fn is_card_present(&self) -> bool {
        self.card_present
    }

    /// Ajoute des données à la fin du fichier de log principal (`/sd/edge.log`).
    ///
    /// Opération silencieuse si la carte est absente (retourne `Ok(())`).
    ///
    /// Sur firmware réel : `fopen("/sdcard/edge.log", "a")` + `fwrite()`.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] si [`open`](HalDevice::open) n'a pas été appelé.
    /// - [`HalError::BufferOverflow`] si `data` dépasse la capacité du buffer.
    pub fn append_log(&mut self, data: &[u8]) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        if !self.card_present {
            return Ok(()); // carte absente — dégradation silencieuse
        }
        if data.len() > self.config.write_buffer_size as usize {
            return Err(HalError::BufferOverflow);
        }
        self.simulated_file
            .extend_from_slice(data)
            .map_err(|_| HalError::BufferOverflow)?;
        // Sur firmware réel : écriture VFS FAT32.
        Ok(())
    }

    /// Lit les `max_bytes` premiers octets du fichier `path`.
    ///
    /// Retourne un buffer vide si la carte est absente.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn read_file(
        &self,
        _path: &str,
        max_bytes: usize,
    ) -> Result<heapless::Vec<u8, 512>, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        let mut buf: heapless::Vec<u8, 512> = heapless::Vec::new();
        if !self.card_present || max_bytes == 0 {
            return Ok(buf);
        }
        let end = (self.read_cursor + max_bytes).min(self.simulated_file.len());
        buf.extend_from_slice(&self.simulated_file[self.read_cursor..end])
            .map_err(|_| HalError::BufferOverflow)?;
        Ok(buf)
    }

    /// Force la présence simul ée de la carte (tests uniquement).
    #[cfg(any(test, feature = "std"))]
    pub fn set_card_present(&mut self, present: bool) {
        self.card_present = present;
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &StorageConfig {
        &self.config
    }
}

impl HalDevice for StorageHal {
    /// Tente de monter la carte SD.
    ///
    /// Sur firmware réel : `esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot, &cfg, &card)`.
    /// Retourne `Ok(())` même si la carte est absente (dégradation propre).
    fn open(&mut self) -> Result<(), HalError> {
        // Simulation : carte absente par défaut.
        // Sur firmware réel : tenter le montage, mettre card_present selon résultat.
        self.ready = true;
        self.read_cursor = 0;
        Ok(())
    }

    /// Démonte la carte et libère les ressources.
    fn close(&mut self) {
        self.card_present = false;
        self.ready = false;
        self.read_cursor = 0;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

impl HalWriter for StorageHal {
    fn write_buf(&mut self, data: &[u8]) -> Result<usize, HalError> {
        self.append_log(data)?;
        Ok(data.len())
    }

    fn flush(&mut self) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        Ok(())
    }
}

impl HalReader for StorageHal {
    fn read_buf(&mut self, buf: &mut IoBuffer) -> Result<usize, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        buf.clear();
        if !self.card_present || self.read_cursor >= self.simulated_file.len() {
            return Ok(0);
        }

        let remaining = self.simulated_file.len() - self.read_cursor;
        let count = remaining.min(buf.capacity());
        buf.extend_from_slice(&self.simulated_file[self.read_cursor..self.read_cursor + count])
            .map_err(|_| HalError::BufferOverflow)?;
        self.read_cursor += count;
        Ok(count)
    }

    fn bytes_available(&self) -> usize {
        if !self.ready || !self.card_present {
            return 0;
        }
        self.simulated_file.len().saturating_sub(self.read_cursor)
    }
}

impl HalTextWriter for StorageHal {
    fn write_str(&mut self, s: &str) -> Result<(), HalError> {
        self.write_buf(s.as_bytes())?;
        Ok(())
    }
}

impl HalTextReader for StorageHal {
    fn read_line(&mut self, buf: &mut TextBuffer) -> Result<usize, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        buf.clear();
        if !self.card_present || self.read_cursor >= self.simulated_file.len() {
            return Ok(0);
        }

        let remaining = &self.simulated_file[self.read_cursor..];
        let newline_offset = remaining.iter().position(|byte| *byte == b'\n');
        let Some(end_offset) = newline_offset else {
            return Ok(0);
        };
        let line_bytes = &remaining[..end_offset];
        let line = str::from_utf8(line_bytes).map_err(|_| HalError::BusError)?;
        buf.push_str(line).map_err(|_| HalError::BufferOverflow)?;
        self.read_cursor += end_offset + 1;
        Ok(buf.len())
    }

    fn line_available(&self) -> bool {
        self.ready
            && self.card_present
            && self.simulated_file[self.read_cursor..].contains(&b'\n')
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hal::{HalDevice, HalReader, HalTextReader, HalTextWriter, HalWriter, IoBuffer, TextBuffer};

    #[test]
    fn not_ready_before_open() {
        let mut sd = StorageHal::new(StorageConfig::default());
        assert_eq!(sd.append_log(b"test"), Err(HalError::NotInitialised));
    }

    #[test]
    fn card_absent_by_default() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        assert!(!sd.is_card_present());
    }

    #[test]
    fn append_log_silently_skips_if_no_card() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        assert!(sd.append_log(b"hello").is_ok()); // pas de carte, pas d'erreur
    }

    #[test]
    fn append_log_with_card_present() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        sd.set_card_present(true);
        assert!(sd.append_log(b"log entry").is_ok());
    }

    #[test]
    fn buffer_overflow_detected() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        sd.set_card_present(true);
        let big = vec![0u8; 600];
        assert_eq!(sd.append_log(&big), Err(HalError::BufferOverflow));
    }

    #[test]
    fn hal_writer_and_reader_roundtrip() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        sd.set_card_present(true);
        sd.write_buf(b"abc").unwrap();
        let mut buf = IoBuffer::new();
        let count = sd.read_buf(&mut buf).unwrap();
        assert_eq!(count, 3);
        assert_eq!(&buf[..], b"abc");
    }

    #[test]
    fn hal_text_writer_and_reader_roundtrip() {
        let mut sd = StorageHal::new(StorageConfig::default());
        sd.open().unwrap();
        sd.set_card_present(true);
        sd.write_line("ligne 1").unwrap();
        let mut line = TextBuffer::new();
        let count = sd.read_line(&mut line).unwrap();
        assert_eq!(count, 7);
        assert_eq!(line.as_str(), "ligne 1");
    }
}
