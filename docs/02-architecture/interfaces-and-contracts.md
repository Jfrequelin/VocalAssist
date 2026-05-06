# Interfaces et Contrats API

## Contrat Edge -> Serveur (commande vocale)

### Endpoint `POST /edge/audio` - Contrat v2 (migration PCM16LE)

Payload v2:

```json
{
	"correlation_id": "cid-123",
	"device_id": "edge-001",
	"timestamp_ms": 1730000000000,
	"sample_rate_hz": 16000,
	"channels": 1,
	"encoding": "pcm16le",
	"audio_base64": "..."
}
```

Encodages acceptes:
- `pcm16le`
- `pcm_s16le`

Compatibilite legacy (transitoire):
- `utf8`, `utf-8`, `text`
- active uniquement pour migration progressive du mode historique texte-proxy.

Flag de compatibilite:
- `EDGE_BACKEND_ALLOW_TEXT_PROXY=true|false`
- `true` (defaut): autorise temporairement le mode texte-proxy pour `pcm16le|pcm_s16le`.
- `false`: rejette ce mode transitoire avec `unsupported_encoding`.

Erreurs standardisees v2 (`status=error`):
- `invalid_json`
- `invalid_payload_type`
- `missing_fields:<...>`
- `invalid_correlation_id`
- `invalid_device_id`
- `invalid_sample_rate`
- `invalid_channels`
- `invalid_encoding`
- `invalid_audio_base64`
- `empty_audio`
- `unsupported_encoding`
- `invalid_pcm_frame`
- `invalid_audio_utf8`
- `empty_command`

Structure de reponse erreur:

```json
{
	"status": "error",
	"api_version": "v2",
	"reason": "invalid_pcm_frame"
}
```

Structure de reponse succes:

```json
{
	"status": "accepted",
	"api_version": "v2",
	"correlation_id": "cid-123",
	"received_bytes": 3200,
	"encoding": "pcm16le",
	"intent": "time",
	"source": "local",
	"answer": "Il est 14:03."
}
```

### Format canonique firmware <-> assistant

Le firmware edge doit converger vers une enveloppe unique pour tous les types de donnees:

```json
{
	"correlation_id": "uuid-ou-id-local",
	"device_id": "edge-001",
	"timestamp_ms": 1714600000000,
	"kind": "audio|image|text|variable|binary",
	"payload": {}
}
```

Contraintes:
- un seul format d'enveloppe quel que soit le peripherique source;
- un seul payload par type de donnees;
- encodage explicite dans le payload (`pcm16le`, `opus`, `png`, `jpeg`, `rgb565`, `utf8`, `json`, `raw`);
- transport JSON borne et serialisable cote firmware sans allocation dynamique non bornee.

Payloads canoniques recommandes:

#### `kind=audio`

```json
{
	"encoding": "pcm16le",
	"sample_rate_hz": 16000,
	"channels": 1,
	"data_base64": "..."
}
```

#### `kind=text`

```json
{
	"encoding": "utf8",
	"text": "quelle heure est-il"
}
```

#### `kind=image`

```json
{
	"encoding": "png",
	"width": 360,
	"height": 360,
	"data_base64": "..."
}
```

#### `kind=variable`

```json
{
	"name": "muted",
	"value_type": "bool",
	"value": true
}
```

#### `kind=binary`

```json
{
	"mime_type": "application/octet-stream",
	"data_base64": "..."
}
```

Compatibilite descendante:
- l'audio conserve un mapping explicite vers le contrat historique `EdgeAudioRequest`;
- l'assistant Python doit accepter a la fois l'ancien format audio et l'enveloppe canonique.

Champs minimaux:
- api_version
- device_id
- session_id
- correlation_id
- input (audio ou texte)
- metadata (langue, confidence)
- context (room, mode_degrade)

Champs recommandes avec le hardware cible:
- edge_status (muted, listening, speaking, error)
- battery (percent, charging)
- network (wifi_rssi, connected)
- ui_capabilities (screen=true, touch=true)

## Contrat Serveur -> Edge (reponse)

La meme enveloppe canonique peut etre reutilisee en retour quand le serveur transmet:
- du texte (`kind=text`) pour affichage ou TTS locale,
- une variable (`kind=variable`) pour muter/mettre a jour un etat,
- de l'audio (`kind=audio`) pour lecture locale,
- une image (`kind=image`) pour l'ecran rond.

Champs minimaux:
- source (local/leon/degrade)
- intent
- answer_text
- action optionnelle
- policy (retry/cache/confirmation)

Champs recommandes avec le hardware cible:
- ui_state (idle|listening|thinking|speaking|error|muted)
- ui_hint (notification courte pour ecran/tactile)

## Contrat lecture audio locale

Action `play_stream`:
- url
- codec
- buffer_ms
- retry_policy

Controles locaux obligatoires:
- stop
- pause
- resume
- volume +/-

Controles locaux rendus accessibles par le hardware:
- mute via bouton physique et tactile
- validation/annulation simple via tactile
- affichage statut local (audio/screen/network/battery)

## Contrat commandes parametrees

Exemple `play_podcast`:
- slots obligatoires: podcast_name, provider
- slots optionnels: episode_name, date, position
- etat: ready_to_execute | needs_clarification | not_found

## References materiel audio

- Datasheet ES8311 (codec audio): https://files.waveshare.com/wiki/common/ES8311.DS.pdf
- User Guide ES8311: https://files.waveshare.com/wiki/common/ES8311.user.Guide.pdf

---

## Protocole de communication complet v3 (base <-> serveur)

Objectif:
- protocole bidirectionnel temps reel;
- gestion de plusieurs bases simultanees;
- transport des evenements metier et systeme;
- transfert audio et image robuste;
- reprise sur incident reseau.

### 1. Transport

Canal principal (temps reel):
- `WebSocket TLS` sur `/v3/realtime`.
- 1 connexion active par base (`device_id`) et par session.

Canal de secours (fallback):
- HTTP `POST /v3/events` pour uplink quand WebSocket indisponible.
- HTTP `GET /v3/commands/poll?device_id=...` pour downlink degrade.

Regle de priorite:
- si WebSocket disponible: tout passe sur WebSocket;
- sinon fallback HTTP avec meme enveloppe de message.

### 2. Identification multi-bases

Champs obligatoires pour chaque message:
- `tenant_id`: partition logique (client, site, projet)
- `device_id`: identifiant unique base (ex: edge-001)
- `session_id`: session de dialogue active
- `message_id`: UUID unique message
- `correlation_id`: regroupe une transaction (capture -> NLU -> reponse)

Contraintes:
- unicite `(device_id, message_id)` sur 24h cote serveur;
- un `session_id` actif par device, rotation sur reboot/login;
- routage serveur par `(tenant_id, device_id)`.

Annonce a la connexion (obligatoire):
- juste apres ouverture du canal realtime, la base envoie `event_type=device.online`;
- ce message doit contenir `payload.capabilities` pour exposer ses capacites materielles/logicielles;
- le serveur utilise ces capacites pour router les commandes compatibles (audio/image/ui/touch).

### 3. Enveloppe canonique unique

Tous les messages (event, commande, ack, media chunk) utilisent la meme structure.

```json
{
	"api_version": "v3",
	"transport": "ws",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-2026-05-06-01",
	"message_id": "2c6d9f34-0c7b-4ef4-9ea8-fd2fd5a2c2f1",
	"correlation_id": "corr-1730000000123",
	"direction": "edge_to_server",
	"kind": "event",
	"event_type": "audio.capture.completed",
	"timestamp_ms": 1730000000123,
	"qos": "at_least_once",
	"requires_ack": true,
	"payload": {},
	"meta": {
		"trace_id": "trace-abc",
		"firmware_version": "0.2.0",
		"rssi": -58
	}
}
```

Enumerations:
- `direction`: `edge_to_server | server_to_edge`
- `kind`: `event | command | ack | error | media_chunk | media_commit | media_cancel | heartbeat`
- `qos`: `best_effort | at_least_once`

### 4. Fiabilite, ACK, retries

ACK explicite:
- tout message avec `requires_ack=true` doit recevoir un `kind=ack`.
- ACK contient `acked_message_id`, `status`, `timestamp_ms`.

Timeout/retry recommande:
- timeout ACK: 1200 ms (LAN) / 3000 ms (WAN)
- retry max: 3
- backoff: 250 ms, 500 ms, 1000 ms

Idempotence serveur:
- si `message_id` deja traite -> repond ACK duplicate sans retraiter.

Exemple ACK:

```json
{
	"api_version": "v3",
	"kind": "ack",
	"direction": "server_to_edge",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-2026-05-06-01",
	"message_id": "ack-7c8b",
	"correlation_id": "corr-1730000000123",
	"timestamp_ms": 1730000000321,
	"payload": {
		"acked_message_id": "2c6d9f34-0c7b-4ef4-9ea8-fd2fd5a2c2f1",
		"status": "ok"
	}
}
```

### 5. Evenements edge -> serveur

Systeme:
- `device.online`
- `device.offline`
- `device.heartbeat`
- `device.health`
- `network.changed`

UI/interaction:
- `ui.button.pressed`
- `ui.touch`
- `conversation.started`
- `conversation.ended`

Audio:
- `audio.capture.started`
- `audio.capture.completed`
- `audio.playback.started`
- `audio.playback.completed`

Image/camera:
- `image.capture.started`
- `image.capture.completed`

Exemple event audio complete:

```json
{
	"api_version": "v3",
	"kind": "event",
	"event_type": "audio.capture.completed",
	"direction": "edge_to_server",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-1",
	"message_id": "m-audio-ready",
	"correlation_id": "corr-voice-1",
	"timestamp_ms": 1730000001000,
	"requires_ack": true,
	"payload": {
		"sample_rate_hz": 16000,
		"channels": 1,
		"encoding": "pcm16le",
		"duration_ms": 1400,
		"media_id": "med-aud-001"
	}
}
```

Exemple event de connexion avec capacites:

```json
{
	"api_version": "v3",
	"kind": "event",
	"event_type": "device.online",
	"direction": "edge_to_server",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-1",
	"message_id": "m-online-001",
	"correlation_id": "corr-online-1",
	"timestamp_ms": 1730000000000,
	"requires_ack": true,
	"payload": {
		"firmware_version": "0.2.0",
		"hardware_model": "ESP32-S3-Touch-LCD-1.85C-BOX",
		"capabilities": {
			"audio_input": true,
			"audio_output": true,
			"display": {
				"present": true,
				"shape": "round",
				"width": 360,
				"height": 360,
				"pixel_format": "rgb565"
			},
			"touch": true,
			"camera": false,
			"supported_image_encodings": ["jpeg", "png", "rgb565"],
			"supported_audio_encodings": ["pcm16le", "opus"],
			"max_uplink_chunk_bytes": 16384,
			"max_downlink_chunk_bytes": 16384
		}
	}
}
```

### 6. Commandes serveur -> edge

Commandes principales:
- `audio.play`
- `audio.stop`
- `ui.render`
- `ui.set_state`
- `camera.capture`
- `device.reboot`
- `config.update`

Exemple commande lecture audio:

```json
{
	"api_version": "v3",
	"kind": "command",
	"direction": "server_to_edge",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-1",
	"message_id": "cmd-play-001",
	"correlation_id": "corr-voice-1",
	"timestamp_ms": 1730000001400,
	"requires_ack": true,
	"payload": {
		"command": "audio.play",
		"media_id": "med-aud-reply-001",
		"priority": "normal"
	}
}
```

### 7. Transfert media (audio + image)

Regle:
- les gros contenus passent en `media_chunk` (chunking), puis `media_commit`.
- pas de base64 geant en un seul message WebSocket.

Format `media_chunk`:

```json
{
	"api_version": "v3",
	"kind": "media_chunk",
	"direction": "edge_to_server",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-1",
	"message_id": "chunk-12",
	"correlation_id": "corr-voice-1",
	"timestamp_ms": 1730000001200,
	"requires_ack": true,
	"payload": {
		"media_id": "med-aud-001",
		"media_kind": "audio",
		"encoding": "pcm16le",
		"sample_rate_hz": 16000,
		"channels": 1,
		"chunk_index": 12,
		"chunk_count": 28,
		"data_base64": "..."
	}
}
```

Format `media_commit`:

```json
{
	"api_version": "v3",
	"kind": "media_commit",
	"direction": "edge_to_server",
	"tenant_id": "tenant-a",
	"device_id": "edge-001",
	"session_id": "sess-1",
	"message_id": "commit-001",
	"correlation_id": "corr-voice-1",
	"timestamp_ms": 1730000001300,
	"requires_ack": true,
	"payload": {
		"media_id": "med-aud-001",
		"media_kind": "audio",
		"chunk_count": 28,
		"total_bytes": 44800,
		"sha256": "hex..."
	}
}
```

Media supportes:
- audio: `pcm16le`, `opus` (optionnel phase suivante)
- image: `jpeg`, `png`, `rgb565`

Tailles recommandees:
- chunk audio: 8 KB a 16 KB brut avant base64
- chunk image: 12 KB a 24 KB brut avant base64

### 8. Presence et heartbeat

Heartbeat periodique edge -> serveur:
- `kind=heartbeat` toutes les 10 s.
- timeout presence serveur: 30 s sans heartbeat => `device_offline`.

Payload heartbeat:
- `uptime_ms`, `free_heap`, `wifi_rssi`, `battery_percent`, `state`.

### 9. Securite

Exigences minimales:
- TLS obligatoire (wss/https)
- JWT court terme dans header `Authorization: Bearer ...`
- rotation token + refresh endpoint
- ACL serveur par `tenant_id` et `device_id`

Anti-rejeu:
- verifier `timestamp_ms` fenetre max (ex: 60 s)
- rejet des `message_id` deja vus.

### 10. Gestion erreurs standard

Format erreur:

```json
{
	"api_version": "v3",
	"kind": "error",
	"direction": "server_to_edge",
	"message_id": "err-001",
	"correlation_id": "corr-voice-1",
	"timestamp_ms": 1730000001500,
	"payload": {
		"code": "invalid_media_chunk",
		"message": "chunk_index out of range",
		"retryable": false
	}
}
```

Codes requis:
- `invalid_json`
- `invalid_schema`
- `unauthorized`
- `forbidden_device`
- `message_too_large`
- `invalid_media_chunk`
- `media_checksum_mismatch`
- `ack_timeout`
- `internal_error`

### 11. Compatibilite avec contrat actuel

Migration en 3 phases:
- phase A: conserver `POST /edge/audio` actuel (v2) + ajouter WebSocket v3 en parallele;
- phase B: media chunking v3 pour audio/image, garder fallback HTTP;
- phase C: bascule complete realtime v3, fallback HTTP degrade uniquement.

Mapping minimal v2 -> v3:
- `POST /edge/audio` actuel correspond a:
	- `audio.capture.completed` + `media_chunk(audio)` + `media_commit(audio)`
	- puis `command audio.play` (ou `kind=event` reponse) serveur -> edge.

### 12. KPI latence a suivre

Timestamps obligatoires (ms):
- `t_capture_start`
- `t_capture_end`
- `t_upload_first_chunk`
- `t_upload_commit`
- `t_server_first_token` (ou premiere decision)
- `t_downlink_first_chunk`
- `t_playback_start`

KPI:
- `capture_to_playback_ms = t_playback_start - t_capture_start`
- `network_uplink_ms = t_upload_commit - t_upload_first_chunk`
- `network_downlink_ms = t_playback_start - t_downlink_first_chunk`

Objectif initial:
- mediane `< 1200 ms` en LAN;
- p95 `< 2200 ms` en LAN.

### 13. Schema JSON (etape 1)

Schema de validation officiel v3:
- `docs/02-architecture/schemas/protocol-v3-envelope.schema.json`

Usage recommande:
- validation backend a la reception des messages v3;
- validation edge avant emission des messages critiques (`requires_ack=true`);
- tests contractuels CI avec cas valides/invalides (event, command, ack, error, media_chunk, media_commit, heartbeat).
