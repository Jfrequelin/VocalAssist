//! HAL LED — indicateur d'état visuel.
//!
//! # Cible matérielle
//! LED(s) GPIO pilotées directement ou via PWM (LEDC ESP32-S3).
//!
//! Ce module réutilise [`crate::LedColor`] et [`crate::LedPattern`] déjà définis
//! dans `lib.rs` et alignés sur [`crate::BaseState`].
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::led::{LedHal, LedConfig};
//! use edge_base::hal::HalDevice;
//! use edge_base::{BaseState, led_pattern_for};
//!
//! let mut led = LedHal::new(LedConfig::default());
//! led.open().unwrap();
//! let pattern = led_pattern_for(BaseState::Listening);
//! led.apply_pattern(pattern).unwrap();
//! led.close();
//! ```

use super::{HalDevice, HalError};
use crate::{LedColor, LedPattern};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique LED.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LedConfig {
    /// Numéro de canal PWM LEDC (0–7 sur ESP32-S3).
    pub pwm_channel: u8,
    /// Fréquence PWM en Hz (défaut 1000 Hz).
    pub pwm_freq_hz: u32,
    /// Luminosité maximale (0–255).
    pub max_brightness: u8,
}

impl Default for LedConfig {
    fn default() -> Self {
        Self {
            pwm_channel: 0,
            pwm_freq_hz: 1_000,
            max_brightness: 200,
        }
    }
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de la LED d'état.
///
/// Sur ESP32-S3 : `ledc_set_duty()` + GPIO pour couleur (si LED RGB).
/// En simulation (`std`) : mémorise l'état courant sans sortie réelle.
pub struct LedHal {
    config: LedConfig,
    ready: bool,
    current_pattern: Option<LedPattern>,
}

impl LedHal {
    /// Crée une nouvelle instance.
    pub fn new(config: LedConfig) -> Self {
        Self {
            config,
            ready: false,
            current_pattern: None,
        }
    }

    /// Retourne le pattern LED actuellement appliqué.
    pub fn current_pattern(&self) -> Option<LedPattern> {
        self.current_pattern
    }

    /// Applique un [`LedPattern`] (couleur + clignotement).
    ///
    /// `blink_hz_x10 = 0` → LED fixe.
    /// `blink_hz_x10 = 10` → clignotement 1 Hz.
    ///
    /// Sur firmware réel : configure le timer LEDC + éventuellement une tâche
    /// de clignotement si `blink_hz_x10 > 0`.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn apply_pattern(&mut self, pattern: LedPattern) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.current_pattern = Some(pattern);
        // Sur firmware réel :
        //   ledc_set_duty(channel, duty_from_color(pattern.color));
        //   if pattern.blink_hz_x10 > 0 { start_blink_task(pattern.blink_hz_x10); }
        Ok(())
    }

    /// Éteint la LED immédiatement.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn turn_off(&mut self) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.current_pattern = None;
        Ok(())
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &LedConfig {
        &self.config
    }
}

impl HalDevice for LedHal {
    /// Configure le canal PWM LEDC et éteint la LED.
    ///
    /// Sur firmware réel :
    /// ```text
    /// ledc_timer_config(&timer_cfg);
    /// ledc_channel_config(&channel_cfg);
    /// ledc_set_duty(channel, 0); // éteint
    /// ```
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        self.current_pattern = None;
        Ok(())
    }

    /// Éteint la LED et libère le canal PWM.
    fn close(&mut self) {
        self.current_pattern = None;
        self.ready = false;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

// ─── Utilitaire : couleur → intensité PWM (stub) ─────────────────────────────

/// Convertit une [`LedColor`] en valeur de duty cycle PWM (0–255).
///
/// Sur firmware RGB réel, cette fonction sélectionne la broche GPIO et le
/// canal LEDC appropriés pour produire la couleur demandée.
#[allow(dead_code)]
pub fn duty_from_color(color: LedColor) -> u8 {
    match color {
        LedColor::Green => 200,
        LedColor::Blue => 180,
        LedColor::Yellow => 220,
        LedColor::Orange => 210,
        LedColor::Red => 230,
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{BaseState, led_pattern_for};
    use crate::hal::HalDevice;

    #[test]
    fn not_ready_before_open() {
        let mut led = LedHal::new(LedConfig::default());
        let p = led_pattern_for(BaseState::Idle);
        assert_eq!(led.apply_pattern(p), Err(HalError::NotInitialised));
    }

    #[test]
    fn apply_listening_pattern() {
        let mut led = LedHal::new(LedConfig::default());
        led.open().unwrap();
        let p = led_pattern_for(BaseState::Listening);
        led.apply_pattern(p).unwrap();
        assert_eq!(led.current_pattern(), Some(p));
    }

    #[test]
    fn turn_off_clears_pattern() {
        let mut led = LedHal::new(LedConfig::default());
        led.open().unwrap();
        led.apply_pattern(led_pattern_for(BaseState::Error)).unwrap();
        led.turn_off().unwrap();
        assert_eq!(led.current_pattern(), None);
    }

    #[test]
    fn all_states_have_pattern() {
        use crate::BaseState;
        let states = [
            BaseState::Idle, BaseState::Listening, BaseState::Sending,
            BaseState::Speaking, BaseState::Muted, BaseState::Error,
        ];
        for s in states {
            let _ = led_pattern_for(s); // ne doit pas paniquer
        }
    }
}
