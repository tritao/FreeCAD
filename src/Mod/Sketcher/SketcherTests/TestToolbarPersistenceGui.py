# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import FreeCAD

try:
    import FreeCADGui
except ImportError:
    FreeCADGui = None

from PySide import QtCore, QtGui


def is_gui_available():
    if FreeCADGui is None:
        return False

    try:
        return FreeCADGui.getMainWindow() is not None
    except (AttributeError, RuntimeError):
        return False


class TestToolbarPersistenceGui(unittest.TestCase):
    def setUp(self):
        if not is_gui_available():
            self.skipTest("GUI not available")

        self._modified_toolbars = {}
        self._ensure_workbenches("PartWorkbench", "PartDesignWorkbench", "SketcherWorkbench")
        self._set_per_workbench_layout_preference(True)

        self.doc = FreeCAD.newDocument("TestToolbarPersistenceGui")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        self.pump(200)

        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()
        self.pump(200)

    def tearDown(self):
        if not is_gui_available():
            return

        try:
            self._restore_toolbars()
        finally:
            gui_doc = FreeCADGui.ActiveDocument
            if gui_doc is not None:
                try:
                    gui_doc.resetEdit()
                except Exception:
                    # resetEdit() can legitimately fail when nothing is currently in edit mode.
                    pass

            if hasattr(self, "doc") and self.doc is not None:
                if self.doc.Name in FreeCAD.listDocuments():
                    FreeCAD.closeDocument(self.doc.Name)

    def _ensure_workbenches(self, *names):
        workbenches = FreeCADGui.listWorkbenches()
        missing = [name for name in names if name not in workbenches]
        if missing:
            self.skipTest(f"Required workbenches are unavailable: {', '.join(missing)}")

    def _set_per_workbench_layout_preference(self, enabled):
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
        saved = {
            "RememberToolbarLayoutByWorkbench": params.GetBool(
                "RememberToolbarLayoutByWorkbench", False
            )
        }
        self.addCleanup(self._restore_param_values, params, saved)
        params.SetBool("RememberToolbarLayoutByWorkbench", enabled)

    def _restore_param_values(self, params, values):
        for key, value in values.items():
            if isinstance(value, bool):
                params.SetBool(key, value)
            else:
                params.SetString(key, value)

    def pump(self, timeout_ms=120):
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec_()

    def wait_until(self, predicate, description, timeout_ms=6000, step_ms=120):
        remaining = timeout_ms
        while remaining > 0:
            if predicate():
                return True
            self.pump(step_ms)
            remaining -= step_ms

        if predicate():
            return True

        self.fail(f"Timed out waiting for {description}")
        return False

    def main_window(self):
        return FreeCADGui.getMainWindow()

    def normalized_action_text(self, action):
        return str(action.text()).replace("&", "")

    def menu_action_texts(self, menu):
        return [
            text
            for text in (self.normalized_action_text(action) for action in menu.actions())
            if text
        ]

    def menu_section_texts(self, menu):
        return [
            text
            for text in (
                self.normalized_action_text(action)
                for action in menu.actions()
                if action.isSeparator()
            )
            if text
        ]

    def find_action_by_whats_this(self, whats_this):
        for action in self.main_window().findChildren(QtGui.QAction):
            if str(action.whatsThis()) == whats_this:
                return action
        return None

    def toolbar_menu(self):
        action = self.find_action_by_whats_this("Std_ToolBarMenu")
        self.assertIsNotNone(action, "Could not find Std_ToolBarMenu action")
        menu = action.menu()
        self.assertIsNotNone(menu, "Std_ToolBarMenu action should own a menu")
        return menu

    def capture_popup_menu(self, popup):
        popup.clear()
        popup.aboutToShow.emit()
        self.pump(120)
        texts = self.menu_action_texts(popup)
        sections = self.menu_section_texts(popup)
        return sections, texts

    def prepare_popup_menu(self, popup):
        popup.clear()
        popup.aboutToShow.emit()
        self.pump(120)
        return popup

    def trigger_menu_action(self, popup, action_text):
        menu = self.prepare_popup_menu(popup)
        for action in menu.actions():
            if self.normalized_action_text(action) == action_text:
                action.trigger()
                self.pump(250)
                return

        self.fail(f"Menu action '{action_text}' was not found")

    def find_menu_action(self, menu, action_text):
        for action in menu.actions():
            if self.normalized_action_text(action) == action_text:
                return action
        return None

    def find_menu_submenu(self, menu, action_text):
        action = self.find_menu_action(menu, action_text)
        if action is None:
            return None
        return action.menu()

    def trigger_menu_path(self, popup, *action_texts):
        menu = self.prepare_popup_menu(popup)
        for action_text in action_texts[:-1]:
            submenu = self.find_menu_submenu(menu, action_text)
            self.assertIsNotNone(submenu, f"Menu '{action_text}' was not found")
            menu = self.prepare_popup_menu(submenu)

        action = self.find_menu_action(menu, action_texts[-1])
        self.assertIsNotNone(action, f"Menu action '{action_texts[-1]}' was not found")
        action.trigger()
        self.pump(250)

    def capture_status_bar_context_menu(self):
        status_bar = self.main_window().statusBar()
        self.assertIsNotNone(status_bar, "Main window should provide a status bar")

        result = {}
        local_pos = status_bar.rect().center()
        global_pos = status_bar.mapToGlobal(local_pos)
        QtGui.QCursor.setPos(global_pos)

        def capture():
            popup = QtGui.QApplication.activePopupWidget()
            if popup is None:
                return

            result["texts"] = self.menu_action_texts(popup)
            result["sections"] = self.menu_section_texts(popup)
            popup.hide()

        QtCore.QTimer.singleShot(150, capture)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            local_pos,
            global_pos,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier,
        )
        QtGui.QApplication.sendEvent(status_bar, event)
        self.assertIn("texts", result, "Status bar context menu did not open")
        self.pump(120)
        return result["sections"], result["texts"]

    def active_view_graphics_view(self):
        active_view = getattr(FreeCADGui.ActiveDocument, "ActiveView", None)
        self.assertIsNotNone(active_view, "Expected an active FreeCAD GUI view")
        graphics_view = active_view.graphicsView()
        self.assertIsNotNone(
            graphics_view, "Expected the active GUI view to expose a graphics view"
        )
        return graphics_view

    def open_active_view_context_menu(self):
        popup = QtGui.QApplication.activePopupWidget()
        if popup is not None:
            popup.hide()
            self.pump(120)

        graphics_view = self.active_view_graphics_view()
        target = graphics_view.viewport() if hasattr(graphics_view, "viewport") else graphics_view
        local_pos = target.rect().center()
        global_pos = target.mapToGlobal(local_pos)
        QtGui.QCursor.setPos(global_pos)

        press_event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            local_pos,
            global_pos,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier,
        )
        release_event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            local_pos,
            global_pos,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier,
        )
        QtGui.QApplication.sendEvent(target, press_event)
        self.pump(120)
        QtGui.QApplication.sendEvent(target, release_event)
        self.wait_until(
            lambda: QtGui.QApplication.activePopupWidget() is not None,
            "3D view context menu to open",
        )
        popup = QtGui.QApplication.activePopupWidget()
        self.assertIsNotNone(popup, "Expected the active view context menu popup")
        return popup

    def open_toolbar_context_menu(self, toolbar):
        popup = QtGui.QApplication.activePopupWidget()
        if popup is not None:
            popup.hide()
            self.pump(120)

        local_pos = toolbar.rect().center()
        global_pos = toolbar.mapToGlobal(local_pos)
        QtGui.QCursor.setPos(global_pos)

        press_event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            local_pos,
            global_pos,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier,
        )
        release_event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            local_pos,
            global_pos,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier,
        )
        QtGui.QApplication.sendEvent(toolbar, press_event)
        self.pump(120)
        QtGui.QApplication.sendEvent(toolbar, release_event)
        self.wait_until(
            lambda: QtGui.QApplication.activePopupWidget() is not None,
            "toolbar context menu to open",
        )
        popup = QtGui.QApplication.activePopupWidget()
        self.assertIsNotNone(popup, "Expected the toolbar context menu popup")
        return popup

    def toolbar_key(self, toolbar):
        key = toolbar.property("PersistenceKey")
        if key:
            return str(key)
        return str(toolbar.objectName())

    def toolbar_tier(self, toolbar):
        tier = toolbar.property("Tier")
        if tier:
            return str(tier)
        return ""

    def toolbar_host(self, toolbar):
        host = toolbar.property("Host")
        if host:
            return str(host)
        return "main-window"

    def toolbar_panel_role(self, toolbar):
        role = toolbar.property("PanelRole")
        if role:
            return str(role)
        return "none"

    def toolbar_view_presentation(self, toolbar):
        presentation = toolbar.property("ViewPresentation")
        if presentation:
            return str(presentation)
        return "docked"

    def toolbar_view_overlay_edge(self, toolbar):
        edge = toolbar.property("ViewOverlayEdge")
        if edge:
            return str(edge)
        return "top"

    def toolbar_overlay_lane(self, toolbar):
        if self.toolbar_view_presentation(toolbar) != "centered-overlay":
            return None
        return toolbar.parentWidget()

    def toolbar_overlay_anchor(self, toolbar):
        lane = self.toolbar_overlay_lane(toolbar)
        if lane is None:
            return None
        return lane.parentWidget()

    def model_tree_toolbar_host(self):
        hosts = [
            host
            for host in self.main_window().findChildren(QtGui.QWidget)
            if host.objectName() == "_fc_panel_toolbar_host_model_tree"
        ]
        self.assertTrue(hosts, "Expected a model-tree toolbar host widget")
        for host in hosts:
            if host.isVisible():
                return host
        return hosts[0]

    def toolbar_tier_label(self, toolbar):
        labels = {
            "recommended": QtGui.QApplication.translate("MainWindow", "Recommended"),
            "secondary": QtGui.QApplication.translate("MainWindow", "Secondary"),
            "advanced": QtGui.QApplication.translate("MainWindow", "Advanced"),
            "contextual": QtGui.QApplication.translate("MainWindow", "Contextual"),
        }
        return labels.get(self.toolbar_tier(toolbar), "")

    def toolbar_menu_label(self, toolbar):
        base_label = self.normalized_action_text(toolbar.toggleViewAction())
        if self.toolbar_tier(toolbar) in {"recommended", "contextual"}:
            return base_label

        tier_label = self.toolbar_tier_label(toolbar)
        if not tier_label:
            return base_label
        return f"{base_label} ({tier_label})"

    def toolbar_area_value(self, area):
        return int(getattr(area, "value", area))

    def toolbar_area_enum(self, value):
        mapping = {
            self.toolbar_area_value(QtCore.Qt.LeftToolBarArea): QtCore.Qt.LeftToolBarArea,
            self.toolbar_area_value(QtCore.Qt.RightToolBarArea): QtCore.Qt.RightToolBarArea,
            self.toolbar_area_value(QtCore.Qt.TopToolBarArea): QtCore.Qt.TopToolBarArea,
            self.toolbar_area_value(QtCore.Qt.BottomToolBarArea): QtCore.Qt.BottomToolBarArea,
            self.toolbar_area_value(QtCore.Qt.NoToolBarArea): QtCore.Qt.NoToolBarArea,
        }
        return mapping[value]

    def alternative_toolbar_area(self, toolbar):
        current_area = self.toolbar_area_value(
            self.toolbar_host_window(toolbar).toolBarArea(toolbar)
        )
        for area in (
            QtCore.Qt.RightToolBarArea,
            QtCore.Qt.LeftToolBarArea,
            QtCore.Qt.BottomToolBarArea,
            QtCore.Qt.TopToolBarArea,
        ):
            if self.toolbar_area_value(area) != current_area:
                return area

        return QtCore.Qt.TopToolBarArea

    def toolbar_area_name(self, area):
        mapping = {
            self.toolbar_area_value(QtCore.Qt.LeftToolBarArea): "Left",
            self.toolbar_area_value(QtCore.Qt.RightToolBarArea): "Right",
            self.toolbar_area_value(QtCore.Qt.TopToolBarArea): "Top",
            self.toolbar_area_value(QtCore.Qt.BottomToolBarArea): "Bottom",
        }
        return mapping[self.toolbar_area_value(area)]

    def backup_bool_param(self, params, key):
        existing = key in {str(name) for name in params.GetBools()}
        value = params.GetBool(key) if existing else False

        def restore():
            if existing:
                params.SetBool(key, value)
            else:
                params.RemBool(key)

        self.addCleanup(restore)

    def backup_group(self, params, group_name, backup_name):
        had_group = params.HasGroup(group_name)
        params.RemGroup(backup_name)
        if had_group:
            params.GetGroup(group_name).CopyTo(params.GetGroup(backup_name))

        def restore():
            params.RemGroup(group_name)
            if had_group:
                params.GetGroup(backup_name).CopyTo(params.GetGroup(group_name))
            params.RemGroup(backup_name)

        self.addCleanup(restore)

    def all_toolbars(self):
        return list(self.main_window().findChildren(QtGui.QToolBar))

    def active_mdi_view(self):
        mdi_area = self.mdi_area()
        sub_window = mdi_area.activeSubWindow()
        self.assertIsNotNone(sub_window, "Expected an active MDI subwindow")
        widget = sub_window.widget()
        self.assertIsNotNone(widget, "Expected the active MDI subwindow to own a widget")
        return widget

    def mdi_area(self):
        mdi_area = self.main_window().findChild(QtGui.QMdiArea)
        self.assertIsNotNone(mdi_area, "Main window should provide an MDI area")
        return mdi_area

    def mdi_sub_window(self, view):
        for sub_window in self.mdi_area().subWindowList():
            if sub_window.widget() is view:
                return sub_window

        self.fail("Expected MDI subwindow for the given view")

    def activate_mdi_view(self, view):
        sub_window = self.mdi_sub_window(view)
        mdi_area = self.mdi_area()
        mdi_area.setActiveSubWindow(sub_window)
        self.pump(250)
        self.wait_until(lambda: self.active_mdi_view() is view, "active MDI view to switch")
        return view

    def close_mdi_view(self, view):
        for sub_window in self.mdi_area().subWindowList():
            if sub_window.widget() is view:
                sub_window.close()
                self.pump(250)
                break

    def create_additional_view(self, title):
        mdi_area = self.mdi_area()
        existing = list(mdi_area.subWindowList())
        FreeCADGui.createViewer(1, title)
        self.pump(250)

        for sub_window in mdi_area.subWindowList():
            if sub_window not in existing:
                view = sub_window.widget()
                self.assertIsNotNone(view, "Expected a widget for the new MDI subwindow")
                self.addCleanup(self.close_mdi_view, view)
                return view

        self.fail("Expected createViewer() to add a new MDI subwindow")

    def create_text_document_view(self):
        mdi_area = self.mdi_area()
        existing = list(mdi_area.subWindowList())
        FreeCADGui.runCommand("Std_TextDocument")
        self.pump(250)

        for sub_window in mdi_area.subWindowList():
            if sub_window not in existing:
                view = sub_window.widget()
                self.assertIsNotNone(view, "Expected a widget for the new text document view")
                self.addCleanup(self.close_mdi_view, view)
                return view

        self.fail("Expected Std_TextDocument to add a new MDI subwindow")

    def toolbar_host_window(self, toolbar):
        if self.toolbar_host(toolbar) == "view":
            return self.active_mdi_view()
        return self.main_window()

    def assert_toolbar_panel_host(self, key):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        host = self.model_tree_toolbar_host()
        self.wait_until(
            lambda: toolbar.parentWidget() is host and toolbar.isVisible(),
            f"toolbar {key} to attach to the model-tree host",
        )

    def toolbars_for_prefix(self, prefix, active_only=False):
        items = []
        for toolbar in self.all_toolbars():
            key = self.toolbar_key(toolbar)
            if not key.startswith(prefix):
                continue
            if active_only and not toolbar.toggleViewAction().isVisible():
                continue
            items.append(toolbar)

        items.sort(key=lambda toolbar: self.toolbar_key(toolbar))
        return items

    def toolbar_by_key(self, key):
        for toolbar in self.all_toolbars():
            if self.toolbar_key(toolbar) == key:
                return toolbar
        return None

    def wait_for_toolbar(self, key):
        self.wait_until(lambda: self.toolbar_by_key(key) is not None, f"toolbar {key}")
        return self.toolbar_by_key(key)

    def activate_workbench(self, name, prefix=None):
        FreeCADGui.activateWorkbench(name)
        self.pump(350)
        if prefix:
            self.wait_until(
                lambda: len(self.toolbars_for_prefix(prefix, active_only=True)) > 0,
                f"{name} toolbars with prefix {prefix}",
            )
        self.pump(250)

    def choose_toolbar(self, prefix, exclude=None):
        exclude = exclude or set()
        items = [
            toolbar
            for toolbar in self.toolbars_for_prefix(prefix, active_only=True)
            if self.toolbar_key(toolbar) not in exclude
        ]
        self.assertTrue(items, f"No active toolbar found for prefix {prefix}")
        return items[0]

    def record_toolbar_state(self, toolbar, workbench, context=None):
        key = self.toolbar_key(toolbar)
        if key in self._modified_toolbars:
            return key

        self._modified_toolbars[key] = {
            "workbench": workbench,
            "context": context,
            "presentation": self.toolbar_view_presentation(toolbar),
            "area": (
                self.toolbar_area_value(self.toolbar_host_window(toolbar).toolBarArea(toolbar))
                if self.toolbar_view_presentation(toolbar) == "docked"
                else None
            ),
            "visible": toolbar.isVisible(),
        }
        return key

    def restore_toolbar_state(self, key, state):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist during restore")
        if state.get("presentation") == "docked" and state.get("area") is not None:
            toolbar.show()
            self.toolbar_host_window(toolbar).addToolBar(
                self.toolbar_area_enum(state["area"]), toolbar
            )
            self.pump(200)
        if state["visible"]:
            toolbar.show()
        else:
            toolbar.hide()
        self.pump(150)

    def move_toolbar(self, key, area):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        toolbar.show()
        host_window = self.toolbar_host_window(toolbar)
        host_window.addToolBar(area, toolbar)
        self.pump(250)
        actual_area = host_window.toolBarArea(toolbar)
        self.assertEqual(
            self.toolbar_area_value(actual_area),
            self.toolbar_area_value(area),
            f"Toolbar {key} should be in area {self.toolbar_area_value(area)}",
        )

    def show_toolbar(self, key):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        toolbar.show()
        self.pump(200)

    def hide_toolbar(self, key):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        toolbar.hide()
        self.pump(200)
        self.assertFalse(toolbar.isVisible(), f"Toolbar {key} should be hidden")

    def assert_toolbar_area(self, key, expected_area):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        actual_area = self.toolbar_host_window(toolbar).toolBarArea(toolbar)
        self.assertEqual(
            self.toolbar_area_value(actual_area),
            self.toolbar_area_value(expected_area),
            f"Toolbar {key} should restore to area {self.toolbar_area_value(expected_area)}",
        )

    def assert_toolbar_visibility(self, key, expected_visible):
        toolbar = self.wait_for_toolbar(key)
        self.assertIsNotNone(toolbar, f"Expected toolbar {key} to exist")
        self.wait_until(
            lambda: toolbar.toggleViewAction().isVisible(),
            f"toolbar {key} to become active",
        )
        self.wait_until(
            lambda: toolbar.isVisible() == expected_visible,
            f"toolbar {key} visibility to become {expected_visible}",
        )

    def enter_sketch_edit(self):
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        ok = FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        self.assertTrue(ok, "Failed to enter Sketcher edit mode")
        self.wait_until(
            lambda: len(self.toolbars_for_prefix("ctx:SketcherWorkbench:edit:", active_only=True))
            > 0,
            "Sketcher contextual edit toolbars",
            timeout_ms=8000,
        )

    def leave_sketch_edit(self):
        gui_doc = FreeCADGui.ActiveDocument
        if gui_doc is None:
            return
        gui_doc.resetEdit()
        self.wait_until(
            lambda: len(self.toolbars_for_prefix("ctx:SketcherWorkbench:edit:", active_only=True))
            == 0,
            "Sketcher contextual toolbars to hide",
            timeout_ms=8000,
        )
        self.pump(200)

    def _restore_toolbars(self):
        if not self._modified_toolbars:
            return

        restored_context = False
        try:
            for key, state in self._modified_toolbars.items():
                if state["context"] is not None:
                    continue
                self.activate_workbench(state["workbench"], f"wb:{state['workbench']}:")
                self.restore_toolbar_state(key, state)

            contextual = [
                (key, state)
                for key, state in self._modified_toolbars.items()
                if state["context"] == "edit"
            ]
            if contextual:
                self.enter_sketch_edit()
                restored_context = True
                for key, state in contextual:
                    self.restore_toolbar_state(key, state)
        finally:
            if restored_context:
                self.leave_sketch_edit()

    def test_toolbar_layout_persists_across_workbench_and_edit_switches(self):
        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        part_toolbar = self.choose_toolbar("wb:PartWorkbench:")
        part_key = self.record_toolbar_state(part_toolbar, "PartWorkbench")
        self.move_toolbar(part_key, QtCore.Qt.LeftToolBarArea)

        self.activate_workbench("PartDesignWorkbench", "wb:PartDesignWorkbench:")
        pd_toolbar = self.choose_toolbar("wb:PartDesignWorkbench:")
        pd_key = self.record_toolbar_state(pd_toolbar, "PartDesignWorkbench")
        self.move_toolbar(pd_key, QtCore.Qt.BottomToolBarArea)

        pd_hidden_toolbar = self.choose_toolbar(
            "wb:PartDesignWorkbench:",
            exclude={pd_key},
        )
        pd_hidden_key = self.record_toolbar_state(pd_hidden_toolbar, "PartDesignWorkbench")
        self.show_toolbar(pd_hidden_key)
        self.hide_toolbar(pd_hidden_key)

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        sketch_toolbar = self.choose_toolbar("wb:SketcherWorkbench:")
        sketch_key = self.record_toolbar_state(sketch_toolbar, "SketcherWorkbench")
        self.move_toolbar(sketch_key, QtCore.Qt.RightToolBarArea)

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.assert_toolbar_area(part_key, QtCore.Qt.LeftToolBarArea)

        self.activate_workbench("PartDesignWorkbench", "wb:PartDesignWorkbench:")
        self.assert_toolbar_area(pd_key, QtCore.Qt.BottomToolBarArea)
        self.assert_toolbar_visibility(pd_hidden_key, False)

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.assert_toolbar_area(sketch_key, QtCore.Qt.RightToolBarArea)

        self.enter_sketch_edit()
        edit_toolbar = self.choose_toolbar("ctx:SketcherWorkbench:edit:")
        edit_key = self.record_toolbar_state(
            edit_toolbar,
            "SketcherWorkbench",
            context="edit",
        )
        self.move_toolbar(edit_key, QtCore.Qt.LeftToolBarArea)

        edit_hidden_toolbar = self.choose_toolbar(
            "ctx:SketcherWorkbench:edit:",
            exclude={edit_key},
        )
        edit_hidden_key = self.record_toolbar_state(
            edit_hidden_toolbar,
            "SketcherWorkbench",
            context="edit",
        )
        self.show_toolbar(edit_hidden_key)
        self.hide_toolbar(edit_hidden_key)

        self.leave_sketch_edit()

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.assert_toolbar_area(sketch_key, QtCore.Qt.RightToolBarArea)

        self.enter_sketch_edit()
        self.assert_toolbar_area(edit_key, QtCore.Qt.LeftToolBarArea)
        self.assert_toolbar_visibility(edit_hidden_key, False)
        self.leave_sketch_edit()

    def test_unsaved_scope_falls_back_to_recommended_toolbars(self):
        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        scoped_keys = (
            "wb:SketcherWorkbench:Sketcher",
            "ctx:SketcherWorkbench:edit:Edit Mode",
            "ctx:SketcherWorkbench:edit:Geometries",
            "ctx:SketcherWorkbench:edit:Constraints",
            "ctx:SketcherWorkbench:edit:Sketcher Tools",
            "ctx:SketcherWorkbench:edit:B-Spline Tools",
            "ctx:SketcherWorkbench:edit:Visual Helpers",
        )
        for key in ("shared:View",) + scoped_keys:
            self.backup_bool_param(visibility_group, key)

        layout_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/WorkbenchLayouts")
        self.backup_group(
            layout_params,
            "SketcherWorkbench",
            "__ToolbarUnsavedScopeBackup__SketcherWorkbench",
        )
        self.backup_group(
            layout_params,
            "ctx:SketcherWorkbench:edit",
            "__ToolbarUnsavedScopeBackup__SketcherEdit",
        )

        visibility_group.SetBool("shared:View", True)
        for key in scoped_keys:
            visibility_group.SetBool(key, False)

        layout_params.RemGroup("SketcherWorkbench")
        layout_params.RemGroup("ctx:SketcherWorkbench:edit")

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.assert_toolbar_visibility("shared:View", True)
        self.assert_toolbar_visibility("wb:SketcherWorkbench:Sketcher", True)

        self.enter_sketch_edit()
        self.assert_toolbar_visibility("shared:View", True)
        self.assert_toolbar_visibility("ctx:SketcherWorkbench:edit:Geometries", True)
        self.leave_sketch_edit()

    def test_custom_toolbar_tier_is_loaded_from_preferences(self):
        workbench_params = FreeCAD.ParamGet("User parameter:BaseApp/Workbench")
        self.backup_group(
            workbench_params,
            "SketcherWorkbench",
            "__ToolbarCustomTierBackup__SketcherWorkbench",
        )

        toolbar_group = workbench_params.GetGroup("SketcherWorkbench").GetGroup("Toolbar")
        toolbar_group.Clear()
        custom_toolbar = toolbar_group.GetGroup("Custom_1")
        custom_toolbar.SetString("Name", "Custom Tier Test")
        custom_toolbar.SetBool("Active", True)
        custom_toolbar.SetString("Tier", "advanced")
        custom_toolbar.SetString("Std_Undo", "Gui")

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")

        toolbar = self.wait_for_toolbar("wb:SketcherWorkbench:Custom Tier Test")
        self.assertEqual(self.toolbar_tier(toolbar), "advanced")

    def test_view_hosted_toolbar_uses_active_view_host(self):
        view_toolbar_label = QtGui.QApplication.translate("MainWindow", "View Toolbars")

        toolbar = self.wait_for_toolbar("shared:Individual Views")
        self.assertEqual(self.toolbar_host(toolbar), "view")

        self.show_toolbar("shared:Individual Views")
        active_view = self.active_mdi_view()
        self.assertIs(
            toolbar.parentWidget(),
            active_view,
            "Individual Views toolbar should be hosted inside the active view",
        )
        self.assertEqual(
            self.toolbar_area_value(active_view.toolBarArea(toolbar)),
            self.toolbar_area_value(QtCore.Qt.TopToolBarArea),
            "View-hosted toolbars should default to the top area of the active view",
        )

        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertIn(view_toolbar_label, sections, "Toolbar menu should expose view toolbar group")
        self.assertIn(
            self.toolbar_menu_label(toolbar),
            texts,
            "Toolbar menu should expose the view-hosted toolbar entry",
        )

    def test_view_navigation_toolbar_uses_centered_overlay_host(self):
        key = "shared:View Navigation"
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")

        self.assertEqual(self.toolbar_host(toolbar), "view")
        self.assertEqual(self.toolbar_view_presentation(toolbar), "centered-overlay")
        self.assertEqual(self.toolbar_view_overlay_edge(toolbar), "top")

        self.show_toolbar(key)
        active_view = self.active_mdi_view()
        overlay_anchor = self.toolbar_overlay_anchor(toolbar)
        overlay_lane = self.toolbar_overlay_lane(toolbar)
        self.assertIsNotNone(overlay_anchor, "View Navigation should use an overlay anchor")
        self.assertIsNotNone(overlay_lane, "View Navigation should use an overlay lane")
        self.assertIs(
            overlay_anchor,
            active_view.centralWidget(),
            "View Navigation should overlay the active view content",
        )
        self.assertEqual(
            str(overlay_lane.property("overlayRole")),
            "view-toolbar-lane",
            "View Navigation overlay lane should expose a stable theming role",
        )
        self.assertTrue(
            overlay_lane.property("panelColor").isValid(),
            "View Navigation overlay lane should expose themed panel color properties",
        )
        self.assertNotEqual(
            overlay_lane.property("panelColor"),
            QtGui.QColor.fromRgb(25, 25, 25, 220),
            "View Navigation overlay lane should not fall back to the hardcoded default panel color",
        )
        self.assertEqual(
            self.toolbar_area_value(active_view.toolBarArea(toolbar)),
            self.toolbar_area_value(QtCore.Qt.NoToolBarArea),
            "View Navigation should not be registered as a docked view toolbar",
        )

        lane_center = overlay_lane.geometry().center().x()
        anchor_center = overlay_anchor.rect().center().x()
        self.assertLessEqual(
            abs(lane_center - anchor_center),
            4,
            "View Navigation overlay should be centered on the active view",
        )
        self.assertGreaterEqual(
            overlay_lane.geometry().y(),
            0,
            "View Navigation overlay should remain inside the active view bounds",
        )

    def test_view_toolbar_menu_exposes_hidden_compatible_toolbar(self):
        individual_views_key = "shared:Individual Views"
        view_navigation_key = "shared:View Navigation"
        view_toolbar_label = QtGui.QApplication.translate("MainWindow", "View Toolbars")
        show_label = QtGui.QApplication.translate("MainWindow", "Show")
        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        self.backup_bool_param(visibility_group, individual_views_key)
        self.backup_bool_param(visibility_group, view_navigation_key)
        visibility_group.SetBool(individual_views_key, False)
        visibility_group.SetBool(view_navigation_key, False)

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        individual_views_toolbar = self.wait_for_toolbar(individual_views_key)
        view_navigation_toolbar = self.wait_for_toolbar(view_navigation_key)
        individual_views_toolbar.hide()
        view_navigation_toolbar.hide()
        self.pump(200)
        self.assertFalse(
            individual_views_toolbar.isVisible(),
            "Individual Views toolbar should remain hidden in this test",
        )
        self.assertFalse(
            view_navigation_toolbar.isVisible(),
            "View Navigation toolbar should remain hidden in this test",
        )

        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertIn(
            view_toolbar_label,
            sections,
            "Toolbar menu should expose the view toolbar group for compatible 3D views",
        )
        self.assertIn(
            self.toolbar_menu_label(individual_views_toolbar),
            texts,
            "Toolbar menu should expose hidden compatible Individual Views toolbar",
        )
        self.assertIn(
            self.toolbar_menu_label(view_navigation_toolbar),
            texts,
            "Toolbar menu should expose the View Navigation submenu",
        )
        menu = self.prepare_popup_menu(self.toolbar_menu())
        view_navigation_menu = self.find_menu_submenu(
            menu, self.toolbar_menu_label(view_navigation_toolbar)
        )
        self.assertIsNotNone(view_navigation_menu, "Expected View Navigation submenu to exist")
        show_action = self.find_menu_action(view_navigation_menu, show_label)
        self.assertIsNotNone(show_action, "Expected View Navigation show action to exist")
        self.assertTrue(
            show_action.isEnabled(),
            "Toolbar menu should enable compatible View Navigation toolbar",
        )

        self.trigger_menu_path(
            self.toolbar_menu(), self.toolbar_menu_label(view_navigation_toolbar), show_label
        )
        self.wait_until(
            lambda: view_navigation_toolbar.isVisible(),
            "view-hosted View Navigation menu action to show the toolbar",
        )
        self.pump(250)
        self.assertTrue(
            view_navigation_toolbar.isVisible(),
            "View Navigation toolbar should remain visible after the delayed refresh path runs",
        )
        self.assertTrue(
            visibility_group.GetBool(view_navigation_key),
            "View Navigation toolbar menu action should persist the shown state",
        )

    def test_regular_toolbar_can_move_into_view_host(self):
        key = "shared:Clipboard"
        move_to_label = QtGui.QApplication.translate("MainWindow", "Move To")
        main_window_label = QtGui.QApplication.translate("MainWindow", "Main Window")
        view_label = QtGui.QApplication.translate("MainWindow", "View")
        presentation_label = QtGui.QApplication.translate("MainWindow", "Presentation")
        centered_overlay_label = QtGui.QApplication.translate("MainWindow", "Centered Overlay")

        params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow")
        host_group_name = "HostedToolbarHosts"
        host_backup_name = "TestToolbarPersistenceGuiBackupHostedToolbarHosts"
        presentation_group_name = "ViewToolbarPresentations"
        presentation_backup_name = "TestToolbarPersistenceGuiBackupViewToolbarPresentations"
        had_host_group = params.HasGroup(host_group_name)
        had_presentation_group = params.HasGroup(presentation_group_name)
        params.RemGroup(host_backup_name)
        params.RemGroup(presentation_backup_name)
        if had_host_group:
            params.GetGroup(host_group_name).CopyTo(params.GetGroup(host_backup_name))
        if had_presentation_group:
            params.GetGroup(presentation_group_name).CopyTo(
                params.GetGroup(presentation_backup_name)
            )

        toolbar = None
        try:
            self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
            toolbar = self.wait_for_toolbar(key)
            self.assertEqual(self.toolbar_host(toolbar), "main-window")

            self.trigger_menu_path(
                self.toolbar_menu(), self.toolbar_menu_label(toolbar), move_to_label, view_label
            )
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "view",
                "shared toolbar host to change to the active view",
            )
            toolbar = self.wait_for_toolbar(key)
            self.assertIs(
                toolbar.parentWidget(),
                self.active_mdi_view(),
                "Regular toolbar should dock into the active view after moving it there",
            )

            self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "view",
                "shared toolbar host to stay view in Part",
            )

            self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
            toolbar = self.wait_for_toolbar(key)
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "view",
                "shared toolbar host to persist across workbench switches",
            )

            self.trigger_menu_path(
                self.toolbar_menu(),
                self.toolbar_menu_label(toolbar),
                presentation_label,
                centered_overlay_label,
            )
            self.wait_until(
                lambda: self.toolbar_view_presentation(self.wait_for_toolbar(key))
                == "centered-overlay",
                "regular toolbar presentation to change to centered overlay",
            )
            self.show_toolbar(key)
            toolbar = self.wait_for_toolbar(key)
            self.assertIsNotNone(
                self.toolbar_overlay_anchor(toolbar),
                "Regular toolbar should use the overlay host after choosing centered overlay",
            )

            self.trigger_menu_path(
                self.toolbar_menu(),
                self.toolbar_menu_label(toolbar),
                move_to_label,
                main_window_label,
            )
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "main-window",
                "regular toolbar host to move back to the main window",
            )
            toolbar = self.wait_for_toolbar(key)
            self.assertIs(
                toolbar.parentWidget(),
                self.main_window(),
                "Regular toolbar should return to the main window host",
            )
        finally:
            params.RemGroup(host_group_name)
            params.RemGroup(presentation_group_name)
            if had_host_group:
                params.GetGroup(host_backup_name).CopyTo(params.GetGroup(host_group_name))
            if had_presentation_group:
                params.GetGroup(presentation_backup_name).CopyTo(
                    params.GetGroup(presentation_group_name)
                )
            params.RemGroup(host_backup_name)
            params.RemGroup(presentation_backup_name)

    def test_panel_toolbar_menu_exposes_hidden_model_tree_toolbar(self):
        key = "shared:Tree Controls"
        panel_label = QtGui.QApplication.translate("MainWindow", "Panel Toolbars")

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        tree_controls = self.wait_for_toolbar(key)

        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertIn(panel_label, sections, "Toolbar menu should expose panel toolbar group")
        self.assertIn(
            self.toolbar_menu_label(tree_controls),
            texts,
            "Toolbar menu should expose hidden model-tree toolbar entries",
        )

        self.show_toolbar(key)
        self.assertEqual(self.toolbar_host(tree_controls), "panel")
        self.assertEqual(self.toolbar_panel_role(tree_controls), "model-tree")
        self.assert_toolbar_panel_host(key)

    def test_regular_toolbar_can_move_into_model_tree_host(self):
        key = "shared:Structure"
        move_to_label = QtGui.QApplication.translate("MainWindow", "Move To")
        main_window_label = QtGui.QApplication.translate("MainWindow", "Main Window")
        model_tree_label = QtGui.QApplication.translate("MainWindow", "Model Tree")

        params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow")
        host_group_name = "HostedToolbarHosts"
        host_backup_name = "TestToolbarPersistenceGuiBackupHostedToolbarHosts"
        had_host_group = params.HasGroup(host_group_name)
        params.RemGroup(host_backup_name)
        if had_host_group:
            params.GetGroup(host_group_name).CopyTo(params.GetGroup(host_backup_name))

        try:
            self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
            toolbar = self.wait_for_toolbar(key)
            self.assertEqual(self.toolbar_host(toolbar), "main-window")
            self.assertEqual(self.toolbar_panel_role(toolbar), "model-tree")

            self.trigger_menu_path(
                self.toolbar_menu(),
                self.toolbar_menu_label(toolbar),
                move_to_label,
                model_tree_label,
            )
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "panel",
                "shared toolbar host to change to the model tree",
            )
            self.assert_toolbar_panel_host(key)

            self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "panel",
                "shared toolbar host to stay panel in Part",
            )
            self.assert_toolbar_panel_host(key)

            self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "panel",
                "shared toolbar host to persist across workbench switches",
            )
            self.assert_toolbar_panel_host(key)

            self.trigger_menu_path(
                self.toolbar_menu(),
                self.toolbar_menu_label(self.wait_for_toolbar(key)),
                move_to_label,
                main_window_label,
            )
            self.wait_until(
                lambda: self.toolbar_host(self.wait_for_toolbar(key)) == "main-window",
                "shared toolbar host to move back to the main window",
            )
            toolbar = self.wait_for_toolbar(key)
            self.assertIs(
                toolbar.parentWidget(),
                self.main_window(),
                "Regular toolbar should return to the main window host",
            )
        finally:
            params.RemGroup(host_group_name)
            if had_host_group:
                params.GetGroup(host_backup_name).CopyTo(params.GetGroup(host_group_name))
            params.RemGroup(host_backup_name)
            self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")

    def test_view_context_menu_exposes_view_toolbar_submenu(self):
        individual_views_key = "shared:Individual Views"
        view_navigation_key = "shared:View Navigation"
        view_toolbar_label = QtGui.QApplication.translate("MainWindow", "View Toolbars")
        show_label = QtGui.QApplication.translate("MainWindow", "Show")
        position_label = QtGui.QApplication.translate("MainWindow", "Position")
        reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current View Toolbar Layout"
        )
        recommended_reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended View Toolbar Layout"
        )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        individual_views_toolbar = self.wait_for_toolbar(individual_views_key)
        view_navigation_toolbar = self.wait_for_toolbar(view_navigation_key)
        self.record_toolbar_state(individual_views_toolbar, "SketcherWorkbench")
        self.record_toolbar_state(view_navigation_toolbar, "SketcherWorkbench")
        individual_views_toolbar.hide()
        view_navigation_toolbar.hide()
        self.pump(200)

        popup = self.open_active_view_context_menu()
        self.assertIn(
            view_toolbar_label,
            self.menu_action_texts(popup),
            "3D view context menu should expose the view toolbar submenu",
        )

        submenu = None
        for action in popup.actions():
            if self.normalized_action_text(action) == view_toolbar_label:
                submenu = action.menu()
                break

        self.assertIsNotNone(submenu, "Expected the view toolbar submenu to exist")
        submenu_texts = self.menu_action_texts(submenu)
        self.assertIn(
            self.toolbar_menu_label(individual_views_toolbar),
            submenu_texts,
            "3D view context submenu should expose the Individual Views toolbar",
        )
        self.assertIn(
            self.toolbar_menu_label(view_navigation_toolbar),
            submenu_texts,
            "3D view context submenu should expose the View Navigation submenu",
        )
        view_navigation_menu = self.find_menu_submenu(
            submenu, self.toolbar_menu_label(view_navigation_toolbar)
        )
        self.assertIsNotNone(view_navigation_menu, "Expected the View Navigation submenu")
        self.assertIn(
            show_label,
            self.menu_action_texts(view_navigation_menu),
            "View Navigation submenu should expose a show action",
        )
        self.assertIn(
            position_label,
            self.menu_action_texts(view_navigation_menu),
            "View Navigation submenu should expose a position submenu",
        )
        self.assertIn(
            reset_view_label,
            submenu_texts,
            "3D view context submenu should expose the current view layout reset action",
        )
        self.assertIn(
            recommended_reset_view_label,
            submenu_texts,
            "3D view context submenu should expose the recommended view layout reset action",
        )
        popup.hide()

    def test_overlay_toolbar_context_menu_exposes_overlay_options(self):
        key = "shared:View Navigation"
        show_label = QtGui.QApplication.translate("MainWindow", "Show")
        move_to_label = QtGui.QApplication.translate("MainWindow", "Move To")
        presentation_label = QtGui.QApplication.translate("MainWindow", "Presentation")
        position_label = QtGui.QApplication.translate("MainWindow", "Position")
        reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current View Toolbar Layout"
        )
        bottom_label = QtGui.QApplication.translate("MainWindow", "Bottom")

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar(key)

        popup = self.open_toolbar_context_menu(toolbar)
        texts = self.menu_action_texts(popup)
        self.assertIn(show_label, texts, "Overlay toolbar context menu should expose show toggle")
        self.assertIn(
            move_to_label, texts, "Overlay toolbar context menu should expose host options"
        )
        self.assertIn(
            presentation_label,
            texts,
            "Overlay toolbar context menu should expose presentation options",
        )
        self.assertIn(
            position_label, texts, "Overlay toolbar context menu should expose position options"
        )
        self.assertIn(
            reset_view_label,
            texts,
            "Overlay toolbar context menu should expose the current view reset action",
        )

        self.trigger_menu_path(popup, position_label, bottom_label)
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "bottom",
            "overlay toolbar context menu to move the overlay to bottom",
        )

    def test_view_hosted_toolbar_layout_restores_in_active_view(self):
        key = "shared:Individual Views"
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")

        self.show_toolbar(key)
        target_area = self.alternative_toolbar_area(toolbar)
        self.move_toolbar(key, target_area)

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")

        restored_toolbar = self.wait_for_toolbar(key)
        self.assertIs(
            restored_toolbar.parentWidget(),
            self.active_mdi_view(),
            "View-hosted toolbar should restore into the active view",
        )
        self.assert_toolbar_visibility(key, True)
        self.assert_toolbar_area(key, target_area)

    def test_view_hosted_toolbar_follows_active_view_switches(self):
        key = "shared:Individual Views"

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        original_view = self.active_mdi_view()
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar(key)

        target_area = self.alternative_toolbar_area(toolbar)
        self.move_toolbar(key, target_area)

        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.activate_mdi_view(original_view)

        extra_view = self.create_additional_view("Toolbar Host Test")
        self.activate_mdi_view(extra_view)
        self.wait_until(
            lambda: self.wait_for_toolbar(key).parentWidget() is extra_view,
            "view-hosted toolbar to move to the secondary view",
        )
        self.assert_toolbar_area(key, target_area)

    def test_view_navigation_overlay_follows_active_view_switches(self):
        key = "shared:View Navigation"

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        original_view = self.active_mdi_view()
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar(key)

        original_anchor = self.toolbar_overlay_anchor(toolbar)
        self.assertIs(
            original_anchor,
            original_view.centralWidget(),
            "View Navigation should start on the original active view",
        )

        extra_view = self.create_additional_view("Overlay Toolbar Host Test")
        self.activate_mdi_view(extra_view)
        self.wait_until(
            lambda: self.toolbar_overlay_anchor(self.wait_for_toolbar(key))
            is extra_view.centralWidget(),
            "View Navigation overlay to move to the secondary view",
        )

        self.activate_mdi_view(original_view)
        self.wait_until(
            lambda: self.toolbar_overlay_anchor(self.wait_for_toolbar(key))
            is original_view.centralWidget(),
            "View Navigation overlay to return to the original view",
        )

        self.activate_mdi_view(original_view)
        self.wait_until(
            lambda: self.wait_for_toolbar(key).parentWidget() is original_view,
            "view-hosted toolbar to return to the original view",
        )
        self.assert_toolbar_area(key, target_area)

    def test_view_navigation_overlay_position_persists(self):
        key = "shared:View Navigation"
        position_label = QtGui.QApplication.translate("MainWindow", "Position")
        top_label = QtGui.QApplication.translate("MainWindow", "Top")
        bottom_label = QtGui.QApplication.translate("MainWindow", "Bottom")
        overlay_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow")
        self.backup_group(
            overlay_params,
            "ViewOverlayEdges",
            "TestToolbarPersistenceGuiBackupViewOverlayEdges",
        )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar(key)

        original_y = self.toolbar_overlay_lane(toolbar).geometry().y()
        self.assertEqual(self.toolbar_view_overlay_edge(toolbar), "top")

        self.trigger_menu_path(
            self.toolbar_menu(),
            self.toolbar_menu_label(toolbar),
            position_label,
            bottom_label,
        )
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "bottom",
            "View Navigation overlay edge to change to bottom",
        )
        self.wait_until(
            lambda: self.toolbar_overlay_lane(self.wait_for_toolbar(key)).geometry().y()
            > original_y,
            "View Navigation overlay to move to the bottom edge",
        )

        self.activate_workbench("PartDesignWorkbench", "wb:PartDesignWorkbench:")
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "bottom",
            "View Navigation overlay edge to stay bottom in PartDesign",
        )
        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "bottom",
            "View Navigation overlay edge to stay bottom in Part",
        )
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "bottom",
            "View Navigation overlay edge to persist across workbench switches",
        )

        self.trigger_menu_path(
            self.toolbar_menu(),
            self.toolbar_menu_label(self.wait_for_toolbar(key)),
            position_label,
            top_label,
        )
        self.wait_until(
            lambda: self.toolbar_view_overlay_edge(self.wait_for_toolbar(key)) == "top",
            "View Navigation overlay edge to change back to top",
        )

    def test_view_hosted_toolbar_is_unavailable_outside_3d_views(self):
        key = "shared:Individual Views"
        view_toolbar_label = QtGui.QApplication.translate("MainWindow", "View Toolbars")

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        original_view = self.active_mdi_view()
        toolbar = self.wait_for_toolbar(key)
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar(key)

        text_view = self.create_text_document_view()
        self.activate_mdi_view(text_view)

        self.wait_until(
            lambda: not toolbar.toggleViewAction().isVisible(),
            "view-hosted toolbar action to hide in text document view",
        )
        self.assertIsNot(
            toolbar.parentWidget(),
            text_view,
            "View-hosted toolbar should not reparent into unsupported text views",
        )

        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertNotIn(
            view_toolbar_label,
            sections,
            "Toolbar menu should hide the view section when the active view cannot host it",
        )
        self.assertNotIn(
            self.toolbar_menu_label(toolbar),
            texts,
            "Toolbar menu should not expose view-hosted toolbar entries in unsupported views",
        )

        self.activate_mdi_view(original_view)
        self.wait_until(
            lambda: toolbar.toggleViewAction().isVisible()
            and toolbar.parentWidget() is original_view,
            "view-hosted toolbar to return when switching back to a 3D view",
        )

    def test_toolbar_menu_groups_and_reset_actions(self):
        view_label = QtGui.QApplication.translate("MainWindow", "View Toolbars")
        panel_label = QtGui.QApplication.translate("MainWindow", "Panel Toolbars")
        shared_label = QtGui.QApplication.translate("MainWindow", "Shared Toolbars")
        workbench_label = QtGui.QApplication.translate("MainWindow", "Workbench Toolbars")
        contextual_label = QtGui.QApplication.translate("MainWindow", "Contextual Toolbars")
        reset_workbench_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current Workbench Layout"
        )
        reset_contextual_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current Contextual Layout"
        )
        show_recommended_only_label = QtGui.QApplication.translate(
            "MainWindow", "Show Recommended Only"
        )
        recommended_reset_workbench_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended Workbench Layout"
        )
        recommended_reset_contextual_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended Contextual Layout"
        )
        reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current View Toolbar Layout"
        )
        recommended_reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended View Toolbar Layout"
        )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        sketcher_toolbar_label = self.toolbar_menu_label(
            self.wait_for_toolbar("wb:SketcherWorkbench:Sketcher")
        )
        clipboard_toolbar_label = self.toolbar_menu_label(self.wait_for_toolbar("shared:Clipboard"))
        macro_toolbar_label = self.toolbar_menu_label(self.wait_for_toolbar("shared:Macro"))
        view_navigation_toolbar_label = self.toolbar_menu_label(
            self.wait_for_toolbar("shared:View Navigation")
        )
        tree_controls_toolbar_label = self.toolbar_menu_label(
            self.wait_for_toolbar("shared:Tree Controls")
        )

        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertIn(view_label, sections, "Main toolbar menu should expose view toolbar group")
        self.assertIn(panel_label, sections, "Main toolbar menu should expose panel toolbar group")
        self.assertIn(
            shared_label, sections, "Main toolbar menu should expose shared toolbar group"
        )
        self.assertIn(
            workbench_label,
            sections,
            "Main toolbar menu should expose workbench toolbar group in workbench mode",
        )
        self.assertIn(
            sketcher_toolbar_label,
            texts,
            "Main toolbar menu should expose recommended tier label for workbench toolbars",
        )
        self.assertIn(
            clipboard_toolbar_label,
            texts,
            "Main toolbar menu should expose secondary tier label for shared toolbars",
        )
        self.assertIn(
            macro_toolbar_label,
            texts,
            "Main toolbar menu should expose advanced tier label for shared toolbars",
        )
        self.assertIn(
            view_navigation_toolbar_label,
            texts,
            "Main toolbar menu should expose the View Navigation view toolbar entry",
        )
        self.assertIn(
            tree_controls_toolbar_label,
            texts,
            "Main toolbar menu should expose the Tree Controls panel toolbar entry",
        )
        self.assertIn(
            show_recommended_only_label,
            texts,
            "Main toolbar menu should expose show recommended only action in workbench mode",
        )
        self.assertIn(
            reset_workbench_label,
            texts,
            "Main toolbar menu should expose workbench layout reset in workbench mode",
        )
        self.assertIn(
            recommended_reset_workbench_label,
            texts,
            "Main toolbar menu should expose recommended workbench reset in workbench mode",
        )
        self.assertIn(
            reset_view_label,
            texts,
            "Main toolbar menu should expose view layout reset in workbench mode",
        )
        self.assertIn(
            recommended_reset_view_label,
            texts,
            "Main toolbar menu should expose recommended view reset in workbench mode",
        )

        self.enter_sketch_edit()
        contextual_toolbar_label = self.toolbar_menu_label(
            self.wait_for_toolbar("ctx:SketcherWorkbench:edit:Geometries")
        )
        sections, texts = self.capture_popup_menu(self.toolbar_menu())
        self.assertIn(shared_label, sections, "Main toolbar menu should keep shared toolbar group")
        self.assertIn(
            contextual_label,
            sections,
            "Main toolbar menu should expose contextual toolbar group during edit mode",
        )
        self.assertIn(
            contextual_toolbar_label,
            texts,
            "Main toolbar menu should expose contextual tier label during edit mode",
        )
        self.assertIn(
            show_recommended_only_label,
            texts,
            "Main toolbar menu should expose show recommended only action during edit mode",
        )
        self.assertIn(
            reset_contextual_label,
            texts,
            "Main toolbar menu should expose contextual layout reset during edit mode",
        )
        self.assertIn(
            recommended_reset_contextual_label,
            texts,
            "Main toolbar menu should expose recommended contextual reset during edit mode",
        )
        self.assertIn(
            reset_view_label,
            texts,
            "Main toolbar menu should expose view layout reset during edit mode",
        )
        self.assertIn(
            recommended_reset_view_label,
            texts,
            "Main toolbar menu should expose recommended view reset during edit mode",
        )

        self.leave_sketch_edit()
        _, texts = self.capture_status_bar_context_menu()
        self.assertIn(
            reset_workbench_label,
            texts,
            "Workbench runtime context menu should expose workbench layout reset",
        )
        self.assertNotIn(
            reset_contextual_label,
            texts,
            "Workbench runtime context menu should not expose contextual reset outside edit mode",
        )
        self.assertIn(
            recommended_reset_workbench_label,
            texts,
            "Workbench runtime context menu should expose recommended workbench reset",
        )
        self.assertIn(
            show_recommended_only_label,
            texts,
            "Workbench runtime context menu should expose show recommended only action",
        )
        self.assertIn(
            reset_view_label,
            texts,
            "Workbench runtime context menu should expose view layout reset",
        )
        self.assertIn(
            recommended_reset_view_label,
            texts,
            "Workbench runtime context menu should expose recommended view reset",
        )
        self.assertNotIn(
            recommended_reset_contextual_label,
            texts,
            "Workbench runtime context menu should not expose recommended contextual reset outside edit mode",
        )

        self.enter_sketch_edit()
        _, texts = self.capture_status_bar_context_menu()
        self.assertIn(
            reset_contextual_label,
            texts,
            "Contextual runtime context menu should expose contextual layout reset",
        )
        self.assertNotIn(
            reset_workbench_label,
            texts,
            "Contextual runtime context menu should not expose workbench reset label",
        )
        self.assertIn(
            recommended_reset_contextual_label,
            texts,
            "Contextual runtime context menu should expose recommended contextual reset",
        )
        self.assertIn(
            show_recommended_only_label,
            texts,
            "Contextual runtime context menu should expose show recommended only action",
        )
        self.assertIn(
            reset_view_label,
            texts,
            "Contextual runtime context menu should expose view layout reset",
        )
        self.assertIn(
            recommended_reset_view_label,
            texts,
            "Contextual runtime context menu should expose recommended view reset",
        )
        self.assertNotIn(
            recommended_reset_workbench_label,
            texts,
            "Contextual runtime context menu should not expose recommended workbench reset",
        )
        self.leave_sketch_edit()

    def test_toolbar_tier_metadata_is_exposed(self):
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")

        self.assertEqual(
            self.toolbar_tier(self.wait_for_toolbar("wb:SketcherWorkbench:Sketcher")),
            "recommended",
        )
        self.assertEqual(
            self.toolbar_tier(self.wait_for_toolbar("shared:Clipboard")),
            "secondary",
        )
        self.assertEqual(
            self.toolbar_tier(self.wait_for_toolbar("shared:Macro")),
            "advanced",
        )

        self.enter_sketch_edit()
        self.assertEqual(
            self.toolbar_tier(self.wait_for_toolbar("ctx:SketcherWorkbench:edit:Geometries")),
            "contextual",
        )
        self.leave_sketch_edit()

    def test_recommended_toolbar_reset_restores_tier_defaults(self):
        recommended_reset_workbench_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended Workbench Layout"
        )
        recommended_reset_contextual_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended Contextual Layout"
        )

        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        for key in (
            "shared:View",
            "shared:Clipboard",
            "shared:Macro",
            "ctx:SketcherWorkbench:edit:Geometries",
        ):
            self.backup_bool_param(visibility_group, key)

        layout_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/WorkbenchLayouts")
        self.backup_group(
            layout_params,
            "SketcherWorkbench",
            "__ToolbarRecommendedResetBackup__SketcherWorkbench",
        )
        self.backup_group(
            layout_params,
            "ctx:SketcherWorkbench:edit",
            "__ToolbarRecommendedResetBackup__SketcherEdit",
        )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        for key in ("shared:View", "shared:Clipboard", "shared:Macro"):
            self.record_toolbar_state(self.wait_for_toolbar(key), "SketcherWorkbench")

        self.show_toolbar("shared:Clipboard")
        self.show_toolbar("shared:Macro")
        self.hide_toolbar("shared:View")

        self.trigger_menu_action(self.toolbar_menu(), recommended_reset_workbench_label)
        self.assert_toolbar_visibility("shared:View", True)
        self.assert_toolbar_visibility("shared:Clipboard", False)
        self.assert_toolbar_visibility("shared:Macro", False)

        self.enter_sketch_edit()
        self.record_toolbar_state(
            self.wait_for_toolbar("ctx:SketcherWorkbench:edit:Geometries"),
            "SketcherWorkbench",
            context="edit",
        )
        self.hide_toolbar("ctx:SketcherWorkbench:edit:Geometries")

        self.trigger_menu_action(self.toolbar_menu(), recommended_reset_contextual_label)
        self.assert_toolbar_visibility("ctx:SketcherWorkbench:edit:Geometries", True)
        self.leave_sketch_edit()

    def test_show_recommended_only_preserves_layout(self):
        show_recommended_only_label = QtGui.QApplication.translate(
            "MainWindow", "Show Recommended Only"
        )

        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        for key in (
            "shared:View",
            "shared:Clipboard",
            "shared:Macro",
            "ctx:SketcherWorkbench:edit:Geometries",
        ):
            self.backup_bool_param(visibility_group, key)

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")

        view_toolbar = self.wait_for_toolbar("shared:View")
        self.record_toolbar_state(view_toolbar, "SketcherWorkbench")
        self.move_toolbar("shared:View", QtCore.Qt.RightToolBarArea)

        for key in ("shared:Clipboard", "shared:Macro"):
            self.record_toolbar_state(self.wait_for_toolbar(key), "SketcherWorkbench")

        self.show_toolbar("shared:Clipboard")
        self.show_toolbar("shared:Macro")
        self.hide_toolbar("shared:View")

        self.trigger_menu_action(self.toolbar_menu(), show_recommended_only_label)
        self.assert_toolbar_visibility("shared:View", True)
        self.assert_toolbar_visibility("shared:Clipboard", False)
        self.assert_toolbar_visibility("shared:Macro", False)
        self.assert_toolbar_area("shared:View", QtCore.Qt.RightToolBarArea)

        self.enter_sketch_edit()
        contextual_key = "ctx:SketcherWorkbench:edit:Geometries"
        self.record_toolbar_state(
            self.wait_for_toolbar(contextual_key),
            "SketcherWorkbench",
            context="edit",
        )
        self.move_toolbar(contextual_key, QtCore.Qt.LeftToolBarArea)
        self.hide_toolbar(contextual_key)

        self.trigger_menu_action(self.toolbar_menu(), show_recommended_only_label)
        self.assert_toolbar_visibility(contextual_key, True)
        self.assert_toolbar_area(contextual_key, QtCore.Qt.LeftToolBarArea)
        self.leave_sketch_edit()

    def test_view_toolbar_reset_actions_restore_default_layout(self):
        reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset Current View Toolbar Layout"
        )
        recommended_reset_view_label = QtGui.QApplication.translate(
            "MainWindow", "Reset To Recommended View Toolbar Layout"
        )

        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        self.backup_bool_param(visibility_group, "shared:Individual Views")

        layout_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/WorkbenchLayouts")
        self.backup_group(
            layout_params,
            "SketcherWorkbench",
            "__ToolbarViewResetBackup__SketcherWorkbench",
        )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        toolbar = self.wait_for_toolbar("shared:Individual Views")
        self.record_toolbar_state(toolbar, "SketcherWorkbench")
        self.show_toolbar("shared:Individual Views")
        self.move_toolbar("shared:Individual Views", self.alternative_toolbar_area(toolbar))
        self.hide_toolbar("shared:Individual Views")

        self.trigger_menu_action(self.toolbar_menu(), reset_view_label)
        self.assert_toolbar_area("shared:Individual Views", QtCore.Qt.TopToolBarArea)
        self.assert_toolbar_visibility("shared:Individual Views", False)

        self.move_toolbar("shared:Individual Views", QtCore.Qt.LeftToolBarArea)
        self.hide_toolbar("shared:Individual Views")
        self.trigger_menu_action(self.toolbar_menu(), recommended_reset_view_label)
        self.assert_toolbar_area("shared:Individual Views", QtCore.Qt.TopToolBarArea)
        self.assert_toolbar_visibility("shared:Individual Views", True)

    def test_legacy_toolbar_names_restore_with_scoped_keys(self):
        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        toolbar = self.wait_for_toolbar("wb:SketcherWorkbench:Sketcher")
        key = self.record_toolbar_state(toolbar, "SketcherWorkbench")
        legacy_name = str(toolbar.objectName())
        self.assertNotEqual(key, legacy_name, "Test requires a scoped toolbar persistence key")

        target_area = self.alternative_toolbar_area(toolbar)
        target_area_name = self.toolbar_area_name(target_area)
        self.activate_workbench("PartWorkbench", "wb:PartWorkbench:")

        visibility_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        self.backup_bool_param(visibility_params, key)
        self.backup_bool_param(visibility_params, legacy_name)
        visibility_params.RemBool(key)
        visibility_params.SetBool(legacy_name, False)

        layout_params = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/WorkbenchLayouts")
        self.backup_group(
            layout_params,
            "SketcherWorkbench",
            "__ToolbarMigrationBackup__SketcherWorkbench",
        )
        workbench_layout = layout_params.GetGroup("SketcherWorkbench")
        workbench_layout.Clear()
        workbench_layout.SetBool("Saved", True)
        for area_name in ("Top", "Left", "Right", "Bottom"):
            workbench_layout.SetString(
                area_name, legacy_name if area_name == target_area_name else ""
            )

        self.activate_workbench("SketcherWorkbench", "wb:SketcherWorkbench:")
        self.assert_toolbar_visibility(key, False)
        self.assert_toolbar_area(key, target_area)
