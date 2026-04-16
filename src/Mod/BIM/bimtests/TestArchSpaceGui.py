# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD contributors                               *
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

"""GUI regressions for Arch Space footprint display."""

import Arch
import Part
from bimtests import TestArchBaseGui


class TestArchSpaceGui(TestArchBaseGui.TestArchBaseGui):
    def _find_first_coin_node(self, node, coin_class):
        matches = self._find_coin_nodes(node, coin_class)
        return matches[0] if matches else None

    def _find_coin_nodes(self, node, coin_class):
        if not node:
            return []

        stack = [node]
        class_type = coin_class.getClassTypeId()
        matches = []

        while stack:
            current = stack.pop()
            if not current:
                continue
            if current.isOfType(class_type):
                matches.append(current)
            if hasattr(current, "getNumChildren"):
                for index in range(current.getNumChildren()):
                    stack.append(current.getChild(index))
        return matches

    def test_space_populates_footprint_display_data(self):
        """Spaces should expose footprint display data through the generic mode."""

        base = self.document.addObject("Part::Feature", "GuiSpaceBox")
        base.Shape = Part.makeBox(1000, 500, 2000)
        space = Arch.makeSpace([base])
        self.document.recompute()
        self.pump_gui_events()

        proxy = space.ViewObject.Proxy
        self.assertIn("Footprint", space.ViewObject.listDisplayModes())
        self.assertTrue(hasattr(proxy, "fcoords"))
        self.assertTrue(hasattr(proxy, "fset"))
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.fcoords.point.getNum(), 0)
        self.assertGreater(proxy.fset.coordIndex.getNum(), 0)
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_space_footprint_display_is_a_subtle_underlay(self):
        """Space footprint fills should render as an offset underlay behind walls."""

        from pivy import coin

        base = self.document.addObject("Part::Feature", "GuiSpaceUnderlayBox")
        base.Shape = Part.makeBox(1000, 500, 2000)
        space = Arch.makeSpace([base])
        space.ViewObject.DrawStyle = "Dashed"
        self.document.recompute()
        self.pump_gui_events()

        proxy = space.ViewObject.Proxy
        footprint_group = getattr(proxy, "footprintgroup", None)

        self.assertIsNotNone(footprint_group)

        material = self._find_first_coin_node(footprint_group, coin.SoMaterial)
        self.assertIsNotNone(material)
        self.assertGreater(float(material.transparency[0]), 0.8)

        fill_offset = next(
            (
                node
                for node in self._find_coin_nodes(footprint_group, coin.SoPolygonOffset)
                if node.styles.getValue() == coin.SoPolygonOffsetElement.FILLED
            ),
            None,
        )
        self.assertIsNotNone(fill_offset)
        self.assertGreater(fill_offset.units.getValue(), 0.0)

        draw_style = self._find_first_coin_node(footprint_group, coin.SoDrawStyle)
        self.assertIsNotNone(draw_style)
        self.assertEqual(draw_style.linePattern.getValue(), 0xF00F)
