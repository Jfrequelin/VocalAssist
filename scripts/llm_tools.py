"""Outils pour le proxy LLM — météo, recherche web, radio.

Chaque outil est une fonction Python appelée lors d'un tool_call LLM.
Toutes les APIs utilisées sont gratuites (pas de clé requise sauf Brave Search).

Variables d'environnement optionnelles:
  BRAVE_SEARCH_API_KEY   Clé Brave Search (https://brave.com/search/api/)
                         Sans clé: fallback DDG instant answers
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, parse, request as urllib_request

# ─── Définitions des outils pour l'API OpenAI ────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Obtenir la météo actuelle ou les prévisions pour une ville. "
                "Utilise cet outil quand l'utilisateur demande la météo, la température, "
                "s'il va pleuvoir, le vent, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Nom de la ville (ex: Paris, Lyon, Bordeaux)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Nombre de jours (1=aujourd'hui, 2=demain, jusqu'à 7)",
                        "default": 1,
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Rechercher des informations récentes sur internet. "
                "Utilise cet outil pour les actualités, les événements récents, "
                "les faits qui peuvent avoir changé depuis ta date de formation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche en français ou en anglais",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Nombre de résultats à retourner (défaut: 3, max: 5)",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_radio",
            "description": (
                "Trouver une station de radio par nom ou genre musical. "
                "Retourne le nom, la description et l'URL de streaming. "
                "Utilise cet outil quand l'utilisateur demande à écouter une radio "
                "ou de la musique d'un genre particulier."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nom ou genre de la station (ex: France Inter, jazz, classique, rock)",
                    },
                    "country": {
                        "type": "string",
                        "description": "Code pays ISO (ex: FR, US, GB). Défaut: FR",
                        "default": "FR",
                    },
                },
                "required": ["name"],
            },
        },
    },
]

# ─── Météo (open-meteo.com — gratuit, sans clé) ───────────────────────────────

_WMO_CODES: dict[int, str] = {
    0: "ciel dégagé", 1: "principalement dégagé", 2: "partiellement nuageux",
    3: "couvert", 45: "brouillard", 48: "brouillard givrant",
    51: "bruine légère", 53: "bruine modérée", 55: "bruine dense",
    61: "pluie faible", 63: "pluie modérée", 65: "pluie forte",
    71: "neige faible", 73: "neige modérée", 75: "neige forte",
    80: "averses faibles", 81: "averses modérées", 82: "averses violentes",
    95: "orage", 96: "orage avec grêle", 99: "orage avec forte grêle",
}


def _geocode(city: str) -> tuple[float, float, str]:
    """Retourne (latitude, longitude, nom_officiel)."""
    url = (
        "https://geocoding-api.open-meteo.com/v1/search?"
        + parse.urlencode({"name": city, "count": 1, "language": "fr", "format": "json"})
    )
    try:
        with urllib_request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Géocodage impossible pour '{city}': {exc}") from exc

    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"Ville '{city}' introuvable")
    r = results[0]
    return float(r["latitude"]), float(r["longitude"]), r.get("name", city)


def get_weather(city: str, days: int = 1) -> str:
    days = max(1, min(7, int(days)))
    try:
        lat, lon, city_name = _geocode(city)
    except RuntimeError as exc:
        return str(exc)

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "current_weather": "true",
        "timezone": "Europe/Paris",
        "forecast_days": days,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + parse.urlencode(params)
    try:
        with urllib_request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Erreur météo: {exc}"

    current = data.get("current_weather", {})
    daily = data.get("daily", {})
    dates: list[str] = daily.get("time", [])
    codes: list[int] = daily.get("weathercode", [])
    t_max: list[float] = daily.get("temperature_2m_max", [])
    t_min: list[float] = daily.get("temperature_2m_min", [])
    precip: list[float] = daily.get("precipitation_sum", [])
    wind: list[float] = daily.get("windspeed_10m_max", [])

    lines: list[str] = [f"Météo pour {city_name}:"]

    if current:
        cond = _WMO_CODES.get(int(current.get("weathercode", 0)), "")
        lines.append(
            f"Maintenant: {current.get('temperature', '?')}°C, "
            f"{cond}, vent {current.get('windspeed', '?')} km/h"
        )

    for i, date in enumerate(dates):
        if i >= days:
            break
        code = codes[i] if i < len(codes) else 0
        label = "Aujourd'hui" if i == 0 else ("Demain" if i == 1 else date)
        cond = _WMO_CODES.get(int(code), "")
        tmax = t_max[i] if i < len(t_max) else "?"
        tmin = t_min[i] if i < len(t_min) else "?"
        prc = precip[i] if i < len(precip) else 0
        w = wind[i] if i < len(wind) else "?"
        prc_str = f", {prc:.1f}mm de précipitations" if prc and float(prc) > 0.1 else ""
        lines.append(f"{label}: {tmin}°C / {tmax}°C, {cond}{prc_str}, vent max {w} km/h")

    return "\n".join(lines)


# ─── Recherche web ────────────────────────────────────────────────────────────

def search_web(query: str, count: int = 3) -> str:
    count = max(1, min(5, int(count)))
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()

    if brave_key:
        return _search_brave(query, count, brave_key)
    return _search_ddg(query)


def _search_brave(query: str, count: int, api_key: str) -> str:
    url = "https://api.search.brave.com/res/v1/web/search?" + parse.urlencode(
        {"q": query, "count": count, "search_lang": "fr", "ui_lang": "fr-FR"}
    )
    req = urllib_request.Request(
        url,
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    try:
        with urllib_request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Erreur recherche Brave: {exc}"

    results = (data.get("web") or {}).get("results") or []
    if not results:
        return f"Aucun résultat pour '{query}'"

    parts: list[str] = [f"Résultats de recherche pour: {query}"]
    for r in results[:count]:
        title = r.get("title", "")
        desc = r.get("description", "")
        parts.append(f"• {title}: {desc}")
    return "\n".join(parts)


def _search_ddg(query: str) -> str:
    """Fallback: DuckDuckGo instant answers (sans clé, résultats limités)."""
    url = "https://api.duckduckgo.com/?" + parse.urlencode(
        {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    )
    try:
        with urllib_request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Erreur recherche: {exc}"

    abstract = data.get("AbstractText", "").strip()
    answer = data.get("Answer", "").strip()
    related = data.get("RelatedTopics", [])

    parts: list[str] = []
    if answer:
        parts.append(f"Réponse directe: {answer}")
    if abstract:
        parts.append(f"Résumé: {abstract[:300]}")
    if not parts and related:
        for t in related[:3]:
            if isinstance(t, dict) and t.get("Text"):
                parts.append(f"• {t['Text'][:150]}")

    if not parts:
        return (
            f"Pas de résultat direct pour '{query}'. "
            "Pour des recherches complètes, configurez BRAVE_SEARCH_API_KEY."
        )
    return "\n".join(parts)


# ─── Radio (radio-browser.info — gratuit, sans clé) ──────────────────────────

def find_radio(name: str, country: str = "FR") -> str:
    country_upper = country.upper()
    params = {
        "name": name,
        "countrycode": country_upper,
        "limit": 5,
        "order": "votes",
        "reverse": "true",
        "hidebroken": "true",
    }
    url = "https://de1.api.radio-browser.info/json/stations/search?" + parse.urlencode(params)
    headers = {"User-Agent": "AssistantVocal/1.0"}

    try:
        req = urllib_request.Request(url, headers=headers)
        with urllib_request.urlopen(req, timeout=8) as r:
            stations: list[dict[str, Any]] = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Erreur radio-browser: {exc}"

    # Fallback sans filtre pays si aucun résultat
    if not stations and country_upper != "":
        params2 = {**params, "countrycode": ""}
        url2 = "https://de1.api.radio-browser.info/json/stations/search?" + parse.urlencode(params2)
        try:
            req2 = urllib_request.Request(url2, headers=headers)
            with urllib_request.urlopen(req2, timeout=8) as r:
                stations = json.loads(r.read())
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    if not stations:
        return f"Aucune station trouvée pour '{name}'"

    parts: list[str] = [f"Stations radio trouvées pour '{name}':"]
    for s in stations[:3]:
        sname = s.get("name", "?")
        tags = s.get("tags", "")
        url_stream = s.get("url_resolved") or s.get("url", "")
        bitrate = s.get("bitrate", "")
        br_str = f" ({bitrate}kbps)" if bitrate else ""
        tag_str = f" [{tags}]" if tags else ""
        parts.append(f"• {sname}{tag_str}{br_str}: {url_stream}")

    return "\n".join(parts)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Appelle l'outil correspondant et retourne le résultat sous forme de texte."""
    if name == "get_weather":
        return get_weather(
            city=str(arguments.get("city", "")),
            days=int(arguments.get("days", 1)),
        )
    if name == "search_web":
        return search_web(
            query=str(arguments.get("query", "")),
            count=int(arguments.get("count", 3)),
        )
    if name == "find_radio":
        return find_radio(
            name=str(arguments.get("name", "")),
            country=str(arguments.get("country", "FR")),
        )
    return f"Outil inconnu: {name}"
