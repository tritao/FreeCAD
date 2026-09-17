# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft snap profile helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui


_PLAN_GRID_PREFERENCES = "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
_DEFAULT_GRID_SPACING = 100.0
_DEFAULT_GRID_MAJOR_EVERY = 10


def _get_snapper():
    return getattr(FreeCADGui, "Snapper", None)


def _get_snapper_method(method_name):
    snapper = _get_snapper()
    if not snapper:
        return None
    method = getattr(snapper, method_name, None)
    return method if callable(method) else None


def apply_plan_snap_profile(snap_modes):
    push_snap_modes = _get_snapper_method("push_snap_modes")
    if push_snap_modes is None:
        return
    try:
        push_snap_modes(snap_modes)
    except Exception:
        pass


def restore_snap_profile():
    pop_snap_modes = _get_snapper_method("pop_snap_modes")
    if pop_snap_modes is None:
        return
    try:
        pop_snap_modes()
    except Exception:
        pass


def _plan_grid_spacing():
    """Read Plan Edit grid spacing without changing Draft preferences."""

    preferences = FreeCAD.ParamGet(_PLAN_GRID_PREFERENCES)
    raw_spacing = preferences.GetString("GridSpacing", "100 mm")
    try:
        spacing = FreeCAD.Units.Quantity(raw_spacing).Value
    except (TypeError, ValueError):
        spacing = _DEFAULT_GRID_SPACING
    if spacing <= 0:
        spacing = _DEFAULT_GRID_SPACING
    major_every = preferences.GetInt("GridMainlines", _DEFAULT_GRID_MAJOR_EVERY)
    if major_every <= 0:
        major_every = _DEFAULT_GRID_MAJOR_EVERY
    return spacing, major_every


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

        spacing, major_every = _plan_grid_spacing()
        return GridLattice(
            getattr(plane, "position", FreeCAD.Vector()),
            getattr(plane, "u", FreeCAD.Vector(1, 0, 0)),
            getattr(plane, "v", FreeCAD.Vector(0, 1, 0)),
            spacing=spacing,
            major_every=major_every,
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
        push_interaction_grid(grid)
    except Exception:
        return None
    return grid


def restore_plan_grid(grid=None):
    """Restore the previous Draft interaction grid during Plan Edit teardown."""

    pop_interaction_grid = _get_snapper_method("pop_interaction_grid")
    if pop_interaction_grid is None:
        return None
    try:
        return pop_interaction_grid(grid)
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
    )

    def __init__(self, session, plan_snap_modes):
        self._session = session
        self._plan_snap_modes = tuple(plan_snap_modes or ())
        self._semantic_provider = self._query_semantic_snap
        self._semantic_provider_active = False
        self._interaction_grid = None
        self._interaction_grid_active = False

    @property
    def session(self):
        return self._session

    def apply_plan_snap_profile(self):
        return apply_plan_snap_profile(self._plan_snap_modes)

    def apply_plan_grid(self):
        """Install the session's temporary reference-frame grid once."""

        if self._interaction_grid_active:
            return self._interaction_grid
        grid = apply_plan_grid(self.session)
        if grid is not None:
            self._interaction_grid = grid
            self._interaction_grid_active = True
        return grid

    def restore_plan_grid(self):
        """Restore the interaction grid owned by this Plan Edit session."""

        if not self._interaction_grid_active:
            return None
        restored = restore_plan_grid(self._interaction_grid)
        self._interaction_grid = None
        self._interaction_grid_active = False
        return restored

    def restore_snap_profile(self):
        self.restore_plan_grid()
        return restore_snap_profile()

    def enable_semantic_snapping(self):
        if self._semantic_provider_active:
            return
        method = _get_snapper_method("push_semantic_snap_provider")
        if method is not None:
            method(self._semantic_provider)
            self._semantic_provider_active = True

    def disable_semantic_snapping(self):
        if not self._semantic_provider_active:
            return
        method = _get_snapper_method("pop_semantic_snap_provider")
        if method is not None:
            method(self._semantic_provider)
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
