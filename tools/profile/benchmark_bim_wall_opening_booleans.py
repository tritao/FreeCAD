# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compare sequential and batched OCCT wall-opening subtraction.

Run with a built FreeCADCmd, for example:

    FreeCADCmd tools/profile/benchmark_bim_wall_opening_booleans.py \
        --pass=--openings --pass=10 --pass=--iterations --pass=20

This is an opt-in diagnostic benchmark, not a timing-sensitive unit test.
"""

import argparse
import os
import statistics
import sys
import time

import FreeCAD
import Part


def _arguments():
    arguments = list(sys.argv[1:])
    if "--pass" in arguments:
        arguments = arguments[arguments.index("--pass") + 1 :]
    else:
        arguments = [argument.removeprefix("--pass=") for argument in arguments[1:]]
    parser = argparse.ArgumentParser()
    parser.add_argument("--openings", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=20)
    return parser.parse_args(arguments)


def _measure(operation, iterations):
    samples = []
    result = None
    for _index in range(iterations):
        started = time.perf_counter()
        result = operation()
        samples.append((time.perf_counter() - started) * 1000.0)
    return result, (statistics.median(samples), min(samples), max(samples))


def main():
    options = _arguments()
    if options.openings < 1 or options.iterations < 1:
        raise ValueError("--openings and --iterations must be positive")

    import ArchComponent

    wall_length = max(10000.0, options.openings * 850.0 + 1000.0)
    wall = Part.makeBox(
        wall_length,
        200,
        3000,
        FreeCAD.Vector(0, -100, 0),
    )
    openings = tuple(
        Part.makeBox(600, 400, 1200, FreeCAD.Vector(500 + index * 850, -200, 700))
        for index in range(options.openings)
    )

    def sequential():
        result = wall
        for opening in openings:
            result = result.cut(opening)
        return result

    def batched():
        return ArchComponent.Component._cut_subtraction_tools(wall, openings)

    sequential_shape, sequential_time = _measure(sequential, options.iterations)
    batched_shape, batched_time = _measure(batched, options.iterations)
    if not batched_shape.isValid():
        raise RuntimeError("batched subtraction produced an invalid shape")
    if abs(sequential_shape.Volume - batched_shape.Volume) > 1e-5:
        raise RuntimeError("sequential and batched subtraction volumes differ")

    print(f"openings: {options.openings}, iterations: {options.iterations}")
    for name, result in (("sequential", sequential_time), ("batched", batched_time)):
        print(
            f"{name}: median={result[0]:.3f} ms "
            f"min={result[1]:.3f} ms max={result[2]:.3f} ms"
        )
    print(f"median speedup: {sequential_time[0] / batched_time[0]:.2f}x")


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
