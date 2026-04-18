# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2017 Yorik van Havre <yorik@uncreated.net>              *
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

"""The BIM workbench"""

import os

import FreeCAD
import FreeCADGui
import Arch_rc


class BIMWorkbench(Workbench):

    def __init__(self):

        def QT_TRANSLATE_NOOP(context, text):
            return text

        bdir = os.path.join(FreeCAD.getResourceDir(), "Mod", "BIM")
        tt = QT_TRANSLATE_NOOP("BIM", "The BIM workbench is used to model buildings")
        self.__class__.MenuText = QT_TRANSLATE_NOOP("BIM", "BIM")
        self.__class__.ToolTip = tt
        self.__class__.Icon = os.path.join(bdir, "Resources", "icons", "BIMWorkbench.svg")

    def Initialize(self):

        # add translations and icon paths
        FreeCADGui.addIconPath(":/icons")
        FreeCADGui.addLanguagePath(":/translations")

        # Create menus and toolbars
        self.createTools()

        # Load Arch & Draft preference pages
        self.loadPreferences()

        Log("Loading BIM module… done\n")
        FreeCADGui.updateLocale()

    def createTools(self):
        "Create tolbars and menus"

        def QT_TRANSLATE_NOOP(context, text):
            return text

        # Import Draft & BIM commands
        import DraftTools
        import bimcommands
        from nativeifc import ifc_commands

        # build menus and toolbars
        self.draftingtools = [
            "BIM_Sketch",
            "Draft_Line",
            "Draft_Wire",
            "Draft_Rectangle",
            "BIM_ArcTools",
            "Draft_Circle",
            "Draft_Ellipse",
            "Draft_Polygon",
            "BIM_SplineTools",
            "Draft_Point",
            "Draft_Fillet",
        ]

        self.annotationtools = [
            "BIM_DimensionAligned",
            "BIM_DimensionHorizontal",
            "BIM_DimensionVertical",
            "BIM_Text",
            "BIM_Leader",
            "Draft_Label",
            "Draft_Hatch",
            "BIM_AxisTools",
            "Arch_Grid",
            "Arch_SectionPlane",
            "BIM_Create2DViews",
            "BIM_TDPage",
            "BIM_TDView",
        ]

        self.bimtools = [
            "Arch_Site",
            "Arch_Building",
            "Arch_Level",
            "BIM_PlanEdit",
            "Arch_Space",
            "Separator",
            "Arch_Wall",
            "Arch_CurtainWall",
            "BIM_Column",
            "BIM_Beam",
            "BIM_Slab",
            "BIM_Door",
            "Arch_Window",
            "BIM_Covering",
            "Arch_Pipe",
            "Arch_PipeConnector",
            "Arch_Stairs",
            "Arch_Roof",
            "Arch_Panel",
            "Arch_Frame",
            "Arch_Fence",
            "Arch_Truss",
            "Arch_Equipment",
            "BIM_Library",
            "Arch_Rebar",
            "BIM_GenericTools",
        ]

        self.modify_gen = [
            "Draft_Move",
            "Draft_Rotate",
            "Draft_Scale",
            "Draft_Mirror",
            "BIM_CloneTools",
            "BIM_Copy",
            "BIM_SimpleCopy",
            "BIM_Compound",
        ]
        self.modify_2d = [
            "BIM_OffsetTools",
            "Draft_Trimex",
            "Draft_Join",
            "Draft_Split",
            "Draft_Stretch",
            "Draft_Draft2Sketch",
        ]
        self.modify_obj = [
            "Draft_Upgrade",
            "Draft_Downgrade",
            "Arch_Add",
            "Arch_Remove",
            "BIM_JoinTools",
        ]
        self.modify_3d = [
            "BIM_ArrayTools",
            "Arch_CutPlane",
            "BIM_Extrude",
            "BIM_BooleanTools",
        ]

        sep = ["Separator"]
        self.modify = (
            self.modify_gen + sep + self.modify_2d + sep + self.modify_obj + sep + self.modify_3d
        )

        self.manage = [
            "BIM_Setup",
            "BIM_ProjectManager",
            "BIM_Windows",
            "BIM_IfcManageTools",
            "BIM_Layers",
            "BIM_Material",
            "BIM_ReportTools",
            "BIM_Preflight",
            "Draft_AnnotationStyleEditor",
        ]

        self.utils = [
            "BIM_Trash",
            "BIM_WPView",
            "Draft_SelectGroup",
            "Draft_Slope",
            "Draft_WorkingPlaneProxy",
            "Draft_AddConstruction",
            "Arch_SplitMesh",
            "Arch_MeshToShape",
            "Arch_SelectNonSolidMeshes",
            "Arch_RemoveShape",
            "Arch_CloseHoles",
            "Arch_MergeWalls",
            "Arch_Check",
            "Arch_ToggleIfcBrepFlag",
            "Arch_ToggleSubs",
            "Arch_Survey",
            "BIM_Diff",
            "BIM_IfcExplorer",
            "Arch_IfcSpreadsheet",
            "BIM_ImagePlane",
            "BIM_Unclone",
            "BIM_Rewire",
            "BIM_Glue",
            "BIM_Reextrude",
            "Arch_PanelTools",
            "Arch_StructureTools",
            "BIM_Project",
        ]

        nudge = [
            "BIM_Nudge_Switch",
            "BIM_Nudge_Up",
            "BIM_Nudge_Down",
            "BIM_Nudge_Left",
            "BIM_Nudge_Right",
            "BIM_Nudge_RotateLeft",
            "BIM_Nudge_RotateRight",
            "BIM_Nudge_Extend",
            "BIM_Nudge_Shrink",
        ]

        # append BIM snaps

        from draftutils import init_tools

        self.snapbar = init_tools.get_draft_snap_commands()
        self.snapmenu = self.snapbar + [
            "BIM_SetWPFront",
            "BIM_SetWPTop",
            "BIM_SetWPSide",
            "Draft_SelectPlane",
        ]

        # --- Grouped popup command classes ---
        class BIM_ArcTools:
            def GetCommands(self):
                return ("Draft_Arc", "Draft_Arc_3Points")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_ArcTools", "Arc Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "Draft_Arc"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_SplineTools:
            def GetCommands(self):
                return ("Draft_BSpline", "Draft_BezCurve", "Draft_CubicBezCurve")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_SplineTools", "Spline Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "Draft_BSpline"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_AxisTools:
            def GetCommands(self):
                return ("Arch_Axis", "Arch_AxisSystem")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_AxisTools", "Axis Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "Arch_Axis"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_OffsetTools:
            def GetCommands(self):
                # default: 2D offset
                return ("BIM_Offset2D", "Draft_Offset")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_OffsetTools", "Offset Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "BIM_Offset2D"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_ArrayTools:
            def GetCommands(self):
                # default: Draft_ArrayTools (the main Array UI)
                return (
                    "Draft_OrthoArray",
                    "Draft_PathArray",
                    "Draft_PolarArray",
                    "Draft_PointArray",
                )

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_ArrayTools", "Array Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "Draft_Array"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_BooleanTools:
            def GetCommands(self):
                # default: union (BIM_Fuse)
                return ("BIM_Fuse", "BIM_Cut", "BIM_Common")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_BooleanTools", "Boolean Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "BIM_Fuse"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_IfcManageTools:
            def GetCommands(self):
                return (
                    "BIM_IfcElements",
                    "BIM_IfcQuantities",
                    "BIM_IfcProperties",
                    "BIM_Classification",
                )

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_IfcManageTools", "IFC Management")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "BIM_IfcElements"}

            def IsActive(self):
                return True

        class BIM_ReportTools:
            def GetCommands(self):
                return ("BIM_Report", "Arch_Schedule")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_ReportTools", "Report Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "BIM_Report"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        class BIM_CloneTools:
            def GetCommands(self):
                return ("BIM_Clone", "BIM_LinkMake")

            def GetResources(self):
                label = QT_TRANSLATE_NOOP("BIM_CloneTools", "Cloning Tools")
                tooltip = label
                return {"MenuText": label, "ToolTip": tooltip, "Icon": "BIM_Clone"}

            def IsActive(self):
                return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

        # create generic tools command
        class BIM_GenericTools:
            def GetCommands(self):
                return (
                    "Arch_Profile",
                    "BIM_Box",
                    "BIM_Builder",
                    "Draft_Facebinder",
                    "Arch_Component",
                    "Arch_Reference",
                )

            def GetResources(self):
                t = QT_TRANSLATE_NOOP("BIM_GenericTools", "Generic 3D Tools")
                return {"MenuText": t, "ToolTip": t, "Icon": "BIM_Box"}

            def IsActive(self):
                v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
                return v

        # create 2D views command
        class BIM_Create2DViews:
            def GetCommands(self):
                return ("BIM_DrawingView", "BIM_Shape2DView", "BIM_Shape2DCut")

            def GetResources(self):
                t = QT_TRANSLATE_NOOP("BIM_Create2DViews", "Create 2D Views")
                return {"MenuText": t, "ToolTip": t, "Icon": "BIM_DrawingView"}

            def IsActive(self):
                v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
                return v

        # Register grouped commands
        FreeCADGui.addCommand("BIM_ArcTools", BIM_ArcTools())
        FreeCADGui.addCommand("BIM_SplineTools", BIM_SplineTools())
        FreeCADGui.addCommand("BIM_AxisTools", BIM_AxisTools())
        FreeCADGui.addCommand("BIM_OffsetTools", BIM_OffsetTools())
        FreeCADGui.addCommand("BIM_ArrayTools", BIM_ArrayTools())
        FreeCADGui.addCommand("BIM_BooleanTools", BIM_BooleanTools())
        FreeCADGui.addCommand("BIM_IfcManageTools", BIM_IfcManageTools())
        FreeCADGui.addCommand("BIM_ReportTools", BIM_ReportTools())
        FreeCADGui.addCommand("BIM_GenericTools", BIM_GenericTools())
        FreeCADGui.addCommand("BIM_Create2DViews", BIM_Create2DViews())
        FreeCADGui.addCommand("BIM_CloneTools", BIM_CloneTools())

        class BIM_JoinTools:
            def GetCommands(self):
                # This method tells FreeCAD which commands belong to this group
                return [
                    "BIM_Join_Miter",
                    "BIM_Join_Butt",
                    "BIM_Join_Tee",
                    "BIM_EditWallJoint",
                    "BIM_Unjoin",
                ]

            def GetResources(self):
                # This method defines the appearance of the main button
                t = QT_TRANSLATE_NOOP("BIM_JoinTools", "Join tools")
                return {"MenuText": t, "ToolTip": t, "Icon": "BIM_Join_Miter"}

            def IsActive(self):
                v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
                return v

        FreeCADGui.addCommand("BIM_JoinTools", BIM_JoinTools())

        # load rebar tools (Reinforcement addon)
        try:
            import RebarTools
        except ImportError:
            RebarGroupCommand = None  # for workaround for issue #26539 and #27984
        else:
            # create popup group for Rebar tools
            class RebarGroupCommand:
                def GetCommands(self):
                    return tuple(["Arch_Rebar"] + RebarTools.RebarCommands)

                def GetResources(self):
                    return {
                        "MenuText": QT_TRANSLATE_NOOP("Arch_RebarTools", "Reinforcement Tools"),
                        "ToolTip": QT_TRANSLATE_NOOP("Arch_RebarTools", "Reinforcement tools"),
                        "Icon": "Arch_Rebar",
                    }

                def IsActive(self):
                    v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
                    return v

            FreeCADGui.addCommand("Arch_RebarTools", RebarGroupCommand())
            self.bimtools[self.bimtools.index("Arch_Rebar")] = "Arch_RebarTools"
            RebarTools.load_translations()
            Log("Load Reinforcement Module… done\n")
            if hasattr(RebarTools, "updateLocale"):
                RebarTools.updateLocale()
            # self.rebar = RebarTools.RebarCommands + ["Arch_Rebar"]

        # load webtools

        try:
            import BIMServer
            import Git
            import Sketchfab
        except ImportError:
            pass
        else:
            self.utils.extend(
                [
                    "WebTools_Git",
                    "WebTools_BimServer",
                    "WebTools_Sketchfab",
                ]
            )

        # load flamingo

        try:
            import CommandsPolar
            import CommandsFrame
            import CommandsPipe
        except ImportError:
            flamingo = None
        else:
            flamingo = [
                "frameIt",
                "fillFrame",
                "insertPath",
                "insertSection",
                "FrameLineManager",
                "spinSect",
                "reverseBeam",
                "shiftBeam",
                "pivotBeam",
                "levelBeam",
                "alignEdge",
                "rotJoin",
                "alignFlange",
                "stretchBeam",
                "extend",
                "adjustFrameAngle",
                "insertPipe",
                "insertElbow",
                "insertReduct",
                "insertCap",
                "insertFlange",
                "insertUbolt",
                "insertPypeLine",
                "breakPipe",
                "mateEdges",
                "extend2intersection",
                "extend1intersection",
                "laydown",
                "raiseup",
            ]

        # load fasteners

        try:
            import FastenerBase
            import FastenersCmd
        except ImportError:
            fasteners = None
        else:
            fasteners = [
                c for c in FastenerBase.FSGetCommands("screws") if not isinstance(c, tuple)
            ]

        # load nativeifc tools

        ifctools = ifc_commands.get_commands()

        # create toolbars

        t1 = QT_TRANSLATE_NOOP("Workbench", "Drafting Tools")
        t2 = QT_TRANSLATE_NOOP("Workbench", "Draft Snap")
        t3 = QT_TRANSLATE_NOOP("Workbench", "3D/BIM Tools")
        t4 = QT_TRANSLATE_NOOP("Workbench", "Annotation Tools")
        t5 = QT_TRANSLATE_NOOP("Workbench", "2D Tools")
        t6 = QT_TRANSLATE_NOOP("Workbench", "Manage Tools")
        t7 = QT_TRANSLATE_NOOP("Workbench", "General Tools")
        t8 = QT_TRANSLATE_NOOP("Workbench", "Object Tools")
        t9 = QT_TRANSLATE_NOOP("Workbench", "3D Tools")
        self.appendToolbar(t1, self.draftingtools)
        self.appendToolbar(t2, self.snapbar)
        self.appendToolbar(t3, self.bimtools)
        self.appendToolbar(t4, self.annotationtools)
        self.appendToolbar(t7, self.modify_gen)
        self.appendToolbar(t5, self.modify_2d)
        self.appendToolbar(t8, self.modify_obj)
        self.appendToolbar(t9, self.modify_3d)
        self.appendToolbar(t6, self.manage)

        # create menus

        t1 = QT_TRANSLATE_NOOP("Workbench", "&2D Drafting")
        t2 = QT_TRANSLATE_NOOP("Workbench", "&3D/BIM")
        t3 = QT_TRANSLATE_NOOP("Workbench", "&Reinforcement Tools")
        t4 = QT_TRANSLATE_NOOP("Workbench", "&Annotation")
        t5 = QT_TRANSLATE_NOOP("Workbench", "&Snapping")
        t6 = QT_TRANSLATE_NOOP("Workbench", "M&odify")
        t7 = QT_TRANSLATE_NOOP("Workbench", "Ma&nage")
        # t8 =  QT_TRANSLATE_NOOP("Workbench", "&IFC")
        t9 = QT_TRANSLATE_NOOP("Workbench", "&Flamingo")
        t10 = QT_TRANSLATE_NOOP("Workbench", "Fas&teners")
        t11 = QT_TRANSLATE_NOOP("Workbench", "&Utils")
        t12 = QT_TRANSLATE_NOOP("Workbench", "Nudge")

        # self.bimtools_menu = list(self.bimtools)
        # if "Arch_RebarTools" in self.bimtools_menu:
        #    self.bimtools_menu.remove("Arch_RebarTools")
        self.appendMenu(t1, self.draftingtools)
        self.appendMenu(t2, self.bimtools)
        # if self.rebar:
        #    self.appendMenu([t2, t3], self.rebar)
        self.appendMenu(t4, self.annotationtools)
        self.appendMenu(t5, self.snapmenu)
        self.appendMenu(t6, self.modify)
        self.appendMenu(t7, self.manage)
        # if ifctools:
        #    self.appendMenu(t8, ifctools)
        if flamingo:
            self.appendMenu(t9, flamingo)
        if fasteners:
            self.appendMenu(t10, fasteners)
        self.appendMenu(t11, self.utils + ifctools)
        self.appendMenu([t11, t12], nudge)

        try:
            from Materia.Commands.WorkbenchLayout import append_workbench_layout
        except ImportError:
            pass
        except Exception as err:
            FreeCAD.Console.PrintWarning(
                f"Unable to load Materia layout into BIM workbench: {err}\n"
            )
        else:
            append_workbench_layout(self, FreeCADGui, prefix="Materia")

        self.taskwatcher_setup = [
            "BIM_Setup",
            "BIM_ProjectManager",
            "Arch_Site",
            "Arch_Building",
            "Arch_Level",
            "BIM_Views",
        ]
        self.taskwatcher_plan = [
            "BIM_PlanEdit",
            "BIM_Sketch",
            "Draft_Line",
            "Draft_Wire",
            "Draft_Rectangle",
            "Draft_Circle",
            "BIM_Text",
        ]
        self.taskwatcher_elements = [
            "Arch_Wall",
            "BIM_Slab",
            "BIM_Column",
            "BIM_Beam",
            "BIM_Door",
            "Arch_Window",
            "Arch_Stairs",
            "BIM_Library",
        ]
        self.taskwatcher_container = [
            "Arch_Level",
            "BIM_PlanEdit",
            "BIM_Views",
            "Arch_SectionPlane",
            "BIM_DrawingView",
            "BIM_Shape2DView",
        ]
        self.taskwatcher_2d_modify = [
            "BIM_Offset2D",
            "Draft_Trimex",
            "Draft_Join",
            "Draft_Split",
            "Draft_Stretch",
            "Draft_Draft2Sketch",
        ]
        self.taskwatcher_wall_modify = [
            "Arch_Add",
            "Arch_Remove",
            "BIM_Join_Miter",
            "BIM_Join_Butt",
            "BIM_Join_Tee",
            "BIM_EditWallJoint",
            "BIM_Unjoin",
        ]
        self.taskwatcher_transform = [
            "Draft_Move",
            "Draft_Rotate",
            "Draft_Mirror",
            "BIM_Clone",
            "BIM_LinkMake",
            "Draft_OrthoArray",
            "BIM_Extrude",
        ]
        self.taskwatcher_boolean = [
            "BIM_Compound",
            "BIM_Fuse",
            "BIM_Cut",
            "BIM_Common",
        ]
        self.taskwatcher_ifc = [
            "BIM_IfcElements",
            "BIM_IfcQuantities",
            "BIM_IfcProperties",
            "BIM_Classification",
            "BIM_Preflight",
        ]

    def _has_scene_view(self):
        try:
            return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        except Exception:
            return False

    def _selection(self):
        try:
            return list(FreeCADGui.Selection.getSelection())
        except Exception:
            return []

    def _normalize_type_token(self, value):
        if not value:
            return ""
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    def _object_type_tokens(self, obj):
        if obj is None:
            return set()

        tokens = set()

        def add(value):
            token = self._normalize_type_token(value)
            if token and token != "undefined":
                tokens.add(token)

        try:
            import Draft

            add(Draft.getType(obj))
        except Exception:
            pass

        add(getattr(obj, "IfcType", None))
        add(getattr(getattr(obj, "Proxy", None), "Type", None))

        type_id = getattr(obj, "TypeId", "")
        if type_id:
            add(type_id)
            for part in str(type_id).split("::"):
                add(part)

        return tokens

    def _object_label(self, obj):
        return getattr(obj, "Label", getattr(obj, "Name", "Unnamed object"))

    def _active_bim_context(self):
        view = getattr(FreeCADGui.ActiveDocument, "ActiveView", None)
        if view is None:
            return None

        for name in ("NativeIFC", "Arch"):
            try:
                active = view.getActiveObject(name)
            except Exception:
                active = None
            if active is not None:
                return active
        return None

    def _is_project_container(self, obj):
        tokens = self._object_type_tokens(obj)
        return bool(
            tokens
            & {
                "project",
                "site",
                "building",
                "buildingpart",
                "buildingstorey",
                "floor",
                "workingplaneproxy",
                "ifcproject",
                "ifcsite",
                "ifcbuilding",
                "ifcbuildingstorey",
            }
        )

    def _is_wall_like(self, obj):
        tokens = self._object_type_tokens(obj)
        return bool(tokens & {"wall", "curtainwall", "ifcwall", "ifccurtainwall"})

    def _is_2d_like(self, obj):
        tokens = self._object_type_tokens(obj)
        if self._is_project_container(obj):
            return False
        return bool(
            tokens
            & {
                "sketch",
                "sketchobject",
                "line",
                "wire",
                "rectangle",
                "circle",
                "ellipse",
                "polygon",
                "bspline",
                "bezcurve",
                "cubicbezcurve",
                "point",
                "dimension",
                "lineardimension",
                "text",
                "annotation",
                "label",
                "axis",
                "axissystem",
                "grid",
                "sectionplane",
                "shape2dview",
                "drawingview",
                "facebinder",
                "hatch",
            }
        )

    def _is_model_object(self, obj):
        if obj is None or self._is_project_container(obj) or self._is_2d_like(obj):
            return False

        tokens = self._object_type_tokens(obj)
        if hasattr(obj, "Shape"):
            return True

        return bool(
            tokens
            & {
                "wall",
                "curtainwall",
                "slab",
                "beam",
                "column",
                "door",
                "window",
                "stairs",
                "roof",
                "panel",
                "frame",
                "fence",
                "truss",
                "equipment",
                "space",
                "component",
                "reference",
                "pipe",
                "pipeconnector",
                "rebar",
                "partfeature",
                "feature",
            }
        )

    def _has_project_structure(self):
        doc = FreeCAD.ActiveDocument
        if doc is None:
            return False

        for obj in getattr(doc, "Objects", []):
            tokens = self._object_type_tokens(obj)
            if tokens & {
                "project",
                "site",
                "building",
                "buildingpart",
                "buildingstorey",
                "floor",
                "ifcproject",
                "ifcsite",
                "ifcbuilding",
                "ifcbuildingstorey",
            }:
                return True
        return False

    def _selection_is_containers(self, selection):
        return bool(selection) and all(self._is_project_container(obj) for obj in selection)

    def _selection_is_2d(self, selection):
        return bool(selection) and all(self._is_2d_like(obj) for obj in selection)

    def _selection_has_wall_like(self, selection):
        return any(self._is_wall_like(obj) for obj in selection)

    def _selection_has_model_objects(self, selection):
        return any(self._is_model_object(obj) for obj in selection)

    def _selection_has_ifc_data(self, selection):
        for obj in selection:
            if hasattr(obj, "IfcType") or hasattr(obj, "IfcClass"):
                return True
        return False

    def _selection_label(self, selection, singular, plural=None):
        if not selection:
            return "Nothing selected"
        if len(selection) == 1:
            return "{} selected".format(self._object_label(selection[0]))
        return "{} {} selected".format(len(selection), plural or singular + "s")

    def _taskwatcher_context(self):
        selection = self._selection()
        active_context = self._active_bim_context()

        if not selection:
            if not self._has_project_structure():
                return (
                    "No project structure yet",
                    "Start with site, building, and level setup before placing elements.",
                )
            if active_context and self._is_project_container(active_context):
                return (
                    "Active container: {}".format(self._object_label(active_context)),
                    "Plan, section, and view tools stay focused on the active BIM container.",
                )
            return (
                "Ready to create",
                "Use plan tools for 2D layout or building tools for BIM elements.",
            )

        if self._selection_is_containers(selection):
            return (
                self._selection_label(selection, "container"),
                "Container selection prioritizes levels, sections, and drawing views.",
            )
        if self._selection_has_wall_like(selection):
            return (
                self._selection_label(selection, "host object"),
                "Host editing exposes add/remove and wall joint commands first.",
            )
        if self._selection_is_2d(selection):
            return (
                self._selection_label(selection, "2D object"),
                "Stay in plan editing tools until the geometry becomes a BIM element.",
            )
        if self._selection_has_model_objects(selection):
            return (
                self._selection_label(selection, "model object"),
                "Transform, clone, and boolean tools are prioritized for object editing.",
            )

        return (
            self._selection_label(selection, "object"),
            "Contextual BIM actions adapt to the current selection.",
        )

    def setTaskWatchers(self):
        from PySide import QtGui

        from bimcommands import BimPlanSession

        translate = FreeCAD.Qt.translate
        workbench = self
        FreeCADGui.Control.clearTaskWatcher()

        def scene_ready():
            return (FreeCAD.ActiveDocument is not None) and workbench._has_scene_view()

        def plan_edit_active():
            return BimPlanSession.get_active_session() is not None

        context_card = QtGui.QFrame()
        context_card.setObjectName("BimTaskWatcherContext")
        context_card.setFrameShape(QtGui.QFrame.StyledPanel)
        context_layout = QtGui.QVBoxLayout(context_card)
        context_layout.setContentsMargins(12, 12, 12, 12)
        context_layout.setSpacing(4)

        context_title = QtGui.QLabel(translate("BIM", "BIM Context"))
        context_title.setObjectName("BimTaskWatcherContextTitle")
        title_font = context_title.font()
        title_font.setBold(True)
        context_title.setFont(title_font)

        context_state = QtGui.QLabel()
        context_state.setObjectName("BimTaskWatcherContextState")
        context_state.setWordWrap(True)

        context_hint = QtGui.QLabel()
        context_hint.setObjectName("BimTaskWatcherContextHint")
        context_hint.setWordWrap(True)

        context_layout.addWidget(context_title)
        context_layout.addWidget(context_state)
        context_layout.addWidget(context_hint)

        class BimWatcher:
            def __init__(self, commands, title, condition):
                self.commands = commands
                self.title = title
                self._condition = condition

            def shouldShow(self):
                return scene_ready() and not plan_edit_active() and self._condition()

        class BimContextWatcher:
            def __init__(self):
                self.widgets = [context_card]

            def shouldShow(self):
                if not scene_ready() or plan_edit_active():
                    return False

                state, hint = workbench._taskwatcher_context()
                context_state.setText(state)
                context_hint.setText(hint)
                return True

        class BimPlanEditSessionWatcher:
            def __init__(self):
                self._session = None
                self._widget = None
                self.container = QtGui.QFrame()
                self.container.setObjectName("BIMPlanEditContextPanel")
                self.container.setFrameShape(QtGui.QFrame.NoFrame)
                self.layout = QtGui.QVBoxLayout(self.container)
                self.layout.setContentsMargins(0, 0, 0, 0)
                self.layout.setSpacing(0)
                self.widgets = [self.container]

            def __del__(self):
                self._detach_controls()

            def _detach_controls(self):
                widget = self._widget
                self._session = None
                self._widget = None
                if widget is None:
                    return
                try:
                    self.layout.removeWidget(widget)
                except Exception:
                    pass
                try:
                    widget.hide()
                except Exception:
                    pass
                try:
                    widget.setParent(None)
                except Exception:
                    pass

            def _ensure_controls(self, session):
                controls = getattr(session, "task_panel", None)
                widget = getattr(controls, "form", None) if controls else None
                if widget is None:
                    return False
                if self._session is session and self._widget is widget:
                    return True

                self._detach_controls()
                self.layout.addWidget(widget)
                self._session = session
                self._widget = widget
                return True

            def shouldShow(self):
                if not scene_ready():
                    self._detach_controls()
                    return False

                session = BimPlanSession.get_active_session()
                if session is None:
                    self._detach_controls()
                    return False
                if not self._ensure_controls(session):
                    return False
                try:
                    session.task_panel.refresh_from_session()
                except Exception:
                    self._detach_controls()
                    return False
                return True

        watchers = [
            BimContextWatcher(),
            BimPlanEditSessionWatcher(),
            BimWatcher(
                self.taskwatcher_setup,
                translate("BIM", "Project Setup"),
                lambda: (not workbench._selection()) and (not workbench._has_project_structure()),
            ),
            BimWatcher(
                self.taskwatcher_plan,
                translate("BIM", "Draft / Plan"),
                lambda: not workbench._selection(),
            ),
            BimWatcher(
                self.taskwatcher_elements,
                translate("BIM", "Building Elements"),
                lambda: not workbench._selection(),
            ),
            BimWatcher(
                self.taskwatcher_container,
                translate("BIM", "Container / Views"),
                lambda: (
                    workbench._selection_is_containers(workbench._selection())
                    or (
                        not workbench._selection()
                        and workbench._active_bim_context() is not None
                        and workbench._is_project_container(workbench._active_bim_context())
                    )
                ),
            ),
            BimWatcher(
                self.taskwatcher_2d_modify,
                translate("BIM", "2D Editing"),
                lambda: workbench._selection_is_2d(workbench._selection()),
            ),
            BimWatcher(
                self.taskwatcher_wall_modify,
                translate("BIM", "Wall / Host Editing"),
                lambda: workbench._selection_has_wall_like(workbench._selection()),
            ),
            BimWatcher(
                self.taskwatcher_transform,
                translate("BIM", "Transform / Copy"),
                lambda: workbench._selection_has_model_objects(workbench._selection()),
            ),
            BimWatcher(
                self.taskwatcher_boolean,
                translate("BIM", "Booleans / Composition"),
                lambda: len(
                    [obj for obj in workbench._selection() if workbench._is_model_object(obj)]
                )
                >= 2,
            ),
            BimWatcher(
                self.taskwatcher_ifc,
                translate("BIM", "IFC Data"),
                lambda: workbench._selection_has_ifc_data(workbench._selection()),
            ),
        ]

        FreeCADGui.Control.addTaskWatcher(watchers)

    def loadPreferences(self):
        """Set up preferences pages"""

        def QT_TRANSLATE_NOOP(context, text):
            return text

        t1 = QT_TRANSLATE_NOOP("QObject", "BIM")
        t2 = QT_TRANSLATE_NOOP("QObject", "Draft")
        FreeCADGui.addPreferencePage(":/ui/preferences-arch.ui", t1)
        FreeCADGui.addPreferencePage(":/ui/preferences-archdefaults.ui", t1)
        FreeCADGui.addPreferencePage(":/ui/preferencesNativeIFC.ui", t1)
        if hasattr(FreeCADGui, "draftToolBar"):
            if hasattr(FreeCADGui.draftToolBar, "loadedPreferences"):
                return
        from draftutils import params

        params._param_observer_start()
        FreeCADGui.addPreferencePage(":/ui/preferences-draft.ui", t2)
        FreeCADGui.addPreferencePage(":/ui/preferences-draftinterface.ui", t2)
        FreeCADGui.addPreferencePage(":/ui/preferences-draftsnap.ui", t2)
        FreeCADGui.addPreferencePage(":/ui/preferences-draftvisual.ui", t2)
        FreeCADGui.addPreferencePage(":/ui/preferences-drafttexts.ui", t2)
        FreeCADGui.draftToolBar.loadedPreferences = True

    def setupMultipleObjectSelection(self):

        import BimSelect

        if hasattr(FreeCADGui, "addDocumentObserver") and not hasattr(self, "BimSelectObserver"):
            self.BimSelectObserver = BimSelect.Setup()
            FreeCADGui.addDocumentObserver(self.BimSelectObserver)

    def Activated(self):

        import WorkingPlane
        from draftutils import todo
        import BimStatus
        from nativeifc import ifc_observer
        from draftutils import grid_observer

        PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")

        if hasattr(FreeCADGui, "draftToolBar"):
            FreeCADGui.draftToolBar.Activated()
        if hasattr(FreeCADGui, "Snapper"):
            FreeCADGui.Snapper.show()
        if hasattr(WorkingPlane, "_view_observer_start"):
            WorkingPlane._view_observer_start()
        else:
            FreeCAD.Console.PrintWarning(
                "Improper loading of WorkingPlane code. "
                "The BIM Workbench will not work correctly.\n"
            )
        if hasattr(grid_observer, "_view_observer_setup"):
            grid_observer._view_observer_setup()
        else:
            FreeCAD.Console.PrintWarning(
                "Improper loading of grid_observer code. "
                "The BIM Workbench will not work correctly.\n"
            )

        if PARAMS.GetBool("FirstTime", True) and (not hasattr(FreeCAD, "TestEnvironment")):
            todo.ToDo.delay(FreeCADGui.runCommand, "BIM_Welcome")
        todo.ToDo.delay(BimStatus.setStatusIcons, True)
        FreeCADGui.Control.clearTaskWatcher()
        self.setTaskWatchers()

        # restore views widget if needed
        if PARAMS.GetBool("RestoreBimViews", True):
            from bimcommands import BimViews

            w = BimViews.findWidget()
            if not w:
                FreeCADGui.runCommand("BIM_Views")
            else:
                w.show()
                w.toggleViewAction().setVisible(True)

        self.setupMultipleObjectSelection()

        # add NativeIFC document observer
        ifc_observer.add_observer()

        # adding a Help menu manipulator
        # https://github.com/FreeCAD/FreeCAD/pull/10933
        class BIM_WBManipulator:
            def modifyMenuBar(self):
                return [
                    {"insert": "BIM_Examples", "menuItem": "Std_ReportBug", "after": ""},
                    {"insert": "BIM_Tutorial", "menuItem": "Std_ReportBug", "after": ""},
                    {"insert": "BIM_Help", "menuItem": "Std_ReportBug", "after": ""},
                    {"insert": "BIM_Welcome", "menuItem": "Std_ReportBug", "after": ""},
                ]

        reload = hasattr(Gui, "BIM_WBManipulator")  # BIM WB has previously been loaded.
        if not getattr(Gui, "BIM_WBManipulator", None):
            Gui.BIM_WBManipulator = BIM_WBManipulator()
        Gui.addWorkbenchManipulator(Gui.BIM_WBManipulator)
        if reload:
            Gui.activeWorkbench().reloadActive()

        Log("BIM workbench activated\n")

    def Deactivated(self):

        from draftutils import todo
        import BimStatus
        from bimcommands import BimViews
        import WorkingPlane
        from nativeifc import ifc_observer
        from draftutils import grid_observer

        PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")

        if hasattr(self, "BimSelectObserver"):
            FreeCADGui.removeDocumentObserver(self.BimSelectObserver)
            del self.BimSelectObserver

        if hasattr(FreeCADGui, "draftToolBar"):
            FreeCADGui.draftToolBar.Deactivated()
        if hasattr(FreeCADGui, "Snapper"):
            FreeCADGui.Snapper.hide()
        if hasattr(WorkingPlane, "_view_observer_stop"):
            WorkingPlane._view_observer_stop()
        if hasattr(grid_observer, "_view_observer_setup"):
            grid_observer._view_observer_setup()

        # print("Deactivating status icon")
        todo.ToDo.delay(BimStatus.setStatusIcons, False)
        FreeCADGui.Control.clearTaskWatcher()

        # store views widget state and vertical size
        w = BimViews.findWidget()
        if w:
            PARAMS.SetBool("RestoreBimViews", w.isVisible())
            PARAMS.SetInt("BimViewsSize", w.height())
            w.hide()
            w.toggleViewAction().setVisible(False)

        # add NativeIFC document observer
        ifc_observer.remove_observer()

        # Ifc stuff
        try:
            from nativeifc import ifc_status

            ifc_status.toggle_lock(False)
        except:
            pass

        # remove manipulator
        if hasattr(Gui, "BIM_WBManipulator"):
            Gui.removeWorkbenchManipulator(Gui.BIM_WBManipulator)
            Gui.BIM_WBManipulator = None
            Gui.activeWorkbench().reloadActive()

        Log("BIM workbench deactivated\n")

    def ContextMenu(self, recipient):

        import DraftTools

        translate = FreeCAD.Qt.translate

        if recipient == "Tree":
            groups = False
            ungroupable = False
            for o in FreeCADGui.Selection.getSelection():
                if o.isDerivedFrom("App::DocumentObjectGroup") or o.hasExtension(
                    "App::GroupExtension"
                ):
                    groups = True
                else:
                    groups = False
                    break
            for o in FreeCADGui.Selection.getSelection():
                for parent in o.InList:
                    if parent.isDerivedFrom("App::DocumentObjectGroup") or parent.hasExtension(
                        "App::GroupExtension"
                    ):
                        if o in parent.Group:
                            ungroupable = True
                        else:
                            ungroupable = False
                            break
            if groups:
                self.appendContextMenu("", ["Draft_SelectGroup"])
            if ungroupable:
                self.appendContextMenu("", ["BIM_Ungroup"])
            if (len(FreeCADGui.Selection.getSelection()) == 1) and (
                FreeCADGui.Selection.getSelection()[0].Name == "Trash"
            ):
                self.appendContextMenu("", ["BIM_EmptyTrash"])
        elif recipient == "View":
            self.appendContextMenu(translate("BIM", "Snapping"), self.snapmenu)
        if FreeCADGui.Selection.getSelection():
            if FreeCADGui.Selection.getSelection()[0].Name != "Trash":
                self.appendContextMenu("", ["BIM_Trash"])
            self.appendContextMenu("", ["Draft_AddConstruction", "Draft_AddToGroup"])
            allclones = False
            for obj in FreeCADGui.Selection.getSelection():
                if hasattr(obj, "CloneOf") and obj.CloneOf:
                    allclones = True
                else:
                    allclones = False
                    break
            if allclones:
                self.appendContextMenu("", ["BIM_ResetCloneColors"])
            if len(FreeCADGui.Selection.getSelection()) == 1:
                obj = FreeCADGui.Selection.getSelection()[0]
                if hasattr(obj, "Group"):
                    if obj.getTypeIdOfProperty("Group") == "App::PropertyLinkList":
                        self.appendContextMenu("", ["BIM_Reorder"])
                if obj.isDerivedFrom("TechDraw::DrawView"):
                    self.appendContextMenu("", ["BIM_MoveView"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(BIMWorkbench)

# Preference pages for importing and exporting various file formats
# are independent of the loading of the workbench and can be loaded at startup


def QT_TRANSLATE_NOOP(context, text):
    return text


t = QT_TRANSLATE_NOOP("QObject", "Import-Export")
FreeCADGui.addPreferencePage(":/ui/preferences-ifc.ui", t)
FreeCADGui.addPreferencePage(":/ui/preferences-ifc-export.ui", t)
FreeCADGui.addPreferencePage(":/ui/preferences-dae.ui", t)
FreeCADGui.addPreferencePage(":/ui/preferences-sh3d-import.ui", t)
FreeCADGui.addPreferencePage(":/ui/preferences-webgl.ui", t)

# Add unit tests
FreeCAD.__unit_test__ += ["TestArchGui"]
# The NativeIFC tests require internet connection and file download
# FreeCAD.__unit_test__ += ["nativeifc.ifc_selftest"]
