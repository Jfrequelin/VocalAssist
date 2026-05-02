# Base de Test Firmware (Peripheriques Abstraits)

Cette page decrit la base de test desktop qui simule un firmware edge et valide
le format d'echange avec l'assistant sur `POST /edge/audio` (contrat v2).

## Objectif

- Tester localement la boucle firmware -> assistant sans hardware reel.
- Garder un point d'entree simple pour validation rapide avant integration STM32.
- Reproduire l'echange de payloads avec traces exploitables en tests unitaires.
- Simuler une base complete (routing local, providers, fallback Leon) sur Linux.

## Composants

- Harness: `src/base/test_harness.py`
- Peripheriques abstraits: `src/base/peripherals.py`
- Script d'execution desktop: `scripts/run_base_testbench.py`
- Tests unitaires: `tests/test_base_test_harness.py`

## Peripheriques abstraits

Interfaces:
- `MicrophoneDevice`
- `SpeakerDevice`
- `ScreenDevice`

Implementations desktop/mock:
- `StdinMicrophoneAdapter`: simule le micro via l'entree clavier.
- `ConsoleSpeakerAdapter`: simule la restitution audio via la console.
- `MockScreenAdapter`: stocke les evenements d'ecran pour assertions.
- `ConsoleScreenAdapter`: affiche l'etat firmware en console.
- `TkScreenAdapter`: affiche l'etat firmware dans une fenetre Tk locale.

## Lancer la base de test

Prerequis:
- backend edge joignable (par defaut `http://127.0.0.1:8081`)
- environnement Python du projet actif

Commande:

```bash
python main.py --mode testbench
# ou
python scripts/run_base_testbench.py
```

Modes de simulation:

- `ASSISTANT_TESTBENCH_TRANSPORT=local` (defaut): backend edge simule in-process
- `ASSISTANT_TESTBENCH_TRANSPORT=http`: appel HTTP vers backend externe
- `ASSISTANT_TESTBENCH_PERIPHERALS=auto` (defaut): systeme Linux si disponible, sinon mock
- `ASSISTANT_TESTBENCH_PERIPHERALS=system`: force systeme Linux (`arecord`, `spd-say`/`espeak`)
- `ASSISTANT_TESTBENCH_PERIPHERALS=mock`: force clavier + console
- `ASSISTANT_TESTBENCH_SCREEN=auto`: fenetre Tk si disponible, sinon console
- `ASSISTANT_TESTBENCH_SCREEN=tk`: force une fenetre Tk
- `ASSISTANT_TESTBENCH_SCREEN=console`: force l'affichage console

Commandes de controle pendant la session:

- `/help`
- `/status`
- `/mute`
- `/unmute`

Indicateurs runtime exposes:

- latence par tour (ms)
- intent/source de la reponse backend
- compteurs cumules (turns, sent, rejected, backend_errors, avg_latency_ms)

Exemple d'entree micro simulee:

```text
nova quelle heure est-il
```

Arret:
- saisir `quit`, `exit` ou `stop`

## Variables d'environnement utiles

- `EDGE_BACKEND_URL`
- `EDGE_DEVICE_ID`
- `EDGE_WAKE_WORD`
- `EDGE_SAMPLE_RATE_HZ`
- `EDGE_CHANNELS`
- `EDGE_ENCODING`
- `EDGE_MIN_VOICE_CHARS`
- `EDGE_TIMEOUT_SECONDS`
- `EDGE_RETRY_ATTEMPTS`
- `EDGE_RETRY_BACKOFF_SECONDS`
- `ASSISTANT_TESTBENCH_TRANSPORT`
- `ASSISTANT_TESTBENCH_PERIPHERALS`
- `ASSISTANT_TESTBENCH_SCREEN`
- `TESTBENCH_MIC_SECONDS`

## Couverture de test

`tests/test_base_test_harness.py` valide notamment:
- enregistrement du format d'echange v2 (requete/reponse)
- rejet sans wake word
- propagation d'un rejet backend
- integration des peripheriques abstraits (speaker/screen)
