# Cycle de Session Conversationnelle

## Vue d'ensemble

Une session représente une interaction continue entre l'utilisateur et l'assistant, depuis l'activation du wake word jusqu'à la fin du dialogue. Le gestionnaire de session gère les timeouts, les réactivations et le nettoyage des sessions expirées.

## États et Transitions

```
START
  |
  v
ACTIVE (nouvellement créée)
  |
  +--[inactivité > timeout]----> EXPIRED
  |                                   |
  +--[record_activity()]-------+      |
  |                            |      |
  +--[resume_session()]--------+      |
  |                            |      |
  +--[close_session()]---> CLOSED    |
                            (v)       |
                            ----------+
```

## Détails des États

### ACTIVE
- La session est en cours et peut traiter des commandes.
- Un timeout inactif peut conduire à l'expiration.
- Une activité enregistrée redémarre le timer d'inactivité.

### EXPIRED
- La session a dépassé le timeout inactif.
- Elle peut être restaurée via `resume_session()` (redémarre le timer).
- Après expiration, une nouvelle activation (wake word) commence une nouvelle session.

### CLOSED
- La session a été explicitement fermée.
- Elle ne peut pas être restaurée.
- Une nouvelle activation crée une nouvelle session.

## Paramètres de Timeout

```python
# Prototype utilisateur (interactif)
session_timeout_seconds = 120  # 2 minutes d'inactivité

# Pipeline vocal
session_timeout_seconds = 60   # 1 minute d'inactivité

# Tests
session_timeout_seconds = 0.1  # 100ms pour tests rapides
```

## Cycle Conversationnel Typique

### Mode Terminal

1. **Attente d'activation**
   - L'assistant affiche le prompt et attend une entrée
   - Aucune session active

2. **Wake word détecté**
   - Appel `handler.extract_command(input)`
   - Retour: `result.activated = True`
   - Création d'une nouvelle session via `session_manager.start_session()`

3. **Traitement de commande**
   - Extraction du message: `result.command`
   - Appel orchestrator: `handle_message(message, ...)`
   - Enregistrement d'activité: `session_manager.record_activity(session_id)`

4. **Réponse de l'assistant**
   - Affichage de la réponse
   - Affichage de la trace (correlation_id, source, timing)

5. **Fin de session**
   - Détection d'une action `exit`: appel `session_manager.close_session(session_id)`
   - Ou: inactivité naturelle → expiration automatique après `session_timeout_seconds`

6. **Réactivation optionnelle**
   - Wake word détecté lors de l'inactivité (< timeout)
   - Tentative `session_manager.resume_session(session_id)`
   - Si succès: réutilisation de la session existante
   - Si expirée/échec: création d'une nouvelle session

### Mode Vocal

Même cycle, mais:
- Le STT fournit la transcription continue
- Le timeout est généralement plus court (60s vs 120s)
- Chaque transcription déclenche `record_activity()` pour maintenir la session

## Exemple d'Intégration (Pseudo-code)

```python
session_manager = SessionManager(timeout_seconds=120)

while True:
    raw_input = input("\nVous: ")
    
    # Étape 1: Activation
    result = handler.extract_command(raw_input)
    if not result.activated:
        print("Assistant: mot cle absent, commande ignoree.")
        continue
    
    # Étape 2: Démarrage ou reprise de session
    # (Dans une vraie impl, on vérifierait une session existante d'abord)
    session = session_manager.start_session()
    
    # Étape 3: Traitement
    message = result.command
    reply = handle_message(message, correlation_id=...)
    
    # Étape 4: Enregistrement d'activité
    session_manager.record_activity(session.session_id)
    
    # Étape 5: Affichage et fermeture si nécessaire
    print(f"Assistant: {reply.answer}")
    
    if reply.intent == "exit":
        session_manager.close_session(session.session_id)
        break
```

## Nettoyage

Le gestionnaire propose `cleanup_expired_sessions()` pour éviter les fuites mémoire en environnement production. À appeler régulièrement (ex: toutes les 5 minutes).

```python
# Nettoyage périodique
cleaned = session_manager.cleanup_expired_sessions()
print(f"Sessions expirées nettoyées: {cleaned}")
```
