# SPDX-License-Identifier: LGPL-2.1-or-later

"""Integration panel helpers for BIM Plan Edit controls."""

import weakref

import FreeCAD
from bimplan import task_panel_view_model as plan_task_panel_view_model
from bimplan.providers import PlanIssueSeverity, PlanToolInteraction

translate = FreeCAD.Qt.translate


def _run_queued_integration_panel_refresh(panel_ref, generation):
    panel = panel_ref()
    if panel is not None:
        panel._run_queued_integration_panel_refresh(generation)


class PlanEditIntegrationPanelMixin:
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
        self._set_provider_overlay_mode_combo_value(
            self.session.providers.get_plan_provider_overlay_mode()
        )
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

    def _build_detail_toggle_text(self, expanded, detail_title):
        detail_text = str(detail_title or "").strip() or translate("BIM_PlanEdit", "Details")
        if expanded:
            return translate("BIM_PlanEdit", "Hide details")
        return translate("BIM_PlanEdit", "{detail}...").format(detail=detail_text)

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
            status_label = self._make_wrapped_plain_label(QtGui, status_text, row_widget, bold=True)
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
        actions = plan_task_panel_view_model.filter_integration_actions(
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
            detail_label = self._make_wrapped_plain_label(QtGui, detail_text, detail_content)
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
        provider_label = self.session.providers.get_plan_provider_display_name(section.provider_id)
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
            "BIM_PlanEdit", "Summary"
        )
        self._add_integration_card_header(
            QtGui, layout, block, section_title, eyebrow=provider_label
        )
        scope_text = str(parsed.get("scope", "") or "").strip()
        if scope_text:
            layout.addWidget(
                self._make_summary_meta_row(
                    QtGui, block, translate("BIM_PlanEdit", "Scope"), scope_text
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
        self._add_integration_action_row(QtGui, block, layout, section.actions, primary_first=True)
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
                group_layout.addWidget(self._make_summary_status_row(QtGui, group_widget, row_text))
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
        provider_text = str(provider_label or "").strip() or translate(
            "BIM_PlanEdit", "Integrations"
        )
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
        provider_label = self.session.providers.get_plan_provider_display_name(issue.provider_id)
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
            tuple(issues or ()), key=self._get_provider_issue_severity_rank, reverse=True
        )
        if not ranked:
            return PlanIssueSeverity.INFO
        return getattr(ranked[0], "severity", PlanIssueSeverity.INFO)

    def _get_provider_issue_group_provider_label(self, issues):
        labels = []
        seen = set()
        for issue in tuple(issues or ()):
            label = str(
                self.session.providers.get_plan_provider_display_name(
                    getattr(issue, "provider_id", "")
                )
                or ""
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
        provider_label = self.session.providers.get_plan_provider_display_name(section.provider_id)
        title = str(getattr(section, "title", "") or "").strip()
        if not title:
            return provider_label
        return translate("BIM_PlanEdit", "{provider}: {title}").format(
            provider=provider_label,
            title=title,
        )

    def _is_provider_section_collapsed(self, section):
        return bool(getattr(section, "collapsed", False))

    def _populate_provider_context_detail_content(self, QtGui, content_layout, content, detail):
        for row in tuple(getattr(detail, "rows", ()) or ()):
            content_layout.addWidget(
                self._make_summary_meta_row(
                    QtGui, content, getattr(row, "label", ""), getattr(row, "value", "")
                )
            )
        body_text = str(getattr(detail, "body", "") or "").strip()
        if body_text:
            content_layout.addWidget(self._make_wrapped_plain_label(QtGui, body_text, content))

    def _connect_provider_context_detail_toggle(self, detail_button, content, detail_title):
        def toggle_details(checked):
            is_expanded = bool(checked)
            content.setVisible(is_expanded)
            detail_button.setText(self._build_detail_toggle_text(is_expanded, detail_title))

        try:
            detail_button.toggled.connect(toggle_details)
        except Exception:
            pass

    def _make_provider_context_panel_detail(self, QtGui, parent, layout, detail):
        detail_title = str(getattr(detail, "title", "") or "").strip()
        if not detail_title:
            return
        expanded = not bool(getattr(detail, "collapsed", True))
        detail_button = QtGui.QPushButton(
            self._build_detail_toggle_text(expanded, detail_title), parent
        )
        try:
            detail_button.setCheckable(True)
            detail_button.setChecked(expanded)
            detail_button.setFlat(True)
            detail_button.setAutoDefault(False)
            detail_button.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
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
        self._populate_provider_context_detail_content(QtGui, content_layout, content, detail)
        layout.addWidget(content)
        content.setVisible(expanded)
        self._connect_provider_context_detail_toggle(detail_button, content, detail_title)

    def _add_provider_context_panel_summary(self, QtGui, block, layout, panel):
        subtitle = str(getattr(panel, "subtitle", "") or "").strip()
        if subtitle:
            subtitle_label = self._make_wrapped_plain_label(QtGui, subtitle, block)
            self._set_integration_style_property(subtitle_label, "planPanelSummary", "true")
            layout.addWidget(subtitle_label)
        for row in tuple(getattr(panel, "summary_rows", ()) or ()):
            layout.addWidget(
                self._make_summary_meta_row(
                    QtGui, block, getattr(row, "label", ""), getattr(row, "value", "")
                )
            )
        message = str(getattr(panel, "message", "") or "").strip()
        if message:
            layout.addWidget(self._make_wrapped_plain_label(QtGui, message, block))

    def _add_provider_context_panel_actions(self, QtGui, block, layout, panel):
        actions, has_primary = plan_task_panel_view_model.collect_provider_context_panel_actions(
            panel
        )
        self._add_integration_action_row(
            QtGui, block, layout, actions=actions, primary_first=has_primary
        )

    def _add_provider_context_panel_details(self, QtGui, block, layout, panel):
        for detail in tuple(getattr(panel, "details", ()) or ()):
            self._make_provider_context_panel_detail(QtGui, block, layout, detail)

    def _make_provider_context_panel_block(self, QtGui, panel):
        block, layout = self._create_integration_card(QtGui, "detail")
        title = str(getattr(panel, "title", "") or "").strip() or translate(
            "BIM_PlanEdit", "Context"
        )
        self._add_integration_card_header(QtGui, layout, block, title)
        self._add_provider_context_panel_summary(QtGui, block, layout, panel)
        self._add_provider_context_panel_actions(QtGui, block, layout, panel)
        self._add_provider_context_panel_details(QtGui, block, layout, panel)
        return block

    def _populate_integration_details_content(self, QtGui, content_layout, sections):
        for section in sections:
            block = self._make_integration_block(
                QtGui,
                self._format_provider_section_title(section),
                body=getattr(section, "body", ""),
                actions=section.actions,
            )
            content_layout.addWidget(block)

    def _connect_integration_details_toggle(self, detail_button, content, detail_title):
        def toggle_details(checked):
            is_expanded = bool(checked)
            content.setVisible(is_expanded)
            detail_button.setText(self._build_detail_toggle_text(is_expanded, detail_title))

        try:
            detail_button.toggled.connect(toggle_details)
        except Exception:
            pass

    def _make_integration_details_group(self, QtGui, sections):
        group, layout = self._create_integration_card(QtGui, "detail")
        self._add_integration_card_header(
            QtGui, layout, group, translate("BIM_PlanEdit", "Additional details")
        )
        expanded = any(not self._is_provider_section_collapsed(section) for section in sections)
        detail_title = translate("BIM_PlanEdit", "Provider Notes")
        detail_button = QtGui.QPushButton(
            self._build_detail_toggle_text(expanded, detail_title), group
        )
        try:
            detail_button.setCheckable(True)
            detail_button.setChecked(expanded)
            detail_button.setFlat(True)
            detail_button.setAutoDefault(False)
            detail_button.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
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
        self._populate_integration_details_content(QtGui, content_layout, sections)
        layout.addWidget(content)
        content.setVisible(expanded)
        self._connect_integration_details_toggle(detail_button, content, detail_title)
        return group

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

    def _group_provider_overlay_legend_items(self, items, active_mode=None):
        grouped = []
        groups_by_key = {}
        for item in plan_task_panel_view_model.filter_provider_overlay_legend_items_for_mode(
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
            QtGui, layout, block, translate("BIM_PlanEdit", "Overlays")
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

    def _set_integration_summary_text(self, summary):
        if self.integration_summary is None:
            return
        self.integration_summary.setText(str(summary or ""))
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
        with self.session.performance.plan_perf_trace_event("queued_integration_panel_refresh"):
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
                items, active_mode=active_mode
            )
            if not grouped_items:
                empty_label = self._make_wrapped_plain_label(
                    QtGui,
                    translate("BIM_PlanEdit", "No overlays are available for {mode}.").format(
                        mode=self._format_provider_overlay_mode_label(active_mode)
                    ),
                    parent,
                )
                self._integration_overlay_content_layout.addWidget(empty_label)
                return
            for category, category_label, category_items in grouped_items:
                heading = self._make_wrapped_plain_label(QtGui, category_label, parent, bold=True)
                self._set_integration_style_property(heading, "planSubsectionTitle", "true")
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

    def _should_skip_integration_panel_refresh(self):
        if (
            self.integration_panel is None
            or self.integration_summary is None
            or self.integration_content_layout is None
        ):
            return True
        if self._session_is_inactive():
            self._integration_refresh_queued = False
            self._hide_integration_panel()
            return True
        if self.session.providers.plan_provider_integrations_disabled():
            self.session.performance.plan_perf_count("integration_panel_disabled")
            self._integration_refresh_queued = False
            self._hide_integration_panel()
            return True
        return False

    def _build_integration_panel_refresh_state(self):
        with self.session.providers.plan_provider_refresh_cache_scope():
            snapshot = self.session.providers.get_plan_provider_snapshot()
            integration_vm = plan_task_panel_view_model.build_integration_panel_view_model(
                self.session,
                snapshot,
            )
        return snapshot, integration_vm

    def _queue_provider_overlay_refresh(self):
        queue_overlay_refresh = getattr(self.session, "queue_plan_provider_overlay_sync", None)
        if not callable(queue_overlay_refresh):
            queue_overlay_refresh = getattr(
                self.session,
                "queue_plan_provider_overlay_refresh",
                None,
            )
        if callable(queue_overlay_refresh):
            queue_overlay_refresh()

    def _rebuild_integration_panel_content(self, snapshot, integration_vm):
        from PySide import QtGui

        self._integration_action_buttons = []
        self._integration_overlay_checkboxes = []
        self._reset_integration_panel_dynamic_refs()
        self._clear_layout(self.integration_content_layout)

        for section in integration_vm.summary_sections:
            block = self._make_summary_section_block(QtGui, section)
            self.integration_content_layout.addWidget(block)
        if integration_vm.context_panel is not None:
            self.integration_content_layout.addWidget(
                self._make_integration_group_heading(QtGui, integration_vm.context_panel_heading)
            )
            self.integration_content_layout.addWidget(
                self._make_provider_context_panel_block(QtGui, integration_vm.context_panel)
            )
        if snapshot.issues:
            self.integration_content_layout.addWidget(
                self._make_integration_group_heading(
                    QtGui, translate("BIM_PlanEdit", "Action Needed")
                )
            )
        for issue_group in integration_vm.grouped_issue_sets:
            block = self._make_provider_issue_block(
                QtGui,
                issue_group,
                hidden_action_ids=integration_vm.promoted_action_ids,
            )
            if block is not None:
                self.integration_content_layout.addWidget(block)
        if integration_vm.tools or integration_vm.overlay_items:
            self.integration_content_layout.addWidget(
                self._make_integration_group_heading(QtGui, translate("BIM_PlanEdit", "Utilities"))
            )
        if integration_vm.tools:
            block = self._make_integration_block(
                QtGui,
                translate("BIM_PlanEdit", "Tools"),
                actions=integration_vm.tools,
                card_role="utility",
                hidden_action_ids=integration_vm.promoted_action_ids,
                hidden_action_labels=integration_vm.hidden_tool_action_labels,
                action_columns=3,
                default_action_role="utility",
            )
            self.integration_content_layout.addWidget(block)
        if integration_vm.overlay_items:
            block = self._make_provider_overlay_legend_block(
                QtGui,
                integration_vm.overlay_items,
                active_mode=integration_vm.overlay_mode,
            )
            if block is not None:
                self.integration_content_layout.addWidget(block)
        if integration_vm.regular_sections or integration_vm.detail_sections:
            self.integration_content_layout.addWidget(
                self._make_integration_group_heading(
                    QtGui, translate("BIM_PlanEdit", "More Context")
                )
            )
        for section in integration_vm.regular_sections:
            block = self._make_integration_block(
                QtGui,
                self._format_provider_section_title(section),
                body=getattr(section, "body", ""),
                actions=section.actions,
                card_role="detail",
                hidden_action_ids=integration_vm.promoted_action_ids,
            )
            self.integration_content_layout.addWidget(block)
        if integration_vm.detail_sections:
            group = self._make_integration_details_group(QtGui, integration_vm.detail_sections)
            self.integration_content_layout.addWidget(group)
        self.integration_content_layout.addStretch(1)

    def _apply_integration_panel_view_model(self, snapshot, integration_vm):
        self._set_provider_overlay_mode_combo_value(integration_vm.overlay_mode)
        state = integration_vm.state_key
        if not integration_vm.has_content:
            self._hide_integration_panel()
            return
        self._set_integration_summary_text(integration_vm.summary_text)
        if state != self._integration_panel_state:
            self._integration_panel_state = state
            self._rebuild_integration_panel_content(snapshot, integration_vm)
        elif integration_vm.overlay_items:
            self._refresh_provider_overlay_legend_block(
                integration_vm.overlay_items,
                active_mode=integration_vm.overlay_mode,
            )
        self._set_integration_panel_visible(True)

    def _refresh_integration_panel(self, defer=False):
        with self.session.performance.plan_perf_trace_span("refresh_integration_panel"):
            if self._should_skip_integration_panel_refresh():
                return
            if defer:
                self.session.performance.plan_perf_count("integration_panel_deferred_refreshes")
                self._queue_integration_panel_refresh()
                return
            self._integration_refresh_queued = False
            self._integration_refresh_generation += 1
            snapshot, integration_vm = self._build_integration_panel_refresh_state()
            self._queue_provider_overlay_refresh()
            self._apply_integration_panel_view_model(snapshot, integration_vm)

    def on_provider_action_clicked(self, action):
        if action is None:
            return
        if (
            getattr(action, "interaction", PlanToolInteraction.IMMEDIATE)
            == PlanToolInteraction.POINT
        ):
            self.session.providers.start_plan_provider_point_tool(action)
            return
        self.session.providers.execute_plan_provider_action(
            getattr(action, "provider_id", ""),
            getattr(action, "key", ""),
            transaction_label=getattr(action, "transaction_label", ""),
        )

    def on_provider_overlay_visibility_changed(self, provider_id, overlay_key, visible):
        self.session.providers.set_plan_provider_overlay_visible(provider_id, overlay_key, visible)

    def on_provider_overlay_mode_changed(self, mode):
        getattr(self.session, "set_plan_provider_overlay_mode", lambda _mode: False)(mode)
