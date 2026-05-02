//! HAL microphone — capture audio I2S.
//!
//! # Cible matérielle
//!
//! | Variante | Composant        | Bus  | Signaux                         |
//! |----------|------------------|------|---------------------------------|
//! | V2       | ES7210           | I2S  | MIC_SD, MIC_SCK, MIC_WS        |
//! | V1       | MEMS numérique   | I2S  | MIC_SD, MIC_SCK, MIC_WS        |
//!
//! `MIC_EN` (actif haut) active l'alimentation du micro.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::microphone::{MicrophoneHal, MicConfig};
//! use edge_base::hal::HalDevice;
//!
//! let mut mic = MicrophoneHal::new(MicConfig::default());
//! mic.open().unwrap();
//! let frame = mic.read_frame(1600).unwrap();
//! assert_eq!(frame.num_bytes, 1600 * 2); // PCM16 mono
//! mic.close();
//! ```

use super::{HalDevice, HalError, HalReader, IoBuffer};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique microphone.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MicConfig {
    /// Fréquence d'échantillonnage en Hz (ex. 16 000).
    pub sample_rate_hz: u32,
    /// Nombre de canaux (1 = mono, 2 = stéréo).
    pub channels: u8,
    /// Résolution en bits (16 ou 32).
    pub bit_depth: u8,
}

impl Default for MicConfig {
    fn default() -> Self {
        Self {
            sample_rate_hz: 16_000,
            channels: 1,
            bit_depth: 16,
        }
    }
}

// ─── Trame capturée ───────────────────────────────────────────────────────────

/// Trame audio retournée par [`MicrophoneHal::read_frame`].
#[derive(Debug, PartialEq, Eq)]
pub struct MicFrame {
    /// Données PCM brutes (PCM 16 bits LE).
    ///
    /// Taille = `num_frames × channels × (bit_depth / 8)`.
    pub pcm: heapless::Vec<u8, 8192>,
    /// Nombre de frames d'échantillons.
    pub num_frames: u16,
    /// Nombre d'octets valides dans `pcm`.
    pub num_bytes: u16,
    /// Fréquence d'échantillonnage effective.
    pub sample_rate_hz: u32,
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de la capture audio I2S.
///
/// Sur ESP32-S3 : délègue à `esp_idf_hal::i2s` (driver IDF).
/// En simulation (`std`) : génère des trames de silence (zéros).
pub struct MicrophoneHal {
    config: MicConfig,
    ready: bool,
}

impl MicrophoneHal {
    /// Crée une nouvelle instance avec la configuration donnée.
    pub fn new(config: MicConfig) -> Self {
        Self { config, ready: false }
    }

    /// Lit une trame PCM de `num_frames` échantillons.
    ///
    /// Sur firmware réel : `i2s_read()` bloquant jusqu'à remplissage du buffer.
    /// En simulation : remplit de zéros (silence).
    ///
    /// # Errors
    /// Retourne [`HalError::NotInitialised`] si [`open`](HalDevice::open) n'a pas été appelé.
    /// Retourne [`HalError::InvalidArgument`] si `num_frames` = 0 ou > capacité du buffer.
    pub fn read_frame(&self, num_frames: u16) -> Result<MicFrame, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        if num_frames == 0 {
            return Err(HalError::InvalidArgument);
        }

        let bytes_per_frame =
            self.config.channels as u16 * (self.config.bit_depth as u16 / 8);
        let total_bytes = num_frames
            .checked_mul(bytes_per_frame)
            .ok_or(HalError::BufferOverflow)?;

        let mut pcm: heapless::Vec<u8, 8192> = heapless::Vec::new();
        pcm.resize(total_bytes as usize, 0)
            .map_err(|_| HalError::BufferOverflow)?;

        Ok(MicFrame {
            pcm,
            num_frames,
            num_bytes: total_bytes,
            sample_rate_hz: self.config.sample_rate_hz,
        })
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &MicConfig {
        &self.config
    }

    fn bytes_per_frame(&self) -> usize {
        self.config.channels as usize * (self.config.bit_depth as usize / 8)
    }
}

impl HalDevice for MicrophoneHal {
    /// Active l'alimentation (MIC_EN high) et initialise le driver I2S.
    fn open(&mut self) -> Result<(), HalError> {
        // Sur firmware réel :
        //   gpio_set_level(MIC_EN, 1);
        //   i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
        self.ready = true;
        Ok(())
    }

    /// Coupe MIC_EN et libère le driver I2S.
    fn close(&mut self) {
        // Sur firmware réel :
        //   gpio_set_level(MIC_EN, 0);
        //   i2s_driver_uninstall(I2S_NUM_0);
        self.ready = false;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

impl HalReader for MicrophoneHal {
    fn read_buf(&mut self, buf: &mut IoBuffer) -> Result<usize, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }

        let bytes_per_frame = self.bytes_per_frame();
        if bytes_per_frame == 0 || buf.capacity() < bytes_per_frame {
            return Err(HalError::BufferOverflow);
        }

        let num_frames = (buf.capacity() / bytes_per_frame).min(1600);
        let frame = self.read_frame(num_frames as u16)?;
        buf.clear();
        buf.extend_from_slice(&frame.pcm)
            .map_err(|_| HalError::BufferOverflow)?;
        Ok(frame.num_bytes as usize)
    }

    fn bytes_available(&self) -> usize {
        if !self.ready {
            return 0;
        }
        1600 * self.bytes_per_frame()
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hal::{HalDevice, HalReader, IoBuffer};

    #[test]
    fn not_ready_before_open() {
        let mic = MicrophoneHal::new(MicConfig::default());
        assert!(!mic.is_ready());
        assert_eq!(mic.read_frame(100), Err(HalError::NotInitialised));
    }

    #[test]
    fn read_silence_after_open() {
        let mut mic = MicrophoneHal::new(MicConfig::default());
        mic.open().unwrap();
        let frame = mic.read_frame(1600).unwrap();
        assert_eq!(frame.num_frames, 1600);
        assert_eq!(frame.num_bytes, 1600 * 2); // mono PCM16
        assert!(frame.pcm.iter().all(|&b| b == 0));
    }

    #[test]
    fn zero_frames_rejected() {
        let mut mic = MicrophoneHal::new(MicConfig::default());
        mic.open().unwrap();
        assert_eq!(mic.read_frame(0), Err(HalError::InvalidArgument));
    }

    #[test]
    fn stereo_frame_size() {
        let cfg = MicConfig { channels: 2, ..Default::default() };
        let mut mic = MicrophoneHal::new(cfg);
        mic.open().unwrap();
        let frame = mic.read_frame(800).unwrap();
        assert_eq!(frame.num_bytes, 800 * 2 * 2); // stéréo PCM16
    }

    #[test]
    fn close_marks_not_ready() {
        let mut mic = MicrophoneHal::new(MicConfig::default());
        mic.open().unwrap();
        mic.close();
        assert!(!mic.is_ready());
    }

    #[test]
    fn hal_reader_fills_io_buffer() {
        let mut mic = MicrophoneHal::new(MicConfig::default());
        mic.open().unwrap();
        let mut buf = IoBuffer::new();
        let count = mic.read_buf(&mut buf).unwrap();
        assert_eq!(count, 3200);
        assert_eq!(buf.len(), 3200);
    }
}
