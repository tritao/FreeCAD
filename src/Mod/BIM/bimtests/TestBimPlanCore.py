# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import nullcontext
import unittest
import sys
import weakref
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

if "FreeCAD" not in sys.modules:
    try:
        import FreeCAD  # noqa: F401
    except ModuleNotFoundError:
        freecad_module = ModuleType("FreeCAD")
        freecad_module.Qt = SimpleNamespace(
            translate=lambda _context, text: text,
            QT_TRANSLATE_NOOP=lambda _context, text: text,
        )
        sys.modules["FreeCAD"] = freecad_module

if not hasattr(sys.modules["FreeCAD"], "Vector"):

    class _FakeVector:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            if hasattr(x, "x") and hasattr(x, "y"):
                self.x = float(x.x)
                self.y = float(x.y)
                self.z = float(getattr(x, "z", 0.0) or 0.0)
                return
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)

    sys.modules["FreeCAD"].Vector = _FakeVector

if "FreeCADGui" not in sys.modules:
    freecadgui_module = ModuleType("FreeCADGui")
    freecadgui_module.Snapper = SimpleNamespace(getPoint=lambda **_kwargs: None)
    sys.modules["FreeCADGui"] = freecadgui_module

if "draftguitools.gui_base" not in sys.modules:
    draftguitools_module = sys.modules.setdefault(
        "draftguitools",
        ModuleType("draftguitools"),
    )
    gui_base_module = ModuleType("draftguitools.gui_base")

    class _DraftInteractionHost:
        def __init__(self, command=None):
            self.command = command

        def activate_command(self, command=None):
            self.command = command or self.command

        def deactivate_command(self, command=None):
            self.command = command or self.command

        def request_point(self, **kwargs):
            del kwargs
            return None

    gui_base_module.DraftInteractionHost = _DraftInteractionHost
    sys.modules["draftguitools.gui_base"] = gui_base_module
    draftguitools_module.gui_base = gui_base_module

from bimplan.providers import PlanEditContext, PlanProviderActionContext
from bimplan.runtime.lifecycle import (
    activate_plan_region_tool,
    activate_select_tool,
    activate_space_separator_tool,
    begin_teardown,
    finish,
    shutdown,
)
from bimplan.overlays import providers as provider_overlays
from bimplan.selection.picking import (
    get_hovered_plan_target,
    get_plan_target_at_position,
    get_provider_overlay_target_from_edit_node,
    pick_provider_overlay_target_from_objects_info,
    pick_provider_overlay_target_from_overlays,
)
from bimplan.providers.runtime import (
    collect_plan_provider_contributions,
    get_plan_provider_target_for_object,
    normalize_plan_provider_overlay,
)
from bimplan.providers.runtime import PlanProviderSnapshot, collect_plan_provider_snapshot
from bimplan.providers import (
    PlanActionSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditProvider,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlaySpec,
    PlanOverlayMarkerKind,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanProviderTargetSpec,
    PlanToolSpec,
)
from bimplan.providers import PlanEditRegistry
from bimplan.semantics import PlanSemanticRecord
from bimplan.selection import (
    activate_opening_target,
    activate_semantic_plan_target,
    resolve_selected_target_for_gui_object,
)
from bimplan.tools.spaces import (
    begin_space_region_pick,
    create_space_from_current_selection,
    get_space_creation_request,
    get_space_region_seed_targets,
    should_run_space_preflight_for_targets,
)
from bimplan.selection.target_dispatch import (
    queue_restore_selected_target,
    set_hovered_target,
    validate_plan_target,
)
from bimplan.selection.targets import (
    PlanTarget,
    get_plan_target_for_object,
    make_plan_target_record,
)
from bimplan.transactions import PlanEditTransaction
from bimplan.ui.controls import PlanEditControlsWidget
from bimplan.task_panel_view_model import (
    build_action_context_view_model,
    build_integration_panel_view_model,
    build_region_editor_view_model,
    build_space_editor_view_model,
    build_status_text_view_model,
    build_window_editor_view_model,
    filter_provider_overlay_legend_items_for_mode,
)


def _make_perf_stub(
    *,
    trace_span=None,
    trace_event=None,
    count=None,
    set_fields=None,
    describe_object=None,
    describe_target=None,
    pick_debug_scope=None,
    pick_debug_event=None,
):
    return SimpleNamespace(
        plan_perf_trace_span=trace_span or (lambda *_args, **_kwargs: nullcontext()),
        plan_perf_trace_event=trace_event or (lambda *_args, **_kwargs: nullcontext()),
        plan_perf_count=count or (lambda *_args, **_kwargs: None),
        plan_perf_set_fields=set_fields or (lambda **_kwargs: None),
        plan_perf_describe_object=describe_object or (lambda obj: getattr(obj, "Name", None)),
        plan_perf_describe_target=describe_target
        or (lambda kind, obj: (kind, getattr(obj, "Name", None))),
        plan_pick_debug_scope=pick_debug_scope or (lambda *_args, **_kwargs: nullcontext()),
        plan_pick_debug_event=pick_debug_event or (lambda *_args, **_kwargs: None),
        is_plan_pick_debug_active=lambda: False,
    )


class _DummySession:
    def __init__(
        self,
        selected_targets=None,
        all_targets=None,
        semantic_records=None,
        selected_objects=None,
    ):
        self.selected_targets = tuple(selected_targets or ())
        self.all_targets = tuple(all_targets or self.selected_targets)
        self.semantic_records = tuple(semantic_records or ())
        self.selected_objects = tuple(selected_objects or ())
        self.visibility = SimpleNamespace(get_plan_semantic_object=lambda obj: f"semantic:{obj}")

    def get_plan_targets(self, selected_only=False):
        if selected_only:
            return self.selected_targets
        return self.all_targets

    def get_plan_semantic_records(self, targets=None):
        del targets
        return self.semantic_records

    def get_selected_objects(self):
        return self.selected_objects

    def resolve_plan_target_object(self, target):
        return f"target:{target.object_name}"

    def resolve_plan_semantic_object(self, target):
        return f"semantic:{target.semantic_object_name}"


class _DummyDoc:
    def __init__(self):
        self.events = []

    def openTransaction(self, label):
        self.events.append(("open", label))

    def commitTransaction(self):
        self.events.append(("commit", None))

    def abortTransaction(self):
        self.events.append(("abort", None))

    def recompute(self):
        self.events.append(("recompute", None))


class _DummyProvider(PlanEditProvider):
    def __init__(self, provider_id):
        self.provider_id = provider_id


class _SnapshotProvider(PlanEditProvider):
    provider_id = "snapshot-provider"

    def __init__(self):
        self.calls = []
        self.context_ids = []

    def _record_call(self, name, context):
        self.calls.append(name)
        self.context_ids.append(id(context))

    def get_tools(self, context):
        self._record_call("get_tools", context)
        return (PlanToolSpec(key="provider-tool", label="Provider Tool"),)

    def get_overlays(self, context):
        self._record_call("get_overlays", context)
        return (
            PlanOverlaySpec(
                key="provider-overlay",
                label="Provider Overlay",
                points=((1.0, 2.0, 0.0),),
            ),
        )

    def get_issues(self, context):
        self._record_call("get_issues", context)
        return (
            PlanIssueSpec(
                key="provider-issue",
                title="Provider Issue",
                severity=PlanIssueSeverity.WARNING,
            ),
        )

    def get_context_panels(self, context):
        self._record_call("get_context_panels", context)
        return (
            PlanContextPanelSpec(
                key="provider-context",
                title="Provider Context",
                state=PlanContextPanelState.SINGLE_OBJECT,
                subject_kind=PlanContextSubjectKind.SCOPE,
                summary_rows=(PlanContextRowSpec(label="State", value="Ready"),),
            ),
        )

    def get_inspector_sections(self, context):
        self._record_call("get_inspector_sections", context)
        return (
            PlanInspectorSection(
                key="provider-section",
                title="Provider Section",
            ),
        )


class TestBimPlanCore(unittest.TestCase):
    def test_initialize_session_read_state_creates_typed_buckets(self):
        from bimplan.runtime import session_state as plan_session_state
        from bimplan.runtime.session_state import (
            PlanInteractionState,
            PlanProviderOverlayReadState,
            PlanSelectionState,
            PlanTaskPanelState,
            PlanWallEditState,
        )

        session = SimpleNamespace()

        plan_session_state.initialize_session_read_state(session)

        self.assertIsInstance(session.task_panel_state, PlanTaskPanelState)
        self.assertIsInstance(session.provider_overlay_read_state, PlanProviderOverlayReadState)
        self.assertIsInstance(session.interaction_state, PlanInteractionState)
        self.assertIsInstance(session.selection_state, PlanSelectionState)
        self.assertIsInstance(session.wall_edit_state, PlanWallEditState)
        self.assertEqual([], session.task_panel_state.space_region_candidates)
        self.assertEqual("architecture", session.provider_overlay_read_state.mode)
        self.assertEqual({}, session.provider_overlay_read_state.visibility)
        self.assertIsNone(session.interaction_state.embedded_tool)
        self.assertIsNone(session.selection_state.selected_plan_target_kind)
        self.assertEqual([], session.selection_state.secondary_selected_plan_targets_state)
        self.assertFalse(session.wall_edit_state.wall_edit_modal_active)
        self.assertEqual({}, session.wall_edit_state.wall_edit_opening_clearances)

    def test_plan_edit_session_read_state_properties_bridge_typed_buckets(self):
        from bimplan.runtime.session import PlanEditSession
        from bimplan.runtime.session_state import (
            PlanInteractionState,
            PlanProviderOverlayReadState,
            PlanSelectionState,
            PlanTaskPanelState,
            PlanWallEditState,
        )

        session = object.__new__(PlanEditSession)
        session.task_panel_state = PlanTaskPanelState()
        session.provider_overlay_read_state = PlanProviderOverlayReadState()
        session.interaction_state = PlanInteractionState()
        session.selection_state = PlanSelectionState()
        session.wall_edit_state = PlanWallEditState()

        candidate = {"area": 12.0}
        parent_space = SimpleNamespace(Name="Space001")
        render_state = object()
        embedded_tool = object()
        provider_point_tool = object()
        hovered_wall = SimpleNamespace(Name="Wall001")
        secondary_targets = [("space", parent_space)]
        preview_tracker = object()
        readout_tracker = object()

        session._plan_relation_status_message = "Relation status"
        session._space_region_candidates = (candidate,)
        session._hovered_space_region_candidate = candidate
        session._plan_region_parent_space = parent_space
        session._provider_overlay_mode = "electrical"
        session._provider_overlay_visibility = {("provider", "overlay"): False}
        session._provider_overlay_state = render_state
        session._embedded_tool_name = "Move"
        session._embedded_tool = embedded_tool
        session._provider_point_tool = provider_point_tool
        session._edit_space = parent_space
        session._selected_plan_target_kind = "wall"
        session._selected_plan_target_obj = hovered_wall
        session.hovered_wall = hovered_wall
        session._pending_selected_plan_target = ("space", parent_space)
        session._secondary_selected_plan_targets_state = secondary_targets
        session._wall_edit_modal_active = True
        session._edit_wall = hovered_wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = ("start", "end")
        session._wall_edit_opening_clearances = {"Opening001": {"left_clearance": 100.0}}
        session._wall_edit_opening_clearances_queued = True
        session._wall_edit_task_panel_refresh_queued = True
        session._preview_points = ("preview-a", "preview-b")
        session._preview_line_tracker = preview_tracker
        session._preview_footprint_trackers = (preview_tracker,)
        session._preview_grip_trackers = (preview_tracker,)
        session._wall_edit_readout_trackers = (readout_tracker,)
        session._wall_edit_opening_preview_trackers = (preview_tracker,)
        session._wall_edit_active_readout_tracker = readout_tracker
        session._wall_edit_active_readout_mode = 1
        session._wall_edit_length_edit_queued = True
        session._edit_wall_visibility = False

        self.assertEqual("Relation status", session.task_panel_state.relation_status_message)
        self.assertEqual([candidate], session.task_panel_state.space_region_candidates)
        self.assertIs(candidate, session.task_panel_state.hovered_space_region_candidate)
        self.assertIs(parent_space, session.task_panel_state.plan_region_parent_space)
        self.assertEqual("electrical", session.provider_overlay_read_state.mode)
        self.assertEqual(
            {("provider", "overlay"): False},
            session.provider_overlay_read_state.visibility,
        )
        self.assertIs(render_state, session.provider_overlay_read_state.render_state)
        self.assertEqual("Move", session.interaction_state.embedded_tool_name)
        self.assertIs(embedded_tool, session.interaction_state.embedded_tool)
        self.assertIs(provider_point_tool, session.interaction_state.provider_point_tool)
        self.assertIs(parent_space, session.interaction_state.edit_space)
        self.assertEqual("wall", session.selection_state.selected_plan_target_kind)
        self.assertIs(hovered_wall, session.selection_state.selected_plan_target_obj)
        self.assertIs(hovered_wall, session.selection_state.hovered_wall)
        self.assertEqual(
            ("space", parent_space), session.selection_state.pending_selected_plan_target
        )
        self.assertEqual(
            secondary_targets, session.selection_state.secondary_selected_plan_targets_state
        )
        self.assertTrue(session.wall_edit_state.wall_edit_modal_active)
        self.assertIs(hovered_wall, session.wall_edit_state.edit_wall)
        self.assertEqual("Move", session.wall_edit_state.edit_endpoint)
        self.assertEqual(("start", "end"), session.wall_edit_state.edit_endpoints)
        self.assertEqual(
            {"Opening001": {"left_clearance": 100.0}},
            session.wall_edit_state.wall_edit_opening_clearances,
        )
        self.assertTrue(session.wall_edit_state.wall_edit_opening_clearances_queued)
        self.assertTrue(session.wall_edit_state.wall_edit_task_panel_refresh_queued)
        self.assertEqual(("preview-a", "preview-b"), session.wall_edit_state.preview_points)
        self.assertIs(preview_tracker, session.wall_edit_state.preview_line_tracker)
        self.assertEqual([preview_tracker], session.wall_edit_state.preview_footprint_trackers)
        self.assertEqual([preview_tracker], session.wall_edit_state.preview_grip_trackers)
        self.assertEqual([readout_tracker], session.wall_edit_state.wall_edit_readout_trackers)
        self.assertEqual(
            [preview_tracker],
            session.wall_edit_state.wall_edit_opening_preview_trackers,
        )
        self.assertIs(readout_tracker, session.wall_edit_state.wall_edit_active_readout_tracker)
        self.assertEqual(1, session.wall_edit_state.wall_edit_active_readout_mode)
        self.assertTrue(session.wall_edit_state.wall_edit_length_edit_queued)
        self.assertFalse(session.wall_edit_state.edit_wall_visibility)

    def test_plan_edit_session_owns_selection_spaces_relations_interaction_symbols_windows_viewport_wall_provider_and_status_components(
        self,
    ):
        from bimplan.runtime.session import PlanEditSession
        from bimplan.runtime.session_components import (
            PlanInteractionAPI,
            PlanProvidersAPI,
            PlanWallRelationsAPI,
            PlanSelectionAPI,
            PlanSpacesAPI,
            PlanStatusTextAPI,
            PlanSymbolsAPI,
            PlanViewportAPI,
            PlanWallEditAPI,
            PlanWindowsAPI,
        )

        with patch("bimplan.session.plan_session_state.initialize_session_state"):
            session = PlanEditSession()

        self.assertIsInstance(session.selection, PlanSelectionAPI)
        self.assertIs(session.selection.session, session)
        self.assertIsInstance(session.spaces, PlanSpacesAPI)
        self.assertIs(session.spaces.session, session)
        self.assertIsInstance(session.wall_relations, PlanWallRelationsAPI)
        self.assertIs(session.wall_relations.session, session)
        self.assertIsInstance(session.interaction, PlanInteractionAPI)
        self.assertIs(session.interaction.session, session)
        self.assertIsInstance(session.symbols, PlanSymbolsAPI)
        self.assertIs(session.symbols.session, session)
        self.assertIsInstance(session.windows, PlanWindowsAPI)
        self.assertIs(session.windows.session, session)
        self.assertIsInstance(session.viewport, PlanViewportAPI)
        self.assertIs(session.viewport.session, session)
        self.assertIsInstance(session.wall_edit, PlanWallEditAPI)
        self.assertIs(session.wall_edit.session, session)
        self.assertIsInstance(session.providers, PlanProvidersAPI)
        self.assertIs(session.providers.session, session)
        self.assertIsInstance(session.status_text, PlanStatusTextAPI)
        self.assertIs(session.status_text.session, session)

    def test_plan_edit_session_wrappers_delegate_to_owned_components(self):
        from bimplan.runtime.session import PlanEditSession
        from bimplan.runtime.session_components import (
            PlanInteractionAPI,
            PlanProvidersAPI,
            PlanWallRelationsAPI,
            PlanSelectionAPI,
            PlanSpacesAPI,
            PlanStatusTextAPI,
            PlanSymbolsAPI,
            PlanViewportAPI,
            PlanWallEditAPI,
            PlanWindowsAPI,
        )

        wall = SimpleNamespace(Name="Wall001")
        targets = [("wall", wall)]
        joint = SimpleNamespace(JointType="Miter")

        with patch("bimplan.session.plan_session_state.initialize_session_state"):
            session = PlanEditSession()

        with patch.object(
            PlanSelectionAPI,
            "get_selected_target_for_kind",
            autospec=True,
            return_value=wall,
        ) as get_selected_target_for_kind, patch.object(
            PlanSpacesAPI,
            "get_space_preflight_report",
            autospec=True,
            return_value={"ready": True},
        ) as get_space_preflight_report, patch.object(
            PlanStatusTextAPI,
            "get_status_chip_text",
            autospec=True,
            return_value=("Plan Edit", "Select\nWork directly in the viewport"),
        ) as get_status_chip_text, patch.object(
            PlanViewportAPI,
            "get_plan_view_height",
            autospec=True,
            return_value=4200.0,
        ) as get_plan_view_height, patch.object(
            PlanInteractionAPI,
            "is_modal_plan_interaction_active",
            autospec=True,
            return_value=True,
        ) as is_modal_plan_interaction_active, patch.object(
            PlanSymbolsAPI,
            "symbol_rotation_snap_enabled",
            autospec=True,
            return_value=True,
        ) as symbol_rotation_snap_enabled, patch.object(
            PlanSymbolsAPI,
            "format_symbol_rotation_snap_label",
            autospec=True,
            return_value="15°",
        ) as format_symbol_rotation_snap_label, patch.object(
            PlanWallRelationsAPI,
            "get_plan_join_type_label",
            autospec=True,
            return_value="Miter",
        ) as get_plan_join_type_label, patch.object(
            PlanWallRelationsAPI,
            "get_plan_candidate_joint",
            autospec=True,
            return_value=joint,
        ) as get_plan_candidate_joint, patch.object(
            PlanWindowsAPI,
            "can_place_window",
            autospec=True,
            return_value=True,
        ) as can_place_window, patch.object(
            PlanWindowsAPI,
            "get_selected_window_style_preset",
            autospec=True,
            return_value="Preset A",
        ) as get_selected_window_style_preset, patch.object(
            PlanProvidersAPI,
            "get_plan_provider_display_name",
            autospec=True,
            return_value="Provider A",
        ) as get_plan_provider_display_name, patch.object(
            PlanWallEditAPI,
            "has_active_wall_edit",
            autospec=True,
            return_value=True,
        ) as has_active_wall_edit, patch.object(
            PlanWallEditAPI,
            "clip_preview_polygon_to_plane",
            return_value=("clipped",),
        ) as clip_preview_polygon_to_plane:
            self.assertIs(wall, session.selection.get_selected_target_for_kind("wall"))
            self.assertEqual(
                {"ready": True},
                session.spaces.get_space_preflight_report(targets=targets),
            )
            self.assertTrue(session.windows.can_place_window())
            self.assertTrue(session.interaction.is_modal_plan_interaction_active())
            self.assertTrue(session.symbols.symbol_rotation_snap_enabled())
            self.assertEqual("15°", session.symbols.format_symbol_rotation_snap_label())
            self.assertEqual("Miter", session.wall_relations.get_plan_join_type_label())
            self.assertIs(joint, session.wall_relations.get_plan_candidate_joint())
            self.assertEqual(4200.0, session.viewport.get_plan_view_height())
            self.assertTrue(session.wall_edit.has_active_wall_edit())
            self.assertEqual(
                ("Plan Edit", "Select\nWork directly in the viewport"),
                session.status_text.get_status_chip_text(),
            )
            self.assertEqual("Preset A", session.windows.get_selected_window_style_preset())
            self.assertEqual(
                "Provider A",
                session.providers.get_plan_provider_display_name("provider-a"),
            )
            self.assertEqual(
                ("clipped",),
                session.wall_edit.clip_preview_polygon_to_plane("polygon", "plane", "ref"),
            )

        get_selected_target_for_kind.assert_called_once_with(session.selection, "wall")
        get_space_preflight_report.assert_called_once_with(session.spaces, targets=targets)
        get_status_chip_text.assert_called_once_with(session.status_text)
        get_plan_view_height.assert_called_once_with(session.viewport)
        is_modal_plan_interaction_active.assert_called_once_with(session.interaction)
        symbol_rotation_snap_enabled.assert_called_once_with(session.symbols)
        format_symbol_rotation_snap_label.assert_called_once_with(session.symbols)
        get_plan_join_type_label.assert_called_once_with(session.wall_relations, join_type=None)
        get_plan_candidate_joint.assert_called_once_with(session.wall_relations, target_wall=None)
        can_place_window.assert_called_once_with(session.windows)
        get_selected_window_style_preset.assert_called_once_with(session.windows)
        get_plan_provider_display_name.assert_called_once_with(
            session.providers,
            "provider-a",
        )
        has_active_wall_edit.assert_called_once_with(session.wall_edit)
        clip_preview_polygon_to_plane.assert_called_once_with(
            "polygon",
            "plane",
            "ref",
            tol=1e-7,
        )

    def test_collect_plan_provider_snapshot_builds_panel_surfaces_in_one_pass(self):
        registry = PlanEditRegistry()
        provider = _SnapshotProvider()
        registry.register_provider(provider)

        context_calls = []
        context = SimpleNamespace(name="snapshot-context")
        perf_counts = []

        def _get_plan_edit_context():
            context_calls.append("context")
            return context

        session = SimpleNamespace(
            _plan_provider_refresh_cache={},
            performance=_make_perf_stub(
                trace_span=lambda _name: nullcontext(),
                count=lambda name, value=1: perf_counts.append((name, value)),
            ),
            get_plan_provider_registry=lambda: registry,
        )
        session.document_visuals = SimpleNamespace(document_is_alive=lambda: True)
        session.providers = SimpleNamespace(
            get_plan_edit_context=_get_plan_edit_context,
            plan_provider_integrations_disabled=lambda: False,
            get_plan_provider_id=lambda current_provider: current_provider.get_provider_id(),
            coerce_plan_provider_results=lambda provided: tuple(provided or ()),
            normalize_plan_provider_tool=lambda provider_id, tool: tool.__class__(
                **{**tool.__dict__, "provider_id": provider_id}
            ),
            normalize_plan_provider_overlay=lambda provider_id, overlay: normalize_plan_provider_overlay(
                provider_id,
                overlay,
            ),
            normalize_plan_provider_issue=lambda provider_id, issue: issue.__class__(
                **{**issue.__dict__, "provider_id": provider_id}
            ),
            normalize_plan_provider_context_panel=lambda provider_id, panel: panel.__class__(
                **{**panel.__dict__, "provider_id": provider_id}
            ),
            normalize_plan_provider_section=lambda provider_id, section: section.__class__(
                **{**section.__dict__, "provider_id": provider_id}
            ),
        )

        snapshot = collect_plan_provider_snapshot(session)

        self.assertEqual(["context"], context_calls)
        self.assertEqual(
            [
                "get_tools",
                "get_overlays",
                "get_issues",
                "get_context_panels",
                "get_inspector_sections",
            ],
            provider.calls,
        )
        self.assertEqual({id(context)}, set(provider.context_ids))
        self.assertEqual("snapshot-provider", snapshot.tools[0].provider_id)
        self.assertEqual("snapshot-provider", snapshot.overlays[0].provider_id)
        self.assertEqual("snapshot-provider", snapshot.issues[0].provider_id)
        self.assertEqual("snapshot-provider", snapshot.context_panels[0].provider_id)
        self.assertEqual("snapshot-provider", snapshot.inspector_sections[0].provider_id)
        self.assertEqual(
            snapshot.tools,
            collect_plan_provider_contributions(
                session,
                "get_tools",
                session.providers.normalize_plan_provider_tool,
            ),
        )
        self.assertEqual(1, provider.calls.count("get_tools"))
        self.assertIs(snapshot, collect_plan_provider_snapshot(session))

    def test_build_integration_panel_view_model_derives_panel_state(self):
        summary_action = PlanActionSpec(
            key="summary-action",
            label="Summary Action",
            provider_id="provider-a",
        )
        context_action = PlanActionSpec(
            key="context-action",
            label="Context Action",
            provider_id="provider-a",
            enabled=True,
        )
        snapshot = PlanProviderSnapshot(
            tools=(
                PlanToolSpec(
                    key="tool-b",
                    label="Tool B",
                    provider_id="provider-a",
                    group="z",
                    priority=20,
                ),
                PlanToolSpec(
                    key="tool-a",
                    label="Tool A",
                    provider_id="provider-a",
                    group="a",
                    priority=10,
                ),
            ),
            overlays=(
                PlanOverlaySpec(
                    key="arch-overlay",
                    label="Arch Overlay",
                    provider_id="provider-a",
                    category="architecture",
                    color=(1.0, 0.0, 0.0),
                ),
                PlanOverlaySpec(
                    key="elec-overlay",
                    label="Elec Overlay",
                    provider_id="provider-a",
                    category="electrical",
                    color=(0.0, 1.0, 0.0),
                ),
            ),
            issues=(
                PlanIssueSpec(
                    key="issue-a",
                    title="Issue A",
                    provider_id="provider-a",
                    group_key="workflow",
                    actions=(summary_action,),
                ),
                PlanIssueSpec(
                    key="issue-b",
                    title="Issue B",
                    provider_id="provider-a",
                    group_key="workflow",
                ),
            ),
            context_panels=(
                PlanContextPanelSpec(
                    key="empty-panel",
                    title="Empty",
                    state=PlanContextPanelState.EMPTY,
                    subject_kind=PlanContextSubjectKind.SCOPE,
                ),
                PlanContextPanelSpec(
                    key="selection-panel",
                    title="Selection",
                    provider_id="provider-a",
                    state=PlanContextPanelState.SINGLE_OBJECT,
                    subject_kind=PlanContextSubjectKind.ENDPOINT,
                    primary_action=context_action,
                ),
            ),
            inspector_sections=(
                PlanInspectorSection(
                    key="summary-section",
                    title="Summary",
                    provider_id="provider-a",
                    role="summary",
                    actions=(summary_action,),
                ),
                PlanInspectorSection(
                    key="detail-section",
                    title="Detail",
                    provider_id="provider-a",
                ),
                PlanInspectorSection(
                    key="notes-section",
                    title="Notes",
                    provider_id="provider-a",
                    role="details",
                ),
            ),
        )
        session = SimpleNamespace(
            get_plan_provider_overlay_mode=lambda: "electrical",
            get_plan_provider_display_name=lambda provider_id: (
                "Provider A" if provider_id == "provider-a" else provider_id
            ),
            get_plan_provider_overlay_category=lambda overlay: str(
                getattr(overlay, "category", "") or "architecture"
            ),
            is_plan_provider_overlay_enabled=lambda overlay: overlay.key != "arch-overlay",
        )

        view_model = build_integration_panel_view_model(session, snapshot)

        self.assertTrue(view_model.has_content)
        self.assertEqual(("tool-a", "tool-b"), tuple(tool.key for tool in view_model.tools))
        self.assertEqual("electrical", view_model.overlay_mode)
        self.assertEqual(
            ("elec-overlay",), tuple(item[1] for item in view_model.active_overlay_items)
        )
        self.assertEqual(1, len(view_model.grouped_issue_sets))
        self.assertEqual(
            ("summary-section",), tuple(section.key for section in view_model.summary_sections)
        )
        self.assertEqual(
            ("detail-section",), tuple(section.key for section in view_model.regular_sections)
        )
        self.assertEqual(
            ("notes-section",), tuple(section.key for section in view_model.detail_sections)
        )
        self.assertEqual("selection-panel", view_model.context_panel.key)
        self.assertEqual("Selection", view_model.context_panel_heading)
        self.assertEqual((context_action,), view_model.context_panel_actions)
        self.assertEqual(
            (("provider-a", "summary-action", "Summary Action"),),
            view_model.promoted_action_ids,
        )
        self.assertEqual(("Summary Action", "Context Action"), view_model.hidden_tool_action_labels)
        self.assertEqual("", view_model.summary_text)

    def test_build_action_context_view_model_derives_tool_controls(self):
        wall = SimpleNamespace(Name="Wall001")
        selection = SimpleNamespace(get_selected_plan_target=lambda: ("wall", wall))
        windows = SimpleNamespace(can_place_window=lambda: True)
        wall_relations = SimpleNamespace(get_plan_candidate_joint=lambda target_wall=None: object())
        providers = SimpleNamespace(get_provider_point_tool_label=lambda: "Provider Point")
        interaction = SimpleNamespace(is_modal_plan_interaction_active=lambda: False)
        session = SimpleNamespace(
            current_tool="Join",
            selection=selection,
            windows=windows,
            wall_relations=wall_relations,
            providers=providers,
            interaction=interaction,
        )

        view_model = build_action_context_view_model(session)

        self.assertEqual("Join", view_model.mode_label)
        self.assertTrue(view_model.show_join_options)
        self.assertTrue(view_model.join_button_enabled)
        self.assertTrue(view_model.join_type_enabled)
        self.assertTrue(view_model.unjoin_button_enabled)
        self.assertTrue(view_model.show_window_button)
        self.assertTrue(view_model.window_button_enabled)

    def test_build_status_text_view_model_derives_wall_guidance(self):
        wall = SimpleNamespace(Name="Wall001", Label="Wall 001")
        selection = SimpleNamespace(
            get_selected_plan_target=lambda: ("wall", wall),
            get_selected_plan_targets=lambda: (("wall", wall),),
        )
        status_text = SimpleNamespace(
            format_plan_target_selection_state=lambda kind, obj: f"{kind}:{obj.Label}",
            format_provider_selected_object_state=lambda: "",
            get_plan_selection_summary_text=lambda: "1 target selected",
        )
        wall_edit = SimpleNamespace(is_selected_wall_endpoint_editable=lambda: True)
        wall_relations = SimpleNamespace(get_plan_relation_status_message=lambda: "Relation status")
        session = SimpleNamespace(
            current_tool="Select",
            selection=selection,
            status_text=status_text,
            wall_edit=wall_edit,
            wall_relations=wall_relations,
        )

        view_model = build_status_text_view_model(session)

        self.assertIn("wall:Wall 001", view_model.text)
        self.assertIn("Use wall grips in the viewport", view_model.text)
        self.assertIn("Ctrl-click adds or removes targets", view_model.text)
        self.assertIn("Relation status", view_model.text)

    def test_build_space_and_region_editor_view_models_follow_selection(self):
        space = SimpleNamespace(Name="Space001")
        region = SimpleNamespace(Name="Region001")

        space_session = SimpleNamespace(
            current_tool="Set Space Text",
            selection=SimpleNamespace(get_selected_plan_target=lambda: ("space", space)),
        )
        region_session = SimpleNamespace(
            current_tool="Select",
            selection=SimpleNamespace(get_selected_plan_target=lambda: ("region", region)),
        )

        space_view_model = build_space_editor_view_model(space_session)
        region_view_model = build_region_editor_view_model(region_session)

        self.assertTrue(space_view_model.show_editor)
        self.assertIs(space, space_view_model.space)
        self.assertTrue(region_view_model.show_editor)
        self.assertIs(region, region_view_model.region)

    def test_build_window_editor_view_model_derives_editor_state(self):
        window = SimpleNamespace(Name="Window001", Document=SimpleNamespace(Name="Doc"))
        session = SimpleNamespace(
            current_tool="Select",
            selection=SimpleNamespace(get_selected_plan_target=lambda: ("opening", window)),
            windows=SimpleNamespace(
                can_edit_window_width=lambda obj: obj is window,
                can_edit_window_height=lambda obj: False,
                can_apply_window_style_preset=lambda obj: obj is window,
                get_selected_window_style_preset=lambda: "Preset A",
                get_selected_window_width_text=lambda: "1200 mm",
                get_selected_window_height_text=lambda: "1500 mm",
                get_window_style_preset_options=lambda: ("Preset A", "Preset B"),
            ),
        )

        view_model = build_window_editor_view_model(session)

        self.assertTrue(view_model.show_editor)
        self.assertIs(window, view_model.window)
        self.assertEqual(("Doc", "Window001"), view_model.state_key[0])
        self.assertEqual(
            (("Preset A", "Preset A"), ("Preset B", "Preset B")), view_model.combo_items
        )
        self.assertEqual("Preset A", view_model.current_style)
        self.assertEqual("1200 mm", view_model.current_width_text)
        self.assertEqual("1500 mm", view_model.current_height_text)
        self.assertTrue(view_model.can_edit_width)
        self.assertFalse(view_model.can_edit_height)
        self.assertTrue(view_model.can_apply_style)
        self.assertIn("Current style: Preset A", view_model.note_text)

    def test_task_panel_context_uses_selection_access_fallback(self):
        from bimplan.task_panel_view_model import PlanTaskPanelContext

        wall = SimpleNamespace(Name="Wall001")
        session = SimpleNamespace(
            _get_selected_plan_target=lambda: ("wall", wall),
            _get_selected_plan_targets=lambda: (("wall", wall),),
        )

        context = PlanTaskPanelContext(session)

        self.assertEqual(("wall", wall), context.get_selected_plan_target())
        self.assertEqual((("wall", wall),), context.get_selected_plan_targets())

    def test_as_task_panel_context_preserves_context_like_objects(self):
        from bimplan.task_panel_view_model import as_task_panel_context

        context = SimpleNamespace(
            get_current_tool=lambda: "Select",
            get_selected_plan_target=lambda: (None, None),
            get_selected_plan_targets=lambda: (),
        )

        self.assertIs(context, as_task_panel_context(context))

    def test_task_panel_context_prefers_provider_and_status_components(self):
        from bimplan.task_panel_view_model import PlanTaskPanelContext

        provider = SimpleNamespace(
            get_provider_point_tool_label=lambda: "Socket",
            get_provider_point_tool_prompt=lambda: "Click socket point",
            get_plan_provider_display_name=lambda provider_id: provider_id.upper(),
            get_plan_provider_overlay_category=lambda overlay: "electrical",
            is_plan_provider_overlay_enabled=lambda overlay: True,
            get_plan_provider_overlay_mode=lambda: "electrical",
        )
        status_text = SimpleNamespace(
            format_provider_selected_object_state=lambda: "Object: Socket",
            format_provider_target_help=lambda obj: "Provider target help",
            format_provider_selected_object_help=lambda: "Provider object help",
            format_plan_target_selection_state=lambda kind, obj: f"{kind}:{obj.Name}",
            get_plan_target_display_label=lambda obj: obj.Name,
            summarize_plan_targets=lambda targets: "1 target",
            format_opening_selection_help=lambda obj: "Opening help",
            get_plan_selection_summary_text=lambda: "Summary",
        )
        session = SimpleNamespace(
            providers=provider,
            status_text=status_text,
        )

        context = PlanTaskPanelContext(session)
        overlay = SimpleNamespace(key="socket")
        obj = SimpleNamespace(Name="Socket001")

        self.assertEqual("Socket", context.get_provider_point_tool_label())
        self.assertEqual("Click socket point", context.get_provider_point_tool_prompt())
        self.assertEqual("PROVIDER-A", context.get_plan_provider_display_name("provider-a"))
        self.assertEqual("electrical", context.get_plan_provider_overlay_category(overlay))
        self.assertTrue(context.is_plan_provider_overlay_enabled(overlay))
        self.assertEqual("electrical", context.get_plan_provider_overlay_mode())
        self.assertEqual("Object: Socket", context.format_provider_selected_object_state())
        self.assertEqual("Provider target help", context.format_provider_target_help(obj))
        self.assertEqual("Provider object help", context.format_provider_selected_object_help())
        self.assertEqual(
            "provider:Socket001",
            context.format_plan_target_selection_state("provider", obj),
        )
        self.assertEqual("Socket001", context.get_plan_target_display_label(obj))
        self.assertEqual("1 target", context.summarize_plan_targets((("provider", obj),)))
        self.assertEqual("Opening help", context.format_opening_selection_help(obj))
        self.assertEqual("Summary", context.get_plan_selection_summary_text())

    def test_task_panel_context_prefers_relations_interaction_symbols_spaces_windows_and_wall_edit_components(
        self,
    ):
        from bimplan.task_panel_view_model import PlanTaskPanelContext

        parent_space = SimpleNamespace(Name="Space001")
        hovered_candidate = {"area": 2500000.0}
        wall_relations = SimpleNamespace(
            get_plan_candidate_joint=lambda target_wall=None: "joint",
            get_plan_join_candidate_state=lambda: ("Wall002", "joint", "Existing joint"),
            get_plan_join_type_label=lambda join_type=None: "Miter",
            get_plan_join_mode_action_text=lambda target_wall=None, joint=None: "Join action",
            get_plan_relation_status_message=lambda: "Relation status",
        )
        interaction = SimpleNamespace(is_modal_plan_interaction_active=lambda: True)
        symbols = SimpleNamespace(
            symbol_rotation_snap_enabled=lambda: True,
            format_symbol_rotation_snap_label=lambda: "15°",
        )
        spaces = SimpleNamespace(
            get_space_region_candidate_count=lambda: 2,
            get_hovered_space_region_candidate=lambda: hovered_candidate,
            format_space_region_candidate_area=lambda candidate: "2.500 m^2",
            get_plan_region_parent_space=lambda: parent_space,
            is_plan_space_object=lambda obj: obj is parent_space,
        )
        windows = SimpleNamespace(
            can_place_window=lambda: True,
            get_window_style_preset_options=lambda: ("Preset A", "Preset B"),
            can_edit_window_width=lambda obj=None: obj == "window",
            can_edit_window_height=lambda obj=None: False,
            can_apply_window_style_preset=lambda obj=None: obj == "window",
            get_selected_window_style_preset=lambda: "Preset A",
            get_selected_window_width_text=lambda: "1200 mm",
            get_selected_window_height_text=lambda: "1500 mm",
        )
        wall_edit = SimpleNamespace(is_selected_wall_endpoint_editable=lambda: True)
        session = SimpleNamespace(
            wall_relations=wall_relations,
            interaction=interaction,
            symbols=symbols,
            spaces=spaces,
            windows=windows,
            wall_edit=wall_edit,
        )

        context = PlanTaskPanelContext(session)

        self.assertTrue(context.is_modal_plan_interaction_active())
        self.assertTrue(context.symbol_rotation_snap_enabled())
        self.assertEqual("15°", context.format_symbol_rotation_snap_label())
        self.assertTrue(context.can_place_plan_window())
        self.assertTrue(context.has_plan_candidate_joint())
        self.assertEqual(
            ("Wall002", "joint", "Existing joint"),
            context.get_plan_join_candidate_state(),
        )
        self.assertEqual("Miter", context.get_plan_join_type_label())
        self.assertEqual("Join action", context.get_plan_join_mode_action_text("Wall002", "joint"))
        self.assertEqual("Relation status", context.get_plan_relation_status_message())
        self.assertEqual(2, context.get_space_region_candidate_count())
        self.assertIs(hovered_candidate, context.get_hovered_space_region_candidate())
        self.assertEqual("2.500 m^2", context.format_space_region_candidate_area(hovered_candidate))
        self.assertIs(parent_space, context.get_plan_region_parent_space())
        self.assertTrue(context.is_plan_space_object(parent_space))
        self.assertTrue(context.is_selected_wall_endpoint_editable())
        self.assertEqual(
            ("Preset A", "Preset B"),
            context.get_window_style_preset_options(),
        )
        self.assertTrue(context.can_edit_window_width("window"))
        self.assertFalse(context.can_edit_window_height("window"))
        self.assertTrue(context.can_apply_window_style_preset("window"))
        self.assertEqual("Preset A", context.get_selected_window_style_preset())
        self.assertEqual("1200 mm", context.get_selected_window_width_text())
        self.assertEqual("1500 mm", context.get_selected_window_height_text())

    def test_plan_selection_api_uses_primary_target_kind_policy(self):
        from bimplan.selection import target_kinds as plan_target_kinds
        from bimplan.runtime.session_components import PlanSelectionAPI

        session = object()
        selection = PlanSelectionAPI(session)

        with patch(
            "bimplan.session_components.plan_selection.get_selected_plan_target_state",
            return_value=("wall", "Wall001"),
        ) as get_selected_plan_target_state:
            self.assertEqual(("wall", "Wall001"), selection.get_selected_plan_target_state())

        get_selected_plan_target_state.assert_called_once_with(
            session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
        )

    def test_plan_spaces_api_uses_space_region_pick_visual_key(self):
        from bimplan import document_visuals as plan_document_visuals
        from bimplan.runtime.session_components import PlanSpacesAPI

        session = object()
        candidate = {"area": 12.0}
        spaces = PlanSpacesAPI(session)

        with patch(
            "bimplan.session_components.plan_spaces.set_hovered_space_region_candidate",
            return_value=True,
        ) as set_hovered_space_region_candidate:
            self.assertTrue(spaces.set_hovered_space_region_candidate(candidate))

        set_hovered_space_region_candidate.assert_called_once_with(
            session,
            candidate,
            plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
        )

    def test_plan_viewport_api_uses_view_policies(self):
        from bimplan.runtime.session_components import PlanViewportAPI

        session = SimpleNamespace(
            _plan_view_locked_actions=("Std_ViewTop", "Std_ViewFront"),
            _plan_paper_rgb=(1.0, 1.0, 1.0),
        )
        viewport = PlanViewportAPI(session)

        with patch(
            "bimplan.session_components.plan_view.capture_view_action_state",
            return_value=True,
        ) as capture_view_action_state, patch(
            "bimplan.session_components.plan_view.apply_plan_background_override",
            return_value=True,
        ) as apply_plan_background_override:
            self.assertTrue(viewport.capture_view_action_state())
            self.assertTrue(viewport.apply_plan_background_override())

        capture_view_action_state.assert_called_once_with(
            session,
            session._plan_view_locked_actions,
        )
        apply_plan_background_override.assert_called_once_with(
            session,
            session._plan_paper_rgb,
        )

    def test_activate_plan_region_tool_uses_shared_space_setup(self):
        parent_space = SimpleNamespace(Name="Space001")
        session = SimpleNamespace(
            current_tool="Select",
            _cancel_rect_wall_tool=lambda refresh=False: None,
            _cancel_provider_point_tool=lambda refresh=False: None,
            _clear_plan_relation_status=lambda: None,
            _set_selected_plan_target=lambda *args, **kwargs: None,
            _clear_hovered_plan_targets=lambda *args, **kwargs: None,
            _get_selected_plan_target_object=lambda kind: parent_space if kind == "space" else None,
            task_panels=SimpleNamespace(
                refresh_task_panel_status=lambda selection_only=False: None
            ),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: False,
                cancel_embedded_tool=lambda: None,
                cancel_pending_edit=lambda: None,
            ),
            windows=SimpleNamespace(cancel_window_tool=lambda refresh=False: None),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda restore=True, refresh=True: None),
            spaces=SimpleNamespace(
                cancel_space_region_pick=lambda refresh=False: None,
                cancel_space_separator_tool=lambda refresh=False: None,
                handle_plan_region_point=lambda *args, **kwargs: None,
                update_plan_region_preview=lambda *args, **kwargs: None,
            ),
        )

        with patch(
            "bimplan.lifecycle.plan_spaces.prepare_plan_region_tool_state"
        ) as prepare, patch("bimplan.lifecycle.clear_selection_visuals"), patch(
            "bimplan.lifecycle._start_snap_tool", return_value=True
        ):
            self.assertTrue(activate_plan_region_tool(session))

        prepare.assert_called_once_with(session, parent_space=parent_space)

    def test_activate_space_separator_tool_uses_shared_space_setup(self):
        session = SimpleNamespace(
            current_tool="Select",
            _cancel_rect_wall_tool=lambda refresh=False: None,
            _cancel_provider_point_tool=lambda refresh=False: None,
            _clear_plan_relation_status=lambda: None,
            _set_selected_plan_target=lambda *args, **kwargs: None,
            _get_wall_defaults=lambda: {"height": 2500},
            task_panels=SimpleNamespace(
                refresh_task_panel_status=lambda selection_only=False: None
            ),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: False,
                cancel_embedded_tool=lambda: None,
                cancel_pending_edit=lambda: None,
            ),
            windows=SimpleNamespace(cancel_window_tool=lambda refresh=False: None),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda restore=True, refresh=True: None),
            spaces=SimpleNamespace(
                cancel_space_region_pick=lambda refresh=False: None,
                cancel_plan_region_tool=lambda refresh=False: None,
                handle_space_separator_point=lambda *args, **kwargs: None,
            ),
        )

        with patch(
            "bimplan.lifecycle.plan_spaces.prepare_space_separator_tool_state"
        ) as prepare, patch("bimplan.lifecycle.clear_selection_visuals"), patch(
            "bimplan.lifecycle._start_snap_tool",
            return_value=True,
        ):
            self.assertTrue(activate_space_separator_tool(session))

        prepare.assert_called_once_with(session, height=2500)

    def test_create_space_from_current_selection_finalizes_direct_boundary_space(self):
        wall_a = SimpleNamespace(Name="WallA")
        wall_b = SimpleNamespace(Name="WallB")
        boundaries = [(wall_a, ("Face1",)), (wall_b, ("Face2",))]
        created_space = SimpleNamespace(Name="Space001")
        events = []
        doc = SimpleNamespace(
            openTransaction=lambda label: events.append(("open", label)),
            commitTransaction=lambda: events.append(("commit", None)),
            abortTransaction=lambda: events.append(("abort", None)),
            recompute=lambda: events.append(("recompute", None)),
        )
        session = SimpleNamespace(
            doc=doc,
            _get_selected_plan_targets=lambda: [("wall", wall_a), ("wall", wall_b)],
            visibility=SimpleNamespace(
                add_object_to_active_storey=lambda space: events.append(("add-storey", space)),
                register_plan_object=lambda space: events.append(("register", space)),
            ),
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    boundaries if fallback_space is None else []
                ),
                restore_selected_space=lambda space: events.append(("restore", space)),
                space_has_valid_geometry=lambda space: True,
                report_space_creation_failure=lambda space: (
                    events.append(("report-failure", space)) or False
                ),
            ),
        )
        arch_module = SimpleNamespace(
            makeSpace=lambda value: events.append(("make-space", value)) or created_space
        )
        archspace_module = SimpleNamespace(
            analyzeBoundaryLinks=lambda value: events.append(("analyze", value)) or {}
        )

        with patch.dict(sys.modules, {"Arch": arch_module, "ArchSpace": archspace_module}):
            self.assertTrue(create_space_from_current_selection(session))

        self.assertEqual(
            [
                ("analyze", boundaries),
                ("open", "Create Space"),
                ("make-space", boundaries),
                ("add-storey", created_space),
                ("recompute", None),
                ("commit", None),
                ("register", created_space),
                ("restore", created_space),
            ],
            events,
        )

    def test_begin_space_region_pick_auto_creates_single_remaining_candidate(self):
        candidate = {"area": 12.0}
        created_space = SimpleNamespace(Name="Space001")
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _space_region_pick_boundaries=[],
            _space_region_candidates=[],
            _hovered_space_region_candidate=None,
            _space_region_pick_seed_space=None,
            _register_plan_object=lambda space: calls.append(("register", space)),
            _clear_hovered_plan_targets=lambda **kwargs: calls.append(("clear-hovered", kwargs)),
            _refresh_primary_selected_plan_target=lambda: calls.append("refresh-primary"),
            spaces=SimpleNamespace(
                restore_selected_space=lambda space: calls.append(("restore", space)),
                create_space_from_region_candidate=lambda *args, **kwargs: (
                    calls.append(("create", args, kwargs)) or created_space
                ),
            ),
            overlays=SimpleNamespace(
                clear_space_region_pick_overlays=lambda: calls.append("clear-pick-overlays"),
                clear_wall_grips=lambda: calls.append("clear-wall-grips"),
            ),
        )
        boundaries = [("Boundary001", ("Face1",))]
        report = {
            "candidates": [candidate],
            "candidate_count": 1,
            "skipped_claimed_candidate_count": 1,
        }

        with patch("FreeCAD.Console.PrintMessage") as print_message:
            self.assertTrue(begin_space_region_pick(session, boundaries, report=report))

        self.assertEqual("Select", session.current_tool)
        self.assertEqual(
            [call.args[0] for call in print_message.call_args_list],
            [
                "Ignoring 1 enclosed region(s) already covered by existing spaces.\n",
            ],
        )
        self.assertEqual(
            [
                ("create", (candidate,), {"boundaries": boundaries, "keep_boundaries": True}),
                ("register", created_space),
                ("restore", created_space),
            ],
            calls,
        )

    def test_space_creation_request_uses_wall_boundary_selection_shape(self):
        wall_a = SimpleNamespace(Name="WallA")
        wall_b = SimpleNamespace(Name="WallB")
        boundaries = ((wall_a, ("Face1",)), (wall_b, ("Face2",)))
        session = SimpleNamespace(
            _get_selected_plan_targets=lambda: [("wall", wall_a), ("wall", wall_b)],
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    boundaries if fallback_space is None else ()
                )
            ),
        )

        request = get_space_creation_request(session)

        self.assertTrue(
            should_run_space_preflight_for_targets([("wall", wall_a), ("wall", wall_b)])
        )
        self.assertEqual(boundaries, tuple(request["boundaries"]))
        self.assertIsNone(request["region_seed_space"])

    def test_space_region_seed_targets_require_boundaries_for_single_space(self):
        space = SimpleNamespace(Name="Space001", Label="Living Room")
        boundary = (SimpleNamespace(Name="Divider"), ("Face1",))

        empty_session = SimpleNamespace(
            _get_selected_plan_targets=lambda: [("space", space)],
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: []
            ),
        )
        self.assertEqual((None, []), get_space_region_seed_targets(empty_session))
        self.assertIsNone(get_space_creation_request(empty_session))

        seeded_session = SimpleNamespace(
            _get_selected_plan_targets=lambda: [("space", space)],
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    [boundary] if fallback_space is space else []
                )
            ),
        )
        self.assertEqual((space, []), get_space_region_seed_targets(seeded_session))
        request = get_space_creation_request(seeded_session)
        self.assertIsNotNone(request)
        self.assertEqual("Living Room", request["label"])
        self.assertIs(space, request["region_seed_space"])
        self.assertEqual([boundary], request["boundaries"])

    def test_space_region_seed_targets_preserve_wall_seed_selection(self):
        space = SimpleNamespace(Name="Space001", Label="Seed Space")
        wall = SimpleNamespace(Name="Wall001")
        boundary = (wall, ("Face1",))
        targets = [("space", space), ("wall", wall)]
        session = SimpleNamespace(
            _get_selected_plan_targets=lambda: targets,
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    [boundary] if fallback_space is space else []
                )
            ),
        )

        self.assertTrue(should_run_space_preflight_for_targets(targets))
        self.assertEqual((space, [("wall", wall)]), get_space_region_seed_targets(session))
        request = get_space_creation_request(session)
        self.assertIsNotNone(request)
        self.assertIs(space, request["region_seed_space"])
        self.assertEqual([boundary], request["boundaries"])

    def test_activate_opening_target_uses_behavior_policy(self):
        calls = []
        target = SimpleNamespace(Name="Opening001")
        session = SimpleNamespace(
            _activate_plan_target=lambda *args, **kwargs: calls.append((args, kwargs)) or True
        )

        self.assertTrue(
            activate_opening_target(session, (100, 200), resolved_target=("opening", target))
        )

        self.assertEqual(
            [
                (
                    ("opening", (100, 200)),
                    {
                        "event_callback": None,
                        "sync_gui_selection": True,
                        "clear_hovered_kinds": ("wall", "opening", "symbol", "space", "region"),
                        "resolved_target": ("opening", target),
                        "defer_gui_selection": False,
                        "defer_wall_grips": False,
                    },
                )
            ],
            calls,
        )

    def test_activate_semantic_plan_target_uses_wall_behavior_overrides(self):
        calls = []
        target = SimpleNamespace(Name="Wall001")
        session = SimpleNamespace(
            selection=SimpleNamespace(get_hovered_plan_target=lambda: ("wall", target)),
            _hover_pick_dirty=False,
            performance=_make_perf_stub(),
            _activate_plan_target=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
        )

        self.assertTrue(activate_semantic_plan_target(session, (50, 60)))

        self.assertEqual(
            [
                (
                    ("wall", (50, 60)),
                    {
                        "event_callback": None,
                        "sync_gui_selection": True,
                        "clear_hovered_kinds": ("wall", "symbol", "space", "region"),
                        "resolved_target": ("wall", target),
                        "defer_gui_selection": True,
                        "defer_wall_grips": True,
                    },
                )
            ],
            calls,
        )

    def test_begin_teardown_uses_cleanup_profile(self):
        calls = []
        session = SimpleNamespace(
            _tearing_down=False,
            current_tool="Set Space Text",
            _edit_space="Space001",
            viewport=SimpleNamespace(clear_viewport_status_chip=lambda: calls.append("chip")),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            _cancel_provider_point_tool=lambda refresh=True: calls.append(
                ("provider-point", refresh)
            ),
            lifecycle=SimpleNamespace(
                cancel_embedded_tool=lambda: calls.append("embedded"),
                cancel_pending_edit=lambda: calls.append("pending"),
            ),
            windows=SimpleNamespace(
                cancel_window_tool=lambda refresh=True: calls.append(("window", refresh))
            ),
            wall_edit=SimpleNamespace(
                cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                    ("wall-edit", restore, refresh)
                )
            ),
            spaces=SimpleNamespace(
                cancel_plan_region_tool=lambda refresh=True: calls.append(("plan-region", refresh))
            ),
        )

        with patch("bimplan.lifecycle.plan_command_gate.uninstall") as uninstall, patch(
            "bimplan.lifecycle.clear_hover_visuals"
        ) as clear_hover_visuals, patch(
            "bimplan.lifecycle.clear_selection_visuals"
        ) as clear_selection_visuals, patch(
            "bimplan.lifecycle.clear_transient_visuals"
        ) as clear_transient_visuals, patch(
            "bimplan.lifecycle.detach_runtime_observers"
        ) as detach_runtime_observers:
            begin_teardown(session)

        uninstall.assert_called_once_with(session)
        clear_hover_visuals.assert_called_once_with(
            session,
            include_junction_nodes=True,
            include_hovered_wall_opening_context=True,
        )
        clear_selection_visuals.assert_called_once_with(
            session,
            clear_handle_kinds=("provider", "opening", "symbol"),
            include_wall_grips=True,
            include_selected_wall_opening_context=True,
            include_secondary_selection=True,
        )
        clear_transient_visuals.assert_called_once_with(
            session,
            include_provider_overlays=True,
            include_provider_point_preview=True,
            include_space_region_pick=True,
            include_opening_handle_pool=True,
            include_opening_move_preview=True,
            include_symbol_edit_preview=True,
            include_plan_region_preview=True,
        )
        detach_runtime_observers.assert_called_once_with(session)
        self.assertTrue(session._tearing_down)
        self.assertIsNone(session._edit_space)
        self.assertEqual(
            [
                "chip",
                "hints",
                "embedded",
                ("rect-wall", False),
                ("window", False),
                ("plan-region", False),
                ("provider-point", False),
                ("wall-edit", False, False),
                "pending",
            ],
            calls,
        )

    def test_begin_teardown_uses_shared_space_region_pick_reset(self):
        session = SimpleNamespace(
            _tearing_down=False,
            current_tool="Pick Space Region",
            viewport=SimpleNamespace(clear_viewport_status_chip=lambda: None),
            _clear_input_hints=lambda: None,
            _cancel_rect_wall_tool=lambda refresh=True: None,
            _cancel_provider_point_tool=lambda refresh=True: None,
            lifecycle=SimpleNamespace(
                cancel_embedded_tool=lambda: None,
                cancel_pending_edit=lambda: None,
            ),
            windows=SimpleNamespace(cancel_window_tool=lambda refresh=True: None),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda restore=True, refresh=True: None),
            spaces=SimpleNamespace(cancel_plan_region_tool=lambda refresh=True: None),
        )

        with patch("bimplan.lifecycle.plan_command_gate.uninstall"), patch(
            "bimplan.lifecycle.plan_spaces.reset_space_region_pick_state"
        ) as reset_space_region_pick_state, patch("bimplan.lifecycle.clear_hover_visuals"), patch(
            "bimplan.lifecycle.clear_selection_visuals"
        ), patch(
            "bimplan.lifecycle.clear_transient_visuals"
        ), patch(
            "bimplan.lifecycle.detach_runtime_observers"
        ):
            begin_teardown(session)

        reset_space_region_pick_state.assert_called_once_with(
            session,
            clear_overlays=False,
        )

    def test_begin_teardown_uses_shared_space_text_pick_reset(self):
        session = SimpleNamespace(
            _tearing_down=False,
            current_tool="Set Space Text",
            _edit_space="Space001",
            viewport=SimpleNamespace(clear_viewport_status_chip=lambda: None),
            _clear_input_hints=lambda: None,
            _cancel_rect_wall_tool=lambda refresh=True: None,
            _cancel_provider_point_tool=lambda refresh=True: None,
            lifecycle=SimpleNamespace(
                cancel_embedded_tool=lambda: None,
                cancel_pending_edit=lambda: None,
            ),
            windows=SimpleNamespace(cancel_window_tool=lambda refresh=True: None),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda restore=True, refresh=True: None),
            spaces=SimpleNamespace(cancel_plan_region_tool=lambda refresh=True: None),
        )

        with patch("bimplan.lifecycle.plan_command_gate.uninstall"), patch(
            "bimplan.lifecycle.plan_spaces.reset_space_text_pick_state"
        ) as reset_space_text_pick_state, patch("bimplan.lifecycle.clear_hover_visuals"), patch(
            "bimplan.lifecycle.clear_selection_visuals"
        ), patch(
            "bimplan.lifecycle.clear_transient_visuals"
        ), patch(
            "bimplan.lifecycle.detach_runtime_observers"
        ):
            begin_teardown(session)

        reset_space_text_pick_state.assert_called_once_with(session)

    def test_shutdown_uses_cleanup_profile(self):
        calls = []
        panel = SimpleNamespace(
            mark_closed=lambda: calls.append("mark_closed"),
            detach=lambda: calls.append("detach"),
            close=lambda: calls.append("close"),
        )
        session = SimpleNamespace(
            _tearing_down=False,
            task_panel=panel,
            current_tool="Move Symbol",
            viewport=SimpleNamespace(clear_viewport_status_chip=lambda: calls.append("chip")),
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            lifecycle=SimpleNamespace(
                cancel_embedded_tool=lambda: calls.append("embedded"),
                cancel_pending_edit=lambda: calls.append("pending"),
            ),
            symbols=SimpleNamespace(
                cancel_symbol_handle_point_pick=lambda: calls.append("symbol-handle")
            ),
            restore_state=lambda: calls.append("restore-state"),
            doc=SimpleNamespace(recompute=lambda: calls.append("recompute")),
            wall_edit=SimpleNamespace(
                cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                    ("wall-edit", restore, refresh)
                )
            ),
            spaces=SimpleNamespace(
                cancel_space_separator_tool=lambda refresh=True: calls.append(
                    ("separator", refresh)
                )
            ),
        )

        with patch("bimplan.lifecycle.plan_command_gate.uninstall") as uninstall, patch(
            "bimplan.lifecycle.clear_hover_visuals"
        ) as clear_hover_visuals, patch(
            "bimplan.lifecycle.clear_selection_visuals"
        ) as clear_selection_visuals, patch(
            "bimplan.lifecycle.clear_transient_visuals"
        ) as clear_transient_visuals, patch(
            "bimplan.lifecycle.detach_runtime_observers"
        ) as detach_runtime_observers:
            self.assertTrue(shutdown(session, close_dialog=False))

        uninstall.assert_called_once_with(session)
        clear_hover_visuals.assert_called_once_with(
            session,
            kinds=("wall", "opening", "symbol", "provider"),
            include_junction_nodes=True,
            include_hovered_wall_opening_context=True,
        )
        clear_selection_visuals.assert_called_once_with(
            session,
            clear_handle_kinds=("opening", "symbol"),
            include_wall_grips=True,
            include_selected_wall_opening_context=True,
        )
        clear_transient_visuals.assert_called_once_with(
            session,
            include_provider_overlays=True,
            include_provider_point_preview=True,
            include_opening_handle_pool=True,
            include_opening_move_preview=True,
            include_symbol_edit_preview=True,
        )
        detach_runtime_observers.assert_called_once_with(session)
        self.assertIsNone(session.task_panel)
        self.assertEqual(
            [
                "chip",
                "hints",
                "embedded",
                ("rect-wall", False),
                ("separator", False),
                ("wall-edit", True, False),
                "pending",
                "symbol-handle",
                "mark_closed",
                "detach",
                "restore-state",
                "recompute",
            ],
            calls,
        )

    def test_shutdown_teardown_profile_disables_wall_restore(self):
        calls = []
        session = SimpleNamespace(
            _tearing_down=True,
            task_panel=None,
            current_tool="Move Symbol",
            viewport=SimpleNamespace(clear_viewport_status_chip=lambda: calls.append("chip")),
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            lifecycle=SimpleNamespace(
                cancel_embedded_tool=lambda: calls.append("embedded"),
                cancel_pending_edit=lambda: calls.append("pending"),
                discard_runtime_references=lambda: calls.append("discard-runtime"),
            ),
            symbols=SimpleNamespace(
                cancel_symbol_handle_point_pick=lambda: calls.append("symbol-handle")
            ),
            wall_edit=SimpleNamespace(
                cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                    ("wall-edit", restore, refresh)
                )
            ),
            spaces=SimpleNamespace(
                cancel_space_separator_tool=lambda refresh=True: calls.append(
                    ("separator", refresh)
                )
            ),
        )

        with patch("bimplan.lifecycle.plan_command_gate.uninstall"), patch(
            "bimplan.lifecycle.clear_hover_visuals"
        ), patch("bimplan.lifecycle.clear_selection_visuals"), patch(
            "bimplan.lifecycle.clear_transient_visuals"
        ), patch(
            "bimplan.lifecycle.detach_runtime_observers"
        ):
            self.assertTrue(shutdown(session, teardown=True))

        self.assertEqual(
            [
                "chip",
                "hints",
                "embedded",
                ("rect-wall", False),
                ("separator", False),
                ("wall-edit", False, False),
                "pending",
                "symbol-handle",
                "discard-runtime",
            ],
            calls,
        )

    def test_target_dispatch_uses_policy_for_validation_and_restore(self):
        restored = []
        target = SimpleNamespace(Name="Space001")
        session = SimpleNamespace(
            _is_plan_space_object=lambda obj: obj is target,
            spaces=SimpleNamespace(queue_restore_selected_space=lambda obj: restored.append(obj)),
        )

        self.assertTrue(validate_plan_target(session, "space", target))
        self.assertTrue(queue_restore_selected_target(session, "space", target))
        self.assertEqual([target], restored)

    def test_target_dispatch_uses_policy_for_hover_sync(self):
        calls = []
        target = SimpleNamespace(Name="Opening001")
        session = SimpleNamespace(
            hovered_opening=None,
            selection=SimpleNamespace(is_selected_plan_target=lambda kind, obj=None: False),
            overlays=SimpleNamespace(
                sync_selected_wall_opening_context_overlay=lambda: calls.append("context"),
                sync_hovered_opening_overlay=lambda: calls.append("hover"),
            ),
        )

        self.assertTrue(set_hovered_target(session, "opening", target))
        self.assertIs(session.hovered_opening, target)
        self.assertEqual(["context", "hover"], calls)
        self.assertFalse(set_hovered_target(session, "opening", target))

    def test_finish_uses_current_tool_dispatch_before_fallback_actions(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Move Provider",
            providers=SimpleNamespace(
                cancel_provider_handle_point_pick=lambda: calls.append("move-provider")
            ),
            _has_active_provider_point_tool=lambda: True,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: True,
                cancel_embedded_tool=lambda: calls.append("embedded"),
            ),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            wall_edit=SimpleNamespace(
                has_active_wall_edit=lambda: True,
                cancel_wall_edit=lambda: calls.append("wall-edit"),
            ),
            shutdown=lambda close_dialog=True: calls.append(("shutdown", close_dialog)),
        )

        self.assertTrue(finish(session))
        self.assertEqual(["move-provider"], calls)

    def test_finish_stops_after_first_matching_fallback_action(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _has_active_provider_point_tool=lambda: True,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: True,
                cancel_embedded_tool=lambda: calls.append("embedded"),
            ),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            wall_edit=SimpleNamespace(
                has_active_wall_edit=lambda: True,
                cancel_wall_edit=lambda: calls.append("wall-edit"),
            ),
            shutdown=lambda close_dialog=True: calls.append(("shutdown", close_dialog)),
        )

        self.assertTrue(finish(session))
        self.assertEqual(["provider-point"], calls)

    def test_finish_calls_shutdown_when_no_cleanup_applies(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _has_active_provider_point_tool=lambda: False,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: False,
                cancel_embedded_tool=lambda: calls.append("embedded"),
            ),
            _has_active_rect_wall_tool=lambda: False,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            wall_edit=SimpleNamespace(
                has_active_wall_edit=lambda: False,
                cancel_wall_edit=lambda: calls.append("wall-edit"),
            ),
            shutdown=lambda close_dialog=True: ("shutdown", close_dialog),
        )

        self.assertEqual(("shutdown", False), finish(session, close_dialog=False))
        self.assertEqual([], calls)

    def test_activate_select_tool_stops_after_current_tool_cancel(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Move Symbol",
            symbols=SimpleNamespace(cancel_symbol_handle_point_pick=lambda: calls.append("symbol")),
            _has_active_provider_point_tool=lambda: True,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: True,
                cancel_embedded_tool=lambda: calls.append("embedded"),
            ),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _cancel_join_tool=lambda: calls.append("join"),
            windows=SimpleNamespace(
                has_active_window_tool=lambda: True,
                cancel_window_tool=lambda: calls.append("window"),
            ),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda: calls.append("wall-edit")),
            spaces=SimpleNamespace(
                cancel_space_region_pick=lambda: calls.append("space-region"),
                has_active_plan_region_tool=lambda: True,
                cancel_plan_region_tool=lambda: calls.append("plan-region"),
                has_active_space_separator_tool=lambda: True,
                cancel_space_separator_tool=lambda: calls.append("separator"),
            ),
        )

        activate_select_tool(session)

        self.assertEqual(["symbol"], calls)

    def test_activate_select_tool_runs_ordered_cleanup_actions(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            symbols=SimpleNamespace(cancel_symbol_handle_point_pick=lambda: calls.append("symbol")),
            _has_active_provider_point_tool=lambda: False,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            lifecycle=SimpleNamespace(
                has_active_embedded_tool=lambda: True,
                cancel_embedded_tool=lambda: calls.append("embedded"),
            ),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _cancel_join_tool=lambda: calls.append("join"),
            windows=SimpleNamespace(
                has_active_window_tool=lambda: False,
                cancel_window_tool=lambda: calls.append("window"),
            ),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda: calls.append("wall-edit")),
            spaces=SimpleNamespace(
                cancel_space_region_pick=lambda: calls.append("space-region"),
                has_active_plan_region_tool=lambda: True,
                cancel_plan_region_tool=lambda: calls.append("plan-region"),
                has_active_space_separator_tool=lambda: True,
                cancel_space_separator_tool=lambda: calls.append("separator"),
            ),
        )

        activate_select_tool(session)

        self.assertEqual(
            ["embedded", "rect-wall", "plan-region", "separator", "wall-edit", "join"],
            calls,
        )

    def test_plan_edit_context_proxies_session_helpers(self):
        target = PlanTarget(
            kind="space",
            document_name="PlanDoc",
            object_name="Space001",
            label="Kitchen",
            semantic_document_name="PlanDoc",
            semantic_object_name="Space001",
            semantic_label="Kitchen",
            is_selected=True,
            is_primary=True,
        )
        semantic_record = PlanSemanticRecord(
            target_kind="space",
            document_name="PlanDoc",
            object_name="Space001",
            label="Kitchen",
            semantic_document_name="PlanDoc",
            semantic_object_name="Space001",
            semantic_label="Kitchen",
            space_key="kitchen_main",
            space_label="Kitchen",
            usage_category="kitchen",
        )
        session = _DummySession(
            selected_targets=(target,),
            all_targets=(target,),
            semantic_records=(semantic_record,),
            selected_objects=("raw-object",),
        )
        context = PlanEditContext(
            session=session,
            document_name="PlanDoc",
            active_storey_name="Level0",
            active_storey_label="Level 0",
            current_tool="Select",
        )

        self.assertEqual((target,), context.get_selected_targets())
        self.assertEqual((target,), context.get_all_targets())
        self.assertEqual(target, context.get_primary_target())
        self.assertEqual(("raw-object",), context.get_selected_objects())
        self.assertEqual((semantic_record,), context.get_selected_semantic_records())
        self.assertEqual(semantic_record, context.get_primary_semantic_record())
        self.assertEqual("target:Space001", context.resolve_object(target))
        self.assertEqual("semantic:Space001", context.resolve_semantic_object(target))
        self.assertEqual("semantic:raw-object", context.get_semantic_object("raw-object"))

    def test_plan_provider_action_context_proxies_limited_session_commands(self):
        doc = _DummyDoc()
        opening = SimpleNamespace(Document=doc)
        wall = SimpleNamespace(Name="Wall001")
        calls = []
        session = SimpleNamespace(
            doc=doc,
            selection=SimpleNamespace(
                select_wall_for_plan_edit=lambda obj, sync_gui_selection=True: calls.append(
                    ("select", obj, sync_gui_selection)
                )
                or True
            ),
            openings=SimpleNamespace(
                invalidate_wall_hosted_openings_cache=lambda: calls.append(("invalidate", None))
            ),
            document_visuals=SimpleNamespace(
                queue_recompute_opening_hosts=lambda obj: calls.append(("recompute-hosts", obj)),
                refresh_opening_host_footprint_displays=lambda obj: calls.append(
                    ("refresh-hosts", obj)
                ),
                refresh_opening_footprint_display=lambda obj: calls.append(
                    ("refresh-opening", obj)
                ),
            ),
        )

        context = PlanProviderActionContext(
            _session=session,
            payload={"point": (1.0, 2.0, 0.0)},
            document_name="PlanDoc",
            current_tool="Provider Point",
        )

        self.assertEqual({"point": (1.0, 2.0, 0.0)}, context.get_action_payload())
        self.assertTrue(context.select_wall_for_plan_edit(wall))
        self.assertTrue(context.queue_recompute_opening_hosts(opening))
        self.assertTrue(context.recompute_document())
        context.refresh_opening_visuals(opening)

        self.assertEqual(
            [
                ("select", wall, True),
                ("recompute-hosts", opening),
                ("invalidate", None),
                ("refresh-hosts", opening),
                ("refresh-opening", opening),
            ],
            calls,
        )
        self.assertIn(("recompute", None), doc.events)

    def test_execute_plan_provider_action_passes_action_context_proxy(self):
        from bimplan.providers.runtime import execute_plan_provider_action
        from bimplan.providers import PlanEditRegistry

        captured = {}

        class _ActionProvider(PlanEditProvider):
            provider_id = "action-provider"

            def execute_action(self, action_key, context, commands, payload=None):
                captured["action_key"] = action_key
                captured["context"] = context
                captured["command_context"] = commands
                captured["payload"] = payload
                captured["payload_from_commands"] = commands.get_action_payload()
                return True

        registry = PlanEditRegistry()
        provider = _ActionProvider()
        registry.register_provider(provider)
        doc = _DummyDoc()
        plan_context = SimpleNamespace(name="plan-context")
        action_context = PlanProviderActionContext(
            _session=SimpleNamespace(doc=doc),
            payload={"key": "value"},
            document_name="PlanDoc",
            current_tool="Provider Point",
        )
        session = SimpleNamespace(
            doc=doc,
            viewport=SimpleNamespace(focus_plan_view=lambda: None),
            get_plan_provider_registry=lambda: registry,
            defer_document_visual_updates=lambda: nullcontext(),
            _refresh_primary_selected_plan_target=lambda: None,
            document_visuals=SimpleNamespace(
                document_is_alive=lambda: True,
                invalidate_document_dependent_plan_visuals=lambda: None,
            ),
            task_panels=SimpleNamespace(
                refresh_task_panel_status=lambda selection_only=False: None
            ),
            providers=SimpleNamespace(
                get_plan_edit_context=lambda: plan_context,
                get_plan_provider_action_context=lambda payload=None: action_context,
            ),
        )

        self.assertTrue(
            execute_plan_provider_action(
                session,
                "action-provider",
                "do-work",
                payload={"key": "value"},
            )
        )
        self.assertEqual("do-work", captured["action_key"])
        self.assertIs(plan_context, captured["context"])
        self.assertIs(action_context, captured["command_context"])
        self.assertEqual({"key": "value"}, captured["payload"])
        self.assertEqual({"key": "value"}, captured["payload_from_commands"])
        self.assertIn(("recompute", None), doc.events)

    def test_plan_overlay_spec_carries_normalized_point_targets(self):
        overlay = PlanOverlaySpec(
            key="fixture-status",
            points=((1.0, 2.0, 3.0), ("invalid",)),
            marker_kind=PlanOverlayMarkerKind.DIAMOND,
            point_targets=(
                PlanOverlayTargetSpec(
                    document_name=" PlanDoc ",
                    object_name=" Socket001 ",
                    target_kind=PlanOverlayTargetKind.OBJECT,
                ),
                PlanOverlayTargetSpec(object_name="Ignored"),
            ),
        )

        normalized = normalize_plan_provider_overlay("test-provider", overlay)

        self.assertEqual("test-provider", normalized.provider_id)
        self.assertEqual(((1.0, 2.0, 3.0),), normalized.points)
        self.assertEqual(PlanOverlayMarkerKind.DIAMOND, normalized.marker_kind)
        self.assertEqual(
            (
                PlanOverlayTargetSpec(
                    document_name="PlanDoc",
                    object_name="Socket001",
                    target_kind=PlanOverlayTargetKind.OBJECT,
                ),
            ),
            normalized.point_targets,
        )

    def test_get_hovered_plan_target_returns_provider_target(self):
        provider = SimpleNamespace(Name="Socket001")
        session = SimpleNamespace(
            hovered_opening=None,
            hovered_provider=provider,
            hovered_symbol=None,
            hovered_wall=None,
            hovered_region=None,
            hovered_space=None,
        )

        self.assertEqual(("provider", provider), get_hovered_plan_target(session))

    def test_hovered_provider_overlay_specs_follow_visible_socket_marker(self):
        provider = SimpleNamespace(
            Name="Socket001",
            Document=SimpleNamespace(Name="PlanDoc"),
        )
        session = SimpleNamespace(
            viewport=SimpleNamespace(
                scaled_line_width=lambda width: float(width),
                scaled_marker_size=lambda size: float(size),
            ),
            current_tool="Select",
            hovered_provider=provider,
            doc=provider.Document,
            _plan_provider_refresh_cache_scope=lambda: nullcontext(),
            get_plan_provider_overlays=lambda: (
                PlanOverlaySpec(
                    key="fixture-status",
                    points=((100.0, 200.0, 0.0),),
                    point_targets=(
                        PlanOverlayTargetSpec(
                            object_name=provider.Name,
                            target_kind=PlanOverlayTargetKind.PROVIDER,
                        ),
                    ),
                    marker_kind=PlanOverlayMarkerKind.SQUARE,
                    marker_size=180.0,
                ),
            ),
            is_plan_provider_overlay_visible=lambda _overlay: True,
            visibility=SimpleNamespace(
                get_document_object_key=lambda obj: (
                    getattr(getattr(obj, "Document", None), "Name", None),
                    getattr(obj, "Name", None),
                )
            ),
        )

        specs = provider_overlays._get_hovered_provider_segment_specs(session)

        self.assertEqual(4, len(specs))
        self.assertTrue(all(spec["color"] == (0.38, 0.62, 0.96) for spec in specs))
        self.assertTrue(all(spec["width"] > 2.0 for spec in specs))

    def test_provider_overlay_edit_node_resolves_raw_document_object(self):
        class _Field:
            def __init__(self, value):
                self._value = value

            def getValue(self):
                return self._value

        marker = SimpleNamespace(Name="Socket001")
        doc = SimpleNamespace(getObject=lambda name: marker if name == marker.Name else None)
        session = SimpleNamespace(
            doc=doc,
            _is_valid_plan_target=lambda _kind, _obj: False,
            selection=SimpleNamespace(get_plan_target_for_object=lambda _obj: (None, None)),
        )
        point = SimpleNamespace(
            documentName=_Field(""),
            objectName=_Field("Socket001"),
            subElementName=_Field("ProviderOverlayPoint:object:0"),
        )

        self.assertEqual(
            (None, marker),
            get_provider_overlay_target_from_edit_node(
                session,
                ("provider_overlay_point", point),
            ),
        )

    def test_pick_provider_overlay_target_from_overlays_resolves_marker(self):
        marker = SimpleNamespace(Name="Socket001", Label="Socket 001")
        doc = SimpleNamespace(getObject=lambda name: marker if name == marker.Name else None)

        class _View:
            def getPointOnScreen(self, point):
                return (float(point.x), float(point.y))

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlays=lambda: (
                PlanOverlaySpec(
                    key="fixture-status",
                    points=((100.0, 200.0, 0.0),),
                    point_targets=(
                        PlanOverlayTargetSpec(
                            object_name=marker.Name,
                            target_kind=PlanOverlayTargetKind.OBJECT,
                        ),
                    ),
                    marker_size=220.0,
                ),
            ),
            is_plan_provider_overlay_visible=lambda _overlay: True,
            performance=_make_perf_stub(),
        )

        self.assertEqual(
            ("object", marker),
            pick_provider_overlay_target_from_overlays(session, (108, 204)),
        )

    def test_pick_provider_overlay_target_from_overlays_accepts_square_corner_click(self):
        marker = SimpleNamespace(Name="Socket001", Label="Socket 001")
        doc = SimpleNamespace(getObject=lambda name: marker if name == marker.Name else None)

        class _View:
            def getPointOnScreen(self, point):
                return (float(point.x), float(point.y))

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlays=lambda: (
                PlanOverlaySpec(
                    key="fixture-status",
                    points=((100.0, 200.0, 0.0),),
                    point_targets=(
                        PlanOverlayTargetSpec(
                            object_name=marker.Name,
                            target_kind=PlanOverlayTargetKind.OBJECT,
                        ),
                    ),
                    marker_kind=PlanOverlayMarkerKind.SQUARE,
                    marker_size=200.0,
                ),
            ),
            is_plan_provider_overlay_visible=lambda _overlay: True,
            performance=_make_perf_stub(),
        )

        self.assertEqual(
            ("object", marker),
            pick_provider_overlay_target_from_overlays(session, (200, 300)),
        )

    def test_pick_provider_overlay_target_from_objects_info_resolves_marker(self):
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: marker if name == marker.Name else None,
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": marker.Name,
                    },
                )

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlays=lambda: (
                PlanOverlaySpec(
                    key="fixture-status",
                    point_targets=(
                        PlanOverlayTargetSpec(
                            document_name=doc.Name,
                            object_name=marker.Name,
                            target_kind=PlanOverlayTargetKind.OBJECT,
                        ),
                    ),
                ),
            ),
            is_plan_provider_overlay_visible=lambda _overlay: True,
            performance=_make_perf_stub(),
        )

        self.assertEqual(
            ("object", marker),
            pick_provider_overlay_target_from_objects_info(session, (100, 200)),
        )

    def test_get_plan_target_at_position_prefers_provider_overlay_over_space_fallback(self):
        space = SimpleNamespace(
            Name="Space001",
            Label="Bedroom",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: (
                space if name == space.Name else marker if name == marker.Name else None
            ),
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": space.Name,
                    },
                )

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlay_mode=lambda: "all",
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda mouse_pos, radius_px=16: (
                    "provider",
                    marker,
                ),
                pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            ),
            openings=SimpleNamespace(get_wall_hosted_openings=lambda *_args, **_kwargs: ()),
            performance=_make_perf_stub(
                describe_object=lambda obj: getattr(obj, "Name", ""),
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with patch(
            "bimplan.picking.plan_targets.get_plan_pick_target_for_object",
            return_value=("space", space),
        ):
            self.assertEqual(
                ("provider", marker),
                get_plan_target_at_position(session, (100, 200)),
            )

    def test_get_plan_target_at_position_prefers_provider_over_wall_in_focused_overlay_mode(self):
        wall = SimpleNamespace(
            Name="Wall001",
            Label="Wall 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: (
                wall if name == wall.Name else marker if name == marker.Name else None
            ),
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": wall.Name,
                    },
                    {
                        "Document": doc.Name,
                        "Object": marker.Name,
                    },
                )

        def _get_plan_pick_target_for_object(_session, obj, parent_obj=None):
            del parent_obj
            if obj is wall:
                return ("wall", wall)
            if obj is marker:
                return ("provider", marker)
            return (None, None)

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlay_mode=lambda: "electrical",
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
                pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: None,
            ),
            openings=SimpleNamespace(get_wall_hosted_openings=lambda *_args, **_kwargs: ()),
            performance=_make_perf_stub(
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with patch(
            "bimplan.picking.plan_targets.get_plan_pick_target_for_object",
            side_effect=_get_plan_pick_target_for_object,
        ):
            self.assertEqual(
                ("provider", marker),
                get_plan_target_at_position(session, (100, 200)),
            )

    def test_get_plan_target_at_position_keeps_wall_priority_in_all_overlay_mode(self):
        wall = SimpleNamespace(
            Name="Wall001",
            Label="Wall 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: (
                wall if name == wall.Name else marker if name == marker.Name else None
            ),
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": wall.Name,
                    },
                    {
                        "Document": doc.Name,
                        "Object": marker.Name,
                    },
                )

        def _get_plan_pick_target_for_object(_session, obj, parent_obj=None):
            del parent_obj
            if obj is wall:
                return ("wall", wall)
            if obj is marker:
                return ("provider", marker)
            return (None, None)

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlay_mode=lambda: "all",
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
                pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: None,
            ),
            openings=SimpleNamespace(get_wall_hosted_openings=lambda *_args, **_kwargs: ()),
            performance=_make_perf_stub(
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with patch(
            "bimplan.picking.plan_targets.get_plan_pick_target_for_object",
            side_effect=_get_plan_pick_target_for_object,
        ):
            self.assertEqual(
                ("wall", wall),
                get_plan_target_at_position(session, (100, 200)),
            )

    def test_get_plan_target_at_position_keeps_space_fallback_for_clicks_in_focused_overlay_mode(
        self,
    ):
        space = SimpleNamespace(
            Name="SpaceKitchen",
            Label="Kitchen",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: space if name == space.Name else None,
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": space.Name,
                    },
                )

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlay_mode=lambda: "electrical",
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
                pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            ),
            openings=SimpleNamespace(get_wall_hosted_openings=lambda *_args, **_kwargs: ()),
            performance=_make_perf_stub(
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with patch(
            "bimplan.picking.plan_targets.get_plan_pick_target_for_object",
            return_value=("space", space),
        ):
            self.assertEqual(
                ("space", space),
                get_plan_target_at_position(session, (100, 200)),
            )

    def test_get_plan_target_at_position_can_skip_space_fallback_for_hover_in_focused_overlay_mode(
        self,
    ):
        space = SimpleNamespace(
            Name="SpaceKitchen",
            Label="Kitchen",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: space if name == space.Name else None,
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": doc.Name,
                        "Object": space.Name,
                    },
                )

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            get_plan_provider_overlay_mode=lambda: "electrical",
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
                pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            ),
            openings=SimpleNamespace(get_wall_hosted_openings=lambda *_args, **_kwargs: ()),
            performance=_make_perf_stub(
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with patch(
            "bimplan.picking.plan_targets.get_plan_pick_target_for_object",
            return_value=("space", space),
        ):
            self.assertEqual(
                (None, None),
                get_plan_target_at_position(
                    session,
                    (100, 200),
                    include_space_fallback=False,
                ),
            )

    def test_resolve_selected_target_for_gui_object_preserves_pending_provider_target(self):
        marker = SimpleNamespace(
            Name="Link002",
            Label="Nightstand002",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        session = SimpleNamespace(
            _is_valid_plan_target=lambda kind, obj: kind == "provider" and obj is marker,
            selection=SimpleNamespace(
                get_plan_target_for_object=lambda _selected: ("symbol", marker)
            ),
        )

        self.assertEqual(
            ("provider", marker),
            resolve_selected_target_for_gui_object(
                session,
                marker,
                pending_kind="provider",
                pending_target=marker,
            ),
        )

    def test_resolve_selected_target_for_gui_object_preserves_visible_provider_target(self):
        marker = SimpleNamespace(
            Name="Link002",
            Label="Nightstand002",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        session = SimpleNamespace(
            _is_valid_plan_target=lambda kind, obj: kind == "provider" and obj is marker,
            selection=SimpleNamespace(
                get_plan_target_for_object=lambda _selected: ("symbol", marker)
            ),
        )

        with patch(
            "bimplan.selection.plan_provider_runtime.is_plan_provider_target_visible_for_mode",
            return_value=True,
        ):
            self.assertEqual(
                ("provider", marker),
                resolve_selected_target_for_gui_object(
                    session,
                    marker,
                    preserved_kind="provider",
                    preserved_target=marker,
                ),
            )

    def test_provider_overlay_legend_items_filter_by_mode(self):
        items = (
            (
                "test-provider",
                "provider-preview",
                "Provider Preview",
                (0.1, 0.2, 0.3),
                True,
                "architecture",
            ),
            (
                "test-provider",
                "electrical-preview",
                "Electrical Preview",
                (0.9, 0.6, 0.1),
                True,
                "electrical",
            ),
        )

        self.assertEqual(
            (items[0],),
            filter_provider_overlay_legend_items_for_mode(
                items,
                active_mode="architecture",
            ),
        )
        self.assertEqual(
            (items[1],),
            filter_provider_overlay_legend_items_for_mode(
                items,
                active_mode="electrical",
            ),
        )
        self.assertEqual(
            items,
            filter_provider_overlay_legend_items_for_mode(
                items,
                active_mode="all",
            ),
        )

    def test_integration_refresh_timer_uses_weak_panel_reference(self):
        callbacks = []

        class _Timer:
            @staticmethod
            def singleShot(_delay, callback):
                callbacks.append(callback)

        widget = object.__new__(PlanEditControlsWidget)
        widget.form = object()
        widget.session = SimpleNamespace()
        widget._integration_refresh_queued = False
        widget._integration_refresh_generation = 0

        with patch.dict(
            sys.modules,
            {"PySide": SimpleNamespace(QtCore=SimpleNamespace(QTimer=_Timer))},
        ):
            widget._queue_integration_panel_refresh()

        self.assertEqual(1, len(callbacks))
        callback = callbacks[0]
        callback_refs = list(callback.__defaults__ or ())
        if callback.__closure__:
            callback_refs.extend(cell.cell_contents for cell in callback.__closure__)

        self.assertNotIn(widget, callback_refs)
        self.assertTrue(
            any(isinstance(ref, weakref.ReferenceType) and ref() is widget for ref in callback_refs)
        )

    def test_plan_controls_dispose_detaches_without_deferred_delete(self):
        class _Signal:
            def __init__(self):
                self.disconnected = False

            def disconnect(self):
                self.disconnected = True

        class _Button:
            def __init__(self):
                self.clicked = _Signal()
                self.toggled = _Signal()

        class _Combo:
            def __init__(self):
                self.currentIndexChanged = _Signal()

        class _LineEdit:
            def __init__(self):
                self.editingFinished = _Signal()
                self.returnPressed = _Signal()
                self.textChanged = _Signal()

        class _Layout:
            def __init__(self):
                self.removed = None

            def removeWidget(self, widget):
                self.removed = widget

        class _Parent:
            def __init__(self, layout):
                self._layout = layout

            def layout(self):
                return self._layout

        class _Form:
            def __init__(self, parent, button, combo, line_edit):
                self._parent = parent
                self._children = {
                    _Button: [button],
                    _Combo: [combo],
                    _LineEdit: [line_edit],
                }
                self.hidden = False
                self.parent_set_to = object()
                self.delete_later_called = False

            def findChildren(self, child_type):
                return list(self._children.get(child_type, ()))

            def parentWidget(self):
                return self._parent

            def hide(self):
                self.hidden = True

            def setParent(self, parent):
                self.parent_set_to = parent

            def deleteLater(self):
                self.delete_later_called = True

        button = _Button()
        combo = _Combo()
        line_edit = _LineEdit()
        layout = _Layout()
        form = _Form(_Parent(layout), button, combo, line_edit)

        widget = object.__new__(PlanEditControlsWidget)
        widget.form = form
        widget.session = SimpleNamespace()
        widget._integration_refresh_queued = True
        widget._integration_refresh_generation = 0
        widget._space_type_completer = None

        with patch.dict(
            sys.modules,
            {
                "PySide": SimpleNamespace(
                    QtGui=SimpleNamespace(
                        QAbstractButton=_Button,
                        QComboBox=_Combo,
                        QLineEdit=_LineEdit,
                    )
                )
            },
        ):
            widget.dispose()

        self.assertFalse(widget._integration_refresh_queued)
        self.assertEqual(1, widget._integration_refresh_generation)
        self.assertTrue(button.clicked.disconnected)
        self.assertTrue(button.toggled.disconnected)
        self.assertTrue(combo.currentIndexChanged.disconnected)
        self.assertTrue(line_edit.editingFinished.disconnected)
        self.assertTrue(line_edit.returnPressed.disconnected)
        self.assertTrue(line_edit.textChanged.disconnected)
        self.assertIs(layout.removed, form)
        self.assertTrue(form.hidden)
        self.assertIsNone(form.parent_set_to)
        self.assertFalse(form.delete_later_called)
        self.assertIsNone(widget.form)
        self.assertIsNone(widget.session)
        widget._run_queued_integration_panel_refresh(widget._integration_refresh_generation)

    def test_provider_target_record_uses_provider_metadata(self):
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="PlanDoc"),
        )
        provider_target = PlanProviderTargetSpec(
            key="electrical-fixture:PlanDoc:Socket001",
            label="Kitchen Socket",
            provider_id="materia-electrical-fixtures",
            document_name="PlanDoc",
            object_name="Socket001",
            semantic_document_name="PlanDoc",
            semantic_object_name="Socket001",
            category="electrical",
            role="fixture",
        )
        session = SimpleNamespace(
            selection=SimpleNamespace(
                get_plan_target_kind_for_object=lambda obj: "provider" if obj is marker else None,
                get_plan_target_state_key=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
            visibility=SimpleNamespace(get_plan_semantic_object=lambda obj: obj),
            providers=SimpleNamespace(
                get_plan_provider_target_for_object=lambda obj: (
                    provider_target if obj is marker else None
                )
            ),
            resolve_plan_semantic_object=lambda target: (
                marker if target == provider_target else None
            ),
        )

        self.assertEqual(("provider", marker), get_plan_target_for_object(session, marker))

        record = make_plan_target_record(session, "provider", marker)
        self.assertEqual("Kitchen Socket", record.label)
        self.assertEqual("materia-electrical-fixtures", record.provider_id)
        self.assertEqual("electrical-fixture:PlanDoc:Socket001", record.target_key)
        self.assertEqual("electrical", record.category)
        self.assertEqual("fixture", record.role)

    def test_get_plan_provider_target_for_object_matches_document_identity(self):
        marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="PlanDoc"),
        )
        other_marker = SimpleNamespace(
            Name="Socket001",
            Label="Socket 001",
            Document=SimpleNamespace(Name="OtherDoc"),
        )
        provider_target = PlanProviderTargetSpec(
            key="electrical-fixture:PlanDoc:Socket001",
            provider_id="materia-electrical-fixtures",
            document_name="PlanDoc",
            object_name="Socket001",
        )
        session = SimpleNamespace(
            doc=SimpleNamespace(Name="PlanDoc"),
            _plan_provider_refresh_cache={},
            get_plan_provider_targets=lambda: (provider_target,),
        )

        self.assertIs(provider_target, get_plan_provider_target_for_object(session, marker))
        self.assertIsNone(get_plan_provider_target_for_object(session, other_marker))

    def test_registry_preserves_provider_order_and_replacement(self):
        registry = PlanEditRegistry()
        first = _DummyProvider("first")
        second = _DummyProvider("second")
        replacement = _DummyProvider("first")

        registry.register_provider(first)
        registry.register_provider(second)
        registry.register_provider(replacement)

        self.assertEqual(("first", "second"), registry.provider_ids())
        self.assertEqual((replacement, second), registry.iter_providers())
        self.assertIs(replacement, registry.get_provider("first"))

        removed = registry.unregister_provider("second")
        self.assertIs(removed, second)
        self.assertEqual(("first",), registry.provider_ids())

    def test_plan_issue_spec_carries_generic_presentation_hints(self):
        issue = PlanIssueSpec(
            key="missing-generated-output",
            title="Missing generated output",
            severity=PlanIssueSeverity.WARNING,
            role="workflow",
            category="MEP",
            group_key="mep-generation",
            group_title="Generate MEP output",
            collapsed=True,
            summary="Generated output is missing.",
        )

        self.assertEqual("workflow", issue.role)
        self.assertEqual("MEP", issue.category)
        self.assertEqual("mep-generation", issue.group_key)
        self.assertEqual("Generate MEP output", issue.group_title)
        self.assertTrue(issue.collapsed)
        self.assertEqual("Generated output is missing.", issue.summary)
        self.assertEqual(PlanIssueSeverity.WARNING, issue.severity)

    def test_plan_edit_transaction_commits_on_success_and_aborts_on_failure(self):
        doc = _DummyDoc()
        with PlanEditTransaction(doc, "Apply Plan Edit Change"):
            pass
        self.assertEqual(
            [("open", "Apply Plan Edit Change"), ("commit", None)],
            doc.events,
        )

        doc = _DummyDoc()
        with self.assertRaises(RuntimeError):
            with PlanEditTransaction(doc, "Apply Plan Edit Change"):
                raise RuntimeError("boom")
        self.assertEqual(
            [("open", "Apply Plan Edit Change"), ("abort", None)],
            doc.events,
        )
