# SPDX-License-Identifier: LGPL-2.1-or-later

"""Lightweight parametric profiles for generated rectangular BIM openings."""

import FreeCAD


class RectangularOpeningProfile:
    """Generate ordered rectangular wires without invoking the Sketcher solver."""

    Type = "RectangularOpeningProfile"

    def __init__(self, obj):
        self.Object = obj
        self.setProperties(obj)
        obj.Proxy = self

    @staticmethod
    def setProperties(obj):
        if "Width" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "Width", "Opening Profile")
        if "Height" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "Height", "Opening Profile")
        if "ProfileInsets" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyFloatList",
                "ProfileInsets",
                "Opening Profile",
                "Left, right, bottom and top inset for each ordered wire",
            )
            obj.setEditorMode("ProfileInsets", 2)
        obj.setEditorMode("Width", 2)
        obj.setEditorMode("Height", 2)

    def onDocumentRestored(self, obj):
        self.Object = obj
        self.setProperties(obj)

    def dumps(self):
        return self.Type

    def loads(self, state):
        self.Type = state or "RectangularOpeningProfile"

    @staticmethod
    def setOpeningDimension(obj, name, value):
        """Update one supported profile dimension."""

        if name not in {"Width", "Height"}:
            return False
        setattr(obj, name, float(value))
        return True

    def execute(self, obj):
        import Part

        width = float(obj.Width.Value)
        height = float(obj.Height.Value)
        values = tuple(float(value) for value in obj.ProfileInsets)
        if width <= 0.0 or height <= 0.0 or not values or len(values) % 4:
            obj.Shape = Part.Shape()
            return

        wires = []
        for left, right, bottom, top in zip(
            values[0::4], values[1::4], values[2::4], values[3::4]
        ):
            x_min = left
            x_max = width - right
            y_min = bottom
            y_max = height - top
            if x_max <= x_min or y_max <= y_min:
                obj.Shape = Part.Shape()
                return
            points = (
                FreeCAD.Vector(x_min, y_min, 0.0),
                FreeCAD.Vector(x_max, y_min, 0.0),
                FreeCAD.Vector(x_max, y_max, 0.0),
                FreeCAD.Vector(x_min, y_max, 0.0),
            )
            wires.append(Part.makePolygon((*points, points[0])))
        obj.Shape = Part.makeCompound(wires)


def make_rectangular_opening_profile(
    width,
    height,
    profile_insets,
    placement=None,
    name="OpeningProfile",
    document=None,
):
    """Create a lightweight ordered rectangular opening profile."""

    document = document or FreeCAD.ActiveDocument
    if document is None:
        return None
    obj = document.addObject("Part::FeaturePython", name)
    RectangularOpeningProfile(obj)
    obj.Width = float(width)
    obj.Height = float(height)
    obj.ProfileInsets = tuple(
        coordinate for insets in profile_insets for coordinate in insets
    )
    if placement is not None:
        obj.Placement = FreeCAD.Placement(placement)
    return obj


def rectangular_profile_insets(shape, tolerance=1e-7):
    """Return ordered rectangular wire insets, or ``None`` for other profiles."""

    wires = tuple(getattr(shape, "Wires", ()) or ())
    if not wires:
        return None
    bounds = []
    for wire in wires:
        if len(wire.Edges) != 4 or len(wire.Vertexes) != 4:
            return None
        box = wire.BoundBox
        if box.ZLength > tolerance or box.XLength <= tolerance or box.YLength <= tolerance:
            return None
        expected_corners = (
            (box.XMin, box.YMin),
            (box.XMin, box.YMax),
            (box.XMax, box.YMin),
            (box.XMax, box.YMax),
        )
        for vertex in wire.Vertexes:
            point = vertex.Point
            if not any(
                abs(point.x - x) <= tolerance and abs(point.y - y) <= tolerance
                for x, y in expected_corners
            ):
                return None
        bounds.append((box.XMin, box.XMax, box.YMin, box.YMax))
    outer = max(bounds, key=lambda item: (item[1] - item[0]) * (item[3] - item[2]))
    x_min, x_max, y_min, y_max = outer
    insets = []
    for bx_min, bx_max, by_min, by_max in bounds:
        values = (bx_min - x_min, x_max - bx_max, by_min - y_min, y_max - by_max)
        if any(value < -tolerance for value in values):
            return None
        insets.append(tuple(max(0.0, value) for value in values))
    return (x_max - x_min, y_max - y_min, tuple(insets))


def replace_opening_sketch(opening, name="OpeningProfile"):
    """Replace a rectangular opening sketch while preserving wire ordering."""

    base = getattr(opening, "Base", None)
    shape = getattr(base, "Shape", None)
    if shape is not None:
        shape = shape.copy()
        shape.Placement = FreeCAD.Placement()
    resolved = rectangular_profile_insets(shape)
    if base is None or resolved is None:
        return None
    width, height, insets = resolved
    profile = make_rectangular_opening_profile(
        width,
        height,
        insets,
        placement=base.Placement,
        name=name,
        document=opening.Document,
    )
    if profile is None:
        return None
    profile.Label = "{} Profile".format(opening.Label)
    opening.Base = profile
    return profile
