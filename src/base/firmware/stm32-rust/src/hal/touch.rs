//! HAL touch — capteur tactile capacitif I2C.
//!
//! # Cible matérielle
//! Capteur capacitif monté sur bus I2C avec ligne d'interruption.
//! Adresse I2C onboard : `0x15` (selon FAQ wiki Waveshare).
//!
//! Signaux schéma : `TP_SCL`, `TP_SDA`, `TP_RST`, `TP_INT`.
//!
//! ## Règle debounce
//! Les événements bruts doivent être filtrés par debounce logiciel (≥ 20 ms)
//! avant d'être transmis à la couche applicative.
//! La boucle audio ne doit **pas** être bloquée par la gestion du tactile.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::touch::{TouchHal, TouchConfig, TouchEvent};
//! use edge_base::hal::HalDevice;
//!
//! let mut touch = TouchHal::new(TouchConfig::default());
//! touch.open().unwrap();
//! if let Some(evt) = touch.poll_event() {
//!     println!("tap à ({}, {})", evt.x, evt.y);
//! }
//! touch.close();
//! ```

use super::{HalDevice, HalError};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique tactile.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TouchConfig {
    /// Adresse I2C du contrôleur.
    pub i2c_addr: u8,
    /// Seuil de debounce en millisecondes.
    pub debounce_ms: u16,
    /// Largeur de la surface tactile en pixels.
    pub surface_width: u16,
    /// Hauteur de la surface tactile en pixels.
    pub surface_height: u16,
}

impl Default for TouchConfig {
    fn default() -> Self {
        Self {
            i2c_addr: 0x15,
            debounce_ms: 20,
            surface_width: 360,
            surface_height: 360,
        }
    }
}

// ─── Événements ──────────────────────────────────────────────────────────────

/// Type d'interaction tactile.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TouchKind {
    /// Appui simple.
    Tap,
    /// Appui long (≥ 500 ms).
    LongPress,
    /// Glissement (swipe).
    Swipe,
}

/// Événement tactile retourné par [`TouchHal::poll_event`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TouchEvent {
    /// Coordonnée X en pixels depuis le coin supérieur gauche.
    pub x: u16,
    /// Coordonnée Y en pixels.
    pub y: u16,
    /// Type d'interaction.
    pub kind: TouchKind,
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction du capteur tactile capacitif.
///
/// Sur ESP32-S3 : lecture registres I2C + surveillance ligne TP_INT.
/// En simulation (`std`) : `poll_event()` retourne toujours `None`.
pub struct TouchHal {
    config: TouchConfig,
    ready: bool,
}

impl TouchHal {
    /// Crée une nouvelle instance.
    pub fn new(config: TouchConfig) -> Self {
        Self { config, ready: false }
    }

    /// Interroge le contrôleur tactile et retourne un événement si disponible.
    ///
    /// Retourne `None` si aucun événement n'est en attente ou si la ligne
    /// `TP_INT` est inactive.
    ///
    /// Sur firmware réel : lecture via I2C des registres de coordonnées,
    /// application du debounce, détection du type de geste.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn poll_event(&self) -> Result<Option<TouchEvent>, HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        // Simulation : aucun événement
        Ok(None)
    }

    /// Injecte un événement simulé (utile pour les tests uniquement).
    ///
    /// Sur firmware réel cette méthode n'est pas utilisée.
    #[cfg(any(test, feature = "std"))]
    pub fn inject_event(&self, _event: TouchEvent) {
        // En simulation les tests créent directement des TouchEvent
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &TouchConfig {
        &self.config
    }
}

impl HalDevice for TouchHal {
    /// Reset (TP_RST low → high) et configure le bus I2C.
    ///
    /// Sur firmware réel :
    /// ```text
    /// gpio_set_level(TP_RST, 0); delay_ms(10);
    /// gpio_set_level(TP_RST, 1); delay_ms(50);
    /// i2c_master_init(); // scan + vérif adresse 0x15
    /// gpio_install_isr_service(0);
    /// gpio_isr_handler_add(TP_INT, touch_isr, NULL);
    /// ```
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        Ok(())
    }

    /// Désinstalle l'ISR et libère le bus I2C.
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
        let t = TouchHal::new(TouchConfig::default());
        assert_eq!(t.poll_event(), Err(HalError::NotInitialised));
    }

    #[test]
    fn poll_returns_none_after_open() {
        let mut t = TouchHal::new(TouchConfig::default());
        t.open().unwrap();
        assert_eq!(t.poll_event(), Ok(None));
    }

    #[test]
    fn touch_event_fields() {
        let evt = TouchEvent { x: 120, y: 200, kind: TouchKind::Tap };
        assert_eq!(evt.x, 120);
        assert_eq!(evt.kind, TouchKind::Tap);
    }

    #[test]
    fn close_marks_not_ready() {
        let mut t = TouchHal::new(TouchConfig::default());
        t.open().unwrap();
        t.close();
        assert!(!t.is_ready());
    }
}
