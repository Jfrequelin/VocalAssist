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

## Contrat Serveur -> Edge (reponse)

Champs minimaux:
- source (local/leon/degrade)
- intent
- answer_text
- action optionnelle
- policy (retry/cache/confirmation)

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

## Contrat commandes parametrees

Exemple `play_podcast`:
- slots obligatoires: podcast_name, provider
- slots optionnels: episode_name, date, position
- etat: ready_to_execute | needs_clarification | not_found
