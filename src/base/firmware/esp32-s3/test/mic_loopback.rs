use anyhow::Result;
use esp_idf_hal::{delay::FreeRtos, peripherals::Peripherals};
use log::{info, warn};

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
use config::audio::CAPTURE_MS;

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("=== MIC LOOPBACK TEST boot ===");
    info!("[TEST] Firmware autonome: beep -> capture micro -> lecture locale");

    let peripherals = Peripherals::take()?;

    // Le LCD initialise le bus I2C0 attendu par audio_init() pour configurer ES7210/ES8311.
    let _lcd = lcd::LcdDisplay::new()?;
    info!("[TEST] LCD init OK (I2C audio disponible)");

    audio_init()?;

    let mut mic = MicCapture::new(
        peripherals.i2s0,
        peripherals.pins.gpio48,
        peripherals.pins.gpio38,
        peripherals.pins.gpio39,
        peripherals.pins.gpio47,
        peripherals.pins.gpio2,
    )?;

    // Reconfiguration ES7210 apres activation MCLK via I2S.
    es7210_reconfigure();

    info!("[TEST] Beep de demarrage...");
    mic.play_test_tone(250)?;
    FreeRtos::delay_ms(200);

    let mut cycle: u32 = 0;
    loop {
        cycle = cycle.saturating_add(1);
        info!("[TEST] Cycle {}: beep court", cycle);
        mic.play_test_tone(120)?;
        FreeRtos::delay_ms(120);

        info!("[TEST] Cycle {}: capture {} ms", cycle, CAPTURE_MS);
        let pcm_mono = mic.capture()?;

        let (peak, rms) = compute_peak_rms(&pcm_mono);
        info!(
            "[TEST] Cycle {}: capture bytes={} peak={} rms={}",
            cycle,
            pcm_mono.len(),
            peak,
            rms
        );

        if peak == 0 {
            warn!("[TEST] Cycle {}: silence total detecte (peak=0)", cycle);
        } else if peak < 200 {
            warn!("[TEST] Cycle {}: signal tres faible (peak={})", cycle, peak);
        }

        info!("[TEST] Cycle {}: lecture locale", cycle);
        mic.play_pcm_mono(&pcm_mono)?;

        FreeRtos::delay_ms(900);
    }
}

fn compute_peak_rms(pcm_mono: &[u8]) -> (i32, i32) {
    let frames = pcm_mono.len() / 2;
    if frames == 0 {
        return (0, 0);
    }

    let mut peak = 0i32;
    let mut rms_sum: i64 = 0;

    for sample in pcm_mono.chunks_exact(2) {
        let s = i16::from_le_bytes([sample[0], sample[1]]) as i32;
        let abs = s.abs();
        if abs > peak {
            peak = abs;
        }
        rms_sum += (s * s) as i64;
    }

    let rms = ((rms_sum / frames as i64) as f32).sqrt() as i32;
    (peak, rms)
}
