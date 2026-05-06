use anyhow::Result;
use esp_idf_hal::{delay::FreeRtos, peripherals::Peripherals};
use esp_idf_svc::{eventloop::EspSystemEventLoop, nvs::EspDefaultNvsPartition};
use log::{error, info};

use crate::audio::{audio_init, es7210_reconfigure, MicCapture, MicCaptureAsync};
use crate::config::audio::{CAPTURE_MAX_MS, VAD_MIN_VOICE_MS, VAD_SILENCE_STOP_MS, VAD_VOICE_THRESHOLD};
use crate::config::media::BOOT_HELLO_WORLD_PCM;
use crate::server::ServerPing;
use crate::lcd::LcdDisplay;
use crate::netlog;
use crate::peripherals::{boot::maybe_factory_reset, capabilities::default_device_capabilities};
use crate::touch::CST816S;
use crate::ui;
use crate::wifi::WifiManager;

pub fn run() -> Result<()> {
    info!("=== EDGE booting (Phase 0) ===");
    info!("[P0-01] Console USB CDC active — logs visibles");

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs_partition = EspDefaultNvsPartition::take()?;

    info!("[P0-01] NVS initialisé");

    let mut lcd = LcdDisplay::new()?;
    info!("[P0-01] LCD ST77916 initialisé");

    CST816S::init();
    info!("[P0-01] CST816S touchscreen initialisé");

    match audio_init() {
        Ok(()) => info!("[P0-01] Codecs audio ES7210+ES8311 initialisés"),
        Err(e) => log::warn!("[P0-01] Init audio échouée (non bloquant): {}", e),
    }

    let caps = default_device_capabilities();
    info!("[P0-01] Capacités base: {}", caps.describe());

    info!("[P0-02] Démarrage WiFi...");
    let mut wifi = WifiManager::new(peripherals.modem, sysloop.clone(), nvs_partition.clone())?;

    maybe_factory_reset(&mut wifi)?;

    let wifi_result = if let Some((ssid, password)) = wifi.load_credentials() {
        ui::show_wifi_connecting(&mut lcd)?;
        wifi.connect(ssid.as_str(), password.as_str())
    } else {
        info!("[P0-02] Pas de credentials — provisioning tactile");
        let ssids_raw = wifi.scan()?;
        let ssid_refs: heapless::Vec<&str, 8> = ssids_raw.iter().map(|s| s.as_str()).collect();
        let (selected_ssid, entered_pass) = ui::run_wifi_provisioning(&mut lcd, ssid_refs.as_slice())?;
        wifi.save_credentials(selected_ssid.as_str(), entered_pass.as_str())?;
        ui::show_wifi_connecting(&mut lcd)?;
        wifi.connect(selected_ssid.as_str(), entered_pass.as_str())
    };

    match wifi_result {
        Ok(()) => {
            ui::show_wifi_connected(&mut lcd, wifi.ip())?;
            info!("[P0-02] WiFi connecté — IP: {}", wifi.ip());
            netlog::info(&format!("[P0-02] WiFi connecté ip={}", wifi.ip()));
        }
        Err(e) => {
            ui::show_wifi_failed(&mut lcd)?;
            error!("[P0-02] Échec connexion WiFi: {}", e);
            netlog::error(&format!("[P0-02] WiFi KO: {}", e));
            let _ = wifi.clear_credentials();
            FreeRtos::delay_ms(5000);
            unsafe { esp_idf_svc::sys::esp_restart() };
        }
    }

    info!("=== Phase 0 complète — boucle READY ===");

    info!("[P0-03] Initialisation serveur bridge...");
    let mut server = match ServerPing::new(nvs_partition.clone()) {
        Ok(s) => {
            info!("[P0-03] Bridge: {}:{}", s.host(), s.port());
            // Canal de log distant vers le même host que le bridge.
            if let Err(e) = netlog::init(s.host(), netlog::DEFAULT_LOG_PORT) {
                log::warn!("[NETLOG] init échouée: {}", e);
            } else if let Some(target) = netlog::target() {
                info!("[NETLOG] Envoi UDP activé vers {}", target);
                netlog::info(&format!("[NETLOG] démarré target={}", target));
            }
            netlog::info(&format!("[P0-03] Bridge {}:{}", s.host(), s.port()));
            s
        }
        Err(e) => {
            error!("[P0-03] Impossible de créer ServerPing: {}", e);
            return Err(e);
        }
    };
    // Vérification connectivité bridge au démarrage
    let server_ok = server.ping().ok;
    if !server_ok {
        ui::show_server_unreachable(&mut lcd)?;
        log::warn!("[P0-03] Bridge injoignable — vérifier {}:{}", server.host(), server.port());
        netlog::warn(&format!("[P0-03] Bridge injoignable {}:{}", server.host(), server.port()));
    }

    let mut mic_opt: Option<MicCaptureAsync> = match MicCapture::new(
        peripherals.i2s0,
        peripherals.pins.gpio48,
        peripherals.pins.gpio38,
        peripherals.pins.gpio39,
        peripherals.pins.gpio47,
        peripherals.pins.gpio2,
    ) {
        Ok(m) => {
            info!("[P1.2] MicCapture initialisé");
            // MCLK actif maintenant : ré-écrire les registres ES7210 qui
            // avaient été ignorés lors de l'init pre-MCLK dans audio_init().
            es7210_reconfigure();
            Some(MicCaptureAsync::new(m))
        }
        Err(e) => {
            log::warn!("[P1.2] MicCapture échoué: {} — capture désactivée", e);
            None
        }
    };

    if let Some(ref mic) = mic_opt {
        info!("[BOOT] Lecture phrase locale: hello world ({} bytes)", BOOT_HELLO_WORLD_PCM.len());
        match mic.play_pcm_mono_async(BOOT_HELLO_WORLD_PCM.to_vec()) {
            Ok(handle) => {
                if let Err(e) = handle.join().unwrap_or_else(|_| Err(anyhow::anyhow!("thread audio panic"))) {
                    log::warn!("[BOOT] Lecture hello world échouée: {}", e);
                } else {
                    info!("[BOOT] Lecture hello world terminée");
                }
            }
            Err(e) => log::warn!("[BOOT] Impossible de lancer hello world: {}", e),
        }
    }

    // Affichage initial READY — redessiné seulement après un cycle vocal
    ui::draw_ready_screen(&mut lcd, ui::DeviceState::Idle, wifi.is_connected(), server_ok)?;

    let mut touch_state: i64 = 0;
    loop {
        maybe_factory_reset(&mut wifi)?;

        // ── Sonde tactile (200 ms) — état persistant entre appels ───────────
        match ui::poll_touch_quick(&mut lcd, wifi.is_connected(), server_ok, 200, &mut touch_state)? {
            Some(ui::ReadyAction::StartListening) => {
                info!("[EDGE] Tap → cycle vocal");
                netlog::info("[EDGE] Tap detected");
                handle_ready_cycle(&mut lcd, &mut server, &mut mic_opt)?;
                // Réafficher l'écran READY après le cycle
                ui::draw_ready_screen(&mut lcd, ui::DeviceState::Idle, wifi.is_connected(), server_ok)?;
                continue;
            }
            Some(ui::ReadyAction::ConfigHa) => {
                let (host, port) = ui::run_ha_config(&mut lcd, server.host(), server.port())?;
                if let Err(e) = server.set_address(host.as_str(), port) {
                    error!("[EDGE] set_address: {}", e);
                } else {
                    info!("[EDGE] HA config mise à jour: {}:{}", host, port);
                }
                ui::draw_ready_screen(&mut lcd, ui::DeviceState::Idle, wifi.is_connected(), server_ok)?;
                continue;
            }
            None => {}
        }

        // Wake word désactivé temporairement — boucle tactile seule pour réactivité maximale
    }
}

fn handle_ready_cycle(
    lcd: &mut LcdDisplay,
    server: &mut ServerPing,
    mic_opt: &mut Option<MicCaptureAsync>,
) -> Result<()> {
    const CAPTURE_CHUNK_MS: u32 = 120;

    // ── 1. CAPTURE AUDIO (Listening) — micro d'abord, avant toute connexion ──
    info!("[EDGE] Capture audio...");
    ui::update_ready_state(lcd, ui::DeviceState::Listening)?;

    let pcm_full: Vec<u8> = match mic_opt {
        Some(mic) => {
            let t0_us = unsafe { esp_idf_svc::sys::esp_timer_get_time() } as u64;
            let mut voiced_ms: u32 = 0;
            let mut silence_ms: u32 = 0;
            let mut saw_voice = false;
            let mut buf: Vec<u8> = Vec::new();

            loop {
                let now_us = unsafe { esp_idf_svc::sys::esp_timer_get_time() } as u64;
                if now_us.saturating_sub(t0_us) > CAPTURE_MAX_MS as u64 * 1_000 {
                    netlog::info("[EDGE] capture stop reason=max_ms");
                    break;
                }

                let chunk = mic.capture_window_mono(CAPTURE_CHUNK_MS).unwrap_or_default();
                if chunk.is_empty() { continue; }

                let mut peak: i32 = 0;
                for s in chunk.chunks_exact(2) {
                    let v = i16::from_le_bytes([s[0], s[1]]) as i32;
                    if v.abs() > peak { peak = v.abs(); }
                }

                if peak >= VAD_VOICE_THRESHOLD {
                    saw_voice = true;
                    voiced_ms = voiced_ms.saturating_add(CAPTURE_CHUNK_MS);
                    silence_ms = 0;
                } else if saw_voice {
                    silence_ms = silence_ms.saturating_add(CAPTURE_CHUNK_MS);
                }

                buf.extend_from_slice(&chunk);

                if saw_voice && voiced_ms >= VAD_MIN_VOICE_MS && silence_ms >= VAD_SILENCE_STOP_MS {
                    netlog::info(&format!(
                        "[EDGE] capture stop reason=vad voiced_ms={} silence_ms={} bytes={}",
                        voiced_ms, silence_ms, buf.len()
                    ));
                    break;
                }
            }

            netlog::info(&format!("[EDGE] capture done bytes={} voiced_ms={}", buf.len(), voiced_ms));
            buf
        }
        None => {
            FreeRtos::delay_ms(3_000);
            Vec::new()
        }
    };

    // ── 2. PIPELINE BRIDGE (STT + HA Conversation + TTS) ───────────────────────
    info!("[EDGE] Bridge POST ({} bytes PCM)...", pcm_full.len());
    ui::update_ready_state(lcd, ui::DeviceState::Thinking)?;
    netlog::info(&format!("[EDGE] Bridge start bytes={}", pcm_full.len()));

    let response = match server.post_audio(&pcm_full) {
        Ok(r) => r,
        Err(e) => {
            log::warn!("[EDGE] Erreur bridge: {}", e);
            netlog::error(&format!("[EDGE] Erreur bridge: {}", e));
            ui::update_ready_state(lcd, ui::DeviceState::Error)?;
            FreeRtos::delay_ms(2_000);
            ui::update_ready_state(lcd, ui::DeviceState::Idle)?;
            return Ok(());
        }
    };

    info!("[EDGE] Bridge ok intent='{}' answer='{}' tts={}",
        response.intent.as_str(),
        response.answer.as_str(),
        response.audio_pcm.is_some()
    );
    netlog::info(&format!(
        "[EDGE] Bridge ok intent='{}' answer='{}' tts={}",
        response.intent.as_str(),
        response.answer.as_str(),
        response.audio_pcm.is_some()
    ));

    ui::show_answer(lcd, response.answer.as_str(), response.answer.as_str())?;

    // ── 3. LECTURE TTS (streaming par chunks) ───────────────────────────────────
    if response.audio_pcm.is_some() || response.has_more {
        ui::update_ready_state(lcd, ui::DeviceState::Speaking)?;
        let total = response.total_chunks;
        info!("[EDGE] TTS streaming : {} chunk(s) total", total);
        netlog::info(&format!("[EDGE] TTS streaming total_chunks={}", total));

        // Joue un chunk PCM et retourne Ok/Err
        let play_chunk = |mic_opt: &Option<crate::audio::MicCaptureAsync>, pcm: Vec<u8>| {
            if let Some(ref mic) = mic_opt {
                info!("[EDGE] Lecture chunk {} bytes", pcm.len());
                match mic.play_pcm_mono_async(pcm) {
                    Ok(handle) => match handle.join() {
                        Ok(Ok(())) => {}
                        Ok(Err(e)) => log::warn!("[EDGE] Erreur lecture chunk: {}", e),
                        Err(_)     => log::warn!("[EDGE] Thread TTS chunk panic"),
                    },
                    Err(e) => log::warn!("[EDGE] Impossible de jouer chunk: {}", e),
                }
            }
        };

        // Jouer le premier chunk (dans la réponse POST)
        if let Some(first_pcm) = response.audio_pcm {
            play_chunk(&mic_opt, first_pcm);
        }

        // Récupérer et jouer les chunks suivants si has_more
        if response.has_more {
            if let Some(ref stream_id) = response.stream_id {
                let mut chunk_idx: u32 = 1;
                loop {
                    netlog::info(&format!("[EDGE] Fetch stream chunk {}/{}", chunk_idx, total));
                    match server.get_stream_chunk(stream_id.as_str(), chunk_idx) {
                        Ok(sc) => {
                            if let Some(pcm) = sc.audio_pcm {
                                play_chunk(&mic_opt, pcm);
                            }
                            if !sc.has_more {
                                info!("[EDGE] Streaming terminé (chunk {})", chunk_idx);
                                netlog::info(&format!("[EDGE] Streaming done chunk={}", chunk_idx));
                                break;
                            }
                            chunk_idx += 1;
                        }
                        Err(e) => {
                            log::warn!("[EDGE] Erreur fetch chunk {}: {}", chunk_idx, e);
                            netlog::warn(&format!("[EDGE] Stream chunk {} err: {}", chunk_idx, e));
                            break;
                        }
                    }
                }
            }
        }

        netlog::info("[EDGE] TTS playback done");
    } else {
        FreeRtos::delay_ms(3_000);
    }

    ui::update_ready_state(lcd, ui::DeviceState::Idle)?;
    info!("[EDGE] Cycle terminé → Idle");
    netlog::info("[EDGE] Cycle terminé");
    Ok(())
}
