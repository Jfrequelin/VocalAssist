# Runbook Docker Compose - AssistantVocal

## Objectif
Deployer une stack de demo reproductible en moins de 45 minutes:
- assistant backend (`/edge/audio`)
- Leon mock (`/api/query`)
- Home Assistant mock (services light/scene/climate)

## Prerequis
- Docker 24+
- Docker Compose plugin 2+
- `curl`
- `python3`

Verification rapide:

```bash
docker --version
docker compose version
curl --version
python3 --version
```

## Demarrage standard
Depuis la racine du projet:

```bash
docker compose up -d --build
docker compose ps
```

Services exposes:
- Assistant backend: `http://127.0.0.1:18081/edge/audio`
- Leon mock: acces interne Compose (`http://leon-mock:1337`)
- Home Assistant mock: acces interne Compose (`http://ha-mock:8123`)

## Smoke-test post-deploiement

```bash
./scripts/smoke-test.sh
```

Le script valide:
- readiness des 3 services
- appel critique `POST /edge/audio`
- fallback unknown-intent vers Leon/fallback propre
- endpoint critique Leon mock
- endpoint critique Home Assistant mock

Option cleanup:

```bash
./scripts/smoke-test.sh --teardown
```

## Commandes de debug

Voir les logs:

```bash
docker compose logs --tail=200 assistant-backend
docker compose logs --tail=200 leon-mock
docker compose logs --tail=200 ha-mock
```

Verifier un endpoint manuellement:

```bash
docker compose exec -T assistant-backend python -c "import urllib.request; print(urllib.request.urlopen('http://leon-mock:1337/health').read().decode())"
docker compose exec -T assistant-backend python -c "import urllib.request; print(urllib.request.urlopen('http://ha-mock:8123/health').read().decode())"
```

Test manuel `/edge/audio`:

```bash
AUDIO=$(printf 'allume la lumiere du salon' | base64 -w0)
curl -sS -X POST http://127.0.0.1:18081/edge/audio \
  -H 'Content-Type: application/json' \
  -d "{\"correlation_id\":\"manual-1\",\"device_id\":\"edge-manual\",\"timestamp_ms\":1730000000000,\"sample_rate_hz\":16000,\"channels\":1,\"encoding\":\"pcm_s16le\",\"audio_base64\":\"$AUDIO\"}"
```

## Arret

```bash
docker compose down
```

Arret + nettoyage volumes:

```bash
docker compose down -v
```

## Incidents frequents

### Port deja pris (18081)
- Cause: autre service local deja actif.
- Action: arreter le service conflictuel ou modifier les ports dans `docker-compose.yml`.

### Smoke-test echoue sur readiness
- Action 1: `docker compose ps`
- Action 2: `docker compose logs assistant-backend leon-mock ha-mock`
- Action 3: verifier Docker Desktop/daemon en execution.

### Reponse fallback-error sur unknown-intent
- Ce comportement est acceptable dans le smoke-test (degradation propre).
- Verifier `LEON_*` dans `docker-compose.yml` si vous attendez une reponse Leon.
