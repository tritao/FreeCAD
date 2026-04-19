# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from dataclasses import replace
import inspect

import FreeCAD

from bimplan.providers import (
    PlanActionSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanOverlayTargetSpec,
    PlanSuggestionSpec,
    PlanToolSpec,
)
from bimplan.semantics import PlanSemanticRecord
from bimplan.targets import PlanTarget
from bimplan.transactions import PlanEditTransaction

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
    if tool.provider_id == provider_id:
        return tool
    return replace(tool, provider_id=str(provider_id or ""))


def normalize_plan_provider_issue(session, provider_id, issue):
    if not isinstance(issue, PlanIssueSpec):
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


def normalize_plan_provider_overlay(provider_id, overlay):
    if not isinstance(overlay, PlanOverlaySpec):
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
            target = _coerce_plan_overlay_target(raw_target)
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


def _coerce_plan_overlay_target(target):
    if target is None:
        return PlanOverlayTargetSpec()
    if isinstance(target, PlanOverlayTargetSpec):
        document_name = str(target.document_name or "").strip()
        object_name = str(target.object_name or "").strip()
        target_kind = str(target.target_kind or "").strip()
        subname = str(target.subname or "").strip()
    elif isinstance(target, dict):
        document_name = str(target.get("document_name", "") or "").strip()
        object_name = str(target.get("object_name", "") or "").strip()
        target_kind = str(target.get("target_kind", "") or "").strip()
        subname = str(target.get("subname", "") or "").strip()
    else:
        document_name = str(getattr(target, "document_name", "") or "").strip()
        object_name = str(getattr(target, "object_name", "") or "").strip()
        target_kind = str(getattr(target, "target_kind", "") or "").strip()
        subname = str(getattr(target, "subname", "") or "").strip()
    return PlanOverlayTargetSpec(
        document_name=document_name,
        object_name=object_name,
        target_kind=target_kind,
        subname=subname,
    )


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
        context = session.get_plan_edit_context()
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
        return tuple(results)


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
    provider = session.get_plan_provider_registry().get_provider(provider_id)
    if provider is None:
        return False
    execute_action = getattr(provider, "execute_action", None)
    if not callable(execute_action):
        return False

    context = session.get_plan_edit_context()
    transaction_label = str(transaction_label or "").strip()
    try:
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

    try:
        if session.doc is not None:
            session.doc.recompute()
    except Exception:
        pass
    session._refresh_primary_selected_plan_target()
    session._invalidate_document_dependent_plan_visuals()
    session._refresh_task_panel_status()
    session._focus_plan_view()
    return True
