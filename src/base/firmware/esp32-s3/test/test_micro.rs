//! test-micro — firmware de diagnostic microphone en continu
//!
//! Objectif : valider la capture ES7210 sans WiFi ni serveur.
//!
//! Séquence :
//!   boot → LCD (pour I2C) → audio_init → MicCapture → es7210_reconfigure
//!   → boucle :
//!       capture 500 ms stéréo brut
//!       log peak_L / peak_R / rms / hex-dump 16 premiers bytes
//!       log verdict (silence / faible / OK)
//!       pause 200 ms

use anyhow::Result;
use esp_idf_hal::{delay::FreeRtos, peripherals::Peripherals};
use log::{info, warn, error};

#[path = "../src/audio/mod.rs"]
mod audio;
#[path = "../src/buffers.rs"]
mod buffers;
#[path = "../src/config/mod.rs"]
mod config;
#[path = "../src/lcd/mod.rs"]
mod lcd;
#[path = "../src/touch/mod.rs"]
mod touch;

use audio::{audio_init, es7210_reconfigure, MicCapture};

// Durée de chaque fenêtre de capture (ms)
const CAPTURE_WINDOW_MS: u32 = 500;
// Seuil silence (i16 abs)
const THRESHOLD_SILENCE: i32 = 10;
// Seuil signal faible
const THRESHOLD_WEAK: i32 = 300;

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("=== TEST-MICRO boot ===");
    info!("[MIC] Capture stéréo brute {}ms en boucle — pas de WiFi, pas de lecture", CAPTURE_WINDOW_MS);

    let peripherals = Peripherals::take()?;

    // LCD initialise le bus I2C0 utilisé par les codecs audio.
    let _lcd = lcd::LcdDisplay::new()?;
    info!("[MIC] LCD init OK → I2C actif");

    match audio_init() {
        Ok(()) => info!("[MIC] Codecs ES7210+ES8311 initialisés"),
        Err(e) => {
            error!("[MIC] audio_init échoué: {} — arrêt", e);
            return Err(e);
        }
    }

    let mut mic = match MicCapture::new(
        peripherals.i2s0,
        peripherals.pins.gpio48, // BCK
        peripherals.pins.gpio38, // WS / LRCK
        peripherals.pins.gpio39, // DIN  (ES7210 → ESP32)
        peripherals.pins.gpio47, // DOUT (ESP32 → ES8311)
        peripherals.pins.gpio2,  // MCLK
    ) {
        Ok(m) => {
            info!("[MIC] MicCapture I2S OK");
            m
        }
        Err(e) => {
            error!("[MIC] MicCapture::new échoué: {} — arrêt", e);
            return Err(e);
        }
    };

    // ES7210 : ré-écrire les registres SDP/PGA maintenant que MCLK est actif.
    es7210_reconfigure();

    // Activer I2S une seule fois et ne JAMAIS le désactiver entre les captures.
    // L'ES7210 en mode slave perd sa synchro si MCLK s'interrompt.
    mic.start_continuous()?;
    info!("[MIC] I2S TX+RX actifs en continu (MCLK permanent)");

    info!("[MIC] === Début boucle capture continue ===");
    info!("[MIC] Parlez dans le micro — les stats s'affichent toutes les {}ms", CAPTURE_WINDOW_MS);

    let mut cycle: u32 = 0;
    let mut consecutive_silence: u32 = 0;

    loop {
        cycle = cycle.wrapping_add(1);

        // ── Capture brute stéréo (MCLK toujours actif) ─────────────────────
        let stereo = match mic.read_stereo_chunk(CAPTURE_WINDOW_MS) {
            Ok(v) => v,
            Err(e) => {
                error!("[MIC] #{}: capture erreur: {}", cycle, e);
                FreeRtos::delay_ms(500);
                continue;
            }
        };

        let frames = stereo.len() / 4;
        if frames == 0 {
            warn!("[MIC] #{}: 0 frames reçues (I2S timeout)", cycle);
            FreeRtos::delay_ms(200);
            continue;
        }

        // ── Analyse canal L et R séparément ───────────────────────────────
        let mut peak_l: i32 = 0;
        let mut peak_r: i32 = 0;
        let mut rms_l: i64 = 0;
        let mut rms_r: i64 = 0;

        for i in 0..frames {
            let l = i16::from_le_bytes([stereo[i * 4],     stereo[i * 4 + 1]]) as i32;
            let r = i16::from_le_bytes([stereo[i * 4 + 2], stereo[i * 4 + 3]]) as i32;
            if l.abs() > peak_l { peak_l = l.abs(); }
            if r.abs() > peak_r { peak_r = r.abs(); }
            rms_l += (l * l) as i64;
            rms_r += (r * r) as i64;
        }

        let rms_l = ((rms_l / frames as i64) as f32).sqrt() as i32;
        let rms_r = ((rms_r / frames as i64) as f32).sqrt() as i32;

        // ── Hex dump 16 premiers bytes stéréo (4 frames) ─────────────────
        let dump_len = stereo.len().min(16);
        let mut hex = String::new();
        for (i, b) in stereo[..dump_len].iter().enumerate() {
            if i % 4 == 0 && i > 0 { hex.push(' '); }
            let hi = b"0123456789ABCDEF"[(b >> 4) as usize] as char;
            let lo = b"0123456789ABCDEF"[(b & 0xF) as usize] as char;
            hex.push(hi);
            hex.push(lo);
        }

        info!(
            "[MIC] #{:04}: frames={} | L peak={:5} rms={:4} | R peak={:5} rms={:4} | raw[0..16]: {}",
            cycle, frames, peak_l, rms_l, peak_r, rms_r, hex
        );

        // ── Verdict ────────────────────────────────────────────────────────
        let max_peak = peak_l.max(peak_r);
        if max_peak <= THRESHOLD_SILENCE {
            consecutive_silence += 1;
            warn!("[MIC] #{:04}: SILENCE (peak={}) — consec={}", cycle, max_peak, consecutive_silence);

            // Après 5 silences consécutifs : redump registres ES7210 pour diagnostic
            if consecutive_silence % 5 == 0 {
                warn!("[MIC] #{:04}: {} silences consécutifs → re-reconfigure ES7210", cycle, consecutive_silence);
                es7210_reconfigure();
            }
        } else {
            consecutive_silence = 0;
            if max_peak < THRESHOLD_WEAK {
                warn!("[MIC] #{:04}: signal FAIBLE (peak={})", cycle, max_peak);
            } else {
                info!("[MIC] #{:04}: signal OK ✓ (peak={})", cycle, max_peak);
            }
        }

        FreeRtos::delay_ms(200);
    }
}
