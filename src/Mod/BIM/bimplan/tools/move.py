# SPDX-License-Identifier: LGPL-2.1-or-later

"""Move tool activation for BIM Plan Edit."""

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import target_kinds as plan_target_kinds

_MOVE_TOOL_SELECTION_KINDS = (plan_target_kinds.PLAN_TARGET_WALL,)


class PlanMoveAPI:
    """Owned session surface for Plan Edit move tool behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def activate_move_tool(self):
        return activate_move_tool(self.session)


def _start_move_tool(session):
    from draftguitools import gui_move

    return session.lifecycle.start_embedded_tool(
        plan_runtime_tools.PlanTool.MOVE,
        gui_move.Move(),
    )


def activate_move_tool(session):
    from bimplan.runtime import lifecycle as plan_lifecycle

    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.clear_plan_relation_status()
    plan_lifecycle.clear_selection_visuals(
        session,
        kinds=_MOVE_TOOL_SELECTION_KINDS,
        include_wall_grips=True,
    )
    return _start_move_tool(session)
