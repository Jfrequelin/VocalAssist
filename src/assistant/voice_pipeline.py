from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Protocol

import shutil
import subprocess


class SpeechToTextEngine(Protocol):
    def transcribe(self, audio_payload: str) -> str: ...


class TextToSpeechEngine(Protocol):
    def synthesize(self, text: str) -> str: ...


@dataclass
class MockSpeechToText:
    """Simulation STT: la charge audio est deja du texte."""

    def transcribe(self, audio_payload: str) -> str:
        return audio_payload.strip()


@dataclass
class MockTextToSpeech:
    """Simulation TTS: renvoie simplement le texte de sortie."""

    def synthesize(self, text: str) -> str:
        return text


@dataclass
class FasterWhisperSpeechToText:
    """STT réel optionnel via faster-whisper.

    Si `audio_payload` n'est pas un chemin de fichier existant, la classe
    renvoie directement le texte reçu. Cela permet de garder un mode CLI simple.
    """

    model_size: str = "small"
    language: str = "fr"
    _model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper non installe") from exc

        self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_payload: str) -> str:
        payload = audio_payload.strip()
        if not payload:
            return ""

        audio_path = payload.removeprefix("file://")
        candidate = Path(audio_path)
        if not candidate.exists():
            return payload

        model = self._get_model()
        segments, _ = model.transcribe(str(candidate), language=self.language)
        transcribed = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return transcribed


@dataclass
class PiperTextToSpeech:
    """TTS local optionnel via binaire piper.

    Retourne le chemin du fichier audio généré sous forme de chaîne.
    """

    model_path: str
    output_dir: str = "doc/tickets/.tmp-audio"

    def synthesize(self, text: str) -> str:
        payload = text.strip()
        if not payload:
            return payload

        piper_bin = shutil.which("piper")
        if piper_bin is None:
            raise RuntimeError("binaire piper introuvable")

        model = Path(self.model_path)
        if not model.exists():
            raise RuntimeError(f"modele Piper introuvable: {model}")

        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"tts-{int(time() * 1000)}.wav"

        command = [
            piper_bin,
            "--model",
            str(model),
            "--output_file",
            str(output_file),
        ]
        subprocess.run(command, input=payload.encode("utf-8"), check=True)
        return str(output_file)
