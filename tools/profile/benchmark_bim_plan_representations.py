# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opt-in benchmark for BIM Plan wall representation generation.

Run with a built FreeCADCmd, for example:

    FreeCADCmd tools/profile/benchmark_bim_plan_representations.py --pass --iterations 20

This is deliberately not a unit test: timings are diagnostic and depend on the
machine, build type, and OpenCascade version.
"""

import argparse
import cProfile
import io
import os
import pstats
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
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--sample")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--profile", action="store_true")
    return parser.parse_args(arguments)


def _default_sample_path():
    source_dir = os.environ.get("FREECAD_SOURCE_DIR")
    if source_dir:
        return os.path.join(source_dir, "data", "examples", "BIMPlanEditBasic.FCStd")
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(repository, "data", "examples", "BIMPlanEditBasic.FCStd")


def _plan_request(document):
    from bimplan.representation_request import representation_request_from_storey
    from bimviews.service import BIMViewService

    plan_view = next(
        obj
        for obj in document.Objects
        if obj.isDerivedFrom("App::ViewDefinition") and obj.Purpose == "Plan"
    )
    return representation_request_from_storey(
        BIMViewService(document).context_source(plan_view)
    )


def _measure(operation, iterations):
    samples = []
    for _index in range(iterations):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "median": statistics.median(samples),
        "minimum": min(samples),
        "maximum": max(samples),
    }


def main():
    options = _arguments()
    if options.iterations < 1:
        raise ValueError("--iterations must be positive")
    sample = os.path.abspath(options.sample or _default_sample_path())
    if not os.path.isfile(sample):
        raise FileNotFoundError(sample)

    import ArchPlanAnalytic
    from bimviews import representation_cache

    document = FreeCAD.openDocument(sample)
    try:
        request = _plan_request(document)
        walls = tuple(
            obj for obj in document.Objects if getattr(obj, "IfcType", "") == "Wall"
        )

        def analytic():
            for wall in walls:
                model = ArchPlanAnalytic.straight_wall_plan_model(
                    wall, wall.Proxy, request
                )
                if model is None:
                    raise RuntimeError(f"No analytic model for {wall.Name}")
                model.make_faces()

        def brep():
            for wall in walls:
                tuple(wall.Proxy._getCutRepresentation(wall, request))

        # Report the first derived-data pass separately from steady-state use.
        brep()
        representation_cache.invalidate_document(document)
        analytic_cold = _measure(analytic, 1)
        analytic_result = _measure(analytic, options.iterations)
        brep_result = _measure(brep, options.iterations)
        speedup = brep_result["median"] / analytic_result["median"]
        print(f"sample: {sample}")
        print(f"walls: {len(walls)}, iterations: {options.iterations}")
        print(f"analytic cold: {analytic_cold['median']:.3f} ms")
        for name, result in (("analytic", analytic_result), ("brep", brep_result)):
            print(
                f"{name}: median={result['median']:.3f} ms "
                f"min={result['minimum']:.3f} ms max={result['maximum']:.3f} ms"
            )
        print(f"median speedup: {speedup:.2f}x")
        if options.details:
            print("per-wall median (analytic / brep):")
            for wall in walls:

                def analytic_wall():
                    model = ArchPlanAnalytic.straight_wall_plan_model(
                        wall, wall.Proxy, request
                    )
                    if model is None:
                        raise RuntimeError(f"No analytic model for {wall.Name}")
                    model.make_faces()

                analytic_wall_result = _measure(analytic_wall, options.iterations)
                brep_wall_result = _measure(
                    lambda wall=wall: tuple(
                        wall.Proxy._getCutRepresentation(wall, request)
                    ),
                    options.iterations,
                )
                print(
                    f"  {wall.Name}: {analytic_wall_result['median']:.3f} / "
                    f"{brep_wall_result['median']:.3f} ms"
                )
        if options.profile:
            profiler = cProfile.Profile()
            profiler.enable()
            analytic()
            profiler.disable()
            output = io.StringIO()
            pstats.Stats(profiler, stream=output).sort_stats("cumulative").print_stats(30)
            print(output.getvalue())
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
