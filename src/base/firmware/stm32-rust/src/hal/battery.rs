//! HAL battery — surveillance batterie Li-ion.
//!
//! # Cible matérielle
//! Batterie Li-ion 3.7 V avec circuit de charge intégré.
//! Lecture du niveau via ADC sur `BAT_ADC`.
//! Contrôle d'alimentation via `BAT_Control`.
//!
//! # Garde-fous
//! - Niveau bas (< 10 %) : passer en mode dégradé, réduire les fonctions non critiques.
//! - Niveau critique (< 5 %) : déclencher une séquence d'arrêt propre.
//! - Ne jamais rendre la fonctionnalité vocale dépendante de la mesure batterie.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::battery::{BatteryHal, BatteryConfig, BatteryStatus};
//! use edge_base::hal::HalDevice;
//!
//! let mut bat = BatteryHal::new(BatteryConfig::default());
//! bat.open().unwrap();
//! let status = bat.read_status().unwrap();
//! println!("niveau : {}%  tension : {}mV", status.level_pct, status.voltage_mv);
//! bat.close();
//! ```

use super::{HalDevice, HalError};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique batterie.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BatteryConfig {
    /// Canal ADC utilisé pour BAT_ADC (0–9 sur ESP32-S3).
    pub adc_channel: u8,
    /// Tension maximale de la cellule en mV (ex. 4200 pour Li-ion).
    pub vmax_mv: u16,
    /// Tension minimale de décharge en mV (ex. 3000 pour Li-ion).
    pub vmin_mv: u16,
    /// Seuil de niveau bas en % (déclenchement mode dégradé).
    pub low_threshold_pct: u8,
}

impl Default for BatteryConfig {
    fn default() -> Self {
        Self {
            adc_channel: 4,
            vmax_mv: 4_200,
            vmin_mv: 3_000,
            low_threshold_pct: 10,
        }
    }
}

// ─── État batterie ─────────────────────────────────────────────────────────────

/// État de la batterie retourné par [`BatteryHal::read_status`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BatteryStatus {
    /// Niveau de charge estimé (0–100 %).
    pub level_pct: u8,
    /// Tension mesurée en millivolts.
    pub voltage_mv: u16,
    /// `true` si le chargeur USB est connecté.
    pub charging: bool,
    /// `true` si le niveau est sous le seuil bas configuré.
    pub is_low: bool,
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de la surveillance batterie.
///
/// Sur ESP32-S3 : lecture ADC + éventuelle communication I2C vers un gauge IC.
/// En simulation (`std`) : retourne un état fixe paramétrable.
pub struct BatteryHal {
    config: BatteryConfig,
    ready: bool,
    /// Niveau simulé (modifiable dans les tests).
    simulated_level_pct: u8,
    /// Tension simulée en mV.
    simulated_voltage_mv: u16,
    /// État charge simulé.
    simulated_charging: bool,
}

impl BatteryHal {
    /// Crée une nouvelle instance.
    pub fn new(config: BatteryConfig) -> Self {
        Self {
            config,
            ready: false,
            simulated_level_pct: 80,
            simulated_voltage_mv: 3_900,
            simulated_charging: false,
        }
    }

    /// Lit l'état courant de la batterie.
    ///
    /// Sur firmware réel :
    /// 1. Lire la tension via ADC (`adc1_get_raw()`).
    /// 2. Convertir en mV avec le diviseur résistif.
    /// 3. Déduire le niveau (courbe de décharge linéaire simplifiée).
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn read_status(&self) -> Result<BatteryStatus, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        let is_low = self.simulated_level_pct < self.config.low_threshold_pct;
        Ok(BatteryStatus {
            level_pct: self.simulated_level_pct,
            voltage_mv: self.simulated_voltage_mv,
            charging: self.simulated_charging,
            is_low,
        })
    }

    /// Retourne `true` si le niveau est sous le seuil bas.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn is_low(&self) -> Result<bool, HalError> {
        Ok(self.read_status()?.is_low)
    }

    /// Configure l'état simulé (tests / simulation uniquement).
    #[cfg(any(test, feature = "std"))]
    pub fn set_simulated(
        &mut self,
        level_pct: u8,
        voltage_mv: u16,
        charging: bool,
    ) {
        self.simulated_level_pct = level_pct.min(100);
        self.simulated_voltage_mv = voltage_mv;
        self.simulated_charging = charging;
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &BatteryConfig {
        &self.config
    }
}

impl HalDevice for BatteryHal {
    /// Configure le canal ADC et initialise la surveillance batterie.
    ///
    /// Sur firmware réel : `adc1_config_channel_atten()` + `adc1_config_width()`.
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        Ok(())
    }

    /// Libère les ressources ADC.
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
        let bat = BatteryHal::new(BatteryConfig::default());
        assert_eq!(bat.read_status(), Err(HalError::NotInitialised));
    }

    #[test]
    fn default_level_not_low() {
        let mut bat = BatteryHal::new(BatteryConfig::default());
        bat.open().unwrap();
        let status = bat.read_status().unwrap();
        assert_eq!(status.level_pct, 80);
        assert!(!status.is_low);
    }

    #[test]
    fn low_threshold_detected() {
        let mut bat = BatteryHal::new(BatteryConfig::default());
        bat.open().unwrap();
        bat.set_simulated(5, 3_050, false);
        assert!(bat.is_low().unwrap());
    }

    #[test]
    fn charging_state() {
        let mut bat = BatteryHal::new(BatteryConfig::default());
        bat.open().unwrap();
        bat.set_simulated(60, 3_800, true);
        let s = bat.read_status().unwrap();
        assert!(s.charging);
    }
}
