# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary helpers for BIM Plan Edit."""

import FreeCAD

translate = FreeCAD.Qt.translate


def get_space_reference_point(session, space):
    if not session._is_plan_space_object(space):
        return None
    shape = getattr(space, "Shape", None)
    if shape and hasattr(shape, "CenterOfMass"):
        try:
            return session._project_plan_point(shape.CenterOfMass)
        except Exception:
            pass
    placement = getattr(space, "Placement", None)
    if placement is not None:
        try:
            return session._project_plan_point(placement.Base)
        except Exception:
            pass
    return None


def get_space_boundary_reference_point(session, selection_ex, fallback_space=None):
    points = []
    for selection in selection_ex or []:
        obj = getattr(selection, "Object", None)
        if not obj or obj == fallback_space:
            continue
        subobjects = list(getattr(selection, "SubObjects", []) or [])
        added_subobject_center = False
        for subobject in subobjects:
            center = getattr(subobject, "CenterOfMass", None)
            if center is None:
                continue
            try:
                points.append(FreeCAD.Vector(center.x, center.y, center.z))
                added_subobject_center = True
            except Exception:
                continue
        if added_subobject_center:
            continue
        shape = getattr(obj, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        center = getattr(bound_box, "Center", None) if bound_box is not None else None
        if center is None:
            continue
        try:
            points.append(FreeCAD.Vector(center.x, center.y, center.z))
        except Exception:
            continue
    if points:
        total = FreeCAD.Vector()
        for point in points:
            total = total.add(point)
        return total.multiply(1.0 / float(len(points)))
    return session._get_space_reference_point(fallback_space)


def get_space_boundary_entries(session, space):
    if not session._is_plan_space_object(space):
        return []
    import ArchSpace

    entries = []
    for boundary in getattr(space, "Boundaries", []) or []:
        try:
            obj = boundary[0]
            subnames = boundary[1]
        except Exception:
            continue
        entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
    return ArchSpace.normalizeBoundaryLinks(entries)


def space_boundary_key(boundary):
    import ArchSpace

    obj, subnames = boundary
    return (
        getattr(obj, "Name", None),
        tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
    )


def get_selected_space_boundary_links(session, fallback_space=None):
    import ArchSpace

    selection_ex = session._get_gui_selection_ex()
    reference_point = (
        session._get_space_reference_point(fallback_space)
        if fallback_space is not None
        else session._get_space_boundary_reference_point(selection_ex)
    )
    entries = []
    for selection in selection_ex:
        obj = session._get_plan_semantic_object(getattr(selection, "Object", None))
        if not obj:
            continue
        entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
    return ArchSpace.resolveBoundaryLinks(
        entries,
        reference_point=reference_point,
        exclude_objects=(fallback_space,) if fallback_space is not None else None,
    )


def get_space_region_seed_targets(session, targets=None):
    targets = list(targets if targets is not None else session._get_selected_plan_targets())
    if not targets:
        return (None, [])

    space_targets = [target_obj for target_kind, target_obj in targets if target_kind == "space"]
    if len(space_targets) != 1:
        return (None, [])

    if len(targets) == 1:
        boundary_links = session._get_selected_space_boundary_links(fallback_space=space_targets[0])
        if boundary_links:
            return (space_targets[0], [])
        return (None, [])

    wall_targets = [
        (target_kind, target_obj) for target_kind, target_obj in targets if target_kind == "wall"
    ]
    if len(wall_targets) != len(targets) - 1:
        return (None, [])

    return (space_targets[0], wall_targets)


def get_selected_space_region_seed(session, targets=None):
    region_seed_space, _wall_targets = session._get_space_region_seed_targets(targets)
    return region_seed_space


def copy_shape_without_element_map(shape):
    if shape is None:
        return None
    try:
        return shape.copy(noElementMap=True)
    except Exception:
        try:
            return shape.copy()
        except Exception:
            return None


def get_space_creation_request(session, targets=None):
    targets = targets if targets is not None else session._get_selected_plan_targets()
    if not targets:
        return None

    label = None
    region_seed_space = session._get_selected_space_region_seed(targets)
    if region_seed_space is not None:
        boundaries = session._get_selected_space_boundary_links(fallback_space=region_seed_space)
        label = getattr(region_seed_space, "Label", None)
    elif all(target_kind == "wall" for target_kind, _target_obj in targets):
        boundaries = session._get_selected_space_boundary_links()
    else:
        return None

    return {
        "targets": targets,
        "label": label,
        "region_seed_space": region_seed_space,
        "boundaries": boundaries,
    }


def get_space_preflight_report(session, targets=None):
    if session.current_tool != "Select":
        return None

    request = session._get_space_creation_request(targets=targets)
    if not request:
        return None

    import ArchSpace

    return ArchSpace.analyzeBoundaryLinks(
        request["boundaries"],
        label=request["label"],
        seed_space=request["region_seed_space"],
    )


def format_space_preflight_text(report):
    if not report:
        return ""

    if report.get("valid"):
        inner_void_count = int(report.get("inner_void_count", 0) or 0)
        if inner_void_count <= 0:
            return translate("BIM_PlanEdit", "Space preflight: Valid space")
        if inner_void_count == 1:
            return translate("BIM_PlanEdit", "Space preflight: Valid space with 1 inner void")
        return translate(
            "BIM_PlanEdit", "Space preflight: Valid space with {count} inner voids"
        ).format(count=inner_void_count)

    code = report.get("code")
    status_map = {
        "empty": translate("BIM_PlanEdit", "Space preflight: Select room-bounding walls or faces"),
        "unusable_boundaries": translate(
            "BIM_PlanEdit", "Space preflight: No usable boundary faces"
        ),
        "no_height": translate("BIM_PlanEdit", "Space preflight: Boundaries have no height"),
        "no_intersection": translate(
            "BIM_PlanEdit", "Space preflight: Boundaries miss the plan cut"
        ),
        "open_loop": translate("BIM_PlanEdit", "Space preflight: Open loop"),
        "multiple_regions": translate("BIM_PlanEdit", "Space preflight: Multiple enclosed regions"),
        "nested_islands": translate(
            "BIM_PlanEdit", "Space preflight: Nested islands are not supported"
        ),
        "invalid_solid": translate(
            "BIM_PlanEdit", "Space preflight: Selection cannot become one space"
        ),
    }
    status = status_map.get(
        code,
        translate("BIM_PlanEdit", "Space preflight: Selection cannot become one space"),
    )
    details = [str(detail).strip() for detail in report.get("details", []) if str(detail).strip()]
    if details:
        return "{}\n{}".format(status, details[0])
    return status
