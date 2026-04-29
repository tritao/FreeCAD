# SPDX-License-Identifier: LGPL-2.1-or-later

"""Normalization helpers for BIM Plan Edit provider integrations."""

from dataclasses import replace

from .contracts import (
    PlanActionSpec,
    PlanContextDetailSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditHandleSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlayMarkerKind,
    PlanOverlaySpec,
    PlanOverlayTargetKind,
    PlanOverlayTargetSpec,
    PlanSuggestionSpec,
    PlanToolInteraction,
    PlanToolSpec,
)

_MISSING = object()


def coerce_plan_provider_results(result):
    if result is None:
        return ()
    if isinstance(result, (str, bytes)):
        return ()
    try:
        return tuple(result)
    except TypeError:
        return (result,)


def normalize_plan_provider_action(provider_id, action):
    if not isinstance(action, PlanActionSpec):
        return None
    if action.provider_id == provider_id:
        return action
    return replace(action, provider_id=str(provider_id or ""))


def normalize_plan_provider_tool(provider_id, tool):
    if not isinstance(tool, PlanToolSpec):
        return None
    if not isinstance(tool.interaction, PlanToolInteraction):
        return None
    if tool.provider_id == provider_id:
        return tool
    return replace(tool, provider_id=str(provider_id or ""))


def _normalize_plan_provider_edit_handle_scalars(handle):
    return {
        "key": str(handle.key or "").strip(),
        "label": str(handle.label or "").strip(),
        "tooltip": str(handle.tooltip or "").strip(),
        "target_key": str(handle.target_key or "").strip(),
        "action_key": str(handle.action_key or "").strip(),
        "transaction_label": str(handle.transaction_label or "").strip(),
        "prompt": str(handle.prompt or "").strip(),
        "role": str(handle.role or "").strip(),
    }


def _collect_plan_provider_edit_handle_replacements(provider_id, handle, key, point, fields):
    replacements = {}
    normalized_provider_id = str(provider_id or "")
    if handle.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    if key != handle.key:
        replacements["key"] = key
    if point != handle.point:
        replacements["point"] = point
    for field_name in (
        "label",
        "tooltip",
        "target_key",
        "transaction_label",
        "prompt",
        "role",
    ):
        field_value = fields[field_name]
        if field_value != getattr(handle, field_name):
            replacements[field_name] = field_value
    action_key = fields["action_key"] or key
    if action_key != handle.action_key:
        replacements["action_key"] = action_key
    return replacements


def normalize_plan_provider_edit_handle(provider_id, handle):
    if not isinstance(handle, PlanEditHandleSpec):
        return None
    if not isinstance(handle.interaction, PlanToolInteraction):
        return None
    if not isinstance(handle.marker_kind, PlanOverlayMarkerKind):
        return None
    key = str(handle.key or "").strip()
    point = _coerce_plan_overlay_point(handle.point)
    if not key or point is None:
        return None
    fields = _normalize_plan_provider_edit_handle_scalars(handle)
    replacements = _collect_plan_provider_edit_handle_replacements(
        provider_id,
        handle,
        key,
        point,
        fields,
    )
    if not replacements:
        return handle
    return replace(handle, **replacements)


def _normalize_plan_provider_actions(session, provider_id, actions):
    return tuple(
        normalized
        for normalized in (
            normalize_plan_provider_action(provider_id, action) for action in (actions or ())
        )
        if normalized is not None
    )


def _set_normalized_plan_provider_id(replacements, value, provider_id):
    normalized_provider_id = str(provider_id or "")
    if value != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id


def _set_normalized_text_field(replacements, field_name, value):
    normalized_value = str(value or "").strip()
    if normalized_value != value:
        replacements[field_name] = normalized_value
    return normalized_value


def _normalize_plan_provider_context_rows(rows):
    return tuple(
        normalized
        for normalized in (normalize_plan_provider_context_row(row) for row in (rows or ()))
        if normalized is not None
    )


def normalize_plan_provider_issue(session, provider_id, issue):
    if not isinstance(issue, PlanIssueSpec):
        return None
    if not isinstance(issue.severity, PlanIssueSeverity):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, issue.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, issue.provider_id, provider_id)
    if actions != tuple(issue.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return issue
    return replace(issue, **replacements)


def normalize_plan_provider_suggestion(session, provider_id, suggestion):
    if not isinstance(suggestion, PlanSuggestionSpec):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, suggestion.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, suggestion.provider_id, provider_id)
    if actions != tuple(suggestion.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return suggestion
    return replace(suggestion, **replacements)


def normalize_plan_provider_section(session, provider_id, section):
    if not isinstance(section, PlanInspectorSection):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, section.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, section.provider_id, provider_id)
    if actions != tuple(section.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return section
    return replace(section, **replacements)


def normalize_plan_provider_context_row(row):
    if not isinstance(row, PlanContextRowSpec):
        return None
    replacements = {}
    label = _set_normalized_text_field(replacements, "label", row.label)
    value = _set_normalized_text_field(replacements, "value", row.value)
    if not label:
        return None
    if not replacements:
        return row
    return replace(row, **replacements)


def normalize_plan_provider_context_detail(detail):
    if not isinstance(detail, PlanContextDetailSpec):
        return None
    rows = _normalize_plan_provider_context_rows(detail.rows)
    replacements = {}
    key = _set_normalized_text_field(replacements, "key", detail.key)
    title = _set_normalized_text_field(replacements, "title", detail.title)
    body = _set_normalized_text_field(replacements, "body", detail.body)
    if not key or not title:
        return None
    if rows != tuple(detail.rows or ()):
        replacements["rows"] = rows
    if not replacements:
        return detail
    return replace(detail, **replacements)


def normalize_plan_provider_context_panel(session, provider_id, panel):
    if not isinstance(panel, PlanContextPanelSpec):
        return None
    if not isinstance(panel.state, PlanContextPanelState):
        return None
    if not isinstance(panel.subject_kind, PlanContextSubjectKind):
        return None
    summary_rows = _normalize_plan_provider_context_rows(panel.summary_rows)
    details = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_detail(detail) for detail in (panel.details or ())
        )
        if normalized is not None
    )
    primary_action = None
    if panel.primary_action is not None:
        primary_action = normalize_plan_provider_action(
            provider_id,
            panel.primary_action,
        )
        if primary_action is None:
            return None
    secondary_actions = _normalize_plan_provider_actions(
        session,
        provider_id,
        panel.secondary_actions,
    )
    replacements = {}
    key = _set_normalized_text_field(replacements, "key", panel.key)
    title = _set_normalized_text_field(replacements, "title", panel.title)
    subtitle = _set_normalized_text_field(replacements, "subtitle", panel.subtitle)
    message = _set_normalized_text_field(replacements, "message", panel.message)
    if not key or not title:
        return None
    _set_normalized_plan_provider_id(replacements, panel.provider_id, provider_id)
    if summary_rows != tuple(panel.summary_rows or ()):
        replacements["summary_rows"] = summary_rows
    if primary_action != panel.primary_action:
        replacements["primary_action"] = primary_action
    if secondary_actions != tuple(panel.secondary_actions or ()):
        replacements["secondary_actions"] = secondary_actions
    if details != tuple(panel.details or ()):
        replacements["details"] = details
    if not replacements:
        return panel
    return replace(panel, **replacements)


_SESSION_AWARE_PROVIDER_NORMALIZERS = {
    normalize_plan_provider_issue,
    normalize_plan_provider_suggestion,
    normalize_plan_provider_section,
    normalize_plan_provider_context_panel,
}


def _normalize_plan_overlay_target_keys(target_keys):
    raw_target_keys = tuple(target_keys or ())
    normalized_target_keys = tuple(str(key or "") for key in raw_target_keys if key)
    return raw_target_keys, normalized_target_keys


def _normalize_plan_overlay_points_and_targets(overlay):
    raw_points = tuple(overlay.points or ())
    raw_point_targets = tuple(overlay.point_targets or ())
    point_pairs = []
    for index, raw_point in enumerate(raw_points):
        point = _coerce_plan_overlay_point(raw_point)
        if point is None:
            continue
        target = None
        if raw_point_targets:
            raw_target = raw_point_targets[index] if index < len(raw_point_targets) else None
            target = _normalize_plan_overlay_target(raw_target)
            if raw_target is not None and target is None:
                return None, None, None
        point_pairs.append((point, target))
    points = tuple(point for point, _target in point_pairs)
    point_targets = None
    if raw_point_targets:
        point_targets = tuple(target or PlanOverlayTargetSpec() for _point, target in point_pairs)
    return raw_points, raw_point_targets, (points, point_targets)


def _normalize_plan_overlay_polylines(polylines):
    normalized_polylines = tuple(
        _coerce_plan_overlay_polyline(polyline) for polyline in tuple(polylines or ())
    )
    return tuple(polyline for polyline in normalized_polylines if len(polyline) >= 2)


def _collect_overlay_normalization_replacements(provider_id, overlay):
    replacements = {}
    if overlay.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")

    raw_target_keys, target_keys = _normalize_plan_overlay_target_keys(overlay.target_keys)
    if target_keys != raw_target_keys:
        replacements["target_keys"] = target_keys

    raw_points, raw_point_targets, point_data = _normalize_plan_overlay_points_and_targets(overlay)
    if point_data is None:
        return None
    points, point_targets = point_data
    if points != raw_points:
        replacements["points"] = points
    if raw_point_targets and point_targets != raw_point_targets:
        replacements["point_targets"] = point_targets

    polylines = _normalize_plan_overlay_polylines(overlay.polylines)
    if polylines != tuple(overlay.polylines or ()):
        replacements["polylines"] = polylines

    color = _coerce_plan_overlay_color(overlay.color)
    if color != overlay.color:
        replacements["color"] = color
    return replacements


def normalize_plan_provider_overlay(provider_id, overlay):
    if not isinstance(overlay, PlanOverlaySpec):
        return None
    if not isinstance(overlay.marker_kind, PlanOverlayMarkerKind):
        return None
    replacements = _collect_overlay_normalization_replacements(provider_id, overlay)
    if replacements is None:
        return None
    if not replacements:
        return overlay
    return replace(overlay, **replacements)


def _normalize_plan_overlay_target(target):
    if target is None:
        return PlanOverlayTargetSpec()
    if not isinstance(target, PlanOverlayTargetSpec):
        return None
    if target.target_kind is not None and not isinstance(target.target_kind, PlanOverlayTargetKind):
        return None
    document_name = str(target.document_name or "").strip()
    object_name = str(target.object_name or "").strip()
    subname = str(target.subname or "").strip()
    replacements = {}
    if document_name != target.document_name:
        replacements["document_name"] = document_name
    if object_name != target.object_name:
        replacements["object_name"] = object_name
    if subname != target.subname:
        replacements["subname"] = subname
    if not replacements:
        return target
    return replace(target, **replacements)


def _coerce_plan_overlay_point_from_attributes(point):
    try:
        return (
            float(point.x),
            float(point.y),
            float(getattr(point, "z", 0.0) or 0.0),
        )
    except AttributeError:
        return _MISSING


def _coerce_plan_overlay_point_from_sequence(point):
    try:
        z_value = point[2] if len(point) > 2 else 0.0
        return (float(point[0]), float(point[1]), float(z_value))
    except (TypeError, ValueError, IndexError):
        return None


def _coerce_plan_overlay_point(point):
    coerced = _coerce_plan_overlay_point_from_attributes(point)
    if coerced is not _MISSING:
        return coerced
    return _coerce_plan_overlay_point_from_sequence(point)


def _coerce_plan_overlay_polyline(polyline):
    points = []
    for point in tuple(polyline or ()):
        coerced = _coerce_plan_overlay_point(point)
        if coerced is not None:
            points.append(coerced)
    return tuple(points)


def _coerce_plan_overlay_color(color):
    try:
        values = tuple(float(value) for value in tuple(color or ()))
    except (TypeError, ValueError):
        return (0.2, 0.55, 0.85)
    if len(values) < 3:
        return (0.2, 0.55, 0.85)
    return values[:3]
