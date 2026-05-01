# Matrice de Tests Terrain - Satellite Edge (MACRO-006-T4-S1)

## Objectif
Valider en conditions réelles le comportement du satellite edge sur les scénarios critiques réseau et acoustiques.

## Référence matériel
- Carte cible: Waveshare ESP32-S3-Touch-LCD-1.85C-BOX-EN
- Fiche d'integration hardware/wiki: [doc/waveshare-esp32-s3-touch-lcd-1.85c.md](waveshare-esp32-s3-touch-lcd-1.85c.md)

## Hypothèses de test
- Device cible: ESP32-S3 (ou émulateur edge équivalent)
- Backend edge: endpoint POST /edge/audio
- Wake word: `nova`
- VAD local: heuristique minimale active côté edge
- Ecran et tactile disponibles sur la carte cible, meme si le support logiciel complet reste a ajouter dans ce depot

## Cas de test

| ID | Scénario | Préconditions | Action | Résultat attendu |
|---|---|---|---|---|
| FT-01 | Nominal réseau stable | Wi-Fi stable, backend disponible | Envoyer `nova allume la lumière` | Payload accepté (status=accepted), corrélation présente |
| FT-02 | Bruit ambiant sans wake word | Wi-Fi stable | Injecter segment bruité / parole sans `nova` | Segment ignoré localement, aucun envoi backend |
| FT-03 | Wake word sans commande | Wi-Fi stable | Envoyer `nova` seul | Rejet local (wake_word_without_command), aucun envoi |
| FT-04 | Backend indisponible | Backend arrêté | Envoyer commande valide | Échec d'envoi géré, état `interaction_error`, mode dégradé |
| FT-05 | Reprise après backend rétabli | Backend redémarré après FT-04 | Envoyer commande valide | Reconnexion implicite, payload accepté |
| FT-06 | Wi-Fi faible/instable | Latence + pertes simulées | Envoyer commande valide | Retry appliqué, soit accepted soit échec propre sans crash |
| FT-07 | Mode muet actif | Mute activé | Envoyer commande valide | Traitement backend OK, restitution TTS locale supprimée |
| FT-08 | Coupure utilisateur | Interaction active | Appui bouton | Interaction stoppée, état `button_pressed` |

## KPI à relever
- Taux d'acceptation backend sur 20 essais nominaux
- Taux de faux positifs (bruit ambiant envoyé à tort)
- Temps moyen de reprise après retour backend
- Nombre moyen de retries avant succès en réseau dégradé

## Traçabilité code/tests
- Activation wake word + VAD: [src/assistant/edge_audio.py](src/assistant/edge_audio.py)
- Gestion envoi/retry: [src/assistant/edge_audio.py](src/assistant/edge_audio.py)
- États device (mute/LED/bouton): [src/assistant/edge_device.py](src/assistant/edge_device.py)
- Prototype edge bout en bout: [src/assistant/prototype_edge.py](src/assistant/prototype_edge.py)
- Tests couverture bruit/retry/backend down: [tests/test_edge_audio.py](tests/test_edge_audio.py)
- Tests état appareil: [tests/test_edge_device.py](tests/test_edge_device.py)
- Tests restitution TTS locale edge: [tests/test_prototype_edge.py](tests/test_prototype_edge.py)
