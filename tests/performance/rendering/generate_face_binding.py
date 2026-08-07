"""Generate deterministic face-material binding stress fixtures.

Examples::

    FreeCAD --console generate_face_binding.py --preset overall-medium
    FreeCAD --console generate_face_binding.py --preset perface-same-medium
    FreeCAD --console generate_face_binding.py --variant perface-unique --size large \
        --seed 31603 --output face_perface_unique_large.FCStd
"""

from __future__ import annotations

import argparse

import FreeCAD as App
import Part

from common import (
    add_benchmark_info,
    color,
    configure_view,
    grid_count,
    print_generation_result,
    save_reopen_validate,
    set_diffuse_colors,
    shape_counts,
    require_gui,
    deterministic_color,
    stable_json_hash,
)


VARIANTS = (
    "overall",
    "perface-same",
    "perface-alternating",
    "perface-calibrated",
    "perface-palette-1",
    "perface-palette-2",
    "perface-palette-4",
    "perface-palette-8",
    "perface-palette-13",
    "perface-palette-16",
    "perface-palette-32",
    "perface-palette-64",
    "perface-palette-256",
    "perface-unique",
)
SIZES = ("small", "medium", "large", "xlarge")


def generate(
    *, variant: str, size: str, seed: int, output: str, display_mode: str
) -> dict[str, object]:
    rows = grid_count(size, kind="face")
    columns = rows
    width = 10.0
    depth = 10.0
    thickness = 0.8
    pitch = 12.0
    deviation = 0.1
    angular_deflection = 15.0

    doc = App.newDocument("FaceBinding")
    document_name = doc.Name
    try:
        shapes = []
        for row in range(rows):
            for column in range(columns):
                plate = Part.makeBox(width, depth, thickness)
                z = ((row * 7 + column * 11) % 5) * 4.0
                plate.Placement = App.Placement(
                    App.Vector(column * pitch, row * pitch, z), App.Rotation()
                )
                shapes.append(plate)

        obj = doc.addObject("Part::Feature", "FaceHeavy")
        obj.Label = f"FaceHeavy ({variant}, {size})"
        obj.Shape = Part.makeCompound(shapes)
        base_color = color(0.75, 0.78, 0.82)
        configure_view(
            obj,
            display_mode=display_mode,
            shape_color=base_color,
            deviation=deviation,
            angular_deflection=angular_deflection,
        )

        face_count = shape_counts(obj.Shape)["faces"]
        if variant == "perface-same":
            color_count = len(set_diffuse_colors(obj, [base_color] * face_count))
            distinct_color_count = 1
        elif variant == "perface-alternating":
            alternate = color(0.78, 0.80, 0.86)
            colors = [base_color if index % 2 == 0 else alternate for index in range(face_count)]
            color_count = len(set_diffuse_colors(obj, colors))
            distinct_color_count = 2
        elif variant == "perface-calibrated":
            palette = [deterministic_color(index, seed) for index in range(13)]
            colors = [palette[(index * 7 + seed) % len(palette)] for index in range(face_count)]
            color_count = len(set_diffuse_colors(obj, colors))
            distinct_color_count = len(set(colors))
        elif variant.startswith("perface-palette-"):
            palette_size = int(variant.rsplit("-", 1)[1])
            palette = [deterministic_color(index, seed) for index in range(palette_size)]
            colors = [palette[(index * 7 + seed) % palette_size] for index in range(face_count)]
            color_count = len(set_diffuse_colors(obj, colors))
            distinct_color_count = len(set(colors))
        elif variant == "perface-unique":
            colors = _deterministic_palette(face_count, seed)
            color_count = len(set_diffuse_colors(obj, colors))
            distinct_color_count = len(set(colors))
        else:
            # ShapeColor is intentionally used without assigning a face array.
            color_count = 1
            distinct_color_count = 1

        expected = {
            "visible_objects": 1,
            "links": 0,
            "part_features": 1,
            "visible_faces": face_count,
            "target_object": obj.Name,
            "target_faces": face_count,
            "target_diffuse_color_count": color_count,
            "distinct_face_color_count": distinct_color_count,
            "color_mode": "overall" if variant == "overall" else "per-face",
        }
        geometry_parameters = {
            "size": size,
            "rows": rows,
            "columns": columns,
            "plate_width": width,
            "plate_depth": depth,
            "plate_thickness": thickness,
            "pitch": pitch,
            "deviation": deviation,
            "angular_deflection": angular_deflection,
        }
        parameters = {"variant": variant, **geometry_parameters}
        expected["geometry_signature"] = stable_json_hash(geometry_parameters)
        add_benchmark_info(
            doc,
            fixture_name=f"face_{variant.replace('-', '_')}_{size}",
            generator="generate_face_binding.py",
            preset=f"{variant}-{size}",
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
    parser.add_argument("--preset", help="variant-size shorthand, e.g. perface-same-medium")
    parser.add_argument("--variant", choices=VARIANTS, default="overall")
    parser.add_argument("--size", choices=SIZES, default="medium")
    parser.add_argument("--seed", type=int, default=31603)
    parser.add_argument("--output")
    parser.add_argument("--display-mode", choices=("shaded", "flat-lines"), default="shaded")
    args = parser.parse_args(argv)
    require_gui()

    variant, size = _resolve_preset(args.preset, args.variant, args.size, parser)
    output = args.output or f"face_{variant.replace('-', '_')}_{size}.FCStd"
    expected = generate(
        variant=variant,
        size=size,
        seed=args.seed,
        output=output,
        display_mode=args.display_mode,
    )
    print_generation_result(output, expected)
    return 0


def _deterministic_palette(count: int, seed: int) -> list[tuple[float, float, float, float]]:
    return [deterministic_color(index, seed) for index in range(count)]


def _resolve_preset(
    preset: str | None, variant: str, size: str, parser: argparse.ArgumentParser
) -> tuple[str, str]:
    if not preset:
        return variant, size
    for candidate_variant in VARIANTS:
        prefix = candidate_variant + "-"
        if preset.startswith(prefix):
            candidate_size = preset[len(prefix) :]
            if candidate_size in SIZES:
                return candidate_variant, candidate_size
    parser.error(f"invalid face-binding preset {preset!r}")
    raise AssertionError("argparse.error did not exit")


def _close_document(name: str) -> None:
    try:
        if App.getDocument(name) is not None:
            App.closeDocument(name)
    except (AttributeError, RuntimeError):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
