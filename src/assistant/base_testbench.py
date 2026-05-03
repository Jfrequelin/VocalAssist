from __future__ import annotations

import json
import os
import platform
import shutil
from dataclasses import dataclass
from time import perf_counter
from time import sleep
from time import time
from typing import Any

from src.base import (
    AssistantEdgeTransport,
    AssistantFirmwareTestBench,
    ConsoleScreenAdapter,
    ConsoleSpeakerAdapter,
    EdgeBaseConfig,
    EdgeAudioRequest,
    EdgeAudioResponse,
    LinuxArecordMicrophoneAdapter,
    LinuxSystemSpeakerAdapter,
    StdinMicrophoneAdapter,
    TkScreenAdapter,
)
from src.base.interfaces import TransportClient
from src.base.peripherals import MicrophoneDevice, ScreenDevice, SpeakerDevice

from src.assistant.edge_backend import handle_edge_audio_request
from src.assistant.voice_pipeline import FasterWhisperSpeechToText


@dataclass
class TestbenchMetrics:
    total_turns: int = 0
    sent_turns: int = 0
    rejected_turns: int = 0
    backend_errors: int = 0
    total_latency_ms: float = 0.0
    last_intent: str = "-"
    last_source: str = "-"
    timeline: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.timeline is None:
            self.timeline = []

    @property
    def avg_latency_ms(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return self.total_latency_ms / self.total_turns


def update_metrics(
    metrics: TestbenchMetrics,
    *,
    sent: bool,
    reason: str,
    latency_ms: float,
    response_payload: dict[str, Any] | None,
) -> None:
    metrics.total_turns += 1
    metrics.total_latency_ms += max(0.0, latency_ms)
    if sent:
        metrics.sent_turns += 1
    else:
        metrics.rejected_turns += 1

    if reason == "backend_rejected":
        metrics.backend_errors += 1

    if isinstance(response_payload, dict):
        intent = response_payload.get("intent")
        source = response_payload.get("source")
        if isinstance(intent, str) and intent.strip():
            metrics.last_intent = intent.strip()
        if isinstance(source, str) and source.strip():
            metrics.last_source = source.strip()

    timeline = metrics.timeline if metrics.timeline is not None else []
    timeline.append(
        {
            "timestamp_ms": int(time() * 1000),
            "sent": sent,
            "reason": reason,
            "latency_ms": round(max(0.0, latency_ms), 2),
            "status": (response_payload or {}).get("status") if isinstance(response_payload, dict) else None,
            "intent": (response_payload or {}).get("intent") if isinstance(response_payload, dict) else None,
            "source": (response_payload or {}).get("source") if isinstance(response_payload, dict) else None,
        }
    )
    metrics.timeline = timeline


def format_metrics_line(metrics: TestbenchMetrics) -> str:
    return (
        f"metrics: turns={metrics.total_turns}, sent={metrics.sent_turns}, "
        f"rejected={metrics.rejected_turns}, backend_errors={metrics.backend_errors}, "
        f"avg_latency_ms={metrics.avg_latency_ms:.1f}, "
        f"last_intent={metrics.last_intent}, last_source={metrics.last_source}, "
        f"timeline_events={len(metrics.timeline or [])}"
    )


def build_session_snapshot(metrics: TestbenchMetrics) -> dict[str, Any]:
    return {
        "summary": {
            "total_turns": metrics.total_turns,
            "sent_turns": metrics.sent_turns,
            "rejected_turns": metrics.rejected_turns,
            "backend_errors": metrics.backend_errors,
            "avg_latency_ms": round(metrics.avg_latency_ms, 2),
            "last_intent": metrics.last_intent,
            "last_source": metrics.last_source,
        },
        "timeline": list(metrics.timeline or []),
    }


def maybe_export_snapshot(metrics: TestbenchMetrics) -> str | None:
    export_path = os.getenv("ASSISTANT_TESTBENCH_EXPORT_PATH", "").strip()
    if not export_path:
        return None

    snapshot = build_session_snapshot(metrics)
    parent = os.path.dirname(export_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(export_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=True, indent=2)
    return export_path


def summarize_turn(
    *,
    reason: str,
    latency_ms: float,
    response_payload: dict[str, Any] | None,
) -> str:
    intent = "-"
    source = "-"
    status = "-"
    answer = "-"
    if isinstance(response_payload, dict):
        raw_intent = response_payload.get("intent")
        raw_source = response_payload.get("source")
        raw_status = response_payload.get("status")
        raw_answer = response_payload.get("answer")
        if not isinstance(raw_answer, str):
            raw_answer = response_payload.get("answer_text")
        if isinstance(raw_intent, str) and raw_intent.strip():
            intent = raw_intent.strip()
        if isinstance(raw_source, str) and raw_source.strip():
            source = raw_source.strip()
        if isinstance(raw_status, str) and raw_status.strip():
            status = raw_status.strip()
        if isinstance(raw_answer, str) and raw_answer.strip():
            answer = raw_answer.strip().replace("\n", " ")
            if len(answer) > 120:
                answer = answer[:117] + "..."
    return (
        f"turn: reason={reason}, latency_ms={latency_ms:.1f}, "
        f"status={status}, intent={intent}, source={source}, answer={answer}"
    )


def apply_silence_backoff(*, reason: str, wait_seconds: float) -> bool:
    if reason != "empty_audio":
        return False

    delay = max(0.0, wait_seconds)
    if delay <= 0:
        return False

    sleep(delay)
    return True


class InProcessEdgeBackendTransport(TransportClient):
    """Simulate complete stack in-process using the real edge backend handler."""

    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse:
        raw_body = json.dumps(request.to_dict()).encode("utf-8")
        status_code, response = handle_edge_audio_request(raw_body)
        return EdgeAudioResponse(status_code=status_code, payload=response)


def build_transport(config: EdgeBaseConfig) -> TransportClient:
    mode = os.getenv("ASSISTANT_TESTBENCH_TRANSPORT", "local").strip().lower()
    if mode == "http":
        return AssistantEdgeTransport(config)
    if mode == "local":
        return InProcessEdgeBackendTransport()

    print(f"Testbench: mode transport inconnu '{mode}', fallback local")
    return InProcessEdgeBackendTransport()


def build_linux_microphone(config: EdgeBaseConfig) -> MicrophoneDevice:
    model_size = os.getenv("ASSISTANT_STT_MODEL", "small")
    no_speech_threshold = float(os.getenv("ASSISTANT_STT_NO_SPEECH_THRESHOLD", "0.6"))
    min_avg_amplitude = float(os.getenv("ASSISTANT_STT_MIN_AVG_AMPLITUDE", "180"))
    stt = FasterWhisperSpeechToText(
        model_size=model_size,
        language="fr",
        no_speech_threshold=no_speech_threshold,
        min_avg_amplitude=min_avg_amplitude,
    )
    duration_seconds = int(os.getenv("TESTBENCH_MIC_SECONDS", "3"))
    replay_capture = os.getenv("ASSISTANT_TESTBENCH_REPLAY_CAPTURE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    capture_device = os.getenv("ASSISTANT_TESTBENCH_CAPTURE_DEVICE", "").strip() or None
    playback_device = os.getenv("ASSISTANT_TESTBENCH_PLAYBACK_DEVICE", "").strip() or None
    phrase_mode = os.getenv("ASSISTANT_TESTBENCH_PHRASE_MODE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    max_capture_seconds = float(os.getenv("ASSISTANT_TESTBENCH_MAX_CAPTURE_SECONDS", "10"))
    end_silence_seconds = float(os.getenv("ASSISTANT_TESTBENCH_END_SILENCE_SECONDS", "1.0"))
    vad_start_threshold = float(os.getenv("ASSISTANT_TESTBENCH_VAD_START_THRESHOLD", "120"))
    vad_silence_threshold = float(os.getenv("ASSISTANT_TESTBENCH_VAD_SILENCE_THRESHOLD", "80"))
    vad_chunk_seconds = float(os.getenv("ASSISTANT_TESTBENCH_VAD_CHUNK_SECONDS", "0.2"))
    return LinuxArecordMicrophoneAdapter(
        transcribe=stt.transcribe,
        duration_seconds=duration_seconds,
        sample_rate_hz=config.sample_rate_hz,
        channels=config.channels,
        replay_capture=replay_capture,
        capture_device=capture_device,
        playback_device=playback_device,
        phrase_mode=phrase_mode,
        max_capture_seconds=max_capture_seconds,
        end_silence_seconds=end_silence_seconds,
        vad_start_threshold=vad_start_threshold,
        vad_silence_threshold=vad_silence_threshold,
        vad_chunk_seconds=vad_chunk_seconds,
    )


def build_microphone(config: EdgeBaseConfig) -> MicrophoneDevice:
    mode = os.getenv("ASSISTANT_TESTBENCH_PERIPHERALS", "auto").strip().lower()
    is_linux = platform.system().lower() == "linux"

    if mode == "mock":
        return StdinMicrophoneAdapter(prompt="Micro(simule) > ")

    if mode in {"auto", "system"} and is_linux:
        try:
            return build_linux_microphone(config)
        except RuntimeError as exc:
            print(f"Testbench: micro systeme indisponible ({exc}), fallback clavier")
            return StdinMicrophoneAdapter(prompt="Micro(simule) > ")

    if mode == "system":
        print("Testbench: peripheriques systeme supportes uniquement sous Linux, fallback clavier")
    return StdinMicrophoneAdapter(prompt="Micro(simule) > ")


def build_speaker() -> SpeakerDevice:
    mode = os.getenv("ASSISTANT_TESTBENCH_PERIPHERALS", "auto").strip().lower()
    is_linux = platform.system().lower() == "linux"

    if mode == "mock":
        return ConsoleSpeakerAdapter()

    if mode in {"auto", "system"} and is_linux:
        try:
            return LinuxSystemSpeakerAdapter()
        except RuntimeError as exc:
            print(f"Testbench: speaker systeme indisponible ({exc}), fallback console")
            return ConsoleSpeakerAdapter()

    if mode == "system":
        print("Testbench: peripheriques systeme supportes uniquement sous Linux, fallback console")
    return ConsoleSpeakerAdapter()


def build_screen() -> ScreenDevice:
    mode = os.getenv("ASSISTANT_TESTBENCH_SCREEN", "auto").strip().lower()
    is_linux = platform.system().lower() == "linux"

    if mode == "console":
        return ConsoleScreenAdapter()

    if mode in {"auto", "tk"} and is_linux:
        try:
            return TkScreenAdapter()
        except RuntimeError as exc:
            print(f"Testbench: ecran Tk indisponible ({exc}), fallback console")
            return ConsoleScreenAdapter()

    if mode == "tk":
        print("Testbench: ecran Tk cible Linux desktop, fallback console")
    return ConsoleScreenAdapter()


def run_base_testbench() -> None:
    config = EdgeBaseConfig(
        device_id=os.getenv("EDGE_DEVICE_ID", "desktop-testbench-01"),
        server_base_url=os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8081"),
        wake_word=os.getenv("EDGE_WAKE_WORD", "nova"),
        sample_rate_hz=int(os.getenv("EDGE_SAMPLE_RATE_HZ", "16000")),
        channels=int(os.getenv("EDGE_CHANNELS", "1")),
        encoding=os.getenv("EDGE_ENCODING", "pcm16le"),
        min_voice_chars=int(os.getenv("EDGE_MIN_VOICE_CHARS", "6")),
        timeout_seconds=float(os.getenv("EDGE_TIMEOUT_SECONDS", "3.0")),
        retry_attempts=int(os.getenv("EDGE_RETRY_ATTEMPTS", "2")),
        retry_backoff_seconds=float(os.getenv("EDGE_RETRY_BACKOFF_SECONDS", "0.2")),
    )

    transport = build_transport(config)
    microphone = build_microphone(config)
    speaker = build_speaker()
    screen = build_screen()

    force_wake_word_prefix = os.getenv("ASSISTANT_TESTBENCH_FORCE_WAKE_WORD_PREFIX", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    bench = AssistantFirmwareTestBench(
        config=config,
        transport=transport,
        microphone=microphone,
        speaker=speaker,
        screen=screen,
        force_wake_word_prefix=force_wake_word_prefix,
    )

    transport_mode = os.getenv("ASSISTANT_TESTBENCH_TRANSPORT", "local").strip().lower()
    peripheral_mode = os.getenv("ASSISTANT_TESTBENCH_PERIPHERALS", "auto").strip().lower()
    screen_mode = os.getenv("ASSISTANT_TESTBENCH_SCREEN", "auto").strip().lower()
    silence_wait_seconds = float(os.getenv("ASSISTANT_TESTBENCH_SILENCE_WAIT_SECONDS", "5"))
    replay_capture = os.getenv("ASSISTANT_TESTBENCH_REPLAY_CAPTURE", "true").strip().lower()
    capture_device = os.getenv("ASSISTANT_TESTBENCH_CAPTURE_DEVICE", "").strip() or "auto"
    playback_device = os.getenv("ASSISTANT_TESTBENCH_PLAYBACK_DEVICE", "").strip() or "auto"

    print("=== Base de test firmware edge ===")
    print("Simulation complete: intents locaux, providers externes, fallback Leon, etat edge")
    print("Format d'echange: contrat /edge/audio v2")
    print(f"Transport: {transport_mode} (local=in-process, http=backend distant)")
    print(f"Peripheriques: {peripheral_mode} (auto/system/mock)")
    print(f"Ecran: {screen_mode} (auto/tk/console)")
    print(f"Replay capture: {replay_capture} (true/false)")
    print(f"Capture device: {capture_device}")
    print(f"Playback device: {playback_device}")
    print(f"Force wake-word prefix: {str(force_wake_word_prefix).lower()} (true/false)")
    print(f"Silence wait: {silence_wait_seconds:.1f}s apres empty_audio")
    print("Commandes: /help /status /mute /unmute")
    print("Entrer une requete avec wake word (ex: nova quelle heure est-il)")
    print("Saisir quit/exit/stop pour arreter.")
    if shutil.which("arecord") is None:
        print("Info: arecord absent -> micro clavier simule")

    metrics = TestbenchMetrics()

    while True:
        turn_start = perf_counter()
        record = bench.run_once()
        if record is None:
            break
        latency_ms = (perf_counter() - turn_start) * 1000
        update_metrics(
            metrics,
            sent=record.runtime_result.sent,
            reason=record.runtime_result.reason,
            latency_ms=latency_ms,
            response_payload=record.response_payload,
        )

        screen_message = (
            summarize_turn(
                reason=record.runtime_result.reason,
                latency_ms=latency_ms,
                response_payload=record.response_payload,
            )
            + "\n"
            + format_metrics_line(metrics)
        )
        screen_state = "speaking" if record.runtime_result.sent else "idle"
        if record.runtime_result.reason == "backend_rejected":
            screen_state = "error"
        screen.show(state=screen_state, message=screen_message)

        print("----")
        print(f"transcript: {record.transcript}")
        print(f"result: sent={record.runtime_result.sent}, reason={record.runtime_result.reason}")
        print(f"latency_ms: {latency_ms:.1f}")
        if record.request_payload is not None:
            print(
                "request: "
                f"cid={record.request_payload.get('correlation_id')} "
                f"encoding={record.request_payload.get('encoding')} "
                f"sample_rate={record.request_payload.get('sample_rate_hz')}"
            )
        if record.response_payload is not None:
            source = record.response_payload.get("source")
            answer = record.response_payload.get("answer")
            if not isinstance(answer, str):
                answer = record.response_payload.get("answer_text")
            answer_text = answer.strip() if isinstance(answer, str) and answer.strip() else "-"
            print(
                "response: "
                f"status={record.response_payload.get('status')} "
                f"api_version={record.response_payload.get('api_version')} "
                f"intent={record.response_payload.get('intent')} "
                f"source={source}"
            )
            print(f"response_answer: {answer_text}")
            print(format_metrics_line(metrics))

        if apply_silence_backoff(reason=record.runtime_result.reason, wait_seconds=silence_wait_seconds):
            print(f"silence_backoff: attente {max(0.0, silence_wait_seconds):.1f}s")

        exported = maybe_export_snapshot(metrics)
        if exported is not None:
            print(f"snapshot_export: {exported}")
