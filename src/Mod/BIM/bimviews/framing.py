# SPDX-License-Identifier: LGPL-2.1-or-later

"""Deterministic camera framing for planar BIM representations."""

from dataclasses import dataclass

import FreeCAD


PLAN_FRAME_PADDING = 1.15


@dataclass(frozen=True)
class PlanarViewBounds:
    """World geometry bounds expressed in a planar view's local frame."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    @property
    def center(self):
        return FreeCAD.Vector(
            0.5 * (self.x_min + self.x_max),
            0.5 * (self.y_min + self.y_max),
            0.5 * (self.z_min + self.z_max),
        )

    @property
    def width(self):
        return self.x_max - self.x_min

    @property
    def height(self):
        return self.y_max - self.y_min

    @property
    def depth(self):
        return self.z_max - self.z_min


def planar_view_bounds(objects, frame=None):
    """Project visible document-shape bounds into a planar reference frame.

    Coin's scene bounds also contain transient helpers and unrelated visible
    objects.  Saved BIM views instead frame only their semantic document
    scope, making the captured camera independent of load order and overlays.
    """

    inverse = frame.inverse() if frame is not None else None
    coordinates = []
    for obj in objects or ():
        shape = getattr(obj, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        if bound_box is None:
            continue
        is_valid = getattr(bound_box, "isValid", None)
        if callable(is_valid) and not is_valid():
            continue
        for x in (bound_box.XMin, bound_box.XMax):
            for y in (bound_box.YMin, bound_box.YMax):
                for z in (bound_box.ZMin, bound_box.ZMax):
                    point = FreeCAD.Vector(x, y, z)
                    coordinates.append(inverse.multVec(point) if inverse else point)
    if not coordinates:
        return None
    return PlanarViewBounds(
        min(point.x for point in coordinates),
        max(point.x for point in coordinates),
        min(point.y for point in coordinates),
        max(point.y for point in coordinates),
        min(point.z for point in coordinates),
        max(point.z for point in coordinates),
    )


def frame_planar_view(view, bounds, frame=None, padding=PLAN_FRAME_PADDING):
    """Center an orthographic camera on projected bounds with stable padding."""

    try:
        camera = view.getCameraNode()
        viewport_width, viewport_height = view.getSize()
        if viewport_width <= 0 or viewport_height <= 0:
            return False
        aspect = float(viewport_width) / float(viewport_height)
        height = max(bounds.height, bounds.width / aspect, 1.0) * padding

        local_center = bounds.center
        world_center = frame.multVec(local_center) if frame is not None else local_center
        normal = (
            frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
            if frame is not None
            else FreeCAD.Vector(0, 0, 1)
        )
        position = camera.position.getValue()
        current = FreeCAD.Vector(position[0], position[1], position[2])
        distance = (current - world_center).dot(normal)
        minimum_distance = max(height, bounds.depth, 1.0)
        if distance <= minimum_distance:
            distance = 2.0 * minimum_distance

        camera.position.setValue(world_center + normal * distance)
        camera.height.setValue(height)
        camera.nearDistance.setValue(0.0)
        camera.farDistance.setValue(
            max(2.0 * distance, distance + 0.5 * bounds.depth + height)
        )
        camera.focalDistance.setValue(distance)
        return True
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return False
