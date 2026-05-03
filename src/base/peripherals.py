from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from typing import Callable, Protocol

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - depends on system package availability
    tk = None


@dataclass(frozen=True)
class CapturedAudio:
    transcript: str
    audio_bytes: bytes


class MicrophoneDevice(Protocol):
    def capture(self) -> CapturedAudio | None: ...


class SpeakerDevice(Protocol):
    def play(self, text: str) -> None: ...


class ScreenDevice(Protocol):
    def show(self, *, state: str, message: str) -> None: ...


class StdinMicrophoneAdapter:
    """Desktop adapter: uses keyboard input to simulate microphone capture."""

    def __init__(self, *, prompt: str = "Audio brut(simule): ") -> None:
        self._prompt = prompt

    def capture(self) -> CapturedAudio | None:
        raw = input(self._prompt).strip()
        if raw.lower() in {"quit", "exit", "stop"}:
            return None
        if not raw:
            return CapturedAudio(transcript="", audio_bytes=b"")
        return CapturedAudio(transcript=raw, audio_bytes=raw.encode("utf-8"))


class LinuxArecordMicrophoneAdapter:
    """Linux adapter: records audio with arecord, then transcribes to text."""

    def __init__(
        self,
        *,
        transcribe: Callable[[str], str],
        prompt: str = "Micro(system) > appuyez Entree pour enregistrer ",
        duration_seconds: int = 3,
        sample_rate_hz: int = 16000,
        channels: int = 1,
        arecord_binary: str | None = None,
        replay_capture: bool = True,
        playback_binary: str | None = None,
        capture_device: str | None = None,
        playback_device: str | None = None,
        phrase_mode: bool = False,
        max_capture_seconds: float = 10.0,
        end_silence_seconds: float = 1.0,
        vad_start_threshold: float = 120.0,
        vad_silence_threshold: float = 80.0,
        vad_chunk_seconds: float = 0.2,
    ) -> None:
        self._transcribe = transcribe
        self._prompt = prompt
        self._duration_seconds: int = max(1, duration_seconds)
        self._sample_rate_hz: int = max(8000, sample_rate_hz)
        self._channels: int = max(1, channels)
        self._arecord_binary = arecord_binary or shutil.which("arecord") or ""
        if not self._arecord_binary:
            raise RuntimeError("arecord introuvable")
        self._replay_capture = replay_capture
        self._playback_binary = playback_binary or shutil.which("aplay") or shutil.which("pw-play") or shutil.which("paplay")
        self._capture_device = capture_device.strip() if isinstance(capture_device, str) else None
        self._playback_device = playback_device.strip() if isinstance(playback_device, str) else None
        self._phrase_mode = phrase_mode
        self._max_capture_seconds = max(2.0, max_capture_seconds)
        self._end_silence_seconds = max(0.3, end_silence_seconds)
        self._vad_start_threshold = max(1.0, vad_start_threshold)
        self._vad_silence_threshold = max(1.0, vad_silence_threshold)
        self._vad_chunk_seconds = min(max(0.05, vad_chunk_seconds), 1.0)

    def _build_arecord_command(self, *, wav_path: str, sample_rate_hz: int, channels: int) -> list[str]:
        command = [
            self._arecord_binary,
            "-q",
            "-d",
            str(self._duration_seconds),
            "-f",
            "S16_LE",
            "-c",
            str(channels),
            "-r",
            str(sample_rate_hz),
        ]
        if self._capture_device:
            command.extend(["-D", self._capture_device])
        command.append(wav_path)
        return command

    def _capture_wav(self, wav_path: str) -> bool:
        candidates: list[tuple[int, int]] = [(self._sample_rate_hz, self._channels)]
        fallback_pairs = [
            (self._sample_rate_hz, 2),
            (44100, self._channels),
            (44100, 2),
        ]
        for pair in fallback_pairs:
            if pair not in candidates:
                candidates.append(pair)

        first_failure = ""
        for sample_rate_hz, channels in candidates:
            command = self._build_arecord_command(
                wav_path=wav_path,
                sample_rate_hz=sample_rate_hz,
                channels=channels,
            )
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode == 0:
                if sample_rate_hz != self._sample_rate_hz or channels != self._channels:
                    print(
                        "Audio: fallback capture ALSA actif "
                        f"(sample_rate_hz={sample_rate_hz}, channels={channels})"
                    )
                self._sample_rate_hz = sample_rate_hz
                self._channels = channels
                return True

            stderr = (completed.stderr or "").strip()
            if not first_failure and stderr:
                first_failure = stderr

        if first_failure:
            print(f"Audio: echec capture arecord ({first_failure})")
        return False

    def _capture_phrase_mode_wav(self, wav_path: str) -> bool:
        candidates: list[tuple[int, int]] = [(self._sample_rate_hz, self._channels)]
        fallback_pairs = [
            (self._sample_rate_hz, 2),
            (44100, self._channels),
            (44100, 2),
        ]
        for pair in fallback_pairs:
            if pair not in candidates:
                candidates.append(pair)

        for sample_rate_hz, channels in candidates:
            raw_bytes = self._capture_raw_until_silence(
                sample_rate_hz=sample_rate_hz,
                channels=channels,
            )
            if raw_bytes is None:
                continue
            if not raw_bytes:
                return False

            with wave.open(wav_path, "wb") as wav_handle:
                wav_handle.setnchannels(channels)
                wav_handle.setsampwidth(2)
                wav_handle.setframerate(sample_rate_hz)
                wav_handle.writeframes(raw_bytes)

            if sample_rate_hz != self._sample_rate_hz or channels != self._channels:
                print(
                    "Audio: fallback capture ALSA actif "
                    f"(sample_rate_hz={sample_rate_hz}, channels={channels})"
                )
            self._sample_rate_hz = sample_rate_hz
            self._channels = channels
            return True

        print("Audio: echec capture arecord (mode phrase)")
        return False

    def _capture_raw_until_silence(self, *, sample_rate_hz: int, channels: int) -> bytes | None:
        command = [
            self._arecord_binary,
            "-q",
            "-f",
            "S16_LE",
            "-c",
            str(channels),
            "-r",
            str(sample_rate_hz),
            "-t",
            "raw",
        ]
        if self._capture_device:
            command.extend(["-D", self._capture_device])

        process = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        bytes_per_frame = 2 * max(1, channels)
        chunk_frames = max(1, int(sample_rate_hz * self._vad_chunk_seconds))
        chunk_size = chunk_frames * bytes_per_frame

        chunks: list[bytes] = []
        speech_started = False
        silence_acc = 0.0
        started_at = time.monotonic()

        try:
            if process.stdout is None:
                return None

            while True:
                elapsed = time.monotonic() - started_at
                if elapsed >= self._max_capture_seconds:
                    break

                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)

                avg_amp = self._avg_abs_amplitude_pcm16le(chunk)
                if avg_amp >= self._vad_start_threshold:
                    speech_started = True
                    silence_acc = 0.0
                    continue

                if speech_started and avg_amp <= self._vad_silence_threshold:
                    silence_acc += self._vad_chunk_seconds
                    if silence_acc >= self._end_silence_seconds:
                        break
                elif speech_started:
                    silence_acc = 0.0
        finally:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()

        if not speech_started:
            return b""
        return b"".join(chunks)

    def _avg_abs_amplitude_pcm16le(self, chunk: bytes) -> float:
        if len(chunk) < 2:
            return 0.0

        total_abs = 0
        sample_count = 0
        for idx in range(0, len(chunk) - 1, 2):
            sample = int.from_bytes(chunk[idx : idx + 2], byteorder="little", signed=True)
            total_abs += abs(sample)
            sample_count += 1

        if sample_count == 0:
            return 0.0
        return total_abs / sample_count

    def capture(self) -> CapturedAudio | None:
        try:
            raw = input(self._prompt).strip().lower()
        except EOFError:
            return None
        if raw in {"quit", "exit", "stop"}:
            return None

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(prefix="assistantvocal-", suffix=".wav", delete=False) as handle:
                temp_path = handle.name

            if self._phrase_mode:
                captured = self._capture_phrase_mode_wav(temp_path)
            else:
                captured = self._capture_wav(temp_path)

            if not captured:
                return CapturedAudio(transcript="", audio_bytes=b"")

            if self._replay_capture:
                self._replay_wav(temp_path)

            transcript = self._transcribe(temp_path).strip()
            if not transcript:
                return CapturedAudio(transcript="", audio_bytes=b"")

            # Le backend edge v2 supporte encore le proxy texte pour migration.
            return CapturedAudio(transcript=transcript, audio_bytes=transcript.encode("utf-8"))
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _replay_wav(self, wav_path: str) -> None:
        if not self._playback_binary:
            return
        if self._playback_binary.endswith("aplay"):
            command = [self._playback_binary, "-q"]
            if self._playback_device:
                command.extend(["-D", self._playback_device])
            command.append(wav_path)
            subprocess.run(command, check=False)
            return
        subprocess.run([self._playback_binary, wav_path], check=False)


class ConsoleSpeakerAdapter:
    """Desktop adapter: redirects spoken text to console output."""

    def __init__(self) -> None:
        self.played_messages: list[str] = []

    def play(self, text: str) -> None:
        self.played_messages.append(text)
        print(f"Speaker: {text}")


class LinuxSystemSpeakerAdapter:
    """Linux adapter: plays TTS with spd-say or espeak."""

    def __init__(self) -> None:
        self.played_messages: list[str] = []
        requested_engine = os.getenv("ASSISTANT_TTS_ENGINE", "auto").strip().lower()
        spd_say = shutil.which("spd-say") or ""
        espeak = shutil.which("espeak") or ""

        if requested_engine == "spd-say":
            self._binary = spd_say
        elif requested_engine == "espeak":
            self._binary = espeak
        else:
            self._binary = spd_say or espeak

        if not self._binary:
            raise RuntimeError("aucun binaire TTS systeme trouve (spd-say/espeak)")
        self._warmup_done = False
        self._warmup_enabled = os.getenv("ASSISTANT_TTS_WARMUP", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def play(self, text: str) -> None:
        self.played_messages.append(text)
        if not text.strip():
            return
        if self._binary.endswith("spd-say"):
            if self._warmup_enabled and not self._warmup_done:
                # Warm-up one-shot to reduce first-phoneme clipping on some ALSA/Pulse setups.
                subprocess.run([self._binary, "-w", " "], check=False)
                self._warmup_done = True
            subprocess.run([self._binary, "-w", text], check=False)
            return
        subprocess.run([self._binary, "-v", "fr", text], check=False)


class MockScreenAdapter:
    """Mock screen used by tests to assert UI-like state transitions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def show(self, *, state: str, message: str) -> None:
        self.events.append((state, message))


class ConsoleScreenAdapter:
    """Desktop adapter: shows simplified device UI state in console."""

    def show(self, *, state: str, message: str) -> None:
        print(f"Screen[{state}]: {message}")


class TkScreenAdapter:
    """Desktop adapter: lightweight Tk window to visualize edge state live."""

    _STATE_COLORS = {
        "idle": "#d9e2ec",
        "listening": "#ffe08a",
        "sending": "#9ad1ff",
        "speaking": "#c3f0ca",
        "muted": "#f7a8a8",
        "error": "#ff8b8b",
    }

    def __init__(self, *, title: str = "AssistantVocal Testbench") -> None:
        if tk is None:
            raise RuntimeError("tkinter indisponible")

        try:
            self._root = tk.Tk()
        except tk.TclError as exc:  # type: ignore[union-attr]
            raise RuntimeError("affichage graphique indisponible") from exc

        self._root.title(title)
        self._root.geometry("480x220")
        self._root.configure(bg="#101418")

        self._state_var = tk.StringVar(value="idle")
        self._message_var = tk.StringVar(value="Pret")

        frame = tk.Frame(self._root, bg="#101418", padx=18, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="AssistantVocal Base Linux",
            font=("Helvetica", 18, "bold"),
            fg="#f4f7fb",
            bg="#101418",
        ).pack(anchor="w")

        self._badge = tk.Label(
            frame,
            textvariable=self._state_var,
            font=("Helvetica", 14, "bold"),
            fg="#101418",
            bg=self._STATE_COLORS["idle"],
            padx=12,
            pady=6,
        )
        self._badge.pack(anchor="w", pady=(14, 12))

        tk.Label(
            frame,
            text="Dernier evenement",
            font=("Helvetica", 10),
            fg="#9fb3c8",
            bg="#101418",
        ).pack(anchor="w")

        self._message = tk.Label(
            frame,
            textvariable=self._message_var,
            justify="left",
            anchor="w",
            wraplength=420,
            font=("Helvetica", 12),
            fg="#f4f7fb",
            bg="#101418",
        )
        self._message.pack(fill="x", pady=(6, 0))
        self._pump()

    def show(self, *, state: str, message: str) -> None:
        normalized_state = state.strip().lower() or "idle"
        self._state_var.set(normalized_state)
        self._message_var.set(message.strip() or "-")
        self._badge.configure(bg=self._STATE_COLORS.get(normalized_state, "#d9e2ec"))
        self._pump()

    def _pump(self) -> None:
        self._root.update_idletasks()
        self._root.update()
