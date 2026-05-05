/// server/mod.rs — Ping HTTP GET /health vers le serveur Leon
///
/// Utilise esp_idf_svc::http::client (wrapper esp-idf EspHttpConnection).

use anyhow::{bail, Result};
use esp_idf_svc::{
    http::client::{Configuration as HttpConfig, EspHttpConnection},
    nvs::{EspNvs, NvsDefault},
};
use embedded_svc::http::client::Client as HttpClient;
use embedded_svc::http::Method;
use heapless::String as HString;
use log::{info, warn};

const NVS_NAMESPACE_SERVER: &str = "server_cfg";
const NVS_KEY_HOST:         &str = "host";
const NVS_KEY_PORT:         &str = "port";
#[allow(dead_code)]
const DEFAULT_HOST:         &str = "192.168.1.100";
#[allow(dead_code)]
const DEFAULT_PORT:         u16  = 8080;
const TIMEOUT_MS:           u32  = 5_000;
const RESPONSE_BUF_SIZE:    usize = 256;

#[derive(Debug, Clone)]
pub struct PingResult {
    pub ok:         bool,
    pub latency_ms: u32,
    pub version:    HString<32>,
}

pub struct ServerPing {
    nvs:  EspNvs<NvsDefault>,
    host: HString<64>,
    port: u16,
}

impl ServerPing {
    pub fn new(nvs_partition: esp_idf_svc::nvs::EspDefaultNvsPartition) -> Result<Self> {
        let nvs = EspNvs::new(nvs_partition, NVS_NAMESPACE_SERVER, true)?;
        let mut ping = Self {
            nvs,
            host: HString::new(),
            port: DEFAULT_PORT,
        };
        ping.load_address();
        Ok(ping)
    }

    // ----------------------------------------------------------------
    // NVS
    // ----------------------------------------------------------------

    fn load_address(&mut self) {
        let mut host_buf = [0u8; 65];
        let mut port_buf = [0u8; 2];

        if let Ok(Some(bytes)) = self.nvs.get_blob(NVS_KEY_HOST, &mut host_buf) {
            if let Ok(s) = core::str::from_utf8(bytes) {
                self.host.clear();
                let _ = self.host.push_str(s);
            }
        }
        if let Ok(Some([a, b])) = self.nvs.get_blob(NVS_KEY_PORT, &mut port_buf).map(|r| r.map(|b| [b[0], b[1]])) {
            self.port = u16::from_le_bytes([a, b]);
        }

        // Fallback si rien en NVS
        if self.host.is_empty() {
            let _ = self.host.push_str(DEFAULT_HOST);
            self.port = DEFAULT_PORT;
        }
        info!("Serveur configuré: {}:{}", self.host, self.port);
    }

    #[allow(dead_code)]
    pub fn set_address(&mut self, host: &str, port: u16) -> Result<()> {
        self.host.clear();
        let _ = self.host.push_str(host);
        self.port = port;

        self.nvs.set_blob(NVS_KEY_HOST, host.as_bytes())?;
        self.nvs.set_blob(NVS_KEY_PORT, &port.to_le_bytes())?;
        info!("Adresse serveur sauvegardée: {}:{}", host, port);
        Ok(())
    }

    pub fn clear_address(&mut self) -> Result<()> {
        let _ = self.nvs.remove(NVS_KEY_HOST);
        let _ = self.nvs.remove(NVS_KEY_PORT);
        self.host.clear();
        let _ = self.host.push_str(DEFAULT_HOST);
        self.port = DEFAULT_PORT;
        info!("Adresse serveur effacée (fallback défaut activé)");
        Ok(())
    }

    // ----------------------------------------------------------------
    // GET /health
    // ----------------------------------------------------------------

    /// Accesseurs pour l'UI
    pub fn host(&self) -> &str { self.host.as_str() }
    pub fn port(&self) -> u16  { self.port }

    /// Teste la connectivité vers une adresse donnée sans modifier la config NVS.
    pub fn ping_address(&mut self, host: &str, port: u16) -> bool {
        let url = format!("http://{}:{}/health", host, port);
        info!("Test connexion: GET {}", url);
        self.do_request(url).is_ok()
    }

    pub fn ping(&mut self) -> PingResult {
        let url = format!("http://{}:{}/health", self.host, self.port);
        info!("GET {}", url);

        let t0 = unsafe { esp_idf_svc::sys::esp_timer_get_time() };

        let result = self.do_request(url);

        let t1 = unsafe { esp_idf_svc::sys::esp_timer_get_time() };
        let latency_ms = ((t1 - t0) / 1000) as u32;

        match result {
            Ok(body) => {
                let version = extract_version(&body);
                info!("Serveur OK ✓ — v{} {}ms", version, latency_ms);
                PingResult { ok: true, latency_ms, version }
            }
            Err(e) => {
                warn!("Serveur injoignable ✗ — {}", e);
                let v: HString<32> = HString::new();
                PingResult { ok: false, latency_ms: 0, version: v }
            }
        }
    }

    fn do_request(&mut self, url: String) -> Result<HString<RESPONSE_BUF_SIZE>> {
        let cfg = HttpConfig {
            timeout: Some(core::time::Duration::from_millis(TIMEOUT_MS as u64)),
            ..Default::default()
        };
        let conn = EspHttpConnection::new(&cfg)?;
        let mut client = HttpClient::wrap(conn);

        let headers: &[(&str, &str)] = &[];
        let request = client.request(Method::Get, &url, headers)?;
        let mut response = request.submit()?;

        if response.status() != 200 {
            bail!("HTTP {}", response.status());
        }

        let mut buf = [0u8; RESPONSE_BUF_SIZE];
        let n = response.read(&mut buf).unwrap_or(0);

        let s = core::str::from_utf8(&buf[..n]).unwrap_or("");
        let mut result: HString<RESPONSE_BUF_SIZE> = HString::new();
        let _ = result.push_str(&s[..s.len().min(RESPONSE_BUF_SIZE)]);
        Ok(result)
    }
}

/// Extraction naïve de "version" depuis {"status":"ok","version":"x.y.z"}
fn extract_version(body: &str) -> HString<32> {
    let mut result: HString<32> = HString::new();
    if let Some(pos) = body.find("\"version\"") {
        let after = &body[pos + 9..];
        if let Some(start) = after.find('"') {
            let value = &after[start + 1..];
            if let Some(end) = value.find('"') {
                let _ = result.push_str(&value[..end.min(31)]);
            }
        }
    }
    result
}
