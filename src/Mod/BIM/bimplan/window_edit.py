# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan Edit helpers for editing hosted window styles."""

import ArchWindow
import FreeCAD

translate = FreeCAD.Qt.translate


def get_window_style_preset_options():
    return ArchWindow.getWindowPresetNames("window")


def can_edit_window_style_preset(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canApplyWindowPreset(window))


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
