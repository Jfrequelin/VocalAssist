//! HAL playback — restitution audio I2S/DAC.
//!
//! # Cible matérielle
//!
//! | Variante | Composant                    | Bus  | Signaux                          |
//! |----------|------------------------------|------|----------------------------------|
//! | V2       | ES8311                       | I2S  | I2S_BCK, I2S_LRCK, I2S_DIN      |
//! | V1       | PCM5101APWR + APA2068KAI     | I2S  | I2S_BCK, I2S_LRCK, I2S_DIN      |
//!
//! ## Contraintes PCM5101 (V1)
//! - Séquence **mute pop-free** : mettre en mute DAC *avant* d'arrêter les horloges.
//! - **Recovery horloges** : réinitialiser le registre de mode après toute coupure
//!   d'alimentation.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::playback::{PlaybackHal, PlaybackConfig};
//! use edge_base::hal::HalDevice;
//!
//! let mut spk = PlaybackHal::new(PlaybackConfig::default());
//! spk.open().unwrap();
//! let silence = vec![0i16; 1600];
//! spk.play_pcm(&silence).unwrap();
//! spk.close();
//! ```

use super::{HalDevice, HalError, HalWriter};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique de restitution audio.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlaybackConfig {
    /// Fréquence d'échantillonnage en Hz.
    pub sample_rate_hz: u32,
    /// Nombre de canaux (1 = mono, 2 = stéréo).
    pub channels: u8,
    /// Résolution en bits (16 ou 32).
    pub bit_depth: u8,
    /// Volume initial (0–100).
    pub initial_volume_pct: u8,
}

impl Default for PlaybackConfig {
    fn default() -> Self {
        Self {
            sample_rate_hz: 16_000,
            channels: 1,
            bit_depth: 16,
            initial_volume_pct: 80,
        }
    }
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de la restitution audio I2S.
///
/// Sur ESP32-S3 : délègue à `esp_idf_hal::i2s` en mode TX.
/// En simulation (`std`) : consomme les données sans sortie réelle.
pub struct PlaybackHal {
    config: PlaybackConfig,
    ready: bool,
    muted: bool,
    volume_pct: u8,
}

impl PlaybackHal {
    /// Crée une nouvelle instance.
    pub fn new(config: PlaybackConfig) -> Self {
        let vol = config.initial_volume_pct.min(100);
        Self {
            config,
            ready: false,
            muted: false,
            volume_pct: vol,
        }
    }

    /// Retourne `true` si le mute matériel est actif.
    pub fn is_muted(&self) -> bool {
        self.muted
    }

    /// Volume courant (0–100).
    pub fn volume_pct(&self) -> u8 {
        self.volume_pct
    }

    /// Active ou désactive le mute matériel du DAC.
    ///
    /// Sur firmware réel : écriture registre MUTE du DAC (I2C ou GPIO XSMT).
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si [`open`](HalDevice::open) n'a pas été appelé.
    pub fn set_mute(&mut self, enabled: bool) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.muted = enabled;
        Ok(())
    }

    /// Règle le volume (0 = silence, 100 = maximum).
    ///
    /// Sur firmware réel : rampe progressive pour éviter les clics.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn set_volume(&mut self, pct: u8) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.volume_pct = pct.min(100);
        Ok(())
    }

    /// Envoie des échantillons PCM 16 bits signés vers le DAC via I2S.
    ///
    /// Si le mute est actif, les données sont ignorées silencieusement.
    ///
    /// Sur firmware réel : `i2s_write()` bloquant.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] si non initialisé.
    /// - [`HalError::InvalidArgument`] si `samples` est vide.
    pub fn play_pcm(&self, samples: &[i16]) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        if samples.is_empty() {
            return Err(HalError::InvalidArgument);
        }
        if self.muted {
            return Ok(()); // sortie silencieuse
        }
        // En simulation : rien à faire.
        // Sur firmware réel : i2s_write(I2S_NUM_1, samples.as_ptr(), bytes, &written, timeout)
        Ok(())
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &PlaybackConfig {
        &self.config
    }
}

impl HalDevice for PlaybackHal {
    /// Initialise le bus I2S TX et le DAC.
    ///
    /// Sur firmware réel (séquence PCM5101 pop-free) :
    /// 1. Démarrer les horloges I2S.
    /// 2. Attendre stabilisation (≥ 1 ms).
    /// 3. Désactiver le mute registre DAC.
    fn open(&mut self) -> Result<(), HalError> {
        // Sur firmware réel :
        //   i2s_driver_install(I2S_NUM_1, &tx_cfg, 0, NULL);
        //   dac_init(); // ES8311 via I2C ou PCM5101 via séquence GPIO
        self.ready = true;
        self.muted = false;
        Ok(())
    }

    /// Séquence mute pop-free puis libère I2S.
    ///
    /// Sur firmware réel :
    /// 1. Mettre en mute DAC (registre MUTE ou GPIO XSMT).
    /// 2. Arrêter les horloges I2S.
    /// 3. `i2s_driver_uninstall()`.
    fn close(&mut self) {
        self.muted = true;
        self.ready = false;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

impl HalWriter for PlaybackHal {
    fn write_buf(&mut self, data: &[u8]) -> Result<usize, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        if data.is_empty() {
            return Err(HalError::InvalidArgument);
        }

        let sample_width = (self.config.bit_depth / 8) as usize;
        if sample_width == 0 || data.len() % sample_width != 0 {
            return Err(HalError::InvalidArgument);
        }

        if self.muted {
            return Ok(data.len());
        }

        Ok(data.len())
    }

    fn flush(&mut self) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        Ok(())
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hal::{HalDevice, HalWriter};

    #[test]
    fn not_ready_before_open() {
        let spk = PlaybackHal::new(PlaybackConfig::default());
        assert!(!spk.is_ready());
        assert_eq!(spk.play_pcm(&[0i16; 10]), Err(HalError::NotInitialised));
    }

    #[test]
    fn play_pcm_success() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        assert!(spk.play_pcm(&[0i16; 1600]).is_ok());
    }

    #[test]
    fn empty_samples_rejected() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        assert_eq!(spk.play_pcm(&[]), Err(HalError::InvalidArgument));
    }

    #[test]
    fn mute_silences_output() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        spk.set_mute(true).unwrap();
        // Doit réussir même si muté
        assert!(spk.play_pcm(&[1000i16; 100]).is_ok());
    }

    #[test]
    fn volume_clamped_to_100() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        spk.set_volume(200).unwrap();
        assert_eq!(spk.volume_pct(), 100);
    }

    #[test]
    fn close_sequence_sets_mute() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        spk.close();
        assert!(!spk.is_ready());
        assert!(spk.is_muted());
    }

    #[test]
    fn hal_writer_accepts_pcm_bytes() {
        let mut spk = PlaybackHal::new(PlaybackConfig::default());
        spk.open().unwrap();
        let written = spk.write_buf(&[0u8; 8]).unwrap();
        assert_eq!(written, 8);
        spk.flush().unwrap();
    }
}
