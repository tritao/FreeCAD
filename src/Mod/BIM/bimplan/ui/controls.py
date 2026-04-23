# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task-panel controls for BIM Plan Edit."""

import weakref

import FreeCAD
from bimplan.providers import (
    PlanContextPanelState,
    PlanContextSubjectKind,
    PlanIssueSeverity,
    PlanToolInteraction,
)

translate = FreeCAD.Qt.translate


def _run_queued_integration_panel_refresh(panel_ref, generation):
    panel = panel_ref()
    if panel is not None:
        panel._run_queued_integration_panel_refresh(generation)


class PlanEditControlsWidget:
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
        document_is_alive = getattr(session, "_document_is_alive", None)
        if callable(document_is_alive):
            return not document_is_alive()
        return False

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
        for join_type in self.session.get_plan_join_types():
            self.join_type_combo.addItem(
                self.session.get_plan_join_type_label(join_type), join_type
            )
        self.join_type_combo.currentIndexChanged.connect(self.on_join_type_changed)
        self.unjoin_button = self._make_button(QtGui, "Unjoin", self.on_unjoin_clicked)
        row.addWidget(join_type_label)
        row.addWidget(self.join_type_combo, 1)
        row.addWidget(self.unjoin_button)
        self.join_type_widget = widget
        return widget

    def _build_integration_panel(self, QtGui):
        panel, layout = self._build_section(QtGui, "Plan Guidance")
        panel.setVisible(False)
        layout.setSpacing(10)
        try:
            panel.setObjectName("BIMPlanEditGuidancePanel")
        except Exception:
            pass
        self._apply_integration_panel_styles(panel)

        overlay_mode_row = QtGui.QWidget(panel)
        overlay_mode_layout = QtGui.QHBoxLayout(overlay_mode_row)
        overlay_mode_layout.setContentsMargins(0, 0, 0, 0)
        overlay_mode_layout.setSpacing(8)
        overlay_mode_label = self._make_wrapped_plain_label(
            QtGui,
            translate("BIM_PlanEdit", "Mode"),
            overlay_mode_row,
            bold=True,
        )
        self._set_integration_style_property(overlay_mode_label, "planKeyValueLabel", "true")
        overlay_mode_layout.addWidget(overlay_mode_label)
        self._integration_overlay_mode_combo = QtGui.QComboBox(overlay_mode_row)
        for mode_key, mode_text in self._get_provider_overlay_mode_options():
            self._integration_overlay_mode_combo.addItem(mode_text, mode_key)
        self._set_provider_overlay_mode_combo_value(self.session.get_plan_provider_overlay_mode())
        self._integration_overlay_mode_combo.currentIndexChanged.connect(
            lambda index, current_combo=self._integration_overlay_mode_combo: (
                self.on_provider_overlay_mode_changed(current_combo.itemData(index))
            )
        )
        overlay_mode_layout.addWidget(self._integration_overlay_mode_combo, 1)
        layout.addWidget(overlay_mode_row)

        self.integration_summary = QtGui.QLabel(panel)
        self.integration_summary.setWordWrap(True)
        self._set_integration_style_property(self.integration_summary, "planPanelSummary", "true")
        layout.addWidget(self.integration_summary)

        self.integration_content = QtGui.QWidget(panel)
        self.integration_content_layout = QtGui.QVBoxLayout(self.integration_content)
        self.integration_content_layout.setContentsMargins(0, 0, 0, 0)
        self.integration_content_layout.setSpacing(8)
        layout.addWidget(self.integration_content)
        return panel

    def _apply_integration_panel_styles(self, widget):
        if widget is None:
            return
        try:
            widget.setStyleSheet("""
                QWidget#BIMPlanEditGuidancePanel {
                    background: transparent;
                }
                QFrame[planCard="true"] {
                    background: palette(window);
                    border: 1px solid palette(midlight);
                    border-radius: 3px;
                }
                QFrame[planCardRole="summary"] {
                    background: palette(window);
                    border-color: palette(midlight);
                }
                QFrame[planCardRole="issue-warning"] {
                    background: palette(window);
                    border-color: #d5b27c;
                }
                QFrame[planCardRole="issue-error"] {
                    background: palette(window);
                    border-color: #d29c92;
                }
                QFrame[planCardRole="utility"] {
                    background: palette(window);
                    border-color: palette(midlight);
                }
                QFrame[planCardRole="detail"] {
                    background: palette(window);
                    border-color: palette(midlight);
                }
                QLabel[planCardTitle="true"] {
                    font-weight: bold;
                }
                QLabel[planEyebrow="true"] {
                    color: palette(text);
                    font-weight: bold;
                }
                QLabel[planSectionHeading="true"] {
                    color: palette(window-text);
                    font-weight: bold;
                    margin-top: 4px;
                }
                QLabel[planSubsectionTitle="true"] {
                    color: palette(window-text);
                    font-weight: bold;
                    margin-top: 2px;
                }
                QLabel[planKeyValueLabel="true"] {
                    color: palette(text);
                    font-weight: bold;
                }
                QLabel[planPrimaryValue="true"] {
                    font-weight: bold;
                }
                QLabel[planPanelSummary="true"] {
                    color: palette(text);
                }
                QLabel[planStatusLabel="true"] {
                }
                QLabel[planStatusValue="true"] {
                    font-weight: bold;
                }
                QLabel[planStatusTone="success"] {
                    color: #2f5d38;
                }
                QLabel[planStatusTone="warning"] {
                    color: #785100;
                }
                QLabel[planStatusTone="danger"] {
                    color: #8a4233;
                }
                QLabel[planStatusTone="muted"] {
                    color: #666666;
                }
                QLabel[planStatusTone="neutral"] {
                    color: palette(window-text);
                }
                """)
        except Exception:
            pass

    def _make_wrapped_plain_label(self, QtGui, text, parent, bold=False):
        label = QtGui.QLabel(str(text or ""), parent)
        label.setWordWrap(True)
        try:
            from PySide import QtCore

            label.setTextFormat(QtCore.Qt.PlainText)
        except Exception:
            pass
        try:
            label.setSizePolicy(
                QtGui.QSizePolicy.Preferred,
                QtGui.QSizePolicy.Minimum,
            )
        except Exception:
            pass
        if bold:
            font = label.font()
            font.setBold(True)
            label.setFont(font)
        return label

    def _set_integration_style_property(self, widget, name, value):
        if widget is None:
            return
        try:
            widget.setProperty(name, value)
        except Exception:
            return
        try:
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
        except Exception:
            pass
        try:
            widget.update()
        except Exception:
            pass

    def _make_integration_group_heading(self, QtGui, text):
        heading = self._make_wrapped_plain_label(QtGui, text, self.integration_panel, bold=True)
        self._set_integration_style_property(heading, "planSectionHeading", "true")
        return heading

    def _create_integration_card(self, QtGui, role="default"):
        block = QtGui.QFrame(self.integration_panel)
        block.setFrameShape(QtGui.QFrame.StyledPanel)
        self._set_integration_style_property(block, "planCard", "true")
        self._set_integration_style_property(block, "planCardRole", str(role or "default"))

        layout = QtGui.QVBoxLayout(block)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        return block, layout

    def _add_integration_card_header(self, QtGui, layout, parent, title, eyebrow=""):
        eyebrow_text = str(eyebrow or "").strip()
        if eyebrow_text:
            eyebrow_label = self._make_wrapped_plain_label(QtGui, eyebrow_text, parent, bold=True)
            self._set_integration_style_property(eyebrow_label, "planEyebrow", "true")
            layout.addWidget(eyebrow_label)

        title_label = self._make_wrapped_plain_label(QtGui, title, parent, bold=True)
        self._set_integration_style_property(title_label, "planCardTitle", "true")
        layout.addWidget(title_label)

    def _get_action_identity(self, action):
        return (
            str(getattr(action, "provider_id", "") or "").strip(),
            str(getattr(action, "key", "") or "").strip(),
            str(getattr(action, "label", "") or "").strip(),
        )

    def _collect_action_identities(self, actions):
        identities = []
        seen = set()
        for action in tuple(actions or ()):
            identity = self._get_action_identity(action)
            if identity in seen:
                continue
            seen.add(identity)
            identities.append(identity)
        return tuple(identities)

    def _collect_action_labels(self, actions):
        labels = []
        seen = set()
        for action in tuple(actions or ()):
            label = str(getattr(action, "label", "") or "").strip()
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return tuple(labels)

    def _filter_integration_actions(
        self,
        actions,
        hidden_action_ids=(),
        hidden_action_labels=(),
    ):
        hidden = set(tuple(hidden_action_ids or ()))
        hidden_labels = {str(label or "").strip() for label in tuple(hidden_action_labels or ())}
        visible = []
        for action in tuple(actions or ()):
            if self._get_action_identity(action) in hidden:
                continue
            if str(getattr(action, "label", "") or "").strip() in hidden_labels:
                continue
            visible.append(action)
        return tuple(visible)

    def _build_detail_toggle_text(self, expanded, detail_title):
        detail_text = str(detail_title or "").strip() or translate("BIM_PlanEdit", "Details")
        if expanded:
            return translate("BIM_PlanEdit", "Hide details")
        return translate("BIM_PlanEdit", "{detail}...").format(
            detail=detail_text,
        )

    def _parse_workflow_summary_body(self, body):
        lines = [
            str(line or "").strip()
            for line in str(body or "").splitlines()
            if str(line or "").strip()
        ]
        if not lines:
            return None
        scope = ""
        next_step = ""
        extra_lines = []
        groups = []
        current_group = None
        for index, line in enumerate(lines):
            if line.startswith("Scope:"):
                scope = line.partition(":")[2].strip()
                current_group = None
                continue
            if line.startswith("Next:"):
                next_step = line.partition(":")[2].strip()
                current_group = None
                continue
            if line.startswith("- "):
                if current_group is not None:
                    current_group[1].append(line[2:].strip())
                else:
                    extra_lines.append(line[2:].strip())
                continue
            current_group = None
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if next_line.startswith("- "):
                current_group = [line, []]
                groups.append(current_group)
                continue
            extra_lines.append(line)
        structured_groups = tuple(
            (title, tuple(rows))
            for title, rows in groups
            if str(title or "").strip() or tuple(rows or ())
        )
        if not scope and not next_step and not structured_groups:
            return None
        return {
            "scope": scope,
            "next_step": next_step,
            "groups": structured_groups,
            "extra_lines": tuple(extra_lines),
        }

    def _normalize_summary_status_text(self, text):
        normalized = str(text or "").strip()
        lowered = normalized.lower()
        replacements = {
            "ready": translate("BIM_PlanEdit", "Ready"),
            "waiting for authoring": translate("BIM_PlanEdit", "Blocked"),
            "not generated": translate("BIM_PlanEdit", "Not generated"),
            "no action needed": translate("BIM_PlanEdit", "No action needed"),
        }
        if lowered in replacements:
            return replacements[lowered]
        if normalized[:1].islower():
            return normalized[:1].upper() + normalized[1:]
        return normalized

    def _get_summary_status_tone(self, text):
        lowered = str(text or "").strip().lower()
        if "ready" in lowered or "no action needed" in lowered:
            return "success"
        if "missing" in lowered or "issue" in lowered or "not generated" in lowered:
            return "danger"
        if "waiting" in lowered or "blocked" in lowered:
            return "muted"
        if lowered:
            return "warning"
        return "neutral"

    def _make_summary_meta_row(self, QtGui, parent, label, value, prominent=False):
        row_widget = QtGui.QWidget(parent)
        row = QtGui.QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        key_label = self._make_wrapped_plain_label(QtGui, label, row_widget, bold=True)
        self._set_integration_style_property(key_label, "planKeyValueLabel", "true")
        row.addWidget(key_label)

        value_label = self._make_wrapped_plain_label(QtGui, value, row_widget, bold=prominent)
        if prominent:
            self._set_integration_style_property(value_label, "planPrimaryValue", "true")
        row.addWidget(value_label, 1)
        return row_widget

    def _make_summary_status_row(self, QtGui, parent, row_text):
        row_widget = QtGui.QWidget(parent)
        row = QtGui.QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        label_text, separator, value_text = str(row_text or "").partition(":")
        label = self._make_wrapped_plain_label(QtGui, label_text.strip(), row_widget)
        self._set_integration_style_property(label, "planStatusLabel", "true")
        row.addWidget(label, 1)

        if separator:
            status_text = self._normalize_summary_status_text(value_text)
            status_label = self._make_wrapped_plain_label(
                QtGui,
                status_text,
                row_widget,
                bold=True,
            )
            try:
                status_label.setWordWrap(False)
            except Exception:
                pass
            self._set_integration_style_property(status_label, "planStatusValue", "true")
            self._set_integration_style_property(
                status_label,
                "planStatusTone",
                self._get_summary_status_tone(status_text),
            )
            row.addWidget(status_label)
        return row_widget

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
                child_layout.deleteLater()
                continue
            widget = item.widget()
            if widget is not None:
                try:
                    widget.hide()
                except Exception:
                    pass
                try:
                    widget.setParent(None)
                except Exception:
                    pass
                try:
                    widget.deleteLater()
                except Exception:
                    pass

    def _add_integration_action_row(
        self,
        QtGui,
        parent,
        layout,
        actions=(),
        hidden_action_ids=(),
        hidden_action_labels=(),
        primary_first=False,
        grid_columns=0,
        default_role="secondary",
    ):
        actions = self._filter_integration_actions(
            actions,
            hidden_action_ids=hidden_action_ids,
            hidden_action_labels=hidden_action_labels,
        )
        if not actions:
            return
        use_grid = bool(grid_columns and len(actions) > 1)
        if use_grid:
            action_layout = QtGui.QGridLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setHorizontalSpacing(6)
            action_layout.setVerticalSpacing(6)
        else:
            action_layout = QtGui.QHBoxLayout()
            action_layout.setSpacing(6)
        for index, action in enumerate(actions):
            button = QtGui.QPushButton(str(action.label or ""), parent)
            tooltip = str(action.tooltip or "").strip()
            if tooltip:
                try:
                    button.setToolTip(tooltip)
                except Exception:
                    pass
            try:
                button.setProperty("planActionEnabled", bool(action.enabled))
            except Exception:
                pass
            button.setEnabled(bool(action.enabled))
            button.clicked.connect(
                lambda _checked=False, current_action=action: self.on_provider_action_clicked(
                    current_action
                )
            )
            button_role = (
                "primary" if primary_first and index == 0 else str(default_role or "secondary")
            )
            self._set_integration_style_property(button, "planActionRole", button_role)
            try:
                button.setAutoDefault(False)
                button.setDefault(False)
            except Exception:
                pass
            if button_role == "primary":
                try:
                    button.setMinimumHeight(30)
                except Exception:
                    pass
                try:
                    font = button.font()
                    font.setBold(True)
                    button.setFont(font)
                except Exception:
                    pass
            self._integration_action_buttons.append(button)
            if use_grid:
                row_index = index // int(grid_columns)
                column_index = index % int(grid_columns)
                action_layout.addWidget(button, row_index, column_index)
            else:
                action_layout.addWidget(button)
        if not use_grid:
            action_layout.addStretch(1)
        layout.addLayout(action_layout)

    def _make_integration_block(
        self,
        QtGui,
        title,
        body="",
        actions=(),
        card_role="default",
        eyebrow="",
        hidden_action_ids=(),
        hidden_action_labels=(),
        primary_first=False,
        action_columns=0,
        default_action_role="secondary",
    ):
        block, layout = self._create_integration_card(QtGui, card_role)
        self._add_integration_card_header(QtGui, layout, block, title, eyebrow=eyebrow)

        body_text = str(body or "").strip()
        if body_text:
            body_label = self._make_wrapped_plain_label(QtGui, body_text, block)
            layout.addWidget(body_label)

        self._add_integration_action_row(
            QtGui,
            block,
            layout,
            actions,
            hidden_action_ids=hidden_action_ids,
            hidden_action_labels=hidden_action_labels,
            primary_first=primary_first,
            grid_columns=action_columns,
            default_role=default_action_role,
        )
        return block

    def _make_integration_collapsible_block(
        self,
        QtGui,
        title,
        summary="",
        details="",
        actions=(),
        collapsed=False,
        detail_title="Details",
        card_role="default",
        eyebrow="",
        hidden_action_ids=(),
        hidden_action_labels=(),
        primary_first=False,
    ):
        block, layout = self._create_integration_card(QtGui, card_role)
        self._add_integration_card_header(QtGui, layout, block, title, eyebrow=eyebrow)

        summary_text = str(summary or "").strip()
        if summary_text:
            summary_label = self._make_wrapped_plain_label(QtGui, summary_text, block)
            layout.addWidget(summary_label)

        self._add_integration_action_row(
            QtGui,
            block,
            layout,
            actions,
            hidden_action_ids=hidden_action_ids,
            hidden_action_labels=hidden_action_labels,
            primary_first=primary_first,
        )

        detail_text = str(details or "").strip()
        if detail_text:
            expanded = not bool(collapsed)
            detail_button = QtGui.QPushButton(
                self._build_detail_toggle_text(expanded, detail_title),
                block,
            )
            try:
                detail_button.setCheckable(True)
                detail_button.setChecked(expanded)
            except Exception:
                pass
            try:
                detail_button.setFlat(True)
                detail_button.setAutoDefault(False)
                detail_button.setSizePolicy(
                    QtGui.QSizePolicy.Maximum,
                    QtGui.QSizePolicy.Fixed,
                )
            except Exception:
                pass
            try:
                from PySide import QtCore

                layout.addWidget(detail_button, 0, QtCore.Qt.AlignLeft)
            except Exception:
                layout.addWidget(detail_button)

            detail_content = QtGui.QWidget(block)
            detail_content_layout = QtGui.QVBoxLayout(detail_content)
            detail_content_layout.setContentsMargins(0, 0, 0, 0)
            detail_content_layout.setSpacing(4)

            detail_label = self._make_wrapped_plain_label(
                QtGui,
                detail_text,
                detail_content,
            )
            detail_content_layout.addWidget(detail_label)
            layout.addWidget(detail_content)
            detail_content.setVisible(expanded)

            def toggle_details(checked):
                is_expanded = bool(checked)
                detail_content.setVisible(is_expanded)
                detail_button.setText(self._build_detail_toggle_text(is_expanded, detail_title))

            try:
                detail_button.toggled.connect(toggle_details)
            except Exception:
                pass
        return block

    def _make_summary_section_block(self, QtGui, section):
        provider_label = self.session.get_plan_provider_display_name(section.provider_id)
        parsed = self._parse_workflow_summary_body(getattr(section, "body", ""))
        if parsed is None:
            return self._make_integration_block(
                QtGui,
                str(getattr(section, "title", "") or "").strip()
                or translate("BIM_PlanEdit", "Summary"),
                body=getattr(section, "body", ""),
                actions=section.actions,
                card_role="summary",
                eyebrow=provider_label,
                primary_first=True,
            )

        block, layout = self._create_integration_card(QtGui, "summary")
        section_title = str(getattr(section, "title", "") or "").strip() or translate(
            "BIM_PlanEdit",
            "Summary",
        )
        self._add_integration_card_header(
            QtGui,
            layout,
            block,
            section_title,
            eyebrow=provider_label,
        )

        scope_text = str(parsed.get("scope", "") or "").strip()
        if scope_text:
            layout.addWidget(
                self._make_summary_meta_row(
                    QtGui,
                    block,
                    translate("BIM_PlanEdit", "Scope"),
                    scope_text,
                )
            )

        next_step_text = str(parsed.get("next_step", "") or "").strip()
        if next_step_text:
            layout.addWidget(
                self._make_summary_meta_row(
                    QtGui,
                    block,
                    translate("BIM_PlanEdit", "Next Step"),
                    next_step_text,
                    prominent=True,
                )
            )

        self._add_integration_action_row(
            QtGui,
            block,
            layout,
            section.actions,
            primary_first=True,
        )

        for group_title, rows in tuple(parsed.get("groups", ()) or ()):
            group_widget = QtGui.QWidget(block)
            group_layout = QtGui.QVBoxLayout(group_widget)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)

            group_label = self._make_wrapped_plain_label(
                QtGui, group_title, group_widget, bold=True
            )
            self._set_integration_style_property(group_label, "planSubsectionTitle", "true")
            group_layout.addWidget(group_label)
            for row_text in tuple(rows or ()):
                group_layout.addWidget(
                    self._make_summary_status_row(
                        QtGui,
                        group_widget,
                        row_text,
                    )
                )
            layout.addWidget(group_widget)

        extra_lines = tuple(parsed.get("extra_lines", ()) or ())
        if extra_lines:
            extra_label = self._make_wrapped_plain_label(QtGui, "\n".join(extra_lines), block)
            layout.addWidget(extra_label)
        return block

    def _format_provider_issue_heading(self, provider_label, severity, title):
        severity_label = {
            PlanIssueSeverity.ERROR: translate("BIM_PlanEdit", "Error"),
            PlanIssueSeverity.WARNING: translate("BIM_PlanEdit", "Warning"),
        }.get(severity, translate("BIM_PlanEdit", "Info"))
        provider_text = str(provider_label or "").strip()
        if not provider_text:
            provider_text = translate("BIM_PlanEdit", "Integrations")
        return translate("BIM_PlanEdit", "{provider} [{severity}]: {title}").format(
            provider=provider_text,
            severity=severity_label,
            title=str(title or "").strip(),
        )

    def _format_provider_issue_title(self, issue):
        role = self._get_provider_issue_role(issue)
        if role == "workflow":
            title = self._get_provider_issue_group_title(issue)
            if title:
                return title
            issue_title = str(getattr(issue, "title", "") or "").strip()
            if issue_title:
                return issue_title
        provider_label = self.session.get_plan_provider_display_name(issue.provider_id)
        return self._format_provider_issue_heading(
            provider_label,
            getattr(issue, "severity", ""),
            getattr(issue, "title", ""),
        )

    def _get_provider_issue_body(self, issue):
        issue_text = str(getattr(issue, "title", "") or "").strip()
        message_text = str(getattr(issue, "message", "") or "").strip()
        body = message_text or issue_text
        if body == issue_text:
            body = str(message_text or "").strip()
        return body

    def _get_provider_issue_summary(self, issue):
        summary = str(getattr(issue, "summary", "") or "").strip()
        if summary:
            return summary
        return self._get_provider_issue_body(issue)

    def _get_provider_issue_role(self, issue):
        return str(getattr(issue, "role", "") or "").strip().lower()

    def _get_provider_issue_group_key(self, issue):
        return str(getattr(issue, "group_key", "") or "").strip()

    def _get_provider_issue_group_title(self, issue):
        return str(getattr(issue, "group_title", "") or "").strip()

    def _is_provider_issue_collapsed(self, issue):
        return bool(getattr(issue, "collapsed", False))

    def _get_provider_issue_severity_rank(self, issue):
        return {
            PlanIssueSeverity.ERROR: 3,
            PlanIssueSeverity.WARNING: 2,
            PlanIssueSeverity.INFO: 1,
        }.get(getattr(issue, "severity", PlanIssueSeverity.INFO), 0)

    def _get_provider_issue_group_severity(self, issues):
        ranked = sorted(
            tuple(issues or ()),
            key=self._get_provider_issue_severity_rank,
            reverse=True,
        )
        if not ranked:
            return PlanIssueSeverity.INFO
        return getattr(ranked[0], "severity", PlanIssueSeverity.INFO)

    def _get_provider_issue_group_provider_label(self, issues):
        labels = []
        seen = set()
        for issue in tuple(issues or ()):
            label = str(
                self.session.get_plan_provider_display_name(getattr(issue, "provider_id", "")) or ""
            ).strip()
            if label and label not in seen:
                labels.append(label)
                seen.add(label)
        if len(labels) == 1:
            return labels[0]
        if len(labels) > 1:
            return translate("BIM_PlanEdit", "Integrations")
        return ""

    def _format_provider_issue_group_title(self, issues):
        issues = tuple(issues or ())
        first = issues[0] if issues else None
        title = self._get_provider_issue_group_title(first) if first is not None else ""
        if not title and first is not None:
            title = str(getattr(first, "title", "") or "").strip()
        if not title:
            title = translate("BIM_PlanEdit", "{count} issue(s)").format(count=len(issues))
        if first is not None and self._get_provider_issue_role(first) == "workflow":
            return title
        return self._format_provider_issue_heading(
            self._get_provider_issue_group_provider_label(issues),
            self._get_provider_issue_group_severity(issues),
            title,
        )

    def _format_provider_issue_group_summary(self, issues):
        issues = tuple(issues or ())
        if len(issues) <= 1:
            return self._get_provider_issue_summary(issues[0]) if issues else ""
        summaries = []
        seen = set()
        for issue in issues:
            summary = self._get_provider_issue_summary(issue)
            if not summary or summary in seen:
                continue
            summaries.append(summary)
            seen.add(summary)
        if summaries:
            return "\n".join(f"- {summary}" for summary in summaries)
        return translate("BIM_PlanEdit", "{count} related issue(s).").format(count=len(issues))

    def _format_provider_issue_group_details(self, issues):
        lines = []
        for issue in tuple(issues or ()):
            title = str(getattr(issue, "title", "") or "").strip()
            body = self._get_provider_issue_body(issue)
            if body and body != title:
                lines.append(f"- {title}: {body}")
            elif title:
                lines.append(f"- {title}")
            elif body:
                lines.append(f"- {body}")
        return "\n".join(lines)

    def _collect_provider_issue_group_actions(self, issues):
        actions = []
        seen = set()
        for issue in tuple(issues or ()):
            for action in tuple(getattr(issue, "actions", ()) or ()):
                key = (
                    str(getattr(action, "provider_id", "") or ""),
                    str(getattr(action, "key", "") or ""),
                    str(getattr(action, "label", "") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                actions.append(action)
        return tuple(actions)

    def _group_provider_issues(self, issues):
        grouped = []
        groups_by_key = {}
        for issue in tuple(issues or ()):
            group_key = self._get_provider_issue_group_key(issue)
            if not group_key:
                grouped.append([issue])
                continue
            group = groups_by_key.get(group_key)
            if group is None:
                group = []
                groups_by_key[group_key] = group
                grouped.append(group)
            group.append(issue)
        return tuple(tuple(group) for group in grouped if group)

    def _make_provider_issue_block(self, QtGui, issues, hidden_action_ids=()):
        issues = tuple(issues or ())
        if not issues:
            return None
        has_group_key = bool(self._get_provider_issue_group_key(issues[0]))
        collapsed = any(self._is_provider_issue_collapsed(issue) for issue in issues)
        card_role = {
            PlanIssueSeverity.ERROR: "issue-error",
            PlanIssueSeverity.WARNING: "issue-warning",
        }.get(self._get_provider_issue_group_severity(issues), "detail")
        if len(issues) > 1 or collapsed:
            details = self._format_provider_issue_group_details(issues)
            return self._make_integration_collapsible_block(
                QtGui,
                self._format_provider_issue_group_title(issues),
                summary=self._format_provider_issue_group_summary(issues),
                details=details,
                actions=self._collect_provider_issue_group_actions(issues),
                collapsed=collapsed,
                detail_title=translate("BIM_PlanEdit", "Issue Details"),
                card_role=card_role,
                hidden_action_ids=hidden_action_ids,
            )
        issue = issues[0]
        if has_group_key:
            return self._make_integration_block(
                QtGui,
                self._format_provider_issue_group_title(issues),
                body=self._get_provider_issue_body(issue),
                actions=self._collect_provider_issue_group_actions(issues),
                card_role=card_role,
                hidden_action_ids=hidden_action_ids,
            )
        return self._make_integration_block(
            QtGui,
            self._format_provider_issue_title(issue),
            body=self._get_provider_issue_body(issue),
            actions=issue.actions,
            card_role=card_role,
            hidden_action_ids=hidden_action_ids,
        )

    def _format_provider_section_title(self, section):
        provider_label = self.session.get_plan_provider_display_name(section.provider_id)
        title = str(getattr(section, "title", "") or "").strip()
        if not title:
            return provider_label
        return translate("BIM_PlanEdit", "{provider}: {title}").format(
            provider=provider_label,
            title=title,
        )

    def _get_provider_section_role(self, section):
        return str(getattr(section, "role", "") or "").strip().lower()

    def _is_provider_section_collapsed(self, section):
        return bool(getattr(section, "collapsed", False))

    def _partition_provider_sections(self, sections):
        summary_sections = []
        detail_sections = []
        regular_sections = []
        for section in tuple(sections or ()):
            role = self._get_provider_section_role(section)
            if role == "summary":
                summary_sections.append(section)
            elif role == "details":
                detail_sections.append(section)
            else:
                regular_sections.append(section)
        return (
            tuple(summary_sections),
            tuple(regular_sections),
            tuple(detail_sections),
        )

    def _get_provider_context_panel_state_rank(self, panel):
        return {
            PlanContextPanelState.ACTIVE_TOOL: 0,
            PlanContextPanelState.GEOMETRY_REVIEW: 1,
            PlanContextPanelState.SINGLE_OBJECT: 2,
            PlanContextPanelState.MULTI_SELECTION: 3,
            PlanContextPanelState.EMPTY: 4,
        }.get(getattr(panel, "state", None), 5)

    def _resolve_provider_context_panel(self, panels):
        ranked = []
        for index, panel in enumerate(tuple(panels or ())):
            if not panel:
                continue
            ranked.append((self._get_provider_context_panel_state_rank(panel), index, panel))
        if not ranked:
            return None
        ranked.sort(key=lambda entry: (entry[0], entry[1]))
        return ranked[0][2]

    def _get_provider_context_panel_heading(self, panel):
        state = getattr(panel, "state", None)
        subject_kind = getattr(panel, "subject_kind", None)
        if (
            state == PlanContextPanelState.ACTIVE_TOOL
            or subject_kind == PlanContextSubjectKind.INTERACTION
        ):
            return translate("BIM_PlanEdit", "Current Tool")
        if (
            state == PlanContextPanelState.GEOMETRY_REVIEW
            or subject_kind == PlanContextSubjectKind.GEOMETRY
        ):
            return translate("BIM_PlanEdit", "Geometry")
        if state in (
            PlanContextPanelState.SINGLE_OBJECT,
            PlanContextPanelState.MULTI_SELECTION,
        ) or subject_kind in (
            PlanContextSubjectKind.ENDPOINT,
            PlanContextSubjectKind.NETWORK,
            PlanContextSubjectKind.DISTRIBUTION,
        ):
            return translate("BIM_PlanEdit", "Selection")
        return translate("BIM_PlanEdit", "Context")

    def _collect_provider_context_panel_actions(self, panel):
        actions = []
        seen = set()
        primary_action = getattr(panel, "primary_action", None)
        has_primary = bool(primary_action and getattr(primary_action, "enabled", False))
        if has_primary:
            identity = self._get_action_identity(primary_action)
            seen.add(identity)
            actions.append(primary_action)
        for action in tuple(getattr(panel, "secondary_actions", ()) or ()):
            if not bool(getattr(action, "enabled", False)):
                continue
            identity = self._get_action_identity(action)
            if identity in seen:
                continue
            seen.add(identity)
            actions.append(action)
        return tuple(actions), has_primary

    def _make_provider_context_panel_detail(self, QtGui, parent, layout, detail):
        detail_title = str(getattr(detail, "title", "") or "").strip()
        if not detail_title:
            return
        expanded = not bool(getattr(detail, "collapsed", True))
        detail_button = QtGui.QPushButton(
            self._build_detail_toggle_text(expanded, detail_title),
            parent,
        )
        try:
            detail_button.setCheckable(True)
            detail_button.setChecked(expanded)
            detail_button.setFlat(True)
            detail_button.setAutoDefault(False)
            detail_button.setSizePolicy(
                QtGui.QSizePolicy.Maximum,
                QtGui.QSizePolicy.Fixed,
            )
        except Exception:
            pass
        try:
            from PySide import QtCore

            layout.addWidget(detail_button, 0, QtCore.Qt.AlignLeft)
        except Exception:
            layout.addWidget(detail_button)

        content = QtGui.QWidget(parent)
        content_layout = QtGui.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        for row in tuple(getattr(detail, "rows", ()) or ()):
            content_layout.addWidget(
                self._make_summary_meta_row(
                    QtGui,
                    content,
                    getattr(row, "label", ""),
                    getattr(row, "value", ""),
                )
            )

        body_text = str(getattr(detail, "body", "") or "").strip()
        if body_text:
            content_layout.addWidget(self._make_wrapped_plain_label(QtGui, body_text, content))
        layout.addWidget(content)
        content.setVisible(expanded)

        def toggle_details(checked):
            is_expanded = bool(checked)
            content.setVisible(is_expanded)
            detail_button.setText(self._build_detail_toggle_text(is_expanded, detail_title))

        try:
            detail_button.toggled.connect(toggle_details)
        except Exception:
            pass

    def _make_provider_context_panel_block(self, QtGui, panel):
        block, layout = self._create_integration_card(QtGui, "detail")
        title = str(getattr(panel, "title", "") or "").strip() or translate(
            "BIM_PlanEdit",
            "Context",
        )
        self._add_integration_card_header(QtGui, layout, block, title)

        subtitle = str(getattr(panel, "subtitle", "") or "").strip()
        if subtitle:
            subtitle_label = self._make_wrapped_plain_label(QtGui, subtitle, block)
            self._set_integration_style_property(subtitle_label, "planPanelSummary", "true")
            layout.addWidget(subtitle_label)

        for row in tuple(getattr(panel, "summary_rows", ()) or ()):
            layout.addWidget(
                self._make_summary_meta_row(
                    QtGui,
                    block,
                    getattr(row, "label", ""),
                    getattr(row, "value", ""),
                )
            )

        message = str(getattr(panel, "message", "") or "").strip()
        if message:
            layout.addWidget(self._make_wrapped_plain_label(QtGui, message, block))

        actions, has_primary = self._collect_provider_context_panel_actions(panel)
        self._add_integration_action_row(
            QtGui,
            block,
            layout,
            actions=actions,
            primary_first=has_primary,
        )

        for detail in tuple(getattr(panel, "details", ()) or ()):
            self._make_provider_context_panel_detail(QtGui, block, layout, detail)
        return block

    def _make_integration_details_group(self, QtGui, sections):
        group, layout = self._create_integration_card(QtGui, "detail")
        self._add_integration_card_header(
            QtGui,
            layout,
            group,
            translate("BIM_PlanEdit", "Additional details"),
        )

        expanded = any(not self._is_provider_section_collapsed(section) for section in sections)
        detail_title = translate("BIM_PlanEdit", "Provider Notes")
        detail_button = QtGui.QPushButton(
            self._build_detail_toggle_text(expanded, detail_title),
            group,
        )
        try:
            detail_button.setCheckable(True)
            detail_button.setChecked(expanded)
        except Exception:
            pass
        try:
            detail_button.setFlat(True)
            detail_button.setAutoDefault(False)
            detail_button.setSizePolicy(
                QtGui.QSizePolicy.Maximum,
                QtGui.QSizePolicy.Fixed,
            )
        except Exception:
            pass
        try:
            from PySide import QtCore

            layout.addWidget(detail_button, 0, QtCore.Qt.AlignLeft)
        except Exception:
            layout.addWidget(detail_button)

        content = QtGui.QWidget(group)
        content_layout = QtGui.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        for section in sections:
            block = self._make_integration_block(
                QtGui,
                self._format_provider_section_title(section),
                body=getattr(section, "body", ""),
                actions=section.actions,
            )
            content_layout.addWidget(block)
        layout.addWidget(content)

        content.setVisible(expanded)

        def toggle_details(checked):
            is_expanded = bool(checked)
            content.setVisible(is_expanded)
            detail_button.setText(self._build_detail_toggle_text(is_expanded, detail_title))

        try:
            detail_button.toggled.connect(toggle_details)
        except Exception:
            pass
        return group

    def _sort_provider_tools(self, tools):
        return tuple(
            sorted(
                tuple(tools or ()),
                key=lambda tool: (
                    str(getattr(tool, "group", "") or ""),
                    int(getattr(tool, "priority", 0) or 0),
                    str(getattr(tool, "label", "") or ""),
                    str(getattr(tool, "key", "") or ""),
                ),
            )
        )

    def _build_provider_overlay_legend_items(self, overlays):
        items = []
        seen = set()
        for overlay in tuple(overlays or ()):
            if not bool(getattr(overlay, "visible", True)):
                continue
            provider_id = str(getattr(overlay, "provider_id", "") or "").strip()
            overlay_key = str(getattr(overlay, "key", "") or "").strip()
            if not provider_id or not overlay_key:
                continue
            identity = (provider_id, overlay_key)
            if identity in seen:
                continue
            seen.add(identity)
            label = str(getattr(overlay, "label", "") or "").strip() or overlay_key
            provider_label = self.session.get_plan_provider_display_name(provider_id)
            if provider_label:
                label = translate("BIM_PlanEdit", "{provider}: {label}").format(
                    provider=provider_label,
                    label=label,
                )
            category = self.session.get_plan_provider_overlay_category(overlay)
            items.append(
                (
                    provider_id,
                    overlay_key,
                    label,
                    tuple(getattr(overlay, "color", ()) or ()),
                    self.session.is_plan_provider_overlay_enabled(overlay),
                    category,
                )
            )
        return tuple(items)

    def _get_provider_overlay_mode_options(self):
        return (
            ("architecture", translate("BIM_PlanEdit", "Architecture")),
            ("electrical", translate("BIM_PlanEdit", "Electrical")),
            ("plumbing", translate("BIM_PlanEdit", "Plumbing")),
            ("all", translate("BIM_PlanEdit", "All")),
        )

    def _format_provider_overlay_mode_label(self, mode):
        mode_key = str(mode or "").strip().lower()
        for option_key, option_label in self._get_provider_overlay_mode_options():
            if option_key == mode_key:
                return option_label
        return translate("BIM_PlanEdit", "Architecture")

    def _filter_provider_overlay_legend_items_for_mode(self, items, active_mode=None):
        mode_key = (
            str(
                active_mode
                or getattr(self.session, "get_plan_provider_overlay_mode", lambda: "architecture")()
            )
            .strip()
            .lower()
        )
        if mode_key == "all":
            return tuple(items or ())
        return tuple(
            item for item in tuple(items or ()) if len(item) > 5 and str(item[5] or "") == mode_key
        )

    def _group_provider_overlay_legend_items(self, items, active_mode=None):
        grouped = []
        groups_by_key = {}
        for item in self._filter_provider_overlay_legend_items_for_mode(
            items, active_mode=active_mode
        ):
            category = str(item[5] or "").strip().lower() if len(item) > 5 else "architecture"
            if category not in groups_by_key:
                groups_by_key[category] = []
                grouped.append(category)
            groups_by_key[category].append(item)
        return tuple(
            (
                category,
                self._format_provider_overlay_mode_label(category),
                tuple(groups_by_key.get(category, ())),
            )
            for category in grouped
        )

    def _make_provider_overlay_legend_block(self, QtGui, items, active_mode="architecture"):
        block, layout = self._create_integration_card(QtGui, "utility")
        self._add_integration_card_header(
            QtGui,
            layout,
            block,
            translate("BIM_PlanEdit", "Overlays"),
        )

        content = QtGui.QWidget(block)
        content_layout = QtGui.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        layout.addWidget(content)

        self._integration_overlay_block = block
        self._integration_overlay_content_layout = content_layout
        self._refresh_provider_overlay_legend_block(items, active_mode=active_mode)
        return block

    def _format_provider_overlay_color(self, color):
        rgb = []
        for value in tuple(color or ())[:3]:
            try:
                channel = float(value)
            except (TypeError, ValueError):
                channel = 0.0
            if channel <= 1.0:
                channel *= 255.0
            rgb.append(max(0, min(255, int(round(channel)))))
        while len(rgb) < 3:
            rgb.append(0)
        return "rgb({}, {}, {})".format(rgb[0], rgb[1], rgb[2])

    def _set_integration_panel_visible(self, visible):
        if self.integration_panel is None:
            return
        try:
            self.integration_panel.setVisible(bool(visible))
        except Exception:
            pass

    def _set_widget_updates_enabled(self, widget, enabled):
        if widget is None:
            return
        try:
            widget.setUpdatesEnabled(bool(enabled))
        except Exception:
            pass

    def _refresh_widget_geometry(self, widget):
        if widget is None:
            return
        try:
            widget.updateGeometry()
        except Exception:
            pass
        try:
            widget.update()
        except Exception:
            pass

    def _reset_integration_panel_dynamic_refs(self):
        self._integration_overlay_block = None
        self._integration_overlay_content_layout = None

    def _hide_integration_panel(self):
        self._integration_panel_state = None
        self._integration_action_buttons = []
        self._integration_overlay_checkboxes = []
        self._reset_integration_panel_dynamic_refs()
        if self.integration_summary is not None:
            try:
                self.integration_summary.clear()
            except Exception:
                pass
        self._clear_layout(self.integration_content_layout)
        self._set_integration_panel_visible(False)

    def _set_integration_summary_text(
        self,
        issues,
        sections,
        tools=(),
        overlay_items=(),
        summary_sections=(),
        context_panel=None,
    ):
        if self.integration_summary is None:
            return
        if tuple(summary_sections or ()) or context_panel is not None:
            self.integration_summary.clear()
            try:
                self.integration_summary.setVisible(False)
            except Exception:
                pass
            return
        parts = []
        issue_count = len(issues or ())
        section_count = len(sections or ())
        tool_count = len(tools or ())
        overlay_count = len(overlay_items or ())
        if issue_count:
            parts.append(translate("BIM_PlanEdit", "{count} issue(s)").format(count=issue_count))
        if tool_count:
            parts.append(translate("BIM_PlanEdit", "{count} tool(s)").format(count=tool_count))
        if overlay_count:
            parts.append(
                translate("BIM_PlanEdit", "{count} overlay(s)").format(count=overlay_count)
            )
        if section_count:
            parts.append(
                translate("BIM_PlanEdit", "{count} section(s)").format(count=section_count)
            )
        summary = (
            translate(
                "BIM_PlanEdit",
                "Plan guidance: {details}.",
            ).format(details=", ".join(parts))
            if parts
            else ""
        )
        self.integration_summary.setText(summary)
        try:
            self.integration_summary.setVisible(bool(summary))
        except Exception:
            pass

    def _queue_integration_panel_refresh(self, delay_ms=None):
        if self.form is None or self._session_is_inactive():
            return
        self._integration_refresh_queued = True
        self._integration_refresh_generation += 1
        generation = self._integration_refresh_generation
        if delay_ms is None:
            delay_ms = self._INTEGRATION_REFRESH_DELAY_MS
        try:
            from PySide import QtCore

            panel_ref = weakref.ref(self)
            QtCore.QTimer.singleShot(
                int(delay_ms),
                lambda generation=generation, panel_ref=panel_ref: (
                    _run_queued_integration_panel_refresh(panel_ref, generation)
                ),
            )
        except Exception:
            self._run_queued_integration_panel_refresh(generation)

    def _run_queued_integration_panel_refresh(self, generation=None):
        if not self._integration_refresh_queued:
            return
        if generation is not None and generation != self._integration_refresh_generation:
            return
        if self._session_is_inactive():
            self._integration_refresh_queued = False
            return
        with self.session._plan_perf_trace_event("queued_integration_panel_refresh"):
            self._integration_refresh_queued = False
            self._refresh_integration_panel(defer=False)

    def _set_provider_overlay_mode_combo_value(self, active_mode):
        combo = self._integration_overlay_mode_combo
        if combo is None:
            return
        current_index = combo.findData(str(active_mode or "architecture"))
        if current_index < 0:
            current_index = 0
        if combo.currentIndex() == current_index:
            return
        try:
            combo.blockSignals(True)
            combo.setCurrentIndex(current_index)
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _refresh_provider_overlay_legend_block(self, items, active_mode="architecture"):
        if self._integration_overlay_content_layout is None:
            return
        try:
            from PySide import QtGui
        except Exception:
            return
        parent = self._integration_overlay_block or self.integration_panel
        self._set_widget_updates_enabled(parent, False)
        try:
            self._set_provider_overlay_mode_combo_value(active_mode)
            self._integration_overlay_checkboxes = []
            self._clear_layout(self._integration_overlay_content_layout)

            grouped_items = self._group_provider_overlay_legend_items(
                items,
                active_mode=active_mode,
            )
            if not grouped_items:
                empty_label = self._make_wrapped_plain_label(
                    QtGui,
                    translate(
                        "BIM_PlanEdit",
                        "No overlays are available for {mode}.",
                    ).format(
                        mode=self._format_provider_overlay_mode_label(active_mode),
                    ),
                    parent,
                )
                self._integration_overlay_content_layout.addWidget(empty_label)
                return

            for category, category_label, category_items in grouped_items:
                heading = self._make_wrapped_plain_label(
                    QtGui,
                    category_label,
                    parent,
                    bold=True,
                )
                self._set_integration_style_property(
                    heading,
                    "planSubsectionTitle",
                    "true",
                )
                self._integration_overlay_content_layout.addWidget(heading)
                for (
                    provider_id,
                    overlay_key,
                    label,
                    color,
                    checked,
                    _item_category,
                ) in category_items:
                    row = QtGui.QHBoxLayout()
                    row.setSpacing(6)
                    swatch = QtGui.QLabel(parent)
                    swatch.setFixedSize(12, 12)
                    swatch.setStyleSheet(
                        "background-color: {}; border: 1px solid #555;".format(
                            self._format_provider_overlay_color(color)
                        )
                    )
                    row.addWidget(swatch)

                    checkbox = QtGui.QCheckBox(label, parent)
                    checkbox.setChecked(bool(checked))
                    checkbox.toggled.connect(
                        lambda checked, current_provider_id=provider_id, current_overlay_key=overlay_key: (
                            self.on_provider_overlay_visibility_changed(
                                current_provider_id,
                                current_overlay_key,
                                checked,
                            )
                        )
                    )
                    self._integration_overlay_checkboxes.append(checkbox)
                    row.addWidget(checkbox)
                    row.addStretch(1)
                    self._integration_overlay_content_layout.addLayout(row)
        finally:
            self._set_widget_updates_enabled(parent, True)
            self._refresh_widget_geometry(parent)

    def _refresh_integration_panel(self, defer=False):
        with self.session._plan_perf_trace_span("refresh_integration_panel"):
            if (
                self.integration_panel is None
                or self.integration_summary is None
                or self.integration_content_layout is None
            ):
                return
            if self._session_is_inactive():
                self._integration_refresh_queued = False
                self._hide_integration_panel()
                return
            if self.session._plan_provider_integrations_disabled():
                self.session._plan_perf_count("integration_panel_disabled")
                self._integration_refresh_queued = False
                self._hide_integration_panel()
                return
            if defer:
                self.session._plan_perf_count("integration_panel_deferred_refreshes")
                self._queue_integration_panel_refresh()
                return
            self._integration_refresh_queued = False
            self._integration_refresh_generation += 1
            with self.session._plan_provider_refresh_cache_scope():
                with self.session._plan_perf_trace_span("collect_plan_provider_tools"):
                    tools = tuple(self.session.get_plan_provider_tools())
                with self.session._plan_perf_trace_span("collect_plan_provider_overlays"):
                    overlays = tuple(self.session.get_plan_provider_overlays())
                with self.session._plan_perf_trace_span("collect_plan_provider_issues"):
                    issues = tuple(self.session.get_plan_provider_issues())
                with self.session._plan_perf_trace_span("collect_plan_provider_context_panels"):
                    context_panels = tuple(self.session.get_plan_provider_context_panels())
                with self.session._plan_perf_trace_span("collect_plan_provider_inspector_sections"):
                    sections = tuple(self.session.get_plan_provider_inspector_sections())
            queue_overlay_refresh = getattr(
                self.session,
                "queue_plan_provider_overlay_sync",
                None,
            )
            if not callable(queue_overlay_refresh):
                queue_overlay_refresh = getattr(
                    self.session,
                    "queue_plan_provider_overlay_refresh",
                    None,
                )
            if callable(queue_overlay_refresh):
                queue_overlay_refresh()
            tools = self._sort_provider_tools(tools)
            overlay_items = self._build_provider_overlay_legend_items(overlays)
            overlay_mode = self.session.get_plan_provider_overlay_mode()
            self._set_provider_overlay_mode_combo_value(overlay_mode)
            active_overlay_items = self._filter_provider_overlay_legend_items_for_mode(
                overlay_items,
                active_mode=overlay_mode,
            )
            summary_sections, regular_sections, detail_sections = self._partition_provider_sections(
                sections
            )
            context_panel = self._resolve_provider_context_panel(context_panels)
            context_panel_actions, _has_context_primary = (
                self._collect_provider_context_panel_actions(context_panel)
                if context_panel is not None
                else ((), False)
            )
            state = (tools, overlay_items, issues, sections, context_panel)
            if (
                not tools
                and not overlay_items
                and not issues
                and not sections
                and context_panel is None
            ):
                self._hide_integration_panel()
                return
            self._set_integration_summary_text(
                issues,
                sections,
                tools=tools,
                overlay_items=active_overlay_items,
                summary_sections=summary_sections,
                context_panel=context_panel,
            )
            if state != self._integration_panel_state:
                self._integration_panel_state = state
                self._integration_action_buttons = []
                self._integration_overlay_checkboxes = []
                self._reset_integration_panel_dynamic_refs()
                self._clear_layout(self.integration_content_layout)
                from PySide import QtGui

                grouped_issue_sets = self._group_provider_issues(issues)
                promoted_action_ids = self._collect_action_identities(
                    action
                    for section in summary_sections
                    for action in tuple(getattr(section, "actions", ()) or ())
                )
                hidden_tool_action_labels = self._collect_action_labels(
                    tuple(
                        action
                        for section in summary_sections
                        for action in tuple(getattr(section, "actions", ()) or ())
                    )
                    + tuple(
                        action
                        for issue_group in grouped_issue_sets
                        for action in tuple(
                            self._filter_integration_actions(
                                self._collect_provider_issue_group_actions(issue_group),
                                hidden_action_ids=promoted_action_ids,
                            )
                        )
                    )
                    + tuple(
                        action
                        for section in regular_sections
                        for action in tuple(getattr(section, "actions", ()) or ())
                    )
                    + tuple(context_panel_actions)
                )
                for section in summary_sections:
                    block = self._make_summary_section_block(QtGui, section)
                    self.integration_content_layout.addWidget(block)
                if context_panel is not None:
                    self.integration_content_layout.addWidget(
                        self._make_integration_group_heading(
                            QtGui,
                            self._get_provider_context_panel_heading(context_panel),
                        )
                    )
                    self.integration_content_layout.addWidget(
                        self._make_provider_context_panel_block(QtGui, context_panel)
                    )
                if issues:
                    self.integration_content_layout.addWidget(
                        self._make_integration_group_heading(
                            QtGui,
                            translate("BIM_PlanEdit", "Action Needed"),
                        )
                    )
                for issue_group in grouped_issue_sets:
                    block = self._make_provider_issue_block(
                        QtGui,
                        issue_group,
                        hidden_action_ids=promoted_action_ids,
                    )
                    if block is not None:
                        self.integration_content_layout.addWidget(block)
                if tools or overlay_items:
                    self.integration_content_layout.addWidget(
                        self._make_integration_group_heading(
                            QtGui,
                            translate("BIM_PlanEdit", "Utilities"),
                        )
                    )
                if tools:
                    block = self._make_integration_block(
                        QtGui,
                        translate("BIM_PlanEdit", "Tools"),
                        actions=tools,
                        card_role="utility",
                        hidden_action_ids=promoted_action_ids,
                        hidden_action_labels=hidden_tool_action_labels,
                        action_columns=3,
                        default_action_role="utility",
                    )
                    self.integration_content_layout.addWidget(block)
                if overlay_items:
                    block = self._make_provider_overlay_legend_block(
                        QtGui,
                        overlay_items,
                        active_mode=overlay_mode,
                    )
                    if block is not None:
                        self.integration_content_layout.addWidget(block)
                if regular_sections or detail_sections:
                    self.integration_content_layout.addWidget(
                        self._make_integration_group_heading(
                            QtGui,
                            translate("BIM_PlanEdit", "More Context"),
                        )
                    )
                for section in regular_sections:
                    block = self._make_integration_block(
                        QtGui,
                        self._format_provider_section_title(section),
                        body=getattr(section, "body", ""),
                        actions=section.actions,
                        card_role="detail",
                        hidden_action_ids=promoted_action_ids,
                    )
                    self.integration_content_layout.addWidget(block)
                if detail_sections:
                    group = self._make_integration_details_group(
                        QtGui,
                        detail_sections,
                    )
                    self.integration_content_layout.addWidget(group)
                self.integration_content_layout.addStretch(1)
            elif overlay_items:
                self._refresh_provider_overlay_legend_block(
                    overlay_items,
                    active_mode=overlay_mode,
                )
            self._set_integration_panel_visible(True)

    def _get_space_type_display_options(self, options):
        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)

        common = [option for option in self._COMMON_SPACE_TYPES if option in seen]
        remaining = [option for option in normalized if option not in common]
        if common and remaining:
            return common + [None] + remaining
        return common or remaining

    def _set_space_type_combo_options(self, options):
        from PySide import QtCore

        if self.space_type_combo is None:
            return

        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)

        self.space_type_combo.clear()
        for option in self._get_space_type_display_options(normalized):
            if option is None:
                try:
                    self.space_type_combo.insertSeparator(self.space_type_combo.count())
                except Exception:
                    pass
                continue
            self.space_type_combo.addItem(option, option)
            index = self.space_type_combo.count() - 1
            try:
                self.space_type_combo.setItemData(index, option, QtCore.Qt.ToolTipRole)
            except Exception:
                pass

        if self._space_type_option_model is not None:
            try:
                self._space_type_option_model.setStringList(normalized)
            except Exception:
                pass

    def _find_space_type_combo_index(self, value):
        value = str(value or "").strip().lower()
        if not value or self.space_type_combo is None:
            return -1
        for index in range(self.space_type_combo.count()):
            item_value = self.space_type_combo.itemData(index)
            if item_value is None:
                item_value = self.space_type_combo.itemText(index)
            if str(item_value or "").strip().lower() == value:
                return index
        return -1

    def _commit_space_type_combo_text(self, value):
        if self.space_type_combo is None:
            return False

        if hasattr(value, "data"):
            try:
                value = value.data()
            except Exception:
                pass

        index = self._find_space_type_combo_index(value)
        if index >= 0:
            self.space_type_combo.setCurrentIndex(index)
            line_edit = self.space_type_combo.lineEdit()
            if line_edit is not None:
                line_edit.setText(self.space_type_combo.itemText(index))
            return True

        line_edit = self.space_type_combo.lineEdit()
        current_index = self.space_type_combo.currentIndex()
        if line_edit is not None:
            if current_index >= 0:
                line_edit.setText(self.space_type_combo.itemText(current_index))
            else:
                line_edit.clear()
        return False

    def _format_region_parent_space_label(self, space):
        label = str(getattr(space, "Label", "") or "").strip()
        name = str(getattr(space, "Name", "") or "").strip()
        if label and name and label != name:
            return f"{label} ({name})"
        return label or name or translate("BIM_PlanEdit", "Unnamed Space")

    def _get_editor_object_key(self, obj):
        if obj is None:
            return None
        return (
            getattr(getattr(obj, "Document", None), "Name", None),
            getattr(obj, "Name", None),
        )

    def _normalize_space_type_options(self, options):
        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)
        return tuple(normalized)

    def _get_cached_space_type_options(self, space, current_type):
        if self._space_type_options_cache is None:
            options = []
            try:
                options = list(space.getEnumerationsOfProperty("SpaceType") or [])
            except Exception:
                options = []
            self._space_type_options_cache = self._normalize_space_type_options(options)
        normalized = list(self._space_type_options_cache or ())
        current_type = str(current_type or "").strip()
        if current_type and current_type not in normalized:
            normalized.append(current_type)
        return tuple(normalized)

    def _get_space_boundary_signature(self, space):
        signature = []
        for boundary in getattr(space, "Boundaries", []) or []:
            try:
                obj = boundary[0]
                subnames = boundary[1]
            except Exception:
                continue
            signature.append(
                (
                    self._get_editor_object_key(obj),
                    tuple(str(subname or "") for subname in (subnames or [])),
                )
            )
        return tuple(signature)

    def _get_region_parent_space_candidates(self, current_parent=None):
        candidates = []
        seen = set()
        active_storey = self.session.active_storey

        for obj in getattr(self.session.doc, "Objects", []) or []:
            semantic_obj = self.session._get_plan_semantic_object(obj)
            if not self.session._is_plan_space_object(semantic_obj):
                continue
            name = getattr(semantic_obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append(semantic_obj)

        current_parent = self.session._get_plan_semantic_object(current_parent)
        if self.session._is_plan_space_object(current_parent):
            current_name = getattr(current_parent, "Name", None)
            if current_name and current_name not in seen:
                candidates.append(current_parent)

        def sort_key(space):
            try:
                in_active_storey = bool(
                    active_storey and active_storey in (space.InListRecursive or [])
                )
            except Exception:
                in_active_storey = False
            label = str(getattr(space, "Label", "") or "").strip().lower()
            name = str(getattr(space, "Name", "") or "").strip().lower()
            return (0 if in_active_storey else 1, label or name, name)

        return sorted(candidates, key=sort_key)

    def _set_region_parent_space_combo_options(self, region):
        if self.region_parent_space_combo is None:
            return

        current_parent = self.session._get_plan_semantic_object(
            getattr(region, "ParentSpace", None)
        )
        candidates = self._get_region_parent_space_candidates(current_parent=current_parent)
        self._region_parent_space_items = [None] + candidates

        self.region_parent_space_combo.clear()
        self.region_parent_space_combo.addItem(translate("BIM_PlanEdit", "None"))
        for space in candidates:
            self.region_parent_space_combo.addItem(self._format_region_parent_space_label(space))

        current_name = getattr(current_parent, "Name", None) if current_parent else None
        current_index = 0
        if current_name:
            for index, space in enumerate(self._region_parent_space_items):
                if getattr(space, "Name", None) == current_name:
                    current_index = index
                    break
        self.region_parent_space_combo.setCurrentIndex(current_index)

    def _build_space_editor(self, QtGui):
        from PySide import QtCore

        editor = QtGui.QGroupBox(translate("BIM_PlanEdit", "Space"))
        editor.setVisible(False)
        layout = QtGui.QVBoxLayout(editor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QtGui.QFormLayout()
        form.setSpacing(6)

        self.space_label_edit = QtGui.QLineEdit(editor)
        self.space_label_edit.editingFinished.connect(self.on_space_label_edited)
        form.addRow(translate("BIM_PlanEdit", "Label"), self.space_label_edit)

        self.space_type_combo = QtGui.QComboBox(editor)
        self.space_type_combo.setEditable(True)
        self.space_type_combo.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.space_type_combo.setMaxVisibleItems(12)
        if hasattr(QtGui.QComboBox, "AdjustToMinimumContentsLengthWithIcon"):
            self.space_type_combo.setSizeAdjustPolicy(
                QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
        if hasattr(self.space_type_combo, "setMinimumContentsLength"):
            self.space_type_combo.setMinimumContentsLength(18)
        view = self.space_type_combo.view()
        if view is not None:
            if hasattr(view, "setTextElideMode"):
                view.setTextElideMode(QtCore.Qt.ElideRight)
            if hasattr(view, "setUniformItemSizes"):
                view.setUniformItemSizes(True)
        self._space_type_option_model = QtCore.QStringListModel([], self.space_type_combo)
        self._space_type_completer = QtGui.QCompleter(
            self._space_type_option_model,
            self.space_type_combo,
        )
        self._space_type_completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
        self._space_type_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        if hasattr(self._space_type_completer, "setFilterMode"):
            self._space_type_completer.setFilterMode(QtCore.Qt.MatchContains)
        self.space_type_combo.setCompleter(self._space_type_completer)
        try:
            self._space_type_completer.activated[str].connect(
                self.on_space_type_completion_activated
            )
        except Exception:
            self._space_type_completer.activated.connect(self.on_space_type_completion_activated)
        line_edit = self.space_type_combo.lineEdit()
        if line_edit is not None:
            if hasattr(line_edit, "setPlaceholderText"):
                line_edit.setPlaceholderText(translate("BIM_PlanEdit", "Search space types"))
            if hasattr(line_edit, "setClearButtonEnabled"):
                line_edit.setClearButtonEnabled(True)
            line_edit.editingFinished.connect(self.on_space_type_editing_finished)
        self.space_type_combo.currentIndexChanged.connect(self.on_space_type_changed)
        form.addRow(translate("BIM_PlanEdit", "Type"), self.space_type_combo)

        layout.addLayout(form)

        boundaries_label = QtGui.QLabel(translate("BIM_PlanEdit", "Boundaries"), editor)
        layout.addWidget(boundaries_label)

        self.space_boundary_list = QtGui.QListWidget(editor)
        self.space_boundary_list.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.space_boundary_list.setMinimumHeight(96)
        layout.addWidget(self.space_boundary_list)

        button_row = QtGui.QHBoxLayout()
        button_row.setSpacing(6)

        self.space_add_button = self._make_button(QtGui, "Add", self.on_space_add_clicked)
        self.space_remove_button = self._make_button(QtGui, "Remove", self.on_space_remove_clicked)
        self.space_text_button = self._make_button(
            QtGui,
            "Set Text Position",
            self.on_space_text_clicked,
        )

        button_row.addWidget(self.space_add_button)
        button_row.addWidget(self.space_remove_button)
        button_row.addWidget(self.space_text_button)
        layout.addLayout(button_row)

        return editor

    def _build_region_editor(self, QtGui):
        editor = QtGui.QGroupBox(translate("BIM_PlanEdit", "Region"))
        editor.setVisible(False)
        layout = QtGui.QVBoxLayout(editor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QtGui.QFormLayout()
        form.setSpacing(6)

        self.region_label_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_label_edit, "setClearButtonEnabled"):
            self.region_label_edit.setClearButtonEnabled(True)
        self.region_label_edit.editingFinished.connect(self.on_region_label_edited)
        form.addRow(translate("BIM_PlanEdit", "Label"), self.region_label_edit)

        self.region_scheme_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_scheme_edit, "setPlaceholderText"):
            self.region_scheme_edit.setPlaceholderText(translate("BIM_PlanEdit", "Program"))
        if hasattr(self.region_scheme_edit, "setClearButtonEnabled"):
            self.region_scheme_edit.setClearButtonEnabled(True)
        self.region_scheme_edit.editingFinished.connect(self.on_region_scheme_edited)
        form.addRow(translate("BIM_PlanEdit", "Scheme"), self.region_scheme_edit)

        self.region_type_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_type_edit, "setPlaceholderText"):
            self.region_type_edit.setPlaceholderText(translate("BIM_PlanEdit", "Zone"))
        if hasattr(self.region_type_edit, "setClearButtonEnabled"):
            self.region_type_edit.setClearButtonEnabled(True)
        self.region_type_edit.editingFinished.connect(self.on_region_type_edited)
        form.addRow(translate("BIM_PlanEdit", "Type"), self.region_type_edit)

        self.region_parent_space_combo = QtGui.QComboBox(editor)
        self.region_parent_space_combo.currentIndexChanged.connect(
            self.on_region_parent_space_changed
        )
        form.addRow(translate("BIM_PlanEdit", "Parent Space"), self.region_parent_space_combo)

        layout.addLayout(form)

        note = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan regions store semantic zoning metadata and keep a polygonal footprint in plan.",
            ),
            editor,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        return editor

    def _build_window_editor(self, QtGui):
        editor = QtGui.QGroupBox(translate("BIM_PlanEdit", "Window"))
        editor.setVisible(False)
        layout = QtGui.QVBoxLayout(editor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QtGui.QFormLayout()
        form.setSpacing(6)

        self.window_width_edit = QtGui.QLineEdit(editor)
        if hasattr(self.window_width_edit, "setClearButtonEnabled"):
            self.window_width_edit.setClearButtonEnabled(True)
        if hasattr(self.window_width_edit, "setPlaceholderText"):
            self.window_width_edit.setPlaceholderText(translate("BIM_PlanEdit", "950 mm"))
        self.window_width_edit.textChanged.connect(self.on_window_width_text_changed)
        self.window_width_edit.returnPressed.connect(self.on_window_size_apply_clicked)
        form.addRow(translate("BIM_PlanEdit", "Width"), self.window_width_edit)

        self.window_height_edit = QtGui.QLineEdit(editor)
        if hasattr(self.window_height_edit, "setClearButtonEnabled"):
            self.window_height_edit.setClearButtonEnabled(True)
        if hasattr(self.window_height_edit, "setPlaceholderText"):
            self.window_height_edit.setPlaceholderText(translate("BIM_PlanEdit", "1200 mm"))
        self.window_height_edit.textChanged.connect(self.on_window_height_text_changed)
        self.window_height_edit.returnPressed.connect(self.on_window_size_apply_clicked)
        form.addRow(translate("BIM_PlanEdit", "Height"), self.window_height_edit)

        self.window_preset_combo = QtGui.QComboBox(editor)
        if hasattr(QtGui.QComboBox, "AdjustToMinimumContentsLengthWithIcon"):
            self.window_preset_combo.setSizeAdjustPolicy(
                QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
        if hasattr(self.window_preset_combo, "setMinimumContentsLength"):
            self.window_preset_combo.setMinimumContentsLength(18)
        self.window_preset_combo.currentIndexChanged.connect(
            self.on_window_preset_selection_changed
        )
        form.addRow(translate("BIM_PlanEdit", "Style"), self.window_preset_combo)

        layout.addLayout(form)

        self.window_preset_note = QtGui.QLabel(editor)
        self.window_preset_note.setWordWrap(True)
        layout.addWidget(self.window_preset_note)

        button_row = QtGui.QHBoxLayout()
        button_row.setSpacing(6)
        self.window_size_apply_button = self._make_button(
            QtGui,
            "Apply Size",
            self.on_window_size_apply_clicked,
        )
        button_row.addWidget(self.window_size_apply_button)
        self.window_preset_apply_button = self._make_button(
            QtGui,
            "Apply Style",
            self.on_window_preset_apply_clicked,
        )
        button_row.addWidget(self.window_preset_apply_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        return editor

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
                self.storey_combo.addItem(self.session.get_storey_label(storey))

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
            join_type_index = self.join_type_combo.findData(self.session.get_plan_join_type())
            if join_type_index >= 0:
                self.join_type_combo.setCurrentIndex(join_type_index)
        finally:
            try:
                self.join_type_combo.blockSignals(False)
            except Exception:
                pass

    def _hide_space_editor(self):
        if self.space_editor is not None:
            try:
                self.space_editor.setVisible(False)
            except Exception:
                pass
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None

    def _hide_region_editor(self):
        if self.region_editor is None:
            return
        try:
            self.region_editor.setVisible(False)
        except Exception:
            pass

    def _hide_window_editor(self):
        if self.window_editor is None:
            return
        try:
            self.window_editor.setVisible(False)
        except Exception:
            pass
        self._window_editor_state = None

    def on_provider_action_clicked(self, action):
        if action is None:
            return
        if (
            getattr(action, "interaction", PlanToolInteraction.IMMEDIATE)
            == PlanToolInteraction.POINT
        ):
            self.session.start_plan_provider_point_tool(action)
            return
        self.session.execute_plan_provider_action(
            getattr(action, "provider_id", ""),
            getattr(action, "key", ""),
            transaction_label=getattr(action, "transaction_label", ""),
        )

    def on_provider_overlay_visibility_changed(self, provider_id, overlay_key, visible):
        self.session.set_plan_provider_overlay_visible(provider_id, overlay_key, visible)

    def on_provider_overlay_mode_changed(self, mode):
        getattr(self.session, "set_plan_provider_overlay_mode", lambda _mode: False)(mode)

    def _set_status_text(self, text):
        text = str(text or "")
        if self.status is None or text == self._status_text_state:
            return
        self.status.setText(text)
        self._status_text_state = text

    def _build_status_text(self):
        tool = self.session.current_tool
        selected_kind, selected_obj = self.session.selection.get_selected_plan_target()
        selected_state = self.session._format_plan_target_selection_state(
            selected_kind, selected_obj
        )
        provider_state = self.session._format_provider_selected_object_state()
        if tool == "Join" and selected_kind == "wall" and selected_obj is not None:
            target_wall, joint, detail = self.session._get_plan_join_candidate_state()
            selection_state = translate("BIM_PlanEdit", "Source wall: {label}").format(
                label=self.session._get_plan_target_display_label(selected_obj)
            )
            selection_help = translate(
                "BIM_PlanEdit",
                "Join type: {joint_type}\n{pair_state}\n{action}",
            ).format(
                joint_type=self.session.get_plan_join_type_label(),
                pair_state=detail or translate("BIM_PlanEdit", "Candidate wall: none"),
                action=self.session._get_plan_join_mode_action_text(target_wall, joint),
            )
        elif tool == "Pick Space Region":
            selection_state = translate("BIM_PlanEdit", "Space creation: pick region")
            selection_help = translate(
                "BIM_PlanEdit",
                "Multiple enclosed regions were found. Hover a dashed outline, then click to create that space.",
            )
            targets = self.session.selection.get_selected_plan_targets()
            if targets:
                selection_help = "{}\n{}".format(
                    selection_help,
                    translate("BIM_PlanEdit", "Boundary candidates: {summary}").format(
                        summary=self.session._summarize_plan_targets(targets)
                    ),
                )
            candidate_count = len(self.session._space_region_candidates)
            if candidate_count:
                selection_help = "{}\n{}".format(
                    selection_help,
                    translate("BIM_PlanEdit", "{count} enclosed regions are available.").format(
                        count=candidate_count
                    ),
                )
            hovered_candidate = self.session._hovered_space_region_candidate
            if hovered_candidate:
                selection_help = "{}\n{}".format(
                    selection_help,
                    translate("BIM_PlanEdit", "Hovered region area: {area}").format(
                        area=self.session._format_space_region_candidate_area(hovered_candidate)
                    ),
                )
        elif tool == "Region":
            selection_state = translate("BIM_PlanEdit", "Region: draw polygon")
            selection_help = translate(
                "BIM_PlanEdit",
                "Click polygon points to define a semantic plan region. Press Enter to finish, or click near the first point to close.",
            )
            if self.session._is_plan_space_object(self.session._plan_region_parent_space):
                selection_help = "{}\n{}".format(
                    selection_help,
                    translate("BIM_PlanEdit", "Parent space: {label}").format(
                        label=self.session._plan_region_parent_space.Label
                    ),
                )
        elif tool == "Separator":
            selection_state = translate("BIM_PlanEdit", "Separator: place divider")
            selection_help = translate(
                "BIM_PlanEdit",
                "Click two points to place a room divider that can split Arch Spaces.",
            )
        elif tool == "Window":
            selection_state = translate("BIM_PlanEdit", "Window: place on wall")
            selection_help = translate(
                "BIM_PlanEdit",
                "Click along the selected or hovered wall to place a hosted window.",
            )
        elif tool == "Provider Point":
            selection_state = self.session._get_provider_point_tool_label()
            selection_help = self.session._get_provider_point_tool_prompt()
        elif selected_kind == "opening" and selected_obj is not None:
            selection_state = selected_state
            selection_help = self.session._format_opening_selection_help(selected_obj)
        elif selected_kind == "symbol" and selected_obj is not None:
            selection_state = selected_state
            if self.session.current_tool == "Rotate Symbol":
                if self.session._symbol_rotation_snap_enabled():
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use in-view handles to rotate the selected symbol instance. Rotation snaps to {snap} by default; hold Shift for free angle.",
                    ).format(snap=self.session._format_symbol_rotation_snap_label())
                else:
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use in-view handles to rotate the selected symbol instance.",
                    )
            else:
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use in-view handles to move or rotate the selected symbol instance.",
                )
        elif selected_kind == "region" and selected_obj is not None:
            selection_state = selected_state
            selection_help = translate(
                "BIM_PlanEdit",
                "Use the region controls below to edit label, scheme, type, and parent space.",
            )
        elif selected_kind == "space" and selected_obj is not None:
            selection_state = selected_state
            selection_help = translate(
                "BIM_PlanEdit",
                "Use the space controls below to edit label, type, boundaries, and text position.",
            )
        elif selected_kind == "provider" and selected_obj is not None:
            selection_state = selected_state
            selection_help = self.session._format_provider_target_help(selected_obj)
        elif selected_kind == "wall" and selected_obj is not None:
            selection_state = selected_state
            if self.session.is_selected_wall_endpoint_editable():
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use wall grips in the viewport to stretch or move the selected wall.",
                )
            else:
                selection_help = translate(
                    "BIM_PlanEdit",
                    "This wall can be reviewed in plan, but grip editing is unavailable.",
                )
        elif provider_state:
            selection_state = provider_state
            selection_help = self.session._format_provider_selected_object_help()
        else:
            selection_state = translate("BIM_PlanEdit", "No target selected")
            selection_help = translate(
                "BIM_PlanEdit",
                "Click a wall, opening, symbol, integration target, region, or space. Use create tools to add plan geometry.",
            )
        selection_summary = self.session._get_plan_selection_summary_text()
        if selection_summary:
            selection_help = "{}\n{}".format(selection_help, selection_summary)
        if self.session.current_tool == "Select":
            selection_help = "{}\n{}".format(
                selection_help,
                translate(
                    "BIM_PlanEdit",
                    "Ctrl-click adds or removes targets without replacing the current editor target.",
                ),
            )
        if self.session._plan_relation_status_message:
            selection_help = "{}\n{}".format(
                selection_help,
                self.session._plan_relation_status_message,
            )
        return "{selection_state}\n{selection_help}".format(
            selection_state=selection_state,
            selection_help=selection_help,
        )

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
        if modal_active is None:
            modal_active = self.session._is_modal_plan_interaction_active()
        selected_kind, selected_obj = self.session.selection.get_selected_plan_target()
        current_tool = self.session.current_tool
        has_wall = selected_kind == "wall" and selected_obj is not None
        can_place_window = self.session.can_place_plan_window()
        in_join_mode = current_tool == "Join"
        join_candidate = (
            self.session._get_plan_candidate_joint() is not None if in_join_mode else False
        )
        enabled = not bool(modal_active)

        if self.header_mode_label is not None:
            mode_label = current_tool
            if current_tool == "Provider Point":
                mode_label = self.session._get_provider_point_tool_label()
            self.header_mode_label.setText(
                translate("BIM_PlanEdit", "{tool} mode").format(tool=mode_label)
            )

        self._set_widget_enabled(self.join_button, enabled and has_wall)
        self._set_widget_tooltip(
            self.join_button,
            (
                translate("BIM_PlanEdit", "Select a wall before using Join.")
                if not has_wall
                else translate("BIM_PlanEdit", "Join the selected wall to another wall.")
            ),
        )

        show_join_options = has_wall or in_join_mode
        self._set_widget_visible(self.join_type_widget, show_join_options)
        self._set_widget_enabled(self.join_type_combo, enabled and show_join_options)
        self._set_widget_tooltip(
            self.join_type_combo,
            translate("BIM_PlanEdit", "Joint type used when joining wall pairs."),
        )

        self._set_widget_enabled(self.unjoin_button, enabled and in_join_mode and join_candidate)
        if not in_join_mode:
            unjoin_tip = translate(
                "BIM_PlanEdit",
                "Start Join mode and hover an existing joined wall pair.",
            )
        elif not join_candidate:
            unjoin_tip = translate(
                "BIM_PlanEdit",
                "Hover an existing joined wall pair before using Unjoin.",
            )
        else:
            unjoin_tip = translate("BIM_PlanEdit", "Remove the hovered existing wall joint.")
        self._set_widget_tooltip(self.unjoin_button, unjoin_tip)
        self._set_widget_visible(self.window_button, can_place_window or current_tool == "Window")
        self._set_widget_enabled(self.window_button, enabled and can_place_window)
        self._set_widget_tooltip(
            self.window_button,
            (
                translate(
                    "BIM_PlanEdit",
                    "Place a hosted window on the selected or hovered wall.",
                )
                if can_place_window
                else translate("BIM_PlanEdit", "Select or hover a wall before placing a window.")
            ),
        )

    def refresh_from_session(self, defer_integrations=False, refresh_integrations=True):
        with self.session._plan_perf_trace_span("refresh_task_panel_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return
            self._sync_join_type_combo_from_session()
            self._set_status_text(self._build_status_text())
            self._refresh_action_context()
            if refresh_integrations:
                self._refresh_integration_panel(defer=defer_integrations)
            self._refresh_space_editor()
            self._refresh_region_editor()
            self._refresh_window_editor()
            self._apply_modal_interaction_state(self.session._is_modal_plan_interaction_active())

    def refresh_selection_from_session(self):
        with self.session._plan_perf_trace_span("refresh_task_panel_selection_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return
            selected_kind, _selected_obj = self.session.selection.get_selected_plan_target()
            if self.session.current_tool != "Select" or selected_kind != "wall":
                self.refresh_from_session(defer_integrations=True)
                return
            self._set_status_text(self._build_status_text())
            self._refresh_action_context()
            self._refresh_integration_panel(defer=True)
            self._hide_space_editor()
            self._hide_region_editor()
            self._hide_window_editor()
            self._apply_modal_interaction_state(self.session._is_modal_plan_interaction_active())

    def refresh_provider_overlay_mode_from_session(self):
        with self.session._plan_perf_trace_span("refresh_task_panel_provider_overlay_mode_widget"):
            if self.form is None or self.integration_panel is None:
                return
            self._set_widget_updates_enabled(self.integration_panel, False)
            try:
                self._refresh_integration_panel(defer=False)
            finally:
                self._set_widget_updates_enabled(self.integration_panel, True)
                self._refresh_widget_geometry(self.integration_panel)

    def _refresh_space_editor(self):
        from PySide import QtGui

        with self.session._plan_perf_trace_span("refresh_space_editor"):
            if self.space_editor is None:
                return
            selected_kind, selected_obj = self.session.selection.get_selected_plan_target()
            space = selected_obj if selected_kind == "space" else None
            show_editor = bool(space and self.session.current_tool in ("Select", "Set Space Text"))
            if not show_editor:
                self._hide_space_editor()
                return
            try:
                self.space_editor.setVisible(True)
            except Exception:
                pass

            self._refreshing_space_editor = True
            try:
                space_key = self._get_editor_object_key(space)
                label = getattr(space, "Label", "")
                if self.space_label_edit is not None:
                    label_state = (space_key, label)
                    if label_state != self._space_editor_label_state:
                        self.space_label_edit.setText(label)
                        self._space_editor_label_state = label_state

                current_type = getattr(space, "SpaceType", "")
                options = self._get_cached_space_type_options(space, current_type)
                if self.space_type_combo is not None:
                    combo_state = (space_key, options, str(current_type or ""))
                    if combo_state != self._space_editor_combo_state:
                        self.session._plan_perf_count("space_type_options", len(options))
                        self.space_type_combo.blockSignals(True)
                        try:
                            self._set_space_type_combo_options(options)
                            current_index = self._find_space_type_combo_index(current_type)
                            if current_index >= 0:
                                self.space_type_combo.setCurrentIndex(current_index)
                            else:
                                line_edit = self.space_type_combo.lineEdit()
                                if line_edit is not None:
                                    line_edit.setText(current_type)
                        finally:
                            self.space_type_combo.blockSignals(False)
                        self._space_editor_combo_state = combo_state

                if self.space_boundary_list is not None:
                    boundary_state = (space_key, self._get_space_boundary_signature(space))
                    if boundary_state != self._space_editor_boundary_state:
                        boundary_entries = list(
                            self.session._get_space_boundary_entries(space) or []
                        )
                        self.session._plan_perf_count(
                            "space_boundary_entries", len(boundary_entries)
                        )
                        self.space_boundary_list.clear()
                        for obj, subnames in boundary_entries:
                            label = getattr(obj, "Label", getattr(obj, "Name", ""))
                            suffix = ", ".join(subnames)
                            text = f"{label}: {suffix}" if suffix else label
                            item = QtGui.QListWidgetItem(text)
                            item.setToolTip(getattr(obj, "Name", ""))
                            self.space_boundary_list.addItem(item)
                        self._space_editor_boundary_state = boundary_state
            finally:
                self._refreshing_space_editor = False

    def _refresh_region_editor(self):
        with self.session._plan_perf_trace_span("refresh_region_editor"):
            if self.region_editor is None:
                return
            selected_kind, selected_obj = self.session.selection.get_selected_plan_target()
            region = selected_obj if selected_kind == "region" else None
            show_editor = bool(region and self.session.current_tool == "Select")
            if not show_editor:
                self._hide_region_editor()
                return
            try:
                self.region_editor.setVisible(True)
            except Exception:
                pass

            self._refreshing_region_editor = True
            try:
                if self.region_label_edit is not None:
                    self.region_label_edit.setText(getattr(region, "Label", ""))
                if self.region_scheme_edit is not None:
                    self.region_scheme_edit.setText(getattr(region, "Scheme", ""))
                if self.region_type_edit is not None:
                    self.region_type_edit.setText(getattr(region, "RegionType", ""))
                if self.region_parent_space_combo is not None:
                    self.region_parent_space_combo.blockSignals(True)
                    try:
                        self._set_region_parent_space_combo_options(region)
                        self.session._plan_perf_count(
                            "region_parent_space_candidates",
                            max(0, len(self._region_parent_space_items) - 1),
                        )
                    finally:
                        self.region_parent_space_combo.blockSignals(False)
            finally:
                self._refreshing_region_editor = False

    def _get_window_preset_combo_items(self, current_style):
        items = []
        current_style = str(current_style or "").strip()
        if not current_style:
            items.append(("", translate("BIM_PlanEdit", "Custom / Current")))
        for preset in self.session._get_window_style_preset_options():
            items.append((str(preset or ""), str(preset or "")))
        return tuple(items)

    def _find_combo_data_index(self, combo, value):
        if combo is None:
            return -1
        value = str(value or "").strip()
        if not value:
            return -1
        for index in range(combo.count()):
            item_value = combo.itemData(index)
            if item_value is None:
                item_value = combo.itemText(index)
            if str(item_value or "").strip() == value:
                return index
        return -1

    def _coerce_window_length_mm(self, value):
        if value is None:
            return None
        try:
            value = value.Value
        except AttributeError:
            pass
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return float(FreeCAD.Units.Quantity(text).Value)
        except Exception:
            return None

    def _get_window_editor_target(self):
        selected_kind, selected_obj = self.session.selection.get_selected_plan_target()
        if (
            selected_kind != "opening"
            or selected_obj is None
            or self.session.current_tool != "Select"
        ):
            return None
        if (
            self.session._can_edit_window_width(selected_obj)
            or self.session._can_edit_window_height(selected_obj)
            or self.session._can_apply_window_style_preset(selected_obj)
        ):
            return selected_obj
        return None

    def _format_window_editor_note(
        self,
        current_style,
        current_width_text,
        current_height_text,
        can_edit_width,
        can_edit_height,
        can_apply_style,
    ):
        current_style = str(current_style or "").strip()
        style_text = (
            translate("BIM_PlanEdit", "Current style: {style}").format(style=current_style)
            if current_style
            else translate("BIM_PlanEdit", "Current style: Custom")
        )
        width_text = (
            translate("BIM_PlanEdit", "Current width: {width}").format(
                width=current_width_text,
            )
            if current_width_text
            else translate("BIM_PlanEdit", "Current width: unresolved")
        )
        height_text = (
            translate("BIM_PlanEdit", "Current height: {height}").format(
                height=current_height_text,
            )
            if current_height_text
            else translate("BIM_PlanEdit", "Current height: unresolved")
        )
        if can_edit_width and can_edit_height and can_apply_style:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the width or height directly or apply a built-in preset while keeping the hosted position.",
            )
        elif can_edit_width and can_apply_style:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the width directly or apply a built-in preset while keeping the hosted position.",
            )
        elif can_edit_height and can_apply_style:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the height directly or apply a built-in preset while keeping the hosted position.",
            )
        elif can_edit_width and can_edit_height:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the width or height directly while keeping the hosted position.",
            )
        elif can_edit_width:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the width directly while keeping the hosted position.",
            )
        elif can_edit_height:
            hint_text = translate(
                "BIM_PlanEdit",
                "Change the height directly while keeping the hosted position.",
            )
        elif can_apply_style:
            hint_text = translate(
                "BIM_PlanEdit",
                "Apply a built-in preset while keeping the hosted position, width, height, frame depth, and frame offset.",
            )
        else:
            hint_text = translate(
                "BIM_PlanEdit",
                "Window editing is unavailable for the current selection.",
            )
        return "{}\n{}\n{}\n{}".format(style_text, width_text, height_text, hint_text)

    def _update_window_size_apply_state(self, modal_active=None):
        if (
            self.window_width_edit is None
            or self.window_height_edit is None
            or self.window_size_apply_button is None
        ):
            return

        can_apply = bool(
            self.session._can_apply_selected_window_size(
                width_value=self.window_width_edit.text(),
                height_value=self.window_height_edit.text(),
            )
        )
        if modal_active is None:
            modal_active = self.session._is_modal_plan_interaction_active()
        if modal_active:
            can_apply = False

        try:
            self.window_size_apply_button.setEnabled(can_apply)
        except Exception:
            pass
        self._set_widget_tooltip(
            self.window_size_apply_button,
            (
                translate(
                    "BIM_PlanEdit",
                    "Apply the entered width and height values in one step.",
                )
                if can_apply
                else translate(
                    "BIM_PlanEdit",
                    "Enter at least one different positive size before applying it.",
                )
            ),
        )

    def _update_window_preset_apply_state(self, modal_active=None):
        if self.window_preset_combo is None or self.window_preset_apply_button is None:
            return

        window = self._get_window_editor_target()
        can_apply_style = bool(window and self.session._can_apply_window_style_preset(window))
        if modal_active is None:
            modal_active = self.session._is_modal_plan_interaction_active()

        current_style = self.session._get_selected_window_style_preset() if can_apply_style else ""
        selected_style = ""
        index = self.window_preset_combo.currentIndex()
        if index >= 0:
            selected_style = self.window_preset_combo.itemData(index)
            if selected_style is None:
                selected_style = self.window_preset_combo.itemText(index)
        selected_style = str(selected_style or "").strip()
        can_apply = bool(can_apply_style and selected_style and selected_style != current_style)
        if modal_active:
            can_apply = False

        try:
            self.window_preset_apply_button.setEnabled(can_apply)
        except Exception:
            pass
        self._set_widget_tooltip(
            self.window_preset_apply_button,
            (
                translate(
                    "BIM_PlanEdit",
                    "Apply the selected built-in style to the current window.",
                )
                if can_apply
                else translate(
                    "BIM_PlanEdit",
                    "Choose a different built-in style before applying it.",
                )
            ),
        )

    def _refresh_window_editor(self):
        with self.session._plan_perf_trace_span("refresh_window_editor"):
            if self.window_editor is None:
                return

            window = self._get_window_editor_target()
            show_editor = bool(window)
            if not show_editor:
                self._hide_window_editor()
                return

            try:
                self.window_editor.setVisible(True)
            except Exception:
                pass

            self._refreshing_window_editor = True
            try:
                window_key = self._get_editor_object_key(window)
                can_edit_width = self.session._can_edit_window_width(window)
                can_edit_height = self.session._can_edit_window_height(window)
                can_apply_style = self.session._can_apply_window_style_preset(window)
                current_style = self.session._get_selected_window_style_preset()
                current_width_text = self.session._get_selected_window_width_text()
                current_height_text = self.session._get_selected_window_height_text()
                combo_items = self._get_window_preset_combo_items(current_style)
                state = (
                    window_key,
                    combo_items,
                    str(current_style or ""),
                    str(current_width_text or ""),
                    str(current_height_text or ""),
                    bool(can_edit_width),
                    bool(can_edit_height),
                    bool(can_apply_style),
                )
                if state != self._window_editor_state:
                    self.window_width_edit.blockSignals(True)
                    self.window_height_edit.blockSignals(True)
                    self.window_preset_combo.blockSignals(True)
                    try:
                        self.window_width_edit.setText(str(current_width_text or ""))
                        self.window_height_edit.setText(str(current_height_text or ""))
                        self.window_preset_combo.clear()
                        for item_data, item_label in combo_items:
                            self.window_preset_combo.addItem(item_label, item_data)
                        current_index = self._find_combo_data_index(
                            self.window_preset_combo,
                            current_style,
                        )
                        self.window_preset_combo.setCurrentIndex(
                            current_index if current_index >= 0 else 0
                        )
                    finally:
                        self.window_width_edit.blockSignals(False)
                        self.window_height_edit.blockSignals(False)
                        self.window_preset_combo.blockSignals(False)

                    self.window_preset_note.setText(
                        self._format_window_editor_note(
                            current_style,
                            current_width_text,
                            current_height_text,
                            can_edit_width,
                            can_edit_height,
                            can_apply_style,
                        )
                    )
                    self._window_editor_state = state

                self._set_widget_enabled(self.window_width_edit, bool(can_edit_width))
                self._set_widget_enabled(self.window_height_edit, bool(can_edit_height))
                self._set_widget_enabled(self.window_preset_combo, bool(can_apply_style))
            finally:
                self._refreshing_window_editor = False

            self._update_window_size_apply_state()
            self._update_window_preset_apply_state()

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        selected_kind, _selected_obj = self.session.selection.get_selected_plan_target()
        join_candidate = (
            self.session._get_plan_candidate_joint() is not None
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
            and self.session._can_edit_window_width(_selected_obj)
        )
        can_edit_window_height = (
            selected_kind == "opening"
            and _selected_obj is not None
            and self.session._can_edit_window_height(_selected_obj)
        )
        can_apply_window_style = (
            selected_kind == "opening"
            and _selected_obj is not None
            and self.session._can_apply_window_style_preset(_selected_obj)
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
            self.session.set_active_storey(self._storey_items[index])

    def on_select_clicked(self):
        self.session.activate_select_tool()

    def on_wall_clicked(self):
        self.session.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.activate_rect_wall_tool()

    def on_window_clicked(self):
        self.session.activate_window_tool()

    def on_space_clicked(self):
        self.session.activate_space_tool()

    def on_region_clicked(self):
        self.session.activate_plan_region_tool()

    def on_separator_clicked(self):
        self.session.activate_space_separator_tool()

    def on_move_clicked(self):
        self.session.activate_move_tool()

    def on_join_clicked(self):
        self.session.activate_join_tool()

    def on_join_type_changed(self, index):
        if self.join_type_combo is None or index < 0:
            return
        join_type = self.join_type_combo.itemData(index) or self.join_type_combo.itemText(index)
        self.session.set_plan_join_type(join_type)

    def on_unjoin_clicked(self):
        self.session._unjoin_current_plan_wall_pair()

    def on_reapply_clicked(self):
        self.session.apply_plan_view(fit=False)
        self.refresh_from_session()

    def on_space_label_edited(self):
        if self._refreshing_space_editor or self.space_label_edit is None:
            return
        self.session._set_selected_space_label(self.space_label_edit.text())

    def on_space_type_changed(self, index):
        if self._refreshing_space_editor or self.space_type_combo is None or index < 0:
            return
        value = self.space_type_combo.itemData(index) or self.space_type_combo.itemText(index)
        self.session._set_selected_space_type(value)

    def on_space_type_completion_activated(self, value):
        if self._refreshing_space_editor or self.space_type_combo is None:
            return
        self._commit_space_type_combo_text(value)

    def on_space_type_editing_finished(self):
        if self._refreshing_space_editor or self.space_type_combo is None:
            return
        line_edit = self.space_type_combo.lineEdit()
        if line_edit is None:
            return
        self._commit_space_type_combo_text(line_edit.text())

    def on_space_add_clicked(self):
        self.session._add_boundaries_to_selected_space()

    def on_space_remove_clicked(self):
        if self.space_boundary_list is None:
            return
        rows = sorted({index.row() for index in self.space_boundary_list.selectedIndexes()})
        self.session._remove_selected_space_boundaries(rows)

    def on_space_text_clicked(self):
        self.session._start_space_text_position_pick()

    def on_region_label_edited(self):
        if self._refreshing_region_editor or self.region_label_edit is None:
            return
        self.session._set_selected_region_label(self.region_label_edit.text())

    def on_region_scheme_edited(self):
        if self._refreshing_region_editor or self.region_scheme_edit is None:
            return
        self.session._set_selected_region_scheme(self.region_scheme_edit.text())

    def on_region_type_edited(self):
        if self._refreshing_region_editor or self.region_type_edit is None:
            return
        self.session._set_selected_region_type(self.region_type_edit.text())

    def on_region_parent_space_changed(self, index):
        if self._refreshing_region_editor or self.region_parent_space_combo is None:
            return
        if index < 0 or index >= len(self._region_parent_space_items):
            return
        self.session._set_selected_region_parent_space(self._region_parent_space_items[index])

    def on_window_preset_selection_changed(self, index):
        del index
        if self._refreshing_window_editor:
            return
        self._update_window_preset_apply_state()

    def on_window_width_text_changed(self, _text):
        if self._refreshing_window_editor:
            return
        self._update_window_size_apply_state()

    def on_window_height_text_changed(self, _text):
        if self._refreshing_window_editor:
            return
        self._update_window_size_apply_state()

    def on_window_size_apply_clicked(self):
        if (
            self._refreshing_window_editor
            or self.window_width_edit is None
            or self.window_height_edit is None
        ):
            return
        if self.session._set_selected_window_size(
            width_value=self.window_width_edit.text(),
            height_value=self.window_height_edit.text(),
        ):
            self.refresh_from_session(defer_integrations=True)

    def on_window_preset_apply_clicked(self):
        if self._refreshing_window_editor or self.window_preset_combo is None:
            return
        index = self.window_preset_combo.currentIndex()
        if index < 0:
            return
        preset_name = self.window_preset_combo.itemData(index)
        if preset_name is None:
            preset_name = self.window_preset_combo.itemText(index)
        preset_name = str(preset_name or "").strip()
        if not preset_name:
            return
        if self.session._apply_selected_window_style_preset(preset_name):
            self.refresh_from_session(defer_integrations=True)

    def on_exit_clicked(self):
        self.session.shutdown()
