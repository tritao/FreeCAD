# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
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

__title__ = "FreeCAD Equipment"
__author__ = "Yorik van Havre"
__url__ = "https://www.freecad.org"

## @package ArchEquipment
#  \ingroup ARCH
#  \brief The Equipment object and tools
#
#  This module provides tools to build equipment objects.
#  Equipment is used to represent furniture and all kinds of electrical
#  or hydraulic appliances in a building

import FreeCAD
import ArchComponent
import DraftVecUtils

if FreeCAD.GuiUp:
    from PySide import QtGui
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


if FreeCAD.GuiUp:

    class EquipmentTaskPanel(ArchComponent.ComponentOptionsTaskPanel):
        """A task panel for Arch Equipment using the generic options box"""

        def __init__(self, obj):
            property_definitions = [
                {"prop": "Model", "label": translate("Arch", "Model")},
                {"prop": "EquipmentPower", "label": translate("Arch", "Equipment Power")},
            ]
            super().__init__(obj, property_definitions)


class _Equipment(ArchComponent.Component):
    "The Equipment object"

    def __init__(self, obj):

        ArchComponent.Component.__init__(self, obj)
        self.Type = "Equipment"
        self.setProperties(obj)
        from ArchIFC import IfcTypes

        if "Furniture" in IfcTypes:
            # IfcFurniture is new in IFC4
            obj.IfcType = "Furniture"
        elif "Furnishing Element" in IfcTypes:
            # IFC2x3 does know a IfcFurnishingElement
            obj.IfcType = "Furnishing Element"
        else:
            obj.IfcType = "Building Element Proxy"

    def setProperties(self, obj):

        pl = obj.PropertiesList
        if not "Model" in pl:
            obj.addProperty(
                "App::PropertyString",
                "Model",
                "Equipment",
                QT_TRANSLATE_NOOP("App::Property", "The model description of this equipment"),
                locked=True,
            )
        if not "ProductURL" in pl:
            obj.addProperty(
                "App::PropertyString",
                "ProductURL",
                "Equipment",
                QT_TRANSLATE_NOOP("App::Property", "The URL of the product page of this equipment"),
                locked=True,
            )
        if not "StandardCode" in pl:
            obj.addProperty(
                "App::PropertyString",
                "StandardCode",
                "Equipment",
                QT_TRANSLATE_NOOP("App::Property", "A standard code (MasterFormat, OmniClass,…)"),
                locked=True,
            )
        if not "SnapPoints" in pl:
            obj.addProperty(
                "App::PropertyVectorList",
                "SnapPoints",
                "Equipment",
                QT_TRANSLATE_NOOP("App::Property", "Additional snap points for this equipment"),
                locked=True,
            )
        if not "EquipmentPower" in pl:
            obj.addProperty(
                "App::PropertyFloat",
                "EquipmentPower",
                "Equipment",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The electric power needed by this equipment in Watts"
                ),
                locked=True,
            )
        if not "PlanSymbols" in pl:
            obj.addProperty(
                "App::PropertyLinkList",
                "PlanSymbols",
                "Equipment",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Optional authored 2D plan symbol objects for this equipment"
                ),
                locked=True,
            )
        obj.setEditorMode("VerticalArea", 2)
        obj.setEditorMode("HorizontalArea", 2)
        obj.setEditorMode("PerimeterLength", 2)

    def onDocumentRestored(self, obj):

        ArchComponent.Component.onDocumentRestored(self, obj)
        self.setProperties(obj)

    def loads(self, state):

        self.Type = "Equipment"

    def onChanged(self, obj, prop):

        self.hideSubobjects(obj, prop)
        ArchComponent.Component.onChanged(self, obj, prop)

    def execute(self, obj):

        if self.clone(obj):
            return
        if not self.ensureBase(obj):
            return

        pl = obj.Placement
        if obj.Base:
            base = None
            if hasattr(obj.Base, "Shape"):
                base = obj.Base.Shape.copy()
                base = self.processSubShapes(obj, base, pl)
                self.applyShape(obj, base, pl, allowinvalid=False, allownosolid=True)

        # Execute features in the SketchArch External Add-on, if present
        self.executeSketchArchFeatures(obj)

    def executeSketchArchFeatures(self, obj, linkObj=None, index=None, linkElement=None):
        """
        To execute features in the SketchArch External Add-on  (https://github.com/paullee0/FreeCAD_SketchArch)
        -  import ArchSketchObject module, and
        -  execute features that are common to ArchObjects (including Links) and ArchSketch

        To install SketchArch External Add-on, see https://github.com/paullee0/FreeCAD_SketchArch#iv-install
        """

        # To execute features in SketchArch External Add-on, if present
        try:
            import ArchSketchObject

            # Execute SketchArch Feature - Intuitive Automatic Placement for Arch Windows/Doors, Equipment etc.
            # see https://forum.freecad.org/viewtopic.php?f=23&t=50802
            ArchSketchObject.updateAttachmentOffset(obj, linkObj)
        except:
            pass

    def computeAreas(self, obj):
        return

    def _iter_plan_symbol_shapes(self, obj):
        base_z = None
        if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
            base_z = obj.Shape.BoundBox.ZMin
        for plan_obj in getattr(obj, "PlanSymbols", []) or []:
            shape = getattr(plan_obj, "Shape", None)
            if not shape or shape.isNull():
                continue
            shape = shape.copy()
            placement = getattr(plan_obj, "Placement", None)
            if placement:
                try:
                    shape.Placement = placement.multiply(shape.Placement)
                except Exception:
                    pass
            if base_z is not None and abs(shape.BoundBox.ZMin - base_z) > 0.001:
                shape.translate(FreeCAD.Vector(0, 0, base_z - shape.BoundBox.ZMin))
            yield shape

    def getFootprint(self, obj):
        """Return plan footprint faces for shape-based equipment.

        Prefer a horizontal slice through the equipment at the standard plan
        cut height. Shorter equipment is sliced just below its top and then
        flattened to its base elevation so low furniture still appears in plan.
        If no slice can be built, fall back to literal bottom faces.
        """

        from draftutils import params

        symbol_faces = []
        for shape in self._iter_plan_symbol_shapes(obj):
            if shape.Faces:
                symbol_faces.extend(shape.Faces)
        if symbol_faces:
            return symbol_faces

        shape = getattr(obj, "Shape", None)
        if not shape or shape.isNull():
            return []

        if shape.Solids or shape.Faces:
            bb = shape.BoundBox
            if bb.ZLength > 0.001:
                cut_height = params.get_param_arch("FootprintCutHeight")
                if cut_height is None:
                    cut_height = 1000.0
                cut_z = max(bb.ZMin + 0.001, min(bb.ZMax - 0.001, bb.ZMin + cut_height))
                faces = ArchComponent.get_horizontal_slice_faces(
                    shape, cut_z, translate_z=bb.ZMin - cut_z
                )
                if faces:
                    return faces

        faces = []
        if shape:
            for face in shape.Faces:
                if face.normalAt(0, 0).getAngle(FreeCAD.Vector(0, 0, -1)) < 0.01:
                    if abs(face.CenterOfMass.z - shape.BoundBox.ZMin) < 0.001:
                        faces.append(face)
        return faces


class _ViewProviderEquipment(ArchComponent.ViewProviderComponent):
    "A View Provider for the Equipment object"

    def __init__(self, vobj):

        ArchComponent.ViewProviderComponent.__init__(self, vobj)

    def getIcon(self):

        import Arch_rc

        if hasattr(self, "Object"):
            if hasattr(self.Object, "CloneOf"):
                if self.Object.CloneOf:
                    return ":/icons/Arch_Equipment_Clone.svg"
        return ":/icons/Arch_Equipment_Tree.svg"

    def attach(self, vobj):

        self.Object = vobj.Object
        from pivy import coin

        sep = coin.SoSeparator()
        self.coords = coin.SoCoordinate3()
        sep.addChild(self.coords)
        self.coords.point.deleteValues(0)
        symbol = coin.SoMarkerSet()
        symbol.markerIndex = FreeCADGui.getMarkerIndex("", 5)
        sep.addChild(symbol)
        rn = vobj.RootNode
        rn.addChild(sep)
        ArchComponent.ViewProviderComponent.attach(self, vobj)

    def createFootprintGroup(self):
        """Create a mixed fill/line footprint style for equipment."""

        from pivy import coin

        base_color = getattr(self.Object.ViewObject, "ShapeColor", (0.7, 0.7, 0.7))
        fill_color = tuple((component + 2.0) / 3.0 for component in base_color[:3])
        line_color = tuple(max(component * 0.35, 0.15) for component in base_color[:3])

        self.fcoords = coin.SoCoordinate3()
        self.fset = coin.SoIndexedFaceSet()
        self.lcoords = coin.SoCoordinate3()
        self.lset = coin.SoLineSet()
        shape_hints = coin.SoShapeHints()
        shape_hints.faceType = coin.SoShapeHints.UNKNOWN_FACE_TYPE

        loffset = coin.SoPolygonOffset()
        loffset.styles = coin.SoPolygonOffsetElement.LINES
        loffset.factor = -1.0
        loffset.units = -2.0
        loffset.on = True
        lstyle = coin.SoDrawStyle()
        lstyle.lineWidth = 1.5
        lmat = coin.SoBaseColor()
        lmat.rgb = line_color

        sep = coin.SoSeparator()
        sep.addChild(
            ArchComponent.ViewProviderComponent.buildFootprintFillSeparator(
                self,
                fill_color,
                0.65,
                self.fcoords,
                self.fset,
                shape_hints=shape_hints,
            )
        )
        line_sep = coin.SoSeparator()
        line_sep.addChild(loffset)
        line_sep.addChild(lmat)
        line_sep.addChild(lstyle)
        line_sep.addChild(self.lcoords)
        line_sep.addChild(self.lset)
        sep.addChild(line_sep)
        return sep

    def _get_footprint_inverse_placement(self):
        if not hasattr(self, "Object"):
            return None
        placement = getattr(self.Object, "Placement", None)
        if placement:
            try:
                return placement.inverse()
            except Exception:
                return None
        return None

    def _collect_edge_points(self, edge):
        points = edge.tessellate(1)
        if points and all(isinstance(point, FreeCAD.Vector) for point in points):
            return points

        try:
            points = edge.discretize(Deflection=1.0)
        except Exception:
            points = []
        if points:
            return [
                point if isinstance(point, FreeCAD.Vector) else FreeCAD.Vector(point)
                for point in points
            ]

        return [vertex.Point for vertex in edge.Vertexes]

    def _points_to_local_footprint_polyline(self, points, base_z, inverse_placement):
        if len(points) < 2:
            return None
        local_points = []
        for point in points:
            point = FreeCAD.Vector(point.x, point.y, base_z)
            if inverse_placement is not None:
                point = inverse_placement.multVec(point)
            local_points.append([point.x, point.y, point.z])
        return local_points

    def _collect_local_footprint_polylines(self):
        if not hasattr(self, "Object"):
            return []

        inverse_placement = self._get_footprint_inverse_placement()
        shape = getattr(self.Object, "Shape", None)
        base_z = shape.BoundBox.ZMin if shape and not shape.isNull() else 0.0
        polylines = []
        faces = self.Object.Proxy.getFootprint(self.Object) or []

        for face in faces:
            for wire in face.Wires:
                points = [vertex.Point for vertex in wire.Vertexes]
                if len(points) < 2:
                    continue
                if points[0].distanceToPoint(points[-1]) > 0.001:
                    points.append(points[0])
                polyline = self._points_to_local_footprint_polyline(
                    points, base_z, inverse_placement
                )
                if polyline:
                    polylines.append(polyline)

        if polylines:
            return polylines

        symbol_shapes = list(self.Object.Proxy._iter_plan_symbol_shapes(self.Object))
        edge_shapes = symbol_shapes
        if not edge_shapes and shape and not shape.isNull():
            edge_shapes = [shape]

        for edge_shape in edge_shapes:
            for edge in getattr(edge_shape, "Edges", []) or []:
                polyline = self._points_to_local_footprint_polyline(
                    self._collect_edge_points(edge),
                    base_z,
                    inverse_placement,
                )
                if polyline:
                    polylines.append(polyline)
        return polylines

    def updateData(self, obj, prop):

        ArchComponent.ViewProviderComponent.updateData(self, obj, prop)
        if prop == "SnapPoints":
            if obj.SnapPoints:
                self.coords.point.setNum(len(obj.SnapPoints))
                self.coords.point.setValues([[p.x, p.y, p.z] for p in obj.SnapPoints])
            else:
                self.coords.point.deleteValues(0)

    def updateFootprint(self):
        ArchComponent.ViewProviderComponent.updateFootprint(self)

        if not hasattr(self, "lcoords") or not hasattr(self, "lset"):
            return

        self.lcoords.point.deleteValues(0)
        self.lset.numVertices.deleteValues(0)

        polylines = self._collect_local_footprint_polylines()
        if not polylines:
            return

        verts = []
        counts = []
        for polyline in polylines:
            if len(polyline) < 2:
                continue
            verts.extend(polyline)
            counts.append(len(polyline))

        if verts:
            self.lcoords.point.setValues(verts)
            self.lset.numVertices.setValues(0, len(counts), counts)

    def setEdit(self, vobj, mode):
        if mode != 0:
            return None

        taskd = EquipmentTaskPanel(vobj.Object)
        FreeCADGui.Control.showDialog(taskd, FreeCADGui.ActiveDocument)
        return True
