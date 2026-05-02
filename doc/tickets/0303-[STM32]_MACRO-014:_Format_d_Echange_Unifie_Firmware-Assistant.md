# [303] [STM32] MACRO-014: Format d'Echange Unifie Firmware-Assistant

**État**: open
**Créé**: 2026-05-02T00:00:00Z
**Mis à jour**: 2026-05-02T00:00:00Z
**Assigné à**: Non assigné

## Labels
`status-queued`, `firmware`, `contract`, `edge`, `assistant`

## Milestone
Aucun

## Description

## Objectif
Definir et stabiliser un format d'echange canonique entre le firmware edge et l'assistant pour tous les types de donnees: audio, image, texte, variables et binaire generique.

## Contexte
- Le crate Rust introduit une enveloppe `AssistantPacket` et des payloads types dans `src/base/firmware/stm32-rust/src/hal/exchange.rs`.
- Le code Python ne connait aujourd'hui qu'un contrat audio specifique (`EdgeAudioRequest`).
- Sans contrat canonique partage, chaque nouveau peripherique ou type de donnees risque d'introduire un format ad hoc.

## Portee
- enveloppe commune: `correlation_id`, `device_id`, `timestamp_ms`, `kind`, `payload`
- types de donnees supportes:
  - `audio`
  - `image`
  - `text`
  - `variable`
  - `binary`
- encodages canoniques documentes (`pcm16le`, `opus`, `png`, `jpeg`, `rgb565`, `utf8`, `json`, `raw`)
- compatibilite descendante avec `EdgeAudioRequest`

## Taches
- [ ] Documenter la spec JSON canonique complete avec exemples par `kind`
- [ ] Definir les contraintes de taille et d'encodage cote firmware (`no_std`, buffers bornes)
- [ ] Definir les regles de versioning du contrat (`api_version` ou evolution compatible)
- [ ] Valider le mapping `AssistantPacket -> EdgeAudioRequest` pour l'audio
- [ ] Ajouter des tests de non-regression sur la serialisation des differents payloads

## Critères d'acceptation
- [ ] Le format canonique couvre au moins audio, texte, image et variable
- [ ] Chaque `kind` a un schema JSON et un exemple documente
- [ ] Le firmware peut serialiser le format sans allocation dynamique non bornee
- [ ] Le contrat audio existant reste consomme par l'assistant sans regression
- [ ] Les tests Rust couvrent la serialisation canonique et la compatibilite audio

## Dépendances
- `src/base/firmware/stm32-rust/src/hal/exchange.rs`
- `src/base/contracts.py`
- `docs/02-architecture/interfaces-and-contracts.md`

## Métadonnées JSON

```json
{
  "number": 303,
  "title": "[STM32] MACRO-014: Format d'Echange Unifie Firmware-Assistant",
  "state": "open",
  "labels": ["status-queued", "firmware", "contract", "edge", "assistant"],
  "created_at": "2026-05-02T00:00:00Z",
  "updated_at": "2026-05-02T00:00:00Z"
}
```