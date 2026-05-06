#!/usr/bin/env python3.13
"""
Serveur mock FastAPI — AssistantVocal Phase 1.
GET  /health       -> ping
POST /edge/audio   -> reçoit PCM16LE base64, renvoie réponse stub
Usage : python3 scripts/mock_server.py [port]
"""
import base64
import logging
import math
import struct
import sys
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("mock_server")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
START_TIME = time.time()
app = FastAPI(title="AssistantVocal mock server")

def make_tone_pcm16(sr: int = 16000, hz: int = 660, duration_ms: int = 700, amp: int = 12000) -> bytes:
    samples = max(1, int(sr * duration_ms / 1000))
    out = bytearray(samples * 2)
    for i in range(samples):
        v = int(amp * math.sin(2.0 * math.pi * hz * (i / sr)))
        out[2 * i:2 * i + 2] = struct.pack("<h", v)
    return bytes(out)

def apply_gain_pcm16(pcm: bytes, gain: float = 3.0) -> bytes:
    if not pcm:
        return pcm
    samples = len(pcm) // 2
    values = list(struct.unpack(f"<{samples}h", pcm[:samples * 2]))
    boosted: list[int] = []
    for s in values:
        v = int(s * gain)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        boosted.append(v)
    return struct.pack(f"<{samples}h", *boosted)

@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "version": "mock-0.2.0", "uptime_s": int(time.time() - START_TIME)}

@app.post("/edge/audio")
async def edge_audio(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("JSON invalide: %s", exc)
        return JSONResponse(status_code=400, content={"error": "invalid json"})
    cid       = payload.get("correlation_id", "")
    encoding  = payload.get("encoding", "pcm16le")
    sr        = payload.get("sample_rate_hz", 16000)
    channels  = payload.get("channels", 1)
    audio_b64 = payload.get("audio_base64", "")
    received_bytes = 0
    duration_ms = 0
    if audio_b64:
        try:
            pcm = base64.b64decode(audio_b64)
            received_bytes = len(pcm)
            samples = received_bytes // 2
            duration_ms = int(samples / max(sr, 1) * 1000)
            shorts = struct.unpack(f"<{samples}h", pcm[:samples * 2])
            rms = int((sum(s*s for s in shorts) / max(len(shorts), 1)) ** 0.5)
            logger.info("Audio: %d bytes, %d ms, RMS=%d", received_bytes, duration_ms, rms)
        except Exception as exc:
            logger.warning("Decode audio: %s", exc)
    # Echo: renvoie le son capturé tel quel.
    # Fallback bip si audio absent/non décodable pour garder un retour audible de diagnostic.
    if audio_b64 and received_bytes > 0:
        try:
            in_pcm = base64.b64decode(audio_b64)
            out_pcm = apply_gain_pcm16(in_pcm, gain=3.0)
            response_b64 = base64.b64encode(out_pcm).decode()
            logger.info("Reply audio: echo+gain bytes=%d gain=3.0x", len(out_pcm))
        except Exception as exc:
            logger.warning("Echo gain failed: %s", exc)
            response_b64 = audio_b64
            logger.info("Reply audio: raw echo %d bytes", received_bytes)
    else:
        response_pcm = make_tone_pcm16(sr=16000, hz=660, duration_ms=700)
        response_b64 = base64.b64encode(response_pcm).decode()
        logger.info("Reply audio: fallback tone %d bytes", len(response_pcm))

    stub_answer = f"Recu {received_bytes} bytes ({duration_ms} ms). Echo audio renvoyé."
    return JSONResponse(status_code=202, content={
        "status": "accepted", "api_version": "v2",
        "correlation_id": cid, "received_bytes": received_bytes,
        "duration_ms": duration_ms, "encoding": encoding,
        "sample_rate_hz": sr, "channels": channels,
        "audio_base64": response_b64,
        "intent": "commande_stub", "answer": stub_answer,
    })

if __name__ == "__main__":
    print(f"Mock server port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
