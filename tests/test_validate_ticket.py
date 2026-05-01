from __future__ import annotations

import unittest

from scripts.validate_ticket import build_plan


class TestValidateTicketPlan(unittest.TestCase):
    def test_build_plan_with_all_tools(self) -> None:
        plan = build_plan(
            files=["src/assistant/prototype_voice.py"],
            tests=["tests/test_voice_pipeline.py"],
            has_pyright=True,
            has_pylint=True,
            pylint_fail_under=9.0,
        )

        names = [step.name for step in plan]
        self.assertEqual(
            names,
            ["py_compile", "tests", "pyright", "pylint"],
        )

    def test_build_plan_without_pyright(self) -> None:
        plan = build_plan(
            files=["src/assistant/prototype_voice.py"],
            tests=["tests/test_voice_pipeline.py"],
            has_pyright=False,
            has_pylint=True,
            pylint_fail_under=9.0,
        )

        names = [step.name for step in plan]
        self.assertEqual(
            names,
            ["py_compile", "tests", "pylint"],
        )

    def test_build_plan_without_tests_uses_full_suite(self) -> None:
        plan = build_plan(
            files=["src/assistant/prototype_voice.py"],
            tests=[],
            has_pyright=True,
            has_pylint=True,
            pylint_fail_under=9.0,
        )

        tests_step = next(step for step in plan if step.name == "tests")
        self.assertEqual(tests_step.command, ["python3", "-m", "unittest"])

    def test_build_plan_pylint_fail_under(self) -> None:
        plan = build_plan(
            files=["scripts/validate_ticket.py"],
            tests=["tests/test_validate_ticket.py"],
            has_pyright=False,
            has_pylint=True,
            pylint_fail_under=9.0,
        )

        pylint_step = next(step for step in plan if step.name == "pylint")
        self.assertEqual(
            pylint_step.command,
            [
                "python3",
                "-m",
                "pylint",
                "--fail-under=9",
                "scripts/validate_ticket.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
