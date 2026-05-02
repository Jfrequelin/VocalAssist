from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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
    ) -> None:
        self._transcribe = transcribe
        self._prompt = prompt
        self._duration_seconds = max(1, duration_seconds)
        self._sample_rate_hz = max(8000, sample_rate_hz)
        self._channels = max(1, channels)
        self._arecord_binary = arecord_binary or shutil.which("arecord") or ""
        if not self._arecord_binary:
            raise RuntimeError("arecord introuvable")

    def capture(self) -> CapturedAudio | None:
        raw = input(self._prompt).strip().lower()
        if raw in {"quit", "exit", "stop"}:
            return None

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(prefix="assistantvocal-", suffix=".wav", delete=False) as handle:
                temp_path = handle.name

            command = [
                self._arecord_binary,
                "-q",
                "-d",
                str(self._duration_seconds),
                "-f",
                "S16_LE",
                "-c",
                str(self._channels),
                "-r",
                str(self._sample_rate_hz),
                temp_path,
            ]
            completed = subprocess.run(command, check=False)
            if completed.returncode != 0:
                return CapturedAudio(transcript="", audio_bytes=b"")

            transcript = self._transcribe(temp_path).strip()
            if transcript.lower() in {"quit", "exit", "stop"}:
                return None
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
        self._binary = shutil.which("spd-say") or shutil.which("espeak") or ""
        if not self._binary:
            raise RuntimeError("aucun binaire TTS systeme trouve (spd-say/espeak)")

    def play(self, text: str) -> None:
        self.played_messages.append(text)
        if not text.strip():
            return
        if self._binary.endswith("spd-say"):
            subprocess.run([self._binary, text], check=False)
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
