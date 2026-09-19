# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shell and lifecycle helpers for BIM Plan Edit controls."""

import warnings

import FreeCAD
import FreeCADGui
from bimplan.ui import task_panel_view_model as plan_task_panel_view_model

translate = FreeCAD.Qt.translate


class PlanEditControlsShellMixin:
    def refresh_for_session(self, reason="full"):
        normalized_reason = str(reason or "full").strip().lower()
        if normalized_reason == "selection":
            return self.refresh_selection_from_session()
        if normalized_reason == "provider_overlay_mode":
            return self.refresh_provider_overlay_mode_from_session()
        return self.refresh_from_session()

    def _session_is_inactive(self):
        session = getattr(self, "session", None)
        if session is None:
            return True
        lifecycle_state = getattr(session, "lifecycle_state", None)
        if lifecycle_state is not None and (
            lifecycle_state.tearing_down or lifecycle_state.finishing
        ):
            return True
        document_visuals = getattr(session, "document_visuals", None)
        document_is_alive = getattr(document_visuals, "document_is_alive", None)
        if callable(document_is_alive):
            return not document_is_alive()
        return False

    def _build_form(self, QtGui):
        outer = QtGui.QWidget()
        outer.setMinimumWidth(0)
        try:
            outer.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum)
        except (AttributeError, RuntimeError, TypeError):
            pass
        layout = QtGui.QVBoxLayout(outer)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        layout.addWidget(self._build_header(QtGui))

        self.status_group, status_layout = self._build_section(QtGui, "")
        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred)
        status_layout.addWidget(self.status)
        layout.addWidget(self.status_group)

        self.create_group = self._build_action_group(
            QtGui,
            "Create",
            (
                (
                    ("wall_button", "Wall", self.on_wall_clicked),
                    ("rect_wall_button", "Rect Wall", self.on_rect_wall_clicked),
                ),
                (
                    ("window_button", "Window", self.on_window_clicked),
                    ("door_button", "Door", self.on_door_clicked),
                ),
                (
                    ("space_button", "Space", self.on_space_clicked),
                    ("region_button", "Region", self.on_region_clicked),
                ),
                (
                    ("separator_button", "Separator", self.on_separator_clicked),
                ),
            ),
        )
        layout.addWidget(self.create_group)

        self.modify_group, modify_layout = self._build_section(QtGui, "Actions")
        modify_layout.addLayout(
            self._build_button_row(
                (
                    ("select_button", "Select", self.on_select_clicked),
                    ("move_button", "Move", self.on_move_clicked),
                )
            )
        )
        modify_layout.addLayout(
            self._build_button_row(
                (("join_button", "Join", self.on_join_clicked),)
            )
        )
        modify_layout.addWidget(self._build_join_type_widget(QtGui))
        layout.addWidget(self.modify_group)

        layout.addWidget(self._build_view_settings(QtGui))

        self.space_editor = self._build_space_editor(QtGui)
        layout.addWidget(self.space_editor)
        self.region_editor = self._build_region_editor(QtGui)
        layout.addWidget(self.region_editor)
        self.window_editor = self._build_window_editor(QtGui)
        layout.addWidget(self.window_editor)
        self.integration_panel = self._build_integration_panel(QtGui)
        layout.addWidget(self.integration_panel)

        self._modal_focus_widgets = [
            self.storey_combo,
            self.join_type_combo,
            self.unjoin_button,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.window_button,
            self.door_button,
            self.space_button,
            self.region_button,
            self.separator_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
            self.grid_snap_checkbox,
            self.space_label_edit,
            self.space_type_combo,
            self.space_boundary_list,
            self.space_add_button,
            self.space_remove_button,
            self.space_text_button,
            self.region_label_edit,
            self.region_scheme_edit,
            self.region_type_edit,
            self.region_parent_space_combo,
            self.window_width_edit,
            self.window_height_edit,
            self.window_size_apply_button,
            self.window_preset_combo,
            self.window_preset_apply_button,
        ]
        self._capture_focus_policies()
        return outer

    def _build_header(self, QtGui):
        header = QtGui.QWidget()
        self._set_vertical_size_policy(QtGui, header)
        row = QtGui.QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        title_col = QtGui.QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        self.header_title_label = QtGui.QLabel(translate("BIM_PlanEdit", "Plan"))
        title_font = self.header_title_label.font()
        title_font.setBold(True)
        self.header_title_label.setFont(title_font)
        self.header_title_label.setWordWrap(True)
        self.header_title_label.setMinimumWidth(0)
        self.header_title_label.setSizePolicy(
            QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred
        )
        title_col.addWidget(self.header_title_label)

        self.header_mode_label = QtGui.QLabel("")
        self.header_mode_label.setWordWrap(True)
        title_col.addWidget(self.header_mode_label)

        row.addLayout(title_col, 1)
        return header

    def _make_button(self, QtGui, label, handler):
        button = QtGui.QPushButton(translate("BIM_PlanEdit", label))
        button.setMinimumWidth(0)
        button.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        button.clicked.connect(handler)
        return button

    def _set_vertical_size_policy(self, QtGui, widget):
        try:
            widget.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Maximum)
        except (AttributeError, RuntimeError, TypeError):
            pass

    def _build_section(self, QtGui, title):
        section = QtGui.QWidget()
        self._set_vertical_size_policy(QtGui, section)
        layout = QtGui.QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if title:
            title_label = QtGui.QLabel(translate("BIM_PlanEdit", title))
            title_font = title_label.font()
            title_font.setBold(True)
            title_label.setFont(title_font)
            layout.addWidget(title_label)
        return section, layout

    def _build_storey_section(self, QtGui):
        section, layout = self._build_section(QtGui, "Storey")
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.setMinimumWidth(0)
        self.storey_combo.setMinimumContentsLength(8)
        self.storey_combo.setSizeAdjustPolicy(
            QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.storey_combo.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Fixed)
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        layout.addWidget(self.storey_combo)
        return section

    def _build_view_settings(self, QtGui):
        from PySide import QtCore

        container = QtGui.QWidget()
        self._set_vertical_size_policy(QtGui, container)
        layout = QtGui.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.view_settings_toggle = QtGui.QToolButton(container)
        self.view_settings_toggle.setText(translate("BIM_PlanEdit", "View settings"))
        self.view_settings_toggle.setCheckable(True)
        self.view_settings_toggle.setChecked(False)
        self.view_settings_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.view_settings_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.view_settings_toggle.toggled.connect(self.on_view_settings_toggled)
        layout.addWidget(self.view_settings_toggle)

        self.view_settings_content = QtGui.QWidget(container)
        content_layout = QtGui.QVBoxLayout(self.view_settings_content)
        content_layout.setContentsMargins(12, 0, 0, 0)
        content_layout.setSpacing(7)
        self.grid_snap_checkbox = QtGui.QCheckBox(
            translate("BIM_PlanEdit", "Snap to grid"), self.view_settings_content
        )
        self.grid_snap_checkbox.setToolTip(
            translate(
                "BIM_PlanEdit",
                "Snap creation and editing points to the Plan grid",
            )
        )
        self.grid_snap_checkbox.toggled.connect(self.on_grid_snap_toggled)
        content_layout.addWidget(self.grid_snap_checkbox)
        self.storey_section = self._build_storey_section(QtGui)
        content_layout.addWidget(self.storey_section)
        self.view_group = self._build_action_group(
            QtGui,
            "",
            ((("reapply_button", "Reapply View", self.on_reapply_clicked),),),
        )
        content_layout.addWidget(self.view_group)
        self.view_settings_content.setVisible(False)
        layout.addWidget(self.view_settings_content)
        return container

    def _build_action_group(self, QtGui, title, rows):
        section, layout = self._build_section(QtGui, title)
        for specs in rows:
            layout.addLayout(self._build_button_row(specs))
        return section

    def _build_button_row(self, specs):
        from PySide import QtGui

        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        for attr, label, handler in specs:
            button = self._make_button(QtGui, label, handler)
            setattr(self, attr, button)
            row.addWidget(button)
        return row

    def _build_join_type_widget(self, QtGui):
        widget = QtGui.QWidget()
        row = QtGui.QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        join_type_label = QtGui.QLabel(translate("BIM_PlanEdit", "Join Type"))
        self.join_type_combo = QtGui.QComboBox()
        self.join_type_combo.setMinimumWidth(0)
        self.join_type_combo.setMinimumContentsLength(6)
        self.join_type_combo.setSizeAdjustPolicy(
            QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.join_type_combo.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Fixed)
        for join_type in self.session.wall_relations.get_plan_join_types():
            self.join_type_combo.addItem(
                self.session.wall_relations.get_plan_join_type_label(join_type), join_type
            )
        self.join_type_combo.currentIndexChanged.connect(self.on_join_type_changed)
        self.unjoin_button = self._make_button(QtGui, "Unjoin", self.on_unjoin_clicked)
        row.addWidget(join_type_label)
        row.addWidget(self.join_type_combo, 1)
        row.addWidget(self.unjoin_button)
        self.join_type_widget = widget
        return widget

    def _capture_focus_policies(self):
        for widget in self._modal_focus_widgets:
            try:
                self._saved_focus_policies[widget] = widget.focusPolicy()
            except Exception:
                pass

    def mark_closed(self):
        self._integration_refresh_queued = False
        self._integration_refresh_generation += 1

    def _disconnect_signal(self, signal):
        if signal is None:
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                signal.disconnect()
        except (TypeError, RuntimeError):
            pass
        except Exception:
            pass

    def _disconnect_widget_signals(self, form):
        if form is None:
            return
        try:
            from PySide import QtGui
        except ImportError:
            return

        try:
            buttons = form.findChildren(QtGui.QAbstractButton)
        except (AttributeError, RuntimeError, TypeError):
            buttons = []
        for button in buttons:
            self._disconnect_signal(getattr(button, "clicked", None))
            self._disconnect_signal(getattr(button, "toggled", None))

        try:
            combos = form.findChildren(QtGui.QComboBox)
        except (AttributeError, RuntimeError, TypeError):
            combos = []
        for combo in combos:
            self._disconnect_signal(getattr(combo, "currentIndexChanged", None))

        try:
            line_edits = form.findChildren(QtGui.QLineEdit)
        except (AttributeError, RuntimeError, TypeError):
            line_edits = []
        for line_edit in line_edits:
            self._disconnect_signal(getattr(line_edit, "editingFinished", None))
            self._disconnect_signal(getattr(line_edit, "returnPressed", None))
            self._disconnect_signal(getattr(line_edit, "textChanged", None))

        completer = self._space_type_completer
        if completer is not None:
            try:
                self._disconnect_signal(completer.activated[str])
            except (AttributeError, KeyError, TypeError):
                self._disconnect_signal(getattr(completer, "activated", None))

    def detach(self):
        if self._task_dialog_rejecting:
            self.mark_closed()
            self.session = None
            return
        self._close_task_dialog()
        self.dispose()

    def close(self):
        self._close_task_dialog()
        self.dispose()

    def _close_task_dialog(self):
        if self._task_dialog_rejecting:
            return
        document_name = self._task_dialog_document_name
        if not document_name or document_name not in FreeCAD.listDocuments():
            self._task_dialog_document_name = ""
            self._task_dialog_handle = None
            return
        try:
            import FreeCADGui

            gui_document = FreeCADGui.getDocument(document_name)
            if FreeCADGui.Control.activeDialog(gui_document):
                FreeCADGui.Control.closeDialog(gui_document)
        except (AttributeError, NameError, ReferenceError, RuntimeError):
            pass
        self._task_dialog_document_name = ""
        self._task_dialog_handle = None

    def getStandardButtons(self):
        from PySide import QtGui

        return QtGui.QDialogButtonBox.NoButton

    def isAllowedAlterDocument(self):
        return True

    def isAllowedAlterView(self):
        return True

    def isAllowedAlterSelection(self):
        return True

    def reject(self):
        session = self.session
        if session is None:
            return True
        self._task_dialog_rejecting = True
        try:
            session.shutdown(close_dialog=False)
        finally:
            self._task_dialog_rejecting = False
        return True

    def dispose(self):
        self.mark_closed()
        form = self.form
        if form is not None:
            self._disconnect_widget_signals(form)
            try:
                parent = form.parentWidget()
                layout_getter = getattr(parent, "layout", None) if parent is not None else None
                if callable(layout_getter):
                    layout = layout_getter()
                    if layout is not None:
                        layout.removeWidget(form)
            except (AttributeError, RuntimeError, TypeError):
                pass
            if FreeCADGui.isValidQObject(form):
                form.hide()
                form.setParent(None)
            FreeCADGui.deleteLater(form)
        self.form = None
        self.session = None
        self._task_dialog_document_name = ""
        self._task_dialog_handle = None
        self.status = None
        self.header_title_label = None
        self.header_mode_label = None
        self.status_group = None
        self.create_group = None
        self.modify_group = None
        self.view_group = None
        self.storey_section = None
        self.view_settings_toggle = None
        self.view_settings_content = None
        self.grid_snap_checkbox = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.window_button = None
        self.door_button = None
        self.space_button = None
        self.region_button = None
        self.separator_button = None
        self.move_button = None
        self.join_button = None
        self.join_type_combo = None
        self.join_type_widget = None
        self.unjoin_button = None
        self.reapply_button = None
        self.integration_panel = None
        self.integration_summary = None
        self.integration_content = None
        self.integration_content_layout = None
        self._integration_panel_state = None
        self._integration_action_buttons = []
        self._integration_overlay_checkboxes = []
        self.space_editor = None
        self.space_label_edit = None
        self.space_type_combo = None
        self.space_boundary_list = None
        self.space_add_button = None
        self.space_remove_button = None
        self.space_text_button = None
        self.region_editor = None
        self.region_label_edit = None
        self.region_scheme_edit = None
        self.region_type_edit = None
        self.region_parent_space_combo = None
        self.window_editor = None
        self.window_width_edit = None
        self.window_height_edit = None
        self.window_size_apply_button = None
        self.window_preset_combo = None
        self.window_preset_note = None
        self.window_preset_apply_button = None
        self._region_parent_space_items = []
        self._window_editor_state = None
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self._status_text_state = None
        self._modal_interaction_state = None
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._storey_items = []

    def refresh(self, defer_integrations=False, refresh_integrations=True):
        if self.form is None or self.storey_combo is None:
            return
        self.storey_combo.blockSignals(True)
        try:
            self.storey_combo.clear()
            self._storey_items = [None] + list(self.session.storeys)
            self.storey_combo.addItem(translate("BIM_PlanEdit", "Global XY (Z=0)"))
            for storey in self.session.storeys:
                self.storey_combo.addItem(self.session.storey.get_storey_label(storey))

            current = self.session.active_storey
            try:
                index = self._storey_items.index(current)
            except ValueError:
                index = 0
            self.storey_combo.setCurrentIndex(index)
        finally:
            try:
                self.storey_combo.blockSignals(False)
            except Exception:
                pass
        self.refresh_from_session(
            defer_integrations=defer_integrations,
            refresh_integrations=refresh_integrations,
        )

    def _sync_join_type_combo_from_session(self):
        if self.join_type_combo is None:
            return
        self.join_type_combo.blockSignals(True)
        try:
            join_type_index = self.join_type_combo.findData(
                self.session.wall_relations.get_plan_join_type()
            )
            if join_type_index >= 0:
                self.join_type_combo.setCurrentIndex(join_type_index)
        finally:
            try:
                self.join_type_combo.blockSignals(False)
            except Exception:
                pass

    def _set_status_text(self, text):
        text = str(text or "")
        if self.status is None or text == self._status_text_state:
            return
        self.status.setText(text)
        self._status_text_state = text

    def _set_widget_tooltip(self, widget, text):
        if widget is None:
            return
        try:
            widget.setToolTip(str(text or ""))
        except Exception:
            pass

    def _set_widget_enabled(self, widget, enabled):
        if widget is None:
            return
        try:
            widget.setEnabled(bool(enabled))
        except Exception:
            pass

    def _set_widget_visible(self, widget, visible):
        if widget is None:
            return
        try:
            widget.setVisible(bool(visible))
        except Exception:
            pass

    def _refresh_action_context(self, modal_active=None):
        action_context_vm = plan_task_panel_view_model.build_action_context_view_model(
            self.session,
            modal_active=modal_active,
        )
        selected_kind, selected_obj = self.session.selection.state.get_selected_plan_target()
        current_tool = str(self.session.current_tool or "Select")
        if self.header_title_label is not None:
            source = getattr(self.session.representation_request, "source", None)
            context_label = str(
                getattr(source, "Label", "")
                or getattr(source, "Name", "")
                or translate("BIM_PlanEdit", "Plan")
            )
            self.header_title_label.setText(context_label)
            self.header_title_label.setToolTip(context_label)
        if self.header_mode_label is not None:
            mode_text = translate("BIM_PlanEdit", "PLAN")
            if current_tool != "Select":
                mode_text = translate("BIM_PlanEdit", "PLAN · {tool}").format(
                    tool=action_context_vm.mode_label
                )
            self.header_mode_label.setText(mode_text)
        has_context = selected_obj is not None or current_tool != "Select"
        self._set_widget_visible(self.modify_group, has_context)
        self._set_widget_visible(self.select_button, current_tool != "Select")
        self._set_widget_visible(
            self.move_button,
            selected_obj is not None or current_tool == "Move",
        )
        self._set_widget_enabled(self.join_button, action_context_vm.join_button_enabled)
        self._set_widget_tooltip(self.join_button, action_context_vm.join_button_tooltip)
        self._set_widget_visible(self.join_type_widget, action_context_vm.show_join_options)
        self._set_widget_enabled(self.join_type_combo, action_context_vm.join_type_enabled)
        self._set_widget_tooltip(self.join_type_combo, action_context_vm.join_type_tooltip)
        self._set_widget_enabled(self.unjoin_button, action_context_vm.unjoin_button_enabled)
        self._set_widget_tooltip(self.unjoin_button, action_context_vm.unjoin_button_tooltip)
        self._set_widget_visible(self.window_button, action_context_vm.show_window_button)
        self._set_widget_enabled(self.window_button, action_context_vm.window_button_enabled)
        self._set_widget_tooltip(self.window_button, action_context_vm.window_button_tooltip)
        self._set_widget_visible(self.door_button, action_context_vm.show_door_button)
        self._set_widget_enabled(self.door_button, action_context_vm.door_button_enabled)
        self._set_widget_tooltip(self.door_button, action_context_vm.door_button_tooltip)

    def _build_context_guidance_text(self):
        selected_kind, selected_obj = self.session.selection.state.get_selected_plan_target()
        current_tool = str(self.session.current_tool or "Select")
        status_text = plan_task_panel_view_model.build_status_text_view_model(self.session).text
        if current_tool != "Select":
            return status_text
        if selected_obj is None:
            return translate(
                "BIM_PlanEdit",
                "Select an element for contextual actions. Ctrl-click selects multiple elements.",
            )
        lines = [line.strip() for line in str(status_text or "").splitlines() if line.strip()]
        return "\n".join(lines[:2])

    def refresh_from_session(self, defer_integrations=False, refresh_integrations=True):
        with self.session.performance.plan_perf_trace_span("refresh_task_panel_widget"):
            if self.form is None or self.status is None:
                return
            self._sync_join_type_combo_from_session()
            if self.grid_snap_checkbox is not None:
                self.grid_snap_checkbox.blockSignals(True)
                try:
                    self.grid_snap_checkbox.setChecked(
                        self.session.snap.is_grid_snap_enabled()
                    )
                finally:
                    self.grid_snap_checkbox.blockSignals(False)
            self._set_status_text(self._build_context_guidance_text())
            self._refresh_action_context()
            if refresh_integrations:
                self._refresh_integration_panel(defer=defer_integrations)
            self._refresh_space_editor()
            self._refresh_region_editor()
            self._refresh_window_editor()
            self._apply_modal_interaction_state(
                self.session.interaction.is_modal_plan_interaction_active()
            )

    def refresh_selection_from_session(self):
        with self.session.performance.plan_perf_trace_span("refresh_task_panel_selection_widget"):
            if self.form is None or self.status is None:
                return
            selected_kind, _selected_obj = self.session.selection.state.get_selected_plan_target()
            if self.session.current_tool != "Select" or selected_kind != "wall":
                self.refresh_from_session(defer_integrations=True)
                return
            self._set_status_text(self._build_context_guidance_text())
            self._refresh_action_context()
            if self._should_refresh_integration_panel_for_selection(selected_kind):
                self._refresh_integration_panel(defer=True)
            else:
                self._cancel_queued_integration_panel_refresh()
            self._hide_space_editor()
            self._hide_region_editor()
            self._hide_window_editor()
            self._apply_modal_interaction_state(
                self.session.interaction.is_modal_plan_interaction_active()
            )

    def refresh_provider_overlay_mode_from_session(self):
        with self.session.performance.plan_perf_trace_span(
            "refresh_task_panel_provider_overlay_mode_widget"
        ):
            if self.form is None or self.integration_panel is None:
                return
            self._set_widget_updates_enabled(self.integration_panel, False)
            try:
                self._refresh_integration_panel(defer=False)
            finally:
                self._set_widget_updates_enabled(self.integration_panel, True)
                self._refresh_widget_geometry(self.integration_panel)

    def _set_modal_focus_policies(self, modal_active, QtCore):
        for widget in self._modal_focus_widgets:
            if widget is None:
                continue
            try:
                widget.setFocusPolicy(
                    QtCore.Qt.NoFocus
                    if modal_active
                    else self._saved_focus_policies.get(widget, QtCore.Qt.StrongFocus)
                )
            except Exception:
                pass

    def _set_modal_enabled_state(self, widgets, enabled):
        for widget in widgets:
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(enabled))
            except Exception:
                pass

    def _apply_modal_core_action_state(self, modal_active, join_candidate):
        self._set_modal_enabled_state(
            (
                self.storey_combo,
                self.select_button,
                self.wall_button,
                self.rect_wall_button,
                self.window_button,
                self.door_button,
                self.space_button,
                self.region_button,
                self.separator_button,
                self.move_button,
                self.join_button,
                self.join_type_combo,
                self.unjoin_button,
                self.reapply_button,
                self.grid_snap_checkbox,
            ),
            not modal_active,
        )
        if self.unjoin_button is not None:
            try:
                self.unjoin_button.setEnabled(
                    not modal_active and self.session.current_tool == "Join" and join_candidate
                )
            except Exception:
                pass

    def _apply_modal_integration_state(self, modal_active):
        for button in self._integration_action_buttons:
            if button is None:
                continue
            try:
                base_enabled = button.property("planActionEnabled")
                button.setEnabled(bool(base_enabled) and not modal_active)
            except Exception:
                pass
        self._set_modal_enabled_state(self._integration_overlay_checkboxes, not modal_active)

    def _apply_modal_editor_state(self, modal_active, selected_kind):
        has_space = selected_kind == "space"
        self._set_modal_enabled_state(
            (
                self.space_label_edit,
                self.space_type_combo,
                self.space_boundary_list,
                self.space_add_button,
                self.space_remove_button,
                self.space_text_button,
            ),
            has_space and not modal_active,
        )
        has_region = selected_kind == "region"
        self._set_modal_enabled_state(
            (
                self.region_label_edit,
                self.region_scheme_edit,
                self.region_type_edit,
                self.region_parent_space_combo,
            ),
            has_region and not modal_active,
        )

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        selected_kind, selected_obj = self.session.selection.state.get_selected_plan_target()
        join_candidate = (
            self.session.wall_relations.get_plan_candidate_joint() is not None
            if self.session.current_tool == "Join"
            else False
        )
        state = (
            bool(modal_active),
            selected_kind,
            self.session.current_tool == "Join",
            bool(join_candidate),
        )
        if state == self._modal_interaction_state:
            return
        self._modal_interaction_state = state

        self._set_modal_focus_policies(modal_active, QtCore)
        self._apply_modal_core_action_state(modal_active, join_candidate)
        self._refresh_action_context(modal_active=modal_active)
        self._apply_modal_integration_state(modal_active)
        self._apply_modal_editor_state(modal_active, selected_kind)

        can_edit_window_width = (
            selected_kind == "opening"
            and selected_obj is not None
            and self.session.hosted_openings.can_edit_window_width(selected_obj)
        )
        can_edit_window_height = (
            selected_kind == "opening"
            and selected_obj is not None
            and self.session.hosted_openings.can_edit_window_height(selected_obj)
        )
        can_apply_window_style = (
            selected_kind == "opening"
            and selected_obj is not None
            and self.session.hosted_openings.can_apply_window_style_preset(selected_obj)
        )
        for widget in (self.window_width_edit,):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(can_edit_window_width and not modal_active))
            except Exception:
                pass
        for widget in (self.window_height_edit,):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(can_edit_window_height and not modal_active))
            except Exception:
                pass
        for widget in (self.window_preset_combo, self.window_preset_apply_button):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(can_apply_window_style and not modal_active))
            except Exception:
                pass
        self._update_window_size_apply_state(modal_active=modal_active)
        self._update_window_preset_apply_state(modal_active=modal_active)

    def on_storey_changed(self, index):
        if 0 <= index < len(self._storey_items):
            self.session.storey.set_active_storey(self._storey_items[index])

    def on_view_settings_toggled(self, expanded):
        from PySide import QtCore

        form = self.form
        if form is not None:
            form.setUpdatesEnabled(False)
        if self.view_settings_content is not None:
            self.view_settings_content.setVisible(bool(expanded))
        if self.view_settings_toggle is not None:
            self.view_settings_toggle.setArrowType(
                QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow
            )
        if form is not None:
            layout = form.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            form.updateGeometry()
            FreeCADGui.invokeLater(
                lambda current=form: self._finish_view_settings_repaint(current)
            )

    def _finish_view_settings_repaint(self, form):
        if form is None or form is not self.form or not FreeCADGui.isValidQObject(form):
            return
        form.setUpdatesEnabled(True)
        form.update()

    def on_grid_snap_toggled(self, enabled):
        self.session.snap.set_grid_snap_enabled(bool(enabled))

    def on_select_clicked(self):
        self.session.lifecycle.activate_select_tool()

    def on_wall_clicked(self):
        self.session.wall_create.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.wall_create.activate_rect_wall_tool()

    def on_window_clicked(self):
        self.session.hosted_openings.activate_window_tool()

    def on_door_clicked(self):
        self.session.hosted_openings.activate_door_tool()

    def on_space_clicked(self):
        self.session.spaces.activate_space_tool()

    def on_region_clicked(self):
        self.session.spaces.activate_plan_region_tool()

    def on_separator_clicked(self):
        self.session.spaces.activate_space_separator_tool()

    def on_move_clicked(self):
        self.session.move_tool.activate_move_tool()

    def on_join_clicked(self):
        self.session.wall_relations.activate_join_tool()

    def on_join_type_changed(self, index):
        if self.join_type_combo is None or index < 0:
            return
        join_type = self.join_type_combo.itemData(index) or self.join_type_combo.itemText(index)
        self.session.wall_relations.set_plan_join_type(join_type)

    def on_unjoin_clicked(self):
        self.session.wall_relations.unjoin_current_plan_wall_pair()

    def on_reapply_clicked(self):
        self.session.viewport.apply_plan_view(fit=False)
        self.refresh_from_session()
