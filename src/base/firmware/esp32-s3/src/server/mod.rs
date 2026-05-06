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
use embedded_io::Write as _;
use heapless::String as HString;
use log::{info, warn};
use crate::config::network::{
    AUDIO_RESP_CHUNK_SIZE, AUDIO_RESP_MAX_SIZE, DEFAULT_HOST, DEFAULT_PORT,
    NET_MAX_PCM_BYTES, NET_SILENCE_PAD_SAMPLES, NET_SILENCE_THRESHOLD,
    NVS_KEY_HOST, NVS_KEY_PORT, NVS_NAMESPACE_SERVER, RESPONSE_BUF_SIZE, TIMEOUT_MS,
};

/// Réponse du serveur à un POST /edge/audio
#[derive(Debug, Clone)]
pub struct AudioResponse {
    /// Texte réponse (TTS ou affiché à l'écran)
    pub answer: HString<256>,
    /// Intent détecté
    pub intent: HString<64>,
    /// Audio PCM16LE mono renvoyé par le serveur (premier chunk, optionnel)
    pub audio_pcm: Option<Vec<u8>>,
    /// Identifiant de session streaming (présent si has_more=true)
    pub stream_id: Option<HString<64>>,
    /// Indique s'il y a d'autres chunks à récupérer via GET /edge/stream/{id}/{idx}
    pub has_more: bool,
    /// Nombre total de chunks dans la session
    pub total_chunks: u32,
}

/// Un chunk audio supplémentaire récupéré via GET /edge/stream/{stream_id}/{idx}
#[derive(Debug)]
pub struct StreamChunk {
    /// Audio PCM16LE mono
    pub audio_pcm: Option<Vec<u8>>,
    /// Vrai si d'autres chunks suivent encore
    pub has_more: bool,
}

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

    // ----------------------------------------------------------------
    // POST /edge/audio
    // ----------------------------------------------------------------

    /// Envoie les bytes PCM mono 16 bits 16 kHz vers POST /edge/audio.
    ///
    /// Construit le payload JSON conforme au contrat EdgeAudioRequest v2 :
    /// ```json
    /// {
    ///   "device_id": "edge-001",
    ///   "correlation_id": "<timestamp>",
    ///   "timestamp_ms": <u64>,
    ///   "sample_rate_hz": 16000,
    ///   "channels": 1,
    ///   "encoding": "pcm16le",
    ///   "audio_base64": "<base64>"
    /// }
    /// ```
    pub fn post_audio(&mut self, pcm_mono: &[u8]) -> Result<AudioResponse> {
        use crate::audio::base64_encode;

        let url = format!("http://{}:{}/edge/audio", self.host, self.port);
        let ts_ms = unsafe { esp_idf_svc::sys::esp_timer_get_time() } / 1000;
        let cid   = format!("edge-{}", ts_ms);

        // Optimisation transfert: retire les silences périphériques et borne la taille.
        let pcm_net = optimize_pcm_for_network(pcm_mono);

        let audio_b64 = base64_encode(&pcm_net);
        info!(
            "[SERVER] POST /edge/audio — {} -> {} bytes PCM (net) → {} chars B64",
            pcm_mono.len(),
            pcm_net.len(),
            audio_b64.len()
        );

        // Construire le JSON manuellement (serde_json en alloc mode)
        let body = format!(
            r#"{{"device_id":"edge-001","correlation_id":"{cid}","timestamp_ms":{ts_ms},"sample_rate_hz":16000,"channels":1,"encoding":"pcm16le","audio_base64":"{audio_b64}"}}"#
        );

        let cfg = HttpConfig {
            timeout: Some(core::time::Duration::from_millis(15_000)),
            ..Default::default()
        };
        let conn = EspHttpConnection::new(&cfg)?;
        let mut client = HttpClient::wrap(conn);

        let headers: &[(&str, &str)] = &[("content-type", "application/json")];
        let request  = client.request(Method::Post, &url, headers)?;
        let mut request = request;
        request.write_all(body.as_bytes())?;
        request.flush()?;
        let mut resp = request.submit()?;

        let status = resp.status();
        info!("[SERVER] Réponse HTTP {}", status);
        if status != 200 && status != 202 {
            bail!("[SERVER] HTTP {} depuis /edge/audio", status);
        }

        // Lire la réponse complète en chunks (nécessaire pour audio_base64).
        let mut body_bytes: Vec<u8> = Vec::with_capacity(8 * 1024);
        let mut chunk = [0u8; AUDIO_RESP_CHUNK_SIZE];
        loop {
            let n = resp.read(&mut chunk).unwrap_or(0);
            if n == 0 {
                break;
            }
            if body_bytes.len() + n > AUDIO_RESP_MAX_SIZE {
                bail!("[SERVER] Réponse /edge/audio trop volumineuse");
            }
            body_bytes.extend_from_slice(&chunk[..n]);
        }

        let body_str = core::str::from_utf8(&body_bytes).unwrap_or("");
        info!("[SERVER] Réponse body: {}", &body_str[..body_str.len().min(120)]);

        Ok(parse_audio_response(body_str))
    }

    /// Récupère le chunk audio n°chunk_idx depuis GET /edge/stream/{stream_id}/{chunk_idx}.
    ///
    /// Retourne `StreamChunk { audio_pcm, has_more }` ou une erreur.
    pub fn get_stream_chunk(&mut self, stream_id: &str, chunk_idx: u32) -> Result<StreamChunk> {
        let url = format!("http://{}:{}/edge/stream/{}/{}", self.host, self.port, stream_id, chunk_idx);
        info!("[STREAM] GET {} (chunk {})", url, chunk_idx);

        let cfg = HttpConfig {
            timeout: Some(core::time::Duration::from_millis(15_000)),
            ..Default::default()
        };
        let conn = EspHttpConnection::new(&cfg)?;
        let mut client = HttpClient::wrap(conn);

        let headers: &[(&str, &str)] = &[];
        let request = client.request(embedded_svc::http::Method::Get, &url, headers)?;
        let mut resp = request.submit()?;

        let status = resp.status();
        if status != 200 {
            bail!("[STREAM] HTTP {} pour chunk {}", status, chunk_idx);
        }

        let mut body_bytes: Vec<u8> = Vec::with_capacity(8 * 1024);
        let mut chunk_buf = [0u8; AUDIO_RESP_CHUNK_SIZE];
        loop {
            let n = resp.read(&mut chunk_buf).unwrap_or(0);
            if n == 0 { break; }
            if body_bytes.len() + n > AUDIO_RESP_MAX_SIZE {
                bail!("[STREAM] Chunk trop volumineux");
            }
            body_bytes.extend_from_slice(&chunk_buf[..n]);
        }

        let body_str = core::str::from_utf8(&body_bytes).unwrap_or("");
        info!("[STREAM] chunk {} reçu {} bytes JSON", chunk_idx, body_bytes.len());

        let audio_pcm = extract_field_owned(body_str, "audio_base64")
            .and_then(|b64| crate::audio::base64_decode(&b64).ok());
        let has_more = extract_bool(body_str, "has_more");

        Ok(StreamChunk { audio_pcm, has_more })
    }
}

fn optimize_pcm_for_network(pcm_mono: &[u8]) -> Vec<u8> {
    if pcm_mono.len() < 4 {
        return pcm_mono.to_vec();
    }

    let samples = pcm_mono.len() / 2;
    let mut first_voice: Option<usize> = None;
    let mut last_voice: usize = 0;

    for i in 0..samples {
        let b0 = pcm_mono[2 * i];
        let b1 = pcm_mono[2 * i + 1];
        let s = i16::from_le_bytes([b0, b1]);
        if s.unsigned_abs() > NET_SILENCE_THRESHOLD as u16 {
            if first_voice.is_none() {
                first_voice = Some(i);
            }
            last_voice = i;
        }
    }

    let trimmed = if let Some(first) = first_voice {
        let start = first.saturating_sub(NET_SILENCE_PAD_SAMPLES);
        let end = (last_voice + NET_SILENCE_PAD_SAMPLES + 1).min(samples);
        let start_b = start * 2;
        let end_b = end * 2;
        pcm_mono[start_b..end_b].to_vec()
    } else {
        // Si aucune voix n'est détectée (seuil trop strict, attaque de phrase),
        // envoyer une fenêtre longue pour laisser une chance au STT.
        let keep = pcm_mono.len().min(NET_MAX_PCM_BYTES);
        pcm_mono[..keep].to_vec()
    };

    if trimmed.len() > NET_MAX_PCM_BYTES {
        trimmed[..NET_MAX_PCM_BYTES].to_vec()
    } else {
        trimmed
    }
}


/// Extraction naïve de "answer" et "intent" depuis la réponse /edge/audio.
fn parse_audio_response(body: &str) -> AudioResponse {
    let audio_pcm = extract_field_owned(body, "audio_base64")
        .and_then(|b64| crate::audio::base64_decode(&b64).ok());

    let has_more = extract_bool(body, "has_more");
    let stream_id: Option<HString<64>> = if has_more {
        let s: HString<64> = extract_field(body, "stream_id");
        if s.is_empty() { None } else { Some(s) }
    } else {
        None
    };
    let total_chunks = extract_u32(body, "total_chunks").unwrap_or(1);

    AudioResponse {
        answer: extract_field(body, "answer"),
        intent: extract_field(body, "intent"),
        audio_pcm,
        stream_id,
        has_more,
        total_chunks,
    }
}

/// Extrait la valeur d'un champ JSON string de manière naïve (sans dépendance serde).
fn extract_field<const N: usize>(body: &str, key: &str) -> HString<N> {
    let mut result: HString<N> = HString::new();
    let needle = format!("\"{}\"", key);
    if let Some(pos) = body.find(&needle) {
        let after = &body[pos + needle.len()..];
        if let Some(colon) = after.find(':') {
            let val = after[colon + 1..].trim_start();
            if val.starts_with('"') {
                let inner = &val[1..];
                if let Some(end) = inner.find('"') {
                    let _ = result.push_str(&inner[..end.min(N - 1)]);
                }
            }
        }
    }
    result
}

/// Extrait la valeur d'un champ JSON string en String allouée.
fn extract_field_owned(body: &str, key: &str) -> Option<String> {
    let needle = format!("\"{}\"", key);
    let pos = body.find(&needle)?;
    let after = &body[pos + needle.len()..];
    let colon = after.find(':')?;
    let val = after[colon + 1..].trim_start();
    if !val.starts_with('"') {
        return None;
    }
    let inner = &val[1..];
    let end = inner.find('"')?;
    Some(inner[..end].to_owned())
}
/// Extrait la valeur d'un champ JSON booléen (true/false).
fn extract_bool(body: &str, key: &str) -> bool {
    let needle = format!("\"{}\"" , key);
    if let Some(pos) = body.find(&needle) {
        let after = &body[pos + needle.len()..];
        if let Some(colon) = after.find(':') {
            let val = after[colon + 1..].trim_start();
            return val.starts_with("true");
        }
    }
    false
}

/// Extrait la valeur d'un champ JSON entier (u32).
fn extract_u32(body: &str, key: &str) -> Option<u32> {
    let needle = format!("\"{}\"" , key);
    let pos = body.find(&needle)?;
    let after = &body[pos + needle.len()..];
    let colon = after.find(':')?;
    let val = after[colon + 1..].trim_start();
    let end = val.find(|c: char| !c.is_ascii_digit()).unwrap_or(val.len());
    val[..end].parse().ok()
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
