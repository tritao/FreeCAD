# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association

"""Generate the BIM Sheets and material cut-pattern example document.

Run with the GUI FreeCAD binary from the repository root:

    ./build/bin/FreeCAD data/examples/BIMSheetsMaterials.py
"""

import os

import Arch
import FreeCAD as App
import FreeCADGui as Gui
import Materials
from BIMExampleBuilding import make_opening, make_wall
from bimsheets import BIMSheetService, BIMSheetViewTitleService
from bimviews.service import BIMViewService
from PySide import QtCore


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_PATH = os.path.join(ROOT, "data", "examples", "BIMSheetsMaterials.FCStd")
TEMPLATE_PATH = os.path.join(
    App.getResourceDir(), "Mod", "TechDraw", "Templates", "Default_Template_A4_Landscape.svg"
)


def material_from_card(name, relative_path, section_color):
    """Create a document material backed by an official FreeCAD card."""

    card_path = os.path.join(
        App.getResourceDir(), "Mod", "Material", "Resources", "Materials", *relative_path
    )
    material = Arch.makeMaterial(name=name)
    material.Label = name
    material.Material = Materials.MaterialManager().getMaterialByPath(card_path).Properties
    material.SectionColor = section_color
    return material


def center_at_scale(document, page, drawing_view, scale):
    """Apply an exact scale and center its complete titled footprint."""

    sheets = BIMSheetService(document)
    suggestion = sheets.fit_view_layout(
        page,
        drawing_view,
        preferred_scale=scale,
        allow_larger=False,
        centered=True,
    )
    drawing_view.Scale = suggestion.scale
    drawing_view.X = suggestion.x
    drawing_view.Y = suggestion.y
    BIMSheetViewTitleService(document).position_below_view(drawing_view)


def build_document():
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    doc = App.newDocument("BIMSheetsMaterials")
    doc.Label = "BIM Sheets - Material Cut Patterns"
    App.setActiveDocument(doc.Name)
    Gui.ActiveDocument = Gui.getDocument(doc.Name)

    level = Arch.makeFloor(name="Level 0")
    building = Arch.makeBuilding(name="Material Sample Building")
    building.addObject(level)
    if hasattr(level, "PlanCutHeight"):
        level.PlanCutHeight = 1200.0

    concrete = material_from_card(
        "Concrete - SVG pattern",
        ("Patterns", "Pattern Files", "concrete.FCMat"),
        (0.88, 0.88, 0.84),
    )
    insulation = material_from_card(
        "Insulation - PAT hatch",
        ("Patterns", "PAT", "Diagonal4.FCMat"),
        (0.96, 0.93, 0.72),
    )
    exterior_material = Arch.makeMultiMaterial(name="LayeredExteriorWall")
    exterior_material.Label = "Concrete + insulation wall assembly"
    exterior_material.Materials = [concrete, insulation]
    exterior_material.Thicknesses = [200.0, 100.0]

    walls = [
        make_wall(doc, "North layered wall", App.Vector(0, 4000), App.Vector(6000, 4000), width=300),
        make_wall(doc, "East layered wall", App.Vector(6000, 4000), App.Vector(6000, 0), width=300),
        make_wall(doc, "South layered wall", App.Vector(6000, 0), App.Vector(0, 0), width=300),
        make_wall(doc, "West layered wall", App.Vector(0, 0), App.Vector(0, 4000), width=300),
        make_wall(doc, "Interior solid-fill wall", App.Vector(3000, 0), App.Vector(3000, 4000), width=150),
    ]
    for wall in walls[:4]:
        wall.Material = exterior_material
    for wall in walls:
        level.addObject(wall)

    perimeter_joints = [
        Arch.makeWallJoint(walls[0], walls[1], "Miter", name="NorthEastCorner"),
        Arch.makeWallJoint(walls[1], walls[2], "Miter", name="SouthEastCorner"),
        Arch.makeWallJoint(walls[2], walls[3], "Miter", name="SouthWestCorner"),
        Arch.makeWallJoint(walls[3], walls[0], "Miter", name="NorthWestCorner"),
    ]
    interior_joints = [
        Arch.makeWallJoint(walls[2], walls[4], "Tee", name="InteriorSouthTee"),
        Arch.makeWallJoint(walls[0], walls[4], "Tee", name="InteriorNorthTee"),
    ]
    for joint in interior_joints:
        joint.TeeStem = "WallB"
    for joint in perimeter_joints + interior_joints:
        level.addObject(joint)

    door = make_opening(
        doc, walls[2], "Hosted Door", App.Vector(4300, 0), 900.0, 2100.0, door=True
    )
    window = make_opening(
        doc, walls[0], "Hosted Window", App.Vector(1200, 4000), 1200.0, 1200.0
    )
    level.addObject(door)
    level.addObject(window)
    doc.recompute()

    views = BIMViewService(doc)
    views.create_model_view("Default 3D", building)
    plan = views.create_plan_view("Ground Floor Material Plan", level)

    sheets = BIMSheetService(doc)
    page_50, view_50 = views.create_sheet_from_view(plan, TEMPLATE_PATH, page_scale=0.02)
    view_50.CutFillMode = "Material"
    center_at_scale(doc, page_50, view_50, 0.02)

    page_100, view_100 = views.create_sheet_from_view(plan, TEMPLATE_PATH, page_scale=0.01)
    view_100.CutFillMode = "Material"
    center_at_scale(doc, page_100, view_100, 0.01)
    doc.recompute()

    gui_startup = doc.settings("Gui.Startup")
    gui_startup.setInt("SchemaVersion", 1)
    gui_startup.setString("Workbench", "BIMWorkbench")
    page_50.ViewObject.Visibility = False
    page_100.ViewObject.Visibility = False
    view_50.CutFillMode = "Material"
    view_100.CutFillMode = "Material"
    doc.recompute()
    doc.saveAs(OUTPUT_PATH)
    App.closeDocument(doc.Name)


build_document()
QtCore.QTimer.singleShot(0, Gui.getMainWindow().close)
