# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task-panel controls for BIM Plan Edit."""

import FreeCAD
from bimplan import task_panel_view_model as plan_task_panel_view_model
from bimplan.ui.control_editors import PlanEditEditorPanelsMixin
from bimplan.ui.control_integrations import PlanEditIntegrationPanelMixin

translate = FreeCAD.Qt.translate


class PlanEditControlsWidget(PlanEditIntegrationPanelMixin, PlanEditEditorPanelsMixin):
    """Reusable session controls widget for Plan Edit mode."""

    _COMMON_SPACE_TYPES = (
        "Undefined",
        "Room",
        "Office",
        "Restrooms",
        "Corridor / Transition",
        "Lobby",
        "Dining Area",
        "Exterior",
        "Active Storage",
        "Electrical / Mechanical",
    )
    _INTEGRATION_REFRESH_DELAY_MS = 350

    def __init__(self, session):
        from PySide import QtGui

        self.session = session
        self._storey_items = []
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._refreshing_window_editor = False
        self._refreshing_space_editor = False
        self._refreshing_region_editor = False
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._window_editor_state = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self._status_text_state = None
        self._integration_panel_state = None
        self._integration_refresh_queued = False
        self._integration_refresh_generation = 0
        self._integration_action_buttons = []
        self._integration_overlay_checkboxes = []
        self._integration_overlay_block = None
        self._integration_overlay_mode_combo = None
        self._integration_overlay_content_layout = None
        self._modal_interaction_state = None
        self._region_parent_space_items = []
        self.header_mode_label = None
        self.status_group = None
        self.create_group = None
        self.modify_group = None
        self.view_group = None
        self.join_type_widget = None
        self.form = self._build_form(QtGui)
        try:
            self.form.setObjectName("BIMPlanEditContextControls")
        except Exception:
            pass

    @property
    def modal_focus_widgets(self):
        return tuple(self._modal_focus_widgets)

    def _session_is_inactive(self):
        session = getattr(self, "session", None)
        if session is None:
            return True
        if getattr(session, "_tearing_down", False) or getattr(
            session,
            "_finishing",
            False,
        ):
            return True
        return not session.document_visuals.document_is_alive()

    def _build_form(self, QtGui):
        outer = QtGui.QWidget()
        try:
            outer.setSizePolicy(
                QtGui.QSizePolicy.Expanding,
                QtGui.QSizePolicy.Maximum,
            )
        except Exception:
            pass
        layout = QtGui.QVBoxLayout(outer)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        layout.addWidget(self._build_header(QtGui))
        layout.addWidget(self._build_storey_section(QtGui))

        self.status_group, status_layout = self._build_section(QtGui, "Status")
        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        status_layout.addWidget(self.status)
        layout.addWidget(self.status_group)

        self.create_group = self._build_action_group(
            QtGui,
            "Create",
            (
                (
                    ("wall_button", "Wall", self.on_wall_clicked),
                    ("rect_wall_button", "Rect Wall", self.on_rect_wall_clicked),
                    ("window_button", "Window", self.on_window_clicked),
                ),
                (
                    ("space_button", "Space", self.on_space_clicked),
                    ("region_button", "Region", self.on_region_clicked),
                    ("separator_button", "Separator", self.on_separator_clicked),
                ),
            ),
        )
        layout.addWidget(self.create_group)

        self.modify_group, modify_layout = self._build_section(QtGui, "Modify")
        modify_layout.addLayout(
            self._build_button_row(
                (
                    ("select_button", "Select", self.on_select_clicked),
                    ("move_button", "Move", self.on_move_clicked),
                    ("join_button", "Join", self.on_join_clicked),
                ),
            )
        )
        modify_layout.addWidget(self._build_join_type_widget(QtGui))
        layout.addWidget(self.modify_group)

        self.view_group = self._build_action_group(
            QtGui,
            "View",
            ((("reapply_button", "Reapply View", self.on_reapply_clicked),),),
        )
        layout.addWidget(self.view_group)

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
            self.space_button,
            self.region_button,
            self.separator_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
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
            self.exit_button,
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

        title = QtGui.QLabel(translate("BIM_PlanEdit", "Plan Edit"))
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        title_col.addWidget(title)

        self.header_mode_label = QtGui.QLabel("")
        self.header_mode_label.setWordWrap(True)
        title_col.addWidget(self.header_mode_label)

        row.addLayout(title_col, 1)
        self.exit_button = self._make_button(QtGui, "Exit", self.on_exit_clicked)
        self.exit_button.setMinimumHeight(28)
        row.addWidget(self.exit_button)
        return header

    def _make_button(self, QtGui, label, handler):
        button = QtGui.QPushButton(translate("BIM_PlanEdit", label))
        button.clicked.connect(handler)
        return button

    def _set_vertical_size_policy(self, QtGui, widget):
        try:
            widget.setSizePolicy(
                QtGui.QSizePolicy.Preferred,
                QtGui.QSizePolicy.Maximum,
            )
        except Exception:
            pass

    def _build_section(self, QtGui, title):
        section = QtGui.QWidget()
        self._set_vertical_size_policy(QtGui, section)
        layout = QtGui.QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QtGui.QLabel(translate("BIM_PlanEdit", title))
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        return section, layout

    def _build_storey_section(self, QtGui):
        section, layout = self._build_section(QtGui, "Storey")
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        layout.addWidget(self.storey_combo)
        return section

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
            import warnings

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
        except Exception:
            return

        try:
            buttons = form.findChildren(QtGui.QAbstractButton)
        except Exception:
            buttons = []
        for button in buttons:
            self._disconnect_signal(getattr(button, "clicked", None))
            self._disconnect_signal(getattr(button, "toggled", None))

        try:
            combos = form.findChildren(QtGui.QComboBox)
        except Exception:
            combos = []
        for combo in combos:
            self._disconnect_signal(getattr(combo, "currentIndexChanged", None))

        try:
            line_edits = form.findChildren(QtGui.QLineEdit)
        except Exception:
            line_edits = []
        for line_edit in line_edits:
            self._disconnect_signal(getattr(line_edit, "editingFinished", None))
            self._disconnect_signal(getattr(line_edit, "returnPressed", None))
            self._disconnect_signal(getattr(line_edit, "textChanged", None))

        completer = self._space_type_completer
        if completer is not None:
            try:
                self._disconnect_signal(completer.activated[str])
            except Exception:
                self._disconnect_signal(getattr(completer, "activated", None))

    def detach(self):
        self.dispose()

    def close(self):
        self.dispose()

    def dispose(self):
        self.mark_closed()
        form = self.form
        if form is not None:
            self._disconnect_widget_signals(form)
            try:
                parent = form.parentWidget()
                if parent is not None and hasattr(parent, "layout"):
                    layout = parent.layout()
                    if layout is not None:
                        layout.removeWidget(form)
            except Exception:
                pass
            try:
                form.hide()
            except Exception:
                pass
            try:
                form.setParent(None)
            except Exception:
                pass
        self.form = None
        self.session = None
        self.status = None
        self.header_mode_label = None
        self.status_group = None
        self.create_group = None
        self.modify_group = None
        self.view_group = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.window_button = None
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
        self.exit_button = None
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

        if self.header_mode_label is not None:
            self.header_mode_label.setText(
                translate("BIM_PlanEdit", "{tool} mode").format(tool=action_context_vm.mode_label)
            )

        self._set_widget_enabled(self.join_button, action_context_vm.join_button_enabled)
        self._set_widget_tooltip(self.join_button, action_context_vm.join_button_tooltip)
        self._set_widget_visible(self.join_type_widget, action_context_vm.show_join_options)
        self._set_widget_enabled(self.join_type_combo, action_context_vm.join_type_enabled)
        self._set_widget_tooltip(
            self.join_type_combo,
            action_context_vm.join_type_tooltip,
        )
        self._set_widget_enabled(self.unjoin_button, action_context_vm.unjoin_button_enabled)
        self._set_widget_tooltip(self.unjoin_button, action_context_vm.unjoin_button_tooltip)
        self._set_widget_visible(self.window_button, action_context_vm.show_window_button)
        self._set_widget_enabled(self.window_button, action_context_vm.window_button_enabled)
        self._set_widget_tooltip(self.window_button, action_context_vm.window_button_tooltip)

    def refresh_from_session(self, defer_integrations=False, refresh_integrations=True):
        with self.session.performance.plan_perf_trace_span("refresh_task_panel_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return
            self._sync_join_type_combo_from_session()
            self._set_status_text(
                plan_task_panel_view_model.build_status_text_view_model(self.session).text
            )
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
            if self.form is None or self.status is None or self.exit_button is None:
                return
            selected_kind, _selected_obj = self.session.selection.get_selected_plan_target()
            if self.session.current_tool != "Select" or selected_kind != "wall":
                self.refresh_from_session(defer_integrations=True)
                return
            self._set_status_text(
                plan_task_panel_view_model.build_status_text_view_model(self.session).text
            )
            self._refresh_action_context()
            self._refresh_integration_panel(defer=True)
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

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        selected_kind, _selected_obj = self.session.selection.get_selected_plan_target()
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

        for widget in (
            self.storey_combo,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.window_button,
            self.space_button,
            self.region_button,
            self.separator_button,
            self.move_button,
            self.join_button,
            self.join_type_combo,
            self.unjoin_button,
            self.reapply_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(not modal_active)
            except Exception:
                pass
        if self.unjoin_button is not None:
            try:
                self.unjoin_button.setEnabled(
                    not modal_active and self.session.current_tool == "Join" and join_candidate
                )
            except Exception:
                pass
        self._refresh_action_context(modal_active=modal_active)
        for button in self._integration_action_buttons:
            if button is None:
                continue
            try:
                base_enabled = button.property("planActionEnabled")
                button.setEnabled(bool(base_enabled) and not modal_active)
            except Exception:
                pass
        for checkbox in self._integration_overlay_checkboxes:
            if checkbox is None:
                continue
            try:
                checkbox.setEnabled(not modal_active)
            except Exception:
                pass

        has_space = selected_kind == "space"
        for widget in (
            self.space_label_edit,
            self.space_type_combo,
            self.space_boundary_list,
            self.space_add_button,
            self.space_remove_button,
            self.space_text_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(has_space and not modal_active))
            except Exception:
                pass

        has_region = selected_kind == "region"
        for widget in (
            self.region_label_edit,
            self.region_scheme_edit,
            self.region_type_edit,
            self.region_parent_space_combo,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(has_region and not modal_active))
            except Exception:
                pass

        can_edit_window_width = (
            selected_kind == "opening"
            and _selected_obj is not None
            and self.session.windows.can_edit_window_width(_selected_obj)
        )
        can_edit_window_height = (
            selected_kind == "opening"
            and _selected_obj is not None
            and self.session.windows.can_edit_window_height(_selected_obj)
        )
        can_apply_window_style = (
            selected_kind == "opening"
            and _selected_obj is not None
            and self.session.windows.can_apply_window_style_preset(_selected_obj)
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

    def on_select_clicked(self):
        self.session.lifecycle.activate_select_tool()

    def on_wall_clicked(self):
        self.session.lifecycle.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.lifecycle.activate_rect_wall_tool()

    def on_window_clicked(self):
        self.session.lifecycle.activate_window_tool()

    def on_space_clicked(self):
        self.session.lifecycle.activate_space_tool()

    def on_region_clicked(self):
        self.session.lifecycle.activate_plan_region_tool()

    def on_separator_clicked(self):
        self.session.lifecycle.activate_space_separator_tool()

    def on_move_clicked(self):
        self.session.lifecycle.activate_move_tool()

    def on_join_clicked(self):
        self.session.lifecycle.activate_join_tool()

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

    def on_exit_clicked(self):
        self.session.shutdown()
