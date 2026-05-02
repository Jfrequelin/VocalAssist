# Interfaces et Contrats API

## Contrat Edge -> Serveur (commande vocale)

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
