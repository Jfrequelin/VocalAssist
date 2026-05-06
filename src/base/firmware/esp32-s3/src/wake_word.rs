//! Détection de mot de déclenchement via Wyoming openWakeWord (TCP).
//!
//! Protocole Wyoming v1 :
//!   → audio-start  (description du format audio)
//!   → audio-chunk  (PCM16LE mono 16 kHz — fenêtre de 1 s)
//!   → audio-stop
//!   ← detection    (si détecté — contient `name` du modèle)
//!
//! La connexion TCP est ouverte à chaque fenêtre. Si le serveur n'est pas
//! joignable, `check_window` retourne `Ok(None)` sans paniquer.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::time::Duration;

use anyhow::Result;
use log::info;

use crate::netlog;

/// Port TCP du serveur wyoming-openwakeword.
pub const PORT: u16 = 10400;

/// Délai de lecture de la réponse après envoi de la fenêtre audio.
/// Timeout court pour ne pas bloquer la boucle READY (réactivité bouton).
const READ_TIMEOUT_MS: u64 = 120;

/// Envoie `pcm_mono` (PCM16LE 16 kHz mono) au serveur Wyoming openWakeWord.
///
/// Retourne `Some(nom_modele)` si un mot de déclenchement est détecté,
/// `None` si aucune détection ou si le serveur est injoignable.
pub fn check_window(host: &str, pcm_mono: &[u8]) -> Result<Option<String>> {
    if pcm_mono.is_empty() {
        return Ok(None);
    }

    let addr = format!("{}:{}", host, PORT);
    let mut stream = match TcpStream::connect(&addr) {
        Ok(s) => s,
        Err(_) => return Ok(None),
    };
    stream.set_write_timeout(Some(Duration::from_secs(5)))?;
    stream.set_read_timeout(Some(Duration::from_millis(READ_TIMEOUT_MS)))?;

    // ── Format audio (réutilisé dans audio-start et audio-chunk) ─────────────
    let fmt_json = serde_json::json!({
        "rate": 16_000u32,
        "width": 2u32,
        "channels": 1u32
    });
    let fmt_bytes = serde_json::to_vec(&fmt_json)?;

    // ── 1. audio-start ────────────────────────────────────────────────────────
    let header = format!(
        "{{\"type\":\"audio-start\",\"data_length\":{},\"payload_length\":0}}\n",
        fmt_bytes.len()
    );
    stream.write_all(header.as_bytes())?;
    stream.write_all(&fmt_bytes)?;

    // ── 2. audio-chunk (toute la fenêtre en un seul envoi) ────────────────────
    let chunk_header = format!(
        "{{\"type\":\"audio-chunk\",\"data_length\":{},\"payload_length\":{}}}\n",
        fmt_bytes.len(),
        pcm_mono.len()
    );
    stream.write_all(chunk_header.as_bytes())?;
    stream.write_all(&fmt_bytes)?;
    stream.write_all(pcm_mono)?;

    // ── 3. audio-stop ─────────────────────────────────────────────────────────
    stream.write_all(b"{\"type\":\"audio-stop\",\"data_length\":0,\"payload_length\":0}\n")?;
    stream.flush()?;

    // ── 4. Lire la réponse ────────────────────────────────────────────────────
    let mut reader = BufReader::with_capacity(2048, stream);
    let mut line = String::new();
    match reader.read_line(&mut line) {
        Ok(0) => return Ok(None),
        Err(e) => {
            log::debug!("[WW] lecture err: {:?} (probablement timeout)", e.kind());
            return Ok(None);
        }
        Ok(_) => {}
    }

    log::debug!("[WW] réponse: {}", line.trim());
    netlog::info(&format!("[WW] resp={}", line.trim()));

    let h: serde_json::Value = serde_json::from_str(line.trim())
        .unwrap_or(serde_json::Value::Null);

    if h["type"].as_str() != Some("detection") {
        return Ok(None);
    }

    let data_len = h["data_length"].as_u64().unwrap_or(0) as usize;
    let name = if data_len > 0 {
        let mut buf = vec![0u8; data_len];
        let _ = reader.read_exact(&mut buf);
        let d: serde_json::Value =
            serde_json::from_slice(&buf).unwrap_or(serde_json::Value::Null);
        d["name"].as_str().unwrap_or("unknown").to_string()
    } else {
        "unknown".to_string()
    };

    info!("[WW] Détection: '{}'", name);
    netlog::info(&format!("[WW] detected={}", name));
    Ok(Some(name))
}
