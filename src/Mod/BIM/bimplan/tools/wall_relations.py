# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall relation and join tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.transactions import PlanEditTransaction
from bimplan.tools import select as plan_select_tool

translate = FreeCAD.Qt.translate


def _provider_point_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "point", providers)


_PLAN_JOIN_TYPES = ("Miter", "Butt", "Tee")


class JoinTool(plan_runtime_tools.PlanToolHandler):
    """Interactive wall join/unjoin tool."""

    tool_id = plan_runtime_tools.PlanTool.JOIN

    def on_mouse_move(self, mouse_pos, event_callback):
        del event_callback
        return plan_select_tool.sync_selectable_hover(self.session, mouse_pos)

    def on_left_mouse_down(self, mouse_pos, event_callback):
        session = self.session
        target_kind, target_wall = session.picking.pick(mouse_pos)
        source_wall = session.selection.state.get_selected_plan_target_object("wall")
        if (
            target_kind == "wall"
            and session.selection.targets.is_plan_selectable_wall(target_wall)
            and target_wall != source_wall
            and session.wall_relations.apply_plan_wall_join(source_wall, target_wall)
        ):
            session.input.claim_left_button_click(event_callback)
            return True
        return False

    def on_key(self, key, event_callback, coin):
        session = self.session
        if key == coin.SoKeyboardEvent.TAB:
            if session.wall_relations.cycle_plan_join_type():
                _set_key_event_handled(event_callback)
            return True
        if key in (
            getattr(coin.SoKeyboardEvent, "DELETE", None),
            getattr(coin.SoKeyboardEvent, "BACKSPACE", None),
        ):
            if session.wall_relations.unjoin_current_plan_wall_pair():
                _set_key_event_handled(event_callback)
            return True
        if key == coin.SoKeyboardEvent.ESCAPE:
            session.wall_relations.cancel_join_tool()
            return True
        return False


def _set_key_event_handled(event_callback):
    setter = getattr(event_callback, "setHandled", None)
    if callable(setter):
        setter()


class PlanWallRelationsAPI:
    """Owned session surface for Plan Edit wall relation and join reads."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_plan_join_type_label(self, join_type=None):
        return get_plan_join_type_label(self.session, join_type=join_type)

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

    def activate_join_tool(self):
        return activate_join_tool(self.session)

    def cancel_join_tool(self, refresh=True):
        return cancel_join_tool(self.session, refresh=refresh)

    def cancel_for_select(self):
        return self.cancel_join_tool()

    def get_plan_join_command(self):
        return get_plan_join_command(self.session)

    def get_plan_join_candidate_wall(self):
        return get_plan_join_candidate_wall(self.session)

    def get_plan_candidate_joint(self, target_wall=None):
        return get_plan_candidate_joint(self.session, target_wall=target_wall)

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

    def apply_plan_wall_join(self, source_wall, target_wall):
        return apply_plan_wall_join(self.session, source_wall, target_wall)

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

    def clear_plan_relation_status(self):
        return clear_plan_relation_status(self.session)

    def collect_wall_relation_warnings(self, wall):
        return collect_wall_relation_warnings(self.session, wall)

    def update_wall_relation_status(self, wall):
        return update_wall_relation_status(self.session, wall)

    def restore_selected_wall_relation_status(self):
        return restore_selected_wall_relation_status(self.session)


def activate_join_tool(session):
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    _provider_point_api(session).cancel_provider_point_tool(refresh=False)

    if session.embedded_tools.has_active():
        session.embedded_tools.cancel()
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    clear_plan_relation_status(session)
    session.overlays.walls.clear_wall_grips()
    session.overlays.walls.clear_selected_wall_overlay()
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    session.selection.hover.set_hovered_space(None)
    session.selection.hover.set_hovered_region(None)

    wall = session.selection.state.get_selected_plan_target_object("wall")
    if not session.selection.targets.is_plan_selectable_wall(wall):
        selection = []
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            selection = []
        if len(selection) == 1 and session.selection.targets.is_plan_selectable_wall(selection[0]):
            wall = selection[0]

    if not session.selection.targets.is_plan_selectable_wall(wall):
        FreeCAD.Console.PrintWarning(
            translate("BIM_PlanEdit", "Select a wall before using Join.\n")
        )
        return

    session.current_tool = "Join"
    session.selection.state.set_selected_plan_target("wall", wall)
    session.selection.sync.set_gui_selection_object(wall)
    session.overlays.spaces.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status()


def get_plan_join_type(session):
    return session.wall_relation_state.join_type


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
    join_type = normalize_plan_join_type(session, join_type or get_plan_join_type(session))
    return {
        "Miter": translate("BIM_PlanEdit", "Miter"),
        "Butt": translate("BIM_PlanEdit", "Butt"),
        "Tee": translate("BIM_PlanEdit", "Tee"),
    }[join_type]


def get_plan_join_type_phrase(session, join_type=None):
    join_type = normalize_plan_join_type(session, join_type or get_plan_join_type(session))
    return {
        "Miter": translate("BIM_PlanEdit", "miter"),
        "Butt": translate("BIM_PlanEdit", "butt"),
        "Tee": translate("BIM_PlanEdit", "tee"),
    }[join_type]


def get_plan_join_action_text(session, join_type=None):
    return translate("BIM_PlanEdit", "Click another wall to create a {joint_type} joint").format(
        joint_type=get_plan_join_type_phrase(session, join_type)
    )


def set_plan_join_type(session, join_type, refresh=True):
    join_type = normalize_plan_join_type(session, join_type)
    wall_relation_state = session.wall_relation_state
    if wall_relation_state.join_type == join_type:
        if refresh:
            session.task_panels.refresh_task_panel_status()
        return False
    wall_relation_state.join_type = join_type
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def cycle_plan_join_type(session):
    try:
        current_index = _PLAN_JOIN_TYPES.index(get_plan_join_type(session))
    except ValueError:
        current_index = 0
    next_join_type = _PLAN_JOIN_TYPES[(current_index + 1) % len(_PLAN_JOIN_TYPES)]
    set_plan_join_type(session, next_join_type)
    return True


def get_plan_join_command(session):
    from bimcommands.BimJoin import BIM_Join_Butt, BIM_Join_Miter, BIM_Join_Tee

    return {
        "Miter": BIM_Join_Miter,
        "Butt": BIM_Join_Butt,
        "Tee": BIM_Join_Tee,
    }.get(
        normalize_plan_join_type(session, get_plan_join_type(session)),
        BIM_Join_Miter,
    )()


def get_plan_join_candidate_wall(session):
    if session.current_tool != "Join":
        return None
    wall = session.hovered_wall
    if not session.selection.targets.is_plan_selectable_wall(
        wall
    ) or session.selection.state.is_selected_plan_target("wall", wall):
        return None
    return wall


def get_plan_candidate_joint(session, target_wall=None):
    import ArchWallJoin

    source_wall = session.selection.state.get_selected_plan_target_object("wall")
    target_wall = target_wall or get_plan_join_candidate_wall(session)
    if not session.selection.targets.is_plan_selectable_wall(source_wall):
        return None
    if not session.selection.targets.is_plan_selectable_wall(target_wall):
        return None
    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return None
    return ArchWallJoin.find_existing_joint(doc, source_wall, target_wall)


def get_plan_join_candidate_state(session):
    target_wall = get_plan_join_candidate_wall(session)
    if not target_wall:
        return None, None, ""

    joint = get_plan_candidate_joint(session, target_wall)
    if not joint:
        return (
            target_wall,
            None,
            translate("BIM_PlanEdit", "Candidate wall: {label}").format(label=target_wall.Label),
        )

    summary = translate("BIM_PlanEdit", "Existing joint with {label}: {joint_type}").format(
        label=target_wall.Label,
        joint_type=get_plan_join_type_label(session, getattr(joint, "JointType", "Miter")),
    )
    status = getattr(joint, "Status", "")
    if status not in ("", "OK"):
        summary = translate("BIM_PlanEdit", "{summary} ({status})").format(
            summary=summary,
            status=status,
        )
    return target_wall, joint, summary


def get_plan_join_mode_action_text(session, target_wall=None, joint=None):
    target_wall = target_wall or get_plan_join_candidate_wall(session)
    joint = joint or get_plan_candidate_joint(session, target_wall)
    if joint:
        current_type = normalize_plan_join_type(session, getattr(joint, "JointType", "Miter"))
        if current_type == get_plan_join_type(session):
            return translate(
                "BIM_PlanEdit",
                "Press Delete to unjoin this pair, or Tab to choose a different joint type",
            )
        return translate(
            "BIM_PlanEdit",
            "Click wall to change it to a {joint_type} joint",
        ).format(joint_type=get_plan_join_type_phrase(session))
    if target_wall:
        return get_plan_join_action_text(session)
    return translate(
        "BIM_PlanEdit",
        "Hover another wall, then click to create a {joint_type} joint",
    ).format(joint_type=get_plan_join_type_phrase(session))


def _refresh_join_mode_wall_context(session, source_wall):
    if not session.selection.targets.is_plan_selectable_wall(source_wall):
        return
    session.selection.state.set_selected_plan_target("wall", source_wall)
    session.selection.sync.set_gui_selection_object(source_wall)
    session.overlays.spaces.sync_secondary_selected_overlays()
    session.overlays.walls.sync_junction_node_overlays()
    session.overlays.walls.sync_hovered_wall_overlay()
    session.overlays.walls.sync_hovered_wall_opening_context_overlay()


def _warn_post_commit_recompute_failure(action_label, exc):
    message = str(exc or "").strip() or type(exc).__name__
    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Completed {action}, but follow-up recompute failed: {error}\n",
        ).format(action=action_label, error=message)
    )


def _commit_wall_relation_change(doc, action_label, callback):
    try:
        with PlanEditTransaction(doc, action_label):
            result = callback()
    except Exception:
        return False, None
    try:
        doc.recompute()
    except Exception as exc:
        _warn_post_commit_recompute_failure(action_label, exc)
    return True, result


def unjoin_plan_wall_pair(session, source_wall, target_wall):
    import ArchWallJoin

    if not session.selection.targets.is_plan_selectable_wall(source_wall):
        return False
    if not session.selection.targets.is_plan_selectable_wall(target_wall):
        return False

    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return False
    joint = ArchWallJoin.find_existing_joint(doc, source_wall, target_wall)
    if not joint:
        return False

    transaction_name = translate("BIM_PlanEdit", "Unjoin walls")
    success, _result = _commit_wall_relation_change(
        doc,
        transaction_name,
        lambda: doc.removeObject(joint.Name),
    )
    if not success:
        return False

    clear_plan_relation_status(session)
    _refresh_join_mode_wall_context(session, source_wall)
    session.task_panels.refresh_task_panel_status()
    return True


def unjoin_current_plan_wall_pair(session):
    source_wall = session.selection.state.get_selected_plan_target_object("wall")
    target_wall = get_plan_join_candidate_wall(session)
    if not unjoin_plan_wall_pair(session, source_wall, target_wall):
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
    import ArchWallJoin
    import ArchWallJunctionUtils

    if not session.selection.targets.is_plan_selectable_wall(source_wall):
        return None
    if not session.selection.targets.is_plan_selectable_wall(target_wall):
        return None

    candidate_walls = {
        getattr(source_wall, "Name", ""): source_wall,
        getattr(target_wall, "Name", ""): target_wall,
    }
    candidate_relations = []
    seen_relations = set()
    for wall in (source_wall, target_wall):
        for relation in ArchWallJoin.iter_wall_relations(wall):
            relation_name = getattr(relation, "Name", None)
            if not relation_name or relation_name in seen_relations:
                continue
            seen_relations.add(relation_name)
            candidate_relations.append(relation)
            for linked_wall in ArchWallJoin.get_relation_walls(relation):
                if session.selection.targets.is_plan_selectable_wall(linked_wall):
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
    if not wall_names:
        return None
    for relation in candidate_relations:
        if getattr(getattr(relation, "Proxy", None), "Type", None) != "WallJunction":
            continue
        relation_names = {
            getattr(wall, "Name", "") for wall in list(getattr(relation, "Walls", []) or []) if wall
        }
        if relation_names == wall_names:
            return relation
    return None


def apply_plan_wall_junction_promotion(session, doc, source_wall, target_wall):
    import Arch
    import ArchWallJoin

    promotion = find_plan_junction_promotion(session, source_wall, target_wall)
    if not promotion:
        return None

    walls, solution, candidate_relations = promotion
    wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
    junction = find_reusable_plan_junction(candidate_relations, walls)

    for relation in candidate_relations:
        if not ArchWallJoin.is_wall_joint(relation):
            continue
        relation_walls = {
            getattr(wall, "Name", "") for wall in ArchWallJoin.get_relation_walls(relation) if wall
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
    session.task_panel_state.relation_status_message = None


def get_plan_relation_status_message(session):
    return str(session.task_panel_state.relation_status_message or "").strip()


def restore_selected_wall_relation_status(session):
    lifecycle_state = getattr(session, "lifecycle_state", None)
    if lifecycle_state is not None and (
        getattr(lifecycle_state, "tearing_down", False)
        or getattr(lifecycle_state, "finishing", False)
    ):
        clear_plan_relation_status(session)
        return
    wall = session.selection.state.get_selected_plan_target_object("wall")
    if session.selection.targets.is_plan_selectable_wall(wall):
        update_wall_relation_status(session, wall)
        return
    clear_plan_relation_status(session)


def collect_wall_relation_warnings(session, wall):
    if not wall:
        return []
    import ArchWallJoin

    warnings = []
    seen = set()
    for relation in ArchWallJoin.iter_wall_relations(wall):
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

    session.task_panel_state.relation_status_message = summary
    FreeCAD.Console.PrintWarning(summary + "\n")
    for _relation, label, _status, detail in warnings:
        FreeCAD.Console.PrintWarning(f"  - {label}: {detail}\n")


def cancel_join_tool(session, refresh=True):
    if session.current_tool != "Join":
        return False
    selected_wall = session.selection.state.get_selected_plan_target_object("wall")
    session.current_tool = "Select"
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    if selected_wall:
        session.selection.activation.select_wall_for_plan_edit(selected_wall)
        return True
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def apply_plan_wall_join(session, source_wall, target_wall):
    if not session.selection.targets.is_plan_selectable_wall(source_wall):
        return False
    if not session.selection.targets.is_plan_selectable_wall(target_wall):
        return False
    if source_wall == target_wall:
        return False

    import Arch
    import ArchWallJoin

    join_command = session.wall_relations.get_plan_join_command()
    created = False
    doc = getattr(source_wall, "Document", None) or session.doc
    if doc is None:
        return False

    transaction_name = translate("BIM_PlanEdit", "Join walls")

    def _mutate():
        nonlocal created
        relation = apply_plan_wall_junction_promotion(
            session,
            doc,
            source_wall,
            target_wall,
        )
        if relation is None:
            relation = ArchWallJoin.find_existing_joint(doc, source_wall, target_wall)
            if not relation:
                relation = Arch.makeWallJoint(source_wall, target_wall, join_command.JointType)
                created = True
            if not relation:
                raise RuntimeError("Unable to create wall joint")
            if not join_command._configure_joint(relation, source_wall, target_wall):
                raise RuntimeError("Unable to configure wall joint")
        return relation

    success, relation = _commit_wall_relation_change(doc, transaction_name, _mutate)
    if not success:
        return False

    if getattr(getattr(relation, "Proxy", None), "Type", None) == "WallJoint":
        if created or getattr(relation, "Status", "OK") != "OK":
            join_command._report_joint_status(relation)
    elif getattr(relation, "Status", "OK") != "OK":
        message = str(getattr(relation, "StatusMessage", "") or getattr(relation, "Status", ""))
        if message:
            FreeCAD.Console.PrintWarning(message + "\n")
    session.current_tool = "Select"
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    session.selection.activation.select_wall_for_plan_edit(source_wall)
    session.selection.sync.set_gui_selection_object(source_wall)
    return True
