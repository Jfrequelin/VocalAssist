from __future__ import annotations

import unittest

from src.assistant.audio_capture import AudioCaptureConfig, CircularAudioBuffer


class TestCircularAudioBuffer(unittest.TestCase):
    def test_push_and_drain(self) -> None:
        buffer = CircularAudioBuffer(AudioCaptureConfig(chunk_size_bytes=8, max_buffer_chunks=3))
        buffer.push_chunk(b"ab")
        buffer.push_chunk(b"cd")

        merged = buffer.drain()
        self.assertEqual(merged, b"abcd")
        self.assertEqual(buffer.stats().buffered_chunks, 0)

    def test_overflow_drops_oldest(self) -> None:
        buffer = CircularAudioBuffer(AudioCaptureConfig(chunk_size_bytes=4, max_buffer_chunks=2))
        buffer.push_chunk(b"1111")
        buffer.push_chunk(b"2222")
        buffer.push_chunk(b"3333")

        stats = buffer.stats()
        self.assertEqual(stats.dropped_chunks, 1)
        self.assertEqual(buffer.drain(), b"22223333")

    def test_push_truncates_oversized_chunk(self) -> None:
        buffer = CircularAudioBuffer(AudioCaptureConfig(chunk_size_bytes=4, max_buffer_chunks=2))
        buffer.push_chunk(b"ABCDEFG")
        self.assertEqual(buffer.drain(), b"DEFG")

    def test_config_rejects_non_positive_chunk_size(self) -> None:
        with self.assertRaises(ValueError):
            AudioCaptureConfig(chunk_size_bytes=0)

    def test_config_rejects_non_positive_max_buffer_chunks(self) -> None:
        with self.assertRaises(ValueError):
            AudioCaptureConfig(max_buffer_chunks=0)


if __name__ == "__main__":
    unittest.main()
