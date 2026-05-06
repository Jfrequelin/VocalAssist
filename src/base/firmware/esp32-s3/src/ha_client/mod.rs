/// ha_client/mod.rs — Client WebSocket direct vers Home Assistant Assist Pipeline
///
/// Protocole :
///   1. TCP → ws://HA_HOST:8123/api/websocket (WebSocket manuel sur TcpStream)
///   2. Auth : {"type":"auth","access_token":"TOKEN"}
///   3. assist_pipeline/run  start_stage=stt  end_stage=tts
///   4. Streaming audio PCM16LE 16kHz en binary frames (prefixé handler_id)
///   5. Réception events stt-end (transcript) + tts-end (url)
///   6. Téléchargement WAV TTS via HTTP → PCM extrait pour lecture

use anyhow::{anyhow, bail, Context, Result};
use esp_idf_svc::{
    http::client::{Configuration as HttpConfig, EspHttpConnection},
    nvs::{EspDefaultNvsPartition, EspNvs, NvsDefault},
};
use embedded_svc::http::client::Client as HttpClient;
use heapless::String as HString;
use log::{info, warn};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

use crate::netlog;

// ─── Config NVS ──────────────────────────────────────────────────────────────
const NVS_NS: &str = "ha_cfg";
const NVS_HOST: &str = "host";
const NVS_PORT: &str = "port";
const NVS_TOKEN: &str = "token";
const NVS_LANG: &str = "lang";
pub const DEFAULT_HOST: &str = "192.168.51.17";
#[allow(dead_code)]
pub const DEFAULT_PORT: u16 = 8123;

/// Langue STT/TTS, ex. "fr-FR" ou "en-US".
/// Surcharger avec `HA_LANGUAGE=fr-FR cargo build`.
const DEFAULT_LANGUAGE: &str = {
    match option_env!("HA_LANGUAGE") {
        Some(v) => v,
        None    => "fr-FR",
    }
};

/// Token compilé depuis la variable d'environnement HA_TOKEN (build-time).
/// Set `HA_TOKEN=<votre_token>` avant `cargo build`.
const DEFAULT_TOKEN: &str = {
    match option_env!("HA_TOKEN") {
        Some(v) => v,
        None => "",
    }
};

// ─── Types publics ────────────────────────────────────────────────────────────
pub struct HaClient {
    nvs:             EspNvs<NvsDefault>,
    host:            HString<64>,
    port:            u16,
    token:           HString<256>,
    language:        HString<16>,
    /// conversation_id reçu du dernier run-end (contexte multi-tour).
    conversation_id: Option<HString<64>>,
}

pub struct HaResponse {
    /// Ce que l'utilisateur a dit (STT).
    pub transcript: HString<256>,
    /// Ce que Home Assistant a répondu (NLU intent-end).
    pub answer:     HString<256>,
    /// PCM16LE mono raw (extrait du WAV retourné par HA/Piper).
    pub tts_pcm:    Option<Vec<u8>>,
}

// ─── Constantes WebSocket ─────────────────────────────────────────────────────
const WS_OP_TEXT: u8   = 0x01;
const WS_OP_BINARY: u8 = 0x02;
const WS_OP_CLOSE: u8  = 0x08;
// Clé WS fixe (RFC 6455 exemple) — suffisant pour connexion locale non-TLS
const WS_KEY: &str = "dGhlIHNhbXBsZSBub25jZQ==";
// Masque fixe client→serveur (RFC impose masque mais pas de valeur)
const WS_MASK: [u8; 4] = [0x37, 0xFA, 0x21, 0x3D];
// Taille d'un chunk audio envoyé vers HA (~250ms de PCM16 16kHz)
const AUDIO_CHUNK: usize = 8_000;

// ─── HaClient impl ────────────────────────────────────────────────────────────
impl HaClient {
    pub fn new(nvs_partition: EspDefaultNvsPartition) -> Result<Self> {
        let nvs = EspNvs::new(nvs_partition, NVS_NS, true)?;
        let mut client = Self {
            nvs,
            host: HString::new(),
            port: DEFAULT_PORT,
            token: HString::new(),
            language: HString::new(),
            conversation_id: None,
        };
        client.load_config();
        Ok(client)
    }

    fn load_config(&mut self) {
        let mut buf = [0u8; 257];

        // Host
        if let Ok(Some(b)) = self.nvs.get_blob(NVS_HOST, &mut buf) {
            if let Ok(s) = core::str::from_utf8(b) {
                self.host.clear();
                let _ = self.host.push_str(s);
            }
        }
        if self.host.is_empty() {
            let _ = self.host.push_str(DEFAULT_HOST);
        }

        // Port
        let mut pb = [0u8; 2];
        if let Ok(Some(_)) = self.nvs.get_blob(NVS_PORT, &mut pb) {
            self.port = u16::from_le_bytes(pb);
        }

        // Token (jusqu'à 256 chars)
        if let Ok(Some(b)) = self.nvs.get_blob(NVS_TOKEN, &mut buf) {
            if let Ok(s) = core::str::from_utf8(b) {
                self.token.clear();
                let _ = self.token.push_str(s);
            }
        }
        if self.token.is_empty() && !DEFAULT_TOKEN.is_empty() {
            let _ = self.token.push_str(DEFAULT_TOKEN);
        }

        // Language
        if let Ok(Some(b)) = self.nvs.get_blob(NVS_LANG, &mut buf) {
            if let Ok(s) = core::str::from_utf8(b) {
                self.language.clear();
                let _ = self.language.push_str(s);
            }
        }
        if self.language.is_empty() {
            let _ = self.language.push_str(DEFAULT_LANGUAGE);
        }

        info!("[HA] Config: {}:{} lang={} token={}",
            self.host, self.port, self.language,
            if self.token.is_empty() { "ABSENT" } else { "OK" }
        );
        netlog::info(&format!(
            "[HA] Config {}:{} lang={} token={}",
            self.host,
            self.port,
            self.language,
            if self.token.is_empty() { "ABSENT" } else { "OK" }
        ));
    }

    pub fn host(&self) -> &str { self.host.as_str() }
    pub fn port(&self) -> u16  { self.port }
    pub fn token_ok(&self) -> bool { !self.token.is_empty() }
    #[allow(dead_code)]
    pub fn language(&self) -> &str { self.language.as_str() }

    /// Effacer le contexte de conversation (multi-tour → nouvelle session).
    #[allow(dead_code)]
    pub fn reset_conversation(&mut self) { self.conversation_id = None; }

    /// Persister host+port dans NVS.
    #[allow(dead_code)]
    pub fn set_address(&mut self, host: &str, port: u16) -> Result<()> {
        self.nvs.set_blob(NVS_HOST, host.as_bytes())?;
        self.nvs.set_blob(NVS_PORT, &port.to_le_bytes())?;
        self.host.clear();
        let _ = self.host.push_str(host);
        self.port = port;
        Ok(())
    }

    /// Persister le token dans NVS.
    #[allow(dead_code)]
    pub fn set_token(&mut self, token: &str) -> Result<()> {
        self.nvs.set_blob(NVS_TOKEN, token.as_bytes())?;
        self.token.clear();
        let _ = self.token.push_str(token);
        Ok(())
    }

    /// Persister la langue dans NVS.
    #[allow(dead_code)]
    pub fn set_language(&mut self, lang: &str) -> Result<()> {
        self.nvs.set_blob(NVS_LANG, lang.as_bytes())?;
        self.language.clear();
        let _ = self.language.push_str(lang);
        Ok(())
    }

    // ─── API principale ───────────────────────────────────────────────────────

    /// Exécuter le pipeline voix complet : audio PCM16LE → STT+NLU+TTS via HA.
    pub fn run_pipeline(&mut self, pcm_mono: &[u8]) -> Result<HaResponse> {
        if self.token.is_empty() {
            netlog::error("[HA] Token absent");
            bail!("[HA] Token absent — configurer HA_TOKEN ou NVS ha_cfg/token");
        }

        let addr = format!("{}:{}", self.host, self.port);
        info!("[HA] Connexion TCP à {}", addr);
        netlog::info(&format!("[HA] TCP connect {}", addr));

        let mut stream = TcpStream::connect(&addr)
            .with_context(|| format!("TCP connect {} échoué", addr))?;
        stream.set_read_timeout(Some(Duration::from_secs(30)))?;
        stream.set_write_timeout(Some(Duration::from_secs(10)))?;
        stream.set_nodelay(true)?; // réduire latence TCP

        // ── Handshake WebSocket ────────────────────────────────────────────────
        let hs = format!(
            "GET /api/websocket HTTP/1.1\r\n\
             Host: {}:{}\r\n\
             Upgrade: websocket\r\n\
             Connection: Upgrade\r\n\
             Sec-WebSocket-Key: {}\r\n\
             Sec-WebSocket-Version: 13\r\n\
             \r\n",
            self.host, self.port, WS_KEY
        );
        stream.write_all(hs.as_bytes())?;

        // Lire la réponse HTTP jusqu'au double CRLF
        let mut resp_buf = Vec::with_capacity(512);
        let mut b = [0u8; 1];
        loop {
            stream.read_exact(&mut b)?;
            resp_buf.push(b[0]);
            if resp_buf.ends_with(b"\r\n\r\n") { break; }
            if resp_buf.len() > 4096 { bail!("[HA] Réponse HTTP trop longue"); }
        }
        let resp_str = String::from_utf8_lossy(&resp_buf);
        if !resp_str.contains("101") {
            netlog::error("[HA] WebSocket upgrade refusé");
            bail!("[HA] Upgrade WS refusé:\n{}", &resp_str[..resp_str.len().min(300)]);
        }
        info!("[HA] WebSocket établi");
        netlog::info("[HA] WebSocket établi");

        // ── Auth ──────────────────────────────────────────────────────────────
        let m = ws_recv_text(&mut stream)?;
        if !m.contains("auth_required") {
            bail!("[HA] auth_required attendu, reçu: {}", trunc(&m, 120));
        }

        let auth = format!(r#"{{"type":"auth","access_token":"{}"}}"#, self.token);
        ws_send_text(&mut stream, &auth)?;

        let m = ws_recv_text(&mut stream)?;
        if !m.contains("auth_ok") {
            netlog::error("[HA] Auth échouée");
            bail!("[HA] Auth échouée: {}", trunc(&m, 200));
        }
        info!("[HA] Authentifié");
        netlog::info("[HA] Authentifié");

        // ── Démarrer le pipeline assist ───────────────────────────────────────
        // Commande JSON construite dynamiquement (langue + conversation_id optionnel)
        let pipeline_cmd = build_pipeline_cmd(
            &self.language,
            self.conversation_id.as_ref().map(|s| s.as_str()),
        );
        ws_send_text(&mut stream, &pipeline_cmd)?;

        // Attendre run-start → stt_binary_handler_id
        let handler_id = wait_run_start(&mut stream)?;
        info!("[HA] Pipeline démarré, handler_id={}", handler_id);
        netlog::info(&format!("[HA] Pipeline start handler_id={}", handler_id));

        // ── Streaming audio ───────────────────────────────────────────────────
        let mut offset = 0usize;
        while offset < pcm_mono.len() {
            let end = (offset + AUDIO_CHUNK).min(pcm_mono.len());
            let mut frame_data = Vec::with_capacity(1 + end - offset);
            frame_data.push(handler_id);
            frame_data.extend_from_slice(&pcm_mono[offset..end]);
            ws_send_binary(&mut stream, &frame_data)?;
            offset = end;
        }
        // Signal fin de l'audio (frame handler_id seul)
        ws_send_binary(&mut stream, &[handler_id])?;
        info!("[HA] Audio streamé ({} bytes)", pcm_mono.len());
        netlog::info(&format!("[HA] Audio streamé bytes={}", pcm_mono.len()));

        // ── Collecter les événements pipeline ─────────────────────────────────
        let (transcript, answer, tts_url, conv_id) = collect_pipeline_events(&mut stream)?;
        info!("[HA] Transcript: \"{}\" | Réponse: \"{}\" | TTS: {:?}",
            transcript, answer, tts_url);
        netlog::info(&format!(
            "[HA] Pipeline result transcript='{}' answer='{}' tts_url={}",
            transcript,
            answer,
            tts_url.as_deref().unwrap_or("none")
        ));

        // Mémoriser le conversation_id pour les tours suivants
        if let Some(ref cid) = conv_id {
            let mut h: HString<64> = HString::new();
            let _ = h.push_str(&cid[..cid.len().min(63)]);
            self.conversation_id = Some(h);
            info!("[HA] conversation_id={}", cid);
            netlog::info(&format!("[HA] conversation_id={}", cid));
        }

        // ── Synthèse TTS via Wyoming Piper direct (PCM WAV, pas de MP3) ─────
        let tts_pcm = if !answer.is_empty() {
            match synthesize_wyoming(&self.host, &answer) {
                Ok(pcm) if !pcm.is_empty() => {
                    netlog::info(&format!("[TTS] Wyoming OK bytes16k={}", pcm.len()));
                    Some(pcm)
                }
                Ok(_) => {
                    warn!("[HA] TTS Wyoming vide");
                    netlog::warn("[HA] TTS Wyoming vide");
                    None
                }
                Err(e) => {
                    warn!("[HA] TTS Wyoming: {}", e);
                    netlog::warn(&format!("[HA] TTS Wyoming err: {}", e));
                    None
                }
            }
        } else {
            let _ = tts_url; // end_stage=intent → pas de tts-end
            None
        };

        // ── Fermeture WebSocket propre ────────────────────────────────────────
        let _ = ws_send_close(&mut stream); // best-effort

        let mut t = HString::<256>::new();
        let _ = t.push_str(&transcript[..transcript.len().min(255)]);
        let mut a = HString::<256>::new();
        let _ = a.push_str(&answer[..answer.len().min(255)]);

        Ok(HaResponse { transcript: t, answer: a, tts_pcm })
    }

    /// Exécuter le pipeline HA en streaming live: l'audio est fourni chunk par chunk.
    ///
    /// `next_chunk` doit retourner:
    /// - `Ok(Some(bytes_pcm_mono_16k))` pour envoyer un morceau audio,
    /// - `Ok(None)` pour signaler la fin d'audio.
    pub fn run_pipeline_streaming<F>(&mut self, mut next_chunk: F) -> Result<HaResponse>
    where
        F: FnMut() -> Result<Option<Vec<u8>>>,
    {
        if self.token.is_empty() {
            netlog::error("[HA] Token absent");
            bail!("[HA] Token absent — configurer HA_TOKEN ou NVS ha_cfg/token");
        }

        let addr = format!("{}:{}", self.host, self.port);
        info!("[HA] Connexion TCP à {}", addr);
        netlog::info(&format!("[HA] TCP connect {}", addr));

        let mut stream = TcpStream::connect(&addr)
            .with_context(|| format!("TCP connect {} échoué", addr))?;
        stream.set_read_timeout(Some(Duration::from_secs(30)))?;
        stream.set_write_timeout(Some(Duration::from_secs(10)))?;
        stream.set_nodelay(true)?;

        let hs = format!(
            "GET /api/websocket HTTP/1.1\r\n\
             Host: {}:{}\r\n\
             Upgrade: websocket\r\n\
             Connection: Upgrade\r\n\
             Sec-WebSocket-Key: {}\r\n\
             Sec-WebSocket-Version: 13\r\n\
             \r\n",
            self.host, self.port, WS_KEY
        );
        stream.write_all(hs.as_bytes())?;

        let mut resp_buf = Vec::with_capacity(512);
        let mut b = [0u8; 1];
        loop {
            stream.read_exact(&mut b)?;
            resp_buf.push(b[0]);
            if resp_buf.ends_with(b"\r\n\r\n") { break; }
            if resp_buf.len() > 4096 { bail!("[HA] Réponse HTTP trop longue"); }
        }
        let resp_str = String::from_utf8_lossy(&resp_buf);
        if !resp_str.contains("101") {
            netlog::error("[HA] WebSocket upgrade refusé");
            bail!("[HA] Upgrade WS refusé:\n{}", &resp_str[..resp_str.len().min(300)]);
        }

        let m = ws_recv_text(&mut stream)?;
        if !m.contains("auth_required") {
            bail!("[HA] auth_required attendu, reçu: {}", trunc(&m, 120));
        }

        let auth = format!(r#"{{"type":"auth","access_token":"{}"}}"#, self.token);
        ws_send_text(&mut stream, &auth)?;

        let m = ws_recv_text(&mut stream)?;
        if !m.contains("auth_ok") {
            netlog::error("[HA] Auth échouée");
            bail!("[HA] Auth échouée: {}", trunc(&m, 200));
        }

        let pipeline_cmd = build_pipeline_cmd(
            &self.language,
            self.conversation_id.as_ref().map(|s| s.as_str()),
        );
        ws_send_text(&mut stream, &pipeline_cmd)?;

        let handler_id = wait_run_start(&mut stream)?;
        info!("[HA] Pipeline streaming start, handler_id={}", handler_id);
        netlog::info(&format!("[HA] Pipeline streaming start handler_id={}", handler_id));

        let mut total_bytes = 0usize;
        let mut total_chunks = 0usize;
        loop {
            let maybe_chunk = next_chunk()?;
            let chunk = match maybe_chunk {
                Some(c) => c,
                None => break,
            };
            if chunk.is_empty() {
                continue;
            }

            let mut offset = 0usize;
            while offset < chunk.len() {
                let end = (offset + AUDIO_CHUNK).min(chunk.len());
                let mut frame_data = Vec::with_capacity(1 + end - offset);
                frame_data.push(handler_id);
                frame_data.extend_from_slice(&chunk[offset..end]);
                ws_send_binary(&mut stream, &frame_data)?;
                offset = end;
            }

            total_bytes += chunk.len();
            total_chunks += 1;
        }

        ws_send_binary(&mut stream, &[handler_id])?;
        info!("[HA] Audio streamé live ({} chunks, {} bytes)", total_chunks, total_bytes);
        netlog::info(&format!(
            "[HA] Audio streamé live chunks={} bytes={}",
            total_chunks,
            total_bytes
        ));

        let (transcript, answer, tts_url, conv_id) = collect_pipeline_events(&mut stream)?;

        if let Some(ref cid) = conv_id {
            let mut h: HString<64> = HString::new();
            let _ = h.push_str(&cid[..cid.len().min(63)]);
            self.conversation_id = Some(h);
        }

        let tts_pcm = if !answer.is_empty() {
            match synthesize_wyoming(&self.host, &answer) {
                Ok(pcm) if !pcm.is_empty() => Some(pcm),
                Ok(_) => None,
                Err(_) => None,
            }
        } else {
            let _ = tts_url;
            None
        };

        let _ = ws_send_close(&mut stream);

        let mut t = HString::<256>::new();
        let _ = t.push_str(&transcript[..transcript.len().min(255)]);
        let mut a = HString::<256>::new();
        let _ = a.push_str(&answer[..answer.len().min(255)]);

        Ok(HaResponse { transcript: t, answer: a, tts_pcm })
    }

    fn fetch_tts_wav(&self, url_path: &str) -> Result<Vec<u8>> {
        let full_url = format!("http://{}:{}{}", self.host, self.port, url_path);
        info!("[HA] GET TTS: {}", full_url);

        let cfg = HttpConfig {
            timeout: Some(Duration::from_secs(15)),
            ..Default::default()
        };
        let conn = EspHttpConnection::new(&cfg)?;
        let mut client = HttpClient::wrap(conn);
        let req = client.get(&full_url)?;
        let mut resp = req.submit()?;

        if resp.status() != 200 {
            bail!("[HA] TTS HTTP {}", resp.status());
        }

        let mut data = Vec::<u8>::new();
        let mut buf = [0u8; 4096];
        loop {
            match resp.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => data.extend_from_slice(&buf[..n]),
                Err(e) => bail!("[HA] Lecture TTS: {:?}", e),
            }
        }
        info!("[HA] TTS reçu: {} bytes", data.len());

        // Extraire PCM depuis WAV : chercher le chunk 'data'
        extract_wav_pcm(&data)
    }
}

// ─── Helpers WebSocket ────────────────────────────────────────────────────────

fn ws_encode_frame(opcode: u8, payload: &[u8]) -> Vec<u8> {
    let len = payload.len();
    let mut frame = Vec::with_capacity(len + 14);
    frame.push(0x80 | opcode);  // FIN + opcode

    // Longueur avec bit MASK=1
    if len < 126 {
        frame.push(0x80 | len as u8);
    } else if len < 65536 {
        frame.push(0x80 | 126u8);
        frame.extend_from_slice(&(len as u16).to_be_bytes());
    } else {
        frame.push(0x80 | 127u8);
        frame.extend_from_slice(&(len as u64).to_be_bytes());
    }

    frame.extend_from_slice(&WS_MASK);

    for (i, b) in payload.iter().enumerate() {
        frame.push(b ^ WS_MASK[i % 4]);
    }
    frame
}

fn ws_send_text(s: &mut TcpStream, text: &str) -> Result<()> {
    s.write_all(&ws_encode_frame(WS_OP_TEXT, text.as_bytes()))?;
    Ok(())
}

fn ws_send_binary(s: &mut TcpStream, data: &[u8]) -> Result<()> {
    s.write_all(&ws_encode_frame(WS_OP_BINARY, data))?;
    Ok(())
}

fn ws_send_close(s: &mut TcpStream) -> Result<()> {
    // Close frame avec code 1000 (normal closure)
    s.write_all(&ws_encode_frame(WS_OP_CLOSE, &[0x03, 0xE8]))?;
    Ok(())
}

fn ws_recv_text(s: &mut TcpStream) -> Result<String> {
    loop {
        let (opcode, payload) = ws_recv_frame(s)?;
        match opcode {
            WS_OP_TEXT   => return String::from_utf8(payload).map_err(|e| anyhow!("{}", e)),
            WS_OP_CLOSE  => bail!("[HA] WS fermé par serveur"),
            _            => {}  // ignorer ping, binary, etc.
        }
    }
}

fn ws_recv_frame(s: &mut TcpStream) -> Result<(u8, Vec<u8>)> {
    let mut hdr = [0u8; 2];
    s.read_exact(&mut hdr)?;

    let opcode   = hdr[0] & 0x0F;
    let masked   = (hdr[1] & 0x80) != 0;
    let len_byte = (hdr[1] & 0x7F) as usize;

    let payload_len = match len_byte {
        126 => {
            let mut b = [0u8; 2];
            s.read_exact(&mut b)?;
            u16::from_be_bytes(b) as usize
        }
        127 => {
            let mut b = [0u8; 8];
            s.read_exact(&mut b)?;
            u64::from_be_bytes(b) as usize
        }
        n => n,
    };

    let mask_key = if masked {
        let mut k = [0u8; 4]; s.read_exact(&mut k)?; k
    } else {
        [0u8; 4]
    };

    let mut payload = vec![0u8; payload_len];
    s.read_exact(&mut payload)?;

    if masked {
        for (i, b) in payload.iter_mut().enumerate() { *b ^= mask_key[i % 4]; }
    }

    Ok((opcode, payload))
}

// ─── Helpers protocole HA ─────────────────────────────────────────────────────

/// Construit la commande JSON assist_pipeline/run avec conversation_id optionnel.
/// end_stage=intent : HA fait STT+NLU mais pas TTS (on synthétise via Wyoming directement).
fn build_pipeline_cmd(language: &str, conversation_id: Option<&str>) -> String {
    let _ = language;
    if let Some(cid) = conversation_id {
        format!(
            r#"{{"id":1,"type":"assist_pipeline/run","start_stage":"stt","end_stage":"intent","input":{{"sample_rate":16000}},"conversation_id":"{}"}}"#,
            cid
        )
    } else {
        format!(
            r#"{{"id":1,"type":"assist_pipeline/run","start_stage":"stt","end_stage":"intent","input":{{"sample_rate":16000}}}}"#
        )
    }
}

/// Attendre l'événement run-start et extraire stt_binary_handler_id.
fn wait_run_start(s: &mut TcpStream) -> Result<u8> {
    for _ in 0..20 {
        let msg = ws_recv_text(s)?;
        if msg.contains("run-start") {
            let v: serde_json::Value = serde_json::from_str(&msg)
                .context("JSON run-start invalide")?;
            let id = v["event"]["data"]["runner_data"]["stt_binary_handler_id"]
                .as_u64()
                .context("stt_binary_handler_id absent")?;
            return Ok(id as u8);
        }
        if msg.contains("\"error\"") {
            bail!("[HA] Erreur pipeline: {}", trunc(&msg, 200));
        }
    }
    bail!("[HA] run-start non reçu après 20 messages");
}

/// Collecter les événements jusqu'à run-end.
/// Retourne (transcript, answer, tts_url, conversation_id).
fn collect_pipeline_events(s: &mut TcpStream) -> Result<(String, String, Option<String>, Option<String>)> {
    let mut transcript = String::new();
    let mut answer = String::new();
    let mut tts_url: Option<String> = None;
    let mut conversation_id: Option<String> = None;

    for _ in 0..60 {
        let msg = ws_recv_text(s)?;

        if msg.contains("stt-end") {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&msg) {
                if let Some(t) = v["event"]["data"]["stt_output"]["text"].as_str() {
                    transcript = t.to_string();
                    info!("[HA] STT: \"{}\"", transcript);
                }
            }
        } else if msg.contains("intent-end") {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&msg) {
                // Réponse vocale de HA (ex: "Allumage effectué")
                if let Some(sp) = v["event"]["data"]["intent_output"]["response"]["speech"]["plain"]["speech"].as_str() {
                    answer = sp.to_string();
                    info!("[HA] Intent réponse: \"{}\"", answer);
                }
                // conversation_id pour multi-tour
                if let Some(cid) = v["event"]["data"]["intent_output"]["conversation_id"].as_str() {
                    conversation_id = Some(cid.to_string());
                }
            }
        } else if msg.contains("tts-end") {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&msg) {
                if let Some(u) = v["event"]["data"]["tts_output"]["url"].as_str() {
                    tts_url = Some(u.to_string());
                }
            }
        } else if msg.contains("run-end") {
            info!("[HA] Pipeline run-end");
            break;
        } else if msg.contains("\"error_code\"") {
            warn!("[HA] Erreur pipeline: {}", trunc(&msg, 300));
            break;
        }
    }

    Ok((transcript, answer, tts_url, conversation_id))
}

// ─── Extraction PCM depuis WAV ────────────────────────────────────────────────

/// Extraire les samples PCM raw d'un fichier WAV RIFF.
/// Cherche le chunk 'data' (gère les WAV avec chunks INFO etc.).
fn extract_wav_pcm(wav: &[u8]) -> Result<Vec<u8>> {
    if wav.len() < 44 || &wav[0..4] != b"RIFF" || &wav[8..12] != b"WAVE" {
        bail!("[HA] WAV invalide (pas RIFF/WAVE), {} bytes", wav.len());
    }

    // Chercher le chunk 'data'
    let mut pos = 12usize;
    while pos + 8 <= wav.len() {
        let chunk_id = &wav[pos..pos + 4];
        let chunk_len = u32::from_le_bytes(wav[pos+4..pos+8].try_into().unwrap()) as usize;
        if chunk_id == b"data" {
            let start = pos + 8;
            let end = (start + chunk_len).min(wav.len());
            info!("[HA] WAV data chunk: {} samples PCM", (end - start) / 2);
            return Ok(wav[start..end].to_vec());
        }
        pos += 8 + chunk_len;
        if pos % 2 != 0 { pos += 1; }  // padding RIFF
    }

    bail!("[HA] Chunk 'data' introuvable dans WAV");
}

// ─── Wyoming TTS direct (PCM16LE sans passer par le proxy MP3 de HA) ──────────

const WYOMING_TTS_PORT: u16 = 10200;
const WYOMING_VOICE: &str = "fr_FR-siwis-medium";
const WYOMING_SRC_HZ: u32 = 22_050;

/// Synthétise `answer` via le serveur Wyoming Piper (TCP).
/// Retourne du PCM16LE mono rééchantillonné à 16 000 Hz.
fn synthesize_wyoming(host: &str, answer: &str) -> Result<Vec<u8>> {
    use std::io::{BufRead, BufReader};

    let addr = format!("{}:{}", host, WYOMING_TTS_PORT);
    let mut stream = TcpStream::connect(&addr)
        .with_context(|| format!("[TTS] Wyoming connect {}", addr))?;
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    stream.set_write_timeout(Some(Duration::from_secs(10)))?;

    // Construire les octets JSON du champ data
    let data_json = serde_json::json!({
        "text": answer,
        "voice": {
            "name": WYOMING_VOICE,
            "language": {"code": "fr_FR"}
        }
    });
    let data_bytes = serde_json::to_vec(&data_json)?;

    // Envoyer header Wyoming v1 puis data JSON (pas de newline dans data)
    let header = format!(
        "{{\"type\":\"synthesize\",\"data_length\":{},\"payload_length\":0}}\n",
        data_bytes.len()
    );
    stream.write_all(header.as_bytes())?;
    stream.write_all(&data_bytes)?;
    stream.flush()?;

    info!("[TTS] Wyoming synthesize '{}' envoyé à {}", &answer[..answer.len().min(40)], addr);

    // Lire les événements Wyoming
    let mut reader = BufReader::with_capacity(16_384, stream);
    let mut pcm_22050: Vec<u8> = Vec::new();

    for _ in 0..2000 {
        let mut header_line = String::new();
        let n = reader.read_line(&mut header_line)?;
        if n == 0 { break; }

        let h: serde_json::Value = serde_json::from_str(header_line.trim())
            .unwrap_or(serde_json::Value::Null);
        let event_type = h["type"].as_str().unwrap_or("").to_string();
        let data_len   = h["data_length"].as_u64().unwrap_or(0) as usize;
        let payload_len = h["payload_length"].as_u64().unwrap_or(0) as usize;

        // Lire data JSON (ignoré sauf pour debug)
        if data_len > 0 {
            let mut buf = vec![0u8; data_len];
            reader.read_exact(&mut buf)?;
        }

        // Lire payload binaire PCM
        if payload_len > 0 {
            let mut payload = vec![0u8; payload_len];
            reader.read_exact(&mut payload)?;
            if event_type == "audio-chunk" {
                pcm_22050.extend_from_slice(&payload);
            }
        }

        match event_type.as_str() {
            "audio-stop" | "error" => break,
            _ => {}
        }
    }

    if pcm_22050.is_empty() {
        bail!("[TTS] Wyoming: aucun audio reçu pour '{}'", &answer[..answer.len().min(40)]);
    }

    info!("[TTS] Wyoming: {} bytes PCM {}Hz reçus", pcm_22050.len(), WYOMING_SRC_HZ);
    netlog::info(&format!("[TTS] Wyoming bytes22k={}", pcm_22050.len()));

    // Rééchantillonner 22050 → 16000 Hz (interpolation linéaire)
    let pcm_16k = resample_linear_pcm16le(&pcm_22050, WYOMING_SRC_HZ, 16_000);
    info!("[TTS] Resampled: {} bytes PCM 16000Hz", pcm_16k.len());
    Ok(pcm_16k)
}

/// Rééchantillonneur linéaire PCM16LE mono.
fn resample_linear_pcm16le(pcm: &[u8], src_hz: u32, dst_hz: u32) -> Vec<u8> {
    if src_hz == dst_hz { return pcm.to_vec(); }
    let src_samples = pcm.len() / 2;
    if src_samples == 0 { return Vec::new(); }
    let dst_samples = (src_samples as u64 * dst_hz as u64 / src_hz as u64) as usize;
    let mut out = Vec::with_capacity(dst_samples * 2);

    for i in 0..dst_samples {
        let pos = i as f32 * src_hz as f32 / dst_hz as f32;
        let idx0 = pos as usize;
        let idx1 = (idx0 + 1).min(src_samples - 1);
        let frac = pos - idx0 as f32;

        let s0 = i16::from_le_bytes([pcm[idx0 * 2], pcm[idx0 * 2 + 1]]) as f32;
        let s1 = i16::from_le_bytes([pcm[idx1 * 2], pcm[idx1 * 2 + 1]]) as f32;
        let sample = (s0 + frac * (s1 - s0)) as i16;
        out.extend_from_slice(&sample.to_le_bytes());
    }
    out
}

fn trunc(s: &str, n: usize) -> &str {
    &s[..s.len().min(n)]
}
