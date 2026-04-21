# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan Edit helpers for editing hosted window dimensions and styles."""

import ArchWindow
import FreeCAD

translate = FreeCAD.Qt.translate
_WINDOW_REWRITE_METHODS = (
    "deleteAllConstraints",
    "deleteAllGeometry",
    "addConstraint",
    "addGeometry",
)


def get_window_style_preset_options():
    return ArchWindow.getWindowPresetNames("window")


def can_edit_window_style_preset(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canApplyWindowPreset(window))


def can_edit_window_width(window):
    if not ArchWindow.isWindowObject(window):
        return False
    base = getattr(window, "Base", None)
    if base is None:
        return False
    if _has_named_constraint(base, "Width"):
        return True
    if not all(hasattr(base, method_name) for method_name in _WINDOW_REWRITE_METHODS):
        return False
    if _get_window_width_mm(window) is None:
        return False
    return _is_simple_width_scalable_sketch(base)


def can_edit_window(window):
    return bool(can_edit_window_style_preset(window) or can_edit_window_width(window))


def get_window_width_mm(window):
    width = _get_window_width_mm(window)
    if width is None or width <= 0.0:
        return None
    return float(width)


def get_window_width_user_string(window):
    width = get_window_width_mm(window)
    if width is None:
        return ""
    return FreeCAD.Units.Quantity(width, FreeCAD.Units.Length).UserString


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

    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Change Window Width"))
        if _has_named_constraint(getattr(window, "Base", None), "Width"):
            window.Width = target_width
        else:
            if not _rewrite_window_width_by_scaling(window, target_width):
                raise RuntimeError("Window width rewrite failed")
            if hasattr(window, "Width"):
                window.Width = target_width
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


def _get_window_width_mm(window):
    base = getattr(window, "Base", None)

    width = _get_named_sketch_constraint_mm(base, "Width")
    if width is not None and width > 0.0:
        return width

    width = _get_sketch_local_width_mm(base)
    if width is not None and width > 0.0:
        return width

    width = _coerce_length_mm(getattr(window, "Width", None))
    if width is not None and width > 0.0:
        return width

    return None


def _rewrite_window_width_by_scaling(window, target_width):
    import Part

    base = getattr(window, "Base", None)
    if base is None or not _is_simple_width_scalable_sketch(base):
        return False

    x_bounds = _get_sketch_local_x_bounds(base)
    if x_bounds is None:
        return False

    current_width = x_bounds[1] - x_bounds[0]
    if current_width <= 1e-6:
        return False

    center_x = (x_bounds[0] + x_bounds[1]) * 0.5
    scale = float(target_width) / float(current_width)
    placement = FreeCAD.Placement(base.Placement)
    geometry = tuple(getattr(base, "Geometry", ()) or ())
    constraints = tuple(getattr(base, "Constraints", ()) or ())

    scaled_geometry = []
    for element in geometry:
        if element.__class__.__name__ != "LineSegment":
            return False
        start_point = FreeCAD.Vector(element.StartPoint)
        end_point = FreeCAD.Vector(element.EndPoint)
        start_point.x = center_x + ((start_point.x - center_x) * scale)
        end_point.x = center_x + ((end_point.x - center_x) * scale)
        scaled_geometry.append(Part.LineSegment(start_point, end_point))

    base.deleteAllConstraints()
    base.deleteAllGeometry()
    base.Placement = placement

    for element in scaled_geometry:
        base.addGeometry(element)

    for constraint in constraints:
        index = base.addConstraint(constraint)
        name = str(getattr(constraint, "Name", "") or "").strip()
        if not name:
            continue
        try:
            base.renameConstraint(index, name)
        except Exception:
            pass

    return True


def _is_simple_width_scalable_sketch(sketch):
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if not geometry:
        return False
    if any(element.__class__.__name__ != "LineSegment" for element in geometry):
        return False
    constraints = tuple(getattr(sketch, "Constraints", ()) or ())
    return not any(str(getattr(constraint, "Name", "") or "").strip() for constraint in constraints)


def _get_sketch_local_width_mm(sketch):
    x_bounds = _get_sketch_local_x_bounds(sketch)
    if x_bounds is None:
        return None
    width = x_bounds[1] - x_bounds[0]
    if width <= 1e-6:
        return None
    return float(width)


def _get_sketch_local_x_bounds(sketch):
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if not geometry:
        return None

    min_x = None
    max_x = None
    for element in geometry:
        try:
            bound_box = element.toShape().BoundBox
        except Exception:
            continue
        current_min = float(bound_box.XMin)
        current_max = float(bound_box.XMax)
        min_x = current_min if min_x is None else min(min_x, current_min)
        max_x = current_max if max_x is None else max(max_x, current_max)

    if min_x is None or max_x is None:
        return None
    return (float(min_x), float(max_x))


def _get_named_sketch_constraint_mm(sketch, name):
    if sketch is None or not hasattr(sketch, "getDatum"):
        return None
    try:
        return _coerce_length_mm(sketch.getDatum(str(name or "").strip()))
    except Exception:
        return None


def _has_named_constraint(sketch, name):
    if sketch is None:
        return False
    name = str(name or "").strip()
    if not name:
        return False
    constraints = tuple(getattr(sketch, "Constraints", ()) or ())
    return any(
        str(getattr(constraint, "Name", "") or "").strip() == name for constraint in constraints
    )


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
