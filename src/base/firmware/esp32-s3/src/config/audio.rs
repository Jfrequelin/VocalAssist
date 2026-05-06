#![allow(dead_code)]

pub const SAMPLE_RATE_HZ: u32 = 16_000;
pub const CAPTURE_MS: u32 = 3_000;
pub const PLAYBACK_TIMEOUT_TICKS: u32 = 5_000;
pub const READ_TIMEOUT_TICKS: u32 = 200;
pub const CAPTURE_MAX_MS: u64 = 4_500;
pub const PLAYBACK_GAIN: i32 = 1;
pub const PLAYBACK_TARGET_PEAK: i32 = 12_000;
pub const PLAYBACK_MAX_ADAPTIVE_GAIN: i32 = 6;
pub const TEST_TONE_HZ: u32 = 440;
pub const CAPTURE_FRAMES: usize = (SAMPLE_RATE_HZ as usize) * (CAPTURE_MS as usize / 1000);
pub const CAPTURE_BYTES: usize = CAPTURE_FRAMES * 4;

// ─── VAD (Voice Activity Detection) ──────────────────────────────────────────
/// Amplitude minimum (PCM16LE) pour considérer un chunk comme "voix".
pub const VAD_VOICE_THRESHOLD: i32 = 150;
/// Durée de voix minimale avant d'activer la détection de fin (ms).
pub const VAD_MIN_VOICE_MS: u32 = 180;
/// Durée de silence consécutif après la voix pour arrêter la capture (ms).
pub const VAD_SILENCE_STOP_MS: u32 = 450;
