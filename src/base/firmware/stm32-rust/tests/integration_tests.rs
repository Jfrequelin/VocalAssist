#[cfg(test)]
mod integration_tests {
    use edge_base::{Config, Runtime, process_transcript, BaseResult};

    #[test]
    fn test_full_wake_word_flow() {
        let config = Config::new("nova");
        let mut runtime = Runtime::new(&config);

        // Test: wake word + command
        let decision = process_transcript(&mut runtime, &config, "nova quelle heure est il");
        assert!(decision.should_send);
        assert_eq!(decision.result, BaseResult::Accepted);
        assert!(decision.command.is_some());

        // Test: multiple words after wake word
        let decision = process_transcript(&mut runtime, &config, "nova volume a cinquante pourcent");
        assert!(decision.should_send);
        assert_eq!(decision.command, Some("volume a cinquante pourcent"));
    }

    #[test]
    fn test_rejection_filters() {
        let mut config = Config::new("nova");
        config.min_voice_chars = 12; // Require at least 12 alphanumeric chars
        let mut runtime = Runtime::new(&config);

        // VAD rejection
        let decision = process_transcript(&mut runtime, &config, "nova ...");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::VadRejectedLowVoice);

        // Missing command after wake word
        let decision = process_transcript(&mut runtime, &config, "nova help");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::VadRejectedLowVoice);

        // Missing wake word entirely
        let decision = process_transcript(&mut runtime, &config, "quel est l heure");
        assert!(!decision.should_send);
        assert_eq!(decision.result, BaseResult::WakeWordMissing);
    }
}
