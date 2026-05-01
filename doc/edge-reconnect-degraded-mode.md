# Strategie Reconnexion et Mode Degrade - Edge (MACRO-006-T4-S2)

## Objectif
Assurer la continuité de service locale quand le backend est indisponible, puis reprise automatique sans intervention lourde.

## Référence matériel
- Carte cible: Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN
- Fiche d'integration hardware/wiki: [doc/waveshare-esp32-s3-touch-lcd-1.85c.md](waveshare-esp32-s3-touch-lcd-1.85c.md)

## Strategie

1. Détection d'échec d'envoi
- Un envoi est considéré en échec si la requête échoue ou la réponse est invalide.
- Le composant edge passe en état d'erreur d'interaction (`interaction_error`).

2. Retry court côté edge
- L'envoi supporte une politique de retry bornée (`retry_attempts`).
- Backoff simple configurable (`retry_backoff_seconds`).
- Aucun blocage infini: retour `None` en cas d'échec final.

3. Mode dégradé
- Le segment courant échoue proprement (pas de crash).
- Le satellite reste opérationnel pour les segments suivants.
- La prochaine commande tente automatiquement une reconnexion implicite.

4. Reprise automatique
- Dès que le backend redevient disponible, l'envoi suivant est accepté.
- Pas de redémarrage du process edge requis.

## Paramètres recommandés
- `retry_attempts`: 2
- `retry_backoff_seconds`: 0.1 à 0.3
- `timeout_seconds`: 0.5 à 3.0 selon qualité réseau

## Signaux opérationnels
- Succès: `status=accepted`, `correlation_id`, `received_bytes`
- Échec: message `envoi echoue ou reponse invalide du backend`
- Degradé: message `mode degrade active`

## Validation actuelle
- Retry + succès ultérieur: [tests/test_edge_audio.py](tests/test_edge_audio.py)
- Backend down: [tests/test_edge_audio.py](tests/test_edge_audio.py)
- Bruit ambiant rejeté localement: [tests/test_edge_audio.py](tests/test_edge_audio.py)
- États device et coupure interaction: [tests/test_edge_device.py](tests/test_edge_device.py)
- Restitution edge + mute/non-mute: [tests/test_prototype_edge.py](tests/test_prototype_edge.py)
