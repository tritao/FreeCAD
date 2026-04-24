# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall relation and join tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan import selection as plan_selection

translate = FreeCAD.Qt.translate

_PLAN_JOIN_TYPES = ("Miter", "Butt", "Tee")


class PlanWallRelationsAPI:
    """Owned session surface for Plan Edit wall relation and join reads."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_plan_join_type_label(self, join_type=None):
        return get_plan_join_type_label(self.session, join_type)

    def get_plan_join_type(self):
        return get_plan_join_type(self.session)

    def get_plan_join_types(self):
        return get_plan_join_types(self.session)

    def normalize_plan_join_type(self, join_type):
        return normalize_plan_join_type(self.session, join_type)

    def get_plan_join_type_phrase(self, join_type=None):
        return get_plan_join_type_phrase(self.session, join_type)

    def get_plan_join_action_text(self, join_type=None):
        return get_plan_join_action_text(self.session, join_type)

    def set_plan_join_type(self, join_type, refresh=True):
        return set_plan_join_type(self.session, join_type, refresh=refresh)

    def cycle_plan_join_type(self):
        return cycle_plan_join_type(self.session)

    def get_plan_join_command(self):
        return get_plan_join_command(self.session)

    def get_plan_join_candidate_wall(self):
        return get_plan_join_candidate_wall(self.session)

    def get_plan_candidate_joint(self, target_wall=None):
        return get_plan_candidate_joint(self.session, target_wall)

    def get_plan_join_candidate_state(self):
        return get_plan_join_candidate_state(self.session)

    def get_plan_join_mode_action_text(self, target_wall=None, joint=None):
        return get_plan_join_mode_action_text(
            self.session,
            target_wall=target_wall,
            joint=joint,
        )

    def unjoin_plan_wall_pair(self, source_wall, target_wall):
        return unjoin_plan_wall_pair(self.session, source_wall, target_wall)

    def unjoin_current_plan_wall_pair(self):
        return unjoin_current_plan_wall_pair(self.session)

    def find_plan_junction_promotion(self, source_wall, target_wall):
        return find_plan_junction_promotion(self.session, source_wall, target_wall)

    def apply_plan_wall_junction_promotion(self, doc, source_wall, target_wall):
        return apply_plan_wall_junction_promotion(
            self.session,
            doc,
            source_wall,
            target_wall,
        )

    def get_plan_relation_status_message(self):
        return get_plan_relation_status_message(self.session)


def activate_join_tool(session):
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)

    if session.lifecycle.has_active_embedded_tool():
        session.lifecycle.cancel_embedded_tool()
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session._clear_plan_relation_status()
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session._set_hovered_opening(None)
    session._set_hovered_wall(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)

    wall = plan_selection.get_selected_plan_target_object(session, "wall")
    if not session.selection.is_plan_selectable_wall(wall):
        selection = []
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            selection = []
        if len(selection) == 1 and session.selection.is_plan_selectable_wall(selection[0]):
            wall = selection[0]

    if not session.selection.is_plan_selectable_wall(wall):
        FreeCAD.Console.PrintWarning(
            translate("BIM_PlanEdit", "Select a wall before using Join.\n")
        )
        return

    session.current_tool = "Join"
    session._set_selected_plan_target("wall", wall)
    session._restore_gui_selection(wall)
    session.overlays.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status()


def get_plan_join_type(session):
    return session._plan_join_type


def get_plan_join_types(session):
    del session
    return _PLAN_JOIN_TYPES


def normalize_plan_join_type(session, join_type):
    del session
    if join_type in _PLAN_JOIN_TYPES:
        return join_type
    try:
        join_type = str(join_type)
    except Exception:
        return "Miter"
    if join_type in _PLAN_JOIN_TYPES:
        return join_type
    return "Miter"


def get_plan_join_type_label(session, join_type=None):
    join_type = session.wall_relations.normalize_plan_join_type(
        join_type or session._plan_join_type
    )
    return {
        "Miter": translate("BIM_PlanEdit", "Miter"),
        "Butt": translate("BIM_PlanEdit", "Butt"),
        "Tee": translate("BIM_PlanEdit", "Tee"),
    }[join_type]


def get_plan_join_type_phrase(session, join_type=None):
    join_type = session.wall_relations.normalize_plan_join_type(
        join_type or session._plan_join_type
    )
    return {
        "Miter": translate("BIM_PlanEdit", "miter"),
        "Butt": translate("BIM_PlanEdit", "butt"),
        "Tee": translate("BIM_PlanEdit", "tee"),
    }[join_type]


def get_plan_join_action_text(session, join_type=None):
    return translate("BIM_PlanEdit", "Click another wall to create a {joint_type} joint").format(
        joint_type=session.wall_relations.get_plan_join_type_phrase(join_type)
    )


def set_plan_join_type(session, join_type, refresh=True):
    join_type = session.wall_relations.normalize_plan_join_type(join_type)
    if session._plan_join_type == join_type:
        if refresh:
            session.task_panels.refresh_task_panel_status()
        return False
    session._plan_join_type = join_type
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def cycle_plan_join_type(session):
    try:
        current_index = _PLAN_JOIN_TYPES.index(session._plan_join_type)
    except ValueError:
        current_index = 0
    next_join_type = _PLAN_JOIN_TYPES[(current_index + 1) % len(_PLAN_JOIN_TYPES)]
    session.wall_relations.set_plan_join_type(next_join_type)
    return True


def get_plan_join_command(session):
    from bimcommands.BimJoin import BIM_Join_Butt, BIM_Join_Miter, BIM_Join_Tee

    return {
        "Miter": BIM_Join_Miter,
        "Butt": BIM_Join_Butt,
        "Tee": BIM_Join_Tee,
    }.get(
        session.wall_relations.normalize_plan_join_type(session._plan_join_type),
        BIM_Join_Miter,
    )()


def get_plan_join_candidate_wall(session):
    if session.current_tool != "Join":
        return None
    wall = session.hovered_wall
    if not session.selection.is_plan_selectable_wall(
        wall
    ) or session.selection.is_selected_plan_target("wall", wall):
        return None
    return wall


def get_plan_candidate_joint(session, target_wall=None):
    import ArchWallJoinUtils

    source_wall = plan_selection.get_selected_plan_target_object(session, "wall")
    target_wall = target_wall or session.wall_relations.get_plan_join_candidate_wall()
    if not session.selection.is_plan_selectable_wall(source_wall):
        return None
    if not session.selection.is_plan_selectable_wall(target_wall):
        return None
    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return None
    return ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)


def get_plan_join_candidate_state(session):
    target_wall = session.wall_relations.get_plan_join_candidate_wall()
    if not target_wall:
        return None, None, ""

    joint = session.wall_relations.get_plan_candidate_joint(target_wall)
    if not joint:
        return (
            target_wall,
            None,
            translate("BIM_PlanEdit", "Candidate wall: {label}").format(label=target_wall.Label),
        )

    summary = translate("BIM_PlanEdit", "Existing joint with {label}: {joint_type}").format(
        label=target_wall.Label,
        joint_type=session.wall_relations.get_plan_join_type_label(
            getattr(joint, "JointType", "Miter")
        ),
    )
    status = getattr(joint, "Status", "")
    if status not in ("", "OK"):
        summary = translate("BIM_PlanEdit", "{summary} ({status})").format(
            summary=summary,
            status=status,
        )
    return target_wall, joint, summary


def get_plan_join_mode_action_text(session, target_wall=None, joint=None):
    target_wall = target_wall or session.wall_relations.get_plan_join_candidate_wall()
    joint = joint or session.wall_relations.get_plan_candidate_joint(target_wall)
    if joint:
        current_type = session.wall_relations.normalize_plan_join_type(
            getattr(joint, "JointType", "Miter")
        )
        if current_type == session._plan_join_type:
            return translate(
                "BIM_PlanEdit",
                "Press Delete to unjoin this pair, or Tab to choose a different joint type",
            )
        return translate(
            "BIM_PlanEdit",
            "Click wall to change it to a {joint_type} joint",
        ).format(joint_type=session.wall_relations.get_plan_join_type_phrase())
    if target_wall:
        return session.wall_relations.get_plan_join_action_text()
    return translate(
        "BIM_PlanEdit",
        "Hover another wall, then click to create a {joint_type} joint",
    ).format(joint_type=session.wall_relations.get_plan_join_type_phrase())


def unjoin_plan_wall_pair(session, source_wall, target_wall):
    import ArchWallJoinUtils

    if not session.selection.is_plan_selectable_wall(source_wall):
        return False
    if not session.selection.is_plan_selectable_wall(target_wall):
        return False

    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return False
    joint = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
    if not joint:
        return False

    doc.openTransaction(translate("BIM_PlanEdit", "Unjoin walls"))
    try:
        doc.removeObject(joint.Name)
        doc.commitTransaction()
        doc.recompute()
    except Exception:
        try:
            doc.abortTransaction()
        except Exception:
            pass
        return False

    session._clear_plan_relation_status()
    session.task_panels.refresh_task_panel_status()
    return True


def unjoin_current_plan_wall_pair(session):
    source_wall = plan_selection.get_selected_plan_target_object(session, "wall")
    target_wall = session.wall_relations.get_plan_join_candidate_wall()
    if not session.wall_relations.unjoin_plan_wall_pair(source_wall, target_wall):
        FreeCAD.Console.PrintWarning(
            translate("BIM_PlanEdit", "Hover a joined wall pair before using Unjoin.\n")
        )
        return False
    return True


def iter_unique_wall_sets(source_wall, target_wall, extra_walls):
    import itertools

    base = [source_wall, target_wall]
    extras = sorted(
        [wall for wall in extra_walls if wall not in base],
        key=lambda wall: getattr(wall, "Name", ""),
    )
    seen = set()
    for size in range(len(extras), 0, -1):
        for combo in itertools.combinations(extras, size):
            walls = base + list(combo)
            signature = tuple(sorted(getattr(wall, "Name", "") for wall in walls if wall))
            if signature in seen:
                continue
            seen.add(signature)
            yield walls


def find_plan_junction_promotion(session, source_wall, target_wall):
    import ArchWallJoinUtils
    import ArchWallJunctionUtils

    if not session.selection.is_plan_selectable_wall(source_wall):
        return None
    if not session.selection.is_plan_selectable_wall(target_wall):
        return None

    candidate_walls = {
        getattr(source_wall, "Name", ""): source_wall,
        getattr(target_wall, "Name", ""): target_wall,
    }
    candidate_relations = []
    seen_relations = set()
    for wall in (source_wall, target_wall):
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            relation_name = getattr(relation, "Name", None)
            if not relation_name or relation_name in seen_relations:
                continue
            seen_relations.add(relation_name)
            candidate_relations.append(relation)
            for linked_wall in ArchWallJoinUtils.get_relation_walls(relation):
                if session.selection.is_plan_selectable_wall(linked_wall):
                    candidate_walls[getattr(linked_wall, "Name", "")] = linked_wall

    if len(candidate_walls) < 3:
        return None

    extra_walls = [
        wall
        for name, wall in candidate_walls.items()
        if wall not in (source_wall, target_wall) and name
    ]
    for walls in iter_unique_wall_sets(source_wall, target_wall, extra_walls):
        solution = ArchWallJunctionUtils.solve_wall_junction_inputs(walls)
        if solution.is_ok():
            return walls, solution, candidate_relations
    return None


def find_reusable_plan_junction(candidate_relations, walls):
    wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
    best_relation = None
    best_overlap = 0
    for relation in candidate_relations:
        if getattr(getattr(relation, "Proxy", None), "Type", None) != "WallJunction":
            continue
        relation_names = {
            getattr(wall, "Name", "") for wall in list(getattr(relation, "Walls", []) or []) if wall
        }
        overlap = len(wall_names.intersection(relation_names))
        if overlap > best_overlap:
            best_relation = relation
            best_overlap = overlap
    return best_relation if best_overlap >= 2 else None


def apply_plan_wall_junction_promotion(session, doc, source_wall, target_wall):
    import Arch
    import ArchWallJoinUtils

    promotion = session.wall_relations.find_plan_junction_promotion(source_wall, target_wall)
    if not promotion:
        return None

    walls, solution, candidate_relations = promotion
    wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
    junction = find_reusable_plan_junction(candidate_relations, walls)

    for relation in candidate_relations:
        if not ArchWallJoinUtils.is_wall_joint(relation):
            continue
        relation_walls = {
            getattr(wall, "Name", "")
            for wall in ArchWallJoinUtils.get_relation_walls(relation)
            if wall
        }
        if relation_walls and relation_walls.issubset(wall_names):
            doc.removeObject(relation.Name)

    if junction:
        junction.Walls = list(walls)
        junction.CarrierMode = "Explicit"
        junction.CarrierWall = solution.carrier_wall
        junction.Enabled = True
        return junction

    return Arch.makeWallJunction(list(walls), carrier_wall=solution.carrier_wall)


def clear_plan_relation_status(session):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        state.relation_status_message = None
        return
    session._plan_relation_status_message = None


def get_plan_relation_status_message(session):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        return str(getattr(state, "relation_status_message", "") or "").strip()
    return str(getattr(session, "_plan_relation_status_message", "") or "").strip()


def collect_wall_relation_warnings(session, wall):
    if not wall:
        return []
    import ArchWallJoinUtils

    warnings = []
    seen = set()
    for relation in ArchWallJoinUtils.iter_wall_relations(wall):
        if not relation or relation.Name in seen or not getattr(relation, "Enabled", True):
            continue
        seen.add(relation.Name)
        status = getattr(relation, "Status", "")
        if status in ("", "OK", "Disabled"):
            continue
        label = getattr(relation, "Label", getattr(relation, "Name", ""))
        detail = str(getattr(relation, "StatusMessage", "") or status).strip()
        warnings.append((relation, label, status, detail))
    return warnings


def update_wall_relation_status(session, wall):
    warnings = collect_wall_relation_warnings(session, wall)
    if not warnings:
        clear_plan_relation_status(session)
        return

    if len(warnings) == 1:
        _relation, label, status, _detail = warnings[0]
        summary = translate("BIM_PlanEdit", "Relation warning: {label} ({status})").format(
            label=label,
            status=status,
        )
    else:
        summary = translate(
            "BIM_PlanEdit", "Relation warnings: {count} relations need attention"
        ).format(count=len(warnings))

    state = getattr(session, "task_panel_state", None)
    if state is not None:
        state.relation_status_message = summary
    else:
        session._plan_relation_status_message = summary
    FreeCAD.Console.PrintWarning(summary + "\n")
    for _relation, label, _status, detail in warnings:
        FreeCAD.Console.PrintWarning(f"  - {label}: {detail}\n")


def cancel_join_tool(session, refresh=True):
    if session.current_tool != "Join":
        return False
    selected_wall = plan_selection.get_selected_plan_target_object(session, "wall")
    session.current_tool = "Select"
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    if selected_wall:
        session.selection.select_wall_for_plan_edit(selected_wall)
        return True
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def apply_plan_wall_join(session, source_wall, target_wall):
    if not session.selection.is_plan_selectable_wall(source_wall):
        return False
    if not session.selection.is_plan_selectable_wall(target_wall):
        return False
    if source_wall == target_wall:
        return False

    import Arch
    import ArchWallJoinUtils

    join_command = session._get_plan_join_command()
    created = False
    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return False

    doc.openTransaction(translate("BIM_PlanEdit", "Join walls"))
    try:
        relation = session.wall_relations.apply_plan_wall_junction_promotion(
            doc,
            source_wall,
            target_wall,
        )
        if relation is None:
            relation = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
            if not relation:
                relation = Arch.makeWallJoint(source_wall, target_wall, join_command.JointType)
                created = True
            if not relation:
                raise RuntimeError("Unable to create wall joint")
            if not join_command._configure_joint(relation, source_wall, target_wall):
                raise RuntimeError("Unable to configure wall joint")
        doc.commitTransaction()
        doc.recompute()
    except Exception:
        try:
            doc.abortTransaction()
        except Exception:
            pass
        return False

    if getattr(getattr(relation, "Proxy", None), "Type", None) == "WallJoint":
        if created or getattr(relation, "Status", "OK") != "OK":
            join_command._report_joint_status(relation)
    elif getattr(relation, "Status", "OK") != "OK":
        message = str(getattr(relation, "StatusMessage", "") or getattr(relation, "Status", ""))
        if message:
            FreeCAD.Console.PrintWarning(message + "\n")
    session.current_tool = "Select"
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session.selection.select_wall_for_plan_edit(source_wall)
    session._restore_gui_selection(source_wall)
    return True
