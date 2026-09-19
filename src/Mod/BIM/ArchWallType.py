# SPDX-License-Identifier: LGPL-2.1-or-later

"""Reusable type definitions for Arch walls."""

import FreeCAD


WALL_FUNCTIONS = (
    "Unclassified",
    "Exterior",
    "Interior",
    "Retaining",
    "Foundation",
    "Party",
)
WALL_ALIGNMENTS = ("Left", "Right", "Center")
HATCH_PATTERNS = ("None", "Diagonal", "Cross")


class _WallType:
    """Non-geometric defaults shared by wall occurrences."""

    Type = "WallType"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        properties = obj.PropertiesList
        if "Function" not in properties:
            obj.addProperty("App::PropertyEnumeration", "Function", "Wall Type")
            obj.Function = list(WALL_FUNCTIONS)
        if "Width" not in properties:
            obj.addProperty("App::PropertyLength", "Width", "Wall Type")
            obj.Width = 200.0
        if "DefaultHeight" not in properties:
            obj.addProperty("App::PropertyLength", "DefaultHeight", "Wall Type")
            obj.DefaultHeight = 3000.0
        if "Align" not in properties:
            obj.addProperty("App::PropertyEnumeration", "Align", "Wall Type")
            obj.Align = list(WALL_ALIGNMENTS)
            obj.Align = "Center"
        if "Material" not in properties:
            obj.addProperty("App::PropertyLinkGlobal", "Material", "Wall Type")
        if "PlanHatch" not in properties:
            obj.addProperty("App::PropertyEnumeration", "PlanHatch", "Plan Appearance")
            obj.PlanHatch = list(HATCH_PATTERNS)
        if "PlanHatchSpacing" not in properties:
            obj.addProperty("App::PropertyLength", "PlanHatchSpacing", "Plan Appearance")
            obj.PlanHatchSpacing = 100.0
        if "PlanHatchAngle" not in properties:
            obj.addProperty("App::PropertyAngle", "PlanHatchAngle", "Plan Appearance")
            obj.PlanHatchAngle = 45.0

    def execute(self, obj):
        del obj

    def onChanged(self, obj, prop):
        if prop not in {
            "Function",
            "Width",
            "DefaultHeight",
            "Align",
            "Material",
            "PlanHatch",
            "PlanHatchSpacing",
            "PlanHatchAngle",
        }:
            return
        for occurrence in tuple(getattr(obj, "InList", ()) or ()):
            if getattr(occurrence, "WallType", None) is obj:
                occurrence.touch()

    def dumps(self):
        return self.Type

    def loads(self, state):
        if state:
            self.Type = state


class _ViewProviderWallType:
    def __init__(self, view_object):
        view_object.Proxy = self

    def getIcon(self):
        return ":/icons/Arch_Wall.svg"

    def dumps(self):
        return None

    def loads(self, state):
        del state


def makeWallType(name=None):
    """Create and return a reusable wall type in the active document."""

    document = FreeCAD.ActiveDocument
    if document is None:
        document = FreeCAD.newDocument()
    obj = document.addObject("App::FeaturePython", "WallType")
    obj.Label = name or "Wall Type"
    _WallType(obj)
    if FreeCAD.GuiUp:
        _ViewProviderWallType(obj.ViewObject)
    return obj
