from __future__ import annotations

import unittest

from src.assistant.voice_pipeline import (
    FasterWhisperSpeechToText,
    MockSpeechToText,
    MockTextToSpeech,
    PiperTextToSpeech,
    SpeechToTextEngine,
)


class TestVoicePipeline(unittest.TestCase):
    def test_mock_stt(self) -> None:
        stt = MockSpeechToText()
        self.assertEqual(stt.transcribe("  bonjour  "), "bonjour")

    def test_mock_tts(self) -> None:
        tts = MockTextToSpeech()
        self.assertEqual(tts.synthesize("salut"), "salut")

    # MACRO-005-T3: Pipeline integration tests

    def test_stt_tts_composition(self) -> None:
        """STT and TTS can be composed in pipeline."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        input_audio = "nova test command"
        transcription = stt.transcribe(input_audio)
        response_audio = tts.synthesize(transcription)

        self.assertEqual(transcription, input_audio)
        self.assertEqual(response_audio, input_audio)

    def test_pipeline_nominal_flow(self) -> None:
        """Full nominal pipeline flow."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        # Stage 1: Capture & transcribe
        captured_audio = "nova envoie un email"
        transcription = stt.transcribe(captured_audio)
        self.assertEqual(transcription, captured_audio)

        # Stage 2: Would process (orchestrator)
        # Stage 3: Synthesize response
        response_text = "Email envoyé avec succès"
        audio_output = tts.synthesize(response_text)
        self.assertEqual(audio_output, response_text)

    def test_pipeline_with_wake_word(self) -> None:
        """Pipeline handles commands with wake words."""
        stt = MockSpeechToText()

        input_with_wake_word = "nova quelle heure"
        transcription = stt.transcribe(input_with_wake_word)
        self.assertIn("quelle", transcription.lower())

    def test_pipeline_error_handling_empty_input(self) -> None:
        """Pipeline handles empty input."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        result_stt = stt.transcribe("")
        result_tts = tts.synthesize("")

        self.assertEqual(result_stt, "")
        self.assertEqual(result_tts, "")

    def test_pipeline_repeated_commands(self) -> None:
        """Pipeline handles repeated commands."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        commands = [
            "nova time",
            "nova weather",
            "nova reminder",
        ]

        for cmd in commands:
            transcription = stt.transcribe(cmd)
            self.assertIsInstance(transcription, str)
            response = tts.synthesize(f"Response to: {cmd}")
            self.assertIsInstance(response, str)

    def test_pipeline_with_special_characters(self) -> None:
        """Pipeline handles special characters."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        text = "nova: commande #1 (test)"
        result_stt = stt.transcribe(text)
        self.assertIsInstance(result_stt, str)

        response = "Response (OK) - 100% success!"
        result_tts = tts.synthesize(response)
        self.assertIsInstance(result_tts, str)

    def test_pipeline_fallback_mechanisms(self) -> None:
        """Pipeline falls back gracefully."""
        # Test with real STT (should fallback if file doesn't exist)
        real_stt = FasterWhisperSpeechToText()
        result = real_stt.transcribe("test text not a file")
        self.assertEqual(result, "test text not a file")

    def test_pipeline_isolation_between_calls(self) -> None:
        """Pipeline maintains independence between calls."""
        stt = MockSpeechToText()
        tts = MockTextToSpeech()

        t1 = stt.transcribe("text1")
        r1 = tts.synthesize("response1")

        t2 = stt.transcribe("text2")
        r2 = tts.synthesize("response2")

        # Results should be independent
        self.assertEqual(t1, "text1")
        self.assertEqual(r1, "response1")
        self.assertEqual(t2, "text2")
        self.assertEqual(r2, "response2")

    def test_pipeline_component_substitution(self) -> None:
        """Pipeline works with different implementations."""
        stt_engines: list[SpeechToTextEngine] = [
            MockSpeechToText(),
            FasterWhisperSpeechToText(),
        ]
        text = "test"

        # All STTs should return strings
        for stt in stt_engines:
            self.assertIsInstance(stt.transcribe(text), str)

        # Mock TTS works
        self.assertIsInstance(MockTextToSpeech().synthesize(text), str)

    def test_real_stt_passthrough_for_non_file_input(self) -> None:
        stt = FasterWhisperSpeechToText(model_size="small", language="fr")
        self.assertEqual(stt.transcribe("texte deja transcrit"), "texte deja transcrit")

    def test_real_tts_raises_when_model_missing(self) -> None:
        tts = PiperTextToSpeech(model_path="/tmp/model-inexistant.onnx")
        with self.assertRaises(RuntimeError):
            tts.synthesize("Bonjour")


if __name__ == "__main__":
    unittest.main()
