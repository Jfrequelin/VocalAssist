//! Edge Base Runtime for STM32 in Rust
//!
//! Portable runtime for edge audio processing with wake word detection,
//! VAD filtering, and device state management.

#![cfg_attr(not(feature = "std"), no_std)]

use core::str;
use heapless::Deque;
use heapless::String as HString;

/// Device runtime state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BaseState {
    Idle = 0,
    Listening = 1,
    Sending = 2,
    Speaking = 3,
    Muted = 4,
    Error = 5,
}

/// Processing result codes
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BaseResult {
    Accepted = 0,
    EmptyAudio = 1,
    VadRejectedLowVoice = 2,
    WakeWordMissing = 3,
    WakeWordWithoutCommand = 4,
    Muted = 5,
    InvalidArgument = 6,
}

/// Runtime configuration
#[derive(Debug, Clone)]
pub struct Config {
    pub wake_word: &'static str,
    pub min_voice_chars: u8,
    pub muted: bool,
}

impl Config {
    pub fn new(wake_word: &'static str) -> Self {
        Config {
            wake_word,
            min_voice_chars: 6,
            muted: false,
        }
    }

    pub fn validate(&self) -> Result<(), &'static str> {
        if self.wake_word.is_empty() {
            return Err("wake_word cannot be empty");
        }
        Ok(())
    }
}

/// Runtime state holder
#[derive(Debug, Clone)]
pub struct Runtime {
    pub state: BaseState,
    pub muted: bool,
    pub last_result: BaseResult,
}

impl Runtime {
    pub fn new(config: &Config) -> Self {
        Runtime {
            state: if config.muted {
                BaseState::Muted
            } else {
                BaseState::Idle
            },
            muted: config.muted,
            last_result: BaseResult::EmptyAudio,
        }
    }

    pub fn set_mute(&mut self, enabled: bool) {
        self.muted = enabled;
        self.state = if enabled {
            BaseState::Muted
        } else {
            BaseState::Idle
        };
    }
}

/// LED color abstraction for firmware drivers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LedColor {
    Green,
    Blue,
    Yellow,
    Orange,
    Red,
}

/// LED behavior specification.
///
/// `blink_hz_x10` uses 1 decimal precision to avoid floating point in no_std:
/// - 0   => fixed (no blink)
/// - 5   => 0.5 Hz
/// - 10  => 1.0 Hz
/// - 15  => 1.5 Hz
/// - 20  => 2.0 Hz
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LedPattern {
    pub color: LedColor,
    pub blink_hz_x10: u8,
}

/// Returns LED pattern associated with a runtime state.
pub fn led_pattern_for(state: BaseState) -> LedPattern {
    match state {
        BaseState::Idle => LedPattern {
            color: LedColor::Green,
            blink_hz_x10: 0,
        },
        BaseState::Listening => LedPattern {
            color: LedColor::Blue,
            blink_hz_x10: 10,
        },
        BaseState::Sending => LedPattern {
            color: LedColor::Yellow,
            blink_hz_x10: 20,
        },
        BaseState::Speaking => LedPattern {
            color: LedColor::Orange,
            blink_hz_x10: 15,
        },
        BaseState::Muted => LedPattern {
            color: LedColor::Red,
            blink_hz_x10: 0,
        },
        BaseState::Error => LedPattern {
            color: LedColor::Red,
            blink_hz_x10: 5,
        },
    }
}

/// Device state contract aligned with `assistant.edge_device.EdgeDeviceState`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EdgeDeviceState {
    pub muted: bool,
    pub led_state: BaseState,
    pub interaction_active: bool,
    pub last_event: &'static str,
}

impl Default for EdgeDeviceState {
    fn default() -> Self {
        Self {
            muted: false,
            led_state: BaseState::Idle,
            interaction_active: false,
            last_event: "init",
        }
    }
}

/// Device state controller for button/mute/interaction transitions.
pub struct EdgeDeviceController {
    state: EdgeDeviceState,
    events: Deque<&'static str, 16>,
}

/// Supported local system intents handled without network round-trip.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SystemIntent {
    StopMedia,
    ToggleMute,
    VolumeUp,
    VolumeDown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InformativeIntent {
    Time,
    Date,
    Weather,
    Temperature,
    SystemHelp,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ControlIntent {
    Light,
    Music,
    Reminder,
    Agenda,
    Restart,
    Exit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ControlSlots {
    pub room: Option<HString<32>>,
    pub artist_or_playlist: Option<HString<64>>,
    pub reminder_text: Option<HString<96>>,
}

impl Default for ControlSlots {
    fn default() -> Self {
        Self {
            room: None,
            artist_or_playlist: None,
            reminder_text: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ControlRoute {
    Local,
    RemoteAssistant,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TtsError {
    ModelNotLoaded,
    EmptyText,
    OutputOverflow,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PlaybackError {
    QueueFull,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PlaybackKind {
    Tts,
    Beep,
    ErrorTone,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlaybackItem {
    pub kind: PlaybackKind,
    pub samples_len: u16,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PcmAudio {
    pub samples: heapless::Vec<i16, 2048>,
    pub sample_rate_hz: u16,
    pub channels: u8,
    pub cached: bool,
    pub estimated_latency_ms: u16,
}

#[derive(Debug, Clone)]
pub struct PiperTtsEngine {
    pub model_loaded: bool,
    pub language: &'static str,
    pub cache_enabled: bool,
    cached_text: Option<HString<128>>,
    cached_audio: Option<PcmAudio>,
}

impl PiperTtsEngine {
    pub fn new(language: &'static str) -> Self {
        Self {
            model_loaded: false,
            language,
            cache_enabled: true,
            cached_text: None,
            cached_audio: None,
        }
    }

    pub fn load_model(&mut self) {
        self.model_loaded = true;
    }

    pub fn cache_memory_bytes(&self) -> usize {
        self.cached_audio
            .as_ref()
            .map(|a| a.samples.len() * core::mem::size_of::<i16>())
            .unwrap_or(0)
    }

    pub fn synthesize_to_pcm(&mut self, text: &str) -> Result<PcmAudio, TtsError> {
        if !self.model_loaded {
            return Err(TtsError::ModelNotLoaded);
        }

        let trimmed = text.trim();
        if trimmed.is_empty() {
            return Err(TtsError::EmptyText);
        }

        if self.cache_enabled {
            if let (Some(cached_text), Some(cached_audio)) = (&self.cached_text, &self.cached_audio) {
                if cached_text.as_str() == trimmed {
                    let mut out = cached_audio.clone();
                    out.cached = true;
                    return Ok(out);
                }
            }
        }

        let mut samples: heapless::Vec<i16, 2048> = heapless::Vec::new();
        for b in trimmed.bytes() {
            let amp = ((b as i16) - 64) * 8;
            for _ in 0..4 {
                if samples.push(amp).is_err() {
                    return Err(TtsError::OutputOverflow);
                }
            }
        }

        let est = (120u16).saturating_add((trimmed.len() as u16).saturating_mul(8)).min(480);
        let audio = PcmAudio {
            samples,
            sample_rate_hz: 16_000,
            channels: 1,
            cached: false,
            estimated_latency_ms: est,
        };

        if self.cache_enabled {
            let mut key: HString<128> = HString::new();
            let _ = key.push_str(trimmed);
            self.cached_text = Some(key);
            self.cached_audio = Some(audio.clone());
        }

        Ok(audio)
    }
}

#[derive(Debug, Clone)]
pub struct AudioPlayback {
    pub volume: u8,
    pub muted: bool,
    pub amplifier_enabled: bool,
    pub last_applied_gain: u8,
    queue: Deque<PlaybackItem, 16>,
}

impl Default for AudioPlayback {
    fn default() -> Self {
        Self {
            volume: 50,
            muted: false,
            amplifier_enabled: true,
            last_applied_gain: 50,
            queue: Deque::new(),
        }
    }
}

impl AudioPlayback {
    pub fn set_mute(&mut self, enabled: bool) {
        self.muted = enabled;
        self.amplifier_enabled = !enabled;
    }

    pub fn set_volume(&mut self, v: u8) {
        self.volume = v.min(100);
    }

    pub fn ramp_to_volume(&mut self, target: u8, step: u8) -> u8 {
        let target = target.min(100);
        let step = step.max(1);

        while self.last_applied_gain != target {
            if self.last_applied_gain < target {
                self.last_applied_gain = self.last_applied_gain.saturating_add(step).min(target);
            } else {
                self.last_applied_gain = self.last_applied_gain.saturating_sub(step).max(target);
            }
        }

        self.volume = target;
        self.last_applied_gain
    }

    pub fn queue_len(&self) -> usize {
        self.queue.len()
    }

    pub fn enqueue_tts(&mut self, audio: &PcmAudio) -> Result<(), PlaybackError> {
        self.queue
            .push_back(PlaybackItem {
                kind: PlaybackKind::Tts,
                samples_len: audio.samples.len() as u16,
            })
            .map_err(|_| PlaybackError::QueueFull)
    }

    pub fn enqueue_beep(&mut self) -> Result<(), PlaybackError> {
        self.queue
            .push_back(PlaybackItem {
                kind: PlaybackKind::Beep,
                samples_len: 160,
            })
            .map_err(|_| PlaybackError::QueueFull)
    }

    pub fn enqueue_error_tone(&mut self) -> Result<(), PlaybackError> {
        self.queue
            .push_back(PlaybackItem {
                kind: PlaybackKind::ErrorTone,
                samples_len: 220,
            })
            .map_err(|_| PlaybackError::QueueFull)
    }

    pub fn play_next(&mut self) -> Option<PlaybackItem> {
        if self.muted || !self.amplifier_enabled {
            return None;
        }
        self.queue.pop_front()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpeakError {
    Tts(TtsError),
    Playback(PlaybackError),
}

pub fn speak_response_local(
    controller: &mut EdgeDeviceController,
    tts: &mut PiperTtsEngine,
    playback: &mut AudioPlayback,
    text: &str,
) -> Result<(), SpeakError> {
    let audio = match tts.synthesize_to_pcm(text) {
        Ok(a) => a,
        Err(e) => {
            controller.mark_error();
            let _ = playback.enqueue_error_tone();
            return Err(SpeakError::Tts(e));
        }
    };

    controller.mark_speaking();
    playback
        .enqueue_tts(&audio)
        .map_err(SpeakError::Playback)?;
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ControlDecision {
    pub intent: Option<ControlIntent>,
    pub route: ControlRoute,
    pub should_send_remote: bool,
    pub response_tts: HString<160>,
    pub slots: ControlSlots,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InformativeSnapshot {
    pub hour: u8,
    pub minute: u8,
    pub day: u8,
    pub month: u8,
    pub year: u16,
    pub weather_summary: &'static str,
    pub temperature_c: i8,
}

impl Default for InformativeSnapshot {
    fn default() -> Self {
        Self {
            hour: 12,
            minute: 0,
            day: 1,
            month: 1,
            year: 2026,
            weather_summary: "ciel degage",
            temperature_c: 21,
        }
    }
}

/// Local audio control state (DAC/amplifier abstraction).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AudioControlState {
    pub volume: u8,
    pub muted: bool,
    pub amplifier_enabled: bool,
    pub media_active: bool,
    pub stop_signal: bool,
}

impl Default for AudioControlState {
    fn default() -> Self {
        Self {
            volume: 50,
            muted: false,
            amplifier_enabled: true,
            media_active: false,
            stop_signal: false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LocalSystemDecision {
    pub handled_locally: bool,
    pub intent: Option<SystemIntent>,
}

fn normalize_ascii_lower_no_diacritics(input: &str) -> HString<256> {
    let mut out: HString<256> = HString::new();
    for ch in input.chars() {
        let mapped = match ch {
            'À' | 'Á' | 'Â' | 'Ã' | 'Ä' | 'Å' | 'à' | 'á' | 'â' | 'ã' | 'ä' | 'å' => {
                'a'
            }
            'Ç' | 'ç' => 'c',
            'È' | 'É' | 'Ê' | 'Ë' | 'è' | 'é' | 'ê' | 'ë' => 'e',
            'Ì' | 'Í' | 'Î' | 'Ï' | 'ì' | 'í' | 'î' | 'ï' => 'i',
            'Ñ' | 'ñ' => 'n',
            'Ò' | 'Ó' | 'Ô' | 'Õ' | 'Ö' | 'ò' | 'ó' | 'ô' | 'õ' | 'ö' => 'o',
            'Ù' | 'Ú' | 'Û' | 'Ü' | 'ù' | 'ú' | 'û' | 'ü' => 'u',
            'Ý' | 'ý' | 'ÿ' => 'y',
            _ => ch.to_ascii_lowercase(),
        };
        if out.push(mapped).is_err() {
            break;
        }
    }
    out
}

/// Detect local system intents with priority: stop_media > mute > volume.
pub fn detect_system_intent(transcript: &str) -> Option<SystemIntent> {
    let normalized = normalize_ascii_lower_no_diacritics(transcript);
    let text = normalized.as_str().trim();

    if text.is_empty() {
        return None;
    }

    const STOP_PATTERNS: [&str; 6] = [
        "stop la musique",
        "arrete la musique",
        "arrete musique",
        "pause musique",
        "stop media",
        "coupe la musique",
    ];
    const MUTE_PATTERNS: [&str; 4] = ["mute", "coupe le son", "mode muet", "silence"];
    const VOLUME_UP_PATTERNS: [&str; 4] = ["augmente le son", "monte le son", "plus fort", "volume +"];
    const VOLUME_DOWN_PATTERNS: [&str; 4] =
        ["baisse le son", "moins fort", "diminue le son", "volume -"];

    if STOP_PATTERNS.iter().any(|p| text.contains(p)) {
        return Some(SystemIntent::StopMedia);
    }
    if MUTE_PATTERNS.iter().any(|p| text.contains(p)) {
        return Some(SystemIntent::ToggleMute);
    }
    if VOLUME_UP_PATTERNS.iter().any(|p| text.contains(p)) {
        return Some(SystemIntent::VolumeUp);
    }
    if VOLUME_DOWN_PATTERNS.iter().any(|p| text.contains(p)) {
        return Some(SystemIntent::VolumeDown);
    }

    None
}

/// Detect informative intents handled locally.
pub fn detect_informative_intent(transcript: &str) -> Option<InformativeIntent> {
    let normalized = normalize_ascii_lower_no_diacritics(transcript);
    let text = normalized.as_str();

    if text.contains("aide systeme") || text.contains("help system") || text.contains("help") {
        return Some(InformativeIntent::SystemHelp);
    }
    if text.contains("meteo") {
        return Some(InformativeIntent::Weather);
    }
    if text.contains("temperature") || text.contains("chauffage") || text.contains("thermostat") {
        return Some(InformativeIntent::Temperature);
    }
    if text.contains("heure") || text.contains("time") {
        return Some(InformativeIntent::Time);
    }
    if text.contains("date") || text.contains("jour") {
        return Some(InformativeIntent::Date);
    }
    None
}

pub fn detect_control_intent(transcript: &str) -> Option<ControlIntent> {
    let normalized = normalize_ascii_lower_no_diacritics(transcript);
    let text = normalized.as_str();

    // Priority: restart > exit > light/music/reminder/agenda
    if text.contains("restart")
        || text.contains("redemarre")
        || text.contains("redemarrer")
        || text.contains("redemarrage")
    {
        return Some(ControlIntent::Restart);
    }
    if text.contains("quitte") || text.contains("exit") {
        return Some(ControlIntent::Exit);
    }
    if text.contains("lumiere") || text.contains("lampe") {
        return Some(ControlIntent::Light);
    }
    if text.contains("musique") || text.contains("chanson") || text.contains("play") {
        return Some(ControlIntent::Music);
    }
    if text.contains("rappel") || text.contains("remember") || text.contains("memo") {
        return Some(ControlIntent::Reminder);
    }
    if text.contains("agenda") || text.contains("calendrier") || text.contains("planning") {
        return Some(ControlIntent::Agenda);
    }
    None
}

pub fn extract_control_slots(transcript: &str, intent: ControlIntent) -> ControlSlots {
    let normalized = normalize_ascii_lower_no_diacritics(transcript);
    let text = normalized.as_str();
    let mut slots = ControlSlots::default();

    match intent {
        ControlIntent::Light => {
            for room in ["salon", "chambre", "cuisine", "bureau"] {
                if text.contains(room) {
                    let mut s: HString<32> = HString::new();
                    let _ = s.push_str(room);
                    slots.room = Some(s);
                    break;
                }
            }
        }
        ControlIntent::Music => {
            if let Some(idx) = text.find("de ") {
                let tail = text[idx + 3..].trim();
                if !tail.is_empty() {
                    let mut s: HString<64> = HString::new();
                    let _ = s.push_str(tail);
                    slots.artist_or_playlist = Some(s);
                }
            }
        }
        ControlIntent::Reminder => {
            if let Some(idx) = text.find("rappel") {
                let tail = text[idx + "rappel".len()..].trim();
                if !tail.is_empty() {
                    let mut s: HString<96> = HString::new();
                    let _ = s.push_str(tail);
                    slots.reminder_text = Some(s);
                }
            }
        }
        _ => {}
    }

    slots
}

pub fn handle_control_intent(
    transcript: &str,
    controller: &mut EdgeDeviceController,
) -> ControlDecision {
    if let Some(intent) = detect_control_intent(transcript) {
        let slots = extract_control_slots(transcript, intent);
        let mut response: HString<160> = HString::new();

        match intent {
            ControlIntent::Restart => {
                controller.mark_error();
                let _ = response.push_str("Redemarrage...");
                return ControlDecision {
                    intent: Some(intent),
                    route: ControlRoute::Local,
                    should_send_remote: false,
                    response_tts: response,
                    slots,
                };
            }
            ControlIntent::Exit => {
                controller.finish_interaction();
                let _ = response.push_str("A bientot.");
                return ControlDecision {
                    intent: Some(intent),
                    route: ControlRoute::Local,
                    should_send_remote: false,
                    response_tts: response,
                    slots,
                };
            }
            ControlIntent::Light => {
                controller.mark_sending();
                if let Some(room) = &slots.room {
                    let _ = core::fmt::write(
                        &mut response,
                        format_args!("Lumiere du {} allumee.", room.as_str()),
                    );
                } else {
                    let _ = response.push_str("Lumiere allumee.");
                }
            }
            ControlIntent::Music => {
                controller.mark_sending();
                if let Some(artist) = &slots.artist_or_playlist {
                    let _ = core::fmt::write(
                        &mut response,
                        format_args!("Lecture de {}.", artist.as_str()),
                    );
                } else {
                    let _ = response.push_str("Lecture de votre musique.");
                }
            }
            ControlIntent::Reminder => {
                controller.mark_sending();
                let _ = response.push_str("C'est note.");
            }
            ControlIntent::Agenda => {
                controller.mark_sending();
                let _ = response.push_str("Vous avez 3 evenements aujourd'hui.");
            }
        }

        return ControlDecision {
            intent: Some(intent),
            route: ControlRoute::RemoteAssistant,
            should_send_remote: true,
            response_tts: response,
            slots,
        };
    }

    ControlDecision {
        intent: None,
        route: ControlRoute::Local,
        should_send_remote: false,
        response_tts: HString::new(),
        slots: ControlSlots::default(),
    }
}

/// Build a local textual response for informative intents.
pub fn build_informative_response(
    intent: InformativeIntent,
    snapshot: &InformativeSnapshot,
) -> HString<160> {
    let mut out: HString<160> = HString::new();
    match intent {
        InformativeIntent::Time => {
            let _ = core::fmt::write(
                &mut out,
                format_args!("Il est {:02}:{:02}.", snapshot.hour, snapshot.minute),
            );
        }
        InformativeIntent::Date => {
            let _ = core::fmt::write(
                &mut out,
                format_args!(
                    "Nous sommes le {:02}/{:02}/{:04}.",
                    snapshot.day, snapshot.month, snapshot.year
                ),
            );
        }
        InformativeIntent::Weather => {
            let _ = core::fmt::write(
                &mut out,
                format_args!(
                    "Simulation meteo: {}, {} degres.",
                    snapshot.weather_summary, snapshot.temperature_c
                ),
            );
        }
        InformativeIntent::Temperature => {
            let _ = core::fmt::write(
                &mut out,
                format_args!(
                    "Simulation climatisation: temperature ajustee a {} degres.",
                    snapshot.temperature_c
                ),
            );
        }
        InformativeIntent::SystemHelp => {
            let _ = out.push_str(
                "Aide systeme: commandes critiques disponibles -> mute, volume, stop media, aide.",
            );
        }
    }
    out
}

/// Apply a local system intent on device/audio state.
pub fn apply_system_intent(
    intent: SystemIntent,
    controller: &mut EdgeDeviceController,
    audio: &mut AudioControlState,
) -> LocalSystemDecision {
    match intent {
        SystemIntent::StopMedia => {
            audio.media_active = false;
            audio.stop_signal = true;
            controller.finish_interaction();
        }
        SystemIntent::ToggleMute => {
            let muted = controller.toggle_mute();
            audio.muted = muted;
            audio.amplifier_enabled = !muted;
            if muted {
                audio.media_active = false;
            }
        }
        SystemIntent::VolumeUp => {
            audio.volume = audio.volume.saturating_add(10).min(100);
            audio.stop_signal = false;
        }
        SystemIntent::VolumeDown => {
            audio.volume = audio.volume.saturating_sub(10);
            audio.stop_signal = false;
        }
    }

    LocalSystemDecision {
        handled_locally: true,
        intent: Some(intent),
    }
}

/// Detect then apply local system intent if any.
pub fn handle_system_intent(
    transcript: &str,
    controller: &mut EdgeDeviceController,
    audio: &mut AudioControlState,
) -> LocalSystemDecision {
    if let Some(intent) = detect_system_intent(transcript) {
        apply_system_intent(intent, controller, audio)
    } else {
        LocalSystemDecision {
            handled_locally: false,
            intent: None,
        }
    }
}

impl EdgeDeviceController {
    pub fn new() -> Self {
        let mut controller = Self {
            state: EdgeDeviceState::default(),
            events: Deque::new(),
        };
        controller.log_event("init");
        controller
    }

    fn log_event(&mut self, event: &'static str) {
        if self.events.push_back(event).is_err() {
            let _ = self.events.pop_front();
            let _ = self.events.push_back(event);
        }
        self.state.last_event = event;
    }

    pub fn state(&self) -> &EdgeDeviceState {
        &self.state
    }

    pub fn led_pattern(&self) -> LedPattern {
        led_pattern_for(self.state.led_state)
    }

    pub fn events_len(&self) -> usize {
        self.events.len()
    }

    pub fn set_mute(&mut self, enabled: bool) {
        self.state.muted = enabled;
        if enabled {
            self.state.led_state = BaseState::Muted;
            self.log_event("mute_on");
        } else {
            if !self.state.interaction_active {
                self.state.led_state = BaseState::Idle;
            }
            self.log_event("mute_off");
        }
    }

    pub fn toggle_mute(&mut self) -> bool {
        self.set_mute(!self.state.muted);
        self.state.muted
    }

    pub fn start_interaction(&mut self) {
        self.state.interaction_active = true;
        self.state.led_state = BaseState::Listening;
        self.log_event("interaction_started");
    }

    pub fn mark_sending(&mut self) {
        self.state.led_state = BaseState::Sending;
        self.log_event("audio_sending");
    }

    pub fn mark_speaking(&mut self) {
        self.state.led_state = if self.state.muted {
            BaseState::Muted
        } else {
            BaseState::Speaking
        };
        self.log_event("response_speaking");
    }

    pub fn mark_error(&mut self) {
        self.state.led_state = BaseState::Error;
        self.state.interaction_active = false;
        self.log_event("interaction_error");
    }

    pub fn finish_interaction(&mut self) {
        self.state.interaction_active = false;
        self.state.led_state = if self.state.muted {
            BaseState::Muted
        } else {
            BaseState::Idle
        };
        self.log_event("interaction_finished");
    }

    pub fn press_button(&mut self) {
        self.state.interaction_active = false;
        self.state.led_state = if self.state.muted {
            BaseState::Muted
        } else {
            BaseState::Idle
        };
        self.log_event("button_pressed");
    }
}

// ============================================================
// MACRO-012: Résilience — WiFi, HTTP, EEPROM, Monitoring
// ============================================================

/// WiFi connectivity status.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WifiStatus {
    Connected,
    Disconnected,
    /// Reconnection in progress; `attempt` counts from 1.
    Reconnecting { attempt: u8 },
    /// All retries exhausted — degraded mode.
    Failed,
}

/// Network state with retry logic (no heap, all stack-allocated).
#[derive(Debug, Clone)]
pub struct NetworkState {
    pub status: WifiStatus,
    pub max_retries: u8,
    /// Estimated retry interval in milliseconds (kept for host-side simulation).
    pub retry_interval_ms: u32,
    pub consecutive_failures: u8,
}

impl NetworkState {
    pub fn new(max_retries: u8) -> Self {
        Self {
            status: WifiStatus::Connected,
            max_retries,
            retry_interval_ms: 2_000,
            consecutive_failures: 0,
        }
    }

    pub fn is_available(&self) -> bool {
        self.status == WifiStatus::Connected
    }

    /// Called when a WiFi loss is detected.
    pub fn on_disconnect(&mut self) -> WifiStatus {
        self.status = WifiStatus::Reconnecting { attempt: 1 };
        self.consecutive_failures = self.consecutive_failures.saturating_add(1);
        self.status
    }

    /// Called on each reconnect tick.
    pub fn on_reconnect_attempt(&mut self) -> WifiStatus {
        match self.status {
            WifiStatus::Reconnecting { attempt } => {
                if attempt >= self.max_retries {
                    self.status = WifiStatus::Failed;
                } else {
                    self.status = WifiStatus::Reconnecting {
                        attempt: attempt + 1,
                    };
                }
            }
            _ => {}
        }
        self.status
    }

    /// Called when connection is re-established.
    pub fn on_connected(&mut self) {
        self.status = WifiStatus::Connected;
        self.consecutive_failures = 0;
    }
}

/// Offline pending command queue — buffers commands while WiFi is unavailable.
pub struct PendingCommandQueue {
    queue: Deque<HString<128>, 8>,
}

impl Default for PendingCommandQueue {
    fn default() -> Self {
        Self {
            queue: Deque::new(),
        }
    }
}

impl PendingCommandQueue {
    pub fn enqueue(&mut self, cmd: &str) -> Result<(), ()> {
        let mut s: HString<128> = HString::new();
        let _ = s.push_str(cmd);
        self.queue.push_back(s).map_err(|_| ())
    }

    pub fn dequeue(&mut self) -> Option<HString<128>> {
        self.queue.pop_front()
    }

    pub fn len(&self) -> usize {
        self.queue.len()
    }

    pub fn is_empty(&self) -> bool {
        self.queue.is_empty()
    }
}

/// HTTP response classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HttpOutcome {
    /// 2xx success.
    Ok,
    /// 4xx client error.
    ClientError { status: u16 },
    /// 5xx server error.
    ServerError { status: u16 },
    /// Network-level timeout.
    Timeout,
    /// Connection refused / network unavailable.
    Unreachable,
}

impl HttpOutcome {
    pub fn from_status(code: u16) -> Self {
        match code {
            200..=299 => HttpOutcome::Ok,
            400..=499 => HttpOutcome::ClientError { status: code },
            500..=599 => HttpOutcome::ServerError { status: code },
            _ => HttpOutcome::ClientError { status: code },
        }
    }

    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            HttpOutcome::Timeout
                | HttpOutcome::Unreachable
                | HttpOutcome::ServerError { .. }
        )
    }
}

// ─── EEPROM-backed persistent state (MACRO-012-T3) ─────────────────────────

/// State persisted across resets (simulates EEPROM pages on STM32).
///
/// `magic` must equal `PersistedState::MAGIC` for the struct to be
/// considered valid after a read from flash.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PersistedState {
    pub wifi_ssid: HString<64>,
    pub volume: u8,
    pub muted: bool,
    pub language: &'static str,
    /// Validation marker — must be `MAGIC` for a valid page.
    pub magic: u16,
}

impl Default for PersistedState {
    fn default() -> Self {
        let mut ssid: HString<64> = HString::new();
        let _ = ssid.push_str("HomeNetwork");
        Self {
            wifi_ssid: ssid,
            volume: 50,
            muted: false,
            language: "fr",
            magic: Self::MAGIC,
        }
    }
}

impl PersistedState {
    pub const MAGIC: u16 = 0xA55A;

    pub fn is_valid(&self) -> bool {
        self.magic == Self::MAGIC
    }

    /// Serialize to a fixed-size byte buffer (no std::io dependency).
    /// Layout: [magic_hi, magic_lo, volume, muted, ssid_len, ssid_bytes…]
    pub fn to_bytes(&self) -> heapless::Vec<u8, 128> {
        let mut buf: heapless::Vec<u8, 128> = heapless::Vec::new();
        let _ = buf.push((self.magic >> 8) as u8);
        let _ = buf.push((self.magic & 0xFF) as u8);
        let _ = buf.push(self.volume);
        let _ = buf.push(self.muted as u8);
        let ssid_bytes = self.wifi_ssid.as_bytes();
        let len = ssid_bytes.len().min(63) as u8;
        let _ = buf.push(len);
        for &b in &ssid_bytes[..len as usize] {
            if buf.push(b).is_err() {
                break;
            }
        }
        buf
    }

    /// Deserialize from raw bytes; returns `None` if magic is wrong or
    /// the buffer is truncated.
    pub fn from_bytes(buf: &[u8]) -> Option<Self> {
        if buf.len() < 5 {
            return None;
        }
        let magic = ((buf[0] as u16) << 8) | buf[1] as u16;
        if magic != Self::MAGIC {
            return None;
        }
        let volume = buf[2];
        let muted = buf[3] != 0;
        let ssid_len = buf[4] as usize;
        if buf.len() < 5 + ssid_len {
            return None;
        }
        let mut ssid: HString<64> = HString::new();
        if let Ok(s) = str::from_utf8(&buf[5..5 + ssid_len]) {
            let _ = ssid.push_str(s);
        }
        Some(Self {
            wifi_ssid: ssid,
            volume,
            muted,
            language: "fr",
            magic,
        })
    }
}

// ─── Diagnostic monitoring (MACRO-012-T4) ──────────────────────────────────

/// Error codes for diagnostic log entries.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ErrorCode {
    None = 0,
    WifiTimeout = 1,
    HttpClientError = 2,
    HttpServerError = 3,
    TtsFailure = 4,
    EepromCorrupt = 5,
    QueueOverflow = 6,
}

/// Ring-buffer diagnostic log — keeps last 16 error codes.
pub struct DiagnosticLog {
    errors: Deque<ErrorCode, 16>,
    pub error_count: u32,
    pub last_error: ErrorCode,
}

impl Default for DiagnosticLog {
    fn default() -> Self {
        Self {
            errors: Deque::new(),
            error_count: 0,
            last_error: ErrorCode::None,
        }
    }
}

impl DiagnosticLog {
    pub fn record(&mut self, code: ErrorCode) {
        self.error_count = self.error_count.saturating_add(1);
        self.last_error = code;
        if self.errors.push_back(code).is_err() {
            let _ = self.errors.pop_front();
            let _ = self.errors.push_back(code);
        }
    }

    pub fn len(&self) -> usize {
        self.errors.len()
    }

    pub fn is_empty(&self) -> bool {
        self.errors.is_empty()
    }

    pub fn last(&self) -> ErrorCode {
        self.last_error
    }
}

// ============================================================
// MACRO-013: Pipeline Complet — orchestrateur E2E
// ============================================================

/// Step reached by the pipeline during a single transcript turn.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PipelineStep {
    Idle,
    WakeWordDetected,
    /// A system intent (mute, volume…) was handled locally.
    LocalSystemHandled,
    /// An informative intent (time, date…) was handled locally with TTS.
    LocalInformativeHandled,
    /// A control intent was sent to remote assistant.
    RemoteDispatched,
    /// Command buffered — WiFi unavailable.
    QueuedOffline,
    /// TTS played successfully.
    TtsPlayed,
    /// Non-fatal error, device in Error state.
    Error,
}

/// Full edge pipeline — assembles all MACRO-006→012 components.
pub struct EdgePipeline {
    pub controller: EdgeDeviceController,
    pub tts: PiperTtsEngine,
    pub playback: AudioPlayback,
    pub audio_ctrl: AudioControlState,
    pub network: NetworkState,
    pub pending: PendingCommandQueue,
    pub diag: DiagnosticLog,
    pub snapshot: InformativeSnapshot,
    pub step: PipelineStep,
}

impl EdgePipeline {
    pub fn new() -> Self {
        let mut tts = PiperTtsEngine::new("fr");
        tts.load_model();
        Self {
            controller: EdgeDeviceController::new(),
            tts,
            playback: AudioPlayback::default(),
            audio_ctrl: AudioControlState::default(),
            network: NetworkState::new(3),
            pending: PendingCommandQueue::default(),
            diag: DiagnosticLog::default(),
            snapshot: InformativeSnapshot::default(),
            step: PipelineStep::Idle,
        }
    }

    /// Full-turn processing — from raw transcript to TTS/dispatch.
    ///
    /// Priority order:
    /// 1. Wake-word + VAD filter (`process_transcript`)
    /// 2. System intents (stop media, mute, volume) → local
    /// 3. Informative intents (time, date, weather…) → local TTS
    /// 4. Control intents (light, music…) → remote if online, else queue
    pub fn process(
        &mut self,
        runtime: &mut Runtime,
        config: &Config,
        transcript: &str,
    ) -> PipelineStep {
        let decision = process_transcript(runtime, config, transcript);

        if decision.result != BaseResult::Accepted {
            self.step = PipelineStep::Idle;
            return self.step;
        }

        self.step = PipelineStep::WakeWordDetected;
        let command = decision.command.unwrap_or("");

        // 1. System intents — handled entirely locally
        if let Some(sys_intent) = detect_system_intent(command) {
            apply_system_intent(sys_intent, &mut self.controller, &mut self.audio_ctrl);
            let response_text: &'static str = match sys_intent {
                SystemIntent::StopMedia => "Musique arretee.",
                SystemIntent::ToggleMute => {
                    if self.audio_ctrl.muted {
                        "Mode muet active."
                    } else {
                        "Son reactived."
                    }
                }
                SystemIntent::VolumeUp => "Volume augmente.",
                SystemIntent::VolumeDown => "Volume baisse.",
            };
            if !self.audio_ctrl.muted {
                let _ = speak_response_local(
                    &mut self.controller,
                    &mut self.tts,
                    &mut self.playback,
                    response_text,
                );
            }
            self.step = PipelineStep::LocalSystemHandled;
            return self.step;
        }

        // 2. Informative intents — answered locally with TTS
        if let Some(info_intent) = detect_informative_intent(command) {
            let response = build_informative_response(info_intent, &self.snapshot);
            match speak_response_local(
                &mut self.controller,
                &mut self.tts,
                &mut self.playback,
                response.as_str(),
            ) {
                Ok(()) => {
                    self.step = PipelineStep::LocalInformativeHandled;
                }
                Err(_) => {
                    self.diag.record(ErrorCode::TtsFailure);
                    self.step = PipelineStep::Error;
                }
            }
            return self.step;
        }

        // 3. Control intents — remote if online, else queue
        let ctrl_decision = handle_control_intent(command, &mut self.controller);
        if ctrl_decision.should_send_remote {
            if self.network.is_available() {
                // Simulate remote dispatch — play local TTS confirmation
                if !ctrl_decision.response_tts.is_empty() {
                    match speak_response_local(
                        &mut self.controller,
                        &mut self.tts,
                        &mut self.playback,
                        ctrl_decision.response_tts.as_str(),
                    ) {
                        Ok(()) => {}
                        Err(_) => {
                            self.diag.record(ErrorCode::TtsFailure);
                        }
                    }
                }
                self.step = PipelineStep::RemoteDispatched;
            } else {
                // Offline — buffer command
                if self.pending.enqueue(command).is_err() {
                    self.diag.record(ErrorCode::QueueOverflow);
                    self.step = PipelineStep::Error;
                } else {
                    self.step = PipelineStep::QueuedOffline;
                }
            }
            return self.step;
        }

        // Control handled locally (restart/exit)
        if ctrl_decision.intent.is_some() {
            self.step = PipelineStep::LocalSystemHandled;
            return self.step;
        }

        self.step = PipelineStep::Idle;
        self.step
    }

    /// Flush pending commands when WiFi reconnects.
    /// Returns the number of commands flushed.
    pub fn flush_pending(&mut self) -> usize {
        let mut count = 0;
        while let Some(_cmd) = self.pending.dequeue() {
            // In production this would re-dispatch via HTTP.
            count += 1;
        }
        count
    }
}

impl Default for EdgePipeline {
    fn default() -> Self {
        Self::new()
    }
}

/// Decision structure from transcript processing
#[derive(Debug, Clone)]
pub struct Decision<'a> {
    pub result: BaseResult,
    pub should_send: bool,
    pub command: Option<&'a str>,
}

/// Process a transcript and return activation decision
///
/// Applies sequential filtering:
/// 1. Mute check
/// 2. Empty audio check
/// 3. VAD minimal check (alphanumeric character count)
/// 4. Wake word detection
/// 5. Command presence check
pub fn process_transcript<'a>(
    runtime: &mut Runtime,
    config: &Config,
    transcript: &'a str,
) -> Decision<'a> {
    // Validate config
    if config.validate().is_err() {
        runtime.state = BaseState::Idle;
        runtime.last_result = BaseResult::InvalidArgument;
        return Decision {
            result: BaseResult::InvalidArgument,
            should_send: false,
            command: None,
        };
    }

    // Check mute
    if runtime.muted || config.muted {
        runtime.state = BaseState::Muted;
        runtime.last_result = BaseResult::Muted;
        return Decision {
            result: BaseResult::Muted,
            should_send: false,
            command: None,
        };
    }

    // Trim whitespace
    let trimmed = transcript.trim();

    // Check empty
    if trimmed.is_empty() {
        runtime.state = BaseState::Idle;
        runtime.last_result = BaseResult::EmptyAudio;
        return Decision {
            result: BaseResult::EmptyAudio,
            should_send: false,
            command: None,
        };
    }

    // VAD: count alphanumeric characters
    let alnum_count = trimmed.chars().filter(|c| c.is_alphanumeric()).count();
    if alnum_count < config.min_voice_chars as usize {
        runtime.state = BaseState::Idle;
        runtime.last_result = BaseResult::VadRejectedLowVoice;
        return Decision {
            result: BaseResult::VadRejectedLowVoice,
            should_send: false,
            command: None,
        };
    }

    // Check wake word (case-insensitive)
    let trimmed_lower = trimmed.to_lowercase();
    let wake_word_lower = config.wake_word.to_lowercase();

    if !trimmed_lower.starts_with(&wake_word_lower) {
        runtime.state = BaseState::Idle;
        runtime.last_result = BaseResult::WakeWordMissing;
        return Decision {
            result: BaseResult::WakeWordMissing,
            should_send: false,
            command: None,
        };
    }

    // Extract command
    let command_start = config.wake_word.len();
    let command = trimmed[command_start..].trim();

    if command.is_empty() {
        runtime.state = BaseState::Idle;
        runtime.last_result = BaseResult::WakeWordWithoutCommand;
        return Decision {
            result: BaseResult::WakeWordWithoutCommand,
            should_send: false,
            command: None,
        };
    }

    runtime.state = BaseState::Sending;
    runtime.last_result = BaseResult::Accepted;

    Decision {
        result: BaseResult::Accepted,
        should_send: true,
        command: Some(command),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mute_state() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        runtime.set_mute(true);
        assert_eq!(runtime.state, BaseState::Muted);
        assert!(runtime.muted);

        runtime.set_mute(false);
        assert_eq!(runtime.state, BaseState::Idle);
        assert!(!runtime.muted);
    }

    #[test]
    fn test_rejects_without_wake_word() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "quelle heure est il");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::WakeWordMissing);
    }

    #[test]
    fn test_accepts_command_after_wake_word() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "nova allume la lumiere");
        assert!(decision.should_send);
        assert_eq!(decision.result, BaseResult::Accepted);
        assert_eq!(decision.command, Some("allume la lumiere"));
    }

    #[test]
    fn test_rejects_low_voice() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "...");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::VadRejectedLowVoice);
    }

    #[test]
    fn test_rejects_when_muted() {
        let mut config = Config::new("nova");
        config.muted = true;
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "nova test");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::Muted);
    }

    #[test]
    fn test_case_insensitive_wake_word() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "NOVA allume la lumiere");
        assert!(decision.should_send);
        assert_eq!(decision.result, BaseResult::Accepted);
    }

    #[test]
    fn test_empty_audio() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        let decision = process_transcript(&mut runtime, &config, "");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::EmptyAudio);
    }

    #[test]
    fn test_device_controller_transitions() {
        let mut ctrl = EdgeDeviceController::new();

        assert_eq!(ctrl.state().led_state, BaseState::Idle);
        assert_eq!(ctrl.state().last_event, "init");

        ctrl.start_interaction();
        assert_eq!(ctrl.state().interaction_active, true);
        assert_eq!(ctrl.state().led_state, BaseState::Listening);

        ctrl.mark_sending();
        assert_eq!(ctrl.state().led_state, BaseState::Sending);

        ctrl.mark_speaking();
        assert_eq!(ctrl.state().led_state, BaseState::Speaking);

        ctrl.finish_interaction();
        assert_eq!(ctrl.state().interaction_active, false);
        assert_eq!(ctrl.state().led_state, BaseState::Idle);
        assert_eq!(ctrl.state().last_event, "interaction_finished");
    }

    #[test]
    fn test_mute_override_speaking() {
        let mut ctrl = EdgeDeviceController::new();
        ctrl.set_mute(true);
        ctrl.mark_speaking();

        assert_eq!(ctrl.state().muted, true);
        assert_eq!(ctrl.state().led_state, BaseState::Muted);
        assert_eq!(ctrl.state().last_event, "response_speaking");
    }

    #[test]
    fn test_press_button_resets_interaction() {
        let mut ctrl = EdgeDeviceController::new();
        ctrl.start_interaction();
        ctrl.press_button();

        assert_eq!(ctrl.state().interaction_active, false);
        assert_eq!(ctrl.state().led_state, BaseState::Idle);
        assert_eq!(ctrl.state().last_event, "button_pressed");
    }

    #[test]
    fn test_led_patterns_mapping() {
        assert_eq!(
            led_pattern_for(BaseState::Idle),
            LedPattern {
                color: LedColor::Green,
                blink_hz_x10: 0
            }
        );
        assert_eq!(
            led_pattern_for(BaseState::Listening),
            LedPattern {
                color: LedColor::Blue,
                blink_hz_x10: 10
            }
        );
        assert_eq!(
            led_pattern_for(BaseState::Sending),
            LedPattern {
                color: LedColor::Yellow,
                blink_hz_x10: 20
            }
        );
        assert_eq!(
            led_pattern_for(BaseState::Speaking),
            LedPattern {
                color: LedColor::Orange,
                blink_hz_x10: 15
            }
        );
        assert_eq!(
            led_pattern_for(BaseState::Muted),
            LedPattern {
                color: LedColor::Red,
                blink_hz_x10: 0
            }
        );
        assert_eq!(
            led_pattern_for(BaseState::Error),
            LedPattern {
                color: LedColor::Red,
                blink_hz_x10: 5
            }
        );
    }

    #[test]
    fn test_event_log_is_bounded() {
        let mut ctrl = EdgeDeviceController::new();
        for _ in 0..32 {
            ctrl.toggle_mute();
        }
        assert_eq!(ctrl.events_len(), 16);
    }

    #[test]
    fn test_detect_system_intent_with_diacritics() {
        assert_eq!(
            detect_system_intent("arrête la musique"),
            Some(SystemIntent::StopMedia)
        );
        assert_eq!(
            detect_system_intent("Silence s'il te plait"),
            Some(SystemIntent::ToggleMute)
        );
        assert_eq!(
            detect_system_intent("augmente le son"),
            Some(SystemIntent::VolumeUp)
        );
        assert_eq!(
            detect_system_intent("baisse le son"),
            Some(SystemIntent::VolumeDown)
        );
    }

    #[test]
    fn test_detect_system_intent_ambiguous_stop_is_ignored() {
        assert_eq!(detect_system_intent("stop"), None);
    }

    #[test]
    fn test_handle_system_intent_toggle_mute_syncs_led_and_audio() {
        let mut ctrl = EdgeDeviceController::new();
        let mut audio = AudioControlState::default();

        let decision = handle_system_intent("mode muet", &mut ctrl, &mut audio);
        assert!(decision.handled_locally);
        assert_eq!(decision.intent, Some(SystemIntent::ToggleMute));
        assert_eq!(ctrl.state().led_state, BaseState::Muted);
        assert!(!audio.amplifier_enabled);
        assert!(audio.muted);
    }

    #[test]
    fn test_handle_system_intent_volume_clamp() {
        let mut ctrl = EdgeDeviceController::new();
        let mut audio = AudioControlState {
            volume: 95,
            ..AudioControlState::default()
        };

        let _ = handle_system_intent("augmente le son", &mut ctrl, &mut audio);
        assert_eq!(audio.volume, 100);

        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        let _ = handle_system_intent("baisse le son", &mut ctrl, &mut audio);
        assert_eq!(audio.volume, 0);
    }

    #[test]
    fn test_handle_system_intent_stop_media() {
        let mut ctrl = EdgeDeviceController::new();
        let mut audio = AudioControlState {
            media_active: true,
            ..AudioControlState::default()
        };

        let decision = handle_system_intent("pause musique", &mut ctrl, &mut audio);
        assert!(decision.handled_locally);
        assert_eq!(decision.intent, Some(SystemIntent::StopMedia));
        assert!(!audio.media_active);
        assert!(audio.stop_signal);
        assert_eq!(ctrl.state().led_state, BaseState::Idle);
    }

    #[test]
    fn test_detect_informative_intent() {
        assert_eq!(
            detect_informative_intent("quelle heure est-il"),
            Some(InformativeIntent::Time)
        );
        assert_eq!(
            detect_informative_intent("donne la date"),
            Some(InformativeIntent::Date)
        );
        assert_eq!(
            detect_informative_intent("meteo aujourd'hui"),
            Some(InformativeIntent::Weather)
        );
        assert_eq!(
            detect_informative_intent("temperature du thermostat"),
            Some(InformativeIntent::Temperature)
        );
        assert_eq!(
            detect_informative_intent("aide système"),
            Some(InformativeIntent::SystemHelp)
        );
    }

    #[test]
    fn test_build_informative_responses() {
        let snapshot = InformativeSnapshot {
            hour: 14,
            minute: 35,
            day: 1,
            month: 5,
            year: 2026,
            weather_summary: "ciel degage",
            temperature_c: 22,
        };

        let time = build_informative_response(InformativeIntent::Time, &snapshot);
        assert_eq!(time.as_str(), "Il est 14:35.");

        let date = build_informative_response(InformativeIntent::Date, &snapshot);
        assert_eq!(date.as_str(), "Nous sommes le 01/05/2026.");

        let weather = build_informative_response(InformativeIntent::Weather, &snapshot);
        assert!(weather.as_str().contains("Simulation meteo"));

        let help = build_informative_response(InformativeIntent::SystemHelp, &snapshot);
        assert!(help.as_str().contains("mute, volume, stop media, aide"));
    }

    #[test]
    fn test_detect_control_intents() {
        assert_eq!(
            detect_control_intent("allume la lumiere du salon"),
            Some(ControlIntent::Light)
        );
        assert_eq!(
            detect_control_intent("mets de la musique"),
            Some(ControlIntent::Music)
        );
        assert_eq!(
            detect_control_intent("rappel demain appeler maman"),
            Some(ControlIntent::Reminder)
        );
        assert_eq!(
            detect_control_intent("montre mon agenda"),
            Some(ControlIntent::Agenda)
        );
        assert_eq!(
            detect_control_intent("redemarre le systeme"),
            Some(ControlIntent::Restart)
        );
        assert_eq!(detect_control_intent("exit"), Some(ControlIntent::Exit));
    }

    #[test]
    fn test_extract_control_slots_light_room() {
        let slots = extract_control_slots("allume la lumiere du salon", ControlIntent::Light);
        assert_eq!(slots.room.as_ref().map(|s| s.as_str()), Some("salon"));
    }

    #[test]
    fn test_handle_control_intent_routes_remote() {
        let mut ctrl = EdgeDeviceController::new();
        let decision = handle_control_intent("mets de la musique de daft punk", &mut ctrl);

        assert_eq!(decision.intent, Some(ControlIntent::Music));
        assert_eq!(decision.route, ControlRoute::RemoteAssistant);
        assert!(decision.should_send_remote);
        assert_eq!(ctrl.state().led_state, BaseState::Sending);
    }

    #[test]
    fn test_handle_control_restart_local_safeguard() {
        let mut ctrl = EdgeDeviceController::new();
        let decision = handle_control_intent("redemarre", &mut ctrl);

        assert_eq!(decision.intent, Some(ControlIntent::Restart));
        assert_eq!(decision.route, ControlRoute::Local);
        assert!(!decision.should_send_remote);
        assert_eq!(ctrl.state().led_state, BaseState::Error);
        assert_eq!(decision.response_tts.as_str(), "Redemarrage...");
    }

    #[test]
    fn test_handle_control_exit_cleanup() {
        let mut ctrl = EdgeDeviceController::new();
        ctrl.start_interaction();
        let decision = handle_control_intent("quitte", &mut ctrl);

        assert_eq!(decision.intent, Some(ControlIntent::Exit));
        assert_eq!(decision.route, ControlRoute::Local);
        assert!(!decision.should_send_remote);
        assert_eq!(ctrl.state().interaction_active, false);
        assert_eq!(ctrl.state().led_state, BaseState::Idle);
        assert_eq!(decision.response_tts.as_str(), "A bientot.");
    }

    #[test]
    fn test_tts_requires_model_loaded() {
        let mut tts = PiperTtsEngine::new("fr");
        let err = tts.synthesize_to_pcm("bonjour").err();
        assert_eq!(err, Some(TtsError::ModelNotLoaded));

        tts.load_model();
        let ok = tts.synthesize_to_pcm("bonjour");
        assert!(ok.is_ok());
    }

    #[test]
    fn test_tts_cache_and_latency_budget() {
        let mut tts = PiperTtsEngine::new("fr");
        tts.load_model();

        let a = tts
            .synthesize_to_pcm("Il est 14h30")
            .expect("tts should produce pcm");
        assert!(!a.cached);
        assert!(a.estimated_latency_ms < 500);

        let b = tts
            .synthesize_to_pcm("Il est 14h30")
            .expect("tts cache should work");
        assert!(b.cached);
        assert!(tts.cache_memory_bytes() < 1_000_000);
    }

    #[test]
    fn test_playback_queue_and_i2s_like_flow() {
        let mut tts = PiperTtsEngine::new("fr");
        tts.load_model();
        let audio = tts.synthesize_to_pcm("Lumiere du salon allumee").unwrap();

        let mut playback = AudioPlayback::default();
        assert_eq!(playback.queue_len(), 0);
        playback.enqueue_tts(&audio).unwrap();
        assert_eq!(playback.queue_len(), 1);

        let item = playback.play_next();
        assert!(item.is_some());
        assert_eq!(item.unwrap().kind, PlaybackKind::Tts);
        assert_eq!(playback.queue_len(), 0);
    }

    #[test]
    fn test_volume_ramping_and_mute() {
        let mut playback = AudioPlayback::default();
        let final_gain = playback.ramp_to_volume(90, 7);
        assert_eq!(final_gain, 90);
        assert_eq!(playback.volume, 90);

        playback.set_mute(true);
        assert!(playback.muted);
        assert!(!playback.amplifier_enabled);
        assert!(playback.play_next().is_none());
    }

    #[test]
    fn test_speak_response_marks_speaking_and_fallback_on_error() {
        let mut ctrl = EdgeDeviceController::new();
        let mut playback = AudioPlayback::default();

        // Error path: model not loaded
        let mut tts_err = PiperTtsEngine::new("fr");
        let err = speak_response_local(&mut ctrl, &mut tts_err, &mut playback, "bonjour");
        assert!(err.is_err());
        assert_eq!(ctrl.state().led_state, BaseState::Error);
        assert_eq!(playback.queue_len(), 1); // error tone enqueued

        // Success path
        let mut ctrl_ok = EdgeDeviceController::new();
        let mut playback_ok = AudioPlayback::default();
        let mut tts_ok = PiperTtsEngine::new("fr");
        tts_ok.load_model();
        let ok = speak_response_local(&mut ctrl_ok, &mut tts_ok, &mut playback_ok, "bonjour");
        assert!(ok.is_ok());
        assert_eq!(ctrl_ok.state().led_state, BaseState::Speaking);
        assert_eq!(playback_ok.queue_len(), 1);
    }

    // ─── MACRO-012: WiFi / Network ─────────────────────────────────────────

    #[test]
    fn test_wifi_reconnect_sequence() {
        let mut net = NetworkState::new(3);
        assert_eq!(net.status, WifiStatus::Connected);

        let s1 = net.on_disconnect();
        assert_eq!(s1, WifiStatus::Reconnecting { attempt: 1 });

        let s2 = net.on_reconnect_attempt();
        assert_eq!(s2, WifiStatus::Reconnecting { attempt: 2 });

        let s3 = net.on_reconnect_attempt();
        assert_eq!(s3, WifiStatus::Reconnecting { attempt: 3 });

        // max_retries == 3 → next attempt triggers Failed
        let s4 = net.on_reconnect_attempt();
        assert_eq!(s4, WifiStatus::Failed);

        net.on_connected();
        assert_eq!(net.status, WifiStatus::Connected);
        assert_eq!(net.consecutive_failures, 0);
    }

    #[test]
    fn test_wifi_consecutive_failures_count() {
        let mut net = NetworkState::new(1);
        net.on_disconnect();
        assert_eq!(net.consecutive_failures, 1);
        net.on_connected();
        net.on_disconnect();
        assert_eq!(net.consecutive_failures, 1); // reset on connect then re-incremented
    }

    // ─── MACRO-012: PendingCommandQueue ────────────────────────────────────

    #[test]
    fn test_pending_queue_enqueue_dequeue() {
        let mut q = PendingCommandQueue::default();
        assert!(q.is_empty());

        q.enqueue("allume la lumiere").unwrap();
        q.enqueue("mets de la musique").unwrap();
        assert_eq!(q.len(), 2);

        let first = q.dequeue().unwrap();
        assert_eq!(first.as_str(), "allume la lumiere");
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn test_pending_queue_overflow() {
        let mut q = PendingCommandQueue::default();
        for i in 0..8u8 {
            let cmd = if i % 2 == 0 { "cmd a" } else { "cmd b" };
            q.enqueue(cmd).unwrap();
        }
        // Queue is full (capacity = 8)
        let overflow = q.enqueue("one more");
        assert!(overflow.is_err());
    }

    // ─── MACRO-012: HttpOutcome ─────────────────────────────────────────────

    #[test]
    fn test_http_outcome_classification() {
        assert_eq!(HttpOutcome::from_status(200), HttpOutcome::Ok);
        assert_eq!(
            HttpOutcome::from_status(404),
            HttpOutcome::ClientError { status: 404 }
        );
        assert_eq!(
            HttpOutcome::from_status(503),
            HttpOutcome::ServerError { status: 503 }
        );

        assert!(!HttpOutcome::Ok.is_retryable());
        assert!(HttpOutcome::Timeout.is_retryable());
        assert!(HttpOutcome::Unreachable.is_retryable());
        assert!(HttpOutcome::ServerError { status: 500 }.is_retryable());
        assert!(!HttpOutcome::ClientError { status: 400 }.is_retryable());
    }

    // ─── MACRO-012: PersistedState / EEPROM ─────────────────────────────────

    #[test]
    fn test_persisted_state_roundtrip() {
        let state = PersistedState::default();
        assert!(state.is_valid());

        let bytes = state.to_bytes();
        let recovered = PersistedState::from_bytes(&bytes).expect("should deserialize");

        assert_eq!(recovered.volume, state.volume);
        assert_eq!(recovered.muted, state.muted);
        assert_eq!(recovered.wifi_ssid.as_str(), state.wifi_ssid.as_str());
        assert!(recovered.is_valid());
    }

    #[test]
    fn test_persisted_state_corrupt_magic() {
        let mut bytes = PersistedState::default().to_bytes();
        bytes[0] = 0xDE; // corrupt magic high byte
        bytes[1] = 0xAD;
        let result = PersistedState::from_bytes(&bytes);
        assert!(result.is_none());
    }

    #[test]
    fn test_persisted_state_truncated_buffer() {
        let result = PersistedState::from_bytes(&[0xA5, 0x5A, 50]); // too short
        assert!(result.is_none());
    }

    // ─── MACRO-012: DiagnosticLog ───────────────────────────────────────────

    #[test]
    fn test_diagnostic_log_records_errors() {
        let mut log = DiagnosticLog::default();
        assert!(log.is_empty());

        log.record(ErrorCode::WifiTimeout);
        log.record(ErrorCode::TtsFailure);
        assert_eq!(log.len(), 2);
        assert_eq!(log.error_count, 2);
        assert_eq!(log.last(), ErrorCode::TtsFailure);
    }

    #[test]
    fn test_diagnostic_log_is_bounded() {
        let mut log = DiagnosticLog::default();
        for _ in 0..20 {
            log.record(ErrorCode::HttpServerError);
        }
        assert_eq!(log.len(), 16); // ring buffer capacity
        assert_eq!(log.error_count, 20);
    }

    // ─── MACRO-013: EdgePipeline E2E ───────────────────────────────────────

    #[test]
    fn test_pipeline_local_informative_time() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();
        pipeline.snapshot.hour = 9;
        pipeline.snapshot.minute = 15;

        let step = pipeline.process(&mut runtime, &config, "nova quelle heure est-il");
        assert_eq!(step, PipelineStep::LocalInformativeHandled);
        assert_eq!(pipeline.playback.queue_len(), 1);
        assert_eq!(pipeline.controller.state().led_state, BaseState::Speaking);
    }

    #[test]
    fn test_pipeline_local_mute_toggle() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        let step = pipeline.process(&mut runtime, &config, "nova mode muet");
        assert_eq!(step, PipelineStep::LocalSystemHandled);
        assert!(pipeline.audio_ctrl.muted);
    }

    #[test]
    fn test_pipeline_remote_dispatch_online() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        assert!(pipeline.network.is_available());
        let step = pipeline.process(&mut runtime, &config, "nova allume la lumiere du salon");
        assert_eq!(step, PipelineStep::RemoteDispatched);
        assert_eq!(pipeline.controller.state().led_state, BaseState::Speaking);
    }

    #[test]
    fn test_pipeline_offline_queues_command() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        // Simulate WiFi loss
        pipeline.network.status = WifiStatus::Disconnected;
        let step = pipeline.process(&mut runtime, &config, "nova allume la lumiere");
        assert_eq!(step, PipelineStep::QueuedOffline);
        assert_eq!(pipeline.pending.len(), 1);

        // Simulate reconnect and flush
        pipeline.network.on_connected();
        let flushed = pipeline.flush_pending();
        assert_eq!(flushed, 1);
        assert!(pipeline.pending.is_empty());
    }

    #[test]
    fn test_pipeline_rejected_no_wake_word() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        let step = pipeline.process(&mut runtime, &config, "allume la lumiere");
        assert_eq!(step, PipelineStep::Idle);
    }

    #[test]
    fn test_pipeline_volume_stop_media() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();
        pipeline.audio_ctrl.media_active = true;

        let step = pipeline.process(&mut runtime, &config, "nova pause musique");
        assert_eq!(step, PipelineStep::LocalSystemHandled);
        assert!(!pipeline.audio_ctrl.media_active);
        assert!(pipeline.audio_ctrl.stop_signal);
    }

    // ─── MACRO-013-T4: Stress / Perf ───────────────────────────────────────

    #[test]
    fn test_pipeline_stress_1000_alternating_turns() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        let queries = [
            "nova quelle heure est-il",
            "nova allume la lumiere du salon",
            "nova augmente le son",
            "nova mets de la musique",
            "nova donne la date",
        ];

        for i in 0..1000usize {
            let q = queries[i % queries.len()];
            // Reset runtime state without changing config
            runtime.state = BaseState::Idle;
            runtime.muted = false;
            // Flush playback queue each turn to avoid overflow
            while pipeline.playback.play_next().is_some() {}
            pipeline.process(&mut runtime, &config, q);
        }

        // No panics, no memory corruption — we simply verify the pipeline
        // is still in a consistent state
        assert!(pipeline.diag.error_count < 100);
    }

    #[test]
    fn test_pipeline_memory_bound_no_heap_growth() {
        // All heapless structures have fixed capacity — verify key ones
        // (compile-time check via type system, runtime check via len vs capacity)
        let pipeline = EdgePipeline::new();

        // TTS cache: max 1 entry of PcmAudio<2048>
        assert_eq!(pipeline.tts.cache_memory_bytes(), 0); // nothing cached yet

        // Pending queue max capacity = 8
        let mut q = PendingCommandQueue::default();
        for _ in 0..8 {
            let _ = q.enqueue("test command padding to fill capacity");
        }
        assert_eq!(q.len(), 8);

        // Diagnostic ring: capped at 16
        let mut diag = DiagnosticLog::default();
        for _ in 0..50 {
            diag.record(ErrorCode::WifiTimeout);
        }
        assert_eq!(diag.len(), 16);
    }

    #[test]
    fn test_pipeline_error_recovery_after_tts_failure() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);
        let mut pipeline = EdgePipeline::new();

        // Force TTS into invalid state by unloading the model
        pipeline.tts.model_loaded = false;

        // Informative intent will fail TTS
        let step = pipeline.process(&mut runtime, &config, "nova quelle heure est-il");
        assert_eq!(step, PipelineStep::Error);
        assert_eq!(pipeline.diag.last(), ErrorCode::TtsFailure);
        assert_eq!(pipeline.diag.error_count, 1);

        // Reload model — next turn should recover
        pipeline.tts.load_model();
        runtime.state = BaseState::Idle;
        runtime.muted = false;
        while pipeline.playback.play_next().is_some() {}
        let step2 = pipeline.process(&mut runtime, &config, "nova quelle heure est-il");
        assert_eq!(step2, PipelineStep::LocalInformativeHandled);
    }
}
