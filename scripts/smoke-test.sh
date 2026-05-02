#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEARDOWN=false
if [[ "${1:-}" == "--teardown" ]]; then
  TEARDOWN=true
fi

wait_http() {
  local name="$1"
  local url="$2"
  local max_tries="${3:-60}"
  local i=1
  while [[ "$i" -le "$max_tries" ]]; do
    if curl -sS "$url" >/dev/null 2>&1; then
      echo "[smoke] $name OK"
      return 0
    fi
    i=$((i + 1))
    if [[ "$i" -le "$max_tries" ]]; then
      echo "[smoke] waiting $name ($i/$max_tries)"
    fi
    sleep 1
  done
  echo "[smoke] ERROR: $name not ready: $url" >&2
  return 1
}

wait_internal_http() {
  local name="$1"
  local url="$2"
  local max_tries="${3:-60}"
  local i=1
  while [[ "$i" -le "$max_tries" ]]; do
    if docker compose exec -T assistant-backend python -c "import urllib.request; urllib.request.urlopen('$url', timeout=2)" >/dev/null 2>&1; then
      echo "[smoke] $name OK (internal)"
      return 0
    fi
    i=$((i + 1))
    if [[ "$i" -le "$max_tries" ]]; then
      echo "[smoke] waiting $name internal ($i/$max_tries)"
    fi
    sleep 1
  done
  echo "[smoke] ERROR: $name not ready (internal): $url" >&2
  return 1
}

docker compose up -d --build

wait_http "assistant-backend" "http://127.0.0.1:18081" 40
wait_internal_http "leon-mock" "http://leon-mock:1337/health" 40
wait_internal_http "ha-mock" "http://ha-mock:8123/health" 40

# Backend has no GET endpoint by design, so we validate readiness with a valid POST request.
CID_1="smoke-light-$(date +%s)"
AUDIO_1="$(printf 'allume la lumiere du salon' | base64 -w0)"
REQ_1="$(cat <<JSON
{
  "correlation_id": "$CID_1",
  "device_id": "edge-smoke",
  "timestamp_ms": 1730000000000,
  "sample_rate_hz": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "audio_base64": "$AUDIO_1"
}
JSON
)"

RESP_1="$(curl -fsS -X POST "http://127.0.0.1:18081/edge/audio" -H "Content-Type: application/json" -d "$REQ_1")"

RESP_JSON="$RESP_1" python3 - <<'PY'
import json
import os
obj = json.loads(os.environ["RESP_JSON"])
assert obj.get("status") == "accepted", obj
assert obj.get("source") in {"local", "local-clarification", "leon", "fallback-error"}, obj
print("[smoke] edge/audio light request OK")
PY

CID_2="smoke-leon-$(date +%s)"
AUDIO_2="$(printf 'blorpt inconnu test leon' | base64 -w0)"
REQ_2="$(cat <<JSON
{
  "correlation_id": "$CID_2",
  "device_id": "edge-smoke",
  "timestamp_ms": 1730000001000,
  "sample_rate_hz": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "audio_base64": "$AUDIO_2"
}
JSON
)"

RESP_2="$(curl -fsS -X POST "http://127.0.0.1:18081/edge/audio" -H "Content-Type: application/json" -d "$REQ_2")"

RESP_JSON="$RESP_2" python3 - <<'PY'
import json
import os
obj = json.loads(os.environ["RESP_JSON"])
assert obj.get("status") == "accepted", obj
# Unknown command should either use Leon mock or fallback cleanly.
assert obj.get("source") in {"leon", "fallback-error", "local"}, obj
answer = str(obj.get("answer", ""))
assert answer.strip(), obj
print("[smoke] edge/audio unknown-intent request OK")
PY

# Critical dependency checks
docker compose exec -T assistant-backend python - <<'PY'
import json
import urllib.request

req_leon = urllib.request.Request(
  "http://leon-mock:1337/api/query",
  data=json.dumps({"query": "ping"}).encode("utf-8"),
  headers={"Content-Type": "application/json"},
  method="POST",
)
with urllib.request.urlopen(req_leon, timeout=5):
  pass

req_ha = urllib.request.Request(
  "http://ha-mock:8123/api/services/light/turn_on",
  data=json.dumps({"entity_id": "light.salon"}).encode("utf-8"),
  headers={"Content-Type": "application/json", "Authorization": "Bearer demo-token"},
  method="POST",
)
with urllib.request.urlopen(req_ha, timeout=5):
  pass

print("[smoke] internal critical dependencies OK")
PY

echo "[smoke] SUCCESS: critical endpoints are operational"

if [[ "$TEARDOWN" == "true" ]]; then
  docker compose down -v
  echo "[smoke] Stack stopped (--teardown)"
fi
