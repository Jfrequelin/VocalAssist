"""Proxy HTTP Leon-compatible vers un backend LLM OpenAI-compatible.

Reçoit POST /api/query {"query": "..."} et retourne {"answer": "..."}.
Compatible avec GitHub Models, Ollama, OpenAI, et tout endpoint OpenAI-compatible.
Supporte le tool calling (météo, recherche web, radio) via llm_tools.py.

Variables d'environnement requises:
  LLM_PROXY_ENDPOINT     URL de base de l'API (ex: https://models.inference.ai.azure.com)
  LLM_PROXY_API_KEY      Clé API ou token (ex: GITHUB_TOKEN)
  LLM_PROXY_MODEL        Nom du modèle (ex: gpt-4o-mini, qwen2.5:3b)

Variables optionnelles:
  LLM_PROXY_SYSTEM_PROMPT   Prompt système (défaut: assistant vocal français)
  LLM_PROXY_MAX_TOKENS      Nombre max de tokens en réponse (défaut: 300)
  LLM_PROXY_TEMPERATURE     Température du modèle (défaut: 0.7)
  LLM_PROXY_TOOLS_ENABLED   Active les outils météo/search/radio (défaut: true)
  LLM_PROXY_MAX_TOOL_CALLS  Nombre max de tool calls par requête (défaut: 3)
  LLM_PROXY_HOST            Interface d'écoute (défaut: 0.0.0.0)
  LLM_PROXY_PORT            Port d'écoute (défaut: 1337)
  BRAVE_SEARCH_API_KEY      Clé Brave Search (optionnel, fallback DDG sans clé)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, cast
from urllib import error, request as urllib_request

sys.path.insert(0, str(Path(__file__).parent))
from llm_tools import TOOL_DEFINITIONS, call_tool  # noqa: E402

_DEFAULT_SYSTEM_PROMPT = (
    "Tu es Leon, un assistant vocal personnel open-source. "
    "Donne des réponses courtes, directes et en français. "
    "Quand on te demande la météo, une information récente ou une radio, "
    "utilise les outils disponibles. "
    "Réponse finale: maximum 3 phrases courtes. Pas de markdown. Pas de liste à puces."
)


def _read_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default or "").strip()
    if not value:
        raise RuntimeError(f"Variable d'environnement requise manquante: {name}")
    return value


def _post_llm(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    url = f"{endpoint.rstrip('/')}/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Erreur réseau LLM: {exc}") from exc
    try:
        return cast(dict[str, Any], json.loads(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Réponse LLM invalide (JSON): {raw[:200]}") from exc


def _extract_answer(body: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    choices = body.get("choices") or []
    if not choices:
        return None, []
    first = choices[0]
    if not isinstance(first, dict):
        return None, []
    message = first.get("message") or {}
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []
    text = content.strip() if isinstance(content, str) and content.strip() else None
    return text, [t for t in tool_calls if isinstance(t, dict)]


def call_llm_with_tools(
    endpoint: str,
    api_key: str,
    model: str,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    tools_enabled: bool,
    max_tool_calls: int,
    timeout: float = 30.0,
) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools_enabled:
        payload["tools"] = TOOL_DEFINITIONS
        payload["tool_choice"] = "auto"

    tool_calls_done = 0

    while True:
        body = _post_llm(endpoint, api_key, payload, timeout)
        content, tool_calls = _extract_answer(body)

        if not tool_calls:
            if content:
                return content
            raise RuntimeError(f"Format de réponse LLM inattendu: {json.dumps(body)[:200]}")

        if tool_calls_done >= max_tool_calls:
            return content or "Désolé, je n'ai pas pu obtenir la réponse."

        choices = body.get("choices") or []
        assistant_msg = (choices[0].get("message") or {}) if choices else {}
        messages.append({"role": "assistant", **{k: v for k, v in assistant_msg.items() if k != "role"}})

        for tc in tool_calls:
            tc_id = tc.get("id", "")
            fn = tc.get("function") or {}
            fn_name = fn.get("name", "")
            fn_args_raw = fn.get("arguments", "{}")
            try:
                fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
            except json.JSONDecodeError:
                fn_args = {}
            print(f"[llm-proxy] tool_call: {fn_name}({fn_args})", flush=True)
            result = call_tool(fn_name, fn_args)
            print(f"[llm-proxy] tool_result: {result[:120]}{'...' if len(result) > 120 else ''}", flush=True)
            messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

        tool_calls_done += 1
        payload["messages"] = messages
        payload["tool_choice"] = "none" if tool_calls_done >= max_tool_calls else "auto"


class LLMProxyHandler(BaseHTTPRequestHandler):
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT
    max_tokens: int = 300
    temperature: float = 0.7
    tools_enabled: bool = True
    max_tool_calls: int = 3

    def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
        print(f"[llm-proxy] {fmt % args}", flush=True)

    def _send_json(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            cls = self.__class__
            self._send_json(200, {"status": "ok", "service": "llm-proxy", "model": cls.model, "tools": cls.tools_enabled})
            return
        self._send_json(404, {"status": "error", "reason": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/query":
            self._send_json(404, {"status": "error", "reason": "not_found"})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"status": "error", "reason": "invalid_json"})
            return
        payload_map = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
        query = str(payload_map.get("query", "")).strip()
        if not query:
            self._send_json(400, {"status": "error", "reason": "empty_query"})
            return
        cls = self.__class__
        try:
            answer = call_llm_with_tools(
                endpoint=cls.endpoint, api_key=cls.api_key, model=cls.model,
                user_message=query, system_prompt=cls.system_prompt,
                max_tokens=cls.max_tokens, temperature=cls.temperature,
                tools_enabled=cls.tools_enabled, max_tool_calls=cls.max_tool_calls,
            )
            self._send_json(200, {"answer": answer})
        except RuntimeError as exc:
            print(f"[llm-proxy] ERREUR: {exc}", flush=True)
            self._send_json(502, {"status": "error", "reason": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Proxy LLM compatible Leon avec tool calling")
    parser.add_argument("--host", default=os.getenv("LLM_PROXY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LLM_PROXY_PORT", "1337")))
    args = parser.parse_args()

    try:
        endpoint = _read_env("LLM_PROXY_ENDPOINT")
        api_key = _read_env("LLM_PROXY_API_KEY")
        model = _read_env("LLM_PROXY_MODEL")
    except RuntimeError as exc:
        print(f"[llm-proxy] CONFIGURATION MANQUANTE: {exc}", flush=True)
        raise SystemExit(1) from exc

    system_prompt = os.getenv("LLM_PROXY_SYSTEM_PROMPT", "").strip() or _DEFAULT_SYSTEM_PROMPT
    max_tokens = int(os.getenv("LLM_PROXY_MAX_TOKENS", "300"))
    temperature = float(os.getenv("LLM_PROXY_TEMPERATURE", "0.7"))
    tools_enabled = os.getenv("LLM_PROXY_TOOLS_ENABLED", "true").strip().lower() not in {"false", "0", "no"}
    max_tool_calls = int(os.getenv("LLM_PROXY_MAX_TOOL_CALLS", "3"))

    LLMProxyHandler.endpoint = endpoint
    LLMProxyHandler.api_key = api_key
    LLMProxyHandler.model = model
    LLMProxyHandler.system_prompt = system_prompt
    LLMProxyHandler.max_tokens = max_tokens
    LLMProxyHandler.temperature = temperature
    LLMProxyHandler.tools_enabled = tools_enabled
    LLMProxyHandler.max_tool_calls = max_tool_calls

    tools_str = "activés (météo, recherche, radio)" if tools_enabled else "désactivés"
    print(f"[llm-proxy] Endpoint: {endpoint}", flush=True)
    print(f"[llm-proxy] Model:    {model}", flush=True)
    print(f"[llm-proxy] Outils:   {tools_str}", flush=True)
    print(f"[llm-proxy] Listening on {args.host}:{args.port}", flush=True)

    server = HTTPServer((args.host, args.port), LLMProxyHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
