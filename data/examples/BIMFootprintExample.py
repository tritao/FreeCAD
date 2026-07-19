# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors

"""Generate the BIM Footprint display-mode example file.

Run this with the GUI-enabled FreeCAD executable so the saved document keeps
its Footprint view modes::

    FreeCAD -t BIMFootprintExample.BIMFootprintExample -P /path/to/examples

The generated ``BIMFootprintExample.FCStd`` is written beside this script.
"""

from pathlib import Path
import unittest

import Arch
import Draft
import FreeCAD as App
import Part

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None


OUTPUT_FILE = Path(__file__).with_name("BIMFootprintExample.FCStd")
WINDOW_FRAME_DEPTH = 60.0
WINDOW_FRAME_WIDTH = 100.0


def _wall_point(x, y, distance, angle=0.0):
    """Return a point along a wall baseline."""

    direction = App.Rotation(App.Vector(0, 0, 1), angle).multVec(
        App.Vector(distance, 0, 0)
    )
    return App.Vector(x + direction.x, y + direction.y, 0)


def _make_wall(doc, name, x, y, length=6000.0, angle=0.0):
    end = _wall_point(x, y, length, angle)
    baseline = Draft.makeLine(
        App.Vector(x, y, 0),
        end,
    )
    baseline.Label = name + " baseline (hidden)"
    wall = Arch.makeWall(
        baseobj=baseline,
        width=250.0,
        height=3000.0,
        name=name,
    )
    return wall


def _make_hosted_window(
    doc,
    wall,
    name,
    x,
    y,
    z,
    width=900.0,
    height=700.0,
    angle=0.0,
    ifc_type="Window",
    visible=True,
):
    profile = doc.addObject("Sketcher::SketchObject", name + "Profile")
    frame = WINDOW_FRAME_WIDTH
    profile.addGeometry(
        [
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(width, 0, 0)),
            Part.LineSegment(App.Vector(width, 0, 0), App.Vector(width, height, 0)),
            Part.LineSegment(App.Vector(width, height, 0), App.Vector(0, height, 0)),
            Part.LineSegment(App.Vector(0, height, 0), App.Vector(0, 0, 0)),
            Part.LineSegment(
                App.Vector(frame, frame, 0),
                App.Vector(frame, height - frame, 0),
            ),
            Part.LineSegment(
                App.Vector(frame, height - frame, 0),
                App.Vector(width - frame, height - frame, 0),
            ),
            Part.LineSegment(
                App.Vector(width - frame, height - frame, 0),
                App.Vector(width - frame, frame, 0),
            ),
            Part.LineSegment(
                App.Vector(width - frame, frame, 0),
                App.Vector(frame, frame, 0),
            ),
        ]
    )
    # Wall baselines are centered on the wall thickness. Window profiles
    # extrude from their placement plane, so center the visible frame in the
    # wall instead of leaving it on the baseline's front side.
    wall_rotation = App.Rotation(App.Vector(0, 0, 1), angle)
    profile_origin = wall_rotation.multVec(
        App.Vector(0, -WINDOW_FRAME_DEPTH / 2.0, 0)
    )
    profile.Placement = App.Placement(
        App.Vector(x + profile_origin.x, y + profile_origin.y, z),
        wall_rotation.multiply(App.Rotation(App.Vector(1, 0, 0), 90)),
    )
    doc.recompute()

    window = Arch.makeWindow(profile, name=name)
    window.Width = width
    window.Height = height
    window.HoleDepth = 0
    if ifc_type == "Door":
        window.WindowParts = [
            "DoorPanel",
            "Solid panel",
            "Wire0",
            str(WINDOW_FRAME_DEPTH),
            "0",
        ]
        window.IfcType = "Door"
    else:
        window.WindowParts = [
            "DefaultFrame",
            "Frame",
            "Wire0,Wire1",
            str(WINDOW_FRAME_DEPTH),
            "0",
        ]
    if not visible:
        window.ViewObject.Visibility = False
    Arch.addComponents(window, wall)
    return window


def _make_slab(name, x, y, length=6000.0, width=3500.0):
    slab = Arch.makeStructure(
        length=length,
        width=width,
        height=200.0,
        name=name,
    )
    slab.IfcType = "Slab"
    # Arch structures are centered on their local origin, while the wall
    # helper uses (x, y) as the start of the wall baseline.
    slab.Placement.Base = App.Vector(x + length / 2.0, y, 0)
    return slab


def _set_footprint_mode(obj):
    if Gui is None or not App.GuiUp:
        return
    if "Footprint" in obj.ViewObject.listDisplayModes():
        obj.ViewObject.DisplayMode = "Footprint"


def generate(output_file=OUTPUT_FILE):
    """Create and save the demonstration document."""

    if "BIMFootprintExample" in App.listDocuments():
        App.closeDocument("BIMFootprintExample")

    doc = App.newDocument("BIMFootprintExample")

    building = Arch.makeBuilding(name="Footprint Demonstration Building")

    level_low = Arch.makeFloor(name="Level 01 - low plan cut")
    level_low.PlanCutHeight = 1500.0

    level_high = Arch.makeFloor(name="Level 02 - high plan cut")
    level_high.PlanCutHeight = 2300.0

    # The two levels sit side by side so their plan representations can be
    # compared in one top view. Their different PlanCutHeight values make the
    # two hosted openings resolve differently.
    wall_low = _make_wall(doc, "Wall - low cut", 0, 0)
    _make_hosted_window(doc, wall_low, "Opening below cut", 900, 0, 500)
    _make_hosted_window(doc, wall_low, "Opening above cut", 3900, 0, 1900)
    _make_hosted_window(doc, wall_low, "Opening crossing cut", 2200, 0, 1100, height=800)
    _make_hosted_window(
        doc,
        wall_low,
        "Hidden door opening",
        4800,
        0,
        700,
        width=700,
        height=2100,
        ifc_type="Door",
        visible=False,
    )

    slab_low = _make_slab("Slab - Footprint", 0, 0)
    comparison_wall = _make_wall(doc, "Wall - normal display", 0, 4500, 6000)

    wall_high = _make_wall(doc, "Wall - high cut", 8000, 0)
    _make_hosted_window(doc, wall_high, "High-level opening", 8900, 0, 1900)
    slab_high = _make_slab("Slab - comparison", 8000, 0)

    rotated_wall_origin = (0.0, 9000.0)
    rotated_wall_angle = 25.0
    wall_rotated = _make_wall(
        doc,
        "Wall - rotated",
        *rotated_wall_origin,
        length=4500.0,
        angle=rotated_wall_angle,
    )
    rotated_opening = _wall_point(*rotated_wall_origin, 900.0, rotated_wall_angle)
    _make_hosted_window(
        doc,
        wall_rotated,
        "Rotated wall opening",
        rotated_opening.x,
        rotated_opening.y,
        800,
        angle=rotated_wall_angle,
    )

    level_low.addObject(wall_low)
    level_low.addObject(slab_low)
    level_low.addObject(comparison_wall)
    level_high.addObject(wall_high)
    level_high.addObject(slab_high)
    level_high.addObject(wall_rotated)
    building.addObject(level_low)
    building.addObject(level_high)

    notes = doc.addObject("App::FeaturePython", "FootprintExampleNotes")
    notes.Label = "Footprint example - inspection notes"
    notes.addProperty("App::PropertyString", "Purpose", "Footprint example")
    notes.Purpose = "Compare wall and slab plan footprints, outlines, and snapping."
    notes.addProperty("App::PropertyStringList", "Checks", "Footprint example")
    notes.Checks = [
        "Select a wall or slab and inspect Footprint display mode.",
        "Change a storey's PlanCutHeight and watch hosted openings update.",
        "Use Draft snapping on the visible Footprint boundary outlines.",
        "Compare the normal-display wall with the derived plan graphics.",
        "Show the hosted windows to inspect their 3D frames and open centers; plan mode suppresses their 3D nodes.",
        "The low wall includes openings below, crossing, and above its plan cut.",
        "The hidden door remains hidden when the wall leaves Footprint mode.",
        "The rotated wall checks that hosted suppression follows wall placement.",
    ]
    notes.ViewObject.Visibility = False

    doc.recompute()

    for obj in (wall_low, slab_low, wall_high, wall_rotated):
        _set_footprint_mode(obj)
    if Gui is not None and App.GuiUp:
        comparison_wall.ViewObject.DisplayMode = "Flat Lines"
        slab_high.ViewObject.DisplayMode = "Flat Lines"
        Gui.Selection.clearSelection()
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()

    doc.recompute()
    doc.saveAs(str(output_file))
    return str(output_file)


class BIMFootprintExample(unittest.TestCase):
    """GUI test entry point used to generate the checked-in example."""

    def test_generate(self):
        output_file = generate()
        self.assertTrue(Path(output_file).is_file())
        generated_document = App.ActiveDocument
        generated_name = generated_document.Name
        App.closeDocument(generated_name)

        reopened = App.openDocument(output_file)
        self.assertEqual(reopened.getObject("Wall").ViewObject.DisplayMode, "Footprint")
        self.assertEqual(
            reopened.getObject("Structure").ViewObject.DisplayMode,
            "Footprint",
        )
        self.assertEqual(
            reopened.getObject("Wall002").ViewObject.DisplayMode,
            "Footprint",
        )
        self.assertEqual(
            reopened.getObject("Wall003").ViewObject.DisplayMode,
            "Footprint",
        )
        for name in ("Window", "Window001", "Window002", "Window004", "Window005"):
            window = reopened.getObject(name)
            self.assertTrue(window.ViewObject.Visibility)
            self.assertEqual(window.ViewObject.SwitchNode.whichChild.getValue(), -1)
            self.assertEqual(len(window.Base.Shape.Wires), 2)
            self.assertLess(
                window.Shape.Volume,
                window.Width.Value * window.Height.Value * WINDOW_FRAME_DEPTH,
            )
        hidden_door = reopened.getObject("Window003")
        self.assertFalse(hidden_door.ViewObject.Visibility)
        self.assertEqual(hidden_door.ViewObject.SwitchNode.whichChild.getValue(), -1)
        self.assertEqual(len(hidden_door.Base.Shape.Wires), 2)
        self.assertAlmostEqual(
            hidden_door.Shape.Volume,
            hidden_door.Width.Value * hidden_door.Height.Value * WINDOW_FRAME_DEPTH,
        )
        reopened.getObject("Wall").ViewObject.DisplayMode = "Flat Lines"
        reopened.getObject("Wall002").ViewObject.DisplayMode = "Flat Lines"
        reopened.getObject("Wall003").ViewObject.Visibility = False
        self.assertEqual(
            reopened.getObject("Window005").ViewObject.SwitchNode.whichChild.getValue(),
            -1,
        )
        reopened.getObject("Wall003").ViewObject.Visibility = True
        self.assertTrue(reopened.getObject("Window005").ViewObject.Visibility)
        self.assertEqual(
            reopened.getObject("Window005").ViewObject.SwitchNode.whichChild.getValue(),
            -1,
        )
        self.assertTrue(reopened.getObject("Window").ViewObject.Visibility)
        self.assertTrue(reopened.getObject("Window001").ViewObject.Visibility)
        self.assertTrue(reopened.getObject("Window002").ViewObject.Visibility)
        self.assertFalse(reopened.getObject("Window003").ViewObject.Visibility)
        self.assertTrue(reopened.getObject("Window004").ViewObject.Visibility)
        self.assertTrue(reopened.getObject("Window005").ViewObject.Visibility)
        App.closeDocument(reopened.Name)


if __name__ == "__main__":
    generate()
