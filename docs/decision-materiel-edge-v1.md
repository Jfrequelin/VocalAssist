# Decision materiel Edge V1

> Legacy: document conserve pour historique.
> Source canonique: `docs/01-vision/product-decisions.md`.

Date: 2026-04-30
Statut: valide pour prototype 1

## Decision

Le prototype Edge V1 utilisera un module ESP32-S3 avec haut-parleur integre (produit retenu par l'equipe) comme satellite vocal economique.

## Perimetre fonctionnel vise

- Detection locale du mot de reveil.
- Commandes locales basiques (stop, mute micro, volume, extinction/restart logique appareil).
- Envoi de l'audio au serveur local pour STT/NLU/Leon.
- Lecture locale des reponses TTS et des flux audio ordonnes par le serveur.

## Pourquoi ce choix

- Cout d'entree faible pour iterer vite.
- Suffisant pour une architecture intelligence centralisee serveur.
- Ecosysteme ESP32-S3 mature (outillage et bibliotheques).

## Ce que ce module ne doit pas porter

- STT conversationnel avance.
- NLU complexe et orchestration metier.
- Memoire conversationnelle long terme.

Ces fonctions restent sur le serveur local.

## Risques identifies

- Qualite micro variable selon le module exact.
- Faux positifs wake word si calibration insuffisante.
- Limitations RAM/buffer si streaming audio continu mal calibre.

## Plan de mitigation

- Commencer en push-to-talk comme mode de secours.
- Calibrer wake word par piece (salon/chambre).
- Ajouter buffer audio adaptatif et timeouts stricts.
- Conserver bouton mute materiel prioritaire.

## Checklist acceptance hardware (Go/No-Go)

1. Wake word detecte correctement sur 50 essais en calme.
2. Wake word detecte correctement sur 30 essais avec bruit TV faible.
3. Commande locale stop/mute/volume repond en moins de 300 ms.
4. Envoi audio edge vers serveur stable sur 10 minutes.
5. Lecture TTS locale sans coupure sur 30 phrases.
6. Recuperation propre apres perte Wi-Fi (sans reboot manuel).
7. Aucune surchauffe bloquante sur 60 minutes de test.

## Prochaines actions

- Integrer firmware Edge V1 cible ESP32-S3.
- Executer campagne de validation hardware.
- Enregistrer resultats dans un rapport de test V1.
