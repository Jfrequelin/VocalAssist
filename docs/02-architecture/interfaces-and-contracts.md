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
