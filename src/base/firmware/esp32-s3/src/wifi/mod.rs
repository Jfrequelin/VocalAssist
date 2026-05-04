/// wifi/mod.rs — Connexion WiFi + provisioning NVS
///
/// Utilise esp-idf-svc pour WiFi STA et esp_idf_svc::nvs pour la persistance.

use anyhow::Result;
use esp_idf_svc::{
    eventloop::EspSystemEventLoop,
    nvs::{EspDefaultNvsPartition, EspNvs, NvsDefault},
    wifi::{AuthMethod, BlockingWifi, ClientConfiguration, Configuration, EspWifi},
};
use heapless::String as HString;
use log::info;

const NVS_NAMESPACE: &str = "wifi_creds";
const NVS_KEY_SSID: &str = "ssid";
const NVS_KEY_PASS: &str = "password";
#[allow(dead_code)]
const WIFI_CONNECT_TIMEOUT_MS: u32 = 15_000;

pub struct WifiManager<'d> {
    wifi:      BlockingWifi<EspWifi<'d>>,
    nvs:       EspNvs<NvsDefault>,
    connected: bool,
    ip:        HString<16>,
}

impl<'d> WifiManager<'d> {
    pub fn new(
        modem: esp_idf_hal::modem::Modem<'d>,
        sysloop: EspSystemEventLoop,
        nvs_partition: EspDefaultNvsPartition,
    ) -> Result<Self> {
        let wifi    = EspWifi::new(modem, sysloop.clone(), Some(nvs_partition.clone()))?;
        let wifi    = BlockingWifi::wrap(wifi, sysloop)?;
        let nvs     = EspNvs::new(nvs_partition, NVS_NAMESPACE, true)?;

        Ok(Self { wifi, nvs, connected: false, ip: HString::new() })
    }

    // ----------------------------------------------------------------
    // NVS
    // ----------------------------------------------------------------

    /// Lit les credentials depuis NVS.
    /// Retourne None si absents ou vides.
    pub fn load_credentials(&mut self) -> Option<(HString<32>, HString<64>)> {
        let mut ssid_buf = [0u8; 33];
        let mut pass_buf = [0u8; 65];

        let ssid_bytes = self.nvs.get_blob(NVS_KEY_SSID, &mut ssid_buf).ok()??;
        let pass_bytes = self.nvs.get_blob(NVS_KEY_PASS, &mut pass_buf).ok()??;

        if ssid_bytes.is_empty() { return None; }

        let ssid_str = core::str::from_utf8(ssid_bytes).ok()?;
        let pass_str = core::str::from_utf8(pass_bytes).ok()?;

        let mut ssid: HString<32> = HString::new();
        let mut pass: HString<64> = HString::new();
        ssid.push_str(ssid_str).ok()?;
        pass.push_str(pass_str).ok()?;

        info!("NVS: credentials trouvés pour SSID '{}'", ssid);
        Some((ssid, pass))
    }

    /// Sauvegarde les credentials en NVS.
    pub fn save_credentials(&mut self, ssid: &str, password: &str) -> Result<()> {
        self.nvs.set_blob(NVS_KEY_SSID, ssid.as_bytes())?;
        self.nvs.set_blob(NVS_KEY_PASS, password.as_bytes())?;
        info!("NVS: credentials sauvegardés (SSID: {})", ssid);
        Ok(())
    }

    /// Efface les credentials NVS (pour forcer un nouveau provisioning).
    pub fn clear_credentials(&mut self) -> Result<()> {
        let _ = self.nvs.remove(NVS_KEY_SSID);
        let _ = self.nvs.remove(NVS_KEY_PASS);
        info!("NVS: credentials effacés");
        Ok(())
    }

    // ----------------------------------------------------------------
    // Connexion
    // ----------------------------------------------------------------

    /// Tente la connexion avec les credentials fournis.
    /// Met à jour `self.connected` et `self.ip` en cas de succès.
    pub fn connect(&mut self, ssid: &str, password: &str) -> Result<()> {
        info!("WiFi: connexion à '{}' ...", ssid);

        let auth_method = if password.is_empty() {
            AuthMethod::None
        } else {
            AuthMethod::WPA2Personal
        };

        let client_cfg = ClientConfiguration {
            ssid:        ssid.try_into().map_err(|_| anyhow::anyhow!("SSID trop long"))?,
            password:    password.try_into().map_err(|_| anyhow::anyhow!("MDP trop long"))?,
            auth_method,
            ..Default::default()
        };

        self.wifi.set_configuration(&Configuration::Client(client_cfg))?;
        self.wifi.start()?;
        info!("WiFi: démarré en mode STA");

        self.wifi.connect()?;
        info!("WiFi: en attente d'une IP...");

        self.wifi.wait_netif_up()?;

        let ip_info = self.wifi.wifi().sta_netif().get_ip_info()?;
        let ip_str  = format!("{}", ip_info.ip);

        self.connected = true;
        self.ip.clear();
        for c in ip_str.chars().take(15) {
            let _ = self.ip.push(c);
        }

        info!("WiFi: connecté — IP {}", self.ip);
        Ok(())
    }

    /// Scan et retourne les SSIDs disponibles (jusqu'à 8).
    pub fn scan(&mut self) -> Result<heapless::Vec<HString<32>, 8>> {
        info!("WiFi: scan en cours...");
        self.wifi.start()?;
        let aps = self.wifi.scan()?;
        self.wifi.stop()?;

        let mut result: heapless::Vec<HString<32>, 8> = heapless::Vec::new();
        for ap in aps.iter().take(8) {
            let ssid_str = ap.ssid.as_str();
            if ssid_str.is_empty() { continue; }
            let mut s: HString<32> = HString::new();
            let _ = s.push_str(&ssid_str[..ssid_str.len().min(32)]);
            let _ = result.push(s);
        }

        info!("WiFi: {} réseaux trouvés", result.len());
        Ok(result)
    }

    // ----------------------------------------------------------------
    // Accesseurs
    // ----------------------------------------------------------------

    pub fn is_connected(&self) -> bool { self.connected }
    pub fn ip(&self) -> &str          { self.ip.as_str() }
}
