# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary and creation-request helpers for BIM Plan Edit."""

from dataclasses import dataclass

import FreeCAD

from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate

_SPACE_SELECTION_NONE = "none"
_SPACE_SELECTION_WALL_BOUNDARIES = "wall_boundaries"
_SPACE_SELECTION_SEEDED_REGION = "seeded_region"
_SPACE_SELECTION_SINGLE_SPACE = "single_space"


@dataclass(frozen=True)
class SpaceSelectionShape:
    targets: tuple = ()
    mode: str = _SPACE_SELECTION_NONE
    region_seed_space: object = None
    wall_targets: tuple = ()

    @property
    def should_run_preflight(self):
        if len(self.targets) <= 1:
            return False
        return self.mode in (
            _SPACE_SELECTION_WALL_BOUNDARIES,
            _SPACE_SELECTION_SEEDED_REGION,
        )


@dataclass(frozen=True)
class SpaceCreationRequest:
    targets: tuple = ()
    mode: str = _SPACE_SELECTION_NONE
    label: object = None
    region_seed_space: object = None
    wall_targets: tuple = ()
    boundaries: tuple = ()

    def to_dict(self):
        return {
            "targets": list(self.targets),
            "label": self.label,
            "region_seed_space": self.region_seed_space,
            "boundaries": list(self.boundaries),
        }


def get_space_reference_point(session, space):
    if not session.selection.is_plan_space_object(space):
        return None
    return _get_projected_space_shape_center(session, space) or _get_projected_space_base_point(
        session,
        space,
    )


def _get_projected_space_shape_center(session, space):
    shape = getattr(space, "Shape", None)
    if not (shape and hasattr(shape, "CenterOfMass")):
        return None
    try:
        return session.viewport.project_plan_point(shape.CenterOfMass)
    except Exception:
        return None


def _get_projected_space_base_point(session, space):
    placement = getattr(space, "Placement", None)
    if placement is None:
        return None
    try:
        return session.viewport.project_plan_point(placement.Base)
    except Exception:
        return None


def get_space_boundary_reference_point(session, selection_ex, fallback_space=None):
    points = _collect_space_boundary_selection_points(selection_ex, fallback_space=fallback_space)
    if points:
        return _average_freecad_vectors(points)
    return session.spaces.get_space_reference_point(fallback_space)


def _collect_space_boundary_selection_points(selection_ex, *, fallback_space=None):
    points = []
    for selection in selection_ex or []:
        points.extend(
            _get_space_boundary_selection_points(selection, fallback_space=fallback_space)
        )
    return points


def _get_space_boundary_selection_points(selection, *, fallback_space=None):
    obj = getattr(selection, "Object", None)
    if not obj or obj == fallback_space:
        return []
    subobject_points = _get_space_boundary_subobject_centers(selection)
    if subobject_points:
        return subobject_points
    object_center = _get_space_boundary_object_center(obj)
    if object_center is None:
        return []
    return [object_center]


def _get_space_boundary_subobject_centers(selection):
    points = []
    for subobject in list(getattr(selection, "SubObjects", []) or []):
        center = getattr(subobject, "CenterOfMass", None)
        if center is None:
            continue
        try:
            points.append(FreeCAD.Vector(center.x, center.y, center.z))
        except Exception:
            continue
    return points


def _get_space_boundary_object_center(obj):
    shape = getattr(obj, "Shape", None)
    bound_box = getattr(shape, "BoundBox", None)
    center = getattr(bound_box, "Center", None) if bound_box is not None else None
    if center is None:
        return None
    try:
        return FreeCAD.Vector(center.x, center.y, center.z)
    except Exception:
        return None


def _average_freecad_vectors(points):
    total = FreeCAD.Vector()
    for point in points:
        total = total.add(point)
    return total.multiply(1.0 / float(len(points)))


def get_space_boundary_entries(session, space):
    if not session.selection.is_plan_space_object(space):
        return []
    import ArchSpace

    return ArchSpace.normalizeBoundaryLinks(
        _iter_normalized_space_boundary_entries(getattr(space, "Boundaries", []) or ())
    )


def _iter_normalized_space_boundary_entries(boundaries):
    import ArchSpace

    entries = []
    for boundary in boundaries:
        try:
            obj = boundary[0]
            subnames = boundary[1]
        except Exception:
            continue
        entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
    return entries


def space_boundary_key(boundary):
    import ArchSpace

    obj, subnames = boundary
    return (
        getattr(obj, "Name", None),
        tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
    )


def get_selected_space_boundary_links(session, fallback_space=None):
    import ArchSpace

    selection_ex = session.selection.get_gui_selection_ex()
    reference_point = _get_selected_space_boundary_reference_point(
        session,
        selection_ex,
        fallback_space=fallback_space,
    )
    entries = _get_selected_space_boundary_link_entries(session, selection_ex)
    return ArchSpace.resolveBoundaryLinks(
        entries,
        reference_point=reference_point,
        exclude_objects=(fallback_space,) if fallback_space is not None else None,
    )


def _get_selected_space_boundary_reference_point(session, selection_ex, *, fallback_space=None):
    if fallback_space is not None:
        return session.spaces.get_space_reference_point(fallback_space)
    return session.spaces.get_space_boundary_reference_point(selection_ex)


def _get_selected_space_boundary_link_entries(session, selection_ex):
    entries = []
    for selection in selection_ex:
        obj = session.visibility.get_plan_semantic_object(getattr(selection, "Object", None))
        if not obj:
            continue
        entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
    return entries


def _get_selected_space_boundary_links(session, fallback_space=None):
    spaces_api = getattr(session, "spaces", None)
    if spaces_api is not None:
        return spaces_api.get_selected_space_boundary_links(fallback_space=fallback_space)
    return session.spaces.get_selected_space_boundary_links(fallback_space=fallback_space)


def _get_space_selection_targets(session, targets=None):
    return tuple(
        targets if targets is not None else plan_selection.get_selected_plan_targets(session)
    )


def _build_wall_boundary_space_creation_request(session, selection_shape):
    return SpaceCreationRequest(
        targets=selection_shape.targets,
        mode=selection_shape.mode,
        wall_targets=selection_shape.wall_targets,
        boundaries=tuple(_get_selected_space_boundary_links(session)),
    )


def _get_seed_space_boundary_links(session, selection_shape):
    return tuple(
        _get_selected_space_boundary_links(
            session,
            fallback_space=selection_shape.region_seed_space,
        )
    )


def _build_seeded_region_space_creation_request(session, selection_shape):
    boundaries = _get_seed_space_boundary_links(session, selection_shape)
    if selection_shape.mode == _SPACE_SELECTION_SINGLE_SPACE and not boundaries:
        return None
    region_seed_space = selection_shape.region_seed_space
    return SpaceCreationRequest(
        targets=selection_shape.targets,
        mode=_SPACE_SELECTION_SEEDED_REGION,
        label=getattr(region_seed_space, "Label", None),
        region_seed_space=region_seed_space,
        wall_targets=selection_shape.wall_targets,
        boundaries=boundaries,
    )


def _resolve_space_creation_request(session, targets=None):
    targets = _get_space_selection_targets(session, targets=targets)
    if not targets:
        return None

    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_WALL_BOUNDARIES:
        return _build_wall_boundary_space_creation_request(session, selection_shape)

    if selection_shape.mode not in (
        _SPACE_SELECTION_SEEDED_REGION,
        _SPACE_SELECTION_SINGLE_SPACE,
    ):
        return None
    return _build_seeded_region_space_creation_request(session, selection_shape)


def get_space_region_seed_targets(session, targets=None):
    targets = _get_space_selection_targets(session, targets=targets)
    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_SEEDED_REGION:
        return (selection_shape.region_seed_space, list(selection_shape.wall_targets))
    if selection_shape.mode != _SPACE_SELECTION_SINGLE_SPACE:
        return (None, [])
    boundary_links = _get_seed_space_boundary_links(session, selection_shape)
    if boundary_links:
        return (selection_shape.region_seed_space, [])
    return (None, [])


def get_selected_space_region_seed(session, targets=None):
    region_seed_space, _wall_targets = get_space_region_seed_targets(session, targets)
    return region_seed_space


def get_space_creation_request(session, targets=None):
    request = _resolve_space_creation_request(session, targets=targets)
    return request.to_dict() if request else None


def should_run_space_preflight_for_targets(targets):
    return _resolve_space_selection_shape(targets).should_run_preflight


def get_space_preflight_report(session, targets=None):
    if session.current_tool != "Select":
        return None

    targets = list(
        targets if targets is not None else plan_selection.get_selected_plan_targets(session)
    )
    if not should_run_space_preflight_for_targets(targets):
        return None

    request = _resolve_space_creation_request(session, targets=targets)
    if not request:
        return None

    import ArchSpace

    return ArchSpace.analyzeBoundaryLinks(
        request.boundaries,
        label=request.label,
        seed_space=request.region_seed_space,
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


def _resolve_space_selection_shape(targets):
    targets = tuple(targets or ())
    if not targets:
        return SpaceSelectionShape()

    wall_targets = tuple(
        (target_kind, target_obj)
        for target_kind, target_obj in targets
        if target_kind == plan_target_kinds.PLAN_TARGET_WALL
    )
    if len(wall_targets) == len(targets):
        return SpaceSelectionShape(
            targets=targets,
            mode=_SPACE_SELECTION_WALL_BOUNDARIES,
            wall_targets=wall_targets,
        )

    space_targets = [
        target_obj
        for target_kind, target_obj in targets
        if target_kind == plan_target_kinds.PLAN_TARGET_SPACE
    ]
    if len(space_targets) != 1:
        return SpaceSelectionShape(targets=targets)

    region_seed_space = space_targets[0]
    if len(targets) == 1:
        return SpaceSelectionShape(
            targets=targets,
            mode=_SPACE_SELECTION_SINGLE_SPACE,
            region_seed_space=region_seed_space,
        )

    if len(wall_targets) != len(targets) - 1:
        return SpaceSelectionShape(targets=targets)

    return SpaceSelectionShape(
        targets=targets,
        mode=_SPACE_SELECTION_SEEDED_REGION,
        region_seed_space=region_seed_space,
        wall_targets=wall_targets,
    )
