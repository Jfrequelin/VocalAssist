"""
Outil : contrôle Home Assistant via son API REST.

Variables d'environnement requises :
  HA_URL    URL de Home Assistant  (ex: http://homeassistant.local:8123)
  HA_TOKEN  Long-lived access token

Pour activer : déposer ce fichier dans scripts/tools/ et redémarrer le bridge.
Pour désactiver : retirer le fichier (ou le renommer en _ha_control.py.disabled).
"""

from __future__ import annotations

import os
import requests as _req

# Injecté par le loader : _registry et tool
# (disponibles dans le namespace du module lors de l'exécution)

_HA_URL   = os.getenv("HA_URL",   "http://homeassistant.local:8123").rstrip("/")
_HA_TOKEN = os.getenv("HA_TOKEN", "")


def _ha_headers() -> dict:
    return {
        "Authorization": f"Bearer {_HA_TOKEN}",
        "Content-Type": "application/json",
    }


def _ha_available() -> bool:
    return bool(_HA_TOKEN)


@tool(
    description="Allume ou éteint un appareil domotique (lumière, prise, etc.).",
    params={
        "entity_id": {
            "type": "string",
            "description": "Identifiant Home Assistant de l'entité (ex: light.salon, switch.cuisine)",
        },
        "action": {
            "type": "string",
            "description": "Action à effectuer : 'on' pour allumer, 'off' pour éteindre, 'toggle' pour basculer",
        },
    },
    required=["entity_id", "action"],
)
def control_device(entity_id: str, action: str) -> str:
    if not _ha_available():
        return "Home Assistant non configuré (HA_TOKEN manquant)."
    action = action.strip().lower()
    if action not in ("on", "off", "toggle"):
        return f"Action inconnue : {action!r}. Utiliser 'on', 'off' ou 'toggle'."
    domain = entity_id.split(".")[0]
    service = f"turn_{action}" if action != "toggle" else "toggle"
    url = f"{_HA_URL}/api/services/{domain}/{service}"
    try:
        r = _req.post(url, headers=_ha_headers(), json={"entity_id": entity_id}, timeout=5)
        r.raise_for_status()
        return f"{entity_id} : {action} effectué."
    except Exception as exc:
        return f"Erreur Home Assistant : {exc}"


@tool(
    description="Retourne l'état actuel d'un appareil domotique.",
    params={
        "entity_id": {
            "type": "string",
            "description": "Identifiant Home Assistant de l'entité (ex: light.salon, sensor.temperature)",
        },
    },
    required=["entity_id"],
)
def get_device_state(entity_id: str) -> str:
    if not _ha_available():
        return "Home Assistant non configuré (HA_TOKEN manquant)."
    url = f"{_HA_URL}/api/states/{entity_id}"
    try:
        r = _req.get(url, headers=_ha_headers(), timeout=5)
        if r.status_code == 404:
            return f"Entité {entity_id!r} introuvable."
        r.raise_for_status()
        data = r.json()
        state = data.get("state", "inconnu")
        attrs = data.get("attributes", {})
        friendly = attrs.get("friendly_name", entity_id)
        # Détails utiles selon le type
        extra = ""
        if "brightness" in attrs:
            pct = int(attrs["brightness"] / 255 * 100)
            extra = f", luminosité {pct}%"
        elif "temperature" in attrs:
            extra = f", {attrs['temperature']}°C"
        elif "unit_of_measurement" in attrs:
            extra = f" {attrs['unit_of_measurement']}"
        return f"{friendly} : {state}{extra}."
    except Exception as exc:
        return f"Erreur Home Assistant : {exc}"
