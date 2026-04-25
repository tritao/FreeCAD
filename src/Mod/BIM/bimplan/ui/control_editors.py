# SPDX-License-Identifier: LGPL-2.1-or-later

"""Editor panel helpers for BIM Plan Edit controls."""

import FreeCAD
from bimplan import task_panel_view_model as plan_task_panel_view_model

translate = FreeCAD.Qt.translate


class PlanEditEditorPanelsMixin:
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
            semantic_obj = self.session.visibility.get_plan_semantic_object(obj)
            if not self.session.selection.is_plan_space_object(semantic_obj):
                continue
            name = getattr(semantic_obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append(semantic_obj)
        current_parent = self.session.visibility.get_plan_semantic_object(current_parent)
        if self.session.selection.is_plan_space_object(current_parent):
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
        current_parent = self.session.visibility.get_plan_semantic_object(
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
            QtGui, "Set Text Position", self.on_space_text_clicked
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

    def _refresh_space_editor(self):
        from PySide import QtGui

        with self.session.performance.plan_perf_trace_span("refresh_space_editor"):
            if self.space_editor is None:
                return
            space_editor_vm = plan_task_panel_view_model.build_space_editor_view_model(self.session)
            if not space_editor_vm.show_editor:
                self._hide_space_editor()
                return
            space = space_editor_vm.space
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
                        self.session.performance.plan_perf_count("space_type_options", len(options))
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
                            self.session.spaces.get_space_boundary_entries(space) or []
                        )
                        self.session.performance.plan_perf_count(
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
        with self.session.performance.plan_perf_trace_span("refresh_region_editor"):
            if self.region_editor is None:
                return
            region_editor_vm = plan_task_panel_view_model.build_region_editor_view_model(
                self.session
            )
            if not region_editor_vm.show_editor:
                self._hide_region_editor()
                return
            region = region_editor_vm.region
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
                        self.session.performance.plan_perf_count(
                            "region_parent_space_candidates",
                            max(0, len(self._region_parent_space_items) - 1),
                        )
                    finally:
                        self.region_parent_space_combo.blockSignals(False)
            finally:
                self._refreshing_region_editor = False

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

    def _update_window_size_apply_state(self, modal_active=None):
        if (
            self.window_width_edit is None
            or self.window_height_edit is None
            or self.window_size_apply_button is None
        ):
            return
        can_apply = bool(
            self.session.windows.can_apply_selected_window_size(
                width_value=self.window_width_edit.text(),
                height_value=self.window_height_edit.text(),
            )
        )
        if modal_active is None:
            modal_active = self.session.interaction.is_modal_plan_interaction_active()
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
        window = plan_task_panel_view_model.get_window_editor_target(self.session)
        can_apply_style = bool(
            window and self.session.windows.can_apply_window_style_preset(window)
        )
        if modal_active is None:
            modal_active = self.session.interaction.is_modal_plan_interaction_active()
        current_style = (
            self.session.windows.get_selected_window_style_preset() if can_apply_style else ""
        )
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
        with self.session.performance.plan_perf_trace_span("refresh_window_editor"):
            if self.window_editor is None:
                return
            window_editor_vm = plan_task_panel_view_model.build_window_editor_view_model(
                self.session
            )
            if not window_editor_vm.show_editor:
                self._hide_window_editor()
                return
            try:
                self.window_editor.setVisible(True)
            except Exception:
                pass
            self._refreshing_window_editor = True
            try:
                state = window_editor_vm.state_key
                if state != self._window_editor_state:
                    self.window_width_edit.blockSignals(True)
                    self.window_height_edit.blockSignals(True)
                    self.window_preset_combo.blockSignals(True)
                    try:
                        self.window_width_edit.setText(window_editor_vm.current_width_text)
                        self.window_height_edit.setText(window_editor_vm.current_height_text)
                        self.window_preset_combo.clear()
                        for item_data, item_label in window_editor_vm.combo_items:
                            self.window_preset_combo.addItem(item_label, item_data)
                        current_index = self._find_combo_data_index(
                            self.window_preset_combo,
                            window_editor_vm.current_style,
                        )
                        self.window_preset_combo.setCurrentIndex(
                            current_index if current_index >= 0 else 0
                        )
                    finally:
                        self.window_width_edit.blockSignals(False)
                        self.window_height_edit.blockSignals(False)
                        self.window_preset_combo.blockSignals(False)
                    self.window_preset_note.setText(window_editor_vm.note_text)
                    self._window_editor_state = state
                self._set_widget_enabled(self.window_width_edit, window_editor_vm.can_edit_width)
                self._set_widget_enabled(self.window_height_edit, window_editor_vm.can_edit_height)
                self._set_widget_enabled(self.window_preset_combo, window_editor_vm.can_apply_style)
            finally:
                self._refreshing_window_editor = False
            self._update_window_size_apply_state()
            self._update_window_preset_apply_state()

    def on_space_label_edited(self):
        if self._refreshing_space_editor or self.space_label_edit is None:
            return
        self.session.spaces.set_selected_space_label(self.space_label_edit.text())

    def on_space_type_changed(self, index):
        if self._refreshing_space_editor or self.space_type_combo is None or index < 0:
            return
        value = self.space_type_combo.itemData(index) or self.space_type_combo.itemText(index)
        self.session.spaces.set_selected_space_type(value)

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
        self.session.spaces.add_boundaries_to_selected_space()

    def on_space_remove_clicked(self):
        if self.space_boundary_list is None:
            return
        rows = sorted({index.row() for index in self.space_boundary_list.selectedIndexes()})
        self.session.spaces.remove_selected_space_boundaries(rows)

    def on_space_text_clicked(self):
        self.session.spaces.start_space_text_position_pick()

    def on_region_label_edited(self):
        if self._refreshing_region_editor or self.region_label_edit is None:
            return
        self.session.spaces.set_selected_region_label(self.region_label_edit.text())

    def on_region_scheme_edited(self):
        if self._refreshing_region_editor or self.region_scheme_edit is None:
            return
        self.session.spaces.set_selected_region_scheme(self.region_scheme_edit.text())

    def on_region_type_edited(self):
        if self._refreshing_region_editor or self.region_type_edit is None:
            return
        self.session.spaces.set_selected_region_type(self.region_type_edit.text())

    def on_region_parent_space_changed(self, index):
        if self._refreshing_region_editor or self.region_parent_space_combo is None:
            return
        if index < 0 or index >= len(self._region_parent_space_items):
            return
        self.session.spaces.set_selected_region_parent_space(self._region_parent_space_items[index])

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
        if self.session.windows.set_selected_window_size(
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
        if self.session.windows.apply_selected_window_style_preset(preset_name):
            self.refresh_from_session(defer_integrations=True)
