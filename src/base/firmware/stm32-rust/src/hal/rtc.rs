//! HAL RTC — horloge temps réel PCF85063ATL.
//!
//! # Cible matérielle
//! PCF85063ATL sur bus I2C dédié (`RTC_SCL` / `RTC_SDA`).
//! Adresse I2C onboard : `0x51` (selon FAQ wiki Waveshare).
//!
//! Le RTC fournit l'horodatage local pour :
//! - les timestamps des requêtes audio (`timestamp_ms` dans [`crate::contracts`]),
//! - les intents temporels (« quelle heure est-il ? »),
//! - les fonctions de réveil/veille futures.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::rtc::{RtcHal, RtcConfig, RtcTimestamp};
//! use edge_base::hal::HalDevice;
//!
//! let mut rtc = RtcHal::new(RtcConfig::default());
//! rtc.open().unwrap();
//! let ts = rtc.now().unwrap();
//! println!("{:04}-{:02}-{:02} {:02}:{:02}:{:02}",
//!     ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second);
//! rtc.close();
//! ```

use super::{HalDevice, HalError};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique RTC.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RtcConfig {
    /// Adresse I2C du composant (PCF85063 : 0x51).
    pub i2c_addr: u8,
    /// Offset UTC en heures (ex. 2 pour UTC+2).
    pub utc_offset_hours: i8,
}

impl Default for RtcConfig {
    fn default() -> Self {
        Self {
            i2c_addr: 0x51,
            utc_offset_hours: 0,
        }
    }
}

// ─── Horodatage ───────────────────────────────────────────────────────────────

/// Horodatage lu depuis le RTC.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RtcTimestamp {
    pub year: u16,
    pub month: u8,
    pub day: u8,
    pub hour: u8,
    pub minute: u8,
    pub second: u8,
}

impl RtcTimestamp {
    /// Convertit l'horodatage en millisecondes Unix (approximation sans
    /// gestion des années bissextiles — suffisant pour les logs embarqués).
    pub fn to_unix_ms(&self) -> u64 {
        // Approximation : 365.25 jours / an depuis 1970
        let years_since_epoch = self.year.saturating_sub(1970) as u64;
        let days = years_since_epoch * 365
            + (self.month as u64).saturating_sub(1) * 30
            + self.day as u64;
        let secs = days * 86_400
            + self.hour as u64 * 3_600
            + self.minute as u64 * 60
            + self.second as u64;
        secs * 1_000
    }

    /// Retourne une chaîne `HH:MM` (heapless, taille 6).
    pub fn hhmm(&self) -> heapless::String<6> {
        let mut s = heapless::String::new();
        let _ = core::fmt::write(
            &mut s,
            format_args!("{:02}:{:02}", self.hour, self.minute),
        );
        s
    }
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de l'horloge temps réel PCF85063.
///
/// Sur ESP32-S3 : lecture/écriture registres I2C 0x51.
/// En simulation (`std`) : retourne un horodatage fixe de référence.
pub struct RtcHal {
    config: RtcConfig,
    ready: bool,
    /// Horodatage simulé (modifiable dans les tests via [`set_simulated_time`]).
    simulated: RtcTimestamp,
}

impl RtcHal {
    /// Crée une nouvelle instance.
    pub fn new(config: RtcConfig) -> Self {
        Self {
            config,
            ready: false,
            simulated: RtcTimestamp {
                year: 2026,
                month: 1,
                day: 1,
                hour: 0,
                minute: 0,
                second: 0,
            },
        }
    }

    /// Lit l'heure courante depuis le RTC.
    ///
    /// Sur firmware réel : lecture 7 octets BCD depuis PCF85063 (registres 0x04–0x0A).
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] si non initialisé.
    /// - [`HalError::BusError`] si la communication I2C échoue.
    pub fn now(&self) -> Result<RtcTimestamp, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        Ok(self.simulated)
    }

    /// Règle l'heure du RTC.
    ///
    /// Sur firmware réel : écriture BCD dans les registres PCF85063.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn set_time(&mut self, ts: RtcTimestamp) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.simulated = ts;
        Ok(())
    }

    /// Remplace l'horodatage simulé (tests uniquement).
    #[cfg(any(test, feature = "std"))]
    pub fn set_simulated_time(&mut self, ts: RtcTimestamp) {
        self.simulated = ts;
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &RtcConfig {
        &self.config
    }
}

impl HalDevice for RtcHal {
    /// Vérifie la présence du PCF85063 sur le bus I2C (adresse 0x51).
    ///
    /// Sur firmware réel : `i2c_master_probe(I2C_NUM_0, 0x51, timeout)`.
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        Ok(())
    }

    /// Libère le bus I2C RTC.
    fn close(&mut self) {
        self.ready = false;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hal::HalDevice;

    #[test]
    fn not_ready_before_open() {
        let rtc = RtcHal::new(RtcConfig::default());
        assert_eq!(rtc.now(), Err(HalError::NotInitialised));
    }

    #[test]
    fn default_simulated_time() {
        let mut rtc = RtcHal::new(RtcConfig::default());
        rtc.open().unwrap();
        let ts = rtc.now().unwrap();
        assert_eq!(ts.year, 2026);
    }

    #[test]
    fn set_time_roundtrip() {
        let mut rtc = RtcHal::new(RtcConfig::default());
        rtc.open().unwrap();
        let ts = RtcTimestamp { year: 2026, month: 5, day: 2, hour: 14, minute: 30, second: 0 };
        rtc.set_time(ts).unwrap();
        assert_eq!(rtc.now().unwrap(), ts);
    }

    #[test]
    fn hhmm_format() {
        let ts = RtcTimestamp { year: 2026, month: 5, day: 2, hour: 9, minute: 5, second: 0 };
        assert_eq!(ts.hhmm().as_str(), "09:05");
    }

    #[test]
    fn unix_ms_nonzero() {
        let ts = RtcTimestamp { year: 2026, month: 1, day: 1, hour: 0, minute: 0, second: 0 };
        assert!(ts.to_unix_ms() > 0);
    }
}
