"""Command dispatch shared by the FreeCAD GUI macro and shell wrapper."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence


COMMANDS = {
    "analyze": "analyze_fcstd",
    "benchmark": "benchmark_rotation",
    "generate-assembly": "generate_assembly",
    "generate-face": "generate_face_binding",
    "mutation": "mutation_regression",
    "validate": "validate_fixture",
}


def script_arguments(argv: Sequence[str]) -> list[str]:
    """Return launcher arguments from the environment or direct invocation."""

    encoded = os.environ.get("FREECAD_RENDERING_ARGS")
    if encoded:
        arguments = json.loads(encoded)
        if not isinstance(arguments, list) or not all(
            isinstance(argument, str) for argument in arguments
        ):
            raise ValueError("FREECAD_RENDERING_ARGS must encode a JSON string list")
        return arguments

    try:
        marker = list(argv).index("--pass")
    except ValueError:
        marker = 1
    return list(argv)[marker + 1 :]


def main(arguments: Sequence[str]) -> int:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    parser = argparse.ArgumentParser(
        description="Run rendering fixture tools in the FreeCAD GUI process."
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    command, remaining = parser.parse_known_args(list(arguments))

    module = __import__(COMMANDS[command.command])
    return int(module.main(remaining))
