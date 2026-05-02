from __future__ import annotations

import json
import os
import platform
import shutil

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
    stt = FasterWhisperSpeechToText(model_size=model_size, language="fr")
    duration_seconds = int(os.getenv("TESTBENCH_MIC_SECONDS", "3"))
    return LinuxArecordMicrophoneAdapter(
        transcribe=stt.transcribe,
        duration_seconds=duration_seconds,
        sample_rate_hz=config.sample_rate_hz,
        channels=config.channels,
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

    bench = AssistantFirmwareTestBench(
        config=config,
        transport=transport,
        microphone=microphone,
        speaker=speaker,
        screen=screen,
    )

    transport_mode = os.getenv("ASSISTANT_TESTBENCH_TRANSPORT", "local").strip().lower()
    peripheral_mode = os.getenv("ASSISTANT_TESTBENCH_PERIPHERALS", "auto").strip().lower()
    screen_mode = os.getenv("ASSISTANT_TESTBENCH_SCREEN", "auto").strip().lower()

    print("=== Base de test firmware edge ===")
    print("Simulation complete: intents locaux, providers externes, fallback Leon, etat edge")
    print("Format d'echange: contrat /edge/audio v2")
    print(f"Transport: {transport_mode} (local=in-process, http=backend distant)")
    print(f"Peripheriques: {peripheral_mode} (auto/system/mock)")
    print(f"Ecran: {screen_mode} (auto/tk/console)")
    print("Commandes: /help /status /mute /unmute")
    print("Entrer une requete avec wake word (ex: nova quelle heure est-il)")
    print("Saisir quit/exit/stop pour arreter.")
    if shutil.which("arecord") is None:
        print("Info: arecord absent -> micro clavier simule")

    while True:
        record = bench.run_once()
        if record is None:
            break
        print("----")
        print(f"transcript: {record.transcript}")
        print(f"result: sent={record.runtime_result.sent}, reason={record.runtime_result.reason}")
        if record.request_payload is not None:
            print(
                "request: "
                f"cid={record.request_payload.get('correlation_id')} "
                f"encoding={record.request_payload.get('encoding')} "
                f"sample_rate={record.request_payload.get('sample_rate_hz')}"
            )
        if record.response_payload is not None:
            print(
                "response: "
                f"status={record.response_payload.get('status')} "
                f"api_version={record.response_payload.get('api_version')} "
                f"intent={record.response_payload.get('intent')}"
            )
