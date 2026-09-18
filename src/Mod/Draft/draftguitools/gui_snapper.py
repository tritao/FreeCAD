# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2011 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************
"""Provides the Snapper class to define the snapping tools and modes.

This module provides tools to handle point snapping and
everything that goes with it (toolbar buttons, cursor icons, etc.).
It also creates the Draft grid, which is actually a tracker
defined by `gui_trackers.gridTracker`.
"""

## @package gui_snapper
#  \ingroup draftguitools
#  \brief Provides the Snapper class to define the snapping tools and modes.
#
#  This module provides tools to handle point snapping and
#  everything that goes with it (toolbar buttons, cursor icons, etc.).

## \addtogroup draftguitools
# @{
import collections as coll
import inspect
import itertools
import math
from pivy import coin
from PySide import QtCore
from PySide import QtGui
from PySide import QtWidgets

import FreeCAD as App
import FreeCADGui as Gui
import Part
import DraftVecUtils
import WorkingPlane
from draftgeoutils import edges as geo_edges
from draftgeoutils import general as geo_general
from draftgeoutils import geometry as geo_geometry
from draftgeoutils import intersections as geo_intersections
from draftguitools import gui_trackers as trackers
from draftguitools.snap_context import SnapViewContext
from draftutils import gui_utils
from draftutils import params
from draftutils import utils
from draftutils.init_tools import get_draft_snap_commands
from draftutils.messages import _wrn
from draftutils.translate import translate

__title__ = "FreeCAD Draft Snap tools"
__author__ = "Yorik van Havre"
__url__ = "https://www.freecad.org"

UNSNAPPABLES = ("Image::ImagePlane",)
_UNSET = object()


class Snapper:
    """Classes to manage snapping in Draft and Arch.

    The Snapper objects contains all the functionality used by draft
    and arch module to manage object snapping. It is responsible for
    finding snap points and displaying snap markers. Usually You
    only need to invoke it's snap() function, all the rest is taken
    care of.

    3 functions are useful for the scriptwriter: snap(), constrain()
    or getPoint() which is an all-in-one combo.

    The individual snapToXXX() functions return a snap definition in
    the form [real_point,marker_type,visual_point], and are not
    meant to be used directly, they are all called when necessary by
    the general snap() function.

    The Snapper lives inside Gui once the Draft module has been
    loaded.

    """

    def __init__(self):
        self.activeview = None
        self.toolbar = None
        self.lastObj = []
        self.lastObjSubelements = []
        self.radius = 0
        self.constraintAxis = None
        self.basepoint = None
        self.affinity = None
        self.mask = None
        self.cursorMode = None
        self.cursorQt = None
        self.maxEdges = params.get_param("maxSnapEdges")

        # we still have no 3D view when the draft module initializes
        self.tracker = None
        self.extLine = None
        self.grid = None
        # Hosts such as BIM Plan Edit can temporarily provide a semantic
        # interaction grid without replacing Draft's document-local grid
        # tracker or its preferences.  The stack makes nested hosts safe.
        self.interaction_grid = None
        self._interaction_grid_stack = []
        self.constrainLine = None
        self.trackLine = None
        self.extLine2 = None
        self.radiusTracker = None
        self.dim1 = None
        self.dim2 = None
        self.snapInfo = None
        self.lastExtensions = []
        # the trackers are stored in lists because there can be several views,
        # each with its own set
        # view, grid, snap, extline, radius, dim1, dim2, trackLine,
        # extline2, crosstrackers
        self.trackers = [[], [], [], [], [], [], [], [], [], []]
        self.polarAngles = [90, 45]
        self.selectMode = False
        self.holdTracker = None
        self.holdPoints = []
        self.running = False
        self.callbackClick = None
        self.callbackMove = None
        self._point_request_generation = 0
        self.snapObjectIndex = 0
        self.pointConstraintProvider = None
        self.semanticSnapProviders = []
        self._contexts = {}
        self._fallback_context = SnapViewContext()
        self._current_context = None
        self._point_plane_override_active = False
        self._active_view = None

        # snap keys, it's important that they are in this order for
        # saving in preferences and for properly restoring the toolbar
        # fmt: off
        self.snaps = ['Lock',           # 0
                      'Near',           # 1 former "passive" snap
                      'Extension',      # 2
                      'Parallel',       # 3
                      'Grid',           # 4
                      "Endpoint",       # 5
                      'Midpoint',       # 6
                      'Perpendicular',  # 7
                      'Angle',          # 8
                      'Center',         # 9
                      'Ortho',          # 10
                      'Intersection',   # 11
                      'Special',        # 12
                      'Dimensions',     # 13
                      'WorkingPlane'    # 14
                     ]
        # fmt: on

        self.init_active_snaps()
        self._active_snaps_alias = self.active_snaps
        self._snap_mode_stack = []
        self.set_snap_style()

        self.cursors = coll.OrderedDict(
            [
                ("passive", ":/icons/Draft_Snap_Near.svg"),
                ("extension", ":/icons/Draft_Snap_Extension.svg"),
                ("parallel", ":/icons/Draft_Snap_Parallel.svg"),
                ("grid", ":/icons/Draft_Snap_Grid.svg"),
                ("endpoint", ":/icons/Draft_Snap_Endpoint.svg"),
                ("midpoint", ":/icons/Draft_Snap_Midpoint.svg"),
                ("perpendicular", ":/icons/Draft_Snap_Perpendicular.svg"),
                ("angle", ":/icons/Draft_Snap_Angle.svg"),
                ("center", ":/icons/Draft_Snap_Center.svg"),
                ("ortho", ":/icons/Draft_Snap_Ortho.svg"),
                ("intersection", ":/icons/Draft_Snap_Intersection.svg"),
                ("special", ":/icons/Draft_Snap_Special.svg"),
            ]
        )

    def _get_wp(self):
        # update=False is required, without it WorkingPlane.get_working_plane()
        # is too slow for this function which gets called repeatedly when moving
        # the mouse
        # See: https://github.com/FreeCAD/FreeCAD/issues/24013
        interaction_plane = getattr(self, "interaction_plane", None)
        if interaction_plane is not None:
            return interaction_plane
        context = self._current_context
        if context is not None and context.interaction_plane is not None:
            return context.interaction_plane
        return WorkingPlane.get_working_plane(update=False)

    def context_for(self, view=None):
        """Return the persistent snapping context for ``view``.

        View wrappers are retained by the context itself, so using their
        ``id`` as the registry key also works for bindings that are not
        hashable. A single fallback context preserves the old no-view API.
        """

        if view is None:
            view = gui_utils.get_3d_view()
        if view is None:
            return self._fallback_context
        key = id(view)
        context = self._contexts.get(key)
        if context is not None and context.view is view:
            return context
        if context is not None:
            try:
                if context.view == view:
                    return context
            except Exception:
                pass
        for context in self._contexts.values():
            try:
                if context.view is view or context.view == view:
                    return context
            except Exception:
                continue
        context = SnapViewContext(view=view)
        self._contexts[key] = context
        return context

    def current_context(self, view=None):
        """Return the context used by the latest snap event."""

        if view is not None:
            return self._sync_context_aliases(self.context_for(view))
        if self._current_context is not None:
            return self._sync_context_aliases(self._current_context)
        return self._sync_context_aliases(self.context_for())

    def remove_context(self, view):
        """Forget a closed viewport and its transient trackers."""

        if view is None:
            return None
        context = self._contexts.pop(id(view), None)
        if context is None:
            for key, candidate in tuple(self._contexts.items()):
                try:
                    if candidate.view == view:
                        context = self._contexts.pop(key)
                        break
                except Exception:
                    continue
        if context is not None:
            self._snap_mode_stack = [
                entry for entry in self._snap_mode_stack if entry[0] is not context
            ]
            self._interaction_grid_stack = [
                entry for entry in self._interaction_grid_stack if entry[0] is not context
            ]
            # Keep the legacy parallel arrays in sync for callers that still
            # inspect them directly.  The context owns the actual trackers.
            for index, tracker in enumerate(
                (
                    context.trackers.grid,
                    context.trackers.snap,
                    context.trackers.extension,
                    context.trackers.radius,
                    context.trackers.dim1,
                    context.trackers.dim2,
                    context.trackers.track_line,
                    context.trackers.extension2,
                    context.trackers.hold,
                ),
                start=1,
            ):
                if tracker is None:
                    continue
                try:
                    self.trackers[index].remove(tracker)
                except (ValueError, IndexError):
                    pass
            try:
                self.trackers[0].remove(context.view)
            except (ValueError, IndexError):
                pass
        if context is self._current_context:
            self._sync_context_aliases(self._fallback_context)
        return context

    def _effective_snap_modes(self, context):
        if context is None or context.modes is None:
            return self._global_active_snaps
        return context.modes

    def _sync_context_aliases(self, context):
        """Update legacy fields to point at the active context."""

        # ``active_snaps`` predates view-local contexts and is still assigned
        # directly by a few integrations.  Notice a replacement of that
        # legacy list before rebinding it to the context, preserving the old
        # API while keeping context-local overrides isolated.
        legacy_modes = getattr(self, "active_snaps", None)
        legacy_alias = getattr(self, "_active_snaps_alias", None)
        if legacy_modes is not None and legacy_modes is not legacy_alias:
            requested = set(legacy_modes)
            normalized = [snap for snap in self.snaps if snap in requested]
            if self._current_context is not None and self._current_context.modes is not None:
                self._current_context.modes = normalized
            else:
                self._global_active_snaps = normalized

        self._current_context = context
        self._active_view = context.view
        self.activeview = context.view
        self.active_snaps = self._effective_snap_modes(context)
        self._active_snaps_alias = self.active_snaps
        self.interaction_grid = context.grid_provider
        self.semanticSnapProviders = context.semantic_providers
        if not self._point_plane_override_active:
            self.interaction_plane = context.interaction_plane
        return context

    def _activate_context(self, view=None):
        return self._sync_context_aliases(self.context_for(view))

    def configure_view(
        self,
        view=None,
        *,
        modes=_UNSET,
        interaction_plane=_UNSET,
        grid_provider=_UNSET,
        semantic_providers=_UNSET,
    ):
        """Configure only the view-local inputs used by snapping."""

        context = self.context_for(view)
        if modes is not _UNSET:
            if modes is None:
                context.modes = None
            else:
                requested = set(modes)
                context.modes = [snap for snap in self.snaps if snap in requested]
        if interaction_plane is not _UNSET:
            context.interaction_plane = interaction_plane
        if grid_provider is not _UNSET:
            context.grid_provider = grid_provider
        if semantic_providers is not _UNSET:
            context.semantic_providers = list(semantic_providers or ())
        if context is self._current_context:
            self._sync_context_aliases(context)
        return context

    def init_active_snaps(self):
        """
        set self.active_snaps according to user prefs
        """
        self._global_active_snaps = []
        snap_modes = params.get_param("snapModes")
        i = 0
        for snap in snap_modes:
            if bool(int(snap)):
                self._global_active_snaps.append(self.snaps[i])
            i += 1
        self.active_snaps = self._global_active_snaps

    def get_snap_modes(self, view=None):
        """Return the currently active snap names."""
        if view is not None:
            return list(self._effective_snap_modes(self.context_for(view)))
        if self._current_context is not None:
            return list(self._effective_snap_modes(self._current_context))
        return list(self.active_snaps)

    def set_snap_modes(self, active_snaps, view=None):
        """Replace the current active snaps with the provided snap names."""
        requested = set(active_snaps)
        valid_snaps = [snap for snap in self.snaps if snap in requested]
        context = self.current_context(view)
        context.modes = valid_snaps
        if context is self._current_context:
            self._sync_context_aliases(context)
        self.save_snap_state()
        return list(valid_snaps)

    def push_snap_modes(self, active_snaps, view=None):
        """Save current snap state and apply a temporary snap profile."""
        context = self.current_context(view)
        self._snap_mode_stack.append((context, context.modes))
        requested = set(active_snaps)
        context.modes = [snap for snap in self.snaps if snap in requested]
        if context is self._current_context:
            self._sync_context_aliases(context)
        return self.get_snap_modes(view=context.view)

    def pop_snap_modes(self, view=None):
        """Restore the most recently pushed temporary snap profile."""
        if not self._snap_mode_stack:
            return self.get_snap_modes(view=view)
        context = self.context_for(view) if view is not None else self.current_context()
        stack_index = len(self._snap_mode_stack) - 1
        while stack_index >= 0 and self._snap_mode_stack[stack_index][0] is not context:
            stack_index -= 1
        if stack_index < 0:
            return self.get_snap_modes(view=view)
        context, previous = self._snap_mode_stack.pop(stack_index)
        context.modes = previous
        if context is self._current_context:
            self._sync_context_aliases(context)
        return self.get_snap_modes(view=context.view if view is not None else None)

    def push_semantic_snap_provider(self, provider, view=None):
        """Add a temporary renderer-independent snap source."""

        if callable(provider):
            context = self.current_context(view)
            context.semantic_providers.append(provider)
            if context is self._current_context:
                self._sync_context_aliases(context)
        return provider

    def pop_semantic_snap_provider(self, provider=None, view=None):
        """Remove the newest provider, or a specific registered provider."""

        context = self.current_context(view)
        providers = context.semantic_providers
        if not providers:
            return None
        if provider is None:
            removed = providers.pop()
            if context is self._current_context:
                self._sync_context_aliases(context)
            return removed
        for index in range(len(providers) - 1, -1, -1):
            if providers[index] is provider:
                removed = providers.pop(index)
                if context is self._current_context:
                    self._sync_context_aliases(context)
                return removed
        return None

    def push_interaction_grid(self, grid, view=None):
        """Install a temporary renderer-independent interaction grid.

        The normal ``grid`` tracker remains untouched.  This is intended for
        embedded planar hosts that need their own reference frame and snap
        spacing while still using Draft's point acquisition machinery.
        """

        if grid is None:
            return None
        context = self.current_context(view)
        self._interaction_grid_stack.append((context, context.grid_provider))
        context.grid_provider = grid
        if context is self._current_context:
            self._sync_context_aliases(context)
        return grid

    def pop_interaction_grid(self, grid=None, view=None):
        """Restore the previous temporary interaction grid.

        Passing ``grid`` guards against an owner accidentally removing a
        newer nested provider.  With no stack entry, the active provider is
        simply cleared to keep teardown idempotent.
        """

        context = self.current_context(view)
        active = context.grid_provider
        if grid is not None and active is not grid:
            return None
        if self._interaction_grid_stack:
            stack_index = len(self._interaction_grid_stack) - 1
            while (
                stack_index >= 0
                and self._interaction_grid_stack[stack_index][0] is not context
            ):
                stack_index -= 1
            if stack_index < 0:
                return None
            stacked_context, previous = self._interaction_grid_stack.pop(stack_index)
            context.grid_provider = previous
        else:
            context.grid_provider = None
        if context is self._current_context:
            self._sync_context_aliases(context)
        return active

    def set_snap_style(self):
        self.snapStyle = params.get_param("snapStyle")
        if self.snapStyle:
            self.mk = coll.OrderedDict(
                [
                    ("passive", "SQUARE_LINE"),
                    ("extension", "SQUARE_LINE"),
                    ("parallel", "SQUARE_LINE"),
                    ("grid", "SQUARE_FILLED"),
                    ("endpoint", "SQUARE_FILLED"),
                    ("midpoint", "SQUARE_FILLED"),
                    ("perpendicular", "SQUARE_FILLED"),
                    ("angle", "SQUARE_FILLED"),
                    ("center", "SQUARE_FILLED"),
                    ("ortho", "SQUARE_FILLED"),
                    ("intersection", "SQUARE_FILLED"),
                    ("special", "SQUARE_FILLED"),
                ]
            )
        else:
            self.mk = coll.OrderedDict(
                [
                    ("passive", "CIRCLE_LINE"),
                    ("extension", "CIRCLE_LINE"),
                    ("parallel", "CIRCLE_LINE"),
                    ("grid", "CIRCLE_LINE"),
                    ("endpoint", "CIRCLE_FILLED"),
                    ("midpoint", "DIAMOND_FILLED"),
                    ("perpendicular", "CIRCLE_FILLED"),
                    ("angle", "DIAMOND_FILLED"),
                    ("center", "CIRCLE_FILLED"),
                    ("ortho", "CIRCLE_FILLED"),
                    ("intersection", "CIRCLE_FILLED"),
                    ("special", "CIRCLE_FILLED"),
                ]
            )

    def cstr(self, lastpoint, constrain, point):
        """Return constraints if needed."""
        if constrain or self.mask:
            fpt = self.constrain(point, lastpoint)
        else:
            self.unconstrain()
            fpt = point
        if self.radiusTracker:
            self.radiusTracker.update(fpt)
        return fpt

    def snap(
        self,
        screenpos,
        lastpoint=None,
        active=True,
        constrain=False,
        noTracker=False,
        view=None,
    ):
        """Return a snapped point from the given (x, y) screen position.

        snap(screenpos,lastpoint=None,active=True,constrain=False,
        noTracker=False,view=None): returns a snapped point from the given
        (x,y) screenpos (the position of the mouse cursor), active is to
        activate active point snapping or not (passive),
        lastpoint is an optional other point used to draw an
        imaginary segment and get additional snap locations. Constrain can
        be True to constrain the point against the closest working plane axis.
        Screenpos can be a list, a tuple or a coin.SbVec2s object.
        If noTracker is True, the tracking line is not displayed.
        """
        if self.running:
            # do not allow concurrent runs
            return None

        view = view if view is not None else gui_utils.get_3d_view()
        self._activate_context(view)

        self.running = True

        self.spoint = None

        if params.get_param("SnapBarShowOnlyDuringCommands"):
            toolbar = self.get_snap_toolbar()
            if toolbar:
                toolbar.show()

        self.snapInfo = None

        # Type conversion if needed
        if isinstance(screenpos, list):
            screenpos = tuple(screenpos)
        elif isinstance(screenpos, coin.SbVec2s):
            screenpos = tuple(screenpos.getValue())
        elif not isinstance(screenpos, tuple):
            _wrn("Snap needs valid screen position (list, tuple or sbvec2s)")
            self.running = False
            return None

        # Setup trackers if needed
        self.setTrackers(view=view)

        # Get current snap radius
        self.radius = self.getScreenDist(params.get_param("snapRange"), screenpos, view=view)
        if self.radiusTracker:
            self.radiusTracker.update(self.radius)
            self.radiusTracker.off()

        # Activate snap
        if params.get_param("alwaysSnap"):
            active = True

        self.setCursor("passive")
        if self.tracker:
            self.tracker.off()
        if self.extLine2:
            self.extLine2.off()
        if self.extLine:
            self.extLine.off()
        if self.trackLine:
            self.trackLine.off()
        if self.dim1:
            self.dim1.off()
        if self.dim2:
            self.dim2.off()

        point = self.getApparentPoint(screenpos[0], screenpos[1], view=view)

        semantic_snap = self._snap_to_semantic_provider(point) if active else None
        if semantic_snap is not None:
            snapped = self._apply_point_constraint(
                App.Vector(semantic_snap.point), lastpoint, noTracker
            )
            marker = (
                "endpoint"
                if getattr(semantic_snap.target.geometry, "ShapeType", "") == "Vertex"
                else "passive"
            )
            self.snapInfo = {
                "SemanticSnap": semantic_snap,
                "Object": getattr(semantic_snap.source, "Name", ""),
                "Component": semantic_snap.subelement or "",
            }
            if self.tracker and not self.selectMode:
                self.tracker.setCoords(snapped)
                self.tracker.setMarker(self.mk[marker])
                self.tracker.on()
            self.setCursor(marker)
            self.spoint = snapped
            self.running = False
            return snapped

        # Set up a track line if we got a last point
        if lastpoint and self.trackLine:
            self.trackLine.p1(lastpoint)

        # Check if parallel to one of the edges of the last objects
        # or to a polar direction
        eline = None
        if active:
            point, eline = self.snapToPolar(point, lastpoint)
            point, eline = self.snapToExtensions(point, lastpoint, constrain, eline)

        # Check if we have an object under the cursor and try to
        # snap to it
        if view is None:
            self.running = False
            return point
        objectsUnderCursor = view.getObjectsInfo((screenpos[0], screenpos[1]))
        if objectsUnderCursor:
            if self.snapObjectIndex >= len(objectsUnderCursor):
                self.snapObjectIndex = 0
            self.snapInfo = objectsUnderCursor[self.snapObjectIndex]

        if self.snapInfo and "Component" in self.snapInfo:
            osnap = self.snapToObject(lastpoint, active, constrain, eline, point)
            if osnap:
                osnap = self._apply_point_constraint(osnap, lastpoint, noTracker)
                self.running = False
                return osnap

        # Nothing has been snapped.
        # Check for grid snap and ext crossings
        if active:
            epoint = self.snapToCrossExtensions(point)
            if epoint:
                point = epoint
            else:
                point = self.snapToGrid(point)
        fp = self.cstr(lastpoint, constrain, point)
        fp = self._apply_point_constraint(fp, lastpoint, noTracker)
        if self.trackLine and lastpoint and (not noTracker):
            self.trackLine.p2(fp)
            self.trackLine.setColor()
            self.trackLine.on()
        # Set the arch point tracking
        if lastpoint:
            self.setArchDims(lastpoint, fp)

        self.spoint = fp
        self.running = False
        return fp

    def _snap_to_semantic_provider(self, point):
        """Ask the newest active contextual provider for a semantic target."""

        for provider in reversed(self.semanticSnapProviders):
            try:
                result = provider(App.Vector(point), float(self.radius))
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                continue
            if result is not None:
                return result
        return None

    def cycleSnapObject(self):
        """Increase the index of the snap object by one."""
        self.snapObjectIndex += 1

    def snapToObject(self, lastpoint, active, constrain, eline, point):
        """Snap to an object."""

        if not active:
            return None

        parent = self.snapInfo.get("ParentObject", None)
        if parent:
            subname = self.snapInfo["SubName"]
            obj = parent.getSubObject(subname, retType=1)
        else:
            obj = App.ActiveDocument.getObject(self.snapInfo["Object"])
            parent = obj
            subname = self.snapInfo["Component"]

        if (
            not obj
            or utils.get_type(obj) in UNSNAPPABLES
            or not getattr(obj.ViewObject, "Selectable", True)
        ):
            # increase snapObjectIndex to find other objects under the cursor:
            self.snapObjectIndex += 1
            return None

        snaps = []
        point = App.Vector(self.snapInfo["x"], self.snapInfo["y"], self.snapInfo["z"])
        comp = self.snapInfo["Component"]
        shape = Part.getShape(parent, subname, needSubElement=True, noElementMap=True)

        if not shape.isNull():
            snaps.extend(self.snapToSpecials(obj, lastpoint, eline))

            if utils.get_type(obj) == "Polygon":
                # Special snapping for polygons: add the center
                snaps.extend(self.snapToPolygon(obj))

            elif utils.get_type(obj) == "BuildingPart" and self.isEnabled("Center"):
                # snap to the base placement of empty BuildingParts
                snaps.append([obj.Placement.Base, "center", self.toWP(obj.Placement.Base)])

            if (not self.maxEdges) or (len(shape.Edges) <= self.maxEdges):
                if "Edge" in comp:
                    # we are snapping to an edge
                    if shape.ShapeType == "Edge":
                        edge = shape
                        snaps.extend(self.snapToNear(edge, point))
                        snaps.extend(self.snapToEndpoints(edge))
                        snaps.extend(self.snapToMidpoint(edge))
                        snaps.extend(self.snapToPerpendicular(edge, lastpoint))
                        snaps.extend(self.snapToIntersection(edge))
                        snaps.extend(self.snapToElines(edge, eline))

                        et = geo_general.geomType(edge)
                        if et == "Circle":
                            # the edge is an arc, we have extra options
                            snaps.extend(self.snapToAngles(edge))
                            snaps.extend(self.snapToCenter(edge))
                        elif et == "Ellipse":
                            # extra ellipse options
                            snaps.extend(self.snapToCenter(edge))
                        elif et == "BSplineCurve":
                            snaps.extend(self.snapToBSplineKnots(edge))
                elif "Face" in comp:
                    # we are snapping to a face
                    if shape.ShapeType == "Face":
                        face = shape
                        snaps.extend(self.snapToNearFace(face, point))
                        snaps.extend(self.snapToPerpendicularFace(face, lastpoint))
                        snaps.extend(self.snapToIntersection(face))
                        snaps.extend(self.snapToCenterFace(face))
                elif "Vertex" in comp:
                    # we are snapping to a vertex
                    if shape.ShapeType == "Vertex":
                        snaps.extend(self.snapToEndpoints(shape))
                else:
                    # `Catch-all` for other cases. Probably never executes
                    # as objects with a Shape typically have edges, faces
                    # or vertices.
                    snaps.extend(self.snapToNearUnprojected(point))

        elif utils.get_type(obj) in ("LinearDimension", "AngularDimension"):
            # for dimensions we snap to their 2 points:
            snaps.extend(self.snapToDim(obj))

        elif utils.get_type(obj) == "Axis":
            for edge in obj.Shape.Edges:
                snaps.extend(self.snapToEndpoints(edge))
                snaps.extend(self.snapToIntersection(edge))

        elif utils.get_type(obj).startswith("Mesh::"):
            snaps.extend(self.snapToNearUnprojected(point))
            snaps.extend(self.snapToEndpoints(obj.Mesh))

        elif utils.get_type(obj).startswith("Points::"):
            snaps.extend(self.snapToEndpoints(obj.Points, point))

        elif utils.get_type(obj) in ("WorkingPlaneProxy", "BuildingPart") and self.isEnabled(
            "Center"
        ):
            # snap to the center of WPProxies or to the base
            # placement of no empty BuildingParts
            snaps.append([obj.Placement.Base, "center", self.toWP(obj.Placement.Base)])

        elif utils.get_type(obj) == "SectionPlane":
            # snap to corners of section planes
            snaps.extend(self.snapToEndpoints(obj.Shape))

        # updating last objects list
        # objects must be added even if no snap has been found for the object
        # otherwise Intersection snap (for example) will not work
        if obj.Name in self.lastObj:
            self.lastObjSubelements.pop(self.lastObj.index(obj.Name))
            self.lastObj.remove(obj.Name)
        self.lastObj.append(obj.Name)
        self.lastObjSubelements.append(subname.split(".")[-1])
        if len(self.lastObj) > 8:
            self.lastObj = self.lastObj[-8:]
            self.lastObjSubelements = self.lastObjSubelements[-8:]

        if not snaps:
            return None

        # calculating the nearest snap point
        # a Near ("passive") snap point does not 'win' if a different snap point
        # is within snapRange of the cursor point (in screen coordinates)
        cursor_pt = App.Vector(self.snapInfo["x"], self.snapInfo["y"], self.snapInfo["z"])
        shortest_all = shortest_not_near = 1000000000000000000
        winner_all = winner_not_near = None
        for snap in snaps:
            if (not snap) or (snap[0] is None):
                pass
                # print("debug: Snapper: invalid snap point: ", snaps)
            else:
                dist = snap[0].sub(cursor_pt).Length
                if snap[1] != "passive":
                    if dist < shortest_not_near:
                        shortest_not_near = dist
                        winner_not_near = snap
                if dist < shortest_all:
                    shortest_all = dist
                    winner_all = snap

        if winner_not_near is None or shortest_not_near == shortest_all:
            winner = winner_all
        else:
            # get screen points with pixel coordinates
            scr_win_not_near_pt = App.Vector(*view.getPointOnScreen(winner_not_near[0]), 0)
            scr_cursor_pt = App.Vector(*view.getPointOnScreen(cursor_pt), 0)
            if scr_win_not_near_pt.sub(scr_cursor_pt).Length <= params.get_param("snapRange"):
                winner = winner_not_near
            else:
                winner = winner_all

        fp = point
        if winner:
            # setting the cursors
            if self.tracker and not self.selectMode:
                self.tracker.setCoords(winner[2])
                self.tracker.setMarker(self.mk[winner[1]])
                self.tracker.on()
            # setting the trackline
            fp = self.cstr(lastpoint, constrain, winner[2])
            if self.trackLine and lastpoint:
                self.trackLine.p2(fp)
                self.trackLine.setColor()
                self.trackLine.on()
            # set the cursor
            self.setCursor(winner[1])

            # set the arch point tracking
            if lastpoint:
                self.setArchDims(lastpoint, fp)

        # return the final point
        self.spoint = fp
        return self.spoint

    def toWP(self, point):
        """Project the given point on the working plane, if needed."""
        if self.isEnabled("WorkingPlane"):
            return self._get_wp().project_point(point)
        return point

    def getApparentPoint(self, x, y, view=None):
        """Return a 3D point, projected on the current working plane."""
        view = view if view is not None else self._active_view or gui_utils.get_3d_view()
        if view is None:
            return App.Vector()
        pt = view.getPoint(x, y)
        if self.mask != "z":
            if view.getCameraType() == "Perspective":
                camera = view.getCameraNode()
                p = camera.getField("position").getValue()
                dv = pt.sub(App.Vector(p[0], p[1], p[2]))
            else:
                dv = view.getViewDirection()
            return self._get_wp().project_point(pt, dv)
        return pt

    def snapToDim(self, obj):
        snaps = []
        if (
            self.isEnabled("Endpoint")
            and obj.ViewObject
            and hasattr(obj.ViewObject.Proxy, "p2")
            and hasattr(obj.ViewObject.Proxy, "p3")
        ):
            snaps.append([obj.ViewObject.Proxy.p2, "endpoint", self.toWP(obj.ViewObject.Proxy.p2)])
            snaps.append([obj.ViewObject.Proxy.p3, "endpoint", self.toWP(obj.ViewObject.Proxy.p3)])
        return snaps

    def snapToExtensions(self, point, last, constrain, eline):
        """Return a point snapped to extension or parallel line.

        The parallel line of the last object, if any.
        """
        tsnap = self.snapToHold(point)
        if tsnap:
            if self.tracker and not self.selectMode:
                self.tracker.setCoords(tsnap[2])
                self.tracker.setMarker(self.mk[tsnap[1]])
                self.tracker.on()
            if self.extLine:
                self.extLine.p1(tsnap[0])
                self.extLine.p2(tsnap[2])
                self.extLine.setColor()
                self.extLine.on()
            self.setCursor(tsnap[1])
            return tsnap[2], eline
        if self.isEnabled("Extension"):
            tsnap = self.snapToExtOrtho(last, constrain, eline)
            if tsnap:
                if (tsnap[0].sub(point)).Length < self.radius:
                    if self.tracker and not self.selectMode:
                        self.tracker.setCoords(tsnap[2])
                        self.tracker.setMarker(self.mk[tsnap[1]])
                        self.tracker.on()
                    if self.extLine:
                        self.extLine.p2(tsnap[2])
                        self.extLine.setColor()
                        self.extLine.on()
                    self.setCursor(tsnap[1])
                    return tsnap[2], eline
            else:
                tsnap = self.snapToExtPerpendicular(last)
                if tsnap:
                    if (tsnap[0].sub(point)).Length < self.radius:
                        if self.tracker and not self.selectMode:
                            self.tracker.setCoords(tsnap[2])
                            self.tracker.setMarker(self.mk[tsnap[1]])
                            self.tracker.on()
                        if self.extLine:
                            self.extLine.p2(tsnap[2])
                            self.extLine.setColor()
                            self.extLine.on()
                        self.setCursor(tsnap[1])
                        return tsnap[2], eline

        for o in self.lastObj:
            if self.isEnabled("Extension") or self.isEnabled("Parallel"):
                ob = App.ActiveDocument.getObject(o)
                if not ob:
                    continue
                if not ob.isDerivedFrom("Part::Feature"):
                    continue
                edges = ob.Shape.Edges
                if utils.get_type(ob) == "Wall":
                    for so in [ob] + ob.Additions:
                        if utils.get_type(so) == "Wall":
                            if so.Base:
                                edges.extend(so.Base.Shape.Edges)
                                edges.reverse()
                if (not self.maxEdges) or (len(edges) <= self.maxEdges):
                    for e in edges:
                        if geo_general.geomType(e) != "Line":
                            continue
                        np = self.getPerpendicular(e, point)
                        if (np.sub(point)).Length < self.radius:
                            if self.isEnabled("Extension"):
                                if geo_general.isPtOnEdge(np, e):
                                    continue
                                if np != e.Vertexes[0].Point:
                                    p0 = e.Vertexes[0].Point
                                    if self.tracker and not self.selectMode:
                                        self.tracker.setCoords(np)
                                        self.tracker.setMarker(self.mk["extension"])
                                        self.tracker.on()
                                    if self.extLine:
                                        self.extLine.p1(p0)
                                        self.extLine.p2(np)
                                        self.extLine.setColor()
                                        self.extLine.on()
                                    self.setCursor("extension")
                                    ne = Part.LineSegment(p0, np).toShape()
                                    # storing extension line for intersection calculations later
                                    if len(self.lastExtensions) == 0:
                                        self.lastExtensions.append(ne)
                                    elif len(self.lastExtensions) == 1:
                                        if not geo_general.areColinear(ne, self.lastExtensions[0]):
                                            self.lastExtensions.append(self.lastExtensions[0])
                                            self.lastExtensions[0] = ne
                                    else:
                                        if (
                                            not geo_general.areColinear(ne, self.lastExtensions[0])
                                        ) and (
                                            not geo_general.areColinear(ne, self.lastExtensions[1])
                                        ):
                                            self.lastExtensions[1] = self.lastExtensions[0]
                                            self.lastExtensions[0] = ne
                                    return np, ne
                        elif self.isEnabled("Parallel"):
                            if last:
                                ve = geo_general.vec(e)
                                if not DraftVecUtils.isNull(ve):
                                    de = Part.LineSegment(last, last.add(ve)).toShape()
                                    np = self.getPerpendicular(de, point)
                                    if (np.sub(point)).Length < self.radius:
                                        if self.tracker and not self.selectMode:
                                            self.tracker.setCoords(np)
                                            self.tracker.setMarker(self.mk["parallel"])
                                            self.tracker.on()
                                        self.setCursor("parallel")
                                        return np, de
        return point, eline

    def snapToCrossExtensions(self, point):
        """Snap to the intersection of the last 2 extension lines."""
        if self.isEnabled("Extension"):
            if len(self.lastExtensions) == 2:
                np = geo_intersections.findIntersection(
                    self.lastExtensions[0], self.lastExtensions[1], True, True
                )
                if np:
                    for p in np:
                        dv = point.sub(p)
                        if (self.radius == 0) or (dv.Length <= self.radius):
                            if self.tracker and not self.selectMode:
                                self.tracker.setCoords(p)
                                self.tracker.setMarker(self.mk["intersection"])
                                self.tracker.on()
                            self.setCursor("intersection")
                            if self.extLine and self.extLine2:
                                if DraftVecUtils.equals(
                                    self.extLine.p1(), self.lastExtensions[0].Vertexes[0].Point
                                ):
                                    p0 = self.lastExtensions[1].Vertexes[0].Point
                                else:
                                    p0 = self.lastExtensions[0].Vertexes[0].Point
                                self.extLine2.p1(p0)
                                self.extLine2.p2(p)
                                self.extLine.p2(p)
                                self.extLine.setColor()
                                self.extLine2.on()
                            return p
        return None

    def snapToPolar(self, point, last):
        """Snap to polar lines from the given point."""
        if self.isEnabled("Ortho") and (not self.mask):
            if last:
                vecs = []
                wp = self._get_wp()
                ax = [wp.u, wp.v, wp.axis]
                for a in self.polarAngles:
                    if a == 90:
                        vecs.extend([ax[0], ax[0].negative()])
                        vecs.extend([ax[1], ax[1].negative()])
                    else:
                        v = DraftVecUtils.rotate(ax[0], math.radians(a), ax[2])
                        vecs.extend([v, v.negative()])
                        v = DraftVecUtils.rotate(ax[1], math.radians(a), ax[2])
                        vecs.extend([v, v.negative()])
                for v in vecs:
                    if not DraftVecUtils.isNull(v):
                        try:
                            de = Part.LineSegment(last, last.add(v)).toShape()
                        except Part.OCCError:
                            return point, None
                        np = self.getPerpendicular(de, point)
                        if ((self.radius == 0) and (point.sub(last).getAngle(v) < 0.087)) or (
                            (np.sub(point)).Length < self.radius
                        ):
                            if self.tracker and not self.selectMode:
                                self.tracker.setCoords(np)
                                self.tracker.setMarker(self.mk["parallel"])
                                self.tracker.on()
                                self.setCursor("ortho")
                            return np, de
        return point, None

    def snapToGrid(self, point):
        """Return a grid snap point if available."""
        grid = self.interaction_grid if self.interaction_grid is not None else self.grid
        if grid is not None and self.isEnabled("Grid"):
            # Temporary interaction grids are semantic providers and do not
            # expose Draft tracker visibility state.  The regular tracker
            # retains its existing Visible gate.
            visible = self.interaction_grid is not None or bool(
                getattr(grid, "Visible", False)
            )
            if visible:
                get_node = getattr(grid, "nearest_node", None)
                if not callable(get_node):
                    get_node = getattr(grid, "getClosestNode", None)
                if callable(get_node):
                    np = get_node(point)
                    if np:
                        dv = point.sub(np)
                        if (self.radius == 0) or (dv.Length <= self.radius):
                            if self.tracker and not self.selectMode:
                                self.tracker.setCoords(np)
                                self.tracker.setMarker(self.mk["grid"])
                                self.tracker.on()
                            self.setCursor("grid")
                            return np
        return point

    def snapToEndpoints(self, shape, point=None):
        """Return a list of endpoints snap locations."""
        if self.isEnabled("Endpoint"):
            if hasattr(shape, "Vertexes"):
                snaps = []
                for v in shape.Vertexes:
                    snaps.append([v.Point, "endpoint", self.toWP(v.Point)])
                return snaps
            if hasattr(shape, "Point"):
                return [[shape.Point, "endpoint", self.toWP(shape.Point)]]
            if hasattr(shape, "Points") and point is not None:
                # point cloud
                # Same as snapToNearUnprojected.
                # Processing individual points in a large point cloud is way too slow:
                # https://github.com/FreeCAD/FreeCAD/issues/22367
                # Must come before handling of mesh as even accessing shape.Points is slow then.
                return [[point, "endpoint", self.toWP(point)]]
            if hasattr(shape, "Points"):
                # mesh
                pts = shape.Points
                if pts and hasattr(pts[0], "Vector"):
                    snaps = []
                    for pt in pts:
                        snaps.append([pt.Vector, "endpoint", self.toWP(pt.Vector)])
                    return snaps
        return []

    def snapToMidpoint(self, shape):
        """Return a list of midpoints snap locations."""
        snaps = []
        if self.isEnabled("Midpoint"):
            if isinstance(shape, Part.Edge):
                mp = geo_edges.findMidpoint(shape)
                if mp:
                    snaps.append([mp, "midpoint", self.toWP(mp)])
        return snaps

    def snapToBSplineKnots(self, edge):
        """Return a list of knot snap locations for a BSpline."""
        snaps = []
        if self.isEnabled("Special"):
            if hasattr(edge, "Curve") and isinstance(edge.Curve, Part.BSplineCurve):
                knots = edge.Curve.getKnots()
                for k in knots:
                    p = edge.Curve.value(k)
                    snaps.append([p, "special", self.toWP(p)])
        return snaps

    def snapToNear(self, shape, point):
        """Return a list with a near snap location for an edge."""
        if self.isEnabled("Near") and point:
            try:
                np = shape.Curve.projectPoint(point, "NearestPoint")
            except Exception:
                return []
            return [[np, "passive", self.toWP(np)]]
        else:
            return []

    def snapToNearFace(self, shape, point):
        """Return a list with a near snap location for a face."""
        if self.isEnabled("Near") and point:
            try:
                np = shape.Surface.projectPoint(point, "NearestPoint")
            except Exception:
                return []
            return [[np, "passive", self.toWP(np)]]
        else:
            return []

    def snapToNearUnprojected(self, point):
        """Return a list with a near snap location that is not projected on the object."""
        if self.isEnabled("Near") and point:
            return [[point, "passive", self.toWP(point)]]
        else:
            return []

    def snapToPerpendicular(self, shape, last):
        """Return a list of perpendicular snap locations for an edge."""
        if self.isEnabled("Perpendicular") and last:
            curv = shape.Curve
            try:
                prs = curv.projectPoint(last, "Parameter")
            except Exception:
                return []
            snaps = []
            for pr in prs:
                np = curv.value(pr)
                snaps.append([np, "perpendicular", self.toWP(np)])
            return snaps
        else:
            return []

    def snapToPerpendicularFace(self, shape, last):
        """Return a list of perpendicular snap locations for a face."""
        if self.isEnabled("Perpendicular") and last:
            surf = shape.Surface
            try:
                prs = surf.projectPoint(last, "Parameters")
            except Exception:
                return []
            snaps = []
            for pr in prs:
                np = surf.value(pr[0], pr[1])
                snaps.append([np, "perpendicular", self.toWP(np)])
            return snaps
        else:
            return []

    def snapToOrtho(self, shape, last, constrain):
        """Return a list of ortho snap locations."""
        snaps = []
        if self.isEnabled("Ortho"):
            if constrain:
                if isinstance(shape, Part.Edge):
                    if last:
                        if geo_general.geomType(shape) == "Line":
                            if self.constraintAxis:
                                tmpEdge = Part.LineSegment(
                                    last, last.add(self.constraintAxis)
                                ).toShape()
                                # get the intersection points
                                pt = geo_intersections.findIntersection(tmpEdge, shape, True, True)
                                if pt:
                                    for p in pt:
                                        snaps.append([p, "ortho", self.toWP(p)])
        return snaps

    def snapToExtOrtho(self, last, constrain, eline):
        """Return an ortho X extension snap location."""
        if self.isEnabled("Extension") and self.isEnabled("Ortho"):
            if constrain and last and self.constraintAxis and self.extLine:
                tmpEdge1 = Part.LineSegment(last, last.add(self.constraintAxis)).toShape()
                tmpEdge2 = Part.LineSegment(self.extLine.p1(), self.extLine.p2()).toShape()
                # get the intersection points
                pt = geo_intersections.findIntersection(tmpEdge1, tmpEdge2, True, True)
                if pt:
                    return [pt[0], "ortho", pt[0]]
            if eline:
                try:
                    tmpEdge2 = Part.LineSegment(self.extLine.p1(), self.extLine.p2()).toShape()
                    # get the intersection points
                    pt = geo_intersections.findIntersection(eline, tmpEdge2, True, True)
                    if pt:
                        return [pt[0], "ortho", pt[0]]
                except Exception:
                    return None
        return None

    def snapToHold(self, point):
        """Return a snap location that is orthogonal to hold points.

        Or if possible at crossings.
        """
        if not self.holdPoints:
            return None
        wp = self._get_wp()
        u = wp.u
        v = wp.v
        if len(self.holdPoints) > 1:
            # first try mid points
            if self.isEnabled("Midpoint"):
                l = list(self.holdPoints)
                for p1, p2 in itertools.combinations(l, 2):
                    p3 = p1.add((p2.sub(p1)).multiply(0.5))
                    if (p3.sub(point)).Length < self.radius:
                        return [p1, "midpoint", p3]
            # then try int points
            ipoints = []
            l = list(self.holdPoints)
            while len(l) > 1:
                p1 = l.pop()
                for p2 in l:
                    i1 = geo_intersections.findIntersection(
                        p1, p1.add(u), p2, p2.add(v), True, True
                    )
                    if i1:
                        ipoints.append([p1, i1[0]])
                    i2 = geo_intersections.findIntersection(
                        p1, p1.add(v), p2, p2.add(u), True, True
                    )
                    if i2:
                        ipoints.append([p1, i2[0]])
            for p in ipoints:
                if (p[1].sub(point)).Length < self.radius:
                    return [p[0], "ortho", p[1]]
        # then try to stick to a line
        for p in self.holdPoints:
            d = geo_geometry.findDistance(point, [p, p.add(u)])
            if d:
                if d.Length < self.radius:
                    fp = point.add(d)
                    return [p, "extension", fp]
            d = geo_geometry.findDistance(point, [p, p.add(v)])
            if d:
                if d.Length < self.radius:
                    fp = point.add(d)
                    return [p, "extension", fp]
        return None

    def snapToExtPerpendicular(self, last):
        """Return a perpendicular X extension snap location."""
        if self.isEnabled("Extension") and self.isEnabled("Perpendicular"):
            if last and self.extLine:
                if self.extLine.p1() != self.extLine.p2():
                    tmpEdge = Part.LineSegment(self.extLine.p1(), self.extLine.p2()).toShape()
                    np = self.getPerpendicular(tmpEdge, last)
                    return [np, "perpendicular", np]
        return None

    def snapToElines(self, e1, e2):
        """Return a snap at the infinite intersection of the given edges."""
        snaps = []
        if self.isEnabled("Intersection") and self.isEnabled("Extension"):
            if e1 and e2:
                # get the intersection points
                pts = geo_intersections.findIntersection(e1, e2, True, True)
                if pts:
                    for p in pts:
                        snaps.append([p, "intersection", self.toWP(p)])
        return snaps

    def snapToAngles(self, shape):
        """Return a list of angle snap locations."""
        snaps = []
        if self.isEnabled("Angle"):
            place = App.Placement()
            place.Base = shape.Curve.Center
            place.Rotation = App.Rotation(
                App.Vector(1, 0, 0), App.Vector(0, 1, 0), shape.Curve.Axis, "ZXY"
            )
            rad = shape.Curve.Radius
            for deg in (0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330):
                ang = math.radians(deg)
                cur = App.Vector(math.sin(ang) * rad, math.cos(ang) * rad, 0)
                cur = place.multVec(cur)
                snaps.append([cur, "angle", self.toWP(cur)])
        return snaps

    def snapToCenter(self, shape):
        """Return a list of center snap locations."""
        snaps = []
        if self.isEnabled("Center"):
            cen = shape.Curve.Center
            cen_wp = self.toWP(cen)
            if hasattr(shape.Curve, "Radius"):
                place = App.Placement()
                place.Base = cen
                place.Rotation = App.Rotation(
                    App.Vector(1, 0, 0), App.Vector(0, 1, 0), shape.Curve.Axis, "ZXY"
                )
                rad = shape.Curve.Radius
                for deg in (
                    15,
                    37.5,
                    52.5,
                    75,
                    105,
                    127.5,
                    142.5,
                    165,
                    195,
                    217.5,
                    232.5,
                    255,
                    285,
                    307.5,
                    322.5,
                    345,
                ):
                    ang = math.radians(deg)
                    cur = App.Vector(math.sin(ang) * rad, math.cos(ang) * rad, 0)
                    cur = place.multVec(cur)
                    snaps.append([cur, "center", cen_wp])
            else:
                snaps.append([cen, "center", cen_wp])
        return snaps

    def snapToCenterFace(self, shape):
        """Return a face center snap location."""
        snaps = []
        if self.isEnabled("Center"):
            pos = shape.CenterOfMass
            c = self.toWP(pos)
            snaps.append([pos, "center", c])
        return snaps

    def snapToIntersection(self, shape):
        """Return a list of intersection snap locations."""
        snaps = []
        if self.isEnabled("Intersection"):
            # get the stored objects to calculate intersections
            for obj_name, sub_name in zip(self.lastObj, self.lastObjSubelements):
                obj = App.ActiveDocument.getObject(obj_name)
                if obj and (obj.isDerivedFrom("Part::Feature") or utils.get_type(obj) == "Axis"):
                    # obj sub is face, shape is edge:
                    if "Face" in sub_name and shape.ShapeType == "Edge":
                        face = obj.Shape.Faces[int(sub_name[4:]) - 1]
                        try:
                            pts = geo_intersections.findIntersection(face, shape)
                            for pt in pts:
                                snaps.append([pt, "intersection", self.toWP(pt)])
                        except Exception:
                            pass
                    elif "Edge" not in sub_name:
                        pass
                    # obj sub is edge, shape is face:
                    elif shape.ShapeType == "Face":
                        edge = obj.Shape.Edges[int(sub_name[4:]) - 1]
                        try:
                            pts = geo_intersections.findIntersection(edge, shape)
                            for pt in pts:
                                snaps.append([pt, "intersection", self.toWP(pt)])
                        except Exception:
                            pass
                    elif shape.ShapeType != "Edge":
                        pass
                    # obj sub is edge, shape is edge:
                    elif (not self.maxEdges) or (len(obj.Shape.Edges) <= self.maxEdges):
                        for edge in obj.Shape.Edges:
                            try:
                                if (
                                    self.isEnabled("WorkingPlane")
                                    and hasattr(edge, "Curve")
                                    and isinstance(edge.Curve, (Part.Line, Part.LineSegment))
                                    and hasattr(shape, "Curve")
                                    and isinstance(shape.Curve, (Part.Line, Part.LineSegment))
                                ):
                                    # get apparent intersection (lines projected on WP)
                                    p1 = self.toWP(edge.Vertexes[0].Point)
                                    p2 = self.toWP(edge.Vertexes[-1].Point)
                                    p3 = self.toWP(shape.Vertexes[0].Point)
                                    p4 = self.toWP(shape.Vertexes[-1].Point)
                                    pts = geo_intersections.findIntersection(
                                        p1, p2, p3, p4, True, True
                                    )
                                else:
                                    pts = geo_intersections.findIntersection(edge, shape)
                                for pt in pts:
                                    snaps.append([pt, "intersection", self.toWP(pt)])
                            except Exception:
                                pass
                                # some curve types yield an error
                                # when trying to read their types
        return snaps

    def snapToPolygon(self, obj):
        """Return a list of polygon center snap locations."""
        snaps = []
        if self.isEnabled("Center"):
            c = obj.Placement.Base
            for edge in obj.Shape.Edges:
                p1 = edge.Vertexes[0].Point
                p2 = edge.Vertexes[-1].Point
                v1 = p1.add((p2 - p1).scale(0.25, 0.25, 0.25))
                v2 = p1.add((p2 - p1).scale(0.75, 0.75, 0.75))
                snaps.append([v1, "center", self.toWP(c)])
                snaps.append([v2, "center", self.toWP(c)])
        return snaps

    def snapToSpecials(self, obj, lastpoint=None, eline=None):
        """Return special snap locations, if any."""
        snaps = []
        if self.isEnabled("Special"):

            if utils.get_type(obj) == "Wall":
                # special snapping for wall: snap to its base shape if it is linear
                if obj.Base:
                    if not obj.Base.Shape.Solids:
                        for v in obj.Base.Shape.Vertexes:
                            snaps.append([v.Point, "special", self.toWP(v.Point)])

            elif utils.get_type(obj) == "Structure":
                # special snapping for struct: only to its base point
                if obj.Base:
                    if not obj.Base.Shape.Solids:
                        for v in obj.Base.Shape.Vertexes:
                            snaps.append([v.Point, "special", self.toWP(v.Point)])
                else:
                    b = obj.Placement.Base
                    snaps.append([b, "special", self.toWP(b)])
                if obj.ViewObject.ShowNodes:
                    for edge in obj.Proxy.getNodeEdges(obj):
                        snaps.extend(self.snapToEndpoints(edge))
                        snaps.extend(self.snapToMidpoint(edge))
                        snaps.extend(self.snapToPerpendicular(edge, lastpoint))
                        snaps.extend(self.snapToIntersection(edge))
                        snaps.extend(self.snapToElines(edge, eline))

            elif hasattr(obj, "SnapPoints"):
                for p in obj.SnapPoints:
                    p2 = obj.Placement.multVec(p)
                    snaps.append([p2, "special", p2])

        return snaps

    def getScreenDist(self, dist, cursor, view=None):
        """Return a distance in 3D space from a screen pixels distance."""
        view = view if view is not None else self._active_view or gui_utils.get_3d_view()
        if view is None:
            return 0.0
        p1 = view.getPoint(cursor)
        p2 = view.getPoint((cursor[0] + dist, cursor[1]))
        return (p2.sub(p1)).Length

    def getPerpendicular(self, edge, pt):
        """Return a point on an edge, perpendicular to the given point."""
        dv = pt.sub(edge.Vertexes[0].Point)
        nv = DraftVecUtils.project(dv, geo_general.vec(edge))
        np = (edge.Vertexes[0].Point).add(nv)
        return np

    def setArchDims(self, p1, p2):
        """Show arc dimensions between 2 points."""
        if self.isEnabled("Dimensions"):
            if not self.dim1:
                self.dim1 = trackers.archDimTracker(mode=2)
            if not self.dim2:
                self.dim2 = trackers.archDimTracker(mode=3)
            self.dim1.p1(p1)
            self.dim2.p1(p1)
            self.dim1.p2(p2)
            self.dim2.p2(p2)
            if self.dim1.Distance:
                self.dim1.on()
            if self.dim2.Distance:
                self.dim2.on()

    def get_quarter_widget(self, mw):
        if not Gui.isValidQObject(mw):
            return []
        try:
            mdi_area = mw.findChild(QtWidgets.QMdiArea)
        except (AttributeError, RuntimeError, TypeError):
            return []
        if not Gui.isValidQObject(mdi_area):
            return []
        try:
            widgets = mdi_area.findChildren(QtWidgets.QWidget)
        except (AttributeError, RuntimeError, TypeError):
            return []

        views = []
        for widget in widgets:
            if not Gui.isValidQObject(widget):
                continue
            try:
                if widget.inherits("SIM::Coin3D::Quarter::QuarterWidget"):
                    views.append(widget)
            except (AttributeError, RuntimeError, TypeError):
                continue
        return views

    def device_pixel_ratio(self):
        device_pixel_ratio = 1
        for w in self.get_quarter_widget(Gui.getMainWindow()):
            device_pixel_ratio = w.devicePixelRatio()
        return device_pixel_ratio

    def get_cursor_with_tail(self, base_icon_name, tail_icon_name=None):
        # Other cursor code in scr:
        # src/Gui/CommandView.cpp
        # src/Mod/Mesh/Gui/MeshSelection.cpp
        # src/Mod/Sketcher/Gui/CommandConstraints.cpp

        #   +--------+
        #   |  base  |          vertical offset = 0.5*w
        # w |        +--------+
        #   |   w    |  tail  |
        #   +--------+        | w = width = 16
        #            |   w    |
        #            +--------+

        dpr = self.device_pixel_ratio()
        width = 16 * dpr
        new_icon = QtGui.QPixmap(2 * width, 1.5 * width)
        new_icon.fill(QtCore.Qt.transparent)
        base_icon = QtGui.QPixmap(base_icon_name).scaledToWidth(width)
        qp = QtGui.QPainter()
        qp.begin(new_icon)
        qp.drawPixmap(0, 0, base_icon)
        if tail_icon_name is not None:
            tail_icon = QtGui.QPixmap(tail_icon_name).scaledToWidth(width)
            qp.drawPixmap(width, 0.5 * width, tail_icon)
        qp.end()
        new_icon.setDevicePixelRatio(dpr)
        return QtGui.QCursor(new_icon, 8, 8)

    def setCursor(self, mode=None):
        """Set the cursor to the given mode or unset it."""
        views = self.get_quarter_widget(Gui.getMainWindow())
        if self.selectMode or mode is None:
            self.cursorMode = None
            self.cursorQt = None
            for view in views:
                view.unsetCursor()
        elif self.cursorMode == mode and self.cursorQt is not None:
            for view in views:
                view.setCursor(self.cursorQt)
        else:
            self.cursorMode = mode
            self.cursorQt = self.get_cursor_with_tail(
                ":/icons/Draft_Cursor.svg", None if mode == "passive" else self.cursors[mode]
            )
            for view in views:
                view.setCursor(self.cursorQt)

    def restack(self):
        """Lower the grid tracker so it doesn't obscure other objects."""
        if self.grid:
            self.grid.lowerTracker()

    def setPointConstraintProvider(self, provider):
        """Set the active task panel that constrains snapped points."""
        self.pointConstraintProvider = provider

    def clearPointConstraintProvider(self, provider=None):
        """Clear the active provider if it matches ``provider``."""
        if provider is None or self.pointConstraintProvider is provider:
            self.pointConstraintProvider = None

    def _apply_point_constraint(self, point, lastpoint, noTracker):
        """Apply the active task panel's point constraints."""
        provider = self.pointConstraintProvider
        if provider is None:
            return point
        if hasattr(provider, "has_point_constraints") and not provider.has_point_constraints():
            return point
        locked = provider.constrain_point(point, lastpoint)
        if noTracker or locked is None:
            return locked
        if self.tracker:
            self.tracker.setCoords(locked)
            self.tracker.on()
        if self.trackLine and lastpoint:
            self.trackLine.p2(locked)
            self.trackLine.setColor()
            self.trackLine.on()
            self.setArchDims(lastpoint, locked)
        return locked

    def off(self):
        """Finish snapping."""
        if self.tracker:
            self.tracker.off()
        if self.trackLine:
            self.trackLine.off()
        if self.extLine:
            self.extLine.off()
        if self.extLine2:
            self.extLine2.off()
        if self.radiusTracker:
            self.radiusTracker.off()
        if self.dim1:
            self.dim1.off()
        if self.dim2:
            self.dim2.off()
        if self.holdTracker:
            self.holdTracker.clear()
            self.holdTracker.off()
        self.unconstrain()
        self.radius = 0
        self.setCursor()
        self.mask = None
        self.selectMode = False
        self.running = False
        self.interaction_plane = None
        self._point_plane_override_active = False
        self.holdPoints = []
        self.lastObj = []
        self.lastObjSubelements = []

        if hasattr(App, "activeDraftCommand") and App.activeDraftCommand:
            return
        if self.grid:
            if self.grid.show_always is False:
                self.grid.off()
        if params.get_param("SnapBarShowOnlyDuringCommands"):
            toolbar = self.get_snap_toolbar()
            if toolbar:
                toolbar.hide()

    def _clear_point_callbacks(self):
        """Remove the current point-picking callbacks, if any."""
        self._point_request_generation += 1
        callback_click = self.callbackClick
        callback_move = self.callbackMove
        had_callbacks = bool(callback_click or callback_move)
        view = getattr(self, "view", None) or gui_utils.get_3d_view()

        # Invalidate the Python closures immediately, but remove their Coin
        # callbacks only after the current event traversal has returned. Coin
        # callback lists must not be mutated by the callback being traversed.
        self.callbackClick = None
        self.callbackMove = None

        def remove_callbacks():
            try:
                if view and callback_click:
                    view.removeEventCallbackPivy(
                        coin.SoMouseButtonEvent.getClassTypeId(), callback_click
                    )
                if view and callback_move:
                    view.removeEventCallbackPivy(
                        coin.SoLocation2Event.getClassTypeId(), callback_move
                    )
                if had_callbacks:
                    # Next line fixes https://github.com/FreeCAD/FreeCAD/issues/10469:
                    gui_utils.end_all_events()
            except RuntimeError:
                # the view has been deleted already
                pass

        if had_callbacks:
            QtCore.QTimer.singleShot(0, remove_callbacks)

    def _teardown_point_request(self, hide_hints=False):
        """Finish the current point-picking request and restore the Draft UI."""
        self._clear_point_callbacks()
        self.off()
        self.pt = None
        self.interaction_plane = None
        toolbar = getattr(Gui, "draftToolBar", None)
        if toolbar:
            toolbar.offUi()
        if hide_hints:
            QtCore.QTimer.singleShot(0, Gui.HintManager.hide)

    def cancelPointRequest(self):
        """Cancel the current point-picking request and restore the Draft UI."""
        self._teardown_point_request()

    def setSelectMode(self, mode):
        """Set the snapper into select mode (hides snapping temporarily)."""
        self.selectMode = mode
        if not mode:
            self.setCursor()
        else:
            if self.trackLine:
                self.trackLine.off()

    def setAngle(self, delta=None):
        """Keep the current angle."""
        if delta:
            self.mask = delta
        elif isinstance(self.mask, App.Vector):
            self.mask = None
        elif self.trackLine:
            if self.trackLine.Visible:
                self.mask = self.trackLine.p2().sub(self.trackLine.p1())

    def constrain(self, point, basepoint=None, axis=None):
        """Return a constrained point.

        constrain(point,basepoint=None,axis=None: Returns a
        constrained point. Axis can be "x","y" or "z" or a custom vector. If None,
        the closest working plane axis will be picked.
        Basepoint is the base point used to figure out from where the point
        must be constrained. If no basepoint is given, the current point is
        used as basepoint.
        """
        point = App.Vector(point)

        # setup trackers if needed
        if not self.constrainLine:
            self.constrainLine = trackers.lineTracker(dotted=True)

        # setting basepoint
        if not basepoint:
            if not self.basepoint:
                self.basepoint = point
        else:
            self.basepoint = basepoint
        delta = point.sub(self.basepoint)

        if Gui.draftToolBar.globalMode:
            import WorkingPlane

            wp = WorkingPlane.PlaneBase()  # matches the global coordinate system
        else:
            wp = self._get_wp()

        # setting constraint axis
        if axis == "x":
            self.constraintAxis = wp.u
        elif axis == "y":
            self.constraintAxis = wp.v
        elif axis == "z":
            self.constraintAxis = wp.axis
        elif isinstance(axis, App.Vector):
            self.constraintAxis = axis
        else:
            if self.mask is not None:
                self.affinity = self.mask
            if self.affinity is None:
                self.affinity = wp.get_closest_axis(delta)
            if self.affinity == "x":
                self.constraintAxis = wp.u
            elif self.affinity == "y":
                self.constraintAxis = wp.v
            elif self.affinity == "z":
                self.constraintAxis = wp.axis
            elif isinstance(self.affinity, App.Vector):
                self.constraintAxis = self.affinity
            else:
                self.constraintAxis = None

        if self.constraintAxis is None:
            return point

        # calculating constrained point
        cdelta = DraftVecUtils.project(delta, self.constraintAxis)
        npoint = self.basepoint.add(cdelta)

        # setting constrain line
        if self.constrainLine:
            if point != npoint:
                self.constrainLine.p1(point)
                self.constrainLine.p2(npoint)
                self.constrainLine.on()
            else:
                self.constrainLine.off()

        return npoint

    def unconstrain(self):
        """Unset the basepoint and the constrain line."""
        self.basepoint = None
        self.affinity = None
        if self.constrainLine:
            self.constrainLine.off()

    def getPoint(
        self,
        last=None,
        callback=None,
        movecallback=None,
        extradlg=None,
        title=None,
        mode="point",
        hints=None,
        modifier_resolver=None,
        interaction_plane=None,
        noTracker=False,
        view=None,
    ):
        """Get a 3D point from the screen.

        getPoint([last],[callback],[movecallback],[extradlg],[title],[mode],[hints]):
        gets a 3D point from the screen. You can provide an existing point,
        in that case additional snap options and a tracker are available.
        You can also pass a function as callback, which will get called
        with the resulting point as argument, when a point is clicked,
        and optionally another callback which gets called when
        the mouse is moved.

        If the operation gets cancelled (the user pressed Escape),
        no point is returned.

        Example:

        def cb(point):
            if point:
                print "got a 3D point: ",point

        Gui.Snapper.getPoint(callback=cb)

        If the callback function accepts more than one argument,
        it will also receive the last snapped object. Finally, a qt widget
        can be passed as an extra taskbox.
        title is the title of the point task box mode is the dialog box
        you want (default is point, you can also use wire and line)
        If noTracker is True, the default snap rubber-band line is suppressed.

        If getPoint() is invoked without any argument, only the existing
        callbacks are cleared for backward compatibility. Prefer
        cancelPointRequest() for explicit teardown.

        ``hints`` is an optional list of ``Gui.InputHint`` instances to
        display in the status bar for the duration of the point pick. They are
        cleared automatically when the user picks a point or cancels.

        ``modifier_resolver`` is an optional callable that can override the
        Ctrl/Shift modifier state used for snapping and constraints.

        ``view`` optionally identifies the originating 3D viewport. When it
        is omitted, the active FreeCAD viewport is used for compatibility.
        """
        if (
            last is None
            and callback is None
            and movecallback is None
            and extradlg is None
            and title is None
            and mode == "point"
            and hints is None
            and modifier_resolver is None
        ):
            self._clear_point_callbacks()
            self.interaction_plane = None
            self._point_plane_override_active = False
            return

        origin_view = view if view is not None else gui_utils.get_3d_view()
        self._activate_context(origin_view)
        self.pt = None
        self.holdPoints = []
        self.interaction_plane = interaction_plane
        self._point_plane_override_active = interaction_plane is not None
        # Point requests should start from a clean constraint state. Otherwise
        # stale mask/affinity/basepoint values from a previous command can
        # distort the first preview frame of the next interactive request.
        self.unconstrain()
        self.mask = None
        self.constraintAxis = None
        self.ui = Gui.draftToolBar
        self.view = origin_view

        # remove any previous leftover callbacks
        self._clear_point_callbacks()
        request_generation = self._point_request_generation

        def move(event_cb):
            if request_generation != self._point_request_generation:
                return
            if not self.ui.mouse:
                return
            event = event_cb.getEvent()
            mousepos = event.getPosition()
            ctrl = event.wasCtrlDown()
            shift = event.wasShiftDown()
            alt = event.wasAltDown()
            if modifier_resolver:
                try:
                    ctrl, shift = modifier_resolver(ctrl, shift, alt)
                except Exception:
                    pass
            self.pt = Gui.Snapper.snap(
                mousepos,
                lastpoint=last,
                active=ctrl,
                constrain=shift,
                noTracker=noTracker,
                view=origin_view,
            )
            self.ui.displayPoint(self.pt, last, plane=self._get_wp(), mask=Gui.Snapper.affinity)
            if movecallback:
                movecallback(self.pt, self.snapInfo)

        def getcoords(point, global_mode=True, relative_mode=False):
            """Get the global coordinates from a point."""
            if request_generation != self._point_request_generation:
                return
            # Same algorithm as in validatePoint in DraftGui.py.
            ref = App.Vector(0, 0, 0)
            if global_mode is False:
                wp = self._get_wp()
                point = wp.get_global_coords(point, as_vector=True)
                ref = wp.get_global_coords(ref)
            if relative_mode is True and last is not None:
                ref = last
            self.pt = point + ref
            accept()

        def click(event_cb):
            if request_generation != self._point_request_generation:
                return
            if not self.ui.mouse:
                return

            event = event_cb.getEvent()
            if (
                event.getButton() == coin.SoMouseButtonEvent.BUTTON1
                and event.getState() == coin.SoButtonEvent.DOWN
            ):
                # The active Draft command owns this pointer interaction.
                # Prevent navigation styles from arming LMB box selection.
                event_cb.setHandled()
                accept()

        def accept():
            if request_generation != self._point_request_generation:
                return
            point = self.pt
            snap_info = dict(self.snapInfo) if isinstance(self.snapInfo, dict) else self.snapInfo
            self._teardown_point_request(hide_hints=bool(hints))
            if callback:
                if len(inspect.getfullargspec(callback).args) > 1:
                    obj = None
                    if snap_info and ("Object" in snap_info) and snap_info["Object"]:
                        obj = App.ActiveDocument.getObject(snap_info["Object"])
                    callback(point, obj)
                else:
                    callback(point)
            self.pt = None

        def cancel():
            if request_generation != self._point_request_generation:
                return
            self._teardown_point_request(hide_hints=bool(hints))
            if callback:
                if len(inspect.getfullargspec(callback).args) > 1:
                    callback(None, None)
                else:
                    callback(None)

        # adding callback functions
        if mode == "line":
            interface = self.ui.lineUi
        elif mode == "wire":
            interface = self.ui.wireUi
        else:
            interface = self.ui.pointUi
        if callback:
            if title:
                interface(
                    title=title, cancel=cancel, getcoords=getcoords, extra=extradlg, rel=bool(last)
                )
            else:
                interface(cancel=cancel, getcoords=getcoords, extra=extradlg, rel=bool(last))
            self.callbackClick = self.view.addEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(), click
            )
            self.callbackMove = self.view.addEventCallbackPivy(
                coin.SoLocation2Event.getClassTypeId(), move
            )
            self._schedule_hints(hints)

    def _schedule_hints(self, hints):
        """Show ``hints`` in the status bar after the task panel has opened."""
        if not hints:
            return

        def _show():
            Gui.HintManager.show(*hints)

        QtCore.QTimer.singleShot(0, _show)

    def get_snap_toolbar(self):
        """Get the snap toolbar."""
        if self.toolbar is None:
            mw = Gui.getMainWindow()
            self.toolbar = mw.findChild(QtWidgets.QToolBar, "Draft Snap")
        return self.toolbar

    def toggleGrid(self):
        """Toggle FreeCAD Draft Grid."""
        Gui.runCommand("Draft_ToggleGrid")

    def showradius(self):
        """Show the snap radius indicator."""
        self.radius = self.getScreenDist(params.get_param("snapRange"), (400, 300))
        if self.radiusTracker:
            self.radiusTracker.update(self.radius)
            self.radiusTracker.on()

    def hideRadius(self):
        """Hide the snap radius indicator."""
        if self.radiusTracker:
            self.radiusTracker.off()

    def isEnabled(self, snap):
        """Returns true if the given snap is on"""
        if "Lock" in self.active_snaps and snap in self.active_snaps:
            return True
        else:
            return False

    def toggle_snap(self, snap, set_to=None):
        """Sets the given snap on/off according to the given parameter"""
        if set_to is None:  # toggle mode, default
            if not snap in self.active_snaps:
                self.active_snaps.append(snap)
                status = True
            else:
                self.active_snaps.remove(snap)
                status = False
        elif set_to is True:
            if not snap in self.active_snaps:
                self.active_snaps.append(snap)
            status = True
        else:
            if snap in self.active_snaps:
                self.active_snaps.remove(snap)
            status = False
        self.save_snap_state()
        return status

    def save_snap_state(self):
        """
        Save snap state to user preferences to be restored in next session.
        """
        snap_modes = ""
        global_modes = self._global_active_snaps
        for snap in self.snaps:
            if snap in global_modes:
                snap_modes += "1"
            else:
                snap_modes += "0"
        params.set_param("snapModes", snap_modes)

    def show_hide_grids(self, show=True):
        """Show the grid in all 3D views where it was previously visible, or
        hide the grid in all 3D view. Used when switching to different workbenches.

        Hiding the grid can be prevented by setting the GridHideInOtherWorkbenches
        preference to `False`.
        """
        if (not show) and (not params.get_param("GridHideInOtherWorkbenches")):
            return
        mw = Gui.getMainWindow()
        views = mw.getWindowsOfType(
            App.Base.TypeId.fromName("Gui::View3DInventor")
        )  # All 3D views.
        for view in views:
            context = self._contexts.get(id(view))
            if context is None:
                for candidate in self._contexts.values():
                    try:
                        if candidate.view == view:
                            context = candidate
                            break
                    except Exception:
                        continue
            grid = context.trackers.grid if context is not None else None
            if grid is None:
                try:
                    grid = self.trackers[1][self.trackers[0].index(view)]
                except (ValueError, IndexError):
                    grid = None
            if grid is not None:
                if show and grid.show_always:
                    grid.on()
                else:
                    grid.off()

    def show(self):
        """Show the grid in all 3D views where it was previously visible."""
        self.show_hide_grids(show=True)

    def hide(self):
        """Hide the grid in all 3D views."""
        self.show_hide_grids(show=False)

    def setGrid(self):
        """Set the grid, if visible."""
        self.setTrackers()

    def setTrackers(self, update_grid=True, view=None):
        """Set the tracker bundle for one originating viewport."""
        v = view if view is not None else gui_utils.get_3d_view()
        if v is None:
            return

        context = self._activate_context(v)
        bundle = context.trackers
        if bundle.grid is None:
            doc_name = App.ActiveDocument.Name if App.ActiveDocument is not None else None
            bundle.grid = trackers.gridTracker(doc_name)
            if params.get_param("alwaysShowGrid"):
                bundle.grid.show_always = True
            if params.get_param("grid"):
                bundle.grid.show_during_command = True
            bundle.snap = trackers.snapTracker()
            bundle.track_line = trackers.lineTracker()
            bundle.extension = trackers.lineTracker(dotted=True)
            bundle.extension2 = trackers.lineTracker(dotted=True)
            bundle.radius = trackers.radiusTracker()
            bundle.dim1 = trackers.archDimTracker(mode=2)
            bundle.dim2 = trackers.archDimTracker(mode=3)
            bundle.hold = trackers.snapTracker()
            bundle.hold.setMarker("cross")
            bundle.hold.clear()
            # Keep the old parallel arrays populated for third-party code
            # that still inspects them; all internal lookup is context based.
            self.trackers[0].append(v)
            self.trackers[1].append(bundle.grid)
            self.trackers[2].append(bundle.snap)
            self.trackers[3].append(bundle.extension)
            self.trackers[4].append(bundle.radius)
            self.trackers[5].append(bundle.dim1)
            self.trackers[6].append(bundle.dim2)
            self.trackers[7].append(bundle.track_line)
            self.trackers[8].append(bundle.extension2)
            self.trackers[9].append(bundle.hold)

        self.grid = bundle.grid
        self.tracker = bundle.snap
        self.extLine = bundle.extension
        self.radiusTracker = bundle.radius
        self.dim1 = bundle.dim1
        self.dim2 = bundle.dim2
        self.trackLine = bundle.track_line
        self.extLine2 = bundle.extension2
        self.holdTracker = bundle.hold
        self.activeview = v

        self.hideRadius()

        if not update_grid:
            return

        if self.grid.show_always or (
            self.grid.show_during_command
            and hasattr(App, "activeDraftCommand")
            and App.activeDraftCommand
        ):
            self.grid.set()

    def addHoldPoint(self):
        """Add hold snap point to list of hold points."""
        if self.spoint and self.spoint not in self.holdPoints:
            if self.holdTracker:
                self.holdTracker.addCoords(self.spoint)
                self.holdTracker.setColor()
                self.holdTracker.on()
            self.holdPoints.append(self.spoint)

    def recenter_workingplane(self):
        """Recenters the working plane on the current snap position"""
        if self.spoint:
            self._get_wp().set_to_position(self.toWP(self.spoint))


## @}
