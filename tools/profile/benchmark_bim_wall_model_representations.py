# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opt-in benchmark for exact and analytic BIM wall model representations.

Run with a built FreeCADCmd, for example:

    FreeCADCmd tools/profile/benchmark_bim_wall_model_representations.py \
        --pass=--walls --pass=100 --pass=--iterations --pass=20

This measures representation generation, not GPU drawing or frame rate. It is
deliberately not a unit test because timings depend on the machine and build.
"""

import argparse
import os
import statistics
import sys
import time

import FreeCAD


def _arguments():
    arguments = list(sys.argv[1:])
    if "--pass" in arguments:
        arguments = arguments[arguments.index("--pass") + 1 :]
    else:
        arguments = [argument.removeprefix("--pass=") for argument in arguments[1:]]
    parser = argparse.ArgumentParser()
    parser.add_argument("--walls", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=20)
    return parser.parse_args(arguments)


def _measure(operation, iterations):
    samples = []
    for _index in range(iterations):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples), min(samples), max(samples)


def main():
    options = _arguments()
    if options.walls < 1 or options.iterations < 1:
        raise ValueError("--walls and --iterations must be positive")

    import Arch
    import ArchRepresentation

    document = FreeCAD.newDocument("BIMWallModelRepresentationBenchmark")
    try:
        walls = []
        for index in range(options.walls):
            wall = Arch.makeWall(length=4000, width=200, height=3000)
            wall.Placement.Base.y = index * 400
            walls.append(wall)
        document.recompute()
        exact_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
        viewport_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL,
            representation_mode=ArchRepresentation.RepresentationMode.VIEWPORT,
        )

        def generate(request):
            return tuple(
                ArchRepresentation.representation_for(wall, request) for wall in walls
            )

        generate(exact_request)
        generate(viewport_request)
        exact = _measure(lambda: generate(exact_request), options.iterations)
        viewport = _measure(lambda: generate(viewport_request), options.iterations)
        print(f"walls: {options.walls}, iterations: {options.iterations}")
        for name, result in (("part shape", exact), ("viewport", viewport)):
            print(
                f"{name}: median={result[0]:.3f} ms "
                f"min={result[1]:.3f} ms max={result[2]:.3f} ms"
            )
        print(f"median speedup: {exact[0] / viewport[0]:.2f}x")
    finally:
        FreeCAD.closeDocument(document.Name)


def _invoked_as_script():
    if __name__ == "__main__":
        return True
    try:
        return len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(
            __file__
        )
    except OSError:
        return False


if _invoked_as_script():
    main()
