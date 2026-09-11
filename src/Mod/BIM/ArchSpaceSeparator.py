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

"""Virtual room-divider object used to split Arch spaces."""

import FreeCAD

import ArchComponent
import ArchCommands

from draftutils import params

if FreeCAD.GuiUp:
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt


class _SpaceSeparator(ArchComponent.Component):
    """Simple vertical face used as an explicit Arch Space boundary."""

    def __init__(self, obj):
        ArchComponent.Component.__init__(self, obj)
        self.Type = "SpaceSeparator"
        self.setProperties(obj)
        self._set_ifc_type(obj)

    def setProperties(self, obj):
        ArchComponent.Component.setProperties(self, obj)

        pl = obj.PropertiesList
        if "Start" not in pl:
            obj.addProperty(
                "App::PropertyVectorDistance",
                "Start",
                "Separator",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The local start point of this space separator.",
                ),
                locked=True,
            )
            obj.Start = FreeCAD.Vector()
        if "End" not in pl:
            obj.addProperty(
                "App::PropertyVectorDistance",
                "End",
                "Separator",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The local end point of this space separator.",
                ),
                locked=True,
            )
            obj.End = FreeCAD.Vector(1000, 0, 0)
        if "Height" not in pl:
            obj.addProperty(
                "App::PropertyLength",
                "Height",
                "Separator",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The height of this space separator.",
                ),
                locked=True,
            )
            obj.Height = params.get_param_arch("WallHeight")

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
        self.Type = "SpaceSeparator"

    def onDocumentRestored(self, obj):
        self.Type = "SpaceSeparator"
        self.setProperties(obj)
        self._set_ifc_type(obj)

    def onChanged(self, obj, prop):
        ArchComponent.Component.onChanged(self, obj, prop)
        if prop in ("Start", "End", "Height"):
            try:
                obj.touch()
            except Exception:
                pass

    def execute(self, obj):
        import Part

        start = FreeCAD.Vector(getattr(obj, "Start", FreeCAD.Vector()))
        end = FreeCAD.Vector(getattr(obj, "End", FreeCAD.Vector()))
        try:
            height = float(getattr(obj, "Height", 0.0))
        except Exception:
            height = 0.0

        if end.sub(start).Length <= 0.000001 or height <= 0.000001:
            obj.Shape = Part.Shape()
            self.computeAreas(obj)
            return

        p1 = FreeCAD.Vector(start.x, start.y, start.z)
        p2 = FreeCAD.Vector(end.x, end.y, end.z)
        p3 = FreeCAD.Vector(end.x, end.y, end.z + height)
        p4 = FreeCAD.Vector(start.x, start.y, start.z + height)

        face = None
        try:
            face = Part.Face(Part.makePolygon([p1, p2, p3, p4, p1]))
        except Exception:
            face = None

        if not face or face.isNull():
            obj.Shape = Part.Shape()
            self.computeAreas(obj)
            return

        shape = self.processSubShapes(obj, face, obj.Placement)
        self.applyShape(obj, shape, obj.Placement, allownosolid=True)


class _ViewProviderSpaceSeparator(ArchComponent.ViewProviderComponent):
    def __init__(self, vobj):
        ArchComponent.ViewProviderComponent.__init__(self, vobj)
        vobj.LineColor = ArchCommands.getDefaultColor("Wall")
        vobj.ShapeColor = tuple(min(1.0, component + 0.2) for component in vobj.LineColor[:3])
        vobj.Transparency = 80
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
        if not obj:
            return []
        start = FreeCAD.Vector(getattr(obj, "Start", FreeCAD.Vector()))
        end = FreeCAD.Vector(getattr(obj, "End", FreeCAD.Vector()))
        if end.sub(start).Length <= 0.000001:
            return []
        return [start, end]

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
            context="ArchSpaceSeparator.updateFootprint",
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
