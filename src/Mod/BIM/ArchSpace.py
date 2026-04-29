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

from contextlib import contextmanager
import json
import heapq
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

_SLICE_EDGE_VERTEX_TOLERANCE = 0.001
_SLICE_EDGE_GAP_BRIDGE_TOLERANCE = 150.0

ConditioningTypes = [
    "Unconditioned",
    "Heated",
    "Cooled",
    "HeatedAndCooled",
    "Vented",
    "NaturallyVentedOnly",
]

AreaCalculationType = ["XY-plane projection", "At Center of Mass"]

_BOUNDARY_SIDE_HINT_VERSION = 2
_BOUNDARY_REGION_HINT_VERSION = 1
_BOUNDARY_STATUS_OK = "OK"
_BOUNDARY_STATUS_CONFLICT = "Conflict"
_BOUNDARY_STATUS_INVALID = "Invalid"
_SCHEDULED_AUTO_SPACE_TEXT_REFRESHES = {}
_SPACE_TEXT_VERTICAL_DISTANCE_WEIGHT = 1.75
_SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS = 0


@contextmanager
def suppress_boundary_failure_console_reports():
    global _SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS
    _SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS += 1
    try:
        yield
    finally:
        _SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS = max(
            0,
            _SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS - 1,
        )


def _should_report_boundary_failure_to_console():
    return _SUPPRESSED_BOUNDARY_FAILURE_CONSOLE_REPORTS <= 0


class _Space(ArchComponent.Component):
    "A space object"

    def __init__(self, obj):

        ArchComponent.Component.__init__(self, obj)
        self.Type = "Space"
        self._clear_boundary_failure()
        self._pending_boundary_conflict_retries = set()
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
        if not "BoundaryWalls" in pl:
            obj.addProperty(
                "App::PropertyLinkList",
                "BoundaryWalls",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Hidden wall boundary objects used to resolve stable wall-side faces after topology changes",
                ),
                locked=True,
            )
        if "BoundaryWalls" in obj.PropertiesList:
            obj.setEditorMode("BoundaryWalls", 2)
        if not "BoundarySideHints" in pl:
            obj.addProperty(
                "App::PropertyStringList",
                "BoundarySideHints",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Hidden wall-side references used to keep space boundaries stable after wall topology changes",
                ),
                locked=True,
            )
        if "BoundarySideHints" in obj.PropertiesList:
            obj.setEditorMode("BoundarySideHints", 2)
        if not "BoundaryRegionHint" in pl:
            obj.addProperty(
                "App::PropertyString",
                "BoundaryRegionHint",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Hidden region reference used to keep multi-room space boundaries stable after geometry changes",
                ),
                locked=True,
            )
        if "BoundaryRegionHint" in obj.PropertiesList:
            obj.setEditorMode("BoundaryRegionHint", 2)
        if not "BoundaryStatus" in pl:
            obj.addProperty(
                "App::PropertyString",
                "BoundaryStatus",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Read-only boundary validation state for spaces driven by wall or face boundaries",
                ),
                locked=True,
            )
        if "BoundaryStatus" in obj.PropertiesList:
            obj.setEditorMode("BoundaryStatus", 1)
        if not "BoundaryStatusMessage" in pl:
            obj.addProperty(
                "App::PropertyString",
                "BoundaryStatusMessage",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Read-only boundary validation message for this space",
                ),
                locked=True,
            )
        if "BoundaryStatusMessage" in obj.PropertiesList:
            obj.setEditorMode("BoundaryStatusMessage", 1)
        if not "BoundaryStatusDetails" in pl:
            obj.addProperty(
                "App::PropertyStringList",
                "BoundaryStatusDetails",
                "Space",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Read-only boundary validation details for this space",
                ),
                locked=True,
            )
        if "BoundaryStatusDetails" in obj.PropertiesList:
            obj.setEditorMode("BoundaryStatusDetails", 1)
        if not str(getattr(obj, "BoundaryStatus", "") or "").strip():
            self._set_boundary_status(obj, _BOUNDARY_STATUS_OK)
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
        self._pending_boundary_conflict_retries = set()

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
        objs = list(getattr(obj, "Boundaries", []) or [])
        wall_objs = list(getattr(obj, "BoundaryWalls", []) or [])
        for o in subobjects:
            if isinstance(o, (tuple, list)):
                boundary_obj, subnames = self._get_boundary_entry_object_and_subnames(o)
                if not boundary_obj or boundary_obj.Name == obj.Name:
                    continue
                face_names = self.normalizeBoundarySubnames(subnames)
                if self._is_wall_object(boundary_obj):
                    if face_names:
                        objs.append((boundary_obj, tuple(face_names)))
                    elif boundary_obj not in wall_objs:
                        wall_objs.append(boundary_obj)
                elif face_names:
                    objs.append((boundary_obj, tuple(face_names)))
            else:
                for el in o.SubElementNames:
                    if "Face" in el:
                        if o.Object.Name != obj.Name:
                            objs.append((o.Object, el))
        obj.Boundaries = objs
        if hasattr(obj, "BoundaryWalls"):
            obj.BoundaryWalls = wall_objs

    def removeSubobjects(self, obj, subobjects):
        "removes subobjects to this space"
        bounds = list(getattr(obj, "Boundaries", []) or [])
        wall_bounds = list(getattr(obj, "BoundaryWalls", []) or [])
        removed_names = set()
        for o in subobjects:
            object_name = getattr(o, "Name", None)
            if not object_name and hasattr(o, "Object"):
                object_name = getattr(o.Object, "Name", None)
            if object_name:
                removed_names.add(object_name)
            for b in bounds:
                if object_name and object_name == b[0].Name:
                    bounds.remove(b)
                    break
        obj.Boundaries = bounds
        if hasattr(obj, "BoundaryWalls"):
            obj.BoundaryWalls = [
                wall for wall in wall_bounds if getattr(wall, "Name", None) not in removed_names
            ]

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
        message = getattr(self, "_last_boundary_error", "")
        if message:
            return message
        if obj is not None:
            return str(getattr(obj, "BoundaryStatusMessage", "") or "").strip()
        return ""

    def getLastBoundaryErrorDetails(self, obj=None):
        details = list(getattr(self, "_last_boundary_error_details", []))
        if details:
            return details
        if obj is not None:
            return [
                str(detail).strip()
                for detail in list(getattr(obj, "BoundaryStatusDetails", []) or [])
                if str(detail).strip()
            ]
        return []

    def _set_boundary_status(self, obj, status=_BOUNDARY_STATUS_OK, message="", details=None):
        if obj is None:
            return
        status = str(status or _BOUNDARY_STATUS_OK).strip() or _BOUNDARY_STATUS_OK
        message = str(message or "").strip()
        detail_values = [str(detail).strip() for detail in details or [] if str(detail).strip()]
        for property_name, value in (
            ("BoundaryStatus", status),
            ("BoundaryStatusMessage", message),
            ("BoundaryStatusDetails", detail_values),
        ):
            if not hasattr(obj, property_name):
                continue
            try:
                current = getattr(obj, property_name)
            except Exception:
                current = None
            if property_name == "BoundaryStatusDetails":
                current = list(current or [])
            if current == value:
                continue
            try:
                setattr(obj, property_name, value)
            except Exception:
                pass

    def getBoundaryStatus(self, obj=None):
        if obj is None:
            return _BOUNDARY_STATUS_OK
        return str(getattr(obj, "BoundaryStatus", _BOUNDARY_STATUS_OK) or _BOUNDARY_STATUS_OK)

    def getBoundaryStatusMessage(self, obj=None):
        if obj is None:
            return ""
        return str(getattr(obj, "BoundaryStatusMessage", "") or "").strip()

    def getBoundaryStatusDetails(self, obj=None):
        if obj is None:
            return []
        return [
            str(detail).strip()
            for detail in list(getattr(obj, "BoundaryStatusDetails", []) or [])
            if str(detail).strip()
        ]

    def _report_boundary_failure(self, message, details=None):
        if not message or not _should_report_boundary_failure_to_console():
            return
        FreeCAD.Console.PrintError(message + "\n")
        for detail in details or []:
            FreeCAD.Console.PrintError(f"  - {detail}\n")

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
        boundaries = self._get_stable_boundary_links(obj)
        return self._get_boundary_faces_from_links(boundaries)

    def getStableBoundaryLinks(self, obj):
        return self._get_stable_boundary_links(obj)

    def setBoundaryLinks(self, obj, boundaries):
        normalized = self.normalizeBoundaryLinks(boundaries, exclude_objects=obj)
        if self._get_boundary_region_reference_point(obj) is not None:
            self._write_boundary_side_hints(
                obj,
                self._build_boundary_side_hints_from_links(obj, normalized),
            )
        self._write_boundary_storage(
            obj,
            normalized,
            hints=self._load_boundary_side_hints(obj),
        )

    def _get_shape_reference_point(self, shape):
        if shape is None:
            return None
        try:
            if shape.isNull():
                return None
        except Exception:
            pass
        try:
            return FreeCAD.Vector(shape.CenterOfMass)
        except Exception:
            pass
        try:
            bb = shape.BoundBox
            return FreeCAD.Vector(
                0.5 * (float(bb.XMin) + float(bb.XMax)),
                0.5 * (float(bb.YMin) + float(bb.YMax)),
                0.5 * (float(bb.ZMin) + float(bb.ZMax)),
            )
        except Exception:
            return None

    def _get_space_reference_point(self, obj):
        point = self._get_boundary_region_reference_point(obj)
        if point is not None:
            return point
        return self._get_space_shape_reference_point(obj)

    def _get_space_shape_reference_point(self, obj):
        point = self._get_shape_reference_point(getattr(obj, "Shape", None))
        if point is not None:
            return point
        try:
            base_shape = obj.Base.Shape
        except Exception:
            base_shape = None
        return self._get_shape_reference_point(base_shape)

    @staticmethod
    def _vector_to_boundary_hint(point):
        try:
            return [float(point.x), float(point.y), float(point.z)]
        except Exception:
            return None

    @staticmethod
    def _vector_from_boundary_hint(value):
        try:
            if len(value) != 3:
                return None
            return FreeCAD.Vector(float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return None

    def _object_local_point_from_global(self, obj, point):
        try:
            return obj.Placement.inverse().multVec(FreeCAD.Vector(point))
        except Exception:
            return None

    def _object_global_point_from_local(self, obj, point):
        try:
            return obj.Placement.multVec(FreeCAD.Vector(point))
        except Exception:
            return None

    def _object_local_direction_from_global(self, obj, direction):
        try:
            local_direction = obj.Placement.inverse().Rotation.multVec(FreeCAD.Vector(direction))
        except Exception:
            return None
        if local_direction.Length <= 1e-7:
            return None
        local_direction.normalize()
        return local_direction

    def _object_global_direction_from_local(self, obj, direction):
        try:
            global_direction = obj.Placement.Rotation.multVec(FreeCAD.Vector(direction))
        except Exception:
            return None
        if global_direction.Length <= 1e-7:
            return None
        global_direction.normalize()
        return global_direction

    def _load_boundary_side_hints(self, obj):
        hints = {}
        for raw_hint in getattr(obj, "BoundarySideHints", []) or []:
            try:
                hint = json.loads(str(raw_hint))
            except Exception:
                continue
            if not isinstance(hint, dict):
                continue
            if hint.get("kind") != "wall-side":
                continue
            object_name = hint.get("object")
            if object_name:
                hints[str(object_name)] = hint
        return hints

    def _write_boundary_side_hints(self, obj, raw_hints):
        if not hasattr(obj, "BoundarySideHints"):
            return
        raw_hints = list(raw_hints or [])
        try:
            if list(getattr(obj, "BoundarySideHints", []) or []) != raw_hints:
                obj.BoundarySideHints = raw_hints
        except Exception:
            pass

    def _load_boundary_region_hint(self, obj):
        try:
            raw_hint = str(getattr(obj, "BoundaryRegionHint", "") or "").strip()
        except Exception:
            raw_hint = ""
        if not raw_hint:
            return {}
        try:
            hint = json.loads(raw_hint)
        except Exception:
            return {}
        return hint if isinstance(hint, dict) else {}

    def _get_boundary_region_reference_point(self, obj):
        hint = self._load_boundary_region_hint(obj)
        if not hint:
            return None
        local_reference = self._vector_from_boundary_hint(hint.get("local_reference"))
        if local_reference is not None:
            reference_point = self._object_global_point_from_local(obj, local_reference)
            if reference_point is not None:
                return reference_point
        return self._vector_from_boundary_hint(hint.get("reference"))

    def _set_boundary_region_hint(self, obj, point):
        reference_hint = self._vector_to_boundary_hint(point)
        if reference_hint is None:
            return
        hint = {
            "version": _BOUNDARY_REGION_HINT_VERSION,
            "kind": "region-reference",
            "reference": reference_hint,
        }
        local_reference = self._vector_to_boundary_hint(
            self._object_local_point_from_global(obj, point)
        )
        if local_reference is not None:
            hint["local_reference"] = local_reference
        payload = json.dumps(
            hint,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            if str(getattr(obj, "BoundaryRegionHint", "") or "") != payload:
                obj.BoundaryRegionHint = payload
        except Exception:
            pass

    def setBoundaryRegionReferencePoint(self, obj, point):
        self._set_boundary_region_hint(obj, point)

    def _get_boundary_region_record_reference_point(self, record=None, shape=None):
        if record is not None:
            sample_point = record.get("sample")
            if sample_point is not None:
                return FreeCAD.Vector(sample_point)
        point = self._get_shape_reference_point(shape)
        if point is not None:
            return point
        return None

    def _sync_boundary_region_hint(self, obj, shape=None, record=None, force=False):
        if not force and self._get_boundary_region_reference_point(obj) is not None:
            return
        point = self._get_boundary_region_record_reference_point(record=record, shape=shape)
        if point is None:
            try:
                base_shape = obj.Base.Shape
            except Exception:
                base_shape = None
            point = self._get_shape_reference_point(base_shape)
        if point is None:
            return
        self._set_boundary_region_hint(obj, point)

    def _is_boundary_region_base_object(self, base_obj):
        if not base_obj:
            return False
        try:
            if getattr(base_obj, "TypeId", "") != "Part::Feature":
                return False
            return str(getattr(base_obj, "Name", "") or "").startswith("SpaceRegionBase")
        except Exception:
            return False

    def _loop_analysis_regions_match_reference_point(self, obj, loop_analysis):
        if not loop_analysis:
            return False
        reference_point = self._get_space_reference_point(obj)
        if reference_point is None:
            return False

        records = list(loop_analysis.get("records", []) or [])
        for record in loop_analysis.get("top_level", []) or []:
            region_face = self._build_face_from_region_record(records, record)
            if region_face is None:
                continue
            sample_point = record.get("sample")
            sample_z = getattr(sample_point, "z", reference_point.z)
            plan_reference = FreeCAD.Vector(reference_point.x, reference_point.y, sample_z)
            try:
                if region_face.isInside(plan_reference, 0.001, True):
                    return True
            except Exception:
                continue
        return False

    def _describe_boundary_region_reference_conflict(self, label):
        label = str(label or translate("Arch", "Space"))
        return (
            translate(
                "Arch",
                "Arch Space '{label}' kept its previous shape because its stored room reference no longer matches any enclosed region.",
            ).format(label=label),
            [
                translate(
                    "Arch",
                    "Update the boundary selection or reassign the space to the intended enclosed region.",
                )
            ],
        )

    def _preserve_current_shape_with_boundary_failure(
        self,
        obj,
        pl,
        *,
        status=_BOUNDARY_STATUS_INVALID,
        message,
        details=None,
        initialize_boundary_region_point=None,
    ):
        current_shape = self._copy_without_element_map(getattr(obj, "Shape", None))
        if current_shape is None or not getattr(current_shape, "Solids", None):
            return False

        shape = self.processSubShapes(obj, current_shape.Solids[0], pl)
        self.applyShape(obj, shape, pl)
        self._sync_area_properties(obj)
        if (
            initialize_boundary_region_point is not None
            and self._get_boundary_region_reference_point(obj) is None
        ):
            self._set_boundary_region_hint(obj, initialize_boundary_region_point)
        self._sync_boundary_side_hints(obj, shape)
        self._set_boundary_failure(message, details)
        self._set_boundary_status(obj, status, message, details)
        self._report_boundary_failure(message, details)
        return True

    def _preserve_current_shape_with_boundary_conflict(
        self,
        obj,
        pl,
        *,
        message,
        details=None,
        initialize_boundary_region_point=None,
    ):
        if self._preserve_current_shape_with_boundary_failure(
            obj,
            pl,
            status=_BOUNDARY_STATUS_CONFLICT,
            message=message,
            details=details,
            initialize_boundary_region_point=initialize_boundary_region_point,
        ):
            return True
        self._set_boundary_failure(message, details)
        self._set_boundary_status(obj, _BOUNDARY_STATUS_CONFLICT, message, details)
        self._report_boundary_failure(message, details)
        return False

    def _pop_pending_boundary_conflict_retry(self, obj):
        object_name = getattr(obj, "Name", None)
        if not object_name:
            return False
        pending = getattr(self, "_pending_boundary_conflict_retries", None)
        if not isinstance(pending, set):
            pending = set()
            self._pending_boundary_conflict_retries = pending
        if object_name not in pending:
            return False
        pending.discard(object_name)
        return True

    def _schedule_boundary_conflict_retry(self, obj):
        object_name = getattr(obj, "Name", None)
        if not object_name:
            return False
        pending = getattr(self, "_pending_boundary_conflict_retries", None)
        if not isinstance(pending, set):
            pending = set()
            self._pending_boundary_conflict_retries = pending
        if object_name in pending:
            return False
        pending.add(object_name)
        try:
            request_deferred_recompute = getattr(obj, "requestDeferredRecompute", None)
            if callable(request_deferred_recompute):
                request_deferred_recompute(FreeCAD.RecomputePhase.PostUpstream)
            else:
                obj.touch()
        except Exception:
            pending.discard(object_name)
            return False
        return True

    def _can_preserve_current_legacy_region_shape(self, obj, boundary_faces, loop_analysis):
        if not boundary_faces or not loop_analysis:
            return False
        if self._get_boundary_region_reference_point(obj) is not None:
            return False
        if not self._is_boundary_region_base_object(getattr(obj, "Base", None)):
            return False
        if not self._is_usable_solid_shape(getattr(obj, "Shape", None)):
            return False
        if not loop_analysis.get("top_level"):
            return True
        return not self._loop_analysis_regions_match_reference_point(obj, loop_analysis)

    def _get_boundary_face(self, obj, face_name):
        try:
            if not str(face_name).startswith("Face"):
                return None
            index = int(str(face_name)[4:]) - 1
            return obj.Shape.Faces[index]
        except Exception:
            return None

    def _get_boundary_face_normal_and_center(self, face):
        try:
            normal_raw = face.normalAt(0, 0)
            center_raw = face.CenterOfMass
            normal = FreeCAD.Vector(normal_raw.x, normal_raw.y, normal_raw.z)
            center = FreeCAD.Vector(center_raw.x, center_raw.y, center_raw.z)
        except Exception:
            return None, None
        if normal.Length <= 1e-7:
            return None, None
        normal.normalize()
        return normal, center

    def _get_boundary_face_reference_score(self, face, reference_point):
        if face is None or reference_point is None:
            return None
        normal, center = self._get_boundary_face_normal_and_center(face)
        if normal is None or center is None:
            return None
        return float(normal.dot(FreeCAD.Vector(reference_point).sub(center)))

    def _get_boundary_face_tangential_distance(self, face, reference_point):
        if face is None or reference_point is None:
            return None
        normal, center = self._get_boundary_face_normal_and_center(face)
        if normal is None or center is None:
            return None
        reference_vector = FreeCAD.Vector(reference_point).sub(center)
        normal_offset = float(normal.dot(reference_vector))
        tangential = reference_vector.sub(FreeCAD.Vector(normal).multiply(normal_offset))
        return float(tangential.Length)

    def _get_wall_side_reference_point(self, wall, face_name, fallback_reference=None):
        face = self._get_boundary_face(wall, face_name)
        if face is not None:
            normal, center = self._get_boundary_face_normal_and_center(face)
            if normal is not None and center is not None and abs(normal.z) <= 0.2:
                offset = 1000.0
                try:
                    width = getattr(wall, "Width", 0.0)
                    width = getattr(width, "Value", width)
                    offset = max(offset, float(width) * 2.0)
                except Exception:
                    pass
                direction = FreeCAD.Vector(normal)
                direction.multiply(offset)
                return center.add(direction)
        if fallback_reference is not None:
            try:
                return FreeCAD.Vector(fallback_reference)
            except Exception:
                return None
        return None

    def _get_boundary_hint_reference_point(self, wall, hint):
        if not hint:
            return None
        local_reference = self._vector_from_boundary_hint(hint.get("local_reference"))
        if local_reference is not None:
            reference_point = self._object_global_point_from_local(wall, local_reference)
            if reference_point is not None:
                return reference_point
        return self._vector_from_boundary_hint(hint.get("reference"))

    def _get_boundary_hint_normal(self, wall, hint):
        if not hint:
            return None
        local_normal = self._vector_from_boundary_hint(hint.get("local_normal"))
        if local_normal is not None:
            normal = self._object_global_direction_from_local(wall, local_normal)
            if normal is not None:
                return normal
        normal = self._vector_from_boundary_hint(hint.get("normal"))
        if normal is None or normal.Length <= 1e-7:
            return None
        normal.normalize()
        return normal

    def _get_semantic_wall_boundary_face_names(
        self,
        wall,
        *,
        reference_point=None,
        hint=None,
        use_wall_face_sets=False,
    ):
        if not wall:
            return ()

        normal = self._get_boundary_hint_normal(wall, hint)
        if use_wall_face_sets:
            candidate_face_names = ()
            if normal is not None:
                candidate_face_names = self._get_wall_boundary_face_names(
                    wall,
                    reference_point=reference_point,
                    normal=normal,
                )
            if not candidate_face_names:
                candidate_face_names = self._get_wall_boundary_face_names(
                    wall,
                    reference_point=reference_point,
                )
            return tuple(candidate_face_names)

        candidate_face_name = None
        if normal is not None:
            candidate_face_name = self._get_wall_boundary_face_name_for_normal(
                wall,
                normal,
                reference_point=reference_point,
            )
        if not candidate_face_name:
            candidate_face_name = self._get_wall_boundary_face_name(
                wall,
                reference_point,
            )
        return (candidate_face_name,) if candidate_face_name else ()

    def _serialize_boundary_side_hint(self, boundary_obj, face_names, space_reference):
        object_name = getattr(boundary_obj, "Name", None)
        if not object_name or not self._is_wall_object(boundary_obj):
            return None

        face_names = self.normalizeBoundarySubnames(face_names)
        if not face_names:
            return None

        primary_face_name = face_names[0]
        if len(face_names) > 1 and space_reference is not None:
            candidate_face_name = self._get_wall_boundary_face_name(
                boundary_obj,
                space_reference,
            )
            if candidate_face_name in face_names:
                primary_face_name = candidate_face_name

        face = self._get_boundary_face(boundary_obj, primary_face_name)
        reference_point = self._get_wall_side_reference_point(
            boundary_obj,
            primary_face_name,
            fallback_reference=space_reference,
        )
        reference_hint = self._vector_to_boundary_hint(reference_point)
        if reference_hint is None:
            return None

        local_reference_hint = self._vector_to_boundary_hint(
            self._object_local_point_from_global(boundary_obj, reference_point)
        )
        normal, _center = self._get_boundary_face_normal_and_center(face)
        normal_hint = self._vector_to_boundary_hint(normal)
        local_normal_hint = self._vector_to_boundary_hint(
            self._object_local_direction_from_global(boundary_obj, normal)
        )

        hint = {
            "version": _BOUNDARY_SIDE_HINT_VERSION,
            "kind": "wall-side",
            "object": object_name,
            "reference": reference_hint,
        }
        if local_reference_hint is not None:
            hint["local_reference"] = local_reference_hint
        if normal_hint is not None:
            hint["normal"] = normal_hint
        if local_normal_hint is not None:
            hint["local_normal"] = local_normal_hint
        return json.dumps(
            hint,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _build_boundary_side_hints_from_links(self, obj, boundaries, shape=None):
        if not hasattr(obj, "BoundarySideHints"):
            return []

        space_reference = self._get_shape_reference_point(shape)
        if space_reference is None:
            space_reference = self._get_space_reference_point(obj)

        hints = []
        seen = set()
        for boundary_obj, subnames in boundaries or []:
            object_name = getattr(boundary_obj, "Name", None)
            if not object_name or object_name in seen:
                continue
            raw_hint = self._serialize_boundary_side_hint(
                boundary_obj,
                subnames,
                space_reference,
            )
            if raw_hint is None:
                continue
            hints.append(raw_hint)
            seen.add(object_name)
        return hints

    def _get_wall_boundary_face_name_for_normal(self, wall, normal, reference_point=None):
        if wall is None or normal is None:
            return None
        try:
            if Draft.getType(wall) != "Wall":
                return None
        except Exception:
            return None
        shape = getattr(wall, "Shape", None)
        if shape is None or not getattr(shape, "Faces", None):
            return None

        normal = FreeCAD.Vector(normal)
        if normal.Length <= 1e-7:
            return None
        normal.normalize()

        best_face_name = None
        best_sort_key = None
        for index, face in enumerate(shape.Faces, start=1):
            face_normal, face_center = self._get_boundary_face_normal_and_center(face)
            if face_normal is None or face_center is None:
                continue
            if abs(face_normal.z) > 0.2:
                continue
            normal_score = float(face_normal.dot(normal))
            if normal_score <= 0.8:
                continue
            facing_score = 0.0
            tangential_distance = 0.0
            if reference_point is not None:
                facing_score = float(
                    face_normal.dot(FreeCAD.Vector(reference_point).sub(face_center))
                )
                tangential_distance = self._get_boundary_face_tangential_distance(
                    face,
                    reference_point,
                )
                if tangential_distance is None:
                    tangential_distance = float("inf")
            sort_key = (
                normal_score,
                -float(tangential_distance),
                facing_score,
                float(face.Area or 0.0),
            )
            if best_sort_key is None or sort_key > best_sort_key:
                best_sort_key = sort_key
                best_face_name = f"Face{index}"
        return best_face_name

    def _should_refresh_wall_boundary_face(
        self, wall, current_face_name, candidate_face_name, reference_point
    ):
        if not candidate_face_name or candidate_face_name == current_face_name:
            return False

        current_face = self._get_boundary_face(wall, current_face_name)
        candidate_face = self._get_boundary_face(wall, candidate_face_name)
        if current_face is None:
            return True
        if candidate_face is None:
            return False

        current_score = self._get_boundary_face_reference_score(current_face, reference_point)
        candidate_score = self._get_boundary_face_reference_score(candidate_face, reference_point)
        if current_score is not None and current_score <= 1e-7:
            return True

        try:
            current_normal = current_face.normalAt(0, 0)
            if abs(float(current_normal.z)) > 0.2:
                return True
        except Exception:
            pass

        try:
            current_area = float(current_face.Area or 0.0)
            candidate_area = float(candidate_face.Area or 0.0)
        except Exception:
            current_area = 0.0
            candidate_area = 0.0
        if candidate_area > 0.0 and current_area <= 0.0:
            return True
        if candidate_area > max(current_area * 2.0, current_area + 1.0):
            return True

        if (
            candidate_score is not None
            and current_score is not None
            and candidate_score > max(current_score * 2.0, current_score + 1.0)
        ):
            return True

        return False

    def _get_stable_boundary_links(self, obj):
        boundaries = self._get_boundary_storage_links(obj)
        if not boundaries:
            return boundaries

        hints = self._load_boundary_side_hints(obj)
        fallback_reference = self._get_space_reference_point(obj)
        boundary_region_reference = self._get_boundary_region_reference_point(obj)
        use_wall_face_sets = self._get_boundary_region_reference_point(obj) is not None
        stable_boundaries = []

        for entry in boundaries:
            boundary_obj, subnames = self._get_boundary_entry_object_and_subnames(entry)
            if not boundary_obj:
                continue
            face_names = self.normalizeBoundarySubnames(subnames)
            object_name = getattr(boundary_obj, "Name", None)
            is_wall = self._is_wall_object(boundary_obj)

            if is_wall and object_name:
                hint = hints.get(object_name)
                if boundary_region_reference is not None:
                    # When the room anchor is known, let the current wall topology decide
                    # which face bounds that room. This handles join-generated trim faces
                    # that are no longer described by the original wall-side normal.
                    face_names = self.getBoundaryFaceNamesForObject(
                        boundary_obj,
                        reference_point=boundary_region_reference,
                    )
                else:
                    reference_point = None
                    if hint:
                        reference_point = self._get_boundary_hint_reference_point(
                            boundary_obj,
                            hint,
                        )
                    if reference_point is None:
                        reference_point = fallback_reference

                    if use_wall_face_sets:
                        face_names = self._get_semantic_wall_boundary_face_names(
                            boundary_obj,
                            reference_point=reference_point,
                            hint=hint,
                            use_wall_face_sets=True,
                        )
                    elif not face_names:
                        face_names = self._get_semantic_wall_boundary_face_names(
                            boundary_obj,
                            reference_point=reference_point,
                            hint=hint,
                            use_wall_face_sets=False,
                        )
                    elif len(face_names) == 1:
                        current_face_name = face_names[0]
                        candidate_face_names = self._get_semantic_wall_boundary_face_names(
                            boundary_obj,
                            reference_point=reference_point,
                            hint=hint,
                            use_wall_face_sets=False,
                        )
                        if candidate_face_names and candidate_face_names[0] != current_face_name:
                            candidate_face_name = candidate_face_names[0]
                            if self._should_refresh_wall_boundary_face(
                                boundary_obj,
                                current_face_name,
                                candidate_face_name,
                                reference_point,
                            ):
                                face_names = tuple(candidate_face_names)

            if face_names:
                stable_boundaries.append((boundary_obj, tuple(face_names)))

        stable_boundaries = self.normalizeBoundaryLinks(stable_boundaries, exclude_objects=obj)
        self._write_boundary_storage(
            obj,
            stable_boundaries,
            hints=hints,
        )
        return stable_boundaries

    def _get_boundary_storage_links(self, obj):
        boundaries = []
        explicit_wall_names = set()
        for entry in list(getattr(obj, "Boundaries", []) or []):
            boundary_obj, subnames = self._get_boundary_entry_object_and_subnames(entry)
            if not boundary_obj:
                continue
            face_names = self.normalizeBoundarySubnames(subnames)
            if not face_names:
                continue
            boundaries.append((boundary_obj, tuple(face_names)))
            if self._is_wall_object(boundary_obj):
                object_name = getattr(boundary_obj, "Name", None)
                if object_name:
                    explicit_wall_names.add(object_name)

        for wall in list(getattr(obj, "BoundaryWalls", []) or []):
            if not self._is_wall_object(wall):
                continue
            object_name = getattr(wall, "Name", None)
            if not object_name or object_name in explicit_wall_names:
                continue
            boundaries.append((wall, ()))
        return boundaries

    def _split_boundary_storage_links(
        self,
        boundaries,
        hints=None,
        store_hinted_wall_boundaries=False,
    ):
        hinted_objects = set()
        if isinstance(hints, dict):
            hinted_objects = {str(name) for name in hints.keys() if str(name)}
        explicit_boundaries = []
        wall_objects = []
        seen_wall_names = set()
        for boundary_obj, subnames in boundaries or []:
            if not boundary_obj:
                continue
            object_name = getattr(boundary_obj, "Name", None)
            is_wall = self._is_wall_object(boundary_obj)
            face_names = tuple(self.normalizeBoundarySubnames(subnames))
            if store_hinted_wall_boundaries and is_wall and object_name in hinted_objects:
                if object_name not in seen_wall_names:
                    wall_objects.append(boundary_obj)
                    seen_wall_names.add(object_name)
            else:
                explicit_boundaries.append((boundary_obj, face_names))
        return (explicit_boundaries, wall_objects)

    def _write_boundary_storage(self, obj, stable_boundaries, hints=None):
        explicit_boundaries, wall_objects = self._split_boundary_storage_links(
            stable_boundaries,
            hints=hints,
            store_hinted_wall_boundaries=self._get_boundary_region_reference_point(obj) is not None,
        )
        try:
            if list(getattr(obj, "Boundaries", []) or []) != explicit_boundaries:
                obj.Boundaries = explicit_boundaries
        except Exception:
            pass
        if hasattr(obj, "BoundaryWalls"):
            try:
                if list(getattr(obj, "BoundaryWalls", []) or []) != wall_objects:
                    obj.BoundaryWalls = wall_objects
            except Exception:
                pass

    def _sync_boundary_side_hints(self, obj, shape=None):
        stable_links = self._get_stable_boundary_links(obj)
        self._write_boundary_side_hints(
            obj,
            self._build_boundary_side_hints_from_links(obj, stable_links, shape=shape),
        )
        self._write_boundary_storage(
            obj,
            stable_links,
            hints=self._load_boundary_side_hints(obj),
        )

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

    def _get_slice_edge_endpoint_records(self, section_edges):
        records = []
        for edge_index, edge in enumerate(section_edges or []):
            vertexes = list(getattr(edge, "Vertexes", []) or [])
            if len(vertexes) < 2:
                continue
            for endpoint_index, vertex in enumerate((vertexes[0], vertexes[-1])):
                try:
                    point = FreeCAD.Vector(vertex.Point)
                except Exception:
                    continue
                records.append(
                    {
                        "id": len(records),
                        "edge_index": edge_index,
                        "edge": edge,
                        "endpoint_index": endpoint_index,
                        "point": point,
                    }
                )
        return records

    def _get_slice_edge_gap_distance(self, point, other):
        delta = FreeCAD.Vector(point).sub(FreeCAD.Vector(other))
        delta.z = 0.0
        return float(delta.Length)

    def _is_slice_edge_point_on_edge(self, point, edge, tolerance=_SLICE_EDGE_VERTEX_TOLERANCE):
        import Part

        if self._get_slice_edge_curve_type(edge) == "Line":
            vertexes = list(getattr(edge, "Vertexes", []) or [])
            if len(vertexes) >= 2:
                start = FreeCAD.Vector(vertexes[0].Point)
                end = FreeCAD.Vector(vertexes[-1].Point)
                point = FreeCAD.Vector(point)
                segment = end.sub(start)
                length_sq = segment.dot(segment)
                if length_sq <= tolerance * tolerance:
                    return point.distanceToPoint(start) <= tolerance
                t = point.sub(start).dot(segment) / length_sq
                if t < -0.000001 or t > 1.000001:
                    return False
                offset = FreeCAD.Vector(segment)
                offset.multiply(max(0.0, min(1.0, t)))
                closest = start.add(offset)
                return point.distanceToPoint(closest) <= tolerance

        try:
            vertex = Part.Vertex(FreeCAD.Vector(point))
            result = vertex.distToShape(edge)
        except Exception:
            return False
        if not result:
            return False
        try:
            distance = float(result[0])
        except Exception:
            return False
        return distance <= tolerance

    def _can_build_faces_from_slice_edges(
        self, section_edges, tolerance=_SLICE_EDGE_VERTEX_TOLERANCE
    ):
        endpoint_records = self._get_slice_edge_endpoint_records(section_edges)
        if len(endpoint_records) < 2:
            return False

        for record in endpoint_records:
            point = record["point"]
            for edge_index, edge in enumerate(section_edges or []):
                if edge_index == record["edge_index"]:
                    continue
                if not self._is_slice_edge_point_on_edge(point, edge, tolerance=tolerance):
                    continue
                other_vertexes = list(getattr(edge, "Vertexes", []) or [])
                if any(
                    self._get_slice_edge_gap_distance(point, vertex.Point) <= tolerance
                    for vertex in other_vertexes
                ):
                    continue
                return True
        return False

    def _get_gap_bridged_slice_edges(
        self,
        section_edges,
        gap_tolerance=_SLICE_EDGE_GAP_BRIDGE_TOLERANCE,
        vertex_tolerance=_SLICE_EDGE_VERTEX_TOLERANCE,
    ):
        import Part

        edges = list(section_edges or [])
        if len(edges) < 2:
            return edges

        endpoint_records = self._get_slice_edge_endpoint_records(edges)
        if len(endpoint_records) < 2:
            return edges

        dangling = []
        for record in endpoint_records:
            point = record["point"]
            is_connected = False
            for other in endpoint_records:
                if other["id"] == record["id"] or other["edge_index"] == record["edge_index"]:
                    continue
                if self._get_slice_edge_gap_distance(point, other["point"]) <= vertex_tolerance:
                    is_connected = True
                    break
            if not is_connected:
                dangling.append(record)
        if len(dangling) < 2:
            return edges

        nearest_pairs = {}
        for record in dangling:
            point = record["point"]
            best_match = None
            best_distance = None
            for other in dangling:
                if other["id"] == record["id"] or other["edge_index"] == record["edge_index"]:
                    continue
                distance = self._get_slice_edge_gap_distance(point, other["point"])
                if distance <= vertex_tolerance or distance > gap_tolerance:
                    continue
                if best_distance is None or distance < best_distance:
                    best_match = other
                    best_distance = distance
            if best_match is not None:
                nearest_pairs[record["id"]] = (best_distance, best_match)

        connectors = []
        used_ids = set()
        for record in dangling:
            record_id = record["id"]
            if record_id in used_ids:
                continue
            pair = nearest_pairs.get(record_id)
            if pair is None:
                continue
            _distance, other = pair
            other_id = other["id"]
            if other_id in used_ids:
                continue
            other_pair = nearest_pairs.get(other_id)
            if other_pair is None or other_pair[1]["id"] != record_id:
                continue
            try:
                connector = Part.makeLine(record["point"], other["point"])
            except Exception:
                continue
            if getattr(connector, "Length", 0.0) <= vertex_tolerance:
                continue
            connectors.append(connector)
            used_ids.add(record_id)
            used_ids.add(other_id)

        if not connectors:
            return edges
        return edges + connectors

    def _make_transient_face_from_wires(self, wires):
        import Part

        plain_wires = []
        for wire in wires or []:
            plain_wire = self._copy_without_element_map(wire)
            if plain_wire is None:
                continue
            if len(getattr(plain_wire, "Vertexes", []) or []) < 3:
                continue
            plain_wires.append(plain_wire)
        if not plain_wires:
            return None

        maker = "Part::FaceMakerSimple" if len(plain_wires) == 1 else "Part::FaceMakerCheese"
        try:
            shape = Part.makeFace(plain_wires, maker, noElementMap=True)
        except Exception:
            return None
        if not shape or shape.isNull():
            return None

        faces = [
            face
            for face in getattr(shape, "Faces", []) or []
            if getattr(face, "Area", 0.0) > 0.000001
        ]
        if len(faces) != 1:
            return None
        return faces[0]

    def _get_horizontal_slice_faces_from_edges(self, section_edges):
        import Part

        if not section_edges or len(section_edges) < 4:
            return []
        plain_edges = [self._copy_clean_slice_edge(edge) for edge in section_edges]
        try:
            section_shape = Part.makeFace(
                plain_edges,
                "Part::FaceMakerBuildFace",
                noElementMap=True,
            )
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

    def _get_wires_from_slice_edges(self, candidate_edges):
        import Part

        plain_edges = [self._copy_clean_slice_edge(edge) for edge in candidate_edges]
        try:
            edge_groups = Part.sortEdges(plain_edges)
        except AttributeError:
            edge_groups = Part.__sortEdges__(plain_edges)

        if edge_groups and hasattr(edge_groups[0], "ShapeType"):
            edge_groups = [edge_groups]

        wires = []
        for edges in edge_groups or []:
            if not edges:
                continue
            try:
                wire = Part.Wire(edges)
            except Exception:
                return []
            if not wire.isClosed() or len(wire.Vertexes) < 3:
                return []
            wires.append(wire)
        return wires

    def _get_horizontal_slice_region_data(self, section_edges):
        region_data = {
            "record_source": None,
            "wires": [],
            "records": [],
            "region_faces": [],
        }
        section_edges = list(section_edges or [])
        if not section_edges:
            return region_data

        bridged_edges = self._get_gap_bridged_slice_edges(section_edges)
        has_bridged_edges = len(bridged_edges) > len(section_edges)

        candidates = [("wire", section_edges, "wire")]
        if has_bridged_edges:
            candidates.append(("bridged-wire", bridged_edges, "wire"))
        candidates.append(("face", section_edges, "face"))
        if has_bridged_edges:
            candidates.append(("bridged-face", bridged_edges, "face"))

        for source, candidate_edges, mode in candidates:
            if mode == "wire":
                wires = self._get_wires_from_slice_edges(candidate_edges)
                records = self._classify_wire_records(wires) if wires else []
            else:
                region_faces = self._get_horizontal_slice_faces_from_edges(candidate_edges)
                records = self._classify_region_faces(region_faces) if region_faces else []
            if not records:
                continue

            region_faces = self._build_faces_from_records(records)
            if not region_faces:
                continue

            region_data.update(
                {
                    "record_source": source,
                    "wires": self._get_region_record_wires(records),
                    "records": records,
                    "region_faces": region_faces,
                }
            )
            return region_data
        return region_data

    def _get_horizontal_slice_wires(self, shapes, cut_z):
        section_edges = self._get_horizontal_slice_edges(shapes, cut_z)
        if not section_edges:
            return []
        return self._get_horizontal_slice_region_data(section_edges).get("wires", [])

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
                    "kind": "wire",
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

    def _classify_region_faces(self, faces):
        records = []
        for face in faces or []:
            if not face or getattr(face, "Area", 0.0) <= 0.000001:
                continue
            region_face = self._copy_without_element_map(face)
            if region_face is None:
                region_face = face
            sample_point = self._get_wire_face_sample_point(region_face)
            if sample_point is None:
                continue
            wires = tuple(getattr(region_face, "Wires", []) or [])
            if not wires:
                continue
            records.append(
                {
                    "kind": "region-face",
                    "wire": wires[0],
                    "wires": wires,
                    "face": region_face,
                    "area": float(region_face.Area),
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

    def _get_region_record_wires(self, records):
        wires = []
        seen = set()
        for record in records or []:
            record_wires = list(record.get("wires") or [])
            if not record_wires and record.get("wire") is not None:
                record_wires = [record["wire"]]
            for wire in record_wires:
                if not wire or not wire.isClosed() or len(wire.Vertexes) < 3:
                    continue
                identity = self._get_wire_identity(wire)
                if identity in seen:
                    continue
                seen.add(identity)
                wires.append(wire)
        return wires

    def _count_region_inner_voids(self, records):
        inner_void_count = 0
        for record in records or []:
            if record.get("kind") == "region-face":
                inner_void_count += max(len(getattr(record.get("face"), "Wires", []) or []) - 1, 0)
                continue
            if record.get("depth") == 1:
                inner_void_count += 1
        return inner_void_count

    def _build_faces_from_wires(self, wires, require_single_outer=False):

        records = self._classify_wire_records(wires)
        if not records:
            return []

        return self._build_faces_from_records(records, require_single_outer=require_single_outer)

    def _build_faces_from_records(self, records, require_single_outer=False):
        if not records:
            return []

        top_level = [record for record in records if record["depth"] == 0]
        nested_islands = [
            record for record in records if record["depth"] > 0 and record["depth"] % 2 == 0
        ]
        if require_single_outer:
            if len(top_level) != 1 or nested_islands:
                return []
            face = self._build_face_from_region_record(records, top_level[0])
            if face is None:
                return []
            return [face]

        faces = []
        for outer in [record for record in records if record["depth"] % 2 == 0]:
            face = self._build_face_from_region_record(records, outer)
            if face is None:
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

    def _is_wall_object(self, obj):
        if not obj or self._is_space_object(obj):
            return False
        try:
            return Draft.getType(obj) == "Wall"
        except Exception:
            return False

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
            tangential_distance = self._get_boundary_face_tangential_distance(face, reference_point)
            if tangential_distance is None:
                tangential_distance = float("inf")
            sort_key = (-float(tangential_distance), facing_score, float(face.Area or 0.0))
            if best_sort_key is None or sort_key > best_sort_key:
                best_sort_key = sort_key
                best_face_name = f"Face{index}"
        if best_sort_key is None:
            return None
        return best_face_name

    def _get_wall_boundary_face_names(
        self, wall, reference_point=None, normal=None, face_name=None
    ):
        if not wall:
            return ()

        primary_face_name = str(face_name or "")
        if not primary_face_name:
            if normal is not None:
                primary_face_name = str(
                    self._get_wall_boundary_face_name_for_normal(
                        wall,
                        normal,
                        reference_point=reference_point,
                    )
                    or ""
                )
            if not primary_face_name:
                primary_face_name = str(
                    self._get_wall_boundary_face_name(wall, reference_point) or ""
                )
        if not primary_face_name:
            return ()

        primary_face = self._get_boundary_face(wall, primary_face_name)
        if primary_face is None:
            return ()
        primary_normal, _primary_center = self._get_boundary_face_normal_and_center(primary_face)
        if primary_normal is None:
            return (primary_face_name,)
        candidate_distance_limit = None
        if reference_point is not None:
            primary_tangential_distance = self._get_boundary_face_tangential_distance(
                primary_face,
                reference_point,
            )
            if primary_tangential_distance is not None:
                candidate_distance_limit = max(primary_tangential_distance * 2.0 + 1.0, 1500.0)

        face_names = [primary_face_name]
        candidates = []
        for index, candidate_face in enumerate(
            getattr(getattr(wall, "Shape", None), "Faces", []) or [], start=1
        ):
            candidate_face_name = f"Face{index}"
            if candidate_face_name == primary_face_name:
                continue
            face_normal, face_center = self._get_boundary_face_normal_and_center(candidate_face)
            if face_normal is None or face_center is None:
                continue
            normal_score = float(face_normal.dot(primary_normal))
            if normal_score <= 0.5:
                continue
            facing_score = 0.0
            if reference_point is not None:
                facing_score = float(
                    face_normal.dot(FreeCAD.Vector(reference_point).sub(face_center))
                )
                if facing_score <= 1e-7:
                    continue
                tangential_distance = self._get_boundary_face_tangential_distance(
                    candidate_face,
                    reference_point,
                )
                if (
                    candidate_distance_limit is not None
                    and tangential_distance is not None
                    and tangential_distance > candidate_distance_limit
                ):
                    continue
            else:
                tangential_distance = 0.0
            candidates.append(
                (
                    -float(tangential_distance or 0.0),
                    normal_score,
                    facing_score,
                    candidate_face_name,
                )
            )

        candidates.sort(reverse=True)
        face_names.extend(
            candidate_face_name for _distance, _score, _facing, candidate_face_name in candidates
        )
        return tuple(face_names)

    def _is_single_wall_side_face_set(self, wall, face_names):
        face_names = tuple(self.normalizeBoundarySubnames(face_names))
        if not wall or not face_names:
            return False
        primary_face = self._get_boundary_face(wall, face_names[0])
        if primary_face is None:
            return False
        primary_normal, _primary_center = self._get_boundary_face_normal_and_center(primary_face)
        if primary_normal is None:
            return False
        for face_name in face_names[1:]:
            candidate_face = self._get_boundary_face(wall, face_name)
            if candidate_face is None:
                return False
            candidate_normal, _candidate_center = self._get_boundary_face_normal_and_center(
                candidate_face
            )
            if candidate_normal is None or float(candidate_normal.dot(primary_normal)) <= 0.5:
                return False
        return True

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
            return self._get_wall_boundary_face_names(obj, reference_point=reference_point)

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
            "record_source": None,
            "wires": [],
            "region_faces": [],
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
        region_data = (
            self._get_horizontal_slice_region_data(section_edges)
            if section_edges
            else {"record_source": None, "wires": [], "region_faces": [], "records": []}
        )
        wires = region_data["wires"]
        region_faces = region_data["region_faces"]
        records = region_data["records"]
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
                "record_source": region_data["record_source"],
                "wires": wires,
                "region_faces": region_faces,
                "records": records,
                "top_level": top_level,
                "nested_islands": nested_islands,
                "supports_single_outer": len(top_level) == 1
                and len(region_faces) == 1
                and not nested_islands,
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

            records = analysis["records"]
            if not records:
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
        if not loop_analysis.get("records"):
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
        inner_void_count = self._count_region_inner_voids(loop_analysis.get("records", []))
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
        inner_void_count = self._count_region_inner_voids(loop_analysis.get("records", []))
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
        if outer_record.get("kind") == "region-face":
            face = self._copy_without_element_map(outer_record.get("face"))
            if face is None:
                face = outer_record.get("face")
            if face is None or getattr(face, "Area", 0.0) <= 0.000001:
                return None
            return face
        wires_for_face = [outer_record["wire"]]
        wires_for_face.extend(
            record["wire"]
            for record in records or []
            if record.get("parent") is outer_record
            and record.get("depth") == outer_record.get("depth", 0) + 1
        )
        face = self._make_transient_face_from_wires(wires_for_face)
        if face is None:
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

    def _select_boundary_region_record(
        self, records, top_level, reference_point, require_containment=False
    ):
        if not top_level or reference_point is None:
            return None

        reference_point = FreeCAD.Vector(reference_point)
        best_record = None
        best_sort_key = None
        for record in top_level:
            sample_point = record.get("sample")
            if sample_point is None:
                continue
            sample_point = FreeCAD.Vector(sample_point)
            plan_reference = FreeCAD.Vector(reference_point.x, reference_point.y, sample_point.z)
            region_face = self._build_face_from_region_record(records, record)
            contains_reference = False
            if region_face is not None:
                try:
                    contains_reference = bool(region_face.isInside(plan_reference, 0.001, True))
                except Exception:
                    contains_reference = False
            if require_containment and not contains_reference:
                continue
            distance = float(sample_point.sub(plan_reference).Length)
            sort_key = (
                0 if contains_reference else 1,
                distance,
                -float(record.get("area", 0.0) or 0.0),
            )
            if best_sort_key is None or sort_key < best_sort_key:
                best_sort_key = sort_key
                best_record = record
        return best_record

    def _build_shape_from_boundary_region_reference(
        self, boundary_faces, reference_point, loop_analysis=None
    ):
        if not boundary_faces or reference_point is None:
            return None
        analysis = loop_analysis or self._analyze_boundary_loops(boundary_faces)
        outer_record = self._select_boundary_region_record(
            analysis.get("records", []),
            analysis.get("top_level", []),
            reference_point,
        )
        if outer_record is None:
            return None
        return self._build_shape_from_boundary_region(
            boundary_faces,
            outer_record,
            loop_analysis=analysis,
        )

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

        inner_void_count = self._count_region_inner_voids(loop_analysis.get("records", []))
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
        self._set_boundary_status(obj, _BOUNDARY_STATUS_OK)
        shape = None
        stored_boundary_links = self.normalizeBoundaryLinks(self._get_boundary_storage_links(obj))
        boundary_links = self._get_stable_boundary_links(obj)
        boundary_links_changed = stored_boundary_links != boundary_links
        boundary_faces = self._get_boundary_faces_from_links(boundary_links)
        loop_analysis = self._analyze_boundary_loops(boundary_faces) if boundary_faces else None
        stored_boundary_reference = self._get_boundary_region_reference_point(obj)
        boundary_reference = stored_boundary_reference
        if boundary_reference is None:
            boundary_reference = self._get_space_shape_reference_point(obj)
        pl = obj.Placement
        retrying_boundary_conflict = self._pop_pending_boundary_conflict_retry(obj)

        if (
            boundary_faces
            and boundary_reference is not None
            and self._is_usable_solid_shape(getattr(obj, "Shape", None))
        ):
            current_region_record = None
            if loop_analysis and loop_analysis.get("top_level"):
                current_region_record = self._select_boundary_region_record(
                    loop_analysis.get("records", []),
                    loop_analysis.get("top_level", []),
                    boundary_reference,
                    require_containment=True,
                )

            if current_region_record is None:
                seeded_boundary_faces = self.getBoundaryFacesFromLinks(
                    boundary_links,
                    seed_space=obj,
                )
                if len(seeded_boundary_faces) > len(boundary_faces):
                    seeded_loop_analysis = self._analyze_boundary_loops(seeded_boundary_faces)
                    seeded_region_record = None
                    if seeded_loop_analysis.get("top_level"):
                        seeded_region_record = self._select_boundary_region_record(
                            seeded_loop_analysis.get("records", []),
                            seeded_loop_analysis.get("top_level", []),
                            boundary_reference,
                            require_containment=True,
                        )
                    if seeded_region_record is not None:
                        boundary_faces = seeded_boundary_faces
                        loop_analysis = seeded_loop_analysis

        # print("starting compute")

        if (
            boundary_faces
            and loop_analysis
            and stored_boundary_reference is not None
            and len(boundary_links) > 1
            and not loop_analysis.get("top_level")
        ):
            label = str(
                getattr(obj, "Label", "") or getattr(obj, "Name", "") or translate("Arch", "Space")
            )
            message, details = self._describe_boundary_region_reference_conflict(label)
            if (
                boundary_links_changed
                and not retrying_boundary_conflict
                and self._schedule_boundary_conflict_retry(obj)
            ):
                return
            if self._preserve_current_shape_with_boundary_conflict(
                obj,
                pl,
                message=message,
                details=details,
            ):
                return

        if self._can_preserve_current_legacy_region_shape(obj, boundary_faces, loop_analysis):
            current_shape = self._copy_without_element_map(getattr(obj, "Shape", None))
            if current_shape is not None and current_shape.Solids:
                shape = self.processSubShapes(obj, current_shape.Solids[0], pl)
                self.applyShape(obj, shape, pl)
                self._sync_area_properties(obj)
                self._sync_boundary_region_hint(obj, shape)
                self._sync_boundary_side_hints(obj, shape)
                self._set_boundary_status(obj, _BOUNDARY_STATUS_OK)
                return

        if boundary_faces and loop_analysis and loop_analysis.get("top_level"):
            selected_region_record = None
            if boundary_reference is not None:
                selected_region_record = self._select_boundary_region_record(
                    loop_analysis.get("records", []),
                    loop_analysis.get("top_level", []),
                    boundary_reference,
                    require_containment=True,
                )
                if selected_region_record is None:
                    label = str(
                        getattr(obj, "Label", "")
                        or getattr(obj, "Name", "")
                        or translate("Arch", "Space")
                    )
                    message, details = self._describe_boundary_region_reference_conflict(label)
                    if (
                        boundary_links_changed
                        and not retrying_boundary_conflict
                        and self._schedule_boundary_conflict_retry(obj)
                    ):
                        return
                    if self._preserve_current_shape_with_boundary_conflict(
                        obj,
                        pl,
                        message=message,
                        details=details,
                        initialize_boundary_region_point=(
                            boundary_reference if stored_boundary_reference is None else None
                        ),
                    ):
                        return
            elif loop_analysis["supports_single_outer"]:
                selected_region_record = loop_analysis.get("top_level", [None])[0]

            if selected_region_record is not None:
                region_shape = self._build_shape_from_boundary_region(
                    boundary_faces,
                    selected_region_record,
                    loop_analysis=loop_analysis,
                )
                if region_shape is not None:
                    shape = self.processSubShapes(obj, region_shape.Solids[0], pl)
                    self.applyShape(obj, shape, pl)
                    self._sync_area_properties(obj)
                    self._sync_boundary_region_hint(
                        obj,
                        shape,
                        record=selected_region_record,
                    )
                    self._sync_boundary_side_hints(obj, shape)
                    return

                if boundary_reference is not None:
                    label = str(
                        getattr(obj, "Label", "")
                        or getattr(obj, "Name", "")
                        or translate("Arch", "Space")
                    )
                    message, details = self._describe_boundary_region_reference_conflict(label)
                    if (
                        boundary_links_changed
                        and not retrying_boundary_conflict
                        and self._schedule_boundary_conflict_retry(obj)
                    ):
                        return
                    if self._preserve_current_shape_with_boundary_conflict(
                        obj,
                        pl,
                        message=message,
                        details=details,
                        initialize_boundary_region_point=(
                            boundary_reference if stored_boundary_reference is None else None
                        ),
                    ):
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
                self._sync_boundary_region_hint(obj, shape)
                self._sync_boundary_side_hints(obj, shape)
                self._set_boundary_status(obj, _BOUNDARY_STATUS_OK)
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
                self._set_boundary_status(obj, _BOUNDARY_STATUS_INVALID, message, details)
                self._report_boundary_failure(message, details)
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
                self._sync_boundary_region_hint(obj, shape)
                self._sync_boundary_side_hints(obj, shape)
                self._set_boundary_status(obj, _BOUNDARY_STATUS_OK)

                return

        label = str(
            getattr(obj, "Label", "") or getattr(obj, "Name", "") or translate("Arch", "Space")
        )
        message, details = self._describe_boundary_failure(
            label, boundary_faces, has_base_shape=has_base_shape
        )
        self._set_boundary_failure(message, details)
        self._set_boundary_status(obj, _BOUNDARY_STATUS_INVALID, message, details)
        self._report_boundary_failure(message, details)

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


class _SpaceBoundaryAnalyzer(_Space):
    """Reusable boundary analysis helper for Plan Edit and tests."""

    def __init__(self):
        # This adapter intentionally exposes the pure boundary-analysis surface of
        # ``_Space`` without binding to a real document object or registering
        # Arch component properties.
        pass


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


def getStableBoundaryLinks(space):
    """Resolve the current stable boundary links for a space."""

    proxy = getattr(space, "Proxy", None)
    stable_links = getattr(proxy, "getStableBoundaryLinks", None)
    if callable(stable_links):
        return stable_links(space)
    return []


def setBoundaryLinks(space, boundaries):
    """Store explicit boundary links, using semantic wall-side storage when available."""

    proxy = getattr(space, "Proxy", None)
    setter = getattr(proxy, "setBoundaryLinks", None)
    if callable(setter):
        setter(space, boundaries)


def setBoundaryRegionReferencePoint(space, point):
    """Store an explicit interior reference point for choosing a boundary-derived room region."""

    proxy = getattr(space, "Proxy", None)
    setter = getattr(proxy, "setBoundaryRegionReferencePoint", None)
    if callable(setter):
        setter(space, point)


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


def _get_length_value(value, default=0.0):
    try:
        return float(value.Value)
    except Exception:
        try:
            return float(value)
        except Exception:
            return default


def _get_object_global_placement(obj):
    if not obj:
        return FreeCAD.Placement()
    if hasattr(obj, "getGlobalPlacement"):
        try:
            placement = obj.getGlobalPlacement()
            if placement is not None:
                return placement
        except Exception:
            pass
    return getattr(obj, "Placement", FreeCAD.Placement())


def _get_linked_object(obj):
    if not obj or getattr(obj, "TypeId", "") != "App::Link":
        return None
    linked = getattr(obj, "LinkedObject", None)
    if linked is not None:
        return linked
    if hasattr(obj, "getLinkedObject"):
        try:
            return obj.getLinkedObject(True)
        except TypeError:
            try:
                return obj.getLinkedObject()
            except Exception:
                return None
        except Exception:
            return None
    return None


def _is_direct_equipment_object(obj):
    if not obj:
        return False
    try:
        if Draft.getType(obj) == "Equipment":
            return True
    except Exception:
        pass
    proxy = getattr(obj, "Proxy", None)
    return getattr(proxy, "Type", None) == "Equipment"


def _has_authored_plan_symbols(obj):
    try:
        if "PlanSymbols" not in (getattr(obj, "PropertiesList", []) or []):
            return False
        return any(symbol is not None for symbol in (getattr(obj, "PlanSymbols", []) or []))
    except Exception:
        return False


def _has_local_plan_footprint_provider(obj):
    view_object = getattr(obj, "ViewObject", None)
    view_proxy = getattr(view_object, "Proxy", None) if view_object else None
    return bool(view_proxy and hasattr(view_proxy, "_collect_local_footprint_polylines"))


def _get_space_label_obstacle_semantic_object(obj):
    if not obj:
        return None
    try:
        if getattr(obj, "IsLibraryDefinition", False) and getattr(obj, "TypeId", "") != "App::Link":
            return None
    except Exception:
        pass
    view_object = getattr(obj, "ViewObject", None)
    if view_object is not None:
        try:
            if not view_object.Visibility:
                return None
        except Exception:
            pass
    if _has_local_plan_footprint_provider(obj):
        return obj

    semantic = obj
    seen = set()
    while getattr(semantic, "TypeId", "") == "App::Link":
        name = getattr(semantic, "Name", None)
        if name in seen:
            break
        if name:
            seen.add(name)
        linked = _get_linked_object(semantic)
        if linked is None or linked is semantic:
            break
        semantic = linked

    if _has_local_plan_footprint_provider(semantic):
        return semantic
    if _is_direct_equipment_object(semantic):
        return semantic
    return None


def _vector_from_point(point):
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        z_value = point[2] if len(point) > 2 else 0.0
        return FreeCAD.Vector(point[0], point[1], z_value)
    except Exception:
        return None


def _iter_plan_obstacle_local_points(obj):
    view_object = getattr(obj, "ViewObject", None)
    view_proxy = getattr(view_object, "Proxy", None) if view_object else None
    if view_proxy and hasattr(view_proxy, "_collect_local_footprint_polylines"):
        try:
            yielded = False
            for polyline in view_proxy._collect_local_footprint_polylines() or []:
                for point in polyline:
                    vector = _vector_from_point(point)
                    if vector is not None:
                        yielded = True
                        yield vector
            if yielded:
                return
        except Exception:
            pass

    if not _is_direct_equipment_object(obj) or not _has_authored_plan_symbols(obj):
        return

    try:
        import ArchEquipment

        shapes = ArchEquipment.get_plan_representation_shapes(obj)
    except Exception:
        shapes = ()

    for shape in shapes or ():
        vertices = getattr(shape, "Vertexes", None) or ()
        if vertices:
            for vertex in vertices:
                point = getattr(vertex, "Point", None)
                if point is not None:
                    yield FreeCAD.Vector(point)
            continue
        try:
            bb = shape.BoundBox
            for x in (bb.XMin, bb.XMax):
                for y in (bb.YMin, bb.YMax):
                    yield FreeCAD.Vector(x, y, bb.ZMin)
        except Exception:
            pass


def _bounds_from_points(points):
    points = list(points or ())
    if not points:
        return None
    return (
        min(float(point.x) for point in points),
        min(float(point.y) for point in points),
        max(float(point.x) for point in points),
        max(float(point.y) for point in points),
        min(float(point.z) for point in points),
        max(float(point.z) for point in points),
    )


def _bounds_center(bounds):
    return FreeCAD.Vector(
        (bounds[0] + bounds[2]) * 0.5,
        (bounds[1] + bounds[3]) * 0.5,
        (bounds[4] + bounds[5]) * 0.5,
    )


def _bounds_intersect_xy(first, second):
    return not (
        first[2] < second[0] or first[0] > second[2] or first[3] < second[1] or first[1] > second[3]
    )


def _bounds_intersection_area_xy(first, second):
    if not _bounds_intersect_xy(first, second):
        return 0.0
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0.0,
        min(first[3], second[3]) - max(first[1], second[1]),
    )


def _bounds_distance_xy(first, second):
    dx = max(second[0] - first[2], first[0] - second[2], 0.0)
    dy = max(second[1] - first[3], first[1] - second[3], 0.0)
    return math.hypot(dx, dy)


def _bounds_signed_distance_xy(first, second):
    x_overlap, y_overlap = _bounds_projection_overlap_xy(first, second)
    if x_overlap > 0.0 and y_overlap > 0.0:
        return -min(x_overlap, y_overlap)
    return _bounds_distance_xy(first, second)


def _point_in_polyline_xy(point, polyline):
    points = list(polyline or ())
    if len(points) < 3:
        return False
    inside = False
    x = float(point.x)
    y = float(point.y)
    previous = points[-1]
    for current in points:
        x1 = float(previous.x)
        y1 = float(previous.y)
        x2 = float(current.x)
        y2 = float(current.y)
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            x_at_y = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x < x_at_y:
                inside = not inside
        previous = current
    return inside


def _point_in_space_footprint(faces, point):
    for face in faces or ():
        try:
            bb = face.BoundBox
            if (
                point.x < bb.XMin - 0.001
                or point.x > bb.XMax + 0.001
                or point.y < bb.YMin - 0.001
                or point.y > bb.YMax + 0.001
            ):
                continue
            test_point = FreeCAD.Vector(point.x, point.y, face.CenterOfMass.z)
            if face.isInside(test_point, 0.001, True):
                return True
        except Exception:
            pass
        try:
            for polyline in ArchPlanGeometry.get_face_wire_polylines([face]):
                if _point_in_polyline_xy(point, polyline):
                    return True
        except Exception:
            pass
    return False


def _bounds_touches_space_footprint(faces, bounds):
    center = _bounds_center(bounds)
    if _point_in_space_footprint(faces, center):
        return True
    for x in (bounds[0], bounds[2]):
        for y in (bounds[1], bounds[3]):
            if _point_in_space_footprint(faces, FreeCAD.Vector(x, y, center.z)):
                return True
    return False


def _get_space_footprint_faces(space):
    proxy = getattr(space, "Proxy", None)
    if proxy and hasattr(proxy, "getFootprint"):
        try:
            faces = proxy.getFootprint(space) or ()
            if faces:
                return tuple(faces)
        except Exception:
            pass
    shape = getattr(space, "Shape", None)
    return tuple(getattr(shape, "Faces", []) or ())


def _get_default_space_text_position(space):
    try:
        shape = space.Shape
        pos = shape.CenterOfMass
        return FreeCAD.Vector(pos.x, pos.y, shape.BoundBox.ZMin)
    except (AttributeError, RuntimeError):
        return FreeCAD.Vector()


def _estimate_space_text_box(vobj):
    text_lines = []
    for line in getattr(vobj, "Text", []) or []:
        line = str(line or "")
        if not line:
            continue
        if hasattr(vobj, "Object"):
            line = line.replace("$label", getattr(vobj.Object, "Label", ""))
            if "$area" in line and hasattr(vobj.Object, "Area"):
                area_value = _get_length_value(getattr(vobj.Object, "Area", 0.0))
                line = line.replace("$area", "{:.2f}".format(area_value))
        text_lines.append(line)
    if not text_lines:
        text_lines = [getattr(getattr(vobj, "Object", None), "Label", "") or " "]

    font_size = max(_get_length_value(getattr(vobj, "FontSize", 0.0), 1.0), 1.0)
    first_line = max(_get_length_value(getattr(vobj, "FirstLine", font_size), font_size), 1.0)
    line_spacing = max(float(getattr(vobj, "LineSpacing", 1.0) or 1.0), 0.1)

    widths = []
    for index, line in enumerate(text_lines):
        size = first_line if index == 0 else font_size
        widths.append(max(1, len(line)) * size * 0.58)
    width = max(widths or [font_size])
    below = font_size * 0.6 * max(1, len(text_lines) - 1)
    above = first_line * line_spacing + font_size * line_spacing * max(0, len(text_lines) - 2)
    padding = max(font_size, first_line) * 0.35
    return {
        "width": width + padding * 2.0,
        "below": below + padding,
        "above": above + padding,
        "padding": padding,
    }


def _get_label_candidate_bounds(point, text_box, text_align="Center"):
    width = float(text_box.get("width", 0.0) or 0.0)
    below = float(text_box.get("below", 0.0) or 0.0)
    above = float(text_box.get("above", 0.0) or 0.0)
    if text_align == "Left":
        xmin = point.x
        xmax = point.x + width
    elif text_align == "Right":
        xmin = point.x - width
        xmax = point.x
    else:
        xmin = point.x - width * 0.5
        xmax = point.x + width * 0.5
    return (xmin, point.y - below, xmax, point.y + above, point.z, point.z)


def _get_space_boundary_polylines(faces):
    polylines = []
    for face in faces or ():
        try:
            polylines.extend(ArchPlanGeometry.get_face_wire_polylines([face]))
        except Exception:
            continue
    return tuple(tuple(FreeCAD.Vector(point) for point in polyline) for polyline in polylines)


def _distance_point_to_segment_xy(point, start, end):
    px = float(point.x)
    py = float(point.y)
    x1 = float(start.x)
    y1 = float(start.y)
    x2 = float(end.x)
    y2 = float(end.y)
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x = x1 + dx * t
    proj_y = y1 + dy * t
    return math.hypot(px - proj_x, py - proj_y)


def _distance_point_to_boundary_polylines_xy(point, boundary_polylines):
    best = None
    for polyline in boundary_polylines or ():
        points = list(polyline or ())
        if len(points) < 2:
            continue
        for start, end in zip(points, points[1:]):
            distance = _distance_point_to_segment_xy(point, start, end)
            if best is None or distance < best:
                best = distance
    return 0.0 if best is None else best


def _space_text_distance_to_default(point, default_point):
    dx = float(point.x) - float(default_point.x)
    dy = float(point.y) - float(default_point.y)
    return math.hypot(dx, dy * _SPACE_TEXT_VERTICAL_DISTANCE_WEIGHT)


def _distance_point_to_bounds_xy(point, bounds, vertical_weight=1.0):
    dx = max(bounds[0] - float(point.x), float(point.x) - bounds[2], 0.0)
    dy = max(bounds[1] - float(point.y), float(point.y) - bounds[3], 0.0)
    return math.hypot(dx, dy * vertical_weight)


def _iter_label_sample_points(candidate_bounds):
    xmin, ymin, xmax, ymax, zmin, _zmax = candidate_bounds
    center_x = (xmin + xmax) * 0.5
    center_y = (ymin + ymax) * 0.5
    points = (
        FreeCAD.Vector(center_x, center_y, zmin),
        FreeCAD.Vector(xmin, ymin, zmin),
        FreeCAD.Vector(xmin, ymax, zmin),
        FreeCAD.Vector(xmax, ymin, zmin),
        FreeCAD.Vector(xmax, ymax, zmin),
        FreeCAD.Vector(center_x, ymin, zmin),
        FreeCAD.Vector(center_x, ymax, zmin),
        FreeCAD.Vector(xmin, center_y, zmin),
        FreeCAD.Vector(xmax, center_y, zmin),
    )
    return points


def _get_candidate_room_signed_distance(faces, boundary_polylines, candidate_bounds):
    signed_distances = []
    for sample in _iter_label_sample_points(candidate_bounds):
        boundary_distance = _distance_point_to_boundary_polylines_xy(sample, boundary_polylines)
        if _point_in_space_footprint(faces, sample):
            signed_distances.append(boundary_distance)
        else:
            signed_distances.append(-boundary_distance)
    return min(signed_distances or [float("-inf")])


def _get_candidate_feasible_signed_distance(
    faces, boundary_polylines, candidate_bounds, obstacle_bounds, preferred_clearance
):
    room_margin = _get_candidate_room_signed_distance(faces, boundary_polylines, candidate_bounds)
    obstacle_margin = min(
        (
            _bounds_signed_distance_xy(candidate_bounds, obstacle) - preferred_clearance
            for obstacle in obstacle_bounds or ()
        ),
        default=float("inf"),
    )
    return min(room_margin, obstacle_margin)


def _get_space_text_search_precision(space_bounds, text_box):
    width = max(float(space_bounds[2] - space_bounds[0]), 0.0)
    height = max(float(space_bounds[3] - space_bounds[1]), 0.0)
    label_scale = max(
        float(text_box.get("width", 0.0) or 0.0),
        float(text_box.get("above", 0.0) or 0.0) + float(text_box.get("below", 0.0) or 0.0),
    )
    return max(min(width, height, max(label_scale * 0.1, 25.0)), 10.0)


def _search_best_space_text_anchor(
    default_point,
    faces,
    boundary_polylines,
    space_bounds,
    text_box,
    text_align,
    obstacle_bounds,
    preferred_clearance,
):
    xmin, ymin, xmax, ymax, zmin, _zmax = space_bounds
    width = xmax - xmin
    height = ymax - ymin
    if width <= 1e-6 or height <= 1e-6:
        return default_point

    class _Cell:
        __slots__ = ("x", "y", "half_size", "distance", "max_distance", "distance_to_default")

        def __init__(self, x, y, half_size):
            self.x = float(x)
            self.y = float(y)
            self.half_size = float(half_size)
            point = FreeCAD.Vector(self.x, self.y, zmin)
            candidate_bounds = _get_label_candidate_bounds(point, text_box, text_align)
            self.distance = _get_candidate_feasible_signed_distance(
                faces, boundary_polylines, candidate_bounds, obstacle_bounds, preferred_clearance
            )
            self.max_distance = self.distance + self.half_size * math.sqrt(2.0)
            self.distance_to_default = _space_text_distance_to_default(point, default_point)

    def _cell_key(cell):
        return (-cell.max_distance, -cell.distance, cell.distance_to_default)

    def _is_better(left, right):
        if left.distance > right.distance + 1e-6:
            return True
        if abs(left.distance - right.distance) <= 1e-6:
            return left.distance_to_default < right.distance_to_default - 1e-6
        return False

    cell_size = min(width, height)
    half_size = cell_size * 0.5
    cells = []
    x = xmin
    while x < xmax - 1e-6:
        y = ymin
        while y < ymax - 1e-6:
            cells.append(_Cell(x + half_size, y + half_size, half_size))
            y += cell_size
        x += cell_size

    best = _Cell(default_point.x, default_point.y, 0.0)
    bbox_center = _Cell(xmin + width * 0.5, ymin + height * 0.5, 0.0)
    if _is_better(bbox_center, best):
        best = bbox_center

    heap = [
        (_cell_key(index_cell[1]), index_cell[0], index_cell[1]) for index_cell in enumerate(cells)
    ]
    heapq.heapify(heap)
    precision = _get_space_text_search_precision(space_bounds, text_box)
    next_index = len(cells)

    while heap:
        _key, _index, cell = heapq.heappop(heap)
        if _is_better(cell, best):
            best = cell
        if cell.max_distance - best.distance <= precision or cell.half_size <= precision * 0.5:
            continue

        next_half = cell.half_size * 0.5
        for dx in (-next_half, next_half):
            for dy in (-next_half, next_half):
                child = _Cell(cell.x + dx, cell.y + dy, next_half)
                heapq.heappush(heap, (_cell_key(child), next_index, child))
                next_index += 1

    return FreeCAD.Vector(best.x, best.y, zmin)


def _search_nearest_feasible_space_text_anchor(
    default_point,
    faces,
    boundary_polylines,
    space_bounds,
    text_box,
    text_align,
    obstacle_bounds,
    preferred_clearance,
    target_distance,
):
    xmin, ymin, xmax, ymax, zmin, _zmax = space_bounds
    width = xmax - xmin
    height = ymax - ymin
    if width <= 1e-6 or height <= 1e-6:
        return None

    class _Cell:
        __slots__ = ("x", "y", "half_size", "distance", "max_distance", "min_distance_to_default")

        def __init__(self, x, y, half_size):
            self.x = float(x)
            self.y = float(y)
            self.half_size = float(half_size)
            point = FreeCAD.Vector(self.x, self.y, zmin)
            candidate_bounds = _get_label_candidate_bounds(point, text_box, text_align)
            self.distance = _get_candidate_feasible_signed_distance(
                faces, boundary_polylines, candidate_bounds, obstacle_bounds, preferred_clearance
            )
            self.max_distance = self.distance + self.half_size * math.sqrt(2.0)
            self.min_distance_to_default = _distance_point_to_bounds_xy(
                default_point,
                (
                    self.x - self.half_size,
                    self.y - self.half_size,
                    self.x + self.half_size,
                    self.y + self.half_size,
                    zmin,
                    zmin,
                ),
                vertical_weight=_SPACE_TEXT_VERTICAL_DISTANCE_WEIGHT,
            )

    cell_size = min(width, height)
    half_size = cell_size * 0.5
    cells = []
    x = xmin
    while x < xmax - 1e-6:
        y = ymin
        while y < ymax - 1e-6:
            cells.append(_Cell(x + half_size, y + half_size, half_size))
            y += cell_size
        x += cell_size

    precision = _get_space_text_search_precision(space_bounds, text_box)
    heap = [
        ((cell.min_distance_to_default, -cell.max_distance), index, cell)
        for index, cell in enumerate(cells)
        if cell.max_distance >= target_distance - precision
    ]
    heapq.heapify(heap)
    next_index = len(cells)
    best = None

    default_cell = _Cell(default_point.x, default_point.y, 0.0)
    if default_cell.distance >= target_distance - 1e-6:
        best = default_cell

    while heap:
        _key, _index, cell = heapq.heappop(heap)
        if cell.max_distance < target_distance - precision:
            continue
        if (
            best is not None
            and cell.min_distance_to_default > best.min_distance_to_default + precision
        ):
            continue
        if cell.distance >= target_distance - 1e-6:
            if best is None or cell.min_distance_to_default < best.min_distance_to_default - 1e-6:
                best = cell
                if cell.half_size <= precision * 0.5:
                    continue
        if cell.half_size <= precision * 0.5:
            continue

        next_half = cell.half_size * 0.5
        for dx in (-next_half, next_half):
            for dy in (-next_half, next_half):
                child = _Cell(cell.x + dx, cell.y + dy, next_half)
                if child.max_distance < target_distance - precision:
                    continue
                heapq.heappush(
                    heap,
                    ((child.min_distance_to_default, -child.max_distance), next_index, child),
                )
                next_index += 1

    if best is None:
        return None
    return FreeCAD.Vector(best.x, best.y, zmin)


def _collect_space_label_obstacle_bounds(space, faces):
    doc = getattr(space, "Document", None) or FreeCAD.ActiveDocument
    if doc is None:
        return ()
    try:
        space_bb = space.Shape.BoundBox
        space_bounds = (
            float(space_bb.XMin),
            float(space_bb.YMin),
            float(space_bb.XMax),
            float(space_bb.YMax),
            float(space_bb.ZMin),
            float(space_bb.ZMax),
        )
    except Exception:
        space_bounds = None
    obstacles = []
    for obj in getattr(doc, "Objects", []) or []:
        if obj is space:
            continue
        semantic = _get_space_label_obstacle_semantic_object(obj)
        if semantic is None or semantic is space:
            continue
        local_points = list(_iter_plan_obstacle_local_points(semantic))
        if not local_points:
            continue
        placement = _get_object_global_placement(obj)
        try:
            global_points = [placement.multVec(point) for point in local_points]
        except Exception:
            continue
        bounds = _bounds_from_points(global_points)
        if bounds is None:
            continue
        if space_bounds is not None and not _bounds_intersect_xy(space_bounds, bounds):
            continue
        if space_bounds is not None and (
            bounds[5] < space_bounds[4] - 1.0 or bounds[4] > space_bounds[5] + 1.0
        ):
            continue
        if not _bounds_touches_space_footprint(faces, bounds):
            continue
        obstacles.append(bounds)
    return tuple(obstacles)


def refresh_auto_space_text_positions(doc, changed_bounds=None):
    """Refresh auto-positioned space labels in a GUI document without recomputing geometry."""

    if (not FreeCAD.GuiUp) or (doc is None):
        return 0

    import DraftVecUtils

    refreshed = 0
    for obj in getattr(doc, "Objects", []) or []:
        if type(getattr(obj, "Proxy", None)).__name__ != "_Space":
            continue

        if changed_bounds is not None:
            try:
                space_bb = obj.Shape.BoundBox
                space_bounds = (
                    float(space_bb.XMin),
                    float(space_bb.YMin),
                    float(space_bb.XMax),
                    float(space_bb.YMax),
                    float(space_bb.ZMin),
                    float(space_bb.ZMax),
                )
            except Exception:
                space_bounds = None

            if space_bounds is not None and not _bounds_intersect_xy(space_bounds, changed_bounds):
                continue
            if space_bounds is not None and (
                changed_bounds[5] < space_bounds[4] - 1.0
                or changed_bounds[4] > space_bounds[5] + 1.0
            ):
                continue
            if space_bounds is not None:
                faces = _get_space_footprint_faces(obj)
                if faces and not _bounds_touches_space_footprint(faces, changed_bounds):
                    continue

        vobj = getattr(obj, "ViewObject", None)
        if not vobj or not hasattr(vobj, "TextPosition"):
            continue
        if not DraftVecUtils.isNull(vobj.TextPosition):
            continue

        proxy = getattr(vobj, "Proxy", None)
        if not proxy or not hasattr(proxy, "onChanged"):
            continue

        try:
            proxy.onChanged(vobj, "TextPosition")
        except Exception:
            continue
        refreshed += 1

    return refreshed


def run_scheduled_auto_space_text_refresh(doc_name):
    changed_bounds = _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES.pop(doc_name, "__missing__")
    if changed_bounds == "__missing__":
        return 0

    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        doc = None
    if doc is None:
        return 0
    return refresh_auto_space_text_positions(doc, changed_bounds=changed_bounds)


def schedule_auto_space_text_refresh(doc, changed_bounds=None):
    if (not FreeCAD.GuiUp) or (doc is None):
        return 0

    doc_name = getattr(doc, "Name", None)
    if not doc_name:
        return 0

    if doc_name in _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES:
        existing_bounds = _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES[doc_name]
        if existing_bounds is None or changed_bounds is None:
            _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES[doc_name] = None
        else:
            _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES[doc_name] = ArchComponent._union_bounds(
                existing_bounds, changed_bounds
            )
        return 1

    _SCHEDULED_AUTO_SPACE_TEXT_REFRESHES[doc_name] = changed_bounds
    try:
        QtCore.QTimer.singleShot(
            0, lambda name=doc_name: run_scheduled_auto_space_text_refresh(name)
        )
    except Exception:
        return run_scheduled_auto_space_text_refresh(doc_name)
    return 1


def _get_space_text_minimum_clearance(text_box):
    height = float(text_box.get("above", 0.0) or 0.0) + float(text_box.get("below", 0.0) or 0.0)
    padding = float(text_box.get("padding", 0.0) or 0.0)
    return max(height * 0.5, padding * 2.0, 150.0)


def _bounds_projection_overlap_xy(bounds_a, bounds_b):
    x_overlap = min(bounds_a[2], bounds_b[2]) - max(bounds_a[0], bounds_b[0])
    y_overlap = min(bounds_a[3], bounds_b[3]) - max(bounds_a[1], bounds_b[1])
    return max(0.0, x_overlap), max(0.0, y_overlap)


def _get_automatic_space_text_position(space, text_box=None, text_align="Center"):
    default_point = _get_default_space_text_position(space)
    faces = _get_space_footprint_faces(space)
    if not faces:
        return default_point
    obstacles = _collect_space_label_obstacle_bounds(space, faces)
    if not obstacles:
        return default_point
    text_box = text_box or {"width": 0.0, "below": 0.0, "above": 0.0, "padding": 0.0}
    minimum_clearance = _get_space_text_minimum_clearance(text_box)
    default_bounds = _get_label_candidate_bounds(default_point, text_box, text_align)
    if all(not _bounds_intersect_xy(default_bounds, obstacle) for obstacle in obstacles):
        return default_point

    try:
        shape_bounds = space.Shape.BoundBox
        space_bounds = (
            float(shape_bounds.XMin),
            float(shape_bounds.YMin),
            float(shape_bounds.XMax),
            float(shape_bounds.YMax),
            float(shape_bounds.ZMin),
            float(shape_bounds.ZMax),
        )
    except Exception:
        return default_point

    boundary_polylines = _get_space_boundary_polylines(faces)
    best_point = _search_best_space_text_anchor(
        default_point,
        faces,
        boundary_polylines,
        space_bounds,
        text_box,
        text_align,
        obstacles,
        0.0,
    )
    nearest_point = _search_nearest_feasible_space_text_anchor(
        default_point,
        faces,
        boundary_polylines,
        space_bounds,
        text_box,
        text_align,
        obstacles,
        0.0,
        minimum_clearance,
    )
    if nearest_point is not None:
        return nearest_point
    return best_point


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
        schedule_auto_space_text_refresh(getattr(vobj.Object, "Document", None))

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
                text_align = getattr(vobj, "TextAlign", "Center")
                pos = _get_automatic_space_text_position(
                    vobj.Object,
                    text_box=_estimate_space_text_box(vobj),
                    text_align=text_align,
                )
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
            boundaries = []
            proxy = getattr(self.obj, "Proxy", None)
            stable_links = getattr(proxy, "getStableBoundaryLinks", None)
            if callable(stable_links):
                try:
                    boundaries = list(stable_links(self.obj) or [])
                except Exception:
                    boundaries = []
            if not boundaries:
                boundaries = list(getattr(self.obj, "Boundaries", []) or [])
            for b in boundaries:
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
                self.obj.Boundaries = [
                    b
                    for b in list(getattr(self.obj, "Boundaries", []) or [])
                    if getattr(b[0], "Name", None) != on
                ]
                if hasattr(self.obj, "BoundaryWalls"):
                    self.obj.BoundaryWalls = [
                        wall
                        for wall in list(getattr(self.obj, "BoundaryWalls", []) or [])
                        if getattr(wall, "Name", None) != on
                    ]
                self.updateBoundaries()
