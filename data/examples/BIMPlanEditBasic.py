# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association

"""Generate the basic BIM Plan Edit example document.

Run with the GUI FreeCAD binary from the repository root:

    ./build/bin/FreeCAD data/examples/BIMPlanEditBasic.py
"""

import os

import Arch
import ArchSpace
import Draft
import FreeCAD as App
import FreeCADGui as Gui
import Part
from bimviews.service import BIMViewService
from PySide import QtCore


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_PATH = os.path.join(ROOT, "data", "examples", "BIMPlanEditBasic.FCStd")
FONT_PATH = os.path.join(ROOT, "data", "examples", "osifont-lgpl3fe.ttf")


def make_wall(doc, name, start, end, *, align="Center", width=200.0):
    direction = end.sub(start)
    wall = Arch.makeWall(length=direction.Length, width=width, height=2800.0)
    wall.Label = name
    wall.Align = align
    wall.Placement = App.Placement(
        (start + end) * 0.5,
        App.Rotation(App.Vector(1, 0, 0), direction.normalize()),
    )
    doc.recompute()
    return wall


def make_opening(doc, wall, name, point, width, height, *, door=False, sill=900.0):
    placement = App.Placement(
        point + App.Vector(0, 0, 0 if door else sill),
        App.Rotation(App.Vector(1, 0, 0), 90),
    )
    opening = Arch.makeWindowPreset(
        "Simple door" if door else "Open 1-pane",
        width=width,
        height=height,
        h1=50.0,
        h2=50.0,
        h3=0.0,
        w1=100.0,
        w2=40.0 if door else 50.0,
        o1=0.0,
        o2=0.0 if door else 50.0,
        placement=placement,
    )
    opening.Label = name
    if door:
        opening.Opening = 100
    Arch.addComponents(opening, wall)
    doc.recompute()
    return opening


def add_label(text, point, size=170.0):
    label = Draft.make_shapestring(text, FONT_PATH, Size=size, Tracking=0)
    label.Label = text
    label.Placement.Base = point
    label.ViewObject.ShapeColor = (0.05, 0.05, 0.05, 0.0)
    return label


def build_document():
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    doc = App.newDocument("BIMPlanEditBasic")
    doc.Label = "BIM Plan Edit - Basic"
    App.setActiveDocument(doc.Name)
    Gui.ActiveDocument = Gui.getDocument(doc.Name)

    level = Arch.makeFloor(name="Level 0 - select this and start Plan Edit")
    building = Arch.makeBuilding(name="Sample Building")
    building.addObject(level)
    if hasattr(level, "PlanCutHeight"):
        level.PlanCutHeight = 1200.0

    walls = [
        make_wall(doc, "North - Center aligned", App.Vector(0, 4000), App.Vector(6000, 4000)),
        make_wall(doc, "East - Right aligned", App.Vector(6000, 4000), App.Vector(6000, 0), align="Right"),
        make_wall(doc, "South - Left aligned", App.Vector(6000, 0), App.Vector(0, 0), align="Left"),
        make_wall(doc, "West - Center aligned", App.Vector(0, 0), App.Vector(0, 4000)),
        make_wall(doc, "Interior editable wall", App.Vector(3000, 0), App.Vector(3000, 4000), width=150.0),
    ]
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
    doc.recompute()

    door = make_opening(
        doc, walls[2], "Hosted Door - move and resize", App.Vector(4300, 0), 900.0, 2100.0, door=True
    )
    window = make_opening(
        doc, walls[0], "Hosted Window - move and resize", App.Vector(1200, 4000), 1200.0, 1200.0
    )
    level.addObject(door)
    level.addObject(window)

    room_base = doc.addObject("Part::Feature", "RoomSpaceBase")
    room_base.Label = "Room footprint source"
    # Match the finished faces of the west, south, north, and interior walls.
    room_base.Shape = Part.makeBox(2825, 3700, 1, App.Vector(100, 200, 0))
    room = Arch.makeSpace(room_base, name="Sample Room")
    room_seed = App.Vector(1512.5, 2050, 0)
    room_boundaries = [
        (wall, ArchSpace.getBoundaryFaceNamesForObject(wall, room_seed))
        for wall in (walls[3], walls[2], walls[0], walls[4])
    ]
    ArchSpace.setBoundaryRegionReferencePoint(room, room_seed)
    ArchSpace.setBoundaryLinks(room, room_boundaries)
    level.addObject(room)

    section = Arch.makeSectionPlane(walls + [door, window], name="Editable Section")
    section.Placement = App.Placement(
        App.Vector(3000, 2000, 1400), App.Rotation(App.Vector(1, 0, 0), 90)
    )

    notes = doc.addObject("App::DocumentObjectGroup", "Instructions")
    notes.Label = "Instructions - orange points are contextual handles"
    notes.addObject(add_label("BIM PLAN EDIT - BASIC", App.Vector(0, -700, 3200), 220))
    notes.addObject(
        add_label(
            "Open Ground Floor Plan or South Elevation in BIM Navigator",
            App.Vector(0, -1000, 3200),
            105,
        )
    )
    notes.addObject(add_label("Drag wall ends, wall width and opening handles", App.Vector(0, -1250, 3200), 105))

    doc.recompute()
    service = BIMViewService(doc)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    service.create_model_view("Default 3D", building)
    service.create_elevation_view("South Elevation", level, direction="South")
    service.create_section_view("Building Section", section)
    plan_view = service.create_plan_view("Ground Floor Plan", level)

    gui_startup = doc.settings("Gui.Startup")
    gui_startup.setInt("SchemaVersion", 1)
    gui_startup.setString("Workbench", "BIMWorkbench")
    bim_startup = doc.settings("BIM.Startup")
    bim_startup.setInt("SchemaVersion", 1)
    bim_startup.setString("Activity", "PlanEdit")
    bim_startup.setString("ContextObject", level.Name)
    bim_startup.setString("ViewObject", plan_view.Name)
    doc.recompute()
    doc.saveAs(OUTPUT_PATH)
    App.closeDocument(doc.Name)


build_document()
QtCore.QTimer.singleShot(0, Gui.getMainWindow().close)
