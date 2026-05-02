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
python scripts/run_base_testbench.py
```

## Base de test firmware (peripheriques abstraits)

Une base de test desktop est disponible pour valider le format d'echange
avec l'assistant (`POST /edge/audio`, contrat v2), en utilisant des
peripheriques abstraits:

- micro desktop simule (entree clavier)
- haut-parleur desktop (sortie console)
- ecran mock/console pour les etats firmware

Commande:

```bash
python scripts/run_base_testbench.py
```

Exemple d'entree:

```text
nova quelle heure est-il
```

## Packaging operable (docker-compose)

Stack de demo reproductible:
- `assistant-backend` (endpoint `POST /edge/audio`, publie en local sur `http://127.0.0.1:18081`)
- `leon-mock` (endpoint `POST /api/query`)
- `ha-mock` (endpoints Home Assistant critiques)

Demarrage:

```bash
docker compose up -d --build
docker compose ps
```

Smoke-test post-deploiement:

```bash
./scripts/smoke-test.sh
```

Runbook d'installation/debug:
- `docs/runbook-docker-compose.md`

Arret:

```bash
docker compose down
```

## Fallback Leon dans la boucle

Le prototype utilise d'abord les intents locaux. Si la demande est inconnue, il tente un fallback vers Leon via HTTP.

Variables requises (obligatoires):

- `LEON_API_URL` (ex: `http://localhost:1337`)
- `LEON_API_ENDPOINT` (ex: `/api/query`)
- `LEON_TIMEOUT_SECONDS` (ex: `5`)
- `LEON_RETRY_ATTEMPTS` (ex: `1`)
- `LEON_RETRY_BACKOFF_SECONDS` (ex: `0`)

Exemple:

```bash
LEON_API_URL=http://localhost:1337 \
LEON_API_ENDPOINT=/api/query \
LEON_TIMEOUT_SECONDS=5 \
LEON_RETRY_ATTEMPTS=1 \
LEON_RETRY_BACKOFF_SECONDS=0 \
python3 main.py --mode prototype
```

Si une variable Leon requise est absente ou invalide, le client Leon remonte une erreur explicite de configuration.

## Providers externes du MVP

Les intents `lumiere`, `scene`, `temperature`, `meteo` et `musique` peuvent utiliser des providers HTTP externes. Sans configuration, le prototype conserve son fallback local simule.

Home Assistant pour la lumiere:

- `HOME_ASSISTANT_URL`
- `HOME_ASSISTANT_TOKEN`
- `HOME_ASSISTANT_LIGHT_DEFAULT_ENTITY` ou une ou plusieurs variables par piece:
	- `HOME_ASSISTANT_LIGHT_SALON`
	- `HOME_ASSISTANT_LIGHT_CHAMBRE`
	- `HOME_ASSISTANT_LIGHT_CUISINE`
	- `HOME_ASSISTANT_LIGHT_BUREAU`
- `HOME_ASSISTANT_TIMEOUT_SECONDS` (optionnelle)

	Home Assistant pour les scenes:

	- `HOME_ASSISTANT_SCENE_SOIREE`
	- `HOME_ASSISTANT_SCENE_TRAVAIL`
	- `HOME_ASSISTANT_SCENE_NUIT`
	- `HOME_ASSISTANT_SCENE_FILM`
	- `HOME_ASSISTANT_SCENE_DETENTE`

	Home Assistant pour le thermostat:

	- `HOME_ASSISTANT_CLIMATE_ENTITY`
	- `HOME_ASSISTANT_CLIMATE_MIN_TEMP` (optionnelle, defaut `10`)
	- `HOME_ASSISTANT_CLIMATE_MAX_TEMP` (optionnelle, defaut `30`)

Provider meteo:

- `WEATHER_PROVIDER_URL_TEMPLATE` avec placeholder `{city}`
- `WEATHER_PROVIDER_TIMEOUT_SECONDS` (optionnelle)

Provider musique/radio:

- `MUSIC_PROVIDER_URL`
- `MUSIC_PROVIDER_AUTH_TOKEN` (optionnelle)
- `MUSIC_PROVIDER_TIMEOUT_SECONDS` (optionnelle)

Exemple:

```bash
HOME_ASSISTANT_URL=http://homeassistant.local:8123 \
HOME_ASSISTANT_TOKEN=xxxx \
HOME_ASSISTANT_LIGHT_SALON=light.salon \
HOME_ASSISTANT_SCENE_SOIREE=scene.soiree \
HOME_ASSISTANT_CLIMATE_ENTITY=climate.salon \
WEATHER_PROVIDER_URL_TEMPLATE='https://weather.example/api/current?city={city}' \
MUSIC_PROVIDER_URL=https://music.example/api/playback \
python3 main.py --mode prototype
```

## Structure

- `main.py`: point d'entree.
- `src/assistant/`: code applicatif.
- `data/simulation_scenarios.json`: jeux de tests de simulation.
- `tests/`: tests unitaires.
- `docs/README.md`: index documentaire canonique.

## Prochaines evolutions

- Ajouter des providers supplementaires (agenda, scene domotique, capteurs).
- Renforcer l'observabilite et les tests de bout en bout sur services externes.
