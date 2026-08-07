"""Generate matched link, unique-object, and compound assembly fixtures.

Examples::

    FreeCAD --console generate_assembly.py --preset links-medium
    FreeCAD --console generate_assembly.py --preset unique-objects-medium
    FreeCAD --console generate_assembly.py --preset single-compound-medium
    FreeCAD --console generate_assembly.py --preset assembly-compound-medium
"""

from __future__ import annotations

import argparse
import math
import random

import FreeCAD as App
import Part

from common import (
    add_benchmark_info,
    color,
    configure_view,
    grid_count,
    print_generation_result,
    save_reopen_validate,
    shape_counts,
    require_gui,
)


REPRESENTATIONS = ("links", "unique-objects", "single-compound")
SIZES = ("small", "medium", "large", "xlarge")


def generate(
    *, representation: str, size: str, seed: int, output: str, display_mode: str
) -> dict[str, object]:
    component_count = grid_count(size, kind="assembly")
    deviation = 0.1
    angular_deflection = 15.0
    spacing = 28.0
    source_specs = _source_specs()
    rng = random.Random(seed)
    instances = _make_instances(component_count, len(source_specs), rng, spacing)

    doc = App.newDocument("Assembly")
    document_name = doc.Name
    try:
        source_objects = []
        if representation == "links":
            for source_index, (source_name, source_shape, source_color) in enumerate(source_specs):
                source = doc.addObject("Part::Feature", source_name)
                source.Label = source_name
                source.Shape = source_shape
                configure_view(
                    source,
                    display_mode=display_mode,
                    visible=False,
                    shape_color=source_color,
                    deviation=deviation,
                    angular_deflection=angular_deflection,
                )
                source_objects.append(source)

            for index, instance in enumerate(instances):
                source = source_objects[instance["source_index"]]
                link = doc.addObject("App::Link", f"Component_{index:05d}")
                link.Label = f"{source.Label} {index:05d}"
                _set_link(link, source)
                link.Placement = instance["placement"]
                configure_view(
                    link,
                    display_mode=display_mode,
                    shape_color=source_specs[instance["source_index"]][2],
                    deviation=deviation,
                    angular_deflection=angular_deflection,
                )

            part_feature_count = len(source_objects)
            visible_objects = component_count
            link_count = component_count
            target_name = None
        elif representation == "unique-objects":
            for index, instance in enumerate(instances):
                source_name, source_shape, source_color = source_specs[instance["source_index"]]
                component = doc.addObject("Part::Feature", f"Component_{index:05d}")
                component.Label = f"{source_name} {index:05d}"
                component.Shape = source_shape.copy()
                component.Placement = instance["placement"]
                configure_view(
                    component,
                    display_mode=display_mode,
                    shape_color=source_color,
                    deviation=deviation,
                    angular_deflection=angular_deflection,
                )

            part_feature_count = component_count
            visible_objects = component_count
            link_count = 0
            target_name = None
        else:
            transformed_shapes = []
            for instance in instances:
                source_shape = source_specs[instance["source_index"]][1].copy()
                source_shape.Placement = instance["placement"]
                transformed_shapes.append(source_shape)
            compound = doc.addObject("Part::Feature", "AssemblyCompound")
            compound.Label = f"AssemblyCompound ({size})"
            compound.Shape = Part.makeCompound(transformed_shapes)
            configure_view(
                compound,
                display_mode=display_mode,
                shape_color=color(0.72, 0.76, 0.82),
                deviation=deviation,
                angular_deflection=angular_deflection,
            )
            part_feature_count = 1
            visible_objects = 1
            link_count = 0
            target_name = compound.Name

        faces_per_source = [shape_counts(shape)["faces"] for _, shape, _ in source_specs]
        visible_faces = sum(faces_per_source[instance["source_index"]] for instance in instances)
        expected = {
            "visible_objects": visible_objects,
            "links": link_count,
            "part_features": part_feature_count,
            "visible_faces": visible_faces,
        }
        if target_name is not None:
            expected["target_object"] = target_name
            expected["target_faces"] = visible_faces
        parameters = {
            "representation": representation,
            "size": size,
            "component_count": component_count,
            "component_types": [name for name, _, _ in source_specs],
            "spacing": spacing,
            "deviation": deviation,
            "angular_deflection": angular_deflection,
        }
        add_benchmark_info(
            doc,
            fixture_name=f"assembly_{representation.replace('-', '_')}_{size}",
            generator="generate_assembly.py",
            preset=f"{representation}-{size}",
            seed=seed,
            display_mode=display_mode,
            parameters=parameters,
            expected=expected,
        )
        save_reopen_validate(doc, output, expected)
        doc = None
        return expected
    finally:
        if doc is not None:
            _close_document(document_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", help="representation-size shorthand, e.g. links-medium")
    parser.add_argument("--representation", choices=REPRESENTATIONS, default="links")
    parser.add_argument("--size", choices=SIZES, default="medium")
    parser.add_argument("--seed", type=int, default=31603)
    parser.add_argument("--output")
    parser.add_argument("--display-mode", choices=("shaded", "flat-lines"), default="shaded")
    args = parser.parse_args(argv)
    require_gui()

    representation, size = _resolve_preset(
        args.preset, args.representation, args.size, parser
    )
    output = args.output or f"assembly_{representation.replace('-', '_')}_{size}.FCStd"
    expected = generate(
        representation=representation,
        size=size,
        seed=args.seed,
        output=output,
        display_mode=args.display_mode,
    )
    print_generation_result(output, expected)
    return 0


def _source_specs() -> list[tuple[str, object, tuple[float, float, float, float]]]:
    return [
        ("BoltSource", _make_bolt(), color(0.68, 0.70, 0.74)),
        ("WasherSource", _make_washer(), color(0.80, 0.82, 0.86)),
        ("BracketSource", _make_bracket(), color(0.58, 0.64, 0.72)),
        ("PlateSource", _make_plate(), color(0.72, 0.76, 0.82)),
        ("SpacerSource", _make_spacer(), color(0.76, 0.63, 0.38)),
    ]


def _make_instances(
    count: int, source_count: int, rng: random.Random, spacing: float
) -> list[dict[str, object]]:
    side = max(1, int(math.ceil(count ** (1.0 / 3.0))))
    instances = []
    for index in range(count):
        source_index = rng.randrange(source_count)
        x = (index % side) * spacing
        y = ((index // side) % side) * spacing
        z = (index // (side * side)) * spacing
        angle = rng.randrange(0, 360)
        placement = App.Placement(
            App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), angle)
        )
        instances.append({"source_index": source_index, "placement": placement})
    return instances


def _make_bolt() -> object:
    shaft = Part.makeCylinder(2.0, 14.0)
    head = Part.makeCylinder(4.0, 2.5, App.Vector(0, 0, 14.0))
    collar = Part.makeCylinder(3.0, 1.0, App.Vector(0, 0, 12.5))
    return Part.makeCompound([shaft, collar, head])


def _make_washer() -> object:
    outer = Part.makeCylinder(5.0, 1.2)
    inner = Part.makeCylinder(2.4, 1.2, App.Vector(0, 0, 0.0))
    # Keep this as a compound rather than a boolean ring: generation stays
    # cheap and the source remains a predictable multi-face shape.
    return Part.makeCompound([outer, inner])


def _make_bracket() -> object:
    upright = Part.makeBox(3.0, 12.0, 20.0)
    foot = Part.makeBox(16.0, 12.0, 3.0, App.Vector(0, 0, 0))
    return Part.makeCompound([upright, foot])


def _make_plate() -> object:
    plate = Part.makeBox(18.0, 14.0, 2.0)
    rib = Part.makeBox(2.0, 14.0, 5.0, App.Vector(8.0, 0, 2.0))
    return Part.makeCompound([plate, rib])


def _make_spacer() -> object:
    body = Part.makeCylinder(4.0, 8.0)
    cap = Part.makeCylinder(5.0, 1.5, App.Vector(0, 0, 8.0))
    return Part.makeCompound([body, cap])


def _set_link(link: object, source: object) -> None:
    try:
        link.setLink(source)
    except (AttributeError, RuntimeError):
        link.LinkedObject = source


def _resolve_preset(
    preset: str | None,
    representation: str,
    size: str,
    parser: argparse.ArgumentParser,
) -> tuple[str, str]:
    if not preset:
        return representation, size
    if preset.startswith("assembly-compound-"):
        candidate_size = preset[len("assembly-compound-") :]
        if candidate_size in SIZES:
            return "single-compound", candidate_size
    for candidate in REPRESENTATIONS:
        prefix = candidate + "-"
        if preset.startswith(prefix):
            candidate_size = preset[len(prefix) :]
            if candidate_size in SIZES:
                return candidate, candidate_size
    parser.error(f"invalid assembly preset {preset!r}")
    raise AssertionError("argparse.error did not exit")


def _close_document(name: str) -> None:
    try:
        if App.getDocument(name) is not None:
            App.closeDocument(name)
    except (AttributeError, RuntimeError):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
