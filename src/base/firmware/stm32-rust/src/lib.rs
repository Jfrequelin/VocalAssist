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
}
