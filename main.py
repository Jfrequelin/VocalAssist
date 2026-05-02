from __future__ import annotations

import argparse

from src.assistant.define import render_project_definition
from src.assistant.base_testbench import run_base_testbench
from src.assistant.prototype import run_prototype
from src.assistant.prototype_voice import run_prototype_voice
from src.assistant.simulate import run_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assistant vocal: definition, simulation et prototype"
    )
    parser.add_argument(
        "--mode",
        choices=["define", "simulate", "prototype", "prototype-voice", "testbench"],
        required=True,
        help="Etape a executer",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "define":
        print(render_project_definition())
    elif args.mode == "simulate":
        run_simulation()
    elif args.mode == "prototype":
        run_prototype()
    elif args.mode == "testbench":
        run_base_testbench()
    else:
        run_prototype_voice()


if __name__ == "__main__":
    main()
