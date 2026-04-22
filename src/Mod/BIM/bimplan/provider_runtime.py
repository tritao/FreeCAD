# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from contextlib import nullcontext
from dataclasses import replace
import inspect

import FreeCAD

from .provider_targets import (
    get_plan_provider_target_for_object as _get_plan_provider_target_for_object,
    get_plan_provider_targets as _get_plan_provider_targets,
    is_plan_provider_target_object as _is_plan_provider_target_object,
    normalize_plan_provider_target as _normalize_plan_provider_target,
)
from .providers import (
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
    PlanOverlaySpec,
    PlanOverlayMarkerKind,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanSuggestionSpec,
    PlanToolSpec,
    PlanToolInteraction,
)
from .semantics import PlanSemanticRecord
from .targets import PlanTarget
from .transactions import PlanEditTransaction

translate = FreeCAD.Qt.translate


def get_plan_provider_display_name(session, provider_id):
    provider = session.get_plan_provider_registry().get_provider(provider_id)
    if provider is None:
        return str(provider_id or "").strip()
    display_name = str(getattr(provider, "display_name", "") or "").strip()
    if display_name:
        return display_name
    getter = getattr(provider, "get_display_name", None)
    if callable(getter):
        try:
            return str(getter() or "").strip()
        except Exception:
            pass
    provider_name = str(getattr(provider, "provider_id", "") or "").strip()
    return provider_name or str(provider_id or "").strip()


def build_plan_semantic_record(session, target_kind, target_obj):
    if not target_kind or target_obj is None:
        return None
    semantic_obj = session._get_plan_semantic_object(target_obj)
    if semantic_obj is None:
        return None
    doc = getattr(target_obj, "Document", None)
    semantic_doc = getattr(semantic_obj, "Document", None)
    space_label = session._get_plan_text_property(
        semantic_obj,
        ("SpaceLabel", "RoomLabel", "Label"),
    )
    source_space_name = session._get_plan_text_property(
        semantic_obj,
        ("SourceSpaceName",),
    )
    if target_kind == "space" and not source_space_name:
        source_space_name = str(getattr(semantic_obj, "Name", "") or "")
    usage_category = session._get_plan_text_property(
        semantic_obj,
        ("UsageCategory", "SpaceType"),
    )
    requirement_tags = session._normalize_plan_requirement_tags(
        getattr(semantic_obj, "RequirementTags", None)
    )
    return PlanSemanticRecord(
        target_kind=str(target_kind or ""),
        document_name=str(getattr(doc, "Name", "") or ""),
        object_name=str(getattr(target_obj, "Name", "") or ""),
        label=str(getattr(target_obj, "Label", getattr(target_obj, "Name", "")) or ""),
        semantic_document_name=str(getattr(semantic_doc, "Name", "") or ""),
        semantic_object_name=str(getattr(semantic_obj, "Name", "") or ""),
        semantic_label=str(getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""),
        space_key=session._get_plan_text_property(semantic_obj, ("SpaceKey",)),
        space_label=str(space_label or ""),
        source_space_name=str(source_space_name or ""),
        usage_category=str(usage_category or ""),
        object_role=session._get_plan_text_property(semantic_obj, ("ObjectRole",)),
        semantic_preset=session._get_plan_text_property(semantic_obj, ("SemanticPreset",)),
        host_ref=session._get_plan_host_ref(semantic_obj),
        mount_height_mm=session._get_plan_float_property(
            semantic_obj,
            ("MountHeight", "MEPMountHeight", "PlumbingMountHeight"),
        ),
        requirement_tags=requirement_tags,
    )


def get_plan_semantic_records(session, targets=None):
    if targets is None:
        targets = session.get_plan_targets(selected_only=True)
    records = []
    for target in targets or ():
        target_kind = None
        target_obj = None
        if isinstance(target, PlanTarget):
            target_kind = target.kind
            target_obj = session.resolve_plan_target_object(target)
        else:
            try:
                target_kind, target_obj = target
            except Exception:
                continue
        record = session._build_plan_semantic_record(target_kind, target_obj)
        if record is not None:
            records.append(record)
    return tuple(records)


def get_plan_provider_id(provider):
    if provider is None:
        return ""
    getter = getattr(provider, "get_provider_id", None)
    if callable(getter):
        try:
            provider_id = str(getter() or "").strip()
        except Exception:
            provider_id = ""
        if provider_id:
            return provider_id
    return str(getattr(provider, "provider_id", "") or "").strip()


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
    replacements = {}
    normalized_provider_id = str(provider_id or "")
    if handle.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    label = str(handle.label or "").strip()
    tooltip = str(handle.tooltip or "").strip()
    target_key = str(handle.target_key or "").strip()
    action_key = str(handle.action_key or "").strip()
    transaction_label = str(handle.transaction_label or "").strip()
    prompt = str(handle.prompt or "").strip()
    role = str(handle.role or "").strip()
    if key != handle.key:
        replacements["key"] = key
    if point != handle.point:
        replacements["point"] = point
    if label != handle.label:
        replacements["label"] = label
    if tooltip != handle.tooltip:
        replacements["tooltip"] = tooltip
    if target_key != handle.target_key:
        replacements["target_key"] = target_key
    if not action_key:
        action_key = key
    if action_key != handle.action_key:
        replacements["action_key"] = action_key
    if transaction_label != handle.transaction_label:
        replacements["transaction_label"] = transaction_label
    if prompt != handle.prompt:
        replacements["prompt"] = prompt
    if role != handle.role:
        replacements["role"] = role
    if not replacements:
        return handle
    return replace(handle, **replacements)


def normalize_plan_provider_issue(session, provider_id, issue):
    if not isinstance(issue, PlanIssueSpec):
        return None
    if not isinstance(issue.severity, PlanIssueSeverity):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session._normalize_plan_provider_action(provider_id, action)
            for action in (issue.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if issue.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(issue.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return issue
    return replace(issue, **replacements)


def normalize_plan_provider_suggestion(session, provider_id, suggestion):
    if not isinstance(suggestion, PlanSuggestionSpec):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session._normalize_plan_provider_action(provider_id, action)
            for action in (suggestion.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if suggestion.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(suggestion.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return suggestion
    return replace(suggestion, **replacements)


def normalize_plan_provider_section(session, provider_id, section):
    if not isinstance(section, PlanInspectorSection):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session._normalize_plan_provider_action(provider_id, action)
            for action in (section.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if section.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(section.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return section
    return replace(section, **replacements)


def normalize_plan_provider_context_row(row):
    if not isinstance(row, PlanContextRowSpec):
        return None
    replacements = {}
    label = str(row.label or "").strip()
    value = str(row.value or "").strip()
    if not label:
        return None
    if label != row.label:
        replacements["label"] = label
    if value != row.value:
        replacements["value"] = value
    if not replacements:
        return row
    return replace(row, **replacements)


def normalize_plan_provider_context_detail(detail):
    if not isinstance(detail, PlanContextDetailSpec):
        return None
    rows = tuple(
        normalized
        for normalized in (normalize_plan_provider_context_row(row) for row in (detail.rows or ()))
        if normalized is not None
    )
    replacements = {}
    key = str(detail.key or "").strip()
    title = str(detail.title or "").strip()
    body = str(detail.body or "").strip()
    if not key or not title:
        return None
    if key != detail.key:
        replacements["key"] = key
    if title != detail.title:
        replacements["title"] = title
    if body != detail.body:
        replacements["body"] = body
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
    summary_rows = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_row(row) for row in (panel.summary_rows or ())
        )
        if normalized is not None
    )
    details = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_detail(detail) for detail in (panel.details or ())
        )
        if normalized is not None
    )
    primary_action = None
    if panel.primary_action is not None:
        primary_action = session._normalize_plan_provider_action(
            provider_id,
            panel.primary_action,
        )
        if primary_action is None:
            return None
    secondary_actions = tuple(
        normalized
        for normalized in (
            session._normalize_plan_provider_action(provider_id, action)
            for action in (panel.secondary_actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    key = str(panel.key or "").strip()
    title = str(panel.title or "").strip()
    subtitle = str(panel.subtitle or "").strip()
    message = str(panel.message or "").strip()
    if not key or not title:
        return None
    if key != panel.key:
        replacements["key"] = key
    if title != panel.title:
        replacements["title"] = title
    if subtitle != panel.subtitle:
        replacements["subtitle"] = subtitle
    if message != panel.message:
        replacements["message"] = message
    if panel.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
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


def normalize_plan_provider_overlay(provider_id, overlay):
    if not isinstance(overlay, PlanOverlaySpec):
        return None
    if not isinstance(overlay.marker_kind, PlanOverlayMarkerKind):
        return None
    replacements = {}
    if overlay.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    target_keys = tuple(str(key or "") for key in tuple(overlay.target_keys or ()) if key)
    if target_keys != tuple(overlay.target_keys or ()):
        replacements["target_keys"] = target_keys
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
                return None
        point_pairs.append((point, target))
    points = tuple(point for point, _target in point_pairs)
    if points != tuple(overlay.points or ()):
        replacements["points"] = points
    if raw_point_targets:
        point_targets = tuple(target or PlanOverlayTargetSpec() for _point, target in point_pairs)
        if point_targets != raw_point_targets:
            replacements["point_targets"] = point_targets
    polylines = tuple(
        _coerce_plan_overlay_polyline(polyline) for polyline in tuple(overlay.polylines or ())
    )
    polylines = tuple(polyline for polyline in polylines if len(polyline) >= 2)
    if polylines != tuple(overlay.polylines or ()):
        replacements["polylines"] = polylines
    color = _coerce_plan_overlay_color(overlay.color)
    if color != overlay.color:
        replacements["color"] = color
    if not replacements:
        return overlay
    return replace(overlay, **replacements)


def normalize_plan_provider_target(provider_id, target):
    return _normalize_plan_provider_target(provider_id, target)


def get_plan_provider_targets(session):
    return _get_plan_provider_targets(session)


def get_plan_provider_edit_handles(session):
    return session._collect_plan_provider_contributions(
        "get_edit_handles",
        session._normalize_plan_provider_edit_handle,
    )


def get_plan_provider_target_for_object(session, obj):
    return _get_plan_provider_target_for_object(session, obj)


def is_plan_provider_target_object(session, obj):
    return _is_plan_provider_target_object(session, obj)


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


def _coerce_plan_overlay_point(point):
    try:
        return (
            float(point.x),
            float(point.y),
            float(getattr(point, "z", 0.0) or 0.0),
        )
    except AttributeError:
        pass
    try:
        z_value = point[2] if len(point) > 2 else 0.0
        return (float(point[0]), float(point[1]), float(z_value))
    except (TypeError, ValueError, IndexError):
        return None


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


def collect_plan_provider_contributions(session, method_name, normalizer):
    with session._plan_perf_trace_span(f"collect_plan_provider_contributions_{method_name}"):
        document_is_alive = getattr(session, "_document_is_alive", None)
        if callable(document_is_alive) and not document_is_alive():
            return ()
        refresh_cache = getattr(session, "_plan_provider_refresh_cache", None)
        cache_key = ("provider_contributions", str(method_name or ""))
        if isinstance(refresh_cache, dict) and cache_key in refresh_cache:
            return refresh_cache[cache_key]
        try:
            context = session.get_plan_edit_context()
        except (ReferenceError, RuntimeError):
            return ()
        results = []
        for provider in session.get_plan_provider_registry().iter_providers():
            provider_id = session._get_plan_provider_id(provider)
            if not provider_id:
                continue
            method = getattr(provider, method_name, None)
            if not callable(method):
                continue
            span_name = "plan_provider_{}_{}".format(
                provider_id.replace(" ", "_"),
                method_name,
            )
            with session._plan_perf_trace_span(span_name):
                try:
                    provided = method(context)
                except Exception as exc:
                    FreeCAD.Console.PrintError(
                        translate(
                            "BIM_PlanEdit",
                            "Plan Edit provider '{provider}' failed in {method}: {error}\n",
                        ).format(provider=provider_id, method=method_name, error=exc)
                    )
                    continue
            contribution_count = 0
            for contribution in session._coerce_plan_provider_results(provided):
                normalized = normalizer(provider_id, contribution)
                if normalized is not None:
                    results.append(normalized)
                    contribution_count += 1
            session._plan_perf_count(
                "plan_provider_{}_{}_contributions".format(provider_id, method_name),
                contribution_count,
            )
        contributions = tuple(results)
        if isinstance(refresh_cache, dict):
            refresh_cache[cache_key] = contributions
        return contributions


def _execute_plan_provider_action_callback(execute_action, action_key, context, session, payload):
    if payload is None:
        return execute_action(action_key, context=context, session=session)
    try:
        signature = inspect.signature(execute_action)
    except (TypeError, ValueError):
        return execute_action(action_key, context=context, session=session)
    parameters = signature.parameters
    accepts_payload = "payload" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if accepts_payload:
        return execute_action(action_key, context=context, session=session, payload=payload)
    return execute_action(action_key, context=context, session=session)


def execute_plan_provider_action(
    session,
    provider_id,
    action_key,
    transaction_label="",
    payload=None,
):
    document_is_alive = getattr(session, "_document_is_alive", None)
    if callable(document_is_alive) and not document_is_alive():
        return False
    provider = session.get_plan_provider_registry().get_provider(provider_id)
    if provider is None:
        return False
    execute_action = getattr(provider, "execute_action", None)
    if not callable(execute_action):
        return False

    context = session.get_plan_edit_context()
    transaction_label = str(transaction_label or "").strip()
    defer_updates = getattr(session, "defer_document_visual_updates", None)
    visual_update_context = defer_updates() if callable(defer_updates) else nullcontext()
    try:
        with visual_update_context:
            if transaction_label:
                with PlanEditTransaction(session.doc, transaction_label):
                    handled = _execute_plan_provider_action_callback(
                        execute_action,
                        action_key,
                        context,
                        session,
                        payload,
                    )
            else:
                handled = _execute_plan_provider_action_callback(
                    execute_action,
                    action_key,
                    context,
                    session,
                    payload,
                )
            if handled is not False:
                try:
                    if session.doc is not None:
                        session.doc.recompute()
                except Exception:
                    pass
    except Exception as exc:
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider '{provider}' action '{action}' failed: {error}\n",
            ).format(provider=provider_id, action=action_key, error=exc)
        )
        return False

    if handled is False:
        return False

    session._refresh_primary_selected_plan_target()
    session._invalidate_document_dependent_plan_visuals()
    session._refresh_task_panel_status()
    session._focus_plan_view()
    return True
