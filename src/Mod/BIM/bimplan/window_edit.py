# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan Edit helpers for editing hosted window dimensions and styles."""

import ArchWindow
import FreeCAD

translate = FreeCAD.Qt.translate


def get_window_style_preset_options():
    return ArchWindow.getWindowPresetNames("window")


def can_edit_window_style_preset(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canApplyWindowPreset(window))


def can_edit_window_width(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canEditWindowWidth(window))


def can_edit_window(window):
    return bool(can_edit_window_style_preset(window) or can_edit_window_width(window))


def get_window_width_mm(window):
    return ArchWindow.getWindowWidthMm(window)


def get_window_width_user_string(window):
    return ArchWindow.getWindowWidthUserString(window)


def get_selected_window_style_preset(session):
    window = session._get_selected_plan_target_object("opening")
    if not ArchWindow.isWindowObject(window):
        return ""
    preset_name = ArchWindow.getWindowPresetName(window)
    if preset_name in get_window_style_preset_options():
        return preset_name
    return ""


def can_apply_selected_window_style_preset(session):
    window = session._get_selected_plan_target_object("opening")
    return can_edit_window_style_preset(window)


def get_selected_window_width_mm(session):
    window = session._get_selected_plan_target_object("opening")
    return get_window_width_mm(window)


def get_selected_window_width_text(session):
    window = session._get_selected_plan_target_object("opening")
    return get_window_width_user_string(window)


def can_apply_selected_window_width(session):
    window = session._get_selected_plan_target_object("opening")
    return can_edit_window_width(window)


def apply_selected_window_style_preset(session, preset_name):
    window = session._get_selected_plan_target_object("opening")
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
    window = session._get_selected_plan_target_object("opening")
    if not can_edit_window_width(window):
        return False

    target_width = _parse_length_mm(value)
    if target_width is None or target_width <= 0.0:
        return False

    current_width = get_window_width_mm(window)
    if current_width is not None and abs(target_width - current_width) <= 1e-6:
        return False

    if not ArchWindow.setWindowWidth(
        window,
        target_width,
        preserve_anchor=True,
        transaction_label=translate("BIM_PlanEdit", "Change Window Width"),
    ):
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


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
