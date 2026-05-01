# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider action execution helpers for BIM Plan Edit integrations."""

import FreeCAD

from .contracts import PlanActionResult, PlanEditContext
from bimplan.transactions import PlanEditTransaction

translate = FreeCAD.Qt.translate


class _UnhandledProviderAction(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


def _runtime():
    from bimplan.providers import runtime as provider_runtime

    return provider_runtime


def _warn_post_commit_recompute_failure(action_label, exc):
    message = str(exc or "").strip() or type(exc).__name__
    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Completed {action}, but follow-up recompute failed: {error}\n",
        ).format(action=action_label, error=message)
    )


def _coerce_provider_action_result(result):
    if isinstance(result, PlanActionResult):
        return bool(result.handled), str(result.message or "").strip()
    return bool(result), ""


def _provider_action_was_handled(result):
    handled, _message = _coerce_provider_action_result(result)
    return handled


def _get_provider_action_feedback_message(session):
    status_text = getattr(session, "status_text", None)
    get_feedback = getattr(status_text, "get_integration_feedback_message", None)
    if not callable(get_feedback):
        return ""
    return str(get_feedback() or "").strip()


def _clear_provider_action_feedback_message(session):
    status_text = getattr(session, "status_text", None)
    clear_feedback = getattr(status_text, "clear_integration_feedback_message", None)
    if callable(clear_feedback):
        clear_feedback()


def _set_provider_action_feedback_message(session, message):
    normalized = str(message or "").strip()
    if not normalized:
        return ""
    status_text = getattr(session, "status_text", None)
    set_feedback = getattr(status_text, "set_integration_feedback_message", None)
    if callable(set_feedback):
        normalized = str(set_feedback(normalized) or normalized)
    task_panels = getattr(session, "task_panels", None)
    refresh_status = getattr(task_panels, "refresh_task_panel_status", None)
    if callable(refresh_status):
        refresh_status()
    return normalized


def _ensure_provider_action_feedback_message(session, message):
    existing = _get_provider_action_feedback_message(session)
    if existing:
        return existing
    return _set_provider_action_feedback_message(session, message)


def _execute_plan_provider_action_callback(
    execute_action,
    action_key,
    context,
    action_context,
    payload,
):
    if payload is None:
        return execute_action(action_key, context, action_context)
    return execute_action(action_key, context, action_context, payload)


def _get_plan_provider_action_executor(session, provider_id):
    provider_runtime = _runtime()
    provider = provider_runtime._get_plan_provider_registry(session).get_provider(provider_id)
    if provider is None:
        return None
    execute_action = getattr(provider, "execute_action", None)
    if not callable(execute_action):
        return None
    return execute_action


def _run_plan_provider_action(
    session,
    execute_action,
    action_key,
    transaction_label="",
    payload=None,
):
    provider_runtime = _runtime()
    context = provider_runtime._get_plan_edit_context_or_none(session)
    if context is None:
        return False
    action_context = provider_runtime.get_plan_provider_action_context(session, payload=payload)
    transaction_label = str(transaction_label or "").strip()
    with provider_runtime._get_document_visual_update_scope(session):
        try:
            if transaction_label:
                with PlanEditTransaction(session.doc, transaction_label):
                    handled = provider_runtime._execute_plan_provider_action_callback(
                        execute_action,
                        action_key,
                        context,
                        action_context,
                        payload,
                    )
                    if not _provider_action_was_handled(handled):
                        raise _UnhandledProviderAction(handled)
            else:
                handled = provider_runtime._execute_plan_provider_action_callback(
                    execute_action,
                    action_key,
                    context,
                    action_context,
                    payload,
                )
        except _UnhandledProviderAction as exc:
            handled = exc.result
        if _provider_action_was_handled(handled):
            try:
                if session.doc is not None:
                    session.doc.recompute()
            except Exception as exc:
                _warn_post_commit_recompute_failure(
                    transaction_label
                    or translate("BIM_PlanEdit", "provider action '{action}'").format(
                        action=action_key
                    ),
                    exc,
                )
    return handled


def _finalize_plan_provider_action(session):
    lifecycle_state = getattr(session, "lifecycle_state", None)
    if lifecycle_state is not None and (
        getattr(lifecycle_state, "tearing_down", False)
        or getattr(lifecycle_state, "finishing", False)
    ):
        return
    if not session.document_visuals.document_is_alive():
        return
    session.selection.refresh.refresh_primary_selected_plan_target()
    session.document_visuals.invalidate_document_dependent_plan_visuals()
    session.task_panels.refresh_task_panel_status()
    session.viewport.focus_plan_view()


def execute_plan_provider_action(
    session,
    provider_id,
    action_key,
    transaction_label="",
    payload=None,
):
    provider_runtime = _runtime()
    if not session.document_visuals.document_is_alive():
        return False
    execute_action = provider_runtime._get_plan_provider_action_executor(session, provider_id)
    if execute_action is None:
        return False

    try:
        handled = provider_runtime._run_plan_provider_action(
            session,
            execute_action,
            action_key,
            transaction_label=transaction_label,
            payload=payload,
        )
    except Exception as exc:
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider '{provider}' action '{action}' failed: {error}\n",
            ).format(provider=provider_id, action=action_key, error=exc)
        )
        return False

    handled, failure_message = _coerce_provider_action_result(handled)
    if not handled:
        if failure_message:
            _set_provider_action_feedback_message(session, failure_message)
        return False

    _clear_provider_action_feedback_message(session)
    provider_runtime._finalize_plan_provider_action(session)
    return True


def get_plan_provider_action_context(session, payload=None):
    provider_runtime = _runtime()
    action_context = provider_runtime._call_provider_method(
        session,
        "get_plan_provider_action_context",
        payload=payload,
        default=provider_runtime._MISSING,
    )
    if action_context is not provider_runtime._MISSING:
        return action_context
    doc = session.doc if session.document_visuals.document_is_alive() else None
    return PlanEditContext.make_action_context(
        session,
        payload=payload,
        document_name=session.visibility.safe_plan_object_name(doc),
        current_tool=str(session.current_tool or ""),
    )
