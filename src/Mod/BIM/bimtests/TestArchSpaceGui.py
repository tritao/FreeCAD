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
        self.assertGreater(proxy.fcoords.point.getNum(), 0)
        self.assertGreater(proxy.fset.coordIndex.getNum(), 0)
