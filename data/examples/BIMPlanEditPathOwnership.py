# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association

"""Generate the BIM Plan Edit path-ownership example document.

Run with the GUI FreeCAD binary from the repository root:

    ./build/bin/FreeCAD data/examples/BIMPlanEditPathOwnership.py
"""

import os

import Arch
import Draft
import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_PATH = os.path.join(ROOT, "data", "examples", "BIMPlanEditPathOwnership.FCStd")
FONT_PATH = os.path.join(ROOT, "data", "examples", "osifont-lgpl3fe.ttf")


def add_label(text, point, size=135.0):
    label = Draft.make_shapestring(text, FONT_PATH, Size=size, Tracking=0)
    label.Label = text
    label.Placement.Base = point
    label.ViewObject.ShapeColor = (0.05, 0.05, 0.05, 0.0)
    return label


def add_case(doc, level, index, title, wall, label_point):
    group = doc.addObject("App::DocumentObjectGroup", "Case{:02d}".format(index))
    group.Label = "{:02d} {}".format(index, title)
    level.addObject(group)
    group.addObject(add_label(group.Label, label_point))
    group.addObject(wall)
    return group


def build_document():
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    doc = App.newDocument("BIMPlanEditPathOwnership")
    doc.Label = "BIM Plan Edit - Path Ownership"
    App.setActiveDocument(doc.Name)
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    level = Arch.makeFloor(name="Level 0 - select this and start Plan Edit")

    native = Arch.makeWall(length=2600, width=200, height=2500)
    native.Label = "Native wall - BIM owns two endpoints"
    native.Placement.Base = App.Vector(1300, 0, 0)
    add_case(doc, level, 1, "Native endpoints", native, App.Vector(0, -450, 2800))

    draft_line = Draft.make_line(App.Vector(0, 2200), App.Vector(2600, 2200))
    draft_line.Label = "Draft line path owner"
    line_wall = Arch.makeWall(draft_line, width=200, height=2500)
    line_wall.Label = "Draft line wall - Draft owns endpoints"
    case = add_case(doc, level, 2, "Draft line-owned path", line_wall, App.Vector(0, 1750, 2800))
    case.addObject(draft_line)

    draft_wire = Draft.makeWire(
        [App.Vector(0, 4400), App.Vector(1500, 4400), App.Vector(2600, 5200)]
    )
    draft_wire.Label = "Draft wire path owner"
    wire_wall = Arch.makeWall(draft_wire, width=200, height=2500)
    wire_wall.Label = "Draft wire wall - three editable vertices"
    case = add_case(doc, level, 3, "Draft wire-owned path", wire_wall, App.Vector(0, 3950, 2800))
    case.addObject(draft_wire)

    sketch = doc.addObject("Sketcher::SketchObject", "JoinedSketchPath")
    sketch.Label = "Sketch path owner with coincident junction"
    sketch.addGeometry(
        [
            Part.LineSegment(App.Vector(0, 6600), App.Vector(1400, 6600)),
            Part.LineSegment(App.Vector(1400, 6600), App.Vector(2600, 7400)),
        ],
        False,
    )
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
    sketch_wall = Arch.makeWall(sketch, width=200, height=2500)
    sketch_wall.Label = "Sketch wall - solver owns joined vertex"
    case = add_case(doc, level, 4, "Sketch solver-owned path", sketch_wall, App.Vector(0, 6150, 2800))
    case.addObject(sketch)

    blocked = doc.addObject("Sketcher::SketchObject", "BlockedSketchPath")
    blocked.Label = "Fully blocked Sketch path owner"
    blocked.addGeometry(
        Part.LineSegment(App.Vector(0, 8800), App.Vector(2600, 8800)), False
    )
    blocked.addConstraint(Sketcher.Constraint("Block", 0))
    blocked_wall = Arch.makeWall(blocked, width=200, height=2500)
    blocked_wall.Label = "Blocked Sketch wall - no path handles"
    case = add_case(doc, level, 5, "Constrained path - handles suppressed", blocked_wall, App.Vector(0, 8350, 2800))
    case.addObject(blocked)

    expression_wall = Arch.makeWall(length=2600, width=200, height=2500)
    expression_wall.Label = "Expression wall - native endpoint handles suppressed"
    expression_wall.Placement.Base = App.Vector(1300, 11000, 0)
    expression_wall.setExpression("Length", "2600 mm")
    add_case(doc, level, 6, "Expression-owned length", expression_wall, App.Vector(0, 10550, 2800))

    notes = doc.addObject("App::DocumentObjectGroup", "Instructions")
    notes.Label = "Instructions - select each wall and compare its orange handles"
    notes.addObject(add_label("PATH OWNERSHIP", App.Vector(3600, 0, 2800), 220))
    notes.addObject(add_label("Orange handles mutate the semantic owner", App.Vector(3600, -350, 2800), 110))
    notes.addObject(add_label("Blocked and expression-owned paths stay protected", App.Vector(3600, -600, 2800), 100))

    doc.recompute()
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    doc.recompute()
    doc.saveAs(OUTPUT_PATH)
    App.closeDocument(doc.Name)


build_document()
QtCore.QTimer.singleShot(0, Gui.getMainWindow().close)
