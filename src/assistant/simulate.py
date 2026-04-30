from __future__ import annotations

from src.assistant.intents import parse_intent, respond
from src.assistant.scenarios import load_scenarios


def run_simulation() -> None:
    print("=== Simulation de scenarios ===")
    scenarios = load_scenarios()
    correct = 0

    for idx, scenario in enumerate(scenarios, start=1):
        message = scenario["user"]
        expected = scenario["expected_intent"]
        intent = parse_intent(message)
        answer = respond(intent)
        is_ok = intent == expected
        if is_ok:
            correct += 1

        print(f"\nScenario {idx}")
        print(f"Utilisateur: {message}")
        print(f"Intent attendu: {expected}")
        print(f"Intent detecte: {intent}")
        print(f"Resultat: {'OK' if is_ok else 'KO'}")
        print(f"Assistant: {answer}")

    total = len(scenarios)
    ratio = (correct / total) * 100 if total else 0
    print("\n=== Resume simulation ===")
    print(f"Scenarios valides: {correct}/{total}")
    print(f"Taux de reconnaissance d'intention: {ratio:.1f}%")
