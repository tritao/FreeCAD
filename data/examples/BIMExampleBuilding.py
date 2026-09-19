# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association

"""Shared construction helpers for generated BIM example documents."""

import Arch
import FreeCAD as App


def make_wall(doc, name, start, end, *, align="Center", width=200.0):
    """Create a straight wall using the conventions shared by BIM examples."""

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
    """Create and host the standard door or window used by BIM examples."""

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
