from __future__ import annotations

import os

from src.base import (
    AssistantEdgeTransport,
    AssistantFirmwareTestBench,
    ConsoleScreenAdapter,
    ConsoleSpeakerAdapter,
    EdgeBaseConfig,
    StdinMicrophoneAdapter,
)


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

    bench = AssistantFirmwareTestBench(
        config=config,
        transport=AssistantEdgeTransport(config),
        microphone=StdinMicrophoneAdapter(prompt="Micro(simule) > "),
        speaker=ConsoleSpeakerAdapter(),
        screen=ConsoleScreenAdapter(),
    )

    print("=== Base de test firmware edge ===")
    print("Format d'echange: contrat /edge/audio v2")
    print("Saisir du texte simule apres wake word (ex: 'nova quelle heure est-il').")
    print("Saisir quit/exit/stop pour arreter.")

    for record in bench.run_until_stop():
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
