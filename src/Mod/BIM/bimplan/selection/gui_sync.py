# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI selection sync and observer helpers for BIM Plan Edit."""

from contextlib import contextmanager

import FreeCAD
import FreeCADGui
from bimplan.providers import runtime as plan_provider_runtime


@contextmanager
def selection_changes_suppressed(session):
    previous_ignore = session.lifecycle_state.ignore_selection_changes
    session.lifecycle_state.ignore_selection_changes = True
    try:
        yield
    finally:
        session.lifecycle_state.ignore_selection_changes = previous_ignore


def get_gui_selection_ex():
    try:
        return list(FreeCADGui.Selection.getSelectionEx() or [])
    except (ReferenceError, RuntimeError):
        return []


def get_gui_selection():
    try:
        return list(FreeCADGui.Selection.getSelection() or [])
    except (ReferenceError, RuntimeError):
        return []


def add_gui_selection_object(obj):
    if not obj:
        return
    doc_name = getattr(getattr(obj, "Document", None), "Name", None)
    obj_name = getattr(obj, "Name", None)
    try:
        if doc_name and obj_name:
            FreeCADGui.Selection.addSelection(doc_name, obj_name)
        else:
            FreeCADGui.Selection.addSelection(obj)
    except Exception:
        if doc_name and obj_name:
            try:
                FreeCADGui.Selection.addSelection(obj)
            except Exception:
                pass


def _reset_gui_selection_sync_state(session):
    session._gui_selection_sync_queued = False
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = None


def _finish_gui_selection_sync(session, generation=None):
    current_generation = getattr(session, "_gui_selection_sync_generation", 0)
    if generation is not None and generation != current_generation:
        return
    session._gui_selection_sync_in_progress = False


def _schedule_finish_gui_selection_sync(session, generation):
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            0,
            lambda generation=generation: _finish_gui_selection_sync(session, generation),
        )
    except Exception:
        _finish_gui_selection_sync(session, generation)


def _apply_gui_selection(session, selection):
    normalized_selection = session.selection.normalize_gui_object_selection(selection)
    with session.performance.plan_perf_trace_span("set_gui_selection"):
        with selection_changes_suppressed(session):
            try:
                with session.performance.plan_perf_trace_span("set_gui_selection_clear"):
                    FreeCADGui.Selection.clearSelection()
                seen = set()
                for obj in normalized_selection:
                    if not obj:
                        continue
                    key = (
                        getattr(getattr(obj, "Document", None), "Name", None),
                        getattr(obj, "Name", None),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    with session.performance.plan_perf_trace_span("set_gui_selection_add"):
                        add_gui_selection_object(obj)
            except Exception:
                pass
        with session.performance.plan_perf_trace_span("set_gui_selection_secondary_targets"):
            session.selection.sync_secondary_selected_plan_targets_from_selection(
                normalized_selection
            )


def set_gui_selection(session, selection):
    _reset_gui_selection_sync_state(session)
    _apply_gui_selection(session, selection)


def set_gui_selection_object(session, obj):
    if not obj:
        return
    set_gui_selection(session, [obj])


def schedule_gui_selection_object(session, obj, delay_ms=80):
    if session.lifecycle_state.tearing_down or not obj:
        return
    session._gui_selection_sync_queued = True
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = obj
    generation = session._gui_selection_sync_generation
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            delay_ms,
            lambda generation=generation: run_scheduled_gui_selection_sync(session, generation),
        )
    except Exception:
        run_scheduled_gui_selection_sync(session, generation)


def run_scheduled_gui_selection_sync(session, generation=None):
    if not session._gui_selection_sync_queued:
        return
    if generation is not None and generation != session._gui_selection_sync_generation:
        return
    obj = session._queued_gui_selection_object
    if obj is None:
        session._gui_selection_sync_queued = False
        return
    with session.performance.plan_perf_trace_event("scheduled_gui_selection_sync"):
        if session.lifecycle_state.tearing_down:
            session._gui_selection_sync_queued = False
            session._queued_gui_selection_object = None
            return
        session._gui_selection_sync_in_progress = True
        current_generation = session._gui_selection_sync_generation
        try:
            set_gui_selection_object(session, obj)
        finally:
            _schedule_finish_gui_selection_sync(session, current_generation)


def attach_selection_observer(session):
    if not session._selection_observer_added:
        FreeCADGui.Selection.addObserver(session)
        session._selection_observer_added = True


def detach_selection_observer(session):
    if session._selection_observer_added:
        FreeCADGui.Selection.removeObserver(session)
        session._selection_observer_added = False


def schedule_selection_refresh(session):
    if session.lifecycle_state.tearing_down or session.lifecycle_state.ignore_selection_changes:
        return
    if session._selection_refresh_queued:
        return
    session._selection_refresh_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, lambda: run_scheduled_selection_refresh(session))
    except Exception:
        run_scheduled_selection_refresh(session)


def schedule_clear_plan_selection_state(session):
    if session.lifecycle_state.tearing_down or session.lifecycle_state.ignore_selection_changes:
        return
    if getattr(session, "_clear_plan_selection_state_queued", False):
        return
    session._clear_plan_selection_state_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, lambda: run_scheduled_clear_plan_selection_state(session))
    except Exception:
        run_scheduled_clear_plan_selection_state(session)


def run_scheduled_clear_plan_selection_state(session):
    if not getattr(session, "_clear_plan_selection_state_queued", False):
        return
    session._clear_plan_selection_state_queued = False
    with session.performance.plan_perf_trace_event("scheduled_clear_plan_selection_state"):
        if session.lifecycle_state.tearing_down or session.lifecycle_state.ignore_selection_changes:
            return
        session.selection.clear_plan_selection_state()


def run_scheduled_selection_refresh(session):
    if not session._selection_refresh_queued:
        return
    session._selection_refresh_queued = False
    with session.performance.plan_perf_trace_event("selection_observer_refresh"):
        if session.lifecycle_state.tearing_down or session.lifecycle_state.ignore_selection_changes:
            return
        session.selection.refresh_primary_selected_plan_target()


def _trace_selection_observer_event(session, event_name, **fields):
    return session.performance.plan_perf_trace_event(event_name, **fields)


def resolve_document_object(session, document_name, object_name):
    object_name = str(object_name or "").strip()
    if not object_name:
        return None
    document_name = str(document_name or "").strip()
    doc = None
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = None
    if doc is None:
        doc = getattr(session, "doc", None)
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def is_visible_provider_target_object(session, obj):
    validate = getattr(session, "_is_valid_plan_target", None)
    if callable(validate) and validate("provider", obj):
        return bool(plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj))
    if not plan_provider_runtime.is_plan_provider_target_object(session, obj):
        return False
    return bool(plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj))


def should_filter_hidden_provider_preselection_for_object(session, obj):
    return not is_visible_provider_target_object(session, obj)


def should_filter_hidden_provider_preselection(session, doc_name, obj_name):
    preselected_obj = resolve_document_object(session, doc_name, obj_name)
    if preselected_obj is None:
        return False
    return should_filter_hidden_provider_preselection_for_object(session, preselected_obj)


def _should_skip_selection_observer_callback(session):
    session.performance.plan_perf_count("selection_observer_callbacks")
    return (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.ignore_selection_changes
        or getattr(session, "_gui_selection_sync_in_progress", False)
    )


def _schedule_selection_refresh_from_observer(session):
    if _should_skip_selection_observer_callback(session):
        return False
    schedule_selection_refresh(session)
    return True


def selection_observer_add(session, doc, obj, sub, point):
    with _trace_selection_observer_event(
        session,
        "selection_observer_add",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        if _should_skip_selection_observer_callback(session):
            return
        if sub in ("EditNode0", "EditNode1", "EditNode2"):
            return
        del doc, obj, sub, point
        schedule_selection_refresh(session)


def selection_observer_remove(session, doc, obj, sub):
    with _trace_selection_observer_event(
        session,
        "selection_observer_remove",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        if not _schedule_selection_refresh_from_observer(session):
            return
        del doc, obj, sub


def selection_observer_set(session, doc):
    with _trace_selection_observer_event(session, "selection_observer_set", selection_document=doc):
        if not _schedule_selection_refresh_from_observer(session):
            return
        del doc


def selection_observer_clear(session, doc):
    selected_kind, selected_obj = session.selection.get_selected_plan_target()
    with _trace_selection_observer_event(
        session,
        "selection_observer_clear",
        selection_document=doc,
        selected_before_clear=session.performance.plan_perf_describe_target(
            selected_kind, selected_obj
        ),
        selected_before_clear_kind=selected_kind or "none",
    ):
        if not _schedule_selection_refresh_from_observer(session):
            return
        del doc


def selection_observer_set_preselection(session, doc, obj, sub):
    with _trace_selection_observer_event(
        session,
        "selection_observer_set_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        if _should_skip_selection_observer_callback(session):
            return
        if not should_filter_hidden_provider_preselection(session, doc, obj):
            return
        session.performance.plan_perf_count("provider_preselection_filtered")
        clear_gui_preselection()


def selection_observer_remove_preselection(session, doc, obj, sub):
    with _trace_selection_observer_event(
        session,
        "selection_observer_remove_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session.performance.plan_perf_count("selection_observer_callbacks")


def _clear_gui_preselection_impl():
    try:
        FreeCADGui.Selection.clearPreselection()
        return True
    except Exception:
        return False


def clear_gui_preselection():
    try:
        import bimplan.selection as plan_selection_pkg
    except Exception:
        plan_selection_pkg = None
    exported = (
        getattr(plan_selection_pkg, "_clear_gui_preselection", None)
        if plan_selection_pkg is not None
        else None
    )
    if callable(exported) and exported is not clear_gui_preselection:
        return exported()
    return _clear_gui_preselection_impl()
