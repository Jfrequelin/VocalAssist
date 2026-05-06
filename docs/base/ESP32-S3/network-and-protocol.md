# Reseau et Protocole - Base ESP32-S3

## Transport actuel
- HTTP pour `/health` et `/edge/audio`

## Cible protocolaire
- WebSocket TLS bidirectionnel pour le temps reel
- fallback HTTP si indisponible

## Messages importants a la connexion
- `device.online`
- `device.heartbeat`
- exposition `capabilities`

## Messages media
- `media_chunk`
- `media_commit`
- `media_cancel`

## References
- ../../02-architecture/interfaces-and-contracts.md
- ../../02-architecture/schemas/protocol-v3-envelope.schema.json
