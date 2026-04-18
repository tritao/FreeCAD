# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task-panel controls for BIM Plan Edit."""

import FreeCAD

translate = FreeCAD.Qt.translate


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

    def __init__(self, session):
        from PySide import QtGui

        self.session = session
        self._storey_items = []
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._refreshing_space_editor = False
        self._refreshing_region_editor = False
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self._status_text_state = None
        self._integration_panel_state = None
        self._integration_action_buttons = []
        self._modal_interaction_state = None
        self._region_parent_space_items = []
        self.form = self._build_form(QtGui)
        try:
            self.form.setObjectName("BIMPlanEditContextControls")
        except Exception:
            pass

    @property
    def modal_focus_widgets(self):
        return tuple(self._modal_focus_widgets)

    def _build_form(self, QtGui):
        container = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        container.setMinimumWidth(280)
        container.setMaximumWidth(360)

        layout.addWidget(self._build_intro_label(QtGui))
        layout.addLayout(self._build_storey_row(QtGui))
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("select_button", "Select", self.on_select_clicked),
                    ("wall_button", "Wall", self.on_wall_clicked),
                    ("rect_wall_button", "Rect Wall", self.on_rect_wall_clicked),
                ),
            )
        )
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("space_button", "Space", self.on_space_clicked),
                    ("region_button", "Region", self.on_region_clicked),
                    ("separator_button", "Separator", self.on_separator_clicked),
                    ("move_button", "Move", self.on_move_clicked),
                ),
            )
        )
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("join_button", "Join", self.on_join_clicked),
                    ("reapply_button", "Reapply View", self.on_reapply_clicked),
                ),
            )
        )
        layout.addLayout(self._build_join_type_row(QtGui))

        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.integration_panel = self._build_integration_panel(QtGui)
        layout.addWidget(self.integration_panel)
        self.space_editor = self._build_space_editor(QtGui)
        layout.addWidget(self.space_editor)
        self.region_editor = self._build_region_editor(QtGui)
        layout.addWidget(self.region_editor)

        self.exit_button = self._make_button(QtGui, "Exit Plan Edit", self.on_exit_clicked)
        self.exit_button.setMinimumHeight(32)
        layout.addWidget(self.exit_button)

        self._modal_focus_widgets = [
            self.storey_combo,
            self.join_type_combo,
            self.unjoin_button,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
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
            self.exit_button,
        ]
        self._capture_focus_policies()

        container.setLayout(layout)
        return container

    def _build_intro_label(self, QtGui):
        intro = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan authoring mode for the active storey.",
            )
        )
        intro.setWordWrap(True)
        return intro

    def _make_button(self, QtGui, label, handler):
        button = QtGui.QPushButton(translate("BIM_PlanEdit", label))
        button.clicked.connect(handler)
        return button

    def _build_storey_row(self, QtGui):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        storey_label = QtGui.QLabel(translate("BIM_PlanEdit", "Storey"))
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        row.addWidget(storey_label)
        row.addWidget(self.storey_combo, 1)
        return row

    def _build_button_row(self, QtGui, specs):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        for attr, label, handler in specs:
            button = self._make_button(QtGui, label, handler)
            setattr(self, attr, button)
            row.addWidget(button)
        return row

    def _build_join_type_row(self, QtGui):
        row = QtGui.QHBoxLayout()
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
        return row

    def _build_integration_panel(self, QtGui):
        panel = QtGui.QGroupBox(translate("BIM_PlanEdit", "Integrations"))
        panel.setVisible(False)
        layout = QtGui.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.integration_summary = QtGui.QLabel(panel)
        self.integration_summary.setWordWrap(True)
        layout.addWidget(self.integration_summary)

        self.integration_content = QtGui.QWidget(panel)
        self.integration_content_layout = QtGui.QVBoxLayout(self.integration_content)
        self.integration_content_layout.setContentsMargins(0, 0, 0, 0)
        self.integration_content_layout.setSpacing(6)
        layout.addWidget(self.integration_content)
        return panel

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

    def _make_integration_block(self, QtGui, title, body="", actions=()):
        block = QtGui.QFrame(self.integration_panel)
        block.setFrameShape(QtGui.QFrame.StyledPanel)
        layout = QtGui.QVBoxLayout(block)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_label = QtGui.QLabel(str(title or ""), block)
        title_label.setWordWrap(True)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)

        body_text = str(body or "").strip()
        if body_text:
            body_label = QtGui.QLabel(body_text, block)
            body_label.setWordWrap(True)
            layout.addWidget(body_label)

        if actions:
            action_row = QtGui.QHBoxLayout()
            action_row.setSpacing(6)
            for action in actions:
                button = QtGui.QPushButton(str(action.label or ""), block)
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
                self._integration_action_buttons.append(button)
                action_row.addWidget(button)
            action_row.addStretch(1)
            layout.addLayout(action_row)
        return block

    def _format_provider_issue_title(self, issue):
        severity = str(getattr(issue, "severity", "") or "").strip().lower()
        severity_label = {
            "error": translate("BIM_PlanEdit", "Error"),
            "warning": translate("BIM_PlanEdit", "Warning"),
        }.get(severity, translate("BIM_PlanEdit", "Info"))
        provider_label = self.session.get_plan_provider_display_name(issue.provider_id)
        return translate("BIM_PlanEdit", "{provider} [{severity}]: {title}").format(
            provider=provider_label,
            severity=severity_label,
            title=str(getattr(issue, "title", "") or "").strip(),
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

    def _make_integration_details_group(self, QtGui, sections):
        group = QtGui.QGroupBox(
            translate("BIM_PlanEdit", "Details"),
            self.integration_panel,
        )
        group.setCheckable(True)
        group.setChecked(
            any(not self._is_provider_section_collapsed(section) for section in sections)
        )

        layout = QtGui.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

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

        content.setVisible(group.isChecked())
        try:
            group.toggled.connect(content.setVisible)
        except Exception:
            pass
        return group

    def _set_integration_panel_visible(self, visible):
        if self.integration_panel is None:
            return
        try:
            self.integration_panel.setVisible(bool(visible))
        except Exception:
            pass

    def _hide_integration_panel(self):
        self._integration_panel_state = None
        self._integration_action_buttons = []
        if self.integration_summary is not None:
            try:
                self.integration_summary.clear()
            except Exception:
                pass
        self._clear_layout(self.integration_content_layout)
        self._set_integration_panel_visible(False)

    def _set_integration_summary_text(self, issues, sections):
        if self.integration_summary is None:
            return
        parts = []
        issue_count = len(issues or ())
        section_count = len(sections or ())
        if issue_count:
            parts.append(translate("BIM_PlanEdit", "{count} issue(s)").format(count=issue_count))
        if section_count:
            parts.append(
                translate("BIM_PlanEdit", "{count} section(s)").format(count=section_count)
            )
        summary = (
            translate(
                "BIM_PlanEdit",
                "Registered plan integrations contributed {details}.",
            ).format(details=", ".join(parts))
            if parts
            else ""
        )
        self.integration_summary.setText(summary)

    def _refresh_integration_panel(self):
        with self.session._plan_perf_trace_span("refresh_integration_panel"):
            if (
                self.integration_panel is None
                or self.integration_summary is None
                or self.integration_content_layout is None
            ):
                return
            issues = tuple(self.session.get_plan_provider_issues())
            sections = tuple(self.session.get_plan_provider_inspector_sections())
            state = (issues, sections)
            if not issues and not sections:
                self._hide_integration_panel()
                return
            if state != self._integration_panel_state:
                self._integration_panel_state = state
                self._integration_action_buttons = []
                self._set_integration_summary_text(issues, sections)
                self._clear_layout(self.integration_content_layout)
                from PySide import QtGui

                summary_sections, regular_sections, detail_sections = (
                    self._partition_provider_sections(sections)
                )
                for section in summary_sections:
                    block = self._make_integration_block(
                        QtGui,
                        self._format_provider_section_title(section),
                        body=getattr(section, "body", ""),
                        actions=section.actions,
                    )
                    self.integration_content_layout.addWidget(block)
                for issue in issues:
                    issue_text = str(getattr(issue, "title", "") or "").strip()
                    message_text = str(getattr(issue, "message", "") or "").strip()
                    body = message_text or issue_text
                    if body == issue_text:
                        body = str(message_text or "").strip()
                    block = self._make_integration_block(
                        QtGui,
                        self._format_provider_issue_title(issue),
                        body=body,
                        actions=issue.actions,
                    )
                    self.integration_content_layout.addWidget(block)
                for section in regular_sections:
                    block = self._make_integration_block(
                        QtGui,
                        self._format_provider_section_title(section),
                        body=getattr(section, "body", ""),
                        actions=section.actions,
                    )
                    self.integration_content_layout.addWidget(block)
                if detail_sections:
                    group = self._make_integration_details_group(
                        QtGui,
                        detail_sections,
                    )
                    self.integration_content_layout.addWidget(group)
                self.integration_content_layout.addStretch(1)
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

    def _capture_focus_policies(self):
        for widget in self._modal_focus_widgets:
            try:
                self._saved_focus_policies[widget] = widget.focusPolicy()
            except Exception:
                pass

    def dispose(self):
        form = self.form
        if form is not None:
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
            try:
                form.deleteLater()
            except Exception:
                pass
        self.form = None
        self.status = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.space_button = None
        self.region_button = None
        self.separator_button = None
        self.move_button = None
        self.join_button = None
        self.join_type_combo = None
        self.unjoin_button = None
        self.reapply_button = None
        self.integration_panel = None
        self.integration_summary = None
        self.integration_content = None
        self.integration_content_layout = None
        self._integration_panel_state = None
        self._integration_action_buttons = []
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
        self._region_parent_space_items = []
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

    def refresh(self):
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
        self.refresh_from_session()

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

    def on_provider_action_clicked(self, action):
        if action is None:
            return
        self.session.execute_plan_provider_action(
            getattr(action, "provider_id", ""),
            getattr(action, "key", ""),
            transaction_label=getattr(action, "transaction_label", ""),
        )

    def _set_status_text(self, text):
        text = str(text or "")
        if self.status is None or text == self._status_text_state:
            return
        self.status.setText(text)
        self._status_text_state = text

    def _build_status_text(self):
        storey_text = self.session.get_storey_label(self.session.active_storey)
        tool = self.session.current_tool
        selected_kind, selected_obj = self.session._get_selected_plan_target()
        selected_state = self.session._format_plan_target_selection_state(
            selected_kind, selected_obj
        )
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
            targets = self.session._get_selected_plan_targets()
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
        elif selected_kind == "opening" and selected_obj is not None:
            selection_state = selected_state
            selection_help = translate(
                "BIM_PlanEdit",
                "Use in-view handles to move or flip the selected opening.",
            )
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
        else:
            selection_state = translate("BIM_PlanEdit", "Selection: none")
            selection_help = translate(
                "BIM_PlanEdit",
                "Select a wall, hosted opening, symbol instance, region, or space to edit it, or use walls and separators to define spaces.",
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
        return translate(
            "BIM_PlanEdit",
            "Mode: {tool}\nStorey: {storey}\nDisplay: Footprint\n{selection_state}\n{selection_help}",
        ).format(
            tool=tool,
            storey=storey_text,
            selection_state=selection_state,
            selection_help=selection_help,
        )

    def refresh_from_session(self):
        with self.session._plan_perf_trace_span("refresh_task_panel_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return
            self._sync_join_type_combo_from_session()
            self._set_status_text(self._build_status_text())
            self._refresh_integration_panel()
            self._refresh_space_editor()
            self._refresh_region_editor()
            self._apply_modal_interaction_state(self.session._is_modal_plan_interaction_active())

    def refresh_selection_from_session(self):
        with self.session._plan_perf_trace_span("refresh_task_panel_selection_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return
            selected_kind, _selected_obj = self.session._get_selected_plan_target()
            if self.session.current_tool != "Select" or selected_kind != "wall":
                self.refresh_from_session()
                return
            self._set_status_text(self._build_status_text())
            self._refresh_integration_panel()
            self._hide_space_editor()
            self._hide_region_editor()
            self._apply_modal_interaction_state(self.session._is_modal_plan_interaction_active())

    def _refresh_space_editor(self):
        from PySide import QtGui

        with self.session._plan_perf_trace_span("refresh_space_editor"):
            if self.space_editor is None:
                return
            selected_kind, selected_obj = self.session._get_selected_plan_target()
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
            selected_kind, selected_obj = self.session._get_selected_plan_target()
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

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        selected_kind, _selected_obj = self.session._get_selected_plan_target()
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
        for button in self._integration_action_buttons:
            if button is None:
                continue
            try:
                base_enabled = button.property("planActionEnabled")
                button.setEnabled(bool(base_enabled) and not modal_active)
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

    def on_storey_changed(self, index):
        if 0 <= index < len(self._storey_items):
            self.session.set_active_storey(self._storey_items[index])

    def on_select_clicked(self):
        self.session.activate_select_tool()

    def on_wall_clicked(self):
        self.session.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.activate_rect_wall_tool()

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

    def on_exit_clicked(self):
        self.session.shutdown()
