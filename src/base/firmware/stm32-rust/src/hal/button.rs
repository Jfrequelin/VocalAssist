//! HAL button — bouton physique GPIO.
//!
//! # Cible matérielle
//! Bouton(s) physique(s) sur GPIO avec résistance de tirage interne ou externe.
//! Un ISR sur front descendant (actif bas) détecte l'appui.
//!
//! # Alignement avec le code existant
//! Ce module implémente l'équivalent firmware de :
//! - [`crate::EdgeDeviceController::press_button`] (Python : `edge_device.py`)
//! - L'intent `SystemIntent::ToggleMute` (Rust : `lib.rs`)
//!
//! # Règle debounce
//! Le debounce matériel ou logiciel est obligatoire (≥ 50 ms) pour éviter les
//! faux déclenchements.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::button::{ButtonHal, ButtonConfig, ButtonEvent};
//! use edge_base::hal::HalDevice;
//!
//! let mut btn = ButtonHal::new(ButtonConfig::default());
//! btn.open().unwrap();
//! // En simulation, déclencher un événement manuellement :
//! btn.simulate_press();
//! if let Some(evt) = btn.poll_event() {
//!     println!("bouton : {:?}", evt);
//! }
//! btn.close();
//! ```

use super::{HalDevice, HalError};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique bouton.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ButtonConfig {
    /// Numéro GPIO du bouton (actif bas).
    pub gpio_pin: u8,
    /// Durée de debounce en millisecondes.
    pub debounce_ms: u16,
    /// Durée minimale en ms pour qualifier un appui long.
    pub long_press_ms: u16,
}

impl Default for ButtonConfig {
    fn default() -> Self {
        Self {
            gpio_pin: 0,
            debounce_ms: 50,
            long_press_ms: 800,
        }
    }
}

// ─── Événements ──────────────────────────────────────────────────────────────

/// Type d'appui sur le bouton.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ButtonEvent {
    /// Appui bref (< `long_press_ms`).
    ShortPress,
    /// Appui long (≥ `long_press_ms`).
    LongPress,
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction du bouton physique GPIO.
///
/// Sur ESP32-S3 : ISR sur front GPIO + file de messages FreeRTOS.
/// En simulation (`std`) : file interne simulée.
pub struct ButtonHal {
    config: ButtonConfig,
    ready: bool,
    pending: Option<ButtonEvent>,
}

impl ButtonHal {
    /// Crée une nouvelle instance.
    pub fn new(config: ButtonConfig) -> Self {
        Self {
            config,
            ready: false,
            pending: None,
        }
    }

    /// Interroge la file d'événements et retourne le prochain événement disponible.
    ///
    /// Retourne `None` si aucun événement n'est en attente.
    ///
    /// Sur firmware réel : `xQueueReceive(button_queue, &evt, 0)`.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn poll_event(&mut self) -> Result<Option<ButtonEvent>, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        Ok(self.pending.take())
    }

    /// Simule un appui court (tests / simulation uniquement).
    #[cfg(any(test, feature = "std"))]
    pub fn simulate_press(&mut self) {
        self.pending = Some(ButtonEvent::ShortPress);
    }

    /// Simule un appui long (tests / simulation uniquement).
    #[cfg(any(test, feature = "std"))]
    pub fn simulate_long_press(&mut self) {
        self.pending = Some(ButtonEvent::LongPress);
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &ButtonConfig {
        &self.config
    }
}

impl HalDevice for ButtonHal {
    /// Configure le GPIO en entrée pull-up et installe l'ISR.
    ///
    /// Sur firmware réel :
    /// ```text
    /// gpio_set_direction(gpio_pin, GPIO_MODE_INPUT);
    /// gpio_set_pull_mode(gpio_pin, GPIO_PULLUP_ONLY);
    /// gpio_set_intr_type(gpio_pin, GPIO_INTR_NEGEDGE);
    /// gpio_install_isr_service(0);
    /// gpio_isr_handler_add(gpio_pin, button_isr, NULL);
    /// ```
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        self.pending = None;
        Ok(())
    }

    /// Désinstalle l'ISR et libère le GPIO.
    fn close(&mut self) {
        self.pending = None;
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
        let mut btn = ButtonHal::new(ButtonConfig::default());
        assert_eq!(btn.poll_event(), Err(HalError::NotInitialised));
    }

    #[test]
    fn no_event_by_default() {
        let mut btn = ButtonHal::new(ButtonConfig::default());
        btn.open().unwrap();
        assert_eq!(btn.poll_event(), Ok(None));
    }

    #[test]
    fn short_press_detected() {
        let mut btn = ButtonHal::new(ButtonConfig::default());
        btn.open().unwrap();
        btn.simulate_press();
        assert_eq!(btn.poll_event(), Ok(Some(ButtonEvent::ShortPress)));
    }

    #[test]
    fn long_press_detected() {
        let mut btn = ButtonHal::new(ButtonConfig::default());
        btn.open().unwrap();
        btn.simulate_long_press();
        assert_eq!(btn.poll_event(), Ok(Some(ButtonEvent::LongPress)));
    }

    #[test]
    fn event_consumed_after_poll() {
        let mut btn = ButtonHal::new(ButtonConfig::default());
        btn.open().unwrap();
        btn.simulate_press();
        let _ = btn.poll_event();
        assert_eq!(btn.poll_event(), Ok(None)); // consommé
    }

    #[test]
    fn close_clears_pending() {
        let mut btn = ButtonHal::new(ButtonConfig::default());
        btn.open().unwrap();
        btn.simulate_press();
        btn.close();
        assert!(!btn.is_ready());
    }
}
