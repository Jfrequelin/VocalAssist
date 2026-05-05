
use anyhow::Result;
use esp_idf_hal::{
    delay::FreeRtos,
    peripherals::Peripherals,
};
use esp_idf_svc::{
    eventloop::EspSystemEventLoop,
    nvs::EspDefaultNvsPartition,
};
use log::{error, info};

mod lcd;
mod ui;
mod wifi;
mod server;
mod touch;
mod audio;

use lcd::LcdDisplay;
use wifi::WifiManager;
use server::ServerPing;
use touch::CST816S;
use audio::{audio_init, MicCapture};

const BOOT_BUTTON_GPIO: i32 = 0;
const LONG_PRESS_RESET_MS: u32 = 3_000;
const LONG_PRESS_POLL_MS:  u32 = 50;

fn is_boot_button_long_pressed() -> bool {
    unsafe {
        let cfg = esp_idf_svc::sys::gpio_config_t {
            pin_bit_mask: 1u64 << BOOT_BUTTON_GPIO,
            mode: esp_idf_svc::sys::gpio_mode_t_GPIO_MODE_INPUT,
            pull_up_en: esp_idf_svc::sys::gpio_pullup_t_GPIO_PULLUP_ENABLE,
            pull_down_en: esp_idf_svc::sys::gpio_pulldown_t_GPIO_PULLDOWN_DISABLE,
            intr_type: esp_idf_svc::sys::gpio_int_type_t_GPIO_INTR_DISABLE,
        };
        esp_idf_svc::sys::gpio_config(&cfg);

        // BOOT est actif à l'état bas.
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

fn maybe_factory_reset(
    wifi: &mut WifiManager,
    nvs_partition: EspDefaultNvsPartition,
) -> Result<()> {
    if !is_boot_button_long_pressed() {
        return Ok(());
    }

    info!("[RESET] Appui long BOOT détecté — effacement paramètres");
    let _ = wifi.clear_credentials();
    let mut server_cfg = ServerPing::new(nvs_partition)?;
    let _ = server_cfg.clear_address();
    info!("[RESET] Paramètres effacés — redémarrage");
    FreeRtos::delay_ms(300);
    unsafe { esp_idf_svc::sys::esp_restart() };
}

fn main() -> Result<()> {
    // ----------------------------------------------------------------
    // [P0-01] Init système : console USB CDC + NVS + logging
    // ----------------------------------------------------------------
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("=== EDGE booting (Phase 0) ===");
    info!("[P0-01] Console USB CDC active — logs visibles");

    let peripherals    = Peripherals::take()?;
    let sysloop        = EspSystemEventLoop::take()?;
    let nvs_partition  = EspDefaultNvsPartition::take()?;

    info!("[P0-01] NVS initialisé");

    // ----------------------------------------------------------------
    // [P0-01] Init LCD ST77916 QSPI + rétroéclairage
    // ----------------------------------------------------------------
    let mut lcd = LcdDisplay::new()?;
    info!("[P0-01] LCD ST77916 initialisé");

    // Init touchscreen CST816S (I2C0 déjà configuré par LcdDisplay::new)
    CST816S::init();
    info!("[P0-01] CST816S touchscreen initialisé");

    // Init audio (ES7210 microphone + ES8311 DAC + PA GPIO)
    // I2C0 est déjà configuré par LcdDisplay::new — on réutilise le même bus.
    match audio_init() {
        Ok(()) => info!("[P0-01] Codecs audio ES7210+ES8311 initialisés"),
        Err(e) => log::warn!("[P0-01] Init audio échouée (non bloquant): {}", e),
    }

    // ----------------------------------------------------------------
    // [P0-02] WiFi provisioning
    // ----------------------------------------------------------------

    info!("[P0-02] Démarrage WiFi...");
    let mut wifi = WifiManager::new(
        peripherals.modem,
        sysloop.clone(),
        nvs_partition.clone(),
    )?;

    // Vérifie dès le boot, puis en continu en boucle principale.
    maybe_factory_reset(&mut wifi, nvs_partition.clone())?;

    let wifi_result = if let Some((ssid, password)) = wifi.load_credentials() {
        // Credentials connus → connexion directe
        ui::show_wifi_connecting(&mut lcd)?;
        wifi.connect(ssid.as_str(), password.as_str())
    } else {
        // Pas de credentials → provisioning tactile
        info!("[P0-02] Pas de credentials — provisioning tactile");
        let ssids_raw = wifi.scan()?;
        let ssid_refs: heapless::Vec<&str, 8> = ssids_raw
            .iter()
            .map(|s| s.as_str())
            .collect();

        let (selected_ssid, entered_pass) =
            ui::run_wifi_provisioning(&mut lcd, ssid_refs.as_slice())?;

        // Sauvegarder avant de tenter la connexion
        wifi.save_credentials(selected_ssid.as_str(), entered_pass.as_str())?;

        ui::show_wifi_connecting(&mut lcd)?;
        wifi.connect(selected_ssid.as_str(), entered_pass.as_str())
    };

    match wifi_result {
        Ok(()) => {
            ui::show_wifi_connected(&mut lcd, wifi.ip())?;
            info!("[P0-02] WiFi connecté — IP: {}", wifi.ip());
        }
        Err(e) => {
            ui::show_wifi_failed(&mut lcd)?;
            error!("[P0-02] Échec connexion WiFi: {}", e);
            // Effacer les credentials potentiellement invalides
            let _ = wifi.clear_credentials();
            // Reboot après 5 s pour permettre un nouveau provisioning
            FreeRtos::delay_ms(5000);
            unsafe { esp_idf_svc::sys::esp_restart() };
        }
    }

    // ----------------------------------------------------------------
    // [P0-03] Configuration + ping serveur GET /health
    // ----------------------------------------------------------------

    info!("[P0-03] Configuration serveur...");
    let mut server = ServerPing::new(nvs_partition.clone())?;

    // Écran de configuration : IP + port + test connexion
    {
        // Extraire host/port avant d'emprunter server en mutable dans la closure
        let cur_host: heapless::String<64> = {
            let mut s = heapless::String::new();
            for c in server.host().chars() { let _ = s.push(c); }
            s
        };
        let cur_port = server.port();
        let (srv_host, srv_port) = ui::run_server_config(
            &mut lcd,
            cur_host.as_str(),
            cur_port,
            &mut |host, port| server.ping_address(host, port),
        )?;
        server.set_address(srv_host.as_str(), srv_port)?;
        info!("[P0-03] Adresse serveur configurée: {}:{}", srv_host, srv_port);
    }

    let ping = server.ping();
    if ping.ok {
        ui::show_server_ok(&mut lcd, ping.version.as_str(), ping.latency_ms)?;
        info!("[P0-03] Serveur OK ✓ — v{} {}ms", ping.version, ping.latency_ms);
    } else {
        ui::show_server_unreachable(&mut lcd)?;
        error!("[P0-03] Serveur injoignable ✗");
    }

    // ----------------------------------------------------------------
    // Phase 1 — Boucle READY (idle → listening → …)
    // ----------------------------------------------------------------

    info!("=== Phase 0 complète — boucle READY ===");

    // ── Phase 1.2 : Initialisation driver I2S microphone ────────────────────
    // Créé une seule fois, réutilisé à chaque cycle READY.
    let mut mic_opt: Option<MicCapture> = match MicCapture::new(
        peripherals.i2s0,
        peripherals.pins.gpio48,  // BCK
        peripherals.pins.gpio38,  // WS / LRCK
        peripherals.pins.gpio39,  // DIN  (ES7210 → ESP32)
        peripherals.pins.gpio2,   // MCLK
    ) {
        Ok(m)  => { info!("[P1.2] MicCapture initialisé"); Some(m) }
        Err(e) => { log::warn!("[P1.2] MicCapture échoué: {} — capture désactivée", e); None }
    };

    loop {
        // Factory reset toujours surveillé (appui long BOOT)
        maybe_factory_reset(&mut wifi, nvs_partition.clone())?;

        match ui::run_ready_loop(&mut lcd, wifi.is_connected(), ping.ok)? {
            ui::ReadyAction::StartListening => {
                info!("[READY] Tap micro → démarrage écoute");

                // ── Phase 1.2 : Capture audio I2S ───────────────────────
                // run_ready_loop a déjà dessiné l'état Listening.
                let pcm_mono = if let Some(ref mut mic) = mic_opt {
                    mic.capture().unwrap_or_else(|e| {
                        log::warn!("[READY] Capture échouée: {}", e);
                        Vec::new()
                    })
                } else {
                    FreeRtos::delay_ms(3_000);  // stub si pas de mic
                    Vec::new()
                };

                // ── Phase 1.3 : POST /edge/audio ─────────────────────────
                ui::update_ready_state(&mut lcd, ui::DeviceState::Thinking)?;

                let audio_answer = if !pcm_mono.is_empty() {
                    match server.post_audio(&pcm_mono) {
                        Ok(resp) => {
                            info!("[READY] Réponse serveur: intent={} answer={}",
                                resp.intent, resp.answer);
                            resp.answer
                        }
                        Err(e) => {
                            log::warn!("[READY] POST /edge/audio échoué: {}", e);
                            let mut s = heapless::String::<256>::new();
                            let _ = s.push_str("Erreur serveur");
                            s
                        }
                    }
                } else {
                    // Pas de données audio — pas d'envoi
                    let mut s = heapless::String::<256>::new();
                    let _ = s.push_str("Pas d'audio capturé");
                    s
                };

                // ── Phase 1.4 : Affichage réponse + état PARLE ───────────
                ui::update_ready_state(&mut lcd, ui::DeviceState::Speaking)?;
                info!("[READY] Réponse: {}", audio_answer);
                // Pause courte pour afficher l'état PARLE (TTS I2S à implémenter Phase 1.5)
                FreeRtos::delay_ms(2_500);

                // Retour Idle → prochain tour de boucle
                info!("[READY] Cycle terminé → retour Idle");
            }
        }
    }
}
