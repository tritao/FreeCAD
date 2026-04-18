# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from dataclasses import replace

import FreeCAD

from bimplan.providers import (
    PlanActionSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanSuggestionSpec,
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
    if overlay.provider_id == provider_id:
        return overlay
    return replace(overlay, provider_id=str(provider_id or ""))


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


def execute_plan_provider_action(session, provider_id, action_key, transaction_label=""):
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
                handled = execute_action(action_key, context=context, session=session)
        else:
            handled = execute_action(action_key, context=context, session=session)
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
