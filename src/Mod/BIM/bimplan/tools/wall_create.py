# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall creation tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
import Part

import ArchRepresentation

from bimplan.runtime import tools as plan_runtime_tools
import ArchWallConstruction as wall_construction

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = wall_construction.MINIMUM_WALL_LENGTH


def _creation_preview_state(session):
    return session.creation_preview_state


def _wall_preview_representation(session, source, segments, width, align="Center"):
    """Build one renderer-neutral plan representation for proposed walls."""

    request = session.representation_request.request
    representation = ArchRepresentation.BIMRepresentation(source=source, request=request)
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
        self._session.contextual_rendering.set_preview_state(
            ArchRepresentation.preview_state_from_representation(representation)
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

    def get_wall_types(self):
        return get_wall_types(self.session)

    def get_active_wall_type(self):
        return get_active_wall_type(self.session)

    def set_active_wall_type(self, wall_type):
        return set_active_wall_type(self.session, wall_type)

    def get_selected_wall(self):
        return get_selected_wall(self.session)

    def assign_selected_wall_type(self, wall_type):
        return assign_selected_wall_type(self.session, wall_type)

    def create_wall_type(self, source=None):
        return create_wall_type(self.session, source=source)

    def reset_selected_wall_type_overrides(self):
        return reset_selected_wall_type_overrides(self.session)

    def update_wall_type(self, wall_type, **settings):
        return update_wall_type(self.session, wall_type, **settings)

    def has_active_rect_wall_tool(self):
        return has_active_rect_wall_tool(self.session)

    def has_active_wall_tool(self):
        return has_active_wall_tool(self.session)

    def clear_rect_wall_preview(self):
        return clear_rect_wall_preview(self.session)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def cancel_rect_wall_tool(self, refresh=True):
        return cancel_rect_wall_tool(self.session, refresh=refresh)

    def cancel_wall_tool(self, refresh=True):
        return cancel_wall_tool(self.session, refresh=refresh)

    def handle_wall_point(self, point=None, obj=None):
        return handle_wall_point(self.session, point=point, obj=obj)

    def update_wall_preview(self, point, info):
        return update_wall_preview(self.session, point, info)

    def cancel_for_select(self):
        if self.has_active_wall_tool():
            self.cancel_wall_tool()
            return True
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


class WallTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for native chained wall placement."""

    tool_id = plan_runtime_tools.PlanTool.WALL

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        return self.cancel()

    def cancel(self):
        self.session.wall_create.cancel_wall_tool()
        return True


def activate_wall_tool(session):
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.wall_create.cancel_wall_tool(refresh=False)
    session.hosted_openings.cancel_window_tool(refresh=False)
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
    preview_state = _creation_preview_state(session)
    preview_state.wall_start = None
    preview_state.wall_previous = None
    preview_state.wall_params = get_wall_defaults(session)
    session.current_tool = plan_runtime_tools.PlanTool.WALL
    session.snap.set_active_draft_command()
    _arm_wall_point_request(session, first=True)
    session.task_panels.refresh_task_panel_status()


def activate_rect_wall_tool(session):
    preview_state = _creation_preview_state(session)
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.hosted_openings.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.embedded_tools.cancel()
    session.wall_create.cancel_wall_tool(refresh=False)
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
        view=session.view,
        task_ui=False,
    )
    session.task_panels.refresh_task_panel_status()


def get_wall_defaults(session):
    from draftutils import params

    defaults = {
        "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
        "width": params.get_param_arch("WallWidth"),
        "height": params.get_param_arch("WallHeight"),
        "offset": params.get_param_arch("WallOffset"),
        "material": None,
        "wall_type": get_active_wall_type(session),
    }
    wall_type = defaults["wall_type"]
    if wall_type is not None:
        defaults.update(
            width=float(wall_type.Width.Value),
            height=float(wall_type.DefaultHeight.Value),
            align=str(wall_type.Align),
            material=getattr(wall_type, "Material", None),
        )
    return defaults


def get_wall_types(session):
    return tuple(
        obj
        for obj in (getattr(session.doc, "Objects", ()) or ())
        if getattr(getattr(obj, "Proxy", None), "Type", "") == "WallType"
    )


def get_active_wall_type(session):
    wall_type = _creation_preview_state(session).active_wall_type
    return wall_type if wall_type in get_wall_types(session) else None


def set_active_wall_type(session, wall_type):
    if wall_type is not None and wall_type not in get_wall_types(session):
        raise ValueError("Wall type does not belong to the active document")
    _creation_preview_state(session).active_wall_type = wall_type
    session.task_panels.refresh_task_panel_status(reason="selection")


def get_selected_wall(session):
    kind, obj = session.selection.state.get_selected_plan_target()
    return obj if kind == "wall" else None


def assign_selected_wall_type(session, wall_type):
    wall = get_selected_wall(session)
    if wall is None:
        set_active_wall_type(session, wall_type)
        return None
    import ArchWall

    try:
        with session.document_visuals.defer_document_visual_updates():
            session.doc.openTransaction(translate("BIM_PlanEdit", "Change Wall Type"))
            ArchWall.assign_wall_type(wall, wall_type, preserve_instance_values=False)
            session.doc.recompute()
            session.doc.commitTransaction()
    except Exception:
        session.doc.abortTransaction()
        raise
    _creation_preview_state(session).active_wall_type = wall_type
    session.contextual_rendering.refresh_object(wall)
    session.selection.activation.select_wall_for_plan_edit(wall)
    session.task_panels.refresh_task_panel_status(reason="selection")
    return wall


def create_wall_type(session, source=None):
    import Arch
    import ArchWall

    existing = get_wall_types(session)
    selected_wall = get_selected_wall(session)
    base_label = (
        translate("BIM_PlanEdit", "Copy of {name}").format(name=source.Label)
        if source is not None
        else translate("BIM_PlanEdit", "New Wall Type")
    )
    labels = {str(getattr(item, "Label", "")) for item in existing}
    label = base_label
    suffix = 2
    while label in labels:
        label = "{} {}".format(base_label, suffix)
        suffix += 1
    try:
        with session.document_visuals.defer_document_visual_updates():
            session.doc.openTransaction(translate("BIM_PlanEdit", "Create Wall Type"))
            wall_type = Arch.makeWallType(label)
            if source is not None:
                for prop in (
                    "Function",
                    "Width",
                    "DefaultHeight",
                    "Align",
                    "Material",
                    "PlanHatch",
                    "PlanHatchSpacing",
                    "PlanHatchAngle",
                ):
                    setattr(wall_type, prop, getattr(source, prop))
            if selected_wall is not None:
                ArchWall.assign_wall_type(
                    selected_wall,
                    wall_type,
                    preserve_instance_values=False,
                )
            session.doc.recompute()
            session.doc.commitTransaction()
    except Exception:
        session.doc.abortTransaction()
        raise
    _creation_preview_state(session).active_wall_type = wall_type
    if selected_wall is not None:
        session.contextual_rendering.refresh_object(selected_wall)
        session.selection.activation.select_wall_for_plan_edit(selected_wall)
    session.task_panels.refresh_task_panel_status(reason="selection")
    return wall_type


def reset_selected_wall_type_overrides(session):
    wall = get_selected_wall(session)
    if wall is None or getattr(wall, "WallType", None) is None:
        return False
    import ArchWall

    overrides = tuple(getattr(wall, "TypeOverrides", ()) or ())
    if not overrides:
        return False
    try:
        with session.document_visuals.defer_document_visual_updates():
            session.doc.openTransaction(
                translate("BIM_PlanEdit", "Reset Wall Type Overrides")
            )
            for prop in overrides:
                ArchWall.set_wall_type_override(wall, prop, False)
            session.doc.recompute()
            session.doc.commitTransaction()
    except Exception:
        session.doc.abortTransaction()
        raise
    session.contextual_rendering.refresh_object(wall)
    _creation_preview_state(session).active_wall_type = wall.WallType
    session.selection.activation.select_wall_for_plan_edit(wall)
    session.task_panels.refresh_task_panel_status(reason="selection")
    return True


def update_wall_type(
    session,
    wall_type,
    *,
    label,
    function,
    width,
    default_height,
    align,
    plan_hatch,
    hatch_spacing,
    hatch_angle,
):
    """Update one shared wall type and refresh all of its occurrences."""
    if wall_type not in get_wall_types(session):
        raise ValueError("Wall type does not belong to the active document")
    label = str(label or "").strip()
    if not label:
        raise ValueError("Wall type name must not be empty")
    if width <= 0 or default_height <= 0 or hatch_spacing <= 0:
        raise ValueError("Wall type dimensions and hatch spacing must be positive")

    selected_wall = get_selected_wall(session)
    occurrences = tuple(
        obj
        for obj in (getattr(wall_type, "InList", ()) or ())
        if getattr(obj, "WallType", None) is wall_type
    )
    try:
        with session.document_visuals.defer_document_visual_updates():
            session.doc.openTransaction(translate("BIM_PlanEdit", "Edit Wall Type"))
            wall_type.Label = label
            wall_type.Function = str(function)
            wall_type.Width = float(width)
            wall_type.DefaultHeight = float(default_height)
            wall_type.Align = str(align)
            wall_type.PlanHatch = str(plan_hatch)
            wall_type.PlanHatchSpacing = float(hatch_spacing)
            wall_type.PlanHatchAngle = float(hatch_angle)
            session.doc.recompute()
            session.doc.commitTransaction()
    except Exception:
        session.doc.abortTransaction()
        raise

    for occurrence in occurrences:
        session.contextual_rendering.refresh_object(occurrence)
    if selected_wall is not None:
        session.selection.activation.select_wall_for_plan_edit(selected_wall)
    session.task_panels.refresh_task_panel_status(reason="selection")
    return wall_type


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
    preview_state.wall_start = None
    preview_state.wall_params = None
    preview_state.wall_previous = None
    preview_state.wall_preview_source = None
    preview_state.rect_wall_start = None
    preview_state.rect_wall_params = None
    preview_state.rect_wall_preview_source = None


def has_active_wall_tool(session):
    state = _creation_preview_state(session)
    return state.wall_start is not None or session.current_tool == plan_runtime_tools.PlanTool.WALL


def _clear_wall_preview(session):
    state = _creation_preview_state(session)
    if state.wall_preview_source is not None:
        session.contextual_rendering.clear_preview(state.wall_preview_source)
    state.wall_preview_source = None


def cancel_wall_tool(session, refresh=True):
    state = _creation_preview_state(session)
    if not session.wall_create.has_active_wall_tool():
        return False
    session.snap.stop_snapper()
    _clear_wall_preview(session)
    state.wall_start = None
    state.wall_params = None
    state.wall_previous = None
    session.snap.clear_active_draft_command()
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def _aligned_wall_point(session, point):
    state = _creation_preview_state(session)
    point = session.viewport.project_plan_point(point)
    start = state.wall_start
    if point is None or start is None:
        return point
    try:
        from PySide import QtCore, QtGui

        if QtGui.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            return point
    except Exception:
        pass
    delta = point.sub(start)
    if abs(delta.x) >= abs(delta.y):
        return FreeCAD.Vector(point.x, start.y, start.z)
    return FreeCAD.Vector(start.x, point.y, start.z)


def _arm_wall_point_request(session, first=False):
    if (
        session.lifecycle_state.tearing_down
        or session.current_tool != plan_runtime_tools.PlanTool.WALL
    ):
        return False
    state = _creation_preview_state(session)
    kwargs = {
        "callback": session.wall_create.handle_wall_point,
        "title": translate(
            "BIM_PlanEdit", "First wall point" if first else "Next wall point"
        ),
        "view": session.view,
        "task_ui": False,
    }
    if not first:
        if state.wall_start is None:
            return False
        kwargs.update(
            movecallback=session.wall_create.update_wall_preview,
            last=state.wall_start,
            mode="line",
        )
    FreeCADGui.Snapper.getPoint(**kwargs)
    return True


def _defer_wall_point_request(session):
    """Arm the next point after the current Coin event has finished dispatching."""

    FreeCADGui.invokeLater(lambda: _arm_wall_point_request(session))


def update_wall_preview(session, point, info):
    del info
    state = _creation_preview_state(session)
    end = _aligned_wall_point(session, point)
    if end is None or end.sub(state.wall_start).Length < _MIN_WALL_LENGTH:
        _clear_wall_preview(session)
        return
    if state.wall_preview_source is None:
        state.wall_preview_source = object()
    representation = _wall_preview_representation(
        session,
        state.wall_preview_source,
        ((state.wall_start, end),),
        state.wall_params["width"],
        state.wall_params["align"],
    )
    session.contextual_rendering.set_preview_state(
        ArchRepresentation.preview_state_from_representation(representation)
    )


def _create_wall_segment(session, start, end):
    state = _creation_preview_state(session)
    params = state.wall_params
    spec = wall_construction.WallConstructionSpec(
        width=params["width"],
        height=params["height"],
        align=params["align"],
        offset=params["offset"],
        material=params.get("material"),
        wall_type=params.get("wall_type"),
    )

    def build_wall():
        return wall_construction.create_wall_segment(
            start,
            end,
            spec,
            on_created=session.visibility.register_plan_object,
        )

    return wall_construction.construct_wall(
        session.doc,
        build_wall,
        transaction_name=translate("BIM_PlanEdit", "Create Wall"),
    )


def handle_wall_point(session, point=None, obj=None):
    del obj
    state = _creation_preview_state(session)
    if point is None:
        session.wall_create.cancel_wall_tool()
        return
    if state.wall_start is None:
        point = session.viewport.project_plan_point(point)
        if point is None:
            return
        state.wall_start = point
    else:
        end = _aligned_wall_point(session, point)
        if end is None:
            return
        try:
            wall = _create_wall_segment(session, state.wall_start, end)
        except Exception as error:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create wall: {}\n").format(error)
            )
            session.wall_create.cancel_wall_tool()
            return
        _clear_wall_preview(session)
        state.wall_start = end
        state.wall_previous = wall
    _defer_wall_point_request(session)


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
    session.contextual_rendering.set_preview_state(
        ArchRepresentation.preview_state_from_representation(representation)
    )


def create_rect_wall_run(session, corners):
    preview_state = _creation_preview_state(session)
    params = preview_state.rect_wall_params
    spec = wall_construction.WallConstructionSpec(
        width=params["width"],
        height=params["height"],
        align=params["align"],
        offset=params["offset"],
        material=params.get("material"),
        wall_type=params.get("wall_type"),
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
            view=session.view,
            task_ui=False,
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
