# SPDX-License-Identifier: LGPL-2.1-or-later

"""Session-owned selection API for BIM Plan Edit."""

from contextlib import contextmanager

from .common import _SessionAPI
from .interaction import (
    PlanSelectionActivationService,
    PlanSelectionHoverService,
    PlanSelectionTargetService,
)
from .state import (
    PlanSelectionRefreshService,
    PlanSelectionStateService,
    PlanSelectionSyncService,
)


class PlanSelectionAPI(_SessionAPI):
    """Owned session surface for BIM Plan Edit selection behavior."""

    def __init__(self, session):
        super().__init__(session)
        self.state = PlanSelectionStateService(session)
        self.refresh = PlanSelectionRefreshService(session)
        self.sync = PlanSelectionSyncService(session)
        self.targets = PlanSelectionTargetService(session)
        self.hover = PlanSelectionHoverService(session)
        self.activation = PlanSelectionActivationService(session)

    def addSelection(self, doc, obj, sub, point):
        return self.sync.selection_observer_add(doc, obj, sub, point)

    def removeSelection(self, doc, obj, sub):
        return self.sync.selection_observer_remove(doc, obj, sub)

    def setSelection(self, doc):
        return self.sync.selection_observer_set(doc)

    def clearSelection(self, doc):
        return self.sync.selection_observer_clear(doc)

    def clear_selected_visuals(self, *args, **kwargs):
        return self.refresh.clear_selected_visuals(*args, **kwargs)

    def discard_runtime_references(self):
        return self.state.discard_runtime_references()

    def setPreselection(self, doc, obj, sub):
        return self.sync.selection_observer_set_preselection(doc, obj, sub)

    def removePreselection(self, doc, obj, sub):
        return self.sync.selection_observer_remove_preselection(doc, obj, sub)

    @contextmanager
    def selection_changes_suppressed(self):
        with self.sync.selection_changes_suppressed():
            yield

    def get_selected_objects(self):
        return tuple(
            self.sync.normalize_gui_object_selection(
                tuple(self.sync.get_gui_selection())
                + tuple(self.session.provider_transient_state.provider_selected_objects)
            )
        )
