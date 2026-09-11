# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
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

"""GUI tests for Draft Snapper point-pick behavior."""

import FreeCAD as App
import FreeCADGui as Gui
from draftguitools import gui_snapper
from drafttests import test_base
from pivy import coin
from unittest.mock import patch


class DraftSnapper(test_base.DraftTestCaseDoc):
    class _FakeToolbar:
        def __init__(self):
            self.mouse = True

        def pointUi(self, **kwargs):
            self.cancel = kwargs.get("cancel")

        def lineUi(self, **kwargs):
            self.pointUi(**kwargs)

        def wireUi(self, **kwargs):
            self.pointUi(**kwargs)

        def offUi(self):
            pass

        def displayPoint(self, *args, **kwargs):
            pass

    class _FakeView:
        def __init__(self):
            self.click_callback = None
            self.move_callback = None

        def addEventCallbackPivy(self, event_type, callback):
            if event_type == coin.SoMouseButtonEvent.getClassTypeId():
                self.click_callback = callback
            elif event_type == coin.SoLocation2Event.getClassTypeId():
                self.move_callback = callback
            return callback

        def removeEventCallbackPivy(self, event_type, callback):
            if event_type == coin.SoMouseButtonEvent.getClassTypeId():
                if self.click_callback == callback:
                    self.click_callback = None
            elif event_type == coin.SoLocation2Event.getClassTypeId():
                if self.move_callback == callback:
                    self.move_callback = None

    class _FakeMouseEvent:
        def getButton(self):
            return 1

        def getState(self):
            return coin.SoMouseButtonEvent.DOWN

    class _FakeEventCallback:
        def __init__(self, event):
            self._event = event

        def getEvent(self):
            return self._event

    def test_getpoint_accept_preserves_point_before_teardown(self):
        """Accept should preserve the picked point even if teardown clears Snapper.pt."""

        snapper = Gui.Snapper
        toolbar = self._FakeToolbar()
        view = self._FakeView()
        received = []

        def callback(point):
            received.append(point)

        def fake_teardown():
            snapper.pt = None

        with patch.object(gui_snapper.gui_utils, "get_3d_view", return_value=view), patch.object(
            gui_snapper.gui_utils, "end_all_events", return_value=None
        ), patch.object(gui_snapper.Gui, "draftToolBar", toolbar, create=True), patch.object(
            snapper, "_teardown_point_request", side_effect=fake_teardown
        ):
            snapper.getPoint(callback=callback)
            snapper.pt = App.Vector(1, 2, 3)
            snapper.snapInfo = {}
            self.assertIsNotNone(view.click_callback)
            view.click_callback(self._FakeEventCallback(self._FakeMouseEvent()))

        self.assertEqual(received, [App.Vector(1, 2, 3)])
