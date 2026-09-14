# SPDX-License-Identifier: LGPL-2.1-or-later

"""Initial session state for BIM Plan Edit."""

from bimplan.representation_request import PlanRepresentationRequestAPI
from bimplan.contextual_rendering import PlanContextualRenderingAPI
from bimplan.object_visibility import PlanVisibilityAPI
from bimplan.picking import PlanPickingAPI
from bimplan.selection import PlanSelectionAPI
from bimplan.snap import PlanSnapAPI
from bimplan.contextual_editing import PlanContextualEditingAPI
from bimplan.overlays.runtime import PlanOverlaysAPI
from bimplan.runtime.session_state import initialize_plan_overlay_state
from bimplan.ui.status_text import PlanStatusTextAPI


_PLAN_EDIT_SNAP_SET = {
    "Lock",
    "Near",
    "Extension",
    "Endpoint",
    "Midpoint",
    "Perpendicular",
    "Ortho",
    "Intersection",
    "WorkingPlane",
}


class PlanEditSession:
    """Hold Plan's storey-scoped representation request."""

    def __init__(self, active_storey=None, doc=None, view=None):
        if doc is None:
            try:
                import FreeCAD

                doc = FreeCAD.ActiveDocument
            except Exception:
                doc = None
        if view is None:
            try:
                import FreeCADGui

                gui_document = FreeCADGui.ActiveDocument
                view = getattr(gui_document, "ActiveView", None)
            except Exception:
                view = None
        self.doc = doc
        self.view = view
        self.active_storey = None
        self.representation_request = PlanRepresentationRequestAPI(self)
        self.visibility = PlanVisibilityAPI(self)
        self.contextual_rendering = PlanContextualRenderingAPI(self)
        initialize_plan_overlay_state(self)
        self.overlays = PlanOverlaysAPI(self)
        self.picking = PlanPickingAPI(self)
        self.selection = PlanSelectionAPI(self)
        self.snap = PlanSnapAPI(self, _PLAN_EDIT_SNAP_SET)
        self.contextual_editing = PlanContextualEditingAPI(self)
        self.status_text = PlanStatusTextAPI(self)
        if active_storey is not None:
            self.set_source(active_storey, refresh=False)

    @property
    def request(self):
        return self.representation_request.request

    def set_source(self, source, *, refresh=True):
        request = self.representation_request.set_source(source, refresh=False)
        if refresh:
            self.contextual_rendering.refresh_all()
            self.visibility.apply_storey_visibility()
        return request

    def includes_object(self, obj):
        return self.representation_request.includes_object(obj)
