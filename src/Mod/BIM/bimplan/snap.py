# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft snap profile helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimviews.grid_settings import get_grid_settings


def _get_snapper():
    return getattr(FreeCADGui, "Snapper", None)


def _get_snapper_method(method_name):
    snapper = _get_snapper()
    if not snapper:
        return None
    method = getattr(snapper, method_name, None)
    return method if callable(method) else None


def _call_for_view(method, *args, view=None):
    """Call a view-aware Snapper method with legacy fallback support."""

    if view is None:
        return method(*args)
    try:
        return method(*args, view=view)
    except TypeError:
        return method(*args)


def _configure_plan_interaction_plane(session, plane):
    """Set the Plan Edit plane on the session's view-local Snapper context."""

    snapper = _get_snapper()
    configure = getattr(snapper, "configure_view", None) if snapper else None
    context_for = getattr(snapper, "context_for", None) if snapper else None
    if not callable(configure) or not callable(context_for):
        return False, None
    view = getattr(session, "view", None)
    try:
        context = context_for(view)
        previous = getattr(context, "interaction_plane", None)
        configure(view, interaction_plane=plane)
    except Exception:
        return False, None
    return True, previous


def _restore_plan_interaction_plane(session, previous):
    snapper = _get_snapper()
    configure = getattr(snapper, "configure_view", None) if snapper else None
    if not callable(configure):
        return None
    try:
        return configure(getattr(session, "view", None), interaction_plane=previous)
    except Exception:
        return None


def apply_plan_snap_profile(snap_modes, view=None):
    push_snap_modes = _get_snapper_method("push_snap_modes")
    if push_snap_modes is None:
        return
    try:
        _call_for_view(push_snap_modes, snap_modes, view=view)
    except Exception:
        pass


def restore_snap_profile(view=None):
    pop_snap_modes = _get_snapper_method("pop_snap_modes")
    if pop_snap_modes is None:
        return
    try:
        _call_for_view(pop_snap_modes, view=view)
    except Exception:
        pass


def _build_plan_grid(session):
    """Build a lattice in the active Plan Edit reference frame."""

    get_plane = getattr(getattr(session, "viewport", None), "get_interaction_plane", None)
    if not callable(get_plane):
        return None
    try:
        plane = get_plane()
    except Exception:
        return None
    if plane is None:
        return None
    try:
        from draftutils.grid import GridLattice

        settings = get_grid_settings()
        return GridLattice(
            getattr(plane, "position", FreeCAD.Vector()),
            getattr(plane, "u", FreeCAD.Vector(1, 0, 0)),
            getattr(plane, "v", FreeCAD.Vector(0, 1, 0)),
            spacing=settings.spacing,
            major_every=settings.major_every,
        )
    except Exception:
        return None


def apply_plan_grid(session):
    """Install a temporary Plan Edit lattice on Draft's Snapper."""

    push_interaction_grid = _get_snapper_method("push_interaction_grid")
    if push_interaction_grid is None:
        return None
    grid = _build_plan_grid(session)
    if grid is None:
        return None
    try:
        _call_for_view(push_interaction_grid, grid, view=getattr(session, "view", None))
    except Exception:
        return None
    return grid


def restore_plan_grid(grid=None, view=None):
    """Restore the previous Draft interaction grid during Plan Edit teardown."""

    pop_interaction_grid = _get_snapper_method("pop_interaction_grid")
    if pop_interaction_grid is None:
        return None
    try:
        return _call_for_view(pop_interaction_grid, grid, view=view)
    except Exception:
        return None


def set_active_draft_command(command):
    FreeCAD.activeDraftCommand = command


def clear_active_draft_command():
    FreeCAD.activeDraftCommand = None


def stop_snapper():
    snapper = _get_snapper()
    if not snapper:
        return
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    _set_toolbar_point_focus_suppressed(toolbar, False)
    try:
        snapper.getPoint()
        snapper.off()
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def set_point_focus_suppressed(suppressed):
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    if not toolbar:
        return
    _set_toolbar_point_focus_suppressed(toolbar, bool(suppressed))


def _set_toolbar_point_focus_suppressed(toolbar, suppressed):
    if toolbar is None:
        return
    set_focus_suppressed = getattr(toolbar, "setPointFocusSuppressed", None)
    if callable(set_focus_suppressed):
        try:
            set_focus_suppressed(bool(suppressed))
        except (AttributeError, RuntimeError, TypeError):
            pass
        return
    if getattr(toolbar, "suppress_point_focus", None) is not None:
        try:
            toolbar.suppress_point_focus = bool(suppressed)
        except (AttributeError, RuntimeError, TypeError):
            pass


class PlanSnapAPI:
    """Owned session surface for Plan Edit snap-profile behavior."""

    __slots__ = (
        "_session",
        "_plan_snap_modes",
        "_semantic_provider",
        "_semantic_provider_active",
        "_interaction_grid",
        "_interaction_grid_active",
        "_legacy_grid_state",
        "_interaction_plane",
        "_interaction_plane_active",
    )

    def __init__(self, session, plan_snap_modes):
        self._session = session
        self._plan_snap_modes = tuple(plan_snap_modes or ())
        self._semantic_provider = self._query_semantic_snap
        self._semantic_provider_active = False
        self._interaction_grid = None
        self._interaction_grid_active = False
        self._legacy_grid_state = None
        self._interaction_plane = None
        self._interaction_plane_active = False

    @property
    def session(self):
        return self._session

    def apply_plan_snap_profile(self):
        result = apply_plan_snap_profile(
            self._plan_snap_modes,
            view=getattr(self.session, "view", None),
        )
        if not self._interaction_plane_active:
            plane = None
            viewport = getattr(self.session, "viewport", None)
            get_plane = getattr(viewport, "get_interaction_plane", None)
            if callable(get_plane):
                try:
                    plane = get_plane()
                except Exception:
                    plane = None
            if plane is not None:
                configured, previous = _configure_plan_interaction_plane(
                    self.session, plane
                )
                if configured:
                    self._interaction_plane = previous
                    self._interaction_plane_active = True
        return result

    def apply_plan_grid(self):
        """Install the session's temporary reference-frame grid once."""

        if self._interaction_grid_active:
            return self._interaction_grid
        grid = apply_plan_grid(self.session)
        if grid is not None:
            self._interaction_grid = grid
            self._interaction_grid_active = True
            self._hide_legacy_grid()
        return grid

    def restore_plan_grid(self):
        """Restore the interaction grid owned by this Plan Edit session."""

        if not self._interaction_grid_active:
            return None
        restored = restore_plan_grid(
            self._interaction_grid,
            view=getattr(self.session, "view", None),
        )
        self._restore_legacy_grid()
        self._interaction_grid = None
        self._interaction_grid_active = False
        return restored

    def _hide_legacy_grid(self):
        """Hide Draft's scene tracker while the BIM grid overlay is active."""

        if self._legacy_grid_state is not None:
            return
        snapper = _get_snapper()
        if snapper is None:
            return
        view = getattr(self.session, "view", None)
        set_trackers = getattr(snapper, "setTrackers", None)
        context_for = getattr(snapper, "context_for", None)
        if not callable(set_trackers) or not callable(context_for):
            return
        try:
            set_trackers(update_grid=False, view=view)
            context = context_for(view)
            grid = getattr(getattr(context, "trackers", None), "grid", None)
            if grid is None:
                grid = getattr(snapper, "grid", None)
            if grid is None:
                return
            self._legacy_grid_state = (
                grid,
                bool(getattr(grid, "Visible", False)),
                bool(getattr(grid, "show_always", False)),
                bool(getattr(grid, "show_during_command", False)),
            )
            grid.show_always = False
            grid.show_during_command = False
            grid.off()
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            self._legacy_grid_state = None

    def _restore_legacy_grid(self):
        state = self._legacy_grid_state
        if state is None:
            return
        self._legacy_grid_state = None
        grid, visible, show_always, show_during_command = state
        try:
            grid.show_always = show_always
            grid.show_during_command = show_during_command
            if visible:
                grid.on()
            else:
                grid.off()
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass

    def restore_snap_profile(self):
        self.restore_plan_grid()
        result = restore_snap_profile(view=getattr(self.session, "view", None))
        if self._interaction_plane_active:
            _restore_plan_interaction_plane(self.session, self._interaction_plane)
            self._interaction_plane = None
            self._interaction_plane_active = False
        return result

    def enable_semantic_snapping(self):
        if self._semantic_provider_active:
            return
        method = _get_snapper_method("push_semantic_snap_provider")
        if method is not None:
            _call_for_view(
                method,
                self._semantic_provider,
                view=getattr(self.session, "view", None),
            )
            self._semantic_provider_active = True

    def disable_semantic_snapping(self):
        if not self._semantic_provider_active:
            return
        method = _get_snapper_method("pop_semantic_snap_provider")
        if method is not None:
            _call_for_view(
                method,
                self._semantic_provider,
                view=getattr(self.session, "view", None),
            )
        self._semantic_provider_active = False

    def _query_semantic_snap(self, point, tolerance):
        renderer = self.session.contextual_rendering.renderer
        if renderer is None:
            return None
        return renderer.query_snap(
            point,
            tolerance,
            request=self.session.representation_request.request,
        )

    def set_active_draft_command(self):
        return set_active_draft_command(self.session)

    def clear_active_draft_command(self):
        return clear_active_draft_command()

    def stop_snapper(self):
        return stop_snapper()

    def set_point_focus_suppressed(self, suppressed):
        return set_point_focus_suppressed(suppressed)
