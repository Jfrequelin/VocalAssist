# Checklist terrain edge (execution)

## Preparation

- Verifier audio Linux:
  - `arecord -l`
  - `aplay -l`
- Verifier environnement Python:
  - `./.venv/bin/python --version`
- Option HTTP: demarrer le backend:
  - `docker compose up -d --build`

## Lancement

- Local (in-process):
  - `./scripts/run_edge_field_profile.sh local`
- HTTP (backend externe):
  - `./scripts/run_edge_field_profile.sh http`

## Campagne FT-01 a FT-08

- FT-01 Nominal
  - Entree: `nova allume la lumiere`
  - Attendu: `status=accepted`, correlation id present

- FT-02 Bruit ambiant sans wake word
  - Entree: bruit/parole sans `nova`
  - Attendu: segment ignore localement, pas d'envoi backend

- FT-03 Wake word sans commande
  - Entree: `nova`
  - Attendu: rejet local `wake_word_without_command`

- FT-04 Backend indisponible (mode HTTP)
  - Action: stopper backend, puis envoyer `nova test`
  - Attendu: echec propre, mode degrade, aucun crash

- FT-05 Reprise apres retour backend (mode HTTP)
  - Action: redemarrer backend, rejouer `nova test`
  - Attendu: reconnexion implicite, payload accepte

- FT-06 Reseau degrade
  - Action: augmenter pertes/latence, rejouer 10 commandes
  - Attendu: retries puis accepted ou echec propre sans blocage

- FT-07 Mute actif
  - Action: `/mute`, puis commande valide
  - Attendu: envoi conserve, restitution locale supprimee

- FT-08 Coupure utilisateur
  - Action: interaction en cours puis `/button`
  - Attendu: interaction stoppee, etat maj

## Observabilite conseillee

- Exporter un snapshot de session:
  - `ASSISTANT_TESTBENCH_EXPORT_PATH=data/edge-field-session.latest.json`
- Conserver au minimum:
  - nombre de turns
  - taux accepted/rejected
  - latence moyenne
  - dernier intent/source

## Nettoyage

- Option HTTP:
  - `docker compose down`
