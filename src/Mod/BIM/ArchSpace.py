# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2013 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

__title__ = "FreeCAD Arch Space"
__author__ = "Yorik van Havre"
__url__ = "https://www.freecad.org"

## @package ArchSpace
#  \ingroup ARCH
#  \brief The Space object and tools
#
#  This module provides tools to build Space objects.
#  Spaces define an open volume inside or outside a
#  building, ie. a room.

import math
import re

import FreeCAD
import ArchComponent
import ArchCommands
import ArchPlanGeometry
import Draft

from draftutils import params

if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui
    from PySide.QtCore import QT_TRANSLATE_NOOP
    import FreeCADGui
    from draftutils.translate import translate
else:
    # \cond
    def translate(ctxt, txt):
        return txt

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt

    # \endcond

SpaceTypes = [
    "Undefined",
    "Exterior",
    "Exterior - Terrace",
    "Office",
    "Office - Enclosed",
    "Office - Open Plan",
    "Conference / Meeting / Multipurpose",
    "Classroom / Lecture / Training For Penitentiary",
    "Lobby",
    "Lobby - For Hotel",
    "Lobby - For Performing Arts Theater",
    "Lobby - For Motion Picture Theater",
    "Audience/Seating Area",
    "Audience/Seating Area - For Gymnasium",
    "Audience/Seating Area - For Exercise Center",
    "Audience/Seating Area - For Convention Center",
    "Audience/Seating Area - For Penitentiary",
    "Audience/Seating Area - For Religious Buildings",
    "Audience/Seating Area - For Sports Arena",
    "Audience/Seating Area - For Performing Arts Theater",
    "Audience/Seating Area - For Motion Picture Theater",
    "Audience/Seating Area - For Transportation",
    "Atrium",
    "Atrium - First Three Floors",
    "Atrium - Each Additional Floor",
    "Lounge / Recreation",
    "Lounge / Recreation - For Hospital",
    "Dining Area",
    "Dining Area - For Penitentiary",
    "Dining Area - For Hotel",
    "Dining Area - For Motel",
    "Dining Area - For Bar Lounge/Leisure Dining",
    "Dining Area - For Family Dining",
    "Food Preparation",
    "Laboratory",
    "Restrooms",
    "Dressing / Locker / Fitting",
    "Room",
    "Corridor / Transition",
    "Corridor / Transition - For Hospital",
    "Corridor / Transition - For Manufacturing Facility",
    "Stairs",
    "Active Storage",
    "Active Storage - For Hospital",
    "Inactive Storage",
    "Inactive Storage - For Museum",
    "Electrical / Mechanical",
    "Gymnasium / Exercise Center",
    "Gymnasium / Exercise Center - Playing Area",
    "Gymnasium / Exercise Center - Exercise Area",
    "Courthouse / Police Station / Penitentiary",
    "Courthouse / Police Station / Penitentiary - Courtroom",
    "Courthouse / Police Station / Penitentiary - Confinement Cells",
    "Courthouse / Police Station / Penitentiary - Judges' Chambers",
    "Fire Stations",
    "Fire Stations - Engine Room",
    "Fire Stations - Sleeping Quarters",
    "Post Office - Sorting Area",
    "Convention Center - Exhibit Space",
    "Library",
    "Library - Card File and Cataloging",
    "Library - Stacks",
    "Library - Reading Area",
    "Hospital",
    "Hospital - Emergency",
    "Hospital - Recovery",
    "Hospital - Nurses' Station",
    "Hospital - Exam / Treatment",
    "Hospital - Pharmacy",
    "Hospital - Patient Room",
    "Hospital - Operating Room",
    "Hospital - Nursery",
    "Hospital - Medical Supply",
    "Hospital - Physical Therapy",
    "Hospital - Radiology",
    "Hospital - Laundry-Washing",
    "Automotive - Service / Repair",
    "Manufacturing",
    "Manufacturing - Low Bay (< 7.5m Floor to Ceiling Height)",
    "Manufacturing - High Bay (> 7.5m Floor to Ceiling Height)",
    "Manufacturing - Detailed Manufacturing",
    "Manufacturing - Equipment Room",
    "Manufacturing - Control Room",
    "Hotel / Motel Guest Rooms",
    "Dormitory - Living Quarters",
    "Museum",
    "Museum - General Exhibition",
    "Museum - Restoration",
    "Bank / Office - Banking Activity Area",
    "Workshop",
    "Sales Area",
    "Religious Buildings",
    "Religious Buildings - Worship Pulpit, Choir",
    "Religious Buildings - Fellowship Hall",
    "Retail",
    "Retail - Sales Area",
    "Retail - Mall Concourse",
    "Sports Arena",
    "Sports Arena - Ring Sports Area",
    "Sports Arena - Court Sports Area",
    "Sports Arena - Indoor Playing Field Area",
    "Warehouse",
    "Warehouse - Fine Material Storage",
    "Warehouse - Medium / Bulky Material Storage",
    "Parking Garage - Garage Area",
    "Transportation",
    "Transportation - Airport / Concourse",
    "Transportation - Air / Train / Bus - Baggage Area",
    "Transportation - Terminal - Ticket Counter",
]

ConditioningTypes = [
    "Unconditioned",
    "Heated",
    "Cooled",
    "HeatedAndCooled",
    "Vented",
    "NaturallyVentedOnly",
]

AreaCalculationType = ["XY-plane projection", "At Center of Mass"]


class _Space(ArchComponent.Component):
    "A space object"

    def __init__(self, obj):

        ArchComponent.Component.__init__(self, obj)
        self.Type = "Space"
        self._clear_boundary_failure()
        self.setProperties(obj)
        obj.IfcType = "Space"
        obj.CompositionType = "ELEMENT"

    def setProperties(self, obj):

        pl = obj.PropertiesList
        if not "Boundaries" in pl:
            obj.addProperty(
                "App::PropertyLinkSubList",
                "Boundaries",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The objects that make the boundaries of this space object"
                ),
                locked=True,
            )
        if not "Area" in pl:
            obj.addProperty(
                "App::PropertyArea",
                "Area",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "Identical to Horizontal Area"),
                locked=True,
            )
        if not "FinishFloor" in pl:
            obj.addProperty(
                "App::PropertyString",
                "FinishFloor",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The finishing of the floor of this space"),
                locked=True,
            )
        if not "FinishWalls" in pl:
            obj.addProperty(
                "App::PropertyString",
                "FinishWalls",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The finishing of the walls of this space"),
                locked=True,
            )
        if not "FinishCeiling" in pl:
            obj.addProperty(
                "App::PropertyString",
                "FinishCeiling",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The finishing of the ceiling of this space"),
                locked=True,
            )
        if not "Group" in pl:
            obj.addProperty(
                "App::PropertyLinkList",
                "Group",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Objects that are included inside this space, such as furniture",
                ),
                locked=True,
            )
        if not "SpaceType" in pl:
            obj.addProperty(
                "App::PropertyEnumeration",
                "SpaceType",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The type of this space"),
                locked=True,
            )
            obj.SpaceType = SpaceTypes
        if not "FloorThickness" in pl:
            obj.addProperty(
                "App::PropertyLength",
                "FloorThickness",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The thickness of the floor finish"),
                locked=True,
            )
        if not "NumberOfPeople" in pl:
            obj.addProperty(
                "App::PropertyInteger",
                "NumberOfPeople",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The number of people who typically occupy this space"
                ),
                locked=True,
            )
        if not "LightingPower" in pl:
            obj.addProperty(
                "App::PropertyFloat",
                "LightingPower",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The electric power needed to light this space in Watts"
                ),
                locked=True,
            )
        if not "EquipmentPower" in pl:
            obj.addProperty(
                "App::PropertyFloat",
                "EquipmentPower",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The electric power needed by the equipment of this space in Watts",
                ),
                locked=True,
            )
        if not "AutoPower" in pl:
            obj.addProperty(
                "App::PropertyBool",
                "AutoPower",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "If True, Equipment Power will be automatically filled by the equipment included in this space",
                ),
                locked=True,
            )
        if not "Conditioning" in pl:
            obj.addProperty(
                "App::PropertyEnumeration",
                "Conditioning",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The type of air conditioning of this space"),
                locked=True,
            )
            obj.Conditioning = ConditioningTypes
        if not "Internal" in pl:
            obj.addProperty(
                "App::PropertyBool",
                "Internal",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Specifies if this space is internal or external"
                ),
                locked=True,
            )
            obj.Internal = True
        if not "AreaCalculationType" in pl:
            obj.addProperty(
                "App::PropertyEnumeration",
                "AreaCalculationType",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Defines the calculation type for the horizontal area and its perimeter length",
                ),
                locked=True,
            )
            obj.AreaCalculationType = AreaCalculationType

    def onDocumentRestored(self, obj):

        ArchComponent.Component.onDocumentRestored(self, obj)
        self._clear_boundary_failure()
        self.setProperties(obj)

    def loads(self, state):

        self.Type = "Space"
        self._clear_boundary_failure()

    def execute(self, obj):

        if self.clone(obj):
            return

        # Space can do without Base.  Base validity is tested in getShape() code below.
        # Remarked out ensureBase() below
        # if not self.ensureBase(obj):
        #    return
        self.getShape(obj)

    def onChanged(self, obj, prop):

        if prop == "Group":
            if hasattr(obj, "EquipmentPower"):
                if obj.AutoPower:
                    p = 0
                    for o in Draft.getObjectsOfType(
                        Draft.get_group_contents(obj.Group, addgroups=True), "Equipment"
                    ):
                        if hasattr(o, "EquipmentPower"):
                            p += o.EquipmentPower
                    if p != obj.EquipmentPower:
                        obj.EquipmentPower = p
        elif prop == "Zone":
            if obj.Zone:
                if obj.Zone.ViewObject:
                    if hasattr(obj.Zone.ViewObject, "Proxy"):
                        if hasattr(obj.Zone.ViewObject.Proxy, "claimChildren"):
                            obj.Zone.ViewObject.Proxy.claimChildren()
        if hasattr(obj, "Area"):
            obj.setEditorMode("Area", 1)
        ArchComponent.Component.onChanged(self, obj, prop)

    def addSubobjects(self, obj, subobjects):
        "adds subobjects to this space"
        objs = obj.Boundaries
        for o in subobjects:
            if isinstance(o, tuple) or isinstance(o, list):
                if o[0].Name != obj.Name:
                    objs.append(tuple(o))
            else:
                for el in o.SubElementNames:
                    if "Face" in el:
                        if o.Object.Name != obj.Name:
                            objs.append((o.Object, el))
        obj.Boundaries = objs

    def removeSubobjects(self, obj, subobjects):
        "removes subobjects to this space"
        bounds = obj.Boundaries
        for o in subobjects:
            for b in bounds:
                if o.Name == b[0].Name:
                    bounds.remove(b)
                    break
        obj.Boundaries = bounds

    def addObject(self, obj, child):
        "Adds an object to this Space"

        if not child in obj.Group:
            g = obj.Group
            g.append(child)
            obj.Group = g

    def _clear_boundary_failure(self):
        self._last_boundary_error = ""
        self._last_boundary_error_details = []

    def _set_boundary_failure(self, message="", details=None):
        self._last_boundary_error = str(message or "").strip()
        self._last_boundary_error_details = [
            str(detail).strip() for detail in details or [] if str(detail).strip()
        ]

    def getLastBoundaryError(self, obj=None):
        return getattr(self, "_last_boundary_error", "")

    def getLastBoundaryErrorDetails(self, obj=None):
        return list(getattr(self, "_last_boundary_error_details", []))

    def _get_shape_horizontal_slice_edges(self, shape, cut_z):
        return self._merge_shape_slice_edges(
            shape, ArchComponent.get_horizontal_slice_edges(shape, cut_z)
        )

    def _get_horizontal_slice_edges(self, shapes, cut_z):
        section_edges = []
        for shape in shapes or []:
            section_edges.extend(self._get_shape_horizontal_slice_edges(shape, cut_z))
        return section_edges

    def _get_slice_edge_curve_type(self, edge):
        curve = getattr(edge, "Curve", None)
        return curve.__class__.__name__ if curve is not None else ""

    def _get_slice_edge_direction(self, edge):
        vertexes = list(getattr(edge, "Vertexes", []) or [])
        if len(vertexes) < 2:
            return None
        direction = vertexes[-1].Point.sub(vertexes[0].Point)
        if direction.Length <= 0.000001:
            return None
        direction.normalize()
        return direction

    def _get_linear_slice_edge_merge_data(self, edge):
        curve = getattr(edge, "Curve", None)
        if self._get_slice_edge_curve_type(edge) != "Line" or curve is None:
            return None
        direction = self._get_slice_edge_direction(edge)
        if direction is None:
            return None
        point = getattr(curve, "Location", None)
        if point is None:
            vertexes = list(getattr(edge, "Vertexes", []) or [])
            if len(vertexes) < 2:
                return None
            point = vertexes[0].Point
        try:
            return FreeCAD.Vector(point), FreeCAD.Vector(direction)
        except Exception:
            return None

    def _get_circular_slice_edge_merge_data(self, edge):
        curve = getattr(edge, "Curve", None)
        if self._get_slice_edge_curve_type(edge) != "Circle" or curve is None:
            return None
        center = getattr(curve, "Center", None)
        axis = getattr(curve, "Axis", None)
        radius = getattr(curve, "Radius", None)
        if center is None or axis is None or radius is None:
            return None
        axis = FreeCAD.Vector(axis)
        if axis.Length <= 0.000001:
            return None
        axis.normalize()
        return FreeCAD.Vector(center), axis, float(radius)

    def _can_merge_slice_edges(self, edge, other, tolerance=0.001):
        if self._get_slice_edge_curve_type(edge) != self._get_slice_edge_curve_type(other):
            return False

        linear_data = self._get_linear_slice_edge_merge_data(edge)
        other_linear_data = self._get_linear_slice_edge_merge_data(other)
        if linear_data and other_linear_data:
            point, direction = linear_data
            other_point, other_direction = other_linear_data
            if abs(abs(direction.dot(other_direction)) - 1.0) > 0.0001:
                return False
            distance = direction.cross(other_point.sub(point)).Length
            return distance <= tolerance

        circular_data = self._get_circular_slice_edge_merge_data(edge)
        other_circular_data = self._get_circular_slice_edge_merge_data(other)
        if circular_data and other_circular_data:
            center, axis, radius = circular_data
            other_center, other_axis, other_radius = other_circular_data
            if center.sub(other_center).Length > tolerance:
                return False
            if abs(abs(axis.dot(other_axis)) - 1.0) > 0.0001:
                return False
            return abs(radius - other_radius) <= tolerance

        return False

    def _merge_linear_slice_edges(self, edges, tolerance=0.001):
        import Part

        data = self._get_linear_slice_edge_merge_data(edges[0])
        if data is None:
            return list(edges)
        origin, direction = data
        distances = []
        for edge in edges:
            for vertex in getattr(edge, "Vertexes", []) or []:
                distances.append(direction.dot(vertex.Point.sub(origin)))
        if not distances:
            return list(edges)
        start_offset = FreeCAD.Vector(direction)
        start_offset.multiply(min(distances))
        end_offset = FreeCAD.Vector(direction)
        end_offset.multiply(max(distances))
        start = origin.add(start_offset)
        end = origin.add(end_offset)
        if start.distanceToPoint(end) <= tolerance:
            return list(edges)
        try:
            return [Part.makeLine(start, end)]
        except Exception:
            return list(edges)

    def _merge_circular_slice_edges(self, edges, tolerance=0.001):
        import Part

        data = self._get_circular_slice_edge_merge_data(edges[0])
        if data is None:
            return list(edges)
        _center, _axis, _radius = data
        circle = edges[0].Curve
        vertexes = [
            vertex.Point for edge in edges for vertex in getattr(edge, "Vertexes", []) or []
        ]
        if len(vertexes) < 2:
            return list(edges)

        try:
            base_param = float(circle.parameter(vertexes[0]))
        except Exception:
            return list(edges)

        params = []
        for point in vertexes:
            try:
                param = float(circle.parameter(point))
            except Exception:
                return list(edges)
            while param < base_param - math.pi:
                param += math.tau
            while param > base_param + math.pi:
                param -= math.tau
            params.append(param)
        if not params:
            return list(edges)

        start_param = min(params)
        end_param = max(params)
        if abs(end_param - start_param) <= tolerance:
            return list(edges)
        try:
            return [Part.ArcOfCircle(circle, start_param, end_param).toShape()]
        except Exception:
            return list(edges)

    def _merge_slice_edge_group(self, edges, tolerance=0.001):
        if len(edges) < 2:
            return list(edges)
        curve_type = self._get_slice_edge_curve_type(edges[0])
        if curve_type == "Line":
            return self._merge_linear_slice_edges(edges, tolerance=tolerance)
        if curve_type == "Circle":
            return self._merge_circular_slice_edges(edges, tolerance=tolerance)
        return list(edges)

    def _merge_shape_slice_edges(self, shape, edges, tolerance=0.001):
        merged_edges = []
        pending = list(edges or [])
        while pending:
            edge = pending.pop(0)
            group = [edge]
            remaining = []
            for candidate in pending:
                if self._can_merge_slice_edges(edge, candidate, tolerance=tolerance):
                    group.append(candidate)
                else:
                    remaining.append(candidate)
            merged_edges.extend(self._merge_slice_edge_group(group, tolerance=tolerance))
            pending = remaining
        return merged_edges

    def _get_boundary_faces_from_links(self, boundaries):
        faces = []
        for boundary in boundaries or []:
            try:
                base_obj = boundary[0]
                subnames = boundary[1]
            except Exception:
                continue
            if not hasattr(base_obj, "Shape"):
                continue
            if isinstance(subnames, str):
                sub_iter = [subnames]
            else:
                sub_iter = list(subnames or [])
            for subname in sub_iter:
                subname = str(subname)
                if not subname.startswith("Face"):
                    continue
                try:
                    face_index = int(subname[4:]) - 1
                    faces.append(base_obj.Shape.Faces[face_index])
                except Exception:
                    continue
        return faces

    def _get_boundary_faces(self, obj):
        return self._get_boundary_faces_from_links(getattr(obj, "Boundaries", []) or [])

    def _copy_without_element_map(self, shape):
        if shape is None:
            return None
        try:
            return shape.copy(noElementMap=True)
        except TypeError:
            try:
                plain_shape = shape.copy()
                if getattr(plain_shape, "ElementMapSize", 0):
                    plain_shape.clearElementMap()
                return plain_shape
            except Exception:
                return shape
        except Exception:
            return shape

    def _copy_clean_slice_edge(self, edge):
        try:
            plain_edge = edge.copy()
            if getattr(plain_edge, "ElementMapSize", 0):
                plain_edge.clearElementMap()
            return plain_edge
        except Exception:
            return edge

    def _get_horizontal_slice_faces_from_edges(self, section_edges):
        import Part

        if not section_edges or len(section_edges) < 4:
            return []
        plain_edges = [self._copy_clean_slice_edge(edge) for edge in section_edges]
        try:
            section_shape = Part.makeFace(plain_edges, "Part::FaceMakerBuildFace")
        except Exception:
            return []
        if not section_shape or section_shape.isNull():
            return []
        faces = []
        for face in getattr(section_shape, "Faces", []) or []:
            if getattr(face, "Area", 0.0) <= 0.000001:
                continue
            faces.append(face)
        if len(faces) < 2:
            return faces

        top_level_faces = []
        for face in faces:
            sample = self._get_wire_face_sample_point(face)
            if sample is None:
                top_level_faces.append(face)
                continue
            parent_candidates = []
            for other in faces:
                if other is face or other.Area <= face.Area + 0.000001:
                    continue
                try:
                    if other.isInside(sample, 0.001, True):
                        parent_candidates.append(other)
                except Exception:
                    continue
            if not parent_candidates:
                top_level_faces.append(face)
        return top_level_faces

    def _get_wire_identity(self, wire, precision=6):
        points = {
            (
                round(vertex.Point.x, precision),
                round(vertex.Point.y, precision),
                round(vertex.Point.z, precision),
            )
            for vertex in getattr(wire, "Vertexes", []) or []
        }
        if not points:
            return ()
        return tuple(sorted(points))

    def _get_horizontal_slice_wires(self, shapes, cut_z):
        import Part

        section_edges = self._get_horizontal_slice_edges(shapes, cut_z)
        if not section_edges:
            return []

        build_faces = self._get_horizontal_slice_faces_from_edges(section_edges)
        if build_faces:
            wires = []
            seen = set()
            for face in build_faces:
                for wire in getattr(face, "Wires", []) or []:
                    if not wire.isClosed() or len(wire.Vertexes) < 3:
                        continue
                    identity = self._get_wire_identity(wire)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    wires.append(wire)
            if wires:
                return wires

        plain_edges = [self._copy_clean_slice_edge(edge) for edge in section_edges]
        try:
            edge_groups = Part.sortEdges(plain_edges)
        except AttributeError:
            edge_groups = Part.__sortEdges__(plain_edges)

        if edge_groups and hasattr(edge_groups[0], "ShapeType"):
            edge_groups = [edge_groups]

        wires = []
        for edges in edge_groups or []:
            try:
                wire = Part.Wire(edges)
            except Exception:
                continue
            if not wire.isClosed() or len(wire.Vertexes) < 3:
                continue
            wires.append(wire)
        return wires

    def _get_wire_face_sample_point(self, face):
        try:
            points, triangles = face.tessellate(1.0)
        except Exception:
            points, triangles = ([], [])
        if triangles:
            p1 = FreeCAD.Vector(points[triangles[0][0]])
            p2 = FreeCAD.Vector(points[triangles[0][1]])
            p3 = FreeCAD.Vector(points[triangles[0][2]])
            return p1.add(p2).add(p3).multiply(1.0 / 3.0)
        center = getattr(face, "CenterOfMass", None)
        if center is not None:
            return FreeCAD.Vector(center)
        return None

    def _classify_wire_records(self, wires):
        import Part

        records = []
        for wire in wires or []:
            try:
                face = Part.Face(wire)
            except Exception:
                continue
            if face.Area <= 0.000001:
                continue
            sample_point = self._get_wire_face_sample_point(face)
            if sample_point is None:
                continue
            records.append(
                {
                    "wire": wire,
                    "face": face,
                    "area": float(face.Area),
                    "sample": sample_point,
                    "parent": None,
                    "depth": 0,
                }
            )
        if not records:
            return []

        for record in records:
            parent_candidates = []
            for other in records:
                if other is record or other["area"] <= record["area"] + 0.000001:
                    continue
                try:
                    if other["face"].isInside(record["sample"], 0.001, True):
                        parent_candidates.append(other)
                except Exception:
                    continue
            if parent_candidates:
                record["parent"] = min(parent_candidates, key=lambda item: item["area"])
                record["depth"] = len(parent_candidates)
        return records

    def _build_faces_from_wires(self, wires, require_single_outer=False):

        records = self._classify_wire_records(wires)
        if not records:
            return []

        return self._build_faces_from_records(records, require_single_outer=require_single_outer)

    def _build_faces_from_records(self, records, require_single_outer=False):
        if require_single_outer:
            top_level = [record for record in records if record["depth"] == 0]
            nested_islands = [
                record for record in records if record["depth"] > 0 and record["depth"] % 2 == 0
            ]
            if len(top_level) != 1 or nested_islands:
                return []
            outer = top_level[0]
            wires_for_face = [outer["wire"]]
            wires_for_face.extend(
                record["wire"]
                for record in records
                if record["parent"] is outer and record["depth"] == 1
            )
            try:
                return [ArchCommands.makeFace(wires_for_face)]
            except Exception:
                return []

        faces = []
        for outer in [record for record in records if record["depth"] % 2 == 0]:
            wires_for_face = [outer["wire"]]
            wires_for_face.extend(
                record["wire"]
                for record in records
                if record["parent"] is outer and record["depth"] == outer["depth"] + 1
            )
            try:
                face = ArchCommands.makeFace(wires_for_face)
            except Exception:
                continue
            if getattr(face, "Area", 0.0) > 0.000001:
                faces.append(face)
        return faces

    def _get_boundary_vertical_overlap(self, boundary_faces):
        z_min = None
        z_max = None
        for face in boundary_faces or []:
            bound_box = getattr(face, "BoundBox", None)
            if bound_box is None:
                continue
            if z_min is None:
                z_min = float(bound_box.ZMin)
                z_max = float(bound_box.ZMax)
                continue
            z_min = max(z_min, float(bound_box.ZMin))
            z_max = min(z_max, float(bound_box.ZMax))
        return z_min, z_max

    def _get_seed_boundary_overlap_cut_z(self, space, boundary_faces):
        shape = getattr(space, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        if bound_box is None:
            return None

        z_min = float(bound_box.ZMin)
        z_max = float(bound_box.ZMax)
        overlap_min, overlap_max = self._get_boundary_vertical_overlap(boundary_faces)
        if overlap_min is not None:
            z_min = max(z_min, float(overlap_min))
        if overlap_max is not None:
            z_max = min(z_max, float(overlap_max))
        if z_max - z_min <= 0.000001:
            return None
        return 0.5 * (z_min + z_max)

    def _get_seed_space_splitter_points(self, space, boundary_faces):
        if not boundary_faces:
            return []

        cut_z = self._get_seed_boundary_overlap_cut_z(space, boundary_faces)
        if cut_z is None:
            return []

        splitter_points = []
        for edge in self._get_horizontal_slice_edges(boundary_faces, cut_z):
            for vertex in getattr(edge, "Vertexes", []) or []:
                point = getattr(vertex, "Point", None)
                if point is None:
                    continue
                splitter_points.append(FreeCAD.Vector(point.x, point.y, point.z))
        return splitter_points

    def _split_seed_space_footprint_edge(self, edge, splitter_points, target_z, tolerance=0.001):
        import Part

        vertexes = list(getattr(edge, "Vertexes", []) or [])
        curve = getattr(edge, "Curve", None)
        if len(vertexes) != 2 or curve.__class__.__name__ != "Line":
            clean_edge = self._copy_without_element_map(edge)
            return [clean_edge] if clean_edge is not None else [edge]

        start = FreeCAD.Vector(vertexes[0].Point.x, vertexes[0].Point.y, target_z)
        end = FreeCAD.Vector(vertexes[1].Point.x, vertexes[1].Point.y, target_z)
        direction = end.sub(start)
        length_sq = direction.dot(direction)
        if length_sq <= tolerance * tolerance:
            return []

        parameters = [0.0, 1.0]
        for point in splitter_points or []:
            projected = FreeCAD.Vector(point.x, point.y, target_z)
            t = direction.dot(projected.sub(start)) / length_sq
            if t <= tolerance or t >= 1.0 - tolerance:
                continue
            closest = start.add(direction.multiply(t))
            if closest.distanceToPoint(projected) > max(tolerance, math.sqrt(length_sq) * 1e-6):
                continue
            parameters.append(float(t))

        parameters = sorted(set(round(value, 9) for value in parameters))
        edges = []
        for param_a, param_b in zip(parameters, parameters[1:]):
            if param_b - param_a <= 1e-9:
                continue
            segment_start = start.add(direction.multiply(param_a))
            segment_end = start.add(direction.multiply(param_b))
            if segment_start.distanceToPoint(segment_end) <= tolerance:
                continue
            try:
                edges.append(Part.makeLine(segment_start, segment_end))
            except Exception:
                continue
        return edges

    def _make_seed_space_boundary_face(self, edge, height):
        import Part

        vertexes = list(getattr(edge, "Vertexes", []) or [])
        if len(vertexes) == 2 and getattr(edge, "Curve", None).__class__.__name__ == "Line":
            p1 = FreeCAD.Vector(vertexes[0].Point)
            p2 = FreeCAD.Vector(vertexes[1].Point)
            p3 = FreeCAD.Vector(p2.x, p2.y, p2.z + height)
            p4 = FreeCAD.Vector(p1.x, p1.y, p1.z + height)
            try:
                return Part.Face(Part.makePolygon([p1, p2, p3, p4, p1]))
            except Exception:
                return None

        try:
            clean_edge = self._copy_without_element_map(edge)
            if clean_edge is None:
                return None
            upper = self._copy_without_element_map(clean_edge)
            if upper is None:
                return None
            upper.translate(FreeCAD.Vector(0, 0, height))
            return Part.makeRuledSurface(clean_edge, upper)
        except Exception:
            return None

    def _get_seed_space_boundary_faces(self, space, boundary_faces=None):
        shape = getattr(space, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        if shape is None or bound_box is None or float(bound_box.ZLength) <= 0.000001:
            return []

        shape_faces = []
        for face in getattr(shape, "Faces", []) or []:
            face_bb = getattr(face, "BoundBox", None)
            if face_bb is None or float(face_bb.ZLength) <= 0.000001:
                continue
            if getattr(face, "Area", 0.0) <= 0.000001:
                continue
            shape_faces.append(face)
        if shape_faces:
            return shape_faces

        proxy = getattr(space, "Proxy", None)
        if not proxy or not hasattr(proxy, "getFootprint"):
            return []
        try:
            footprint_faces = list(proxy.getFootprint(space) or [])
        except Exception:
            return []
        if not footprint_faces:
            return []

        height = float(bound_box.ZLength)
        target_z = float(bound_box.ZMin)
        splitter_points = self._get_seed_space_splitter_points(space, boundary_faces)
        vertical_faces = []
        for footprint_face in footprint_faces:
            for wire in getattr(footprint_face, "Wires", []) or []:
                for edge in getattr(wire, "Edges", []) or []:
                    for lower in self._split_seed_space_footprint_edge(
                        edge,
                        splitter_points,
                        target_z,
                    ):
                        face = self._make_seed_space_boundary_face(lower, height)
                        if face and getattr(face, "Area", 0.0) > 0.000001:
                            vertical_faces.append(face)
        return vertical_faces

    def _is_space_object(self, obj):
        if not obj:
            return False
        try:
            if Draft.getType(obj) == "Space":
                return True
        except Exception:
            pass
        return getattr(obj, "IfcType", "") == "Space"

    @staticmethod
    def normalizeBoundarySubnames(subnames):
        """Normalize a boundary subname list down to explicit face references."""

        if isinstance(subnames, str):
            candidates = [subnames]
        else:
            candidates = list(subnames or [])
        return tuple(str(name) for name in candidates if str(name).startswith("Face"))

    @staticmethod
    def _get_boundary_entry_object_and_subnames(entry):
        if isinstance(entry, (tuple, list)):
            if not entry:
                return (None, ())
            obj = entry[0]
            subnames = entry[1] if len(entry) > 1 else ()
            return (obj, subnames)
        return (
            getattr(entry, "Object", None),
            getattr(entry, "SubElementNames", ()) or (),
        )

    @staticmethod
    def _get_excluded_boundary_object_names(exclude_objects):
        if exclude_objects is None:
            return set()
        if isinstance(exclude_objects, (list, tuple, set)):
            candidates = list(exclude_objects)
        else:
            candidates = [exclude_objects]
        return {getattr(obj, "Name", None) for obj in candidates if getattr(obj, "Name", None)}

    def _get_wall_boundary_face_name(self, wall, reference_point):
        if not wall:
            return None
        try:
            if Draft.getType(wall) != "Wall":
                return None
        except Exception:
            return None
        if reference_point is None:
            return None

        shape = getattr(wall, "Shape", None)
        if shape is None or not getattr(shape, "Faces", None):
            return None

        best_face_name = None
        best_sort_key = None
        reference_point = FreeCAD.Vector(reference_point.x, reference_point.y, reference_point.z)
        reference_z = float(reference_point.z)
        for index, face in enumerate(shape.Faces, start=1):
            try:
                normal_raw = face.normalAt(0, 0)
                center_raw = face.CenterOfMass
                bound_box = face.BoundBox
                normal = FreeCAD.Vector(normal_raw.x, normal_raw.y, normal_raw.z)
                center = FreeCAD.Vector(center_raw.x, center_raw.y, center_raw.z)
            except Exception:
                continue
            if normal.Length <= 1e-7:
                continue
            normal.normalize()
            if abs(normal.z) > 0.2:
                continue
            if bound_box is not None and (
                reference_z < (float(bound_box.ZMin) - 0.001)
                or reference_z > (float(bound_box.ZMax) + 0.001)
            ):
                continue
            facing_score = float(normal.dot(reference_point.sub(center)))
            if facing_score <= 1e-7:
                continue
            sort_key = (float(face.Area or 0.0), facing_score)
            if best_sort_key is None or sort_key > best_sort_key:
                best_sort_key = sort_key
                best_face_name = f"Face{index}"
        if best_sort_key is None:
            return None
        return best_face_name

    def getBoundaryFaceNamesForObject(self, obj, reference_point=None):
        """Return boundary face names for a supported object when no explicit subnames are given."""

        if not obj or self._is_space_object(obj):
            return ()
        try:
            obj_type = Draft.getType(obj)
        except Exception:
            obj_type = ""

        if obj_type == "SpaceSeparator":
            shape = getattr(obj, "Shape", None)
            if shape is None or not getattr(shape, "Faces", None):
                return ()
            return tuple(f"Face{index}" for index, _face in enumerate(shape.Faces, start=1))

        if obj_type == "Wall":
            face_name = self._get_wall_boundary_face_name(obj, reference_point)
            return (face_name,) if face_name else ()

        return ()

    def normalizeBoundaryLinks(self, boundaries, exclude_objects=None):
        """Merge and normalize boundary link-sub tuples into a stable PropertyLinkSubList form."""

        excluded_names = self._get_excluded_boundary_object_names(exclude_objects)
        merged = {}
        order = []
        for entry in boundaries or []:
            obj, subnames = self._get_boundary_entry_object_and_subnames(entry)
            if not obj or self._is_space_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in excluded_names:
                continue
            face_names = self.normalizeBoundarySubnames(subnames)
            if not face_names:
                continue
            if name not in merged:
                merged[name] = [obj, []]
                order.append(name)
            for face_name in face_names:
                if face_name not in merged[name][1]:
                    merged[name][1].append(face_name)
        return [(merged[name][0], tuple(merged[name][1])) for name in order]

    def resolveBoundaryLinks(self, entries, reference_point=None, exclude_objects=None):
        """Resolve selection-like entries into explicit boundary link-sub tuples."""

        boundaries = []
        for entry in entries or []:
            obj, subnames = self._get_boundary_entry_object_and_subnames(entry)
            if not obj:
                continue
            face_names = self.normalizeBoundarySubnames(subnames)
            if not face_names:
                face_names = self.getBoundaryFaceNamesForObject(
                    obj,
                    reference_point=reference_point,
                )
            if face_names:
                boundaries.append((obj, face_names))
        return self.normalizeBoundaryLinks(boundaries, exclude_objects=exclude_objects)

    def getBoundaryFacesFromLinks(self, boundaries, seed_space=None):
        boundary_links = list(boundaries or [])
        boundary_faces = list(self._get_boundary_faces_from_links(boundary_links))
        if seed_space is not None:
            boundary_faces.extend(
                self._get_seed_space_boundary_faces(
                    seed_space,
                    boundary_faces=boundary_faces,
                )
            )
        return boundary_faces

    def _analyze_boundary_loops(self, boundary_faces):
        analysis = {
            "bounding_box": self._get_boundary_bounding_box(boundary_faces),
            "cut_z": None,
            "shared_z_min": None,
            "shared_z_max": None,
            "section_edges": [],
            "wires": [],
            "records": [],
            "top_level": [],
            "nested_islands": [],
            "supports_single_outer": False,
        }
        bb = analysis["bounding_box"]
        if not boundary_faces or not bb or bb.ZLength <= 0.000001:
            return analysis

        shared_z_min, shared_z_max = self._get_boundary_vertical_overlap(boundary_faces)
        if (
            shared_z_min is None
            or shared_z_max is None
            or (shared_z_max - shared_z_min) <= 0.000001
        ):
            analysis.update({"shared_z_min": shared_z_min, "shared_z_max": shared_z_max})
            return analysis

        cut_z = 0.5 * (shared_z_min + shared_z_max)
        section_edges = self._get_horizontal_slice_edges(boundary_faces, cut_z)
        wires = self._get_horizontal_slice_wires(boundary_faces, cut_z) if section_edges else []
        records = self._classify_wire_records(wires) if wires else []
        top_level = [record for record in records if record["depth"] == 0]
        nested_islands = [
            record for record in records if record["depth"] > 0 and record["depth"] % 2 == 0
        ]

        analysis.update(
            {
                "cut_z": cut_z,
                "shared_z_min": shared_z_min,
                "shared_z_max": shared_z_max,
                "section_edges": section_edges,
                "wires": wires,
                "records": records,
                "top_level": top_level,
                "nested_islands": nested_islands,
                "supports_single_outer": len(top_level) == 1 and not nested_islands,
            }
        )
        return analysis

    def _describe_boundary_failure(
        self, label, boundary_faces, has_base_shape=False, loop_analysis=None
    ):
        label = str(label or translate("Arch", "Space"))
        if boundary_faces:
            analysis = loop_analysis or self._analyze_boundary_loops(boundary_faces)
            bb = analysis["bounding_box"]
            if not bb:
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries have no usable geometry.",
                    ).format(label=label),
                    [],
                )
            if bb.ZLength <= 0.000001:
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries have no height.",
                    ).format(label=label),
                    [
                        translate(
                            "Arch",
                            "Select vertical wall faces or room-bounding objects with height.",
                        )
                    ],
                )

            section_edges = analysis["section_edges"]
            if not section_edges:
                details = [
                    translate(
                        "Arch",
                        "Select room-bounding faces that span the storey height.",
                    )
                ]
                shared_z_min = analysis.get("shared_z_min")
                shared_z_max = analysis.get("shared_z_max")
                if (
                    shared_z_min is not None
                    and shared_z_max is not None
                    and (shared_z_max - shared_z_min) <= 0.000001
                ):
                    details = [
                        translate(
                            "Arch",
                            "Select boundaries that overlap vertically at the same storey height.",
                        )
                    ]
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries do not intersect the plan cut.",
                    ).format(label=label),
                    details,
                )

            wires = analysis["wires"]
            if not wires:
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries do not form a closed room loop.",
                    ).format(label=label),
                    [
                        translate(
                            "Arch",
                            "Select all enclosing walls or explicit boundary faces for the room.",
                        )
                    ],
                )

            top_level = analysis["top_level"]
            if len(top_level) > 1:
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries form multiple enclosed regions.",
                    ).format(label=label),
                    [
                        translate(
                            "Arch",
                            "Create one space per enclosed region, or select a single outer loop with optional inner void loops.",
                        )
                    ],
                )

            nested_islands = analysis["nested_islands"]
            if nested_islands:
                return (
                    translate(
                        "Arch",
                        "Arch Space '{label}' could not be created because the selected boundaries contain nested islands that cannot become one space.",
                    ).format(label=label),
                    [
                        translate(
                            "Arch",
                            "Use one outer loop with optional inner void loops, or split the selection into separate spaces.",
                        )
                    ],
                )

            return (
                translate(
                    "Arch",
                    "Arch Space '{label}' could not derive a valid solid from the selected boundaries.",
                ).format(label=label),
                [
                    translate(
                        "Arch",
                        "Check that the selected walls or faces fully enclose the room at plan level.",
                    )
                ],
            )

        if has_base_shape:
            return (
                translate(
                    "Arch",
                    "Arch Space '{label}' could not derive a valid solid from its base object.",
                ).format(label=label),
                [],
            )

        return (
            translate("Arch", "Arch Space '{label}' could not compute its boundary.").format(
                label=label
            ),
            [],
        )

    def _get_boundary_analysis_code(self, boundary_count, boundary_faces, loop_analysis):
        if not boundary_count:
            return "empty"
        if not boundary_faces:
            return "unusable_boundaries"

        bb = loop_analysis.get("bounding_box")
        if not bb:
            return "unusable_boundaries"
        if bb.ZLength <= 0.000001:
            return "no_height"
        if not loop_analysis.get("section_edges"):
            return "no_intersection"
        if not loop_analysis.get("wires"):
            return "open_loop"
        if len(loop_analysis.get("top_level", [])) > 1:
            return "multiple_regions"
        if loop_analysis.get("nested_islands"):
            return "nested_islands"
        if loop_analysis.get("supports_single_outer"):
            return "valid"
        return "invalid_solid"

    def analyzeBoundaryLinks(self, boundaries, label=None, seed_space=None):
        label = str(label or translate("Arch", "Space"))
        boundary_links = list(boundaries or [])
        boundary_faces = self.getBoundaryFacesFromLinks(
            boundary_links,
            seed_space=seed_space,
        )
        boundary_count = len(boundary_links) + (1 if seed_space is not None else 0)
        loop_analysis = self._analyze_boundary_loops(boundary_faces)
        code = self._get_boundary_analysis_code(
            boundary_count,
            boundary_faces,
            loop_analysis,
        )
        message = ""
        details = []
        if code not in ("empty", "valid"):
            message, details = self._describe_boundary_failure(
                label,
                boundary_faces,
                loop_analysis=loop_analysis,
            )
        inner_void_count = len(
            [record for record in loop_analysis.get("records", []) if record.get("depth") == 1]
        )
        return {
            "label": label,
            "code": code,
            "valid": code == "valid",
            "boundary_count": boundary_count,
            "face_count": len(boundary_faces),
            "region_count": len(loop_analysis.get("top_level", [])),
            "inner_void_count": inner_void_count,
            "message": message,
            "details": list(details),
        }

    def analyzeBoundaryFaces(self, boundary_faces, label=None, boundary_count=None):
        label = str(label or translate("Arch", "Space"))
        boundary_faces = list(boundary_faces or [])
        if boundary_count is None:
            boundary_count = len(boundary_faces)
        loop_analysis = self._analyze_boundary_loops(boundary_faces)
        code = self._get_boundary_analysis_code(
            int(boundary_count),
            boundary_faces,
            loop_analysis,
        )
        message = ""
        details = []
        if code not in ("empty", "valid"):
            message, details = self._describe_boundary_failure(
                label,
                boundary_faces,
                loop_analysis=loop_analysis,
            )
        inner_void_count = len(
            [record for record in loop_analysis.get("records", []) if record.get("depth") == 1]
        )
        return {
            "label": label,
            "code": code,
            "valid": code == "valid",
            "boundary_count": int(boundary_count),
            "face_count": len(boundary_faces),
            "region_count": len(loop_analysis.get("top_level", [])),
            "inner_void_count": inner_void_count,
            "message": message,
            "details": list(details),
        }

    def _build_face_from_region_record(self, records, outer_record):
        if not outer_record:
            return None
        wires_for_face = [outer_record["wire"]]
        wires_for_face.extend(
            record["wire"]
            for record in records or []
            if record.get("parent") is outer_record
            and record.get("depth") == outer_record.get("depth", 0) + 1
        )
        try:
            face = ArchCommands.makeFace(wires_for_face)
        except Exception:
            return None
        if not face or getattr(face, "Area", 0.0) <= 0.000001:
            return None
        return face

    def _build_shape_from_boundary_region(self, boundary_faces, outer_record, loop_analysis=None):
        if not boundary_faces or not outer_record:
            return None

        analysis = loop_analysis or self._analyze_boundary_loops(boundary_faces)
        bb = analysis.get("bounding_box")
        cut_z = analysis.get("cut_z")
        if not bb or cut_z is None or bb.ZLength <= 0.000001:
            return None

        footprint = self._build_face_from_region_record(analysis.get("records", []), outer_record)
        if footprint is None:
            return None

        footprint = self._copy_without_element_map(footprint)
        footprint.translate(FreeCAD.Vector(0, 0, bb.ZMin - cut_z))
        try:
            shape = footprint.extrude(FreeCAD.Vector(0, 0, bb.ZLength))
        except Exception:
            return None
        if not shape or not getattr(shape, "Solids", None):
            return None
        try:
            shape = shape.removeSplitter()
        except Exception:
            pass
        return shape.Solids[0] if len(shape.Solids) == 1 else shape

    def getBoundaryRegionCandidates(self, boundaries, label=None, seed_space=None):
        label = str(label or translate("Arch", "Space"))
        boundary_links = list(boundaries or [])
        boundary_faces = self.getBoundaryFacesFromLinks(
            boundary_links,
            seed_space=seed_space,
        )
        return self.getBoundaryFaceRegionCandidates(
            boundary_faces,
            label=label,
            boundary_count=len(boundary_links) + (1 if seed_space is not None else 0),
        )

    def getBoundaryFaceRegionCandidates(self, boundary_faces, label=None, boundary_count=None):
        label = str(label or translate("Arch", "Space"))
        boundary_faces = list(boundary_faces or [])
        if boundary_count is None:
            boundary_count = len(boundary_faces)
        loop_analysis = self._analyze_boundary_loops(boundary_faces)
        code = self._get_boundary_analysis_code(
            int(boundary_count),
            boundary_faces,
            loop_analysis,
        )

        message = ""
        details = []
        if code not in ("empty", "valid"):
            message, details = self._describe_boundary_failure(
                label,
                boundary_faces,
                loop_analysis=loop_analysis,
            )

        bb = loop_analysis.get("bounding_box")
        top_level = list(loop_analysis.get("top_level", []) or [])
        top_level.sort(
            key=lambda record: (
                -float(record.get("area", 0.0) or 0.0),
                round(getattr(record.get("sample"), "x", 0.0), 6),
                round(getattr(record.get("sample"), "y", 0.0), 6),
            )
        )

        candidates = []
        for index, outer_record in enumerate(top_level):
            face = self._build_face_from_region_record(
                loop_analysis.get("records", []), outer_record
            )
            shape = self._build_shape_from_boundary_region(
                boundary_faces,
                outer_record,
                loop_analysis=loop_analysis,
            )
            if face is None or shape is None:
                continue
            sample = outer_record.get("sample")
            sample_point = None
            if sample is not None:
                sample_point = FreeCAD.Vector(
                    sample.x,
                    sample.y,
                    bb.ZMin if bb is not None else sample.z,
                )
            candidates.append(
                {
                    "index": index,
                    "area": float(face.Area),
                    "face": face,
                    "shape": shape,
                    "sample_point": sample_point,
                    "wire_count": len(getattr(face, "Wires", []) or []),
                }
            )

        inner_void_count = len(
            [record for record in loop_analysis.get("records", []) if record.get("depth") == 1]
        )
        return {
            "label": label,
            "code": code,
            "valid": code == "valid",
            "boundary_count": int(boundary_count),
            "face_count": len(boundary_faces),
            "region_count": len(top_level),
            "inner_void_count": inner_void_count,
            "candidate_count": len(candidates),
            "message": message,
            "details": list(details),
            "candidates": candidates,
        }

    def _build_shape_from_boundary_loops(self, boundary_faces, loop_analysis=None):
        if not boundary_faces:
            return None

        analysis = loop_analysis or self._analyze_boundary_loops(boundary_faces)
        bb = analysis["bounding_box"]
        if not bb:
            return None
        if bb.ZLength <= 0.000001:
            return None

        if not analysis["supports_single_outer"]:
            return None

        cut_z = analysis["cut_z"]
        footprint_faces = self._build_faces_from_records(
            analysis["records"], require_single_outer=True
        )
        if len(footprint_faces) != 1:
            return None

        footprint = self._copy_without_element_map(footprint_faces[0])
        footprint.translate(FreeCAD.Vector(0, 0, bb.ZMin - cut_z))
        try:
            shape = footprint.extrude(FreeCAD.Vector(0, 0, bb.ZLength))
        except Exception:
            return None
        if not shape or not getattr(shape, "Solids", None):
            return None
        try:
            shape = shape.removeSplitter()
        except Exception:
            pass
        return shape.Solids[0] if len(shape.Solids) == 1 else shape

    def _get_boundary_bounding_box(self, boundary_faces):
        bb = None
        for face in boundary_faces or []:
            if bb is None:
                bb = face.BoundBox
            else:
                bb.add(face.BoundBox)
        return bb

    def getShape(self, obj):
        "computes a shape from a base shape and/or boundary faces"
        import Part

        self._clear_boundary_failure()
        shape = None
        boundary_faces = self._get_boundary_faces(obj)
        loop_analysis = self._analyze_boundary_loops(boundary_faces) if boundary_faces else None
        pl = obj.Placement

        # print("starting compute")

        if boundary_faces and loop_analysis and loop_analysis["supports_single_outer"]:
            loop_shape = self._build_shape_from_boundary_loops(
                boundary_faces, loop_analysis=loop_analysis
            )
            if loop_shape is not None:
                shape = self.processSubShapes(obj, loop_shape.Solids[0], pl)
                self.applyShape(obj, shape, pl)
                self._sync_area_properties(obj)
                return

        # 1: if we have a base shape, we use it
        # Check if there is obj.Base and its validity to proceed
        has_base_shape = self.ensureBase(obj) and obj.Base.Shape.Solids
        if has_base_shape:
            if obj.Base.Shape.Solids:
                shape = obj.Base.Shape.copy()
                shape = shape.removeSplitter()

        # 2: if not, add all bounding boxes of considered objects and build a first shape
        if shape:
            # print("got shape from base object")
            bb = shape.BoundBox
            if loop_analysis and len(loop_analysis.get("top_level", [])) > 1:
                shape = self.processSubShapes(obj, shape.Solids[0], pl)
                self.applyShape(obj, shape, pl)
                self._sync_area_properties(obj)
                return
        else:
            if boundary_faces and not loop_analysis["supports_single_outer"]:
                label = str(
                    getattr(obj, "Label", "")
                    or getattr(obj, "Name", "")
                    or translate("Arch", "Space")
                )
                message, details = self._describe_boundary_failure(
                    label,
                    boundary_faces,
                    has_base_shape=has_base_shape,
                    loop_analysis=loop_analysis,
                )
                self._set_boundary_failure(message, details)
                if message:
                    FreeCAD.Console.PrintError(message + "\n")
                    for detail in details:
                        FreeCAD.Console.PrintError(f"  - {detail}\n")
                return
            bb = self._get_boundary_bounding_box(boundary_faces)
            if not bb:
                # compute area even if we are not calculating the shape
                if obj.Shape and obj.Shape.Solids:
                    if hasattr(obj.Area, "Value"):
                        a = self.getArea(obj)
                        if obj.Area.Value != a:
                            obj.Area = a
                return
            shape = Part.makeBox(
                bb.XLength, bb.YLength, bb.ZLength, FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin)
            )
            # print("created shape from boundbox")

        # 3: identifying boundary faces
        faces = list(boundary_faces)

        # print("total: ", len(faces), " faces")

        # 4: get cutvolumes from faces
        cutvolumes = []
        for f in faces:
            f = self._copy_without_element_map(f)
            f.reverse()
            cutface, cutvolume, invcutvolume = ArchCommands.getCutVolume(f, shape)
            if cutvolume:
                # print("generated 1 cutvolume")
                cutvolumes.append(self._copy_without_element_map(cutvolume))
                # Part.show(cutvolume)
        for v in cutvolumes:
            # print("cutting")
            shape = shape.cut(v)

        # 5: get the final shape
        if shape:
            if shape.Solids:
                # print("setting objects shape")
                shape = self.processSubShapes(obj, shape.Solids[0], pl)
                self.applyShape(obj, shape, pl)
                self._sync_area_properties(obj)

                return

        label = str(
            getattr(obj, "Label", "") or getattr(obj, "Name", "") or translate("Arch", "Space")
        )
        message, details = self._describe_boundary_failure(
            label, boundary_faces, has_base_shape=has_base_shape
        )
        self._set_boundary_failure(message, details)
        if message:
            FreeCAD.Console.PrintError(message + "\n")
            for detail in details:
                FreeCAD.Console.PrintError(f"  - {detail}\n")

    def getArea(self, obj, notouch=False):
        "returns the horizontal area at the center of the space"

        faces = self.getFootprint(obj)
        self.face = max(faces, key=lambda face: face.Area) if faces else None
        if self.face:
            if not notouch:
                if hasattr(obj, "PerimeterLength"):
                    perimeter = sum(wire.Length for face in faces for wire in face.Wires)
                    if abs(perimeter - obj.PerimeterLength.Value) > 0.000001:
                        obj.PerimeterLength = perimeter
            return sum(face.Area for face in faces)
        else:
            return 0

    def _sync_area_properties(self, obj):
        """Keep the user-facing space area aligned with the available footprint."""

        if not hasattr(obj, "Area"):
            return

        area_mode = getattr(obj, "AreaCalculationType", "")
        horizontal_area = getattr(getattr(obj, "HorizontalArea", None), "Value", None)
        area_value = horizontal_area

        if area_mode == "At Center of Mass":
            area_value = self.getArea(obj)
            if hasattr(obj, "HorizontalArea") and (
                horizontal_area is None or abs(horizontal_area - area_value) > 0.000001
            ):
                obj.HorizontalArea = area_value
        elif horizontal_area is None or horizontal_area <= 0.000001:
            # A valid space footprint can still exist even when the generic XY projection
            # path fails. Fall back so the space label does not stay at 0 m2.
            footprint_area = self.getArea(obj)
            if footprint_area > 0.000001:
                area_value = footprint_area

        if area_value is None:
            return
        if hasattr(obj.Area, "Value"):
            if abs(obj.Area.Value - area_value) > 0.000001:
                obj.Area = area_value
        elif obj.Area != area_value:
            obj.Area = area_value

    def getFootprint(self, obj):
        "returns footprint faces for this space at the center of mass"

        import Part

        if not hasattr(obj.Shape, "CenterOfMass"):
            return []
        try:
            cut_z = float(obj.Shape.CenterOfMass.z)
        except Exception:
            cut_z = float(obj.Shape.BoundBox.Center.z)
        try:
            faces = self._build_faces_from_wires(
                self._get_horizontal_slice_wires(
                    [self._copy_without_element_map(obj.Shape)],
                    cut_z,
                )
            )
            if faces:
                translate_z = obj.Shape.BoundBox.ZMin - cut_z
                if abs(translate_z) > 0.000001:
                    for face in faces:
                        face.translate(FreeCAD.Vector(0, 0, translate_z))
                return faces
        except Part.OCCError:
            pass
        try:
            pl = Part.makePlane(1, 1)
            pl.translate(obj.Shape.CenterOfMass)
            sh = self._copy_without_element_map(obj.Shape)
            cutplane, v1, v2 = ArchCommands.getCutVolume(pl, sh)
            e = sh.section(cutplane)
            e = Part.__sortEdges__(e.Edges)
            w = Part.Wire(e)
            dv = FreeCAD.Vector(
                obj.Shape.CenterOfMass.x, obj.Shape.CenterOfMass.y, obj.Shape.BoundBox.ZMin
            )
            dv = dv.sub(obj.Shape.CenterOfMass)
            w.translate(dv)
            return [Part.Face(w)]
        except Part.OCCError:
            return []


class _SpaceBoundaryAnalyzer:
    """Reusable boundary analysis helper for Plan Edit and tests."""

    _get_shape_horizontal_slice_edges = _Space._get_shape_horizontal_slice_edges
    _get_horizontal_slice_edges = _Space._get_horizontal_slice_edges
    _get_slice_edge_curve_type = _Space._get_slice_edge_curve_type
    _get_slice_edge_direction = _Space._get_slice_edge_direction
    _get_linear_slice_edge_merge_data = _Space._get_linear_slice_edge_merge_data
    _get_circular_slice_edge_merge_data = _Space._get_circular_slice_edge_merge_data
    _can_merge_slice_edges = _Space._can_merge_slice_edges
    _merge_linear_slice_edges = _Space._merge_linear_slice_edges
    _merge_circular_slice_edges = _Space._merge_circular_slice_edges
    _merge_slice_edge_group = _Space._merge_slice_edge_group
    _merge_shape_slice_edges = _Space._merge_shape_slice_edges
    _get_boundary_faces_from_links = _Space._get_boundary_faces_from_links
    _copy_without_element_map = _Space._copy_without_element_map
    _copy_clean_slice_edge = _Space._copy_clean_slice_edge
    _get_horizontal_slice_faces_from_edges = _Space._get_horizontal_slice_faces_from_edges
    _get_wire_identity = _Space._get_wire_identity
    _get_horizontal_slice_wires = _Space._get_horizontal_slice_wires
    _get_wire_face_sample_point = _Space._get_wire_face_sample_point
    _classify_wire_records = _Space._classify_wire_records
    _build_faces_from_wires = _Space._build_faces_from_wires
    _build_faces_from_records = _Space._build_faces_from_records
    _get_boundary_vertical_overlap = _Space._get_boundary_vertical_overlap
    _get_seed_boundary_overlap_cut_z = _Space._get_seed_boundary_overlap_cut_z
    _get_seed_space_splitter_points = _Space._get_seed_space_splitter_points
    _split_seed_space_footprint_edge = _Space._split_seed_space_footprint_edge
    _make_seed_space_boundary_face = _Space._make_seed_space_boundary_face
    _get_seed_space_boundary_faces = _Space._get_seed_space_boundary_faces
    _is_space_object = _Space._is_space_object
    normalizeBoundarySubnames = staticmethod(_Space.normalizeBoundarySubnames)
    _get_boundary_entry_object_and_subnames = staticmethod(
        _Space._get_boundary_entry_object_and_subnames
    )
    _get_excluded_boundary_object_names = staticmethod(_Space._get_excluded_boundary_object_names)
    _get_wall_boundary_face_name = _Space._get_wall_boundary_face_name
    getBoundaryFaceNamesForObject = _Space.getBoundaryFaceNamesForObject
    normalizeBoundaryLinks = _Space.normalizeBoundaryLinks
    resolveBoundaryLinks = _Space.resolveBoundaryLinks
    getBoundaryFacesFromLinks = _Space.getBoundaryFacesFromLinks
    _analyze_boundary_loops = _Space._analyze_boundary_loops
    _describe_boundary_failure = _Space._describe_boundary_failure
    _get_boundary_analysis_code = _Space._get_boundary_analysis_code
    _get_boundary_bounding_box = _Space._get_boundary_bounding_box
    analyzeBoundaryLinks = _Space.analyzeBoundaryLinks
    analyzeBoundaryFaces = _Space.analyzeBoundaryFaces
    _build_face_from_region_record = _Space._build_face_from_region_record
    _build_shape_from_boundary_region = _Space._build_shape_from_boundary_region
    getBoundaryRegionCandidates = _Space.getBoundaryRegionCandidates
    getBoundaryFaceRegionCandidates = _Space.getBoundaryFaceRegionCandidates


_space_boundary_analyzer = _SpaceBoundaryAnalyzer()


def getBoundaryFacesFromLinks(boundaries, seed_space=None):
    """Expose boundary faces built from link-sub boundaries and an optional seed space."""

    return _space_boundary_analyzer.getBoundaryFacesFromLinks(
        boundaries,
        seed_space=seed_space,
    )


def normalizeBoundarySubnames(subnames):
    """Normalize boundary subnames down to explicit face references."""

    return _space_boundary_analyzer.normalizeBoundarySubnames(subnames)


def getBoundaryFaceNamesForObject(obj, reference_point=None):
    """Resolve implicit boundary faces for a supported object."""

    return _space_boundary_analyzer.getBoundaryFaceNamesForObject(
        obj,
        reference_point=reference_point,
    )


def normalizeBoundaryLinks(boundaries, exclude_objects=None):
    """Normalize and merge boundary links into explicit link-sub tuples."""

    return _space_boundary_analyzer.normalizeBoundaryLinks(
        boundaries,
        exclude_objects=exclude_objects,
    )


def resolveBoundaryLinks(entries, reference_point=None, exclude_objects=None):
    """Resolve selection-like entries into explicit boundary link-sub tuples."""

    return _space_boundary_analyzer.resolveBoundaryLinks(
        entries,
        reference_point=reference_point,
        exclude_objects=exclude_objects,
    )


def analyzeBoundaryLinks(boundaries, label=None, seed_space=None):
    """Analyze whether boundary links can form one Arch Space."""

    return _space_boundary_analyzer.analyzeBoundaryLinks(
        boundaries,
        label=label,
        seed_space=seed_space,
    )


def analyzeBoundaryFaces(boundary_faces, label=None, boundary_count=None):
    """Analyze whether boundary faces can form one Arch Space."""

    return _space_boundary_analyzer.analyzeBoundaryFaces(
        boundary_faces,
        label=label,
        boundary_count=boundary_count,
    )


def getBoundaryRegionCandidates(boundaries, label=None, seed_space=None):
    """Expose top-level enclosed regions derived from boundary links."""

    return _space_boundary_analyzer.getBoundaryRegionCandidates(
        boundaries,
        label=label,
        seed_space=seed_space,
    )


def getBoundaryFaceRegionCandidates(boundary_faces, label=None, boundary_count=None):
    """Expose top-level enclosed regions derived from boundary faces."""

    return _space_boundary_analyzer.getBoundaryFaceRegionCandidates(
        boundary_faces,
        label=label,
        boundary_count=boundary_count,
    )


class _ViewProviderSpace(ArchComponent.ViewProviderComponent):
    "A View Provider for Section Planes"

    def __init__(self, vobj):

        ArchComponent.ViewProviderComponent.__init__(self, vobj)
        self.setProperties(vobj)
        vobj.Transparency = params.get_param_arch("defaultSpaceTransparency")
        vobj.LineWidth = params.get_param_view("DefaultShapeLineWidth")
        vobj.LineColor = ArchCommands.getDefaultColor("Space")
        vobj.DrawStyle = ["Solid", "Dashed", "Dotted", "Dashdot"][
            params.get_param_arch("defaultSpaceStyle")
        ]

    def setProperties(self, vobj):

        pl = vobj.PropertiesList
        if not "Text" in pl:
            vobj.addProperty(
                "App::PropertyStringList",
                "Text",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The text to show. Use $area, $label, $longname, $description or any other property name preceded with $ (case insensitive), or $floor, $walls, $ceiling for finishes, to insert the respective data",
                ),
                locked=True,
            )
            vobj.Text = ["$label", "$area"]
        if not "FontName" in pl:
            vobj.addProperty(
                "App::PropertyFont",
                "FontName",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The name of the font"),
                locked=True,
            )
            vobj.FontName = params.get_param("textfont")
        if not "TextColor" in pl:
            vobj.addProperty(
                "App::PropertyColor",
                "TextColor",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The color of the area text"),
                locked=True,
            )
            vobj.TextColor = (0.0, 0.0, 0.0, 1.0)
        if not "FontSize" in pl:
            vobj.addProperty(
                "App::PropertyLength",
                "FontSize",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The size of the text font"),
                locked=True,
            )
            vobj.FontSize = params.get_param("textheight") * params.get_param(
                "DefaultAnnoScaleMultiplier"
            )
        if not "FirstLine" in pl:
            vobj.addProperty(
                "App::PropertyLength",
                "FirstLine",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The size of the first line of text"),
                locked=True,
            )
            vobj.FirstLine = params.get_param("textheight") * params.get_param(
                "DefaultAnnoScaleMultiplier"
            )
        if not "LineSpacing" in pl:
            vobj.addProperty(
                "App::PropertyFloat",
                "LineSpacing",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The space between the lines of text"),
                locked=True,
            )
            vobj.LineSpacing = 1.0
        if not "TextPosition" in pl:
            vobj.addProperty(
                "App::PropertyVectorDistance",
                "TextPosition",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The position of the text. Leave (0,0,0) for automatic position",
                ),
                locked=True,
            )
        if not "TextAlign" in pl:
            vobj.addProperty(
                "App::PropertyEnumeration",
                "TextAlign",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "The justification of the text"),
                locked=True,
            )
            vobj.TextAlign = ["Left", "Center", "Right"]
            vobj.TextAlign = "Center"
        if not "Decimals" in pl:
            vobj.addProperty(
                "App::PropertyInteger",
                "Decimals",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The number of decimals to use for calculated texts"
                ),
                locked=True,
            )
            vobj.Decimals = params.get_param("dimPrecision")
        if not "ShowUnit" in pl:
            vobj.addProperty(
                "App::PropertyBool",
                "ShowUnit",
                "Space",
                QT_TRANSLATE_NOOP("App::Property", "Show the unit suffix"),
                locked=True,
            )
            vobj.ShowUnit = params.get_param("showUnit")

    def onDocumentRestored(self, vobj):

        self.setProperties(vobj)

    def getIcon(self):

        import Arch_rc

        if hasattr(self, "Object"):
            if hasattr(self.Object, "CloneOf"):
                if self.Object.CloneOf:
                    return ":/icons/Arch_Space_Clone.svg"
        return ":/icons/Arch_Space_Tree.svg"

    def attach(self, vobj):

        ArchComponent.ViewProviderComponent.attach(self, vobj)
        from pivy import coin

        self.color = coin.SoBaseColor()
        self.font = coin.SoFont()
        self.text1 = coin.SoAsciiText()
        self.text1.string = " "
        self.text1.justification = coin.SoAsciiText.LEFT
        self.text2 = coin.SoAsciiText()
        self.text2.string = " "
        self.text2.justification = coin.SoAsciiText.LEFT
        self.coords = coin.SoTransform()
        self.header = coin.SoTransform()
        self.label = coin.SoSwitch()
        sep = coin.SoSeparator()
        self.label.whichChild = 0
        sep.addChild(self.coords)
        sep.addChild(self.color)
        sep.addChild(self.font)
        sep.addChild(self.text2)
        sep.addChild(self.header)
        sep.addChild(self.text1)
        self.label.addChild(sep)
        vobj.Annotation.addChild(self.label)
        self.onChanged(vobj, "TextColor")
        self.onChanged(vobj, "FontSize")
        self.onChanged(vobj, "FirstLine")
        self.onChanged(vobj, "LineColor")
        self.onChanged(vobj, "LineWidth")
        self.onChanged(vobj, "LineSpacing")
        self.onChanged(vobj, "DrawStyle")
        self.onChanged(vobj, "FontName")

    def createFootprintGroup(self):
        """Create the generic Footprint display mode node for spaces."""

        from pivy import coin

        self.fcoords = coin.SoCoordinate3()
        self.fset = coin.SoIndexedFaceSet()
        self.lcoords = coin.SoCoordinate3()
        self.lset = coin.SoLineSet()
        shape_hints = coin.SoShapeHints()
        shape_hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        fill_offset = coin.SoPolygonOffset()
        fill_offset.styles = coin.SoPolygonOffsetElement.FILLED
        fill_offset.factor = 1.0
        fill_offset.units = 4.0
        fill_offset.on = True
        line_offset = coin.SoPolygonOffset()
        line_offset.styles = coin.SoPolygonOffsetElement.LINES
        line_offset.factor = -0.5
        line_offset.units = -1.0
        line_offset.on = True
        self.lstyle = coin.SoDrawStyle()
        self.lmat = coin.SoBaseColor()

        base_color = ArchCommands.getDefaultColor("Space")
        fill_color = tuple(min(1.0, 0.84 + component * 0.16) for component in base_color[:3])

        sep = coin.SoSeparator()
        sep.addChild(fill_offset)
        sep.addChild(
            ArchComponent.ViewProviderComponent.buildFootprintFillSeparator(
                self,
                fill_color,
                0.88,
                self.fcoords,
                self.fset,
                shape_hints=shape_hints,
            )
        )
        line_sep = coin.SoSeparator()
        line_sep.addChild(line_offset)
        line_sep.addChild(self.lmat)
        line_sep.addChild(self.lstyle)
        line_sep.addChild(self.lcoords)
        line_sep.addChild(self.lset)
        sep.addChild(line_sep)
        return sep

    def updateFootprint(self):
        ArchComponent.ViewProviderComponent.updateFootprint(self)

        if not hasattr(self, "lcoords") or not hasattr(self, "lset"):
            return

        line_verts = []
        line_counts = []
        if hasattr(self, "Object"):
            faces = self.Object.Proxy.getFootprint(self.Object)
            if faces:
                inverse_placement = None
                placement = getattr(self.Object, "Placement", None)
                if placement:
                    try:
                        inverse_placement = placement.inverse()
                    except Exception:
                        inverse_placement = None

                for wire_points in ArchPlanGeometry.get_face_wire_polylines(faces):
                    start_idx = len(line_verts)
                    for point in wire_points:
                        if inverse_placement is not None:
                            point = inverse_placement.multVec(point)
                        line_verts.append([point.x, point.y, point.z])
                    line_counts.append(len(line_verts) - start_idx)

        self._update_footprint_line_nodes(
            self.lcoords,
            self.lset,
            line_verts,
            line_counts,
            context="ArchSpace.updateFootprint",
        )

    def updateData(self, obj, prop):
        ArchComponent.ViewProviderComponent.updateData(self, obj, prop)

        if prop in ["Shape", "Label", "Tag", "Area"]:
            self.onChanged(obj.ViewObject, "Text")
            self.onChanged(obj.ViewObject, "TextPosition")

    def getTextPosition(self, vobj):

        pos = FreeCAD.Vector()
        if hasattr(vobj, "TextPosition"):
            import DraftVecUtils

            if DraftVecUtils.isNull(vobj.TextPosition):
                try:
                    pos = vobj.Object.Shape.CenterOfMass
                    z = vobj.Object.Shape.BoundBox.ZMin
                    pos = FreeCAD.Vector(pos.x, pos.y, z)
                except (AttributeError, RuntimeError):
                    pos = FreeCAD.Vector()
            else:
                pos = vobj.Object.Placement.multVec(vobj.TextPosition)
        # placement's displacement will be already added by the coin node
        pos = vobj.Object.Placement.inverse().multVec(pos)
        return pos

    def onChanged(self, vobj, prop):

        if prop in ["Text", "Decimals", "ShowUnit"]:
            if hasattr(self, "text1") and hasattr(self, "text2") and hasattr(vobj, "Text"):
                self.text1.string.deleteValues(0)
                self.text2.string.deleteValues(0)
                text1 = []
                text2 = []
                first = True
                for t in vobj.Text:
                    if t:
                        t = t.replace("$label", vobj.Object.Label)
                        if hasattr(vobj.Object, "Area"):
                            from FreeCAD import Units

                            q = Units.Quantity(
                                vobj.Object.Area.Value, Units.Area
                            ).getUserPreferred()
                            qt = vobj.Object.Area.Value / q[1]
                            if hasattr(vobj, "Decimals"):
                                if vobj.Decimals == 0:
                                    qt = str(int(qt))
                                else:
                                    f = "%." + str(abs(vobj.Decimals)) + "f"
                                    qt = f % qt
                            else:
                                qt = str(qt)
                            if hasattr(vobj, "ShowUnit"):
                                if vobj.ShowUnit:
                                    qt = qt + q[2].replace("^2", "\xb2")  # square symbol
                            t = t.replace("$area", qt)
                        if hasattr(vobj.Object, "FinishFloor"):
                            t = t.replace("$floor", vobj.Object.FinishFloor)
                        if hasattr(vobj.Object, "FinishWalls"):
                            t = t.replace("$walls", vobj.Object.FinishWalls)
                        if hasattr(vobj.Object, "FinishCeiling"):
                            t = t.replace("$ceiling", vobj.Object.FinishCeiling)
                        # replace all other properties
                        props = vobj.Object.PropertiesList
                        lower_props = [p.lower() for p in props]
                        for rtag in re.findall(r"\$\w+", t):
                            lower_rtag = rtag[1:].lower()
                            if lower_rtag in lower_props:
                                prop = props[lower_props.index(lower_rtag)]
                                value = getattr(vobj.Object, prop, "")
                                if hasattr(value, "UserString"):
                                    value = value.UserString
                                elif hasattr(value, "Label"):
                                    value = value.Label
                                elif hasattr(value, "Name"):
                                    value = value.Name
                                t = t.replace(rtag, str(value))
                        if first:
                            text1.append(t)
                        else:
                            text2.append(t)
                    first = False
                if text1:
                    self.text1.string.setValues(text1)
                if text2:
                    self.text2.string.setValues(text2)

        elif prop == "FontName":
            if hasattr(self, "font") and hasattr(vobj, "FontName"):
                self.font.name = str(vobj.FontName)

        elif prop == "FontSize":
            if hasattr(self, "font") and hasattr(vobj, "FontSize"):
                self.font.size = vobj.FontSize.Value
                if hasattr(vobj, "FirstLine"):
                    scale = vobj.FirstLine.Value / vobj.FontSize.Value
                    self.header.scaleFactor.setValue([scale, scale, scale])
                    self.onChanged(vobj, "TextPosition")

        elif prop == "FirstLine":
            if hasattr(self, "header") and hasattr(vobj, "FontSize") and hasattr(vobj, "FirstLine"):
                scale = vobj.FirstLine.Value / vobj.FontSize.Value
                self.header.scaleFactor.setValue([scale, scale, scale])
                self.onChanged(vobj, "TextPosition")

        elif prop == "TextColor":
            if hasattr(self, "color") and hasattr(vobj, "TextColor"):
                c = vobj.TextColor
                self.color.rgb.setValue(c[0], c[1], c[2])

        elif prop == "LineColor":
            if hasattr(self, "lmat") and hasattr(vobj, "LineColor"):
                c = vobj.LineColor
                self.lmat.rgb = (c[0], c[1], c[2])

        elif prop == "LineWidth":
            if hasattr(self, "lstyle") and hasattr(vobj, "LineWidth"):
                self.lstyle.lineWidth = max(1.0, float(vobj.LineWidth) * 0.5)

        elif prop == "DrawStyle":
            if hasattr(self, "lstyle") and hasattr(vobj, "DrawStyle"):
                if vobj.DrawStyle == "Solid":
                    self.lstyle.linePattern = 0xFFFF
                elif vobj.DrawStyle == "Dashed":
                    self.lstyle.linePattern = 0xF00F
                elif vobj.DrawStyle == "Dotted":
                    self.lstyle.linePattern = 0x0F0F
                else:
                    self.lstyle.linePattern = 0xFF88

        elif prop == "TextPosition":
            if (
                hasattr(self, "coords")
                and hasattr(self, "header")
                and hasattr(vobj, "TextPosition")
                and hasattr(vobj, "FirstLine")
            ):
                pos = self.getTextPosition(vobj)
                self.coords.translation.setValue(
                    [pos.x, pos.y, pos.z + 0.01]
                )  # adding small z offset to separate from bottom face
                up = vobj.FirstLine.Value * vobj.LineSpacing
                self.header.translation.setValue([0, up, 0])

        elif prop == "LineSpacing":
            if hasattr(self, "text1") and hasattr(self, "text2") and hasattr(vobj, "LineSpacing"):
                self.text1.spacing = vobj.LineSpacing
                self.text2.spacing = vobj.LineSpacing
                self.onChanged(vobj, "TextPosition")

        elif prop == "TextAlign":
            if hasattr(self, "text1") and hasattr(self, "text2") and hasattr(vobj, "TextAlign"):
                from pivy import coin

                if vobj.TextAlign == "Center":
                    self.text1.justification = coin.SoAsciiText.CENTER
                    self.text2.justification = coin.SoAsciiText.CENTER
                elif vobj.TextAlign == "Right":
                    self.text1.justification = coin.SoAsciiText.RIGHT
                    self.text2.justification = coin.SoAsciiText.RIGHT
                else:
                    self.text1.justification = coin.SoAsciiText.LEFT
                    self.text2.justification = coin.SoAsciiText.LEFT

        elif prop == "Visibility":
            if vobj.Visibility:
                self.label.whichChild = 0
            else:
                self.label.whichChild = -1

        elif prop == "Transparency":
            if hasattr(vobj, "DisplayMode"):
                vobj.DisplayMode = "Wireframe" if vobj.Transparency == 100 else "Flat Lines"

    def setEdit(self, vobj, mode):
        if mode != 0:
            return None

        taskd = SpaceTaskPanel(vobj.Object)
        FreeCADGui.Control.showDialog(taskd, FreeCADGui.ActiveDocument)
        return True


class SpaceTaskPanel(ArchComponent.ComponentOptionsTaskPanel):
    """A modified version of the Arch component task panel for Spaces"""

    def __init__(self, obj):
        # Define generic Space options
        property_definitions = [
            {"prop": "SpaceType", "label": translate("Arch", "Space Type")},
            {"prop": "Text", "label": translate("Arch", "Text")},
            {"prop": "FinishFloor", "label": translate("Arch", "Finish Floor")},
            {"prop": "FinishWalls", "label": translate("Arch", "Finish Walls")},
            {"prop": "FinishCeiling", "label": translate("Arch", "Finish Ceiling")},
        ]

        # Initialize parent (creates self.options_widget and self.baseform)
        super().__init__(obj, property_definitions)

        # Create a separate task box for Space-specific tools
        self.space_tools_widget = QtGui.QWidget()
        self.space_tools_widget.setWindowTitle(translate("Arch", "Space Tools"))
        layout = QtGui.QVBoxLayout(self.space_tools_widget)

        self.editButton = QtGui.QPushButton(self.space_tools_widget)
        self.editButton.setIcon(QtGui.QIcon(":/icons/Draft_Edit.svg"))
        self.editButton.setText(translate("Arch", "Set text position"))
        self.editButton.clicked.connect(self.setTextPos)
        layout.addWidget(self.editButton)

        layout.addWidget(QtGui.QLabel(translate("Arch", "Space boundaries")))

        self.boundList = QtGui.QListWidget(self.space_tools_widget)
        layout.addWidget(self.boundList)

        btnLayout = QtGui.QHBoxLayout()
        self.addCompButton = QtGui.QPushButton(self.space_tools_widget)
        self.addCompButton.setIcon(QtGui.QIcon(":/icons/Arch_Add.svg"))
        self.addCompButton.setText(translate("Arch", "Add"))
        self.addCompButton.clicked.connect(self.addBoundary)

        self.delCompButton = QtGui.QPushButton(self.space_tools_widget)
        self.delCompButton.setIcon(QtGui.QIcon(":/icons/Arch_Remove.svg"))
        self.delCompButton.setText(translate("Arch", "Remove"))
        self.delCompButton.clicked.connect(self.delBoundary)

        btnLayout.addWidget(self.addCompButton)
        btnLayout.addWidget(self.delCompButton)
        layout.addLayout(btnLayout)

        # Insert the tools box between Options and Components
        # self.form is currently [options_widget, baseform]
        self.form.insert(1, self.space_tools_widget)

        self.updateBoundaries()

    def updateBoundaries(self):
        self.boundList.clear()
        if self.obj:
            for b in self.obj.Boundaries:
                s = b[0].Label
                for n in b[1]:
                    s += ", " + n
                it = QtGui.QListWidgetItem(s)
                it.setToolTip(b[0].Name)
                self.boundList.addItem(it)

    def setTextPos(self):
        FreeCADGui.runCommand("Draft_Edit")

    def addBoundary(self):
        if self.obj:
            if FreeCADGui.Selection.getSelectionEx():
                self.obj.Proxy.addSubobjects(self.obj, FreeCADGui.Selection.getSelectionEx())
                self.updateBoundaries()

    def delBoundary(self):
        if self.boundList.currentRow() >= 0:
            it = self.boundList.item(self.boundList.currentRow())
            if it and self.obj:
                on = it.toolTip()
                bounds = self.obj.Boundaries
                for b in bounds:
                    if b[0].Name == on:
                        bounds.remove(b)
                        break
                self.obj.Boundaries = bounds
                self.updateBoundaries()
