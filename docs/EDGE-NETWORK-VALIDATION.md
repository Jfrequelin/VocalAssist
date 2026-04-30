# Validation Terrain Edge (ESP32-S3)

## Objectif
Valider la robustesse du satellite edge en conditions reelles pour le flux micro -> serveur.

## Matrice de tests terrain

| ID | Cas | Preconditions | Action | Resultat attendu |
|---|---|---|---|---|
| T-01 | Wi-Fi nominal | Satellite connecte, backend up | Dire `nova quelle heure est il` | Payload envoye et accepte |
| T-02 | Wi-Fi faible | Signal degrade, pertes paquets | Rejouer 10 commandes wake-word | Retry reseau puis acceptation ou mode degrade |
| T-03 | Backend down | Backend coupe | Dire `nova test` | Aucun crash, mode degrade explicite |
| T-04 | Bruit ambiant | Bruit TV/fond sans wake-word | Capturer plusieurs segments | Aucun envoi serveur |
| T-05 | Wake-word sans commande | Audio: `nova` seul | Capturer segment | Rejet local, aucun envoi |
| T-06 | Bouton utilisateur | Interaction en cours | Appuyer bouton (commande `/button`) | Interaction coupee et etat maj |
| T-07 | Mute actif | Mute active | Interaction nominale | Envoi conserve, TTS locale supprimee |

## Strategie reconnexion

- Retry cote edge sur envoi audio: `EDGE_SEND_RETRY_ATTEMPTS`.
- Backoff entre tentatives: `EDGE_SEND_RETRY_BACKOFF_SECONDS`.
- Reconnexion opportuniste: chaque nouveau segment valide tente une nouvelle connexion.

## Mode degrade

- Si backend indisponible apres retries:
- etat device passe `error` puis retour au cycle suivant.
- feedback utilisateur local: "mode degrade active".
- pas de blocage de la boucle edge.
