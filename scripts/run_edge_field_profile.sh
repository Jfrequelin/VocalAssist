#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Erreur: interpreteur Python introuvable: ${PYTHON_BIN}" >&2
  echo "Active ou cree d'abord l'environnement virtuel (.venv)." >&2
  exit 1
fi

MODE="${1:-local}"
if [[ "${MODE}" != "local" && "${MODE}" != "http" ]]; then
  echo "Usage: $0 [local|http]" >&2
  echo "  local: backend in-process (sans service externe)" >&2
  echo "  http:  backend via EDGE_BACKEND_URL (defaut http://127.0.0.1:18081)" >&2
  exit 1
fi

if [[ "${MODE}" == "http" ]]; then
  export EDGE_BACKEND_URL="${EDGE_BACKEND_URL:-http://127.0.0.1:18081}"
fi

export ASSISTANT_TESTBENCH_TRANSPORT="${ASSISTANT_TESTBENCH_TRANSPORT:-${MODE}}"
export ASSISTANT_TESTBENCH_PERIPHERALS="${ASSISTANT_TESTBENCH_PERIPHERALS:-system}"
export ASSISTANT_TESTBENCH_SCREEN="${ASSISTANT_TESTBENCH_SCREEN:-console}"

if [[ -z "${ASSISTANT_TESTBENCH_CAPTURE_DEVICE:-}" ]]; then
  if arecord -L 2>/dev/null | grep -qx "pulse"; then
    export ASSISTANT_TESTBENCH_CAPTURE_DEVICE="pulse"
  else
    export ASSISTANT_TESTBENCH_CAPTURE_DEVICE="hw:CARD=Generic_1,DEV=0"
  fi
fi

export ASSISTANT_TESTBENCH_PLAYBACK_DEVICE="${ASSISTANT_TESTBENCH_PLAYBACK_DEVICE:-default}"

if [[ -z "${ASSISTANT_TESTBENCH_REPLAY_CAPTURE:-}" ]]; then
  if [[ "${ASSISTANT_TESTBENCH_CAPTURE_DEVICE}" == "pulse" ]]; then
    export ASSISTANT_TESTBENCH_REPLAY_CAPTURE="false"
  else
    export ASSISTANT_TESTBENCH_REPLAY_CAPTURE="true"
  fi
fi

if [[ -z "${ASSISTANT_STT_MIN_AVG_AMPLITUDE:-}" ]]; then
  if [[ "${ASSISTANT_TESTBENCH_CAPTURE_DEVICE}" == "pulse" ]]; then
    export ASSISTANT_STT_MIN_AVG_AMPLITUDE="40"
  else
    export ASSISTANT_STT_MIN_AVG_AMPLITUDE="180"
  fi
fi

export ASSISTANT_STT_NO_SPEECH_THRESHOLD="${ASSISTANT_STT_NO_SPEECH_THRESHOLD:-0.6}"

export ASSISTANT_TESTBENCH_PHRASE_MODE="${ASSISTANT_TESTBENCH_PHRASE_MODE:-true}"
export ASSISTANT_TESTBENCH_MAX_CAPTURE_SECONDS="${ASSISTANT_TESTBENCH_MAX_CAPTURE_SECONDS:-10}"
export ASSISTANT_TESTBENCH_END_SILENCE_SECONDS="${ASSISTANT_TESTBENCH_END_SILENCE_SECONDS:-1.0}"
export ASSISTANT_TESTBENCH_VAD_CHUNK_SECONDS="${ASSISTANT_TESTBENCH_VAD_CHUNK_SECONDS:-0.2}"
if [[ -z "${ASSISTANT_TESTBENCH_VAD_START_THRESHOLD:-}" ]]; then
  if [[ "${ASSISTANT_TESTBENCH_CAPTURE_DEVICE}" == "pulse" ]]; then
    export ASSISTANT_TESTBENCH_VAD_START_THRESHOLD="60"
    export ASSISTANT_TESTBENCH_VAD_SILENCE_THRESHOLD="30"
  else
    export ASSISTANT_TESTBENCH_VAD_START_THRESHOLD="120"
    export ASSISTANT_TESTBENCH_VAD_SILENCE_THRESHOLD="80"
  fi
fi

export TESTBENCH_MIC_SECONDS="${TESTBENCH_MIC_SECONDS:-3}"
export ASSISTANT_TESTBENCH_SILENCE_WAIT_SECONDS="${ASSISTANT_TESTBENCH_SILENCE_WAIT_SECONDS:-5}"

echo "=== Edge field profile ==="
echo "transport=${ASSISTANT_TESTBENCH_TRANSPORT}"
echo "peripherals=${ASSISTANT_TESTBENCH_PERIPHERALS}"
echo "screen=${ASSISTANT_TESTBENCH_SCREEN}"
echo "capture_device=${ASSISTANT_TESTBENCH_CAPTURE_DEVICE}"
echo "playback_device=${ASSISTANT_TESTBENCH_PLAYBACK_DEVICE}"
echo "stt_min_avg_amplitude=${ASSISTANT_STT_MIN_AVG_AMPLITUDE}"
echo "stt_no_speech_threshold=${ASSISTANT_STT_NO_SPEECH_THRESHOLD}"
echo "phrase_mode=${ASSISTANT_TESTBENCH_PHRASE_MODE}"
echo "max_capture_seconds=${ASSISTANT_TESTBENCH_MAX_CAPTURE_SECONDS}"
echo "end_silence_seconds=${ASSISTANT_TESTBENCH_END_SILENCE_SECONDS}"
echo "vad_start_threshold=${ASSISTANT_TESTBENCH_VAD_START_THRESHOLD}"
echo "vad_silence_threshold=${ASSISTANT_TESTBENCH_VAD_SILENCE_THRESHOLD}"
if [[ "${MODE}" == "http" ]]; then
  echo "edge_backend_url=${EDGE_BACKEND_URL}"
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" main.py --mode testbench