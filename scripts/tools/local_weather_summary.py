"""
Outil : résumé météo locale via Open-Meteo.

Variables d'environnement optionnelles :
  LOCATION_LAT   Latitude (défaut: 48.8566)
  LOCATION_LON   Longitude (défaut: 2.3522)
  LOCATION_NAME  Nom du lieu (défaut: Paris)
"""

from __future__ import annotations

import os
import requests as _req

_LOCATION_LAT = float(os.getenv("LOCATION_LAT", "48.8566"))
_LOCATION_LON = float(os.getenv("LOCATION_LON", "2.3522"))
_LOCATION_NAME = os.getenv("LOCATION_NAME", "Paris")

_WMO = {
    0: "ciel degage",
    1: "principalement degage",
    2: "partiellement nuageux",
    3: "couvert",
    45: "brouillard",
    48: "brouillard givrant",
    51: "bruine legere",
    53: "bruine moderee",
    55: "bruine dense",
    61: "pluie legere",
    63: "pluie moderee",
    65: "pluie forte",
    71: "neige legere",
    73: "neige moderee",
    75: "neige forte",
    80: "averses legeres",
    81: "averses moderees",
    82: "averses fortes",
    95: "orage",
    96: "orage avec grele",
    99: "orage violent avec grele",
}


@tool(description="Retourne un resume concis de la meteo locale actuelle et du jour.")
def get_local_weather_summary() -> str:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={_LOCATION_LAT}&longitude={_LOCATION_LON}"
        "&current=temperature_2m,apparent_temperature,weathercode,windspeed_10m,is_day"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&timezone=auto"
    )

    try:
        r = _req.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        return f"Meteo indisponible pour {_LOCATION_NAME}: {exc}."

    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    felt = current.get("apparent_temperature")
    code = int(current.get("weathercode", -1))
    wind = current.get("windspeed_10m")

    tmax = None
    tmin = None
    rain_prob = None
    if daily:
        max_list = daily.get("temperature_2m_max") or []
        min_list = daily.get("temperature_2m_min") or []
        rain_list = daily.get("precipitation_probability_max") or []
        if max_list:
            tmax = max_list[0]
        if min_list:
            tmin = min_list[0]
        if rain_list:
            rain_prob = rain_list[0]

    sky = _WMO.get(code, "conditions variables")

    parts = [f"A {_LOCATION_NAME}, {sky}"]
    if temp is not None:
        parts.append(f"{temp} degres")
    if felt is not None:
        parts.append(f"ressenti {felt} degres")
    if wind is not None:
        parts.append(f"vent {wind} kilometres heure")

    line1 = ", ".join(parts) + "."

    day_parts = []
    if tmin is not None and tmax is not None:
        day_parts.append(f"Aujourd hui: min {tmin} degres, max {tmax} degres")
    if rain_prob is not None:
        day_parts.append(f"pluie probable a {rain_prob} pour cent")

    if day_parts:
        return line1 + " " + ", ".join(day_parts) + "."
    return line1
