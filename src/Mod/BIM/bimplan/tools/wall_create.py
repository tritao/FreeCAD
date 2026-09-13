# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall creation tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
import Part

import ArchRepresentation

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.runtime.embedded_commands import _PlanEditWallHost
import ArchWallConstruction as wall_construction

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = wall_construction.MINIMUM_WALL_LENGTH


def _creation_preview_state(session):
    return session.creation_preview_state


def _wall_preview_representation(session, source, segments, width, align="Center"):
    """Build one renderer-neutral plan representation for proposed walls."""

    context = session.representation_context.context
    representation = ArchRepresentation.BIMRepresentation(source=source, context=context)
    for index, (start, end) in enumerate(segments, start=1):
        footprint = session.wall_edit.get_preview_footprint(
            [start, end],
            width=width,
            align=align,
        )
        if not footprint:
            continue
        points = tuple(FreeCAD.Vector(point) for point in footprint)
        if len(points) < 3:
            continue
        closed = (*points, points[0])
        try:
            face = Part.Face(Part.makePolygon(closed))
        except Part.OCCError:
            continue
        representation.add_geometry(
            "cut_geometry",
            face,
            "ProposedWallFootprint",
            subelement=f"Segment{index}",
        )
        representation.add_geometry(
            "projected_geometry",
            closed,
            "ProposedWallBoundary",
            subelement=f"Segment{index}",
        )
    return representation


class SemanticWallPreviewTracker:
    """Draft wall-tracker contract backed by the semantic preview renderer."""

    def __init__(self, session):
        self._session = session
        self._source = object()
        self._width = 0.1
        self._height = 1.0
        self._active = False

    def width(self, value=None):
        if value is not None:
            self._width = float(value)
        return self._width

    def height(self, value=None):
        if value is not None:
            self._height = float(value)
        return self._height

    def on(self):
        self._active = True

    def off(self):
        self._active = False
        self._session.contextual_rendering.clear_preview(self._source)

    def finalize(self):
        self.off()

    def update(self, line=None, normal=None):
        del normal
        if not self._active or not isinstance(line, (list, tuple)) or len(line) != 2:
            return
        start, end = (FreeCAD.Vector(point) for point in line)
        if end.sub(start).Length < _MIN_WALL_LENGTH:
            self._session.contextual_rendering.clear_preview(self._source)
            return
        representation = _wall_preview_representation(
            self._session,
            self._source,
            ((start, end),),
            self._width,
        )
        self._session.contextual_rendering.set_preview_representation(
            self._source,
            representation,
        )


class PlanWallCreateAPI:
    """Owned session surface for Plan Edit wall creation behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def activate_wall_tool(self):
        return activate_wall_tool(self.session)

    def activate_rect_wall_tool(self):
        return activate_rect_wall_tool(self.session)

    def get_wall_defaults(self):
        return get_wall_defaults(self.session)

    def has_active_rect_wall_tool(self):
        return has_active_rect_wall_tool(self.session)

    def clear_rect_wall_preview(self):
        return clear_rect_wall_preview(self.session)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def cancel_rect_wall_tool(self, refresh=True):
        return cancel_rect_wall_tool(self.session, refresh=refresh)

    def cancel_for_select(self):
        if not self.has_active_rect_wall_tool():
            return False
        self.cancel_rect_wall_tool()
        return True

    def get_rect_wall_corners(self, point):
        return get_rect_wall_corners(self.session, point)

    def update_rect_wall_preview(self, point, info):
        return update_rect_wall_preview(self.session, point, info)

    def create_rect_wall_run(self, corners):
        return create_rect_wall_run(self.session, corners)

    def handle_rect_wall_point(self, point=None, obj=None):
        return handle_rect_wall_point(self.session, point=point, obj=obj)


class RectWallTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active rectangular wall placement."""

    tool_id = plan_runtime_tools.PlanTool.RECT_WALL

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        return self.cancel()

    def cancel(self):
        self.session.wall_create.cancel_rect_wall_tool()
        return True


def activate_wall_tool(session):
    from bimcommands import BimWall

    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.clear_plan_relation_status()
    session.selection.state.set_selected_plan_target()
    session.overlays.walls.clear_selected_wall_overlay()
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.spaces.clear_selected_space_overlay()
    session.overlays.spaces.clear_secondary_selected_overlays()
    session.selection.sync.set_gui_selection([])
    session.embedded_tools.start(
        "Wall",
        BimWall.Arch_Wall(),
        host_class=_PlanEditWallHost,
    )


def activate_rect_wall_tool(session):
    preview_state = _creation_preview_state(session)
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.embedded_tools.cancel()
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.clear_plan_relation_status()
    session.selection.state.set_selected_plan_target()
    session.overlays.walls.clear_selected_wall_overlay()
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.spaces.clear_selected_space_overlay()
    session.overlays.spaces.clear_secondary_selected_overlays()
    session.wall_create.clear_rect_wall_preview()
    preview_state.rect_wall_start = None
    preview_state.rect_wall_params = get_wall_defaults(session)
    session.current_tool = "Rect Wall"
    session.snap.set_active_draft_command()
    FreeCADGui.Snapper.getPoint(
        callback=session.wall_create.handle_rect_wall_point,
        title=translate("BIM_PlanEdit", "First rectangle corner"),
    )
    session.task_panels.refresh_task_panel_status()


def get_wall_defaults(session):
    del session

    from draftutils import params

    return {
        "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
        "width": params.get_param_arch("WallWidth"),
        "height": params.get_param_arch("WallHeight"),
        "offset": params.get_param_arch("WallOffset"),
    }


def has_active_rect_wall_tool(session):
    return (
        _creation_preview_state(session).rect_wall_start is not None
        or session.current_tool == "Rect Wall"
    )


def clear_rect_wall_preview(session):
    preview_state = _creation_preview_state(session)
    source = preview_state.rect_wall_preview_source
    if source is not None:
        session.contextual_rendering.clear_preview(source)
    preview_state.rect_wall_preview_source = None


def discard_runtime_references(session):
    preview_state = _creation_preview_state(session)
    preview_state.rect_wall_start = None
    preview_state.rect_wall_params = None
    preview_state.rect_wall_preview_source = None


def cancel_rect_wall_tool(session, refresh=True):
    preview_state = _creation_preview_state(session)
    if not session.wall_create.has_active_rect_wall_tool():
        return False
    session.snap.stop_snapper()
    session.wall_create.clear_rect_wall_preview()
    preview_state.rect_wall_start = None
    preview_state.rect_wall_params = None
    session.snap.clear_active_draft_command()
    session.current_tool = "Select"
    if refresh:
        session.task_panels.refresh_task_panel_status()
    session.overlays.openings.sync_selected_opening_overlay()
    session.overlays.openings.sync_selected_opening_handles()
    session.overlays.spaces.sync_selected_space_overlay()
    session.overlays.providers.sync_selected_provider_overlay()
    session.overlays.providers.sync_selected_provider_handles()
    return True


def get_rect_wall_corners(session, point):
    start = _creation_preview_state(session).rect_wall_start
    if start is None or point is None:
        return None
    end = session.viewport.project_plan_point(point)
    if end is None:
        return None
    x1, y1 = start.x, start.y
    x2, y2 = end.x, end.y
    z = start.z
    if abs(x2 - x1) < _MIN_WALL_LENGTH or abs(y2 - y1) < _MIN_WALL_LENGTH:
        return None
    return [
        FreeCAD.Vector(x1, y1, z),
        FreeCAD.Vector(x2, y1, z),
        FreeCAD.Vector(x2, y2, z),
        FreeCAD.Vector(x1, y2, z),
    ]


def update_rect_wall_preview(session, point, info):
    preview_state = _creation_preview_state(session)
    del info
    corners = session.wall_create.get_rect_wall_corners(point)
    if not corners:
        return
    segments = list(zip(corners, corners[1:] + corners[:1]))
    source = preview_state.rect_wall_preview_source
    if source is None:
        source = object()
        preview_state.rect_wall_preview_source = source
    representation = _wall_preview_representation(
        session,
        source,
        segments,
        preview_state.rect_wall_params["width"],
        preview_state.rect_wall_params["align"],
    )
    session.contextual_rendering.set_preview_representation(source, representation)


def create_rect_wall_run(session, corners):
    preview_state = _creation_preview_state(session)
    params = preview_state.rect_wall_params
    spec = wall_construction.WallConstructionSpec(
        width=params["width"],
        height=params["height"],
        align=params["align"],
        offset=params["offset"],
    )
    return list(
        wall_construction.construct_wall_run(
            session.doc,
            corners,
            spec,
            transaction_name=translate(
                "BIM_PlanEdit", "Create Rectangular Wall Run"
            ),
            closed=True,
            on_created=session.visibility.register_plan_object,
        )
    )


def handle_rect_wall_point(session, point=None, obj=None):
    preview_state = _creation_preview_state(session)
    del obj
    if point is None:
        session.wall_create.cancel_rect_wall_tool()
        return

    point = session.viewport.project_plan_point(point)
    if preview_state.rect_wall_start is None:
        preview_state.rect_wall_start = point
        FreeCADGui.Snapper.getPoint(
            callback=session.wall_create.handle_rect_wall_point,
            movecallback=session.wall_create.update_rect_wall_preview,
            last=point,
            title=translate("BIM_PlanEdit", "Opposite rectangle corner"),
            mode="line",
        )
        return

    corners = session.wall_create.get_rect_wall_corners(point)
    if not corners:
        session.wall_create.cancel_rect_wall_tool()
        return

    try:
        walls = session.wall_create.create_rect_wall_run(corners)
    except Exception:
        session.wall_create.cancel_rect_wall_tool()
        FreeCAD.Console.PrintError(
            translate("BIM_PlanEdit", "Failed to create the rectangular wall run.\n")
        )
        return

    try:
        session.selection.sync.set_gui_selection(walls)
    except Exception:
        pass

    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.current_tool = "Select"
    session.selection.refresh.refresh_primary_selected_plan_target()
    session.task_panels.refresh_task_panel_status()
