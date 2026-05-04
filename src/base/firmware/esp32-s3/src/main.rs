
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
mod wifi;
mod server;
mod touch;

use lcd::LcdDisplay;
use lcd::ui;
use wifi::WifiManager;
use server::ServerPing;
use touch::CST816S;

// Adresse serveur par défaut — remplacée par NVS si déjà configurée
#[allow(dead_code)]
const DEFAULT_SERVER_HOST: &str = "192.168.1.100";
#[allow(dead_code)]
const DEFAULT_SERVER_PORT: u16  = 8080;

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

    // ----------------------------------------------------------------
    // [P0-02] WiFi provisioning
    // ----------------------------------------------------------------

    info!("[P0-02] Démarrage WiFi...");
    let mut wifi = WifiManager::new(
        peripherals.modem,
        sysloop.clone(),
        nvs_partition.clone(),
    )?;

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
    // [P0-03] Ping serveur GET /health
    // ----------------------------------------------------------------

    info!("[P0-03] Test lien serveur...");
    let mut server = ServerPing::new(nvs_partition)?;

    // Utiliser l'adresse par défaut si rien en NVS
    // (server::ServerPing::new gère déjà le fallback)

    let ping = server.ping();
    if ping.ok {
        ui::show_server_ok(&mut lcd, ping.version.as_str(), ping.latency_ms)?;
        info!("[P0-03] Serveur OK ✓ — v{} {}ms", ping.version, ping.latency_ms);
    } else {
        ui::show_server_unreachable(&mut lcd)?;
        error!("[P0-03] Serveur injoignable ✗ — vérifier l'adresse et le réseau");
    }

    // ----------------------------------------------------------------
    // État READY — Phase 0 terminée
    // ----------------------------------------------------------------

    info!("=== Phase 0 terminée — état READY ===");
    info!("Prochain: Phase 1 pipeline vocal (wake word, VAD, TTS)");

    // Boucle principale — heartbeat log toutes les 30 s
    loop {
        FreeRtos::delay_ms(30_000);
        info!("[HEARTBEAT] WiFi: {} | Serveur: {}",
              if wifi.is_connected() { "OK" } else { "KO" },
              if ping.ok { "OK" } else { "KO" });
    }
}
