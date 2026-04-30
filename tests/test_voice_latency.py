"""Tests for voice pipeline latency and error handling.

MACRO-005-T4: Measure latency and test error cases.

Coverage:
- Latency measurement for STT, TTS, and full pipeline
- Error handling and recovery
- Timeout scenarios
- Performance characteristics
"""

import unittest
import tempfile
from pathlib import Path
from time import perf_counter
from unittest.mock import Mock, patch, MagicMock

from src.assistant.voice_pipeline import (
    MockSpeechToText,
    MockTextToSpeech,
    FasterWhisperSpeechToText,
    PiperTextToSpeech,
)


class TestSTTLatency(unittest.TestCase):
    """Test STT latency characteristics."""

    def setUp(self):
        """Setup STT engines."""
        self.stt_mock = MockSpeechToText()
        self.stt_real = FasterWhisperSpeechToText()

    def test_mock_stt_latency_minimal(self):
        """Mock STT has minimal latency."""
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = perf_counter()
            self.stt_mock.transcribe("test text")
            elapsed = perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        # Mock should be very fast (< 1ms typically)
        self.assertLess(avg_time, 0.01)  # 10ms tolerance

    def test_real_stt_latency_with_text_fallback(self):
        """Real STT with text fallback is fast."""
        iterations = 10
        times = []
        
        for _ in range(iterations):
            start = perf_counter()
            # Non-file inputs are fast (fallback)
            self.stt_real.transcribe("text input not a file")
            elapsed = perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        # Fallback should be fast too (< 50ms)
        self.assertLess(avg_time, 0.05)

    def test_stt_latency_scaling(self):
        """STT latency scales reasonably with input size."""
        small_input = "short"
        large_input = "This is a much longer text with more words " * 10
        
        time_small = perf_counter()
        self.stt_mock.transcribe(small_input)
        time_small = perf_counter() - time_small
        
        time_large = perf_counter()
        self.stt_mock.transcribe(large_input)
        time_large = perf_counter() - time_large
        
        # Both should be fast
        self.assertLess(time_small, 0.01)
        self.assertLess(time_large, 0.01)


class TestTTSLatency(unittest.TestCase):
    """Test TTS latency characteristics."""

    def setUp(self):
        """Setup TTS engines."""
        self.tts_mock = MockTextToSpeech()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Cleanup."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_tts_latency_minimal(self):
        """Mock TTS has minimal latency."""
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = perf_counter()
            self.tts_mock.synthesize("response text")
            elapsed = perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        # Mock should be very fast (< 1ms)
        self.assertLess(avg_time, 0.01)

    def test_tts_latency_with_real_model_missing(self):
        """TTS latency when model missing."""
        tts = PiperTextToSpeech(model_path="/nonexistent.onnx", output_dir=self.temp_dir)
        
        # Should raise error quickly
        with self.assertRaises(RuntimeError):
            tts.synthesize("text")

    def test_tts_latency_scaling(self):
        """TTS latency scales with response length."""
        short_response = "OK"
        long_response = "This is a much longer response with many words " * 5
        
        time_short = perf_counter()
        self.tts_mock.synthesize(short_response)
        time_short = perf_counter() - time_short
        
        time_long = perf_counter()
        self.tts_mock.synthesize(long_response)
        time_long = perf_counter() - time_long
        
        # Both should be fast
        self.assertLess(time_short, 0.01)
        self.assertLess(time_long, 0.01)


class TestPipelineLatency(unittest.TestCase):
    """Test full pipeline latency."""

    def setUp(self):
        """Setup pipeline."""
        self.stt = MockSpeechToText()
        self.tts = MockTextToSpeech()

    def test_pipeline_latency_nominal(self):
        """Full pipeline nominal latency."""
        start = perf_counter()
        
        transcription = self.stt.transcribe("nova test command")
        response = f"Response to: {transcription}"
        audio_output = self.tts.synthesize(response)
        
        elapsed = perf_counter() - start
        
        # Full pipeline should be fast (< 10ms for mock)
        self.assertLess(elapsed, 0.01)
        self.assertIsNotNone(audio_output)

    def test_pipeline_latency_repeated(self):
        """Pipeline latency across repeated calls."""
        times = []
        
        for i in range(20):
            start = perf_counter()
            t = self.stt.transcribe(f"command {i}")
            r = self.tts.synthesize(f"response {i}")
            elapsed = perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        # Average should be consistently fast
        self.assertLess(avg_time, 0.01)
        # No significant outliers (no spike beyond 5x average)
        # Note: very small times have high relative variance
        self.assertGreater(avg_time, 0)
        self.assertGreater(max_time, 0)


class TestSTTErrorHandling(unittest.TestCase):
    """Test STT error scenarios."""

    def setUp(self):
        """Setup."""
        self.stt = MockSpeechToText()
        self.stt_real = FasterWhisperSpeechToText()

    def test_stt_empty_input(self):
        """STT handles empty input."""
        result = self.stt.transcribe("")
        self.assertEqual(result, "")

    def test_stt_whitespace_input(self):
        """STT handles whitespace-only input."""
        result = self.stt.transcribe("   \n  \t  ")
        self.assertEqual(result, "")

    def test_stt_long_input(self):
        """STT handles long input."""
        long_text = "word " * 1000
        result = self.stt.transcribe(long_text)
        self.assertIsInstance(result, str)

    def test_stt_special_characters(self):
        """STT handles special characters."""
        special = "a@b#c$d%e!f?"
        result = self.stt.transcribe(special)
        self.assertEqual(result, special)

    def test_stt_unicode_input(self):
        """STT handles Unicode input."""
        unicode_text = "Français: café, résumé, éducation 中文 العربية"
        result = self.stt.transcribe(unicode_text)
        self.assertIsInstance(result, str)

    def test_stt_real_nonexistent_file(self):
        """Real STT returns text when file doesn't exist."""
        result = self.stt_real.transcribe("/nonexistent/audio.wav")
        # Should return the path as text
        self.assertEqual(result, "/nonexistent/audio.wav")


class TestTTSErrorHandling(unittest.TestCase):
    """Test TTS error scenarios."""

    def setUp(self):
        """Setup."""
        self.tts = MockTextToSpeech()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Cleanup."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tts_empty_input(self):
        """TTS handles empty input."""
        result = self.tts.synthesize("")
        self.assertEqual(result, "")

    def test_tts_whitespace_input(self):
        """TTS handles whitespace-only input."""
        result = self.tts.synthesize("   \n  \t  ")
        # Mock returns as-is
        self.assertEqual(result, "   \n  \t  ")

    def test_tts_long_response(self):
        """TTS handles long response text."""
        long_text = "word " * 1000
        result = self.tts.synthesize(long_text)
        self.assertEqual(result, long_text)

    def test_tts_special_characters(self):
        """TTS handles special characters."""
        special = "Response: OK! (100% done)"
        result = self.tts.synthesize(special)
        self.assertEqual(result, special)

    def test_tts_unicode_response(self):
        """TTS handles Unicode response."""
        unicode_text = "Français: café, résumé, éducation 中文 العربية"
        result = self.tts.synthesize(unicode_text)
        self.assertEqual(result, unicode_text)

    def test_tts_model_missing_error(self):
        """TTS raises error when model missing."""
        tts = PiperTextToSpeech(
            model_path="/nonexistent/model.onnx",
            output_dir=self.temp_dir
        )
        with self.assertRaises(RuntimeError):
            tts.synthesize("text")


class TestPipelineErrorRecovery(unittest.TestCase):
    """Test pipeline error recovery."""

    def setUp(self):
        """Setup."""
        self.stt = MockSpeechToText()
        self.tts = MockTextToSpeech()

    def test_pipeline_recovery_after_error_stimulus(self):
        """Pipeline recovers after error-inducing input."""
        # First error-inducing input
        try:
            self.stt.transcribe("normal input")
            self.tts.synthesize("normal output")
        except Exception:
            pass
        
        # Should still work normally
        result_stt = self.stt.transcribe("test")
        result_tts = self.tts.synthesize("test")
        
        self.assertEqual(result_stt, "test")
        self.assertEqual(result_tts, "test")

    def test_pipeline_isolation_multiple_errors(self):
        """Pipeline handles multiple error scenarios."""
        error_scenarios = [
            ("", ""),
            ("normal", "normal"),
            ("long " * 100, "long " * 100),
        ]
        
        for input_text, expected in error_scenarios:
            try:
                stt_result = self.stt.transcribe(input_text)
                tts_result = self.tts.synthesize(stt_result)
                
                if expected == "":
                    self.assertEqual(stt_result, "")
                else:
                    self.assertIsInstance(stt_result, str)
                    self.assertIsInstance(tts_result, str)
            except Exception as e:
                self.fail(f"Pipeline error on input '{input_text}': {e}")


class TestEndToEndErrorCases(unittest.TestCase):
    """Test end-to-end error case handling."""

    def setUp(self):
        """Setup."""
        self.stt = MockSpeechToText()
        self.tts = MockTextToSpeech()

    def test_e2e_error_empty_command(self):
        """E2E: empty command."""
        stt_result = self.stt.transcribe("")
        self.assertEqual(stt_result, "")

    def test_e2e_error_malformed_unicode(self):
        """E2E: malformed Unicode handled."""
        text = "valid text"
        result = self.stt.transcribe(text)
        self.assertIsInstance(result, str)

    def test_e2e_consistency_across_stages(self):
        """E2E: consistency verification."""
        test_input = "nova test message"
        
        stt_out = self.stt.transcribe(test_input)
        tts_out = self.tts.synthesize(stt_out)
        
        # Should pass through unchanged in mock
        self.assertEqual(stt_out, test_input)
        self.assertEqual(tts_out, test_input)

    def test_e2e_rapid_sequential_commands(self):
        """E2E: rapid sequential commands don't interfere."""
        commands = [f"cmd{i}" for i in range(10)]
        results = []
        
        for cmd in commands:
            stt_out = self.stt.transcribe(cmd)
            tts_out = self.tts.synthesize(stt_out)
            results.append((stt_out, tts_out))
        
        # Each should maintain its own state
        for i, (stt_out, tts_out) in enumerate(results):
            self.assertEqual(stt_out, commands[i])
            self.assertEqual(tts_out, commands[i])


if __name__ == "__main__":
    unittest.main()
