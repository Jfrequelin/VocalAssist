from __future__ import annotations

import unittest

from src.assistant.voice_pipeline import (
    FasterWhisperSpeechToText,
    MockSpeechToText,
    MockTextToSpeech,
    PiperTextToSpeech,
)


class TestVoicePipeline(unittest.TestCase):
    def test_mock_stt(self) -> None:
        stt = MockSpeechToText()
        self.assertEqual(stt.transcribe("  bonjour  "), "bonjour")

    def test_mock_tts(self) -> None:
        tts = MockTextToSpeech()
        self.assertEqual(tts.synthesize("salut"), "salut")

    def test_real_stt_passthrough_for_non_file_input(self) -> None:
        stt = FasterWhisperSpeechToText(model_size="small", language="fr")
        self.assertEqual(stt.transcribe("texte deja transcrit"), "texte deja transcrit")

    def test_real_tts_raises_when_model_missing(self) -> None:
        tts = PiperTextToSpeech(model_path="/tmp/model-inexistant.onnx")
        with self.assertRaises(RuntimeError):
            tts.synthesize("Bonjour")


if __name__ == "__main__":
    unittest.main()
