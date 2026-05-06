#!/usr/bin/env python3
"""
AssistantVocal — serveur pont LLM.

Pipeline : PCM16LE base64 → Whisper STT → LLM (Ollama) → Piper TTS → PCM16LE base64

Interface HTTP identique au mock (compat firmware inchangé) :
  GET  /health
  POST /edge/audio

Variables d'environnement (voir .env.example) :
  LANGUAGE      Langue STT/TTS              (défaut : fr)
  WHISPER_MODEL Modèle faster-whisper       (défaut : medium)
  PIPER_VOICE   Voix Piper                  (défaut : fr_FR-siwis-medium)
  PIPER_DATA_DIR Répertoire modèles Piper   (défaut : ./models/piper)
  LLM_URL       URL Ollama                  (défaut : http://localhost:11434)
  LLM_MODEL     Modèle Ollama               (défaut : llama3.2)
  LLM_SYSTEM    Prompt système LLM          (défaut : assistant domotique français)
  SERVER_PORT   Port d'écoute               (défaut : 8080)
  ECHO_FALLBACK Echo PCM sans appel LLM     (défaut : false)
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import math
import operator as _op
import os
import re
import struct
import sys
import time
import unicodedata
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ha_bridge")

# ── Configuration ─────────────────────────────────────────────────────────────

LANGUAGE      = os.getenv("LANGUAGE",      "fr")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
PIPER_VOICE   = os.getenv("PIPER_VOICE",   "fr_FR-siwis-medium")
PIPER_DATA_DIR= Path(os.getenv("PIPER_DATA_DIR", "./models/piper"))
LLM_URL       = os.getenv("LLM_URL",       "http://localhost:11434").rstrip("/")
LLM_MODEL     = os.getenv("LLM_MODEL",     "llama3.2")
LLM_SYSTEM    = os.getenv(
    "LLM_SYSTEM",
    "Tu es un assistant vocal francophone polyvalent, intelligent et concis. "
    "Tu réponds en une ou deux phrases courtes et naturelles, adaptées à être prononcées à voix haute. "
    "Tu peux répondre à des questions générales, faire des calculs, donner la météo et l'heure. "
    "Utilise les outils disponibles quand c'est pertinent.",
)
LLM_TOOLS_ENABLED = os.getenv("LLM_TOOLS_ENABLED", "true").lower() == "true"
LOCATION_LAT  = float(os.getenv("LOCATION_LAT",  "48.8566"))  # Paris par défaut
LOCATION_LON  = float(os.getenv("LOCATION_LON",  "2.3522"))
LOCATION_NAME = os.getenv("LOCATION_NAME", "Paris")
SERVER_PORT       = int(os.getenv("SERVER_PORT", "8080"))
ECHO_FALLBACK     = os.getenv("ECHO_FALLBACK", "false").lower() == "true"
LLM_MAX_TOKENS    = int(os.getenv("LLM_MAX_TOKENS", "100"))  # tokens max LLM (réponse courte)
# PCM max retourné au firmware : AUDIO_RESP_MAX_SIZE firmware = 350 000 bytes
# base64(240 000) ≈ 320 000 bytes + overhead JSON ≈ 330 000 < 350 000 ✓
MAX_TTS_PCM_BYTES = int(os.getenv("MAX_TTS_PCM_BYTES", "240000"))  # ~7,5 s à 16 kHz
_TTS_VOLUME       = [float(os.getenv("TTS_VOLUME", "1.0"))]         # mutable — contrôle vocal
VOLUME_STATE_FILE = Path(os.getenv("VOLUME_STATE_FILE", "/app/models/piper/tts_volume.json"))
FIRMWARE_SR   = 16_000   # sample rate attendu par le firmware ESP32

# ── Streaming TTS par chunks (découpe par phrases) ────────────────────────────
# Stockage temporaire des chunks audio en attente de récupération par le firmware
_stream_store: dict[str, dict[str, Any]] = {}  # stream_id → {chunks: list[bytes], created: float}
_STREAM_TTL_S = 120  # durée de vie d'une session de streaming (secondes)

# ── Modèles (chargés au démarrage) ───────────────────────────────────────────

_whisper_model: Any = None
_piper_voice:   Any = None


def _load_whisper() -> None:
    global _whisper_model
    from faster_whisper import WhisperModel
    import ctranslate2
    use_cuda = ctranslate2.get_cuda_device_count() > 0
    device       = "cuda" if use_cuda else "cpu"
    compute_type = "float16" if use_cuda else "int8"
    logger.info("Chargement Whisper '%s' sur %s (%s) …", WHISPER_MODEL, device, compute_type)
    t0 = time.perf_counter()
    _whisper_model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
    logger.info("Whisper prêt en %.1f s", time.perf_counter() - t0)


def _load_piper() -> None:
    global _piper_voice
    try:
        from piper.voice import PiperVoice
    except ImportError:
        logger.warning("piper-tts non installé — TTS désactivé")
        return

    PIPER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    model_path  = PIPER_DATA_DIR / f"{PIPER_VOICE}.onnx"
    config_path = PIPER_DATA_DIR / f"{PIPER_VOICE}.onnx.json"

    if not model_path.exists():
        logger.info("Téléchargement modèle Piper '%s' …", PIPER_VOICE)
        _download_piper_model(PIPER_VOICE, model_path, config_path)

    logger.info("Chargement Piper '%s' …", PIPER_VOICE)
    _piper_voice = PiperVoice.load(str(model_path), config_path=str(config_path), use_cuda=False)
    logger.info("Piper prêt — sample_rate=%d Hz", _piper_voice.config.sample_rate)


def _download_piper_model(voice: str, model_path: Path, config_path: Path) -> None:
    """Télécharge le modèle ONNX + config depuis le dépôt Piper officiel."""
    # ex: fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
    voice_parts = voice.split("-")  # ['fr_FR', 'siwis', 'medium']
    if len(voice_parts) != 3:
        raise ValueError(f"Format de voix Piper invalide: {voice}")
    lang, name, quality = voice_parts[0], voice_parts[1], voice_parts[2]
    lang_short = lang.split("_")[0]
    url_base = (
        f"https://huggingface.co/rhasspy/piper-voices/resolve/main"
        f"/{lang_short}/{lang}/{name}/{quality}"
    )
    for url, dest in [
        (f"{url_base}/{voice}.onnx",      model_path),
        (f"{url_base}/{voice}.onnx.json", config_path),
    ]:
        logger.info("GET %s", url)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        logger.info("  → %s (%d kB)", dest.name, len(r.content) // 1024)


# ── Pipeline audio ────────────────────────────────────────────────────────────

def _pcm16le_to_float32(pcm: bytes) -> np.ndarray:
    """Convertit PCM16LE bytes → float32 normalisé [-1, 1]."""
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    return samples


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Rééchantillonne si nécessaire (scipy)."""
    if src_sr == dst_sr:
        return audio
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(src_sr, dst_sr)
    return resample_poly(audio, dst_sr // g, src_sr // g).astype(np.float32)


def _float32_to_pcm16le(audio: np.ndarray) -> bytes:
    """float32 [-1,1] → PCM16LE bytes (clip + conversion)."""
    clipped = np.clip(audio, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def _transcribe(pcm: bytes, sample_rate: int) -> str:
    """STT : PCM16LE bytes → texte (faster-whisper)."""
    if _whisper_model is None:
        raise RuntimeError("Whisper non initialisé")
    audio = _pcm16le_to_float32(pcm)
    audio = _resample(audio, sample_rate, 16_000)  # Whisper exige 16 kHz
    if audio.size == 0:
        return ""

    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(np.square(audio))))
    logger.info("STT input stats: peak=%.5f rms=%.5f", peak, rms)

    # Signal trop faible (silence pur) : renvoyer vide immédiatement.
    # Ne pas appeler Whisper sur du silence — il hallucine.
    if peak < 0.001:
        logger.info("STT silence détecté (peak<0.001) — skip")
        return ""

    # Sur certaines cartes, le niveau micro est faible: on normalise modérément
    # pour aider Whisper sans saturer brutalement.
    if peak < 0.12:
        gain = min(12.0, 0.12 / peak)
        audio = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
        logger.info("STT auto-gain appliqué: x%.2f", gain)

    segments, _ = _whisper_model.transcribe(
        audio, language=LANGUAGE, beam_size=5, vad_filter=True
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    if text:
        return text

    # Retry sans VAD: utile quand la détection voix coupe une parole faible/courte.
    segments, _ = _whisper_model.transcribe(
        audio, language=LANGUAGE, beam_size=5, vad_filter=False
    )
    return " ".join(s.text.strip() for s in segments).strip()


# ── Outils LLM (tool calling) ────────────────────────────────────────────────

_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Retourne la date et l'heure actuelles.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Retourne la météo actuelle pour le lieu configuré.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Effectue un calcul mathématique simple (ex: 12 * 4.5, 100 / 7).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expression mathématique à évaluer",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

# Opérateurs autorisés pour la calculatrice sécurisée
_SAFE_OPS: dict = {
    ast.Add:      _op.add,
    ast.Sub:      _op.sub,
    ast.Mult:     _op.mul,
    ast.Div:      _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod:      _op.mod,
    ast.Pow:      _op.pow,
    ast.USub:     _op.neg,
    ast.UAdd:     _op.pos,
}


def _safe_eval(expr: str) -> float:
    """Évalue une expression arithmétique sans exec/eval Python natif."""
    def _walk(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            fn = _SAFE_OPS.get(type(node.op))
            if fn is None:
                raise ValueError(f"Opérateur non supporté : {type(node.op).__name__}")
            return fn(_walk(node.left), _walk(node.right))
        if isinstance(node, ast.UnaryOp):
            fn = _SAFE_OPS.get(type(node.op))
            if fn is None:
                raise ValueError("Opérateur unaire non supporté")
            return fn(_walk(node.operand))
        raise ValueError(f"Nœud non supporté : {type(node).__name__}")
    tree = ast.parse(expr.strip(), mode="eval")
    return _walk(tree.body)


def _tool_get_datetime() -> str:
    import datetime
    now = datetime.datetime.now()
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois  = ["janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return (
        f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}, "
        f"{now.hour:02d}h{now.minute:02d}"
    )


def _tool_get_weather() -> str:
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LOCATION_LAT}&longitude={LOCATION_LON}"
        f"&current=temperature_2m,weathercode,windspeed_10m"
        f"&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        cur = r.json()["current"]
    except Exception as exc:
        return f"Météo indisponible ({exc})."
    temp = cur["temperature_2m"]
    wind = cur["windspeed_10m"]
    code = int(cur["weathercode"])
    _WMO = {
        0: "ciel dégagé", 1: "principalement dégagé", 2: "partiellement nuageux",
        3: "couvert", 45: "brouillard", 48: "brouillard givrant",
        51: "bruine légère", 53: "bruine modérée", 55: "bruine dense",
        61: "pluie légère", 63: "pluie modérée", 65: "pluie forte",
        71: "neige légère", 73: "neige modérée", 75: "neige forte",
        80: "averses", 81: "averses modérées", 82: "averses violentes",
        95: "orage", 96: "orage avec grêle",
    }
    desc = _WMO.get(code, f"code météo {code}")
    return f"À {LOCATION_NAME} : {temp}°C, {desc}, vent {wind} km/h."


def _tool_calculate(expression: str) -> str:
    try:
        result = _safe_eval(expression)
        # Affichage propre : entier si possible
        if result == int(result):
            return str(int(result))
        return f"{result:.6g}"
    except Exception as exc:
        return f"Erreur de calcul : {exc}"


def _execute_tool(name: str, args_raw: str) -> str:
    """Exécute un outil et retourne le résultat en chaîne."""
    try:
        args = json.loads(args_raw) if args_raw else {}
    except json.JSONDecodeError:
        args = {}
    logger.info("Outil appelé : %s(%s)", name, args)
    if name == "get_datetime":
        return _tool_get_datetime()
    if name == "get_weather":
        return _tool_get_weather()
    if name == "calculate":
        return _tool_calculate(args.get("expression", ""))
    return f"Outil inconnu : {name}"


def _ask_llm(text: str) -> str:
    """Envoie le texte à Ollama avec support du tool calling (max 5 tours)."""
    url = f"{LLM_URL}/v1/chat/completions"
    messages: list[dict] = [
        {"role": "system", "content": LLM_SYSTEM},
        {"role": "user",   "content": text},
    ]
    for _turn in range(5):  # garde-fou anti-boucle infinie
        payload: dict = {
            "model":      LLM_MODEL,
            "messages":   messages,
            "max_tokens": LLM_MAX_TOKENS,
            "stream":     False,
        }
        if LLM_TOOLS_ENABLED:
            payload["tools"]       = _TOOL_DEFS
            payload["tool_choice"] = "auto"
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data   = resp.json()
        choice = data["choices"][0]
        msg    = choice["message"]
        finish = choice.get("finish_reason", "")

        if finish == "tool_calls" or msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                result = _execute_tool(
                    tc["function"]["name"],
                    tc["function"].get("arguments", "{}"),
                )
                logger.info("Outil '%s' → %s", tc["function"]["name"], result)
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc["id"],
                    "content":      result,
                })
            continue  # retourner avec le résultat de l'outil

        try:
            return msg["content"].strip()
        except (KeyError, TypeError) as exc:
            logger.warning("Réponse LLM inattendue : %s — %s", data, exc)
            return str(data)

    return "Je n'ai pas pu obtenir une réponse complète."


def _synthesize(text: str) -> tuple[bytes, int]:
    """TTS : texte → (PCM16LE bytes, sample_rate). Compatible piper-tts >= 1.4."""
    import io
    import wave as _wave
    if _piper_voice is None:
        raise RuntimeError("Piper non initialisé")
    wav_io = io.BytesIO()
    with _wave.open(wav_io, "wb") as wf:
        _piper_voice.synthesize_wav(text, wf)
    wav_io.seek(0)
    with _wave.open(wav_io, "rb") as wf:
        sr = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    logger.info("TTS → %d bytes PCM à %d Hz", len(pcm), sr)
    return pcm, sr


def _split_sentences(text: str) -> list[str]:
    """Découpe un texte en phrases individuelles pour le TTS streaming."""
    # Découpe sur ponctuation forte suivie d'un espace ou fin de chaîne
    parts = re.split(r'(?<=[.!?;])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _tts_to_pcm_16k(text: str) -> bytes:
    """Synthétise du texte → PCM16LE 16 kHz (rééchantillonné si besoin)."""
    tts_pcm, tts_sr = _synthesize(text)
    if tts_sr != FIRMWARE_SR:
        audio_f32 = _pcm16le_to_float32(tts_pcm)
        audio_f32 = _resample(audio_f32, tts_sr, FIRMWARE_SR)
        pcm = _float32_to_pcm16le(audio_f32)
    else:
        pcm = tts_pcm
    if _TTS_VOLUME[0] != 1.0:
        pcm = _apply_gain(pcm, _TTS_VOLUME[0])
    if len(pcm) > MAX_TTS_PCM_BYTES:
        logger.warning("TTS chunk tronqué : %d → %d bytes", len(pcm), MAX_TTS_PCM_BYTES)
        pcm = pcm[:MAX_TTS_PCM_BYTES & ~1]
    return pcm


def _clamp_volume(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _persist_volume_state() -> None:
    """Sauvegarde le volume courant dans un fichier JSON persistant."""
    try:
        VOLUME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tts_volume": _TTS_VOLUME[0],
            "updated_at": int(time.time()),
        }
        tmp_path = VOLUME_STATE_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data), encoding="utf-8")
        tmp_path.replace(VOLUME_STATE_FILE)
    except Exception as exc:
        logger.warning("Impossible de sauvegarder le volume: %s", exc)


def _load_volume_state() -> None:
    """Recharge le volume depuis le fichier JSON s'il existe."""
    if not VOLUME_STATE_FILE.exists():
        _TTS_VOLUME[0] = _clamp_volume(_TTS_VOLUME[0])
        return
    try:
        data = json.loads(VOLUME_STATE_FILE.read_text(encoding="utf-8"))
        saved = _clamp_volume(data.get("tts_volume", _TTS_VOLUME[0]))
        _TTS_VOLUME[0] = saved
        logger.info("Volume restauré depuis %s: %.0f%%", VOLUME_STATE_FILE, saved * 100)
    except Exception as exc:
        logger.warning("Impossible de recharger le volume (%s): %s", VOLUME_STATE_FILE, exc)


# ── Commandes vocales volume ──────────────────────────────────────────────────

_RE_VOL_SET_1 = re.compile(
    r"(?:met|mets|mettre|regle|regler|fixe|passe|place)\s+(?:le\s+)?(?:son|volume|audio)\s+a\s*(\d{1,3})(?:\s*(?:%|pour\s*cent|pourcent))?",
    re.IGNORECASE,
)
_RE_VOL_SET_2 = re.compile(
    r"(?:son|volume|audio)\s+a\s*(\d{1,3})(?:\s*(?:%|pour\s*cent|pourcent))?",
    re.IGNORECASE,
)
_RE_VOL_UP   = re.compile(
    r"(?:monte|augment[e]?|hausse|plus\s+fort|plus\s+haut)(?:\s+(?:le\s+)?(?:son|volume|audio))?"
    r"|(?:le\s+)?(?:son|volume|audio)\s+(?:plus\s+fort|plus\s+haut)",
    re.IGNORECASE,
)
_RE_VOL_DOWN = re.compile(
    r"(?:baisse|diminue|reduis|moins\s+fort|plus\s+bas)(?:\s+(?:le\s+)?(?:son|volume|audio))?"
    r"|(?:le\s+)?(?:son|volume|audio)\s+(?:moins\s+fort|plus\s+bas)",
    re.IGNORECASE,
)
_RE_VOL_MUTE = re.compile(
    r"(?:coupe|eteins|mute|silence)(?:\s+(?:le\s+)?(?:son|volume|audio))?",
    re.IGNORECASE,
)
_RE_VOL_MAX  = re.compile(
    r"(?:volume|son)\s+(?:au\s+)?(?:maximum|max|plein|fond)"
    r"|(?:plein\s+volume|son\s+au\s+max)",
    re.IGNORECASE,
)


def _normalize_for_command(text: str) -> str:
    """Normalise texte STT (minuscules, sans accents, espaces compressés)."""
    s = unicodedata.normalize("NFD", text)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9%\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _handle_volume_command(text: str) -> str | None:
    """Détecte une commande vocale volume et sauvegarde la nouvelle valeur."""
    cmd = _normalize_for_command(text)
    cur = _TTS_VOLUME[0]

    m = _RE_VOL_SET_1.search(cmd) or _RE_VOL_SET_2.search(cmd)
    if m:
        pct = max(0, min(100, int(m.group(1))))
        _TTS_VOLUME[0] = _clamp_volume(pct / 100.0)
        _persist_volume_state()
        logger.info("Volume vocal : set → %d%%", pct)
        return f"Volume réglé à {pct} pour cent."

    if _RE_VOL_MAX.search(cmd):
        _TTS_VOLUME[0] = 1.0
        _persist_volume_state()
        logger.info("Volume vocal : max")
        return "Volume au maximum."

    if _RE_VOL_MUTE.search(cmd):
        _TTS_VOLUME[0] = 0.0
        _persist_volume_state()
        logger.info("Volume vocal : mute")
        return "Son coupé."

    if _RE_VOL_UP.search(cmd):
        new = _clamp_volume(round(cur + 0.2, 2))
        _TTS_VOLUME[0] = new
        _persist_volume_state()
        logger.info("Volume vocal : +20%% → %.0f%%", new * 100)
        return f"Volume augmenté, {int(new * 100)} pour cent."

    if _RE_VOL_DOWN.search(cmd):
        new = _clamp_volume(round(cur - 0.2, 2))
        _TTS_VOLUME[0] = new
        _persist_volume_state()
        logger.info("Volume vocal : -20%% → %.0f%%", new * 100)
        return f"Volume baissé, {int(new * 100)} pour cent."

    return None


def _cleanup_streams() -> None:
    """Supprime les sessions de streaming expirées."""
    now = time.time()
    expired = [k for k, v in list(_stream_store.items()) if now - v["created"] > _STREAM_TTL_S]
    for k in expired:
        del _stream_store[k]
    if expired:
        logger.debug("Streaming : %d session(s) expirée(s) supprimée(s)", len(expired))


def _make_tone_pcm16(sr: int = 16000, hz: int = 660, duration_ms: int = 700) -> bytes:
    """Génère un bip de diagnostic (fallback)."""
    n = max(1, int(sr * duration_ms / 1000))
    out = bytearray(n * 2)
    amp = 12000
    for i in range(n):
        v = int(amp * math.sin(2.0 * math.pi * hz * (i / sr)))
        struct.pack_into("<h", out, i * 2, max(-32768, min(32767, v)))
    return bytes(out)


def _apply_gain(pcm: bytes, gain: float) -> bytes:
    n = len(pcm) // 2
    vals = np.frombuffer(pcm[:n * 2], dtype="<i2").astype(np.int32)
    vals = np.clip(vals * gain, -32768, 32767).astype("<i2")
    return vals.tobytes()


# ── Lifespan FastAPI ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_volume_state()
    _load_whisper()
    _load_piper()
    logger.info("LLM backend : %s — modèle : %s", LLM_URL, LLM_MODEL)
    yield


app = FastAPI(title="AssistantVocal LLM bridge", lifespan=lifespan)
_start_time = time.time()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    llm_reachable = False
    try:
        r = requests.get(f"{LLM_URL}/api/tags", timeout=3)
        llm_reachable = r.ok
    except Exception:
        pass
    return {
        "ok":             True,
        "version":        "llm-bridge-1.0.0",
        "uptime_s":       int(time.time() - _start_time),
        "whisper_loaded": _whisper_model is not None,
        "piper_loaded":   _piper_voice   is not None,
        "llm_reachable":  llm_reachable,
        "llm_url":        LLM_URL,
        "llm_model":      LLM_MODEL,
    }


@app.post("/edge/audio")
async def edge_audio(request: Request):  # noqa: C901
    # ── 1. Parse payload ──────────────────────────────────────────────
    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("JSON invalide : %s", exc)
        return JSONResponse(status_code=400, content={"status": "error", "reason": "invalid_json"})

    cid      = payload.get("correlation_id", "")
    encoding = payload.get("encoding", "pcm16le")
    sr       = int(payload.get("sample_rate_hz", FIRMWARE_SR))
    channels = int(payload.get("channels", 1))
    audio_b64= payload.get("audio_base64", "")

    if not audio_b64:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "empty_audio"})

    # ── 2. Décode PCM ─────────────────────────────────────────────────
    try:
        in_pcm = base64.b64decode(audio_b64)
    except Exception as exc:
        logger.warning("Décodage base64 : %s", exc)
        return JSONResponse(status_code=400, content={"status": "error", "reason": "invalid_audio_base64"})

    received_bytes = len(in_pcm)
    samples        = received_bytes // 2
    duration_ms    = int(samples / max(sr, 1) * 1000)
    logger.info("Audio reçu : %d bytes / %d ms (cid=%s)", received_bytes, duration_ms, cid)

    # ── 3. Fallback echo (ECHO_FALLBACK=true) ────────────────────────
    if ECHO_FALLBACK:
        logger.info("Mode echo (ECHO_FALLBACK=true)")
        out_pcm = _apply_gain(in_pcm, 3.0)
        return JSONResponse(status_code=202, content=_build_response(
            cid, received_bytes, duration_ms, encoding, sr, channels,
            out_pcm, intent="echo", answer="Mode echo — mettre ECHO_FALLBACK=false pour activer LLM.",
        ))

    # ── 4. STT ────────────────────────────────────────────────────────
    try:
        transcript = _transcribe(in_pcm, sr)
    except Exception as exc:
        logger.error("STT échoué : %s", exc, exc_info=True)
        fallback_pcm = _make_tone_pcm16()
        return JSONResponse(status_code=202, content=_build_response(
            cid, received_bytes, duration_ms, encoding, sr, channels,
            fallback_pcm, intent="stt_error", answer="Erreur de transcription.",
        ))

    logger.info("STT → '%s'", transcript)
    if not transcript:
        fallback_pcm = _make_tone_pcm16(hz=440, duration_ms=200)
        return JSONResponse(status_code=202, content=_build_response(
            cid, received_bytes, duration_ms, encoding, sr, channels,
            fallback_pcm, intent="empty_transcript", answer="",
        ))

    # ── 5. Commande volume (sans LLM) ─────────────────────────────────
    vol_response = _handle_volume_command(transcript)
    if vol_response is not None:
        answer_text = vol_response
        logger.info("Commande volume → '%s'", answer_text)
    else:
        # ── 6. LLM ───────────────────────────────────────────────────────
        try:
            answer_text = _ask_llm(transcript)
        except Exception as exc:
            logger.error("LLM échoué : %s", exc, exc_info=True)
            answer_text = "Je ne peux pas joindre le modèle de langage pour le moment."
        logger.info("LLM → '%s'", answer_text)

    # ── 6. TTS streaming par phrases ─────────────────────────────────
    _cleanup_streams()
    try:
        sentences = _split_sentences(answer_text)
        if not sentences:
            sentences = [answer_text]

        chunks: list[bytes] = []
        for sent in sentences:
            try:
                chunks.append(_tts_to_pcm_16k(sent))
            except Exception as exc:
                logger.warning("TTS phrase ignorée '%s': %s", sent[:40], exc)

        if not chunks:
            chunks = [_make_tone_pcm16(hz=880, duration_ms=500)]

        first_chunk = chunks[0]
        extra_chunks = chunks[1:]

        logger.info("TTS : %d phrase(s) → %d chunk(s), first=%d bytes",
                    len(sentences), len(chunks), len(first_chunk))

    except Exception as exc:
        logger.error("TTS échoué : %s", exc, exc_info=True)
        first_chunk = _make_tone_pcm16(hz=880, duration_ms=500)
        extra_chunks = []

    # Si plusieurs chunks : enregistre les suivants en attente et retourne stream_id
    stream_id: str | None = None
    if extra_chunks:
        stream_id = uuid.uuid4().hex
        _stream_store[stream_id] = {
            "chunks":  extra_chunks,
            "created": time.time(),
        }
        logger.info("Streaming session %s : %d chunks supplémentaires", stream_id, len(extra_chunks))

    return JSONResponse(status_code=202, content=_build_response(
        cid, received_bytes, duration_ms, encoding, sr, channels,
        first_chunk, intent="llm_response", answer=answer_text,
        stream_id=stream_id, total_chunks=len(chunks),
    ))


def _build_response(
    cid: str, received_bytes: int, duration_ms: int,
    encoding: str, sr: int, channels: int,
    out_pcm: bytes, intent: str, answer: str,
    stream_id: str | None = None,
    total_chunks: int = 1,
) -> dict:
    resp: dict = {
        "status":         "accepted",
        "api_version":    "v2",
        "correlation_id": cid,
        "received_bytes": received_bytes,
        "duration_ms":    duration_ms,
        "encoding":       encoding,
        "sample_rate_hz": FIRMWARE_SR,
        "channels":       channels,
        "audio_base64":   base64.b64encode(out_pcm).decode(),
        "intent":         intent,
        "answer":         answer,
        "chunk_index":    0,
        "total_chunks":   total_chunks,
        "has_more":       stream_id is not None,
    }
    if stream_id:
        resp["stream_id"] = stream_id
    return resp


@app.get("/edge/stream/{stream_id}/{chunk_idx}")
async def get_stream_chunk(stream_id: str, chunk_idx: int):
    """Retourne le chunk audio n°chunk_idx d'une session de streaming TTS."""
    session = _stream_store.get(stream_id)
    if session is None:
        raise HTTPException(status_code=404, detail="stream_id inconnu ou expiré")

    chunks: list[bytes] = session["chunks"]
    # chunk_idx ici est relatif aux chunks EXTRA (index 1+ dans la liste globale)
    # On normalise : le firmware demande 1, 2, 3 … ; on soustrait 1 pour l'index interne.
    internal_idx = chunk_idx - 1
    if internal_idx < 0 or internal_idx >= len(chunks):
        raise HTTPException(status_code=404, detail=f"chunk {chunk_idx} introuvable")

    pcm = chunks[internal_idx]
    has_more = internal_idx < len(chunks) - 1
    logger.info("Stream %s chunk %d/%d has_more=%s (%d bytes)",
                stream_id, chunk_idx, len(chunks), has_more, len(pcm))

    # Nettoyage si dernier chunk consommé
    if not has_more:
        _stream_store.pop(stream_id, None)
        logger.info("Stream %s terminé — session supprimée", stream_id)

    return JSONResponse(content={
        "audio_base64": base64.b64encode(pcm).decode(),
        "chunk_index":  chunk_idx,
        "total_chunks": len(chunks) + 1,  # +1 pour le premier chunk dans la réponse POST
        "has_more":     has_more,
    })


# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else SERVER_PORT
    logger.info("Démarrage HA bridge sur le port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
