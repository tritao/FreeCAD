# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-free hatch geometry generation shared by Draft and BIM."""

from contextlib import contextmanager

import FreeCAD as App
import Part
import TechDraw
from draftgeoutils.general import geomType


_TECHDRAW_DEBUG = "User parameter:BaseApp/Preferences/Mod/TechDraw/debug"


@contextmanager
def _allow_long_hatch_edges():
    """Temporarily disable TechDraw's 10 m edge rejection."""

    parameters = App.ParamGet(_TECHDRAW_DEBUG)
    existed = "allowCrazyEdge" in parameters.GetBools()
    previous = parameters.GetBool("allowCrazyEdge") if existed else None
    parameters.SetBool("allowCrazyEdge", True)
    try:
        yield
    finally:
        if existed:
            parameters.SetBool("allowCrazyEdge", previous)
        else:
            parameters.RemBool("allowCrazyEdge")


def _planar_face_frame(face):
    """Return a stable local XY frame for a planar face."""

    normal = face.normalAt(0, 0)
    for edge in face.Edges:
        if geomType(edge) != "Line":
            continue
        start = edge.firstVertex().Point
        direction = edge.lastVertex().Point.sub(start)
        if direction.Length <= 0.001:
            continue
        direction.normalize()
        lateral = normal.cross(direction)
        return App.Matrix(
            direction.x,
            lateral.x,
            normal.x,
            start.x,
            direction.y,
            lateral.y,
            normal.y,
            start.y,
            direction.z,
            lateral.z,
            normal.z,
            start.z,
            0.0,
            0.0,
            0.0,
            1.0,
        )
    center = face.CenterOfMass
    return App.Placement(center, App.Rotation(App.Vector(0, 0, 1), normal)).Matrix


def make_hatch_geometry(faces, filename, pattern, scale=1.0, rotation=0.0, translate=True):
    """Return PAT hatch geometry clipped to planar faces.

    No document objects are created. When ``translate`` is true, each face is
    transformed to a stable local XY frame before hatching and the result is
    transformed back into model coordinates. Non-planar faces are ignored.
    """

    rotation = float(getattr(rotation, "Value", rotation) or 0.0)
    faces = tuple(faces or ())
    shapes = []
    with _allow_long_hatch_edges():
        if not translate:
            planar_faces = tuple(face.copy() for face in faces if face.findPlane() is not None)
            if not planar_faces:
                return Part.Shape()
            source_shape = Part.makeCompound(planar_faces)
            if rotation:
                source_shape.rotate(App.Vector(), App.Vector(0, 0, 1), -rotation)
            shape = TechDraw.makeGeomHatch(
                source_shape,
                float(scale),
                str(pattern),
                str(filename),
            )
            if shape is None:
                return Part.Shape()
            if rotation:
                shape.rotate(App.Vector(), App.Vector(0, 0, 1), rotation)
            return shape
        for source_face in faces:
            if source_face.findPlane() is None:
                continue
            face = source_face.copy()
            frame = None
            if translate:
                frame = _planar_face_frame(face)
                face = face.transformShape(frame.inverse()).Faces[0]
            if rotation:
                face.rotate(App.Vector(), App.Vector(0, 0, 1), -rotation)
            shape = TechDraw.makeGeomHatch(
                face,
                float(scale),
                str(pattern),
                str(filename),
            )
            if rotation:
                shape.rotate(App.Vector(), App.Vector(0, 0, 1), rotation)
            if frame is not None:
                shape = shape.transformShape(frame)
            shapes.append(shape)
    return Part.makeCompound(shapes) if shapes else Part.Shape()
