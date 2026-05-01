# Interfaces et Contrats API

## Contrat Edge -> Serveur (commande vocale)

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
