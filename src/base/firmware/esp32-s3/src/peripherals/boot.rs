use anyhow::Result;
use esp_idf_hal::delay::FreeRtos;
use log::info;

use crate::config::input::{BOOT_BUTTON_GPIO, LONG_PRESS_POLL_MS, LONG_PRESS_RESET_MS};
use crate::wifi::WifiManager;

pub fn is_boot_button_long_pressed() -> bool {
    unsafe {
        let cfg = esp_idf_svc::sys::gpio_config_t {
            pin_bit_mask: 1u64 << BOOT_BUTTON_GPIO,
            mode: esp_idf_svc::sys::gpio_mode_t_GPIO_MODE_INPUT,
            pull_up_en: esp_idf_svc::sys::gpio_pullup_t_GPIO_PULLUP_ENABLE,
            pull_down_en: esp_idf_svc::sys::gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: esp_idf_svc::sys::gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        esp_idf_svc::sys::gpio_config(&cfg);

        if esp_idf_svc::sys::gpio_get_level(BOOT_BUTTON_GPIO) != 0 {
            return false;
        }

        let mut elapsed = 0u32;
        while elapsed < LONG_PRESS_RESET_MS {
            FreeRtos::delay_ms(LONG_PRESS_POLL_MS);
            if esp_idf_svc::sys::gpio_get_level(BOOT_BUTTON_GPIO) != 0 {
                return false;
            }
            elapsed += LONG_PRESS_POLL_MS;
        }
        true
    }
}

pub fn maybe_factory_reset(
    wifi: &mut WifiManager,
) -> Result<()> {
    if !is_boot_button_long_pressed() {
        return Ok(());
    }

    info!("[RESET] Appui long BOOT détecté — effacement paramètres");
    let _ = wifi.clear_credentials();
    info!("[RESET] Paramètres effacés — redémarrage");
    FreeRtos::delay_ms(300);
    unsafe { esp_idf_svc::sys::esp_restart() };
}
