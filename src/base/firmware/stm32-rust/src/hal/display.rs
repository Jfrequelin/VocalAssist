//! HAL display — écran LCD rond 360×360.
//!
//! # Cible matérielle
//! Écran LCD 1.85" 360×360 262K couleurs (contrôleur ST7701S ou GC9D01 selon variante).
//!
//! Signaux schéma : `LCD_SDA0..LCD_SDA3` (bus parallèle 4 bits), `LCD_CS`, `LCD_SCK`,
//! `LCD_RST`, `LCD_TE` (tearing-effect, synchronisation V-blank).
//!
//! ## Règle critique
//! L'écran ne doit **jamais** bloquer la boucle audio.
//! Toute mise à jour doit être non-bloquante ou déléguée à une tâche RTOS dédiée.
//!
//! # Utilisation (simulation `std`)
//!
//! ```rust,ignore
//! use edge_base::hal::display::{DisplayHal, DisplayConfig, AssistantDisplayState};
//! use edge_base::hal::HalDevice;
//!
//! let mut lcd = DisplayHal::new(DisplayConfig::default());
//! lcd.open().unwrap();
//! lcd.set_assistant_state(AssistantDisplayState::Listening);
//! lcd.show_text("Écoute…", 80, 170);
//! lcd.close();
//! ```

use super::{HalDevice, HalError, HalTextWriter};

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration du périphérique écran LCD.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DisplayConfig {
    /// Largeur en pixels.
    pub width: u16,
    /// Hauteur en pixels.
    pub height: u16,
    /// Rotation en degrés (0, 90, 180, 270).
    pub rotation_deg: u16,
    /// Intensité rétroéclairage initiale (0–100).
    pub initial_backlight_pct: u8,
}

impl Default for DisplayConfig {
    fn default() -> Self {
        Self {
            width: 360,
            height: 360,
            rotation_deg: 0,
            initial_backlight_pct: 80,
        }
    }
}

// ─── État affiché ─────────────────────────────────────────────────────────────

/// État de l'assistant affiché sur l'écran — aligné sur [`crate::BaseState`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AssistantDisplayState {
    Idle,
    Listening,
    Sending,
    Speaking,
    Muted,
    Error,
}

// ─── Zone rectangle ───────────────────────────────────────────────────────────

/// Zone rectangulaire en pixels.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rect {
    pub x: u16,
    pub y: u16,
    pub width: u16,
    pub height: u16,
}

// ─── Abstraction ──────────────────────────────────────────────────────────────

/// Abstraction de l'écran LCD.
///
/// Sur ESP32-S3 : délègue à LVGL ou TFT_eSPI.
/// En simulation (`std`) : toutes les opérations sont des no-ops validées.
pub struct DisplayHal {
    config: DisplayConfig,
    ready: bool,
    current_state: AssistantDisplayState,
    backlight_pct: u8,
}

impl DisplayHal {
    /// Crée une nouvelle instance.
    pub fn new(config: DisplayConfig) -> Self {
        let bl = config.initial_backlight_pct.min(100);
        Self {
            config,
            ready: false,
            current_state: AssistantDisplayState::Idle,
            backlight_pct: bl,
        }
    }

    /// État de l'assistant actuellement affiché.
    pub fn current_state(&self) -> AssistantDisplayState {
        self.current_state
    }

    /// Intensité rétroéclairage courante (0–100).
    pub fn backlight_pct(&self) -> u8 {
        self.backlight_pct
    }

    /// Affiche l'animation correspondant à l'état de l'assistant.
    ///
    /// Sur firmware réel : déclenche l'animation LVGL/TFT_eSPI correspondante.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn set_assistant_state(
        &mut self,
        state: AssistantDisplayState,
    ) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.current_state = state;
        // Sur firmware réel : lv_event_send() ou tft.fillScreen() selon état
        Ok(())
    }

    /// Affiche un texte à la position `(x, y)`.
    ///
    /// `color_rgb` : couleur 24 bits `0xRRGGBB`.
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn show_text(
        &self,
        text: &str,
        x: u16,
        y: u16,
        color_rgb: u32,
    ) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        // Sur firmware réel : tft.drawString(text, x, y) ou lv_label_set_text()
        let _ = (text, x, y, color_rgb);
        Ok(())
    }

    /// Efface l'écran avec la couleur de fond donnée (`0xRRGGBB`).
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn clear(&self, color_rgb: u32) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        // Sur firmware réel : tft.fillScreen(color) ou lv_obj_clean(scr)
        let _ = color_rgb;
        Ok(())
    }

    /// Règle l'intensité du rétroéclairage (0–100).
    ///
    /// Sur firmware réel : `ledc_set_duty()` (PWM).
    ///
    /// # Errors
    /// [`HalError::NotInitialised`] si non initialisé.
    pub fn set_backlight(&mut self, pct: u8) -> Result<(), HalError> {
        if !self.ready {
            return Err(HalError::NotInitialised);
        }
        self.backlight_pct = pct.min(100);
        Ok(())
    }

    /// Retourne la configuration courante.
    pub fn config(&self) -> &DisplayConfig {
        &self.config
    }
}

impl HalDevice for DisplayHal {
    /// Reset LCD → init séquence SPI/parallèle → rétroéclairage.
    ///
    /// Sur firmware réel :
    /// ```text
    /// gpio_set_level(LCD_RST, 0); delay_ms(10);
    /// gpio_set_level(LCD_RST, 1); delay_ms(120);
    /// spi_bus_initialize(); lcd_init_sequence();
    /// ledc_set_duty(backlight_channel, duty);
    /// ```
    fn open(&mut self) -> Result<(), HalError> {
        self.ready = true;
        Ok(())
    }

    /// Éteint le rétroéclairage et libère le bus.
    fn close(&mut self) {
        self.backlight_pct = 0;
        self.ready = false;
    }

    fn is_ready(&self) -> bool {
        self.ready
    }
}

impl HalTextWriter for DisplayHal {
    fn write_str(&mut self, s: &str) -> Result<(), HalError> {
        self.show_text(s, 0, 0, 0xFFFFFF)
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hal::{HalDevice, HalTextWriter};

    #[test]
    fn not_ready_before_open() {
        let lcd = DisplayHal::new(DisplayConfig::default());
        assert!(!lcd.is_ready());
        assert_eq!(lcd.clear(0), Err(HalError::NotInitialised));
    }

    #[test]
    fn set_state_after_open() {
        let mut lcd = DisplayHal::new(DisplayConfig::default());
        lcd.open().unwrap();
        lcd.set_assistant_state(AssistantDisplayState::Listening).unwrap();
        assert_eq!(lcd.current_state(), AssistantDisplayState::Listening);
    }

    #[test]
    fn show_text_success() {
        let mut lcd = DisplayHal::new(DisplayConfig::default());
        lcd.open().unwrap();
        assert!(lcd.show_text("Bonjour", 80, 170, 0xFFFFFF).is_ok());
    }

    #[test]
    fn backlight_clamped_to_100() {
        let mut lcd = DisplayHal::new(DisplayConfig::default());
        lcd.open().unwrap();
        lcd.set_backlight(200).unwrap();
        assert_eq!(lcd.backlight_pct(), 100);
    }

    #[test]
    fn close_turns_off_backlight() {
        let mut lcd = DisplayHal::new(DisplayConfig::default());
        lcd.open().unwrap();
        lcd.close();
        assert_eq!(lcd.backlight_pct(), 0);
        assert!(!lcd.is_ready());
    }

    #[test]
    fn text_writer_delegates_to_display() {
        let mut lcd = DisplayHal::new(DisplayConfig::default());
        lcd.open().unwrap();
        assert!(lcd.write_line("Etat: listening").is_ok());
    }
}
