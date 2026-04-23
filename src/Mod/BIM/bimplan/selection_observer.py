# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI selection and observer helpers for BIM Plan Edit."""

from contextlib import contextmanager

import FreeCAD
import FreeCADGui

from . import provider_runtime as plan_provider_runtime


def _get_selection_compat_module():
    from . import selection as plan_selection

    return plan_selection


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


@contextmanager
def selection_changes_suppressed(session):
    previous_ignore = session._ignore_selection_changes
    session._ignore_selection_changes = True
    try:
        yield
    finally:
        session._ignore_selection_changes = previous_ignore


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


def set_gui_selection(session, selection):
    session._gui_selection_sync_queued = False
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = None
    with session._plan_perf_trace_span("set_gui_selection"):
        with session._selection_changes_suppressed():
            try:
                with session._plan_perf_trace_span("set_gui_selection_clear"):
                    FreeCADGui.Selection.clearSelection()
                seen = set()
                for obj in selection or []:
                    if not obj:
                        continue
                    key = (
                        getattr(getattr(obj, "Document", None), "Name", None),
                        getattr(obj, "Name", None),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    with session._plan_perf_trace_span("set_gui_selection_add"):
                        session._add_gui_selection_object(obj)
            except Exception:
                pass
        with session._plan_perf_trace_span("set_gui_selection_secondary_targets"):
            session._sync_secondary_selected_plan_targets_from_selection(selection)


def set_gui_selection_object(session, obj):
    if not obj:
        return
    session._set_gui_selection([obj])


def schedule_gui_selection_object(session, obj, delay_ms=80):
    if session._tearing_down or not obj:
        return
    session._gui_selection_sync_queued = True
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = obj
    generation = session._gui_selection_sync_generation
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            delay_ms,
            lambda generation=generation: session._run_scheduled_gui_selection_sync(generation),
        )
    except Exception:
        session._run_scheduled_gui_selection_sync(generation)


def run_scheduled_gui_selection_sync(session, generation=None):
    if not session._gui_selection_sync_queued:
        return
    if generation is not None and generation != session._gui_selection_sync_generation:
        return
    obj = session._queued_gui_selection_object
    if obj is None:
        session._gui_selection_sync_queued = False
        return
    with session._plan_perf_trace_event("scheduled_gui_selection_sync"):
        if session._tearing_down:
            session._gui_selection_sync_queued = False
            session._queued_gui_selection_object = None
            return
        set_gui_selection_object(session, obj)


def attach_selection_observer(session):
    if not session._selection_observer_added:
        FreeCADGui.Selection.addObserver(session)
        session._selection_observer_added = True


def detach_selection_observer(session):
    if session._selection_observer_added:
        FreeCADGui.Selection.removeObserver(session)
        session._selection_observer_added = False


def schedule_selection_refresh(session):
    if session._tearing_down or session._ignore_selection_changes:
        return
    if session._selection_refresh_queued:
        return
    session._selection_refresh_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._run_scheduled_selection_refresh)
    except Exception:
        session._run_scheduled_selection_refresh()


def run_scheduled_selection_refresh(session):
    if not session._selection_refresh_queued:
        return
    session._selection_refresh_queued = False
    with session._plan_perf_trace_event("selection_observer_refresh"):
        if session._tearing_down or session._ignore_selection_changes:
            return
        session._refresh_primary_selected_plan_target()


def selection_observer_add(session, doc, obj, sub, point):
    with session._plan_perf_trace_event(
        "selection_observer_add",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        if sub in ("EditNode0", "EditNode1", "EditNode2"):
            return
        del doc, obj, sub, point
        session._schedule_selection_refresh()


def selection_observer_remove(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_remove",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc, obj, sub
        session._schedule_selection_refresh()


def selection_observer_set(session, doc):
    with session._plan_perf_trace_event("selection_observer_set", selection_document=doc):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc
        session._schedule_selection_refresh()


def selection_observer_clear(session, doc):
    selected_kind, selected_obj = session.selection.get_selected_plan_target()
    with session._plan_perf_trace_event(
        "selection_observer_clear",
        selection_document=doc,
        selected_before_clear=session._plan_perf_describe_target(selected_kind, selected_obj),
        selected_before_clear_kind=selected_kind or "none",
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc
        session._schedule_selection_refresh()


def selection_observer_set_preselection(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_set_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if not _should_filter_hidden_provider_preselection(session, doc, obj):
            return
        session._plan_perf_count("provider_preselection_filtered")
        _get_selection_compat_module()._clear_gui_preselection()


def selection_observer_remove_preselection(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_remove_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")


def clear_hidden_provider_preselection(session):
    if session._tearing_down:
        return False
    preselected_obj = _get_selection_compat_module()._get_gui_preselection_object(session)
    if preselected_obj is None:
        return False
    if not _should_filter_hidden_provider_preselection_for_object(session, preselected_obj):
        return False
    session._plan_perf_count("provider_preselection_cleared_for_mode")
    return _get_selection_compat_module()._clear_gui_preselection()


def _should_filter_hidden_provider_preselection(session, doc_name, obj_name):
    preselected_obj = _resolve_document_object(session, doc_name, obj_name)
    if preselected_obj is None:
        return False
    return _should_filter_hidden_provider_preselection_for_object(session, preselected_obj)


def _should_filter_hidden_provider_preselection_for_object(session, obj):
    if not plan_provider_runtime.is_plan_provider_target_object(session, obj):
        return False
    return not plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj)


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not session._is_valid_plan_target(kind, obj):
        return False
    return bool(plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj))


def resolve_selected_target_for_gui_object(
    session,
    selected,
    *,
    pending_kind=None,
    pending_target=None,
    preserved_kind=None,
    preserved_target=None,
):
    if selected is None:
        return (None, None)
    if selected == pending_target and session._is_valid_plan_target(pending_kind, pending_target):
        return (pending_kind, pending_target)
    if _should_preserve_provider_selected_target(
        session,
        preserved_kind,
        preserved_target,
        selected,
    ):
        return (preserved_kind, preserved_target)
    return session._get_plan_target_for_object(selected)


def _resolve_document_object(session, document_name, object_name):
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


def _get_gui_preselection_object(session):
    try:
        preselection = FreeCADGui.Selection.getPreselection()
    except Exception:
        return None
    try:
        obj = getattr(preselection, "Object", None)
    except Exception:
        obj = None
    if obj is not None:
        return obj
    return _resolve_document_object(
        session,
        getattr(preselection, "DocumentName", ""),
        getattr(preselection, "ObjectName", ""),
    )


def _clear_gui_preselection():
    try:
        FreeCADGui.Selection.clearPreselection()
        return True
    except Exception:
        return False
