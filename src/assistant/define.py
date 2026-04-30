from __future__ import annotations


def render_project_definition() -> str:
    sections = [
        "=== Vision produit ===",
        "Assistant vocal personnel de type Alexa, priorite maison connectee et productivite quotidienne.",
        "",
        "=== Fonctionnalites MVP ===",
        "- Activation par mot cle (simulation: 'nova').",
        "- Comprendre des intentions simples (heure, date, meteo, musique, lumiere).",
        "- Reponses contextualisees et ton conversationnel.",
        "- Journal minimal des interactions.",
        "",
        "=== Architecture cible (etapes) ===",
        "1) Capture audio + detection mot cle.",
        "2) STT (speech-to-text).",
        "3) NLU/Intent parser.",
        "4) Orchestrateur des actions.",
        "5) TTS (text-to-speech).",
        "",
        "=== Criteres de succes ===",
        "- 80% des commandes de base reconnues en simulation.",
        "- Latence ressentie < 2s en prototype local.",
        "- Architecture modulaire prete pour APIs reelles.",
    ]
    return "\n".join(sections)
