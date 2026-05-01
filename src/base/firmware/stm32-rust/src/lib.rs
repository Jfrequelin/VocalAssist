//! Edge Base Runtime for STM32 in Rust
//!
//! Portable runtime for edge audio processing with wake word detection,
//! VAD filtering, and device state management.

#![cfg_attr(not(feature = "std"), no_std)]

use core::str;

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
}
