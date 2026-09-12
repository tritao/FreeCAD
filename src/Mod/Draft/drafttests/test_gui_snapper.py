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
import DraftGui
from draftguitools import gui_base
from draftguitools import gui_snapper
from draftguitools import gui_trackers
from drafttests import test_base
from pivy import coin
from types import SimpleNamespace
from unittest.mock import patch


class DraftSnapper(test_base.DraftTestCaseDoc):
    class _FakeFocusWidget:
        def __init__(self, policy):
            self.policy = policy

        def focusPolicy(self):
            return self.policy

        def setFocusPolicy(self, policy):
            self.policy = policy

        def isAncestorOf(self, widget):
            return False

        def clearFocus(self):
            pass

    class _FakeTray(_FakeFocusWidget):
        def __init__(self, policy, children):
            super().__init__(policy)
            self.children = children

        def findChildren(self, widget_type):
            return self.children

    class _FakeToolbar:
        def __init__(self):
            self.mouse = True
            self.off_ui_calls = 0

        def pointUi(self, **kwargs):
            self.cancel = kwargs.get("cancel")

        def lineUi(self, **kwargs):
            self.pointUi(**kwargs)

        def wireUi(self, **kwargs):
            self.pointUi(**kwargs)

        def offUi(self):
            self.off_ui_calls += 1

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

    class _FakeMoveEvent:
        def getPosition(self):
            return (12, 34)

        def wasCtrlDown(self):
            return True

        def wasShiftDown(self):
            return False

        def wasAltDown(self):
            return True

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

    def test_cancel_point_request_removes_callbacks_and_restores_ui(self):
        """Programmatic cancellation should detach callbacks and close point UI."""

        snapper = Gui.Snapper
        toolbar = self._FakeToolbar()
        view = self._FakeView()

        with patch.object(gui_snapper.gui_utils, "get_3d_view", return_value=view), patch.object(
            gui_snapper.gui_utils, "end_all_events", return_value=None
        ), patch.object(gui_snapper.Gui, "draftToolBar", toolbar, create=True), patch.object(
            snapper, "off", return_value=None
        ):
            snapper.getPoint(callback=lambda point: None)
            self.assertIsNotNone(view.click_callback)
            self.assertIsNotNone(view.move_callback)

            snapper.cancelPointRequest()

        self.assertIsNone(view.click_callback)
        self.assertIsNone(view.move_callback)
        self.assertIsNone(snapper.callbackClick)
        self.assertIsNone(snapper.callbackMove)
        self.assertEqual(toolbar.off_ui_calls, 1)

    def test_temporary_snap_profiles_restore_without_persisting(self):
        """Nested host profiles should restore prior snaps without writing preferences."""

        snapper = Gui.Snapper
        original = snapper.get_snap_modes()
        first, second = snapper.snaps[:2]

        with patch.object(snapper, "save_snap_state") as save_snap_state:
            self.assertEqual(snapper.push_snap_modes([first]), [first])
            self.assertEqual(snapper.push_snap_modes([second]), [second])
            self.assertEqual(snapper.pop_snap_modes(), [first])
            self.assertEqual(snapper.pop_snap_modes(), original)

        save_snap_state.assert_not_called()

    def test_interaction_host_forwards_hints_and_modifier_resolver(self):
        """Embedded hosts should pass point-input policy to Snapper."""

        received = {}

        def get_point(**kwargs):
            received.update(kwargs)

        callback = lambda point: None
        resolver = lambda ctrl, shift, alt: (not ctrl, alt)
        hints = [object()]
        with patch.object(
            gui_base.Gui, "Snapper", SimpleNamespace(getPoint=get_point), create=True
        ):
            gui_base.DraftInteractionHost().request_point(
                callback, hints=hints, modifier_resolver=resolver
            )

        self.assertIs(received["callback"], callback)
        self.assertIs(received["modifier_resolver"], resolver)
        self.assertIs(received["hints"], hints)

    def test_point_request_uses_host_modifier_resolution(self):
        """The Snapper applies a host's modifier policy before snapping."""

        snapper = Gui.Snapper
        toolbar = self._FakeToolbar()
        view = self._FakeView()
        plane = object()
        calls = []

        def resolve(ctrl, shift, alt):
            return False, alt

        with patch.object(gui_snapper.gui_utils, "get_3d_view", return_value=view), patch.object(
            gui_snapper.gui_utils, "end_all_events", return_value=None
        ), patch.object(gui_snapper.Gui, "draftToolBar", toolbar, create=True), patch.object(
            snapper, "snap", side_effect=lambda *args, **kwargs: calls.append(kwargs) or App.Vector()
        ), patch.object(snapper, "unconstrain", return_value=None):
            snapper.getPoint(
                callback=lambda point: None,
                modifier_resolver=resolve,
                interaction_plane=plane,
                noTracker=True,
            )
            view.move_callback(self._FakeEventCallback(self._FakeMoveEvent()))

        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]["active"])
        self.assertTrue(calls[0]["constrain"])
        self.assertTrue(calls[0]["noTracker"])

    def test_interaction_plane_is_used_and_cleared_on_cancel(self):
        """A point request uses only its supplied plane and clears it on teardown."""

        snapper = Gui.Snapper
        toolbar = self._FakeToolbar()
        view = self._FakeView()
        plane = object()

        with patch.object(gui_snapper.gui_utils, "get_3d_view", return_value=view), patch.object(
            gui_snapper.gui_utils, "end_all_events", return_value=None
        ), patch.object(gui_snapper.Gui, "draftToolBar", toolbar, create=True), patch.object(
            gui_snapper.WorkingPlane, "get_working_plane", side_effect=AssertionError
        ), patch.object(snapper, "off", return_value=None):
            snapper.getPoint(callback=lambda point: None, interaction_plane=plane)
            self.assertIs(snapper._get_wp(), plane)
            snapper.cancelPointRequest()

        self.assertIsNone(snapper.interaction_plane)

    def test_tracker_uses_an_explicit_working_plane(self):
        """Trackers embedded in a host should prefer their assigned plane."""

        plane = object()
        tracker = SimpleNamespace(working_plane=plane)
        self.assertIs(gui_trackers.Tracker._get_wp(tracker), plane)

    def test_draft_point_focus_policy_is_restored(self):
        """Point-focus suppression must restore each Draft widget's old policy."""

        child = self._FakeFocusWidget(1)
        tray = self._FakeTray(2, [child])
        toolbar = DraftGui.DraftToolBar.__new__(DraftGui.DraftToolBar)
        toolbar.tray = tray
        toolbar.suppress_point_focus = False
        toolbar._saved_point_focus_policies = {}

        toolbar.setPointFocusSuppressed(True)
        self.assertEqual(tray.focusPolicy(), DraftGui.QtCore.Qt.NoFocus)
        self.assertEqual(child.focusPolicy(), DraftGui.QtCore.Qt.NoFocus)

        toolbar.setPointFocusSuppressed(False)
        self.assertEqual(tray.focusPolicy(), 2)
        self.assertEqual(child.focusPolicy(), 1)
        self.assertFalse(toolbar._saved_point_focus_policies)
