# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task-panel controls for BIM Plan Edit."""

import FreeCAD
from bimplan.ui.control_editors import PlanEditEditorPanelsMixin
from bimplan.ui.control_integrations import PlanEditIntegrationPanelMixin
from bimplan.ui.control_shell import PlanEditControlsShellMixin

translate = FreeCAD.Qt.translate


class PlanEditControlsWidget(
    PlanEditControlsShellMixin,
    PlanEditIntegrationPanelMixin,
    PlanEditEditorPanelsMixin,
):
    """Reusable session controls widget for Plan Edit mode."""

    _COMMON_SPACE_TYPES = (
        "Undefined",
        "Room",
        "Office",
        "Restrooms",
        "Corridor / Transition",
        "Lobby",
        "Dining Area",
        "Exterior",
        "Active Storage",
        "Electrical / Mechanical",
    )
    _INTEGRATION_REFRESH_DELAY_MS = 350

    def __init__(self, session):
        from PySide import QtGui

        self.session = session
        self._storey_items = []
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._refreshing_window_editor = False
        self._refreshing_space_editor = False
        self._refreshing_region_editor = False
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._window_editor_state = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self._status_text_state = None
        self._integration_panel_state = None
        self._integration_refresh_queued = False
        self._integration_refresh_generation = 0
        self._integration_action_buttons = []
        self._integration_overlay_checkboxes = []
        self._integration_overlay_block = None
        self._integration_overlay_mode_combo = None
        self._integration_overlay_content_layout = None
        self._modal_interaction_state = None
        self._region_parent_space_items = []
        self.header_mode_label = None
        self.status_group = None
        self.create_group = None
        self.modify_group = None
        self.view_group = None
        self.join_type_widget = None
        self.form = self._build_form(QtGui)
        try:
            self.form.setObjectName("BIMPlanEditContextControls")
        except Exception:
            pass

    @property
    def modal_focus_widgets(self):
        return tuple(self._modal_focus_widgets)
