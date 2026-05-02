# [304] [STM32] MACRO-015: Adoption du Format Unifie cote Assistant

**État**: open
**Créé**: 2026-05-02T00:00:00Z
**Mis à jour**: 2026-05-02T00:00:00Z
**Assigné à**: Non assigné

## Labels
`status-queued`, `assistant`, `contract`, `integration`, `python`

## Milestone
Aucun

## Description

## Objectif
Faire evoluer l'assistant Python pour consommer le format d'echange unifie du firmware, tout en conservant la compatibilite avec le contrat audio historique.

## Contexte
- Le firmware sait produire une enveloppe `AssistantPacket` multi-types.
- Les contrats Python sont specialises sur l'audio dans `src/base/contracts.py`.
- Les prochains peripheriques edge (ecran, image, variables runtime, telemetrie) doivent transiter par une couche unique cote assistant.

## Portee
- parser Python pour l'enveloppe canonique
- deserialisation des `payloads` `audio`, `text`, `image`, `variable`
- fallback vers `EdgeAudioRequest` pour compatibilite descendante
- branchement dans les routes backend edge existantes

## Taches
- [ ] Introduire un modele Python `AssistantPacket` et ses payloads types
- [ ] Ajouter un parseur tolerant capable d'accepter l'ancien format audio et le nouveau format canonique
- [ ] Router `text` et `variable` vers les composants applicatifs appropries
- [ ] Definir le comportement pour `image` et `binary` tant qu'ils ne sont pas encore exploites
- [ ] Couvrir les chemins de compatibilite et de rejet par des tests Python

## Critères d'acceptation
- [ ] Le backend accepte les paquets `audio` au format canonique
- [ ] Le backend accepte toujours `EdgeAudioRequest` sans changement de comportement
- [ ] Les paquets `text` et `variable` sont parsés sans erreur
- [ ] Les paquets non supportes sont rejetes proprement avec message explicite
- [ ] Les tests Python couvrent ancien format, nouveau format et erreurs de schema

## Dépendances
- `src/base/contracts.py`
- `src/base/transport.py`
- `src/base/runtime.py`
- ticket [303] format unifie firmware-assistant

## Métadonnées JSON

```json
{
  "number": 304,
  "title": "[STM32] MACRO-015: Adoption du Format Unifie cote Assistant",
  "state": "open",
  "labels": ["status-queued", "assistant", "contract", "integration", "python"],
  "created_at": "2026-05-02T00:00:00Z",
  "updated_at": "2026-05-02T00:00:00Z"
}
```