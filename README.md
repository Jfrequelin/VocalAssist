# Assistant Vocal - Projet type Alexa

Ce projet avance en 3 phases:

1. Definition du produit et des fonctionnalites cibles.
2. Simulation de dialogues et de comportements metier.
3. Prototype local executable en terminal.

## Objectifs

- Concevoir un assistant vocal personnel orienté maison connectee.
- Tester rapidement les cas d'usage avec une simulation textuelle.
- Construire un prototype evolutif vers la voix reelle (STT/TTS).

## Lancement

Prerequis: Python 3.10+

```bash
python main.py --mode define
python main.py --mode simulate
python main.py --mode prototype
python main.py --mode prototype-voice
python -m unittest discover -s tests -p "test_*.py"
```

## Fallback Leon dans la boucle

Le prototype utilise d'abord les intents locaux. Si la demande est inconnue, il tente un fallback vers Leon via HTTP.

Variables optionnelles:

- `LEON_API_URL` (defaut: `http://localhost:1337`)
- `LEON_API_ENDPOINT` (defaut: `/api/query`)
- `LEON_TIMEOUT_SECONDS` (defaut: `5`)

Exemple:

```bash
LEON_API_URL=http://localhost:1337 LEON_API_ENDPOINT=/api/query python3 main.py --mode prototype
```

## Structure

- `main.py`: point d'entree.
- `src/assistant/`: code applicatif.
- `data/simulation_scenarios.json`: jeux de tests de simulation.
- `tests/`: tests unitaires.
- `docs/README.md`: index documentaire canonique.

## Prochaines evolutions

- Ajouter reconnaissance vocale (Whisper/Vosk).
- Ajouter synthese vocale (Coqui TTS/pyttsx3).
- Connecter des APIs reelles (meteo, calendrier, domotique).
