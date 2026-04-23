# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan Edit helpers for editing hosted window dimensions and styles."""

import ArchWindow
import FreeCAD
from bimplan import selection as plan_selection

translate = FreeCAD.Qt.translate


def get_window_style_preset_options():
    return ArchWindow.getWindowPresetNames("window")


def can_edit_window_style_preset(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canApplyWindowPreset(window))


def can_edit_window_width(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canEditWindowWidth(window))


def can_edit_window_height(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canEditWindowHeight(window))


def can_edit_window(window):
    return bool(
        can_edit_window_style_preset(window)
        or can_edit_window_width(window)
        or can_edit_window_height(window)
    )


def get_window_width_mm(window):
    return ArchWindow.getWindowWidthMm(window)


def get_window_width_user_string(window):
    return ArchWindow.getWindowWidthUserString(window)


def get_window_height_mm(window):
    return ArchWindow.getWindowHeightMm(window)


def get_window_height_user_string(window):
    return ArchWindow.getWindowHeightUserString(window)


def get_selected_window_style_preset(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    if not ArchWindow.isWindowObject(window):
        return ""
    preset_name = ArchWindow.getWindowPresetName(window)
    if preset_name in get_window_style_preset_options():
        return preset_name
    return ""


def can_apply_selected_window_style_preset(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_style_preset(window)


def get_selected_window_width_mm(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_width_mm(window)


def get_selected_window_width_text(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_width_user_string(window)


def get_selected_window_height_mm(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_height_mm(window)


def get_selected_window_height_text(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_height_user_string(window)


def can_apply_selected_window_width(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_width(window)


def can_apply_selected_window_height(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_height(window)


def can_apply_selected_window_size(session, width_value=None, height_value=None):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    resize_targets = _resolve_window_resize_targets(
        window,
        width_value=width_value,
        height_value=height_value,
    )
    if resize_targets is None:
        return False

    target_width, target_height = resize_targets
    status = ArchWindow.validateWindowResize(
        window,
        width=target_width,
        height=target_height,
    )
    return bool(status.allowed and not status.noop)


def apply_selected_window_style_preset(session, preset_name):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    if not can_edit_window_style_preset(window):
        return False

    preset_name = str(preset_name or "").strip()
    if preset_name not in get_window_style_preset_options():
        return False

    if not ArchWindow.applyWindowPreset(
        window,
        preset_name,
        transaction_label=translate("BIM_PlanEdit", "Change Window Style"),
    ):
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


def set_selected_window_width(session, value):
    return _set_selected_window_size(
        session,
        width_value=value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Width"),
    )


def set_selected_window_height(session, value):
    return _set_selected_window_size(
        session,
        height_value=value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Height"),
    )


def set_selected_window_size(session, width_value=None, height_value=None):
    return _set_selected_window_size(
        session,
        width_value=width_value,
        height_value=height_value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Size"),
    )


def _set_selected_window_size(
    session,
    width_value=None,
    height_value=None,
    transaction_label=None,
):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    resize_targets = _resolve_window_resize_targets(
        window,
        width_value=width_value,
        height_value=height_value,
    )
    if resize_targets is None:
        return False

    target_width, target_height = resize_targets
    if not ArchWindow.resizeWindow(
        window,
        width=target_width,
        height=target_height,
        preserve_anchor=True,
        transaction_label=transaction_label,
    ):
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


def _resolve_window_resize_targets(window, width_value=None, height_value=None):
    if not ArchWindow.isWindowObject(window):
        return None

    target_width = None
    if can_edit_window_width(window) and width_value is not None:
        target_width = _parse_length_mm(width_value)
        current_width = get_window_width_mm(window)
        if target_width is None or target_width <= 0.0:
            return None
        if current_width is not None and abs(target_width - current_width) <= 1e-6:
            target_width = None

    target_height = None
    if can_edit_window_height(window) and height_value is not None:
        target_height = _parse_length_mm(height_value)
        current_height = get_window_height_mm(window)
        if target_height is None or target_height <= 0.0:
            return None
        if current_height is not None and abs(target_height - current_height) <= 1e-6:
            target_height = None

    if target_width is None and target_height is None:
        return None
    return target_width, target_height


def _parse_length_mm(value):
    if value is None:
        return None

    length = _coerce_length_mm(value)
    if length is not None:
        return length

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(FreeCAD.Units.Quantity(text).Value)
    except Exception:
        return None


def _coerce_length_mm(value):
    try:
        value = value.Value
    except AttributeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
