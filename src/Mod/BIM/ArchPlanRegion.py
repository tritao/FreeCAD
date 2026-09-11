# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026                                                    *
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

"""Virtual polygonal plan-region object used for semantic plan zoning."""

import FreeCAD

import ArchCommands
import ArchComponent

from draftutils import params

if FreeCAD.GuiUp:
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt


_KITCHEN_PLANNING_MODES = ["Auto", "SingleRun", "Galley", "L", "U"]
_KITCHEN_PRIMARY_EDGE_INDEX_AUTO = -1


def _copy_vector(value, default=None):
    if isinstance(value, FreeCAD.Vector):
        return FreeCAD.Vector(value.x, value.y, value.z)
    if value is None:
        return FreeCAD.Vector(default) if default is not None else None
    try:
        z = value[2] if len(value) > 2 else 0.0
        return FreeCAD.Vector(value[0], value[1], z)
    except Exception:
        return FreeCAD.Vector(default) if default is not None else None


class _PlanRegion(ArchComponent.Component):
    """A lightweight polygon used to encode semantic regions in plan."""

    def __init__(self, obj):
        ArchComponent.Component.__init__(self, obj)
        self.Type = "PlanRegion"
        self.setProperties(obj)
        self._set_ifc_type(obj)

    def setProperties(self, obj):
        ArchComponent.Component.setProperties(self, obj)

        pl = obj.PropertiesList
        if "Points" not in pl:
            obj.addProperty(
                "App::PropertyVectorList",
                "Points",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The local polygon points that define this plan region.",
                ),
            )
            obj.Points = [
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(2400, 0, 0),
                FreeCAD.Vector(2400, 1800, 0),
                FreeCAD.Vector(0, 1800, 0),
            ]
        if "Scheme" not in pl:
            obj.addProperty(
                "App::PropertyString",
                "Scheme",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The semantic scheme that owns this plan region.",
                ),
            )
            obj.Scheme = "Program"
        if "RegionType" not in pl:
            obj.addProperty(
                "App::PropertyString",
                "RegionType",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The classification of this plan region inside its scheme.",
                ),
            )
            obj.RegionType = "Zone"
        if "ParentSpace" not in pl:
            obj.addProperty(
                "App::PropertyLink",
                "ParentSpace",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Optional Arch Space that conceptually owns this plan region.",
                ),
            )
        if "AllowNesting" not in pl:
            obj.addProperty(
                "App::PropertyBool",
                "AllowNesting",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Whether other plan regions may intentionally overlap this region.",
                ),
            )
            obj.AllowNesting = False
        if "KitchenPlanningMode" not in pl:
            obj.addProperty(
                "App::PropertyEnumeration",
                "KitchenPlanningMode",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "How Cabinetry should interpret this kitchen region when planning runs.",
                ),
            ).KitchenPlanningMode = list(_KITCHEN_PLANNING_MODES)
            obj.KitchenPlanningMode = "Auto"
        if "KitchenPrimaryEdgeIndex" not in pl:
            obj.addProperty(
                "App::PropertyInteger",
                "KitchenPrimaryEdgeIndex",
                "Region",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The polygon edge index Cabinetry should treat as the primary kitchen host edge. Use -1 for auto.",
                ),
            )
            obj.KitchenPrimaryEdgeIndex = _KITCHEN_PRIMARY_EDGE_INDEX_AUTO

    def _set_ifc_type(self, obj):
        try:
            from ArchIFC import IfcTypes
        except Exception:
            IfcTypes = []

        if "Virtual Element" in IfcTypes:
            obj.IfcType = "Virtual Element"
        elif "Building Element Proxy" in IfcTypes:
            obj.IfcType = "Building Element Proxy"

    def dumps(self):
        return self.Type

    def loads(self, _state):
        self.Type = "PlanRegion"

    def onDocumentRestored(self, obj):
        self.Type = "PlanRegion"
        self.setProperties(obj)
        self._set_ifc_type(obj)

    def onChanged(self, obj, prop):
        ArchComponent.Component.onChanged(self, obj, prop)
        if prop in ("Points", "Placement", "KitchenPlanningMode", "KitchenPrimaryEdgeIndex"):
            try:
                obj.touch()
            except Exception:
                pass

    def _get_local_points(self, obj):
        points = []
        for value in getattr(obj, "Points", []) or []:
            point = _copy_vector(value)
            if point is None:
                continue
            point.z = 0.0
            if points and point.distanceToPoint(points[-1]) <= 0.000001:
                continue
            points.append(point)
        if len(points) >= 2 and points[0].distanceToPoint(points[-1]) <= 0.000001:
            points.pop()
        return points

    def _build_local_face(self, obj):
        import Part

        points = self._get_local_points(obj)
        if len(points) < 3:
            return None
        try:
            face = Part.Face(Part.makePolygon(points + [points[0]]))
        except Exception:
            return None
        if face is None or face.isNull() or getattr(face, "Area", 0.0) <= 0.000001:
            return None
        return face

    def execute(self, obj):
        import Part

        face = self._build_local_face(obj)
        if not face:
            obj.Shape = Part.Shape()
            self.computeAreas(obj)
            return

        clean_face = ArchComponent._copy_without_element_map(face)
        obj.Shape = clean_face if clean_face is not None else face
        self.computeAreas(obj)

    def getFootprint(self, obj):
        shape = getattr(obj, "Shape", None)
        faces = list(getattr(shape, "Faces", []) or []) if shape else []
        if faces:
            return faces

        face = self._build_local_face(obj)
        if face is None:
            return []

        try:
            placed_face = face.copy()
            placed_face.Placement = obj.Placement.multiply(placed_face.Placement)
            return [placed_face]
        except Exception:
            return []


class _ViewProviderPlanRegion(ArchComponent.ViewProviderComponent):
    def __init__(self, vobj):
        ArchComponent.ViewProviderComponent.__init__(self, vobj)
        vobj.LineColor = ArchCommands.getDefaultColor("Space")
        vobj.ShapeColor = tuple(min(1.0, component + 0.08) for component in vobj.LineColor[:3])
        vobj.Transparency = 85
        vobj.LineWidth = max(1.0, float(params.get_param_view("DefaultShapeLineWidth")))
        vobj.DrawStyle = "Dashed"

    def onDocumentRestored(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        import Arch_rc

        return ":/icons/Arch_Component_Tree.svg"

    def createFootprintGroup(self):
        from pivy import coin

        self.lcoords = coin.SoCoordinate3()
        self.lset = coin.SoLineSet()
        self.lstyle = coin.SoDrawStyle()
        self.lstyle.style = coin.SoDrawStyle.LINES
        self.lmat = coin.SoBaseColor()

        sep = coin.SoSeparator()
        sep.addChild(self.lmat)
        sep.addChild(self.lstyle)
        sep.addChild(self.lcoords)
        sep.addChild(self.lset)
        return sep

    def _get_local_footprint_points(self):
        obj = getattr(self, "Object", None)
        if not obj or not hasattr(obj, "Proxy"):
            return []
        points = obj.Proxy._get_local_points(obj)
        if len(points) < 3:
            return []
        return points + [points[0]]

    def updateFootprint(self):
        if not hasattr(self, "lcoords") or not hasattr(self, "lset"):
            return

        points = self._get_local_footprint_points()
        verts = [[point.x, point.y, point.z] for point in points]
        counts = [len(points)] if len(points) >= 2 else []
        self._update_footprint_line_nodes(
            self.lcoords,
            self.lset,
            verts,
            counts,
            context="ArchPlanRegion.updateFootprint",
        )

    def onChanged(self, vobj, prop):
        ArchComponent.ViewProviderComponent.onChanged(self, vobj, prop)

        if prop == "LineColor" and hasattr(self, "lmat"):
            color = getattr(vobj, "LineColor", (0.0, 0.0, 0.0))
            self.lmat.rgb = (color[0], color[1], color[2])
        elif prop == "LineWidth" and hasattr(self, "lstyle"):
            self.lstyle.lineWidth = max(1.0, float(getattr(vobj, "LineWidth", 1.0)) * 0.5)
        elif prop == "DrawStyle" and hasattr(self, "lstyle"):
            draw_style = getattr(vobj, "DrawStyle", "Solid")
            if draw_style == "Solid":
                self.lstyle.linePattern = 0xFFFF
            elif draw_style == "Dashed":
                self.lstyle.linePattern = 0xF00F
            elif draw_style == "Dotted":
                self.lstyle.linePattern = 0x0F0F
            else:
                self.lstyle.linePattern = 0xFF88

    def attach(self, vobj):
        ArchComponent.ViewProviderComponent.attach(self, vobj)
        self.onChanged(vobj, "LineColor")
        self.onChanged(vobj, "LineWidth")
        self.onChanged(vobj, "DrawStyle")
