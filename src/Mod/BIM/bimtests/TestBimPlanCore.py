# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import ExitStack, contextmanager, nullcontext
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

from bimplan.providers import PlanProviderActionContext
from bimplan.tools.space_interaction import activate_plan_region_tool, activate_space_separator_tool
from bimplan.overlays import providers as provider_overlays
from bimplan import task_panel as plan_task_panel_module
from bimplan.picking.coordinator import get_plan_target_at_position
from bimplan.picking.hover import get_hovered_plan_target
from bimplan.picking.overlays import (
    pick_plan_opening_target_from_overlays,
    pick_plan_symbol_target_from_overlays,
)
from bimplan.providers.picking import (
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
from bimplan.providers import runtime as plan_provider_runtime_module
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
from bimplan.selection import (
    activate_opening_target,
    activate_semantic_plan_target,
    resolve_selected_target_for_gui_object,
)
from bimplan.selection import selection as plan_selection_module
from bimplan.selection import gui_sync as plan_selection_gui_sync
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.tools.spaces import (
    start_space_region_pick,
    create_space_from_current_selection,
    build_space_creation_request,
    resolve_space_region_seed_targets,
    should_run_space_preflight_for_targets,
)
from bimplan.selection.targets import get_plan_target_for_object, make_plan_target_record
from bimplan.transactions import PlanEditTransaction
from bimplan.ui.controls import PlanEditControlsWidget
from bimplan.ui import control_shell as plan_control_shell
from bimplan.task_panel_view_model import (
    ProviderOverlayLegendItem,
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


def _make_lifecycle_state_stub(**kwargs):
    return SimpleNamespace(
        **{
            "tearing_down": False,
            "finishing": False,
            "ignore_selection_changes": False,
            **kwargs,
        }
    )


def _make_hover_pick_state_stub(**kwargs):
    return SimpleNamespace(**{"last_mouse_pos": None, "dirty": False, **kwargs})


def _make_selection_sync_state_stub(**kwargs):
    return SimpleNamespace(
        **{
            "gui_selection_sync_in_progress": False,
            "selection_observer_added": False,
            **kwargs,
        }
    )


def _make_provider_runtime_state_stub(**kwargs):
    return SimpleNamespace(
        **{
            "refresh_cache": {},
            "document_cache": {},
            "target_collection_depth": 0,
            **kwargs,
        }
    )


def _make_provider_overlay_read_state_stub(**kwargs):
    return SimpleNamespace(
        **{
            "mode": "architecture",
            "visibility": {},
            "render_state": None,
            **kwargs,
        }
    )


def _make_provider_transient_state_stub(**kwargs):
    return SimpleNamespace(**{"provider_selected_objects": [], **kwargs})


def _make_plan_target_ref(kind=None, obj=None):
    return plan_target_kinds.make_plan_target_ref(kind, obj)


def _make_selection_state_stub(
    selected_target=None,
    *,
    selected_targets=None,
    selected_objects=None,
    calls=None,
    valid=True,
):
    selected_ref = plan_target_kinds.coerce_plan_target_ref(selected_target)
    if selected_targets is None:
        selected_target_refs = (selected_ref,) if selected_ref.obj is not None else ()
    else:
        selected_target_refs = tuple(
            plan_target_kinds.coerce_plan_target_ref(target) for target in selected_targets
        )
    selected_objects = dict(selected_objects or {})
    calls = calls if calls is not None else []

    def get_selected_plan_target_object(kind=None):
        if kind in selected_objects:
            return selected_objects[kind]
        if kind is not None and selected_ref.kind != kind:
            return None
        return selected_ref.obj

    return SimpleNamespace(
        get_selected_plan_target=lambda: selected_ref,
        get_selected_plan_targets=lambda: selected_target_refs,
        get_selected_plan_target_object=get_selected_plan_target_object,
        set_selected_plan_target=lambda *args, **kwargs: calls.append(
            ("set-selected", args, kwargs)
        ),
        set_selected_plan_target_state=lambda *args, **kwargs: calls.append(
            ("set-selected-state", args, kwargs)
        ),
        is_valid_plan_target=lambda _kind, _obj: bool(valid),
    )


def _make_selection_stub(
    selected_target=None,
    *,
    selected_targets=None,
    hovered_target=None,
    picked_target=None,
    selected_objects=None,
    calls=None,
    valid=True,
):
    calls = calls if calls is not None else []
    hovered_ref = plan_target_kinds.coerce_plan_target_ref(hovered_target)
    picked_ref = plan_target_kinds.coerce_plan_target_ref(picked_target)
    return SimpleNamespace(
        state=_make_selection_state_stub(
            selected_target,
            selected_targets=selected_targets,
            selected_objects=selected_objects,
            calls=calls,
            valid=valid,
        ),
        hover=SimpleNamespace(
            get_hovered_plan_target=lambda: hovered_ref,
            clear_hovered_plan_targets=lambda *args, **kwargs: calls.append(
                ("clear-hovered", args, kwargs)
            ),
        ),
        picking=SimpleNamespace(
            get_plan_target_at_position=lambda _mouse_pos: picked_ref,
        ),
        refresh=SimpleNamespace(
            sanitize_plan_target_references=lambda: calls.append("sanitize"),
            refresh_primary_selected_plan_target=lambda *args, **kwargs: calls.append(
                ("refresh-primary", args, kwargs)
            ),
        ),
        clear_selected_visuals=lambda *args, **kwargs: calls.append(
            ("clear-selected-visuals", args, kwargs)
        ),
    )


@contextmanager
def _patched_plan_target_overlay_pickers(**overrides):
    defaults = {
        "pick_provider_overlay_target_from_overlays": (
            lambda *_args, **_kwargs: _make_plan_target_ref()
        ),
        "pick_plan_opening_target_from_overlays": (lambda *_args, **_kwargs: None),
        "pick_plan_symbol_target_from_overlays": (lambda *_args, **_kwargs: None),
        "pick_plan_region_target_from_polylines": (lambda *_args, **_kwargs: None),
        "pick_plan_region_target_from_footprints": (lambda *_args, **_kwargs: None),
        "pick_plan_region_target_from_overlays": (lambda *_args, **_kwargs: None),
        "pick_plan_space_target_from_footprints": (lambda *_args, **_kwargs: None),
        "pick_plan_space_target_from_overlays": (lambda *_args, **_kwargs: None),
    }
    defaults.update(overrides)
    with ExitStack() as stack:
        for name, replacement in defaults.items():
            stack.enter_context(
                patch(
                    f"bimplan.picking.coordinator.{name}",
                    side_effect=replacement,
                )
            )
        yield


@contextmanager
def _patched_space_boundary_links_from_session():
    def _get_links(session, fallback_space=None):
        return session.spaces.get_selected_space_boundary_links(fallback_space=fallback_space)

    with patch(
        "bimplan.tools.space_boundaries.get_selected_space_boundary_links",
        side_effect=_get_links,
    ):
        yield


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
            lifecycle_state=_make_lifecycle_state_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(refresh_cache={}),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            performance=_make_perf_stub(
                trace_span=lambda _name: nullcontext(),
                count=lambda name, value=1: perf_counts.append((name, value)),
            ),
            selection=_make_selection_stub(),
        )
        session.document_visuals = SimpleNamespace(document_is_alive=lambda: True)
        session.providers = SimpleNamespace(
            get_plan_provider_registry=lambda: registry,
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
            providers=SimpleNamespace(
                get_plan_provider_overlay_mode=lambda: "electrical",
                get_plan_provider_display_name=lambda provider_id: (
                    "Provider A" if provider_id == "provider-a" else provider_id
                ),
                get_plan_provider_overlay_category=lambda overlay: str(
                    getattr(overlay, "category", "") or "architecture"
                ),
                is_plan_provider_overlay_enabled=lambda overlay: overlay.key != "arch-overlay",
            ),
        )

        view_model = build_integration_panel_view_model(session, snapshot)

        self.assertTrue(view_model.has_content)
        self.assertEqual(("tool-a", "tool-b"), tuple(tool.key for tool in view_model.tools))
        self.assertEqual("electrical", view_model.overlay_mode)
        self.assertEqual(
            ("elec-overlay",), tuple(item.overlay_key for item in view_model.active_overlay_items)
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
        selection = _make_selection_stub(("wall", wall))
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
        selection = _make_selection_stub(("wall", wall))
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
            selection=_make_selection_stub(("space", space)),
        )
        region_session = SimpleNamespace(
            current_tool="Select",
            selection=_make_selection_stub(("region", region)),
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
            selection=_make_selection_stub(("opening", window)),
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

    def test_activate_plan_region_tool_uses_shared_space_setup(self):
        parent_space = SimpleNamespace(Name="Space001")
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _set_selected_plan_target=lambda *args, **kwargs: None,
            _clear_hovered_plan_targets=lambda *args, **kwargs: None,
            task_panels=SimpleNamespace(refresh_task_panel_status=lambda *args, **kwargs: None),
            wall_create=SimpleNamespace(cancel_rect_wall_tool=lambda refresh=False: None),
            providers=SimpleNamespace(cancel_provider_point_tool=lambda refresh=False: None),
            wall_relations=SimpleNamespace(clear_plan_relation_status=lambda: None),
            embedded_tools=SimpleNamespace(has_active=lambda: False, cancel=lambda: None),
            interaction_state=SimpleNamespace(embedded_tool=None),
            lifecycle=SimpleNamespace(
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
            selection=_make_selection_stub(
                ("space", parent_space),
                selected_objects={"space": parent_space},
                calls=calls,
            ),
        )

        with patch(
            "bimplan.tools.space_interaction.prepare_plan_region_tool_state"
        ) as prepare, patch("bimplan.tools.space_interaction._start_snap_tool", return_value=True):
            self.assertTrue(activate_plan_region_tool(session))

        prepare.assert_called_once_with(session, parent_space=parent_space)

    def test_activate_space_separator_tool_uses_shared_space_setup(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _set_selected_plan_target=lambda *args, **kwargs: None,
            task_panels=SimpleNamespace(refresh_task_panel_status=lambda *args, **kwargs: None),
            wall_create=SimpleNamespace(
                cancel_rect_wall_tool=lambda refresh=False: None,
                get_wall_defaults=lambda: {"height": 2500},
            ),
            providers=SimpleNamespace(cancel_provider_point_tool=lambda refresh=False: None),
            wall_relations=SimpleNamespace(clear_plan_relation_status=lambda: None),
            embedded_tools=SimpleNamespace(has_active=lambda: False, cancel=lambda: None),
            interaction_state=SimpleNamespace(embedded_tool=None),
            lifecycle=SimpleNamespace(
                cancel_pending_edit=lambda: None,
            ),
            windows=SimpleNamespace(cancel_window_tool=lambda refresh=False: None),
            wall_edit=SimpleNamespace(cancel_wall_edit=lambda restore=True, refresh=True: None),
            spaces=SimpleNamespace(
                cancel_space_region_pick=lambda refresh=False: None,
                cancel_plan_region_tool=lambda refresh=False: None,
                handle_space_separator_point=lambda *args, **kwargs: None,
            ),
            selection=_make_selection_stub(calls=calls),
        )

        with patch(
            "bimplan.tools.space_interaction.prepare_space_separator_tool_state"
        ) as prepare, patch(
            "bimplan.tools.space_interaction._start_snap_tool",
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
            selection=_make_selection_stub(selected_targets=(("wall", wall_a), ("wall", wall_b))),
        )
        arch_module = SimpleNamespace(
            makeSpace=lambda value: events.append(("make-space", value)) or created_space
        )
        archspace_module = SimpleNamespace(
            analyzeBoundaryLinks=lambda value: events.append(("analyze", value)) or {}
        )

        with patch.dict(
            sys.modules, {"Arch": arch_module, "ArchSpace": archspace_module}
        ), _patched_space_boundary_links_from_session():
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

    def test_start_space_region_pick_auto_creates_single_remaining_candidate(self):
        candidate = {"area": 12.0}
        created_space = SimpleNamespace(Name="Space001")
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            space_region_pick_state=SimpleNamespace(
                boundaries=[],
                candidates=[],
                hovered_candidate=None,
                seed_space=None,
            ),
            visibility=SimpleNamespace(
                register_plan_object=lambda space: calls.append(("register", space))
            ),
            selection=SimpleNamespace(
                clear_hovered_plan_targets=lambda **kwargs: calls.append(("clear-hovered", kwargs)),
                refresh_primary_selected_plan_target=lambda: calls.append("refresh-primary"),
            ),
            spaces=SimpleNamespace(
                restore_selected_space=lambda space: calls.append(("restore", space)),
                create_space_from_region_candidate=lambda *args, **kwargs: (
                    calls.append(("create", args, kwargs)) or created_space
                ),
            ),
            overlays=SimpleNamespace(
                spaces=SimpleNamespace(
                    clear_space_region_pick_overlays=lambda: calls.append("clear-pick-overlays"),
                ),
                walls=SimpleNamespace(clear_wall_grips=lambda: calls.append("clear-wall-grips")),
            ),
        )
        boundaries = [("Boundary001", ("Face1",))]
        report = {
            "candidates": [candidate],
            "candidate_count": 1,
            "skipped_claimed_candidate_count": 1,
        }

        with patch("FreeCAD.Console.PrintMessage") as print_message:
            self.assertTrue(start_space_region_pick(session, boundaries, report=report))

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
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    boundaries if fallback_space is None else ()
                )
            ),
            selection=_make_selection_stub(selected_targets=(("wall", wall_a), ("wall", wall_b))),
        )

        with _patched_space_boundary_links_from_session():
            request = build_space_creation_request(session)

        self.assertTrue(
            should_run_space_preflight_for_targets([("wall", wall_a), ("wall", wall_b)])
        )
        self.assertEqual(boundaries, tuple(request["boundaries"]))
        self.assertIsNone(request["region_seed_space"])

    def test_space_region_seed_targets_require_boundaries_for_single_space(self):
        space = SimpleNamespace(Name="Space001", Label="Living Room")
        boundary = (SimpleNamespace(Name="Divider"), ("Face1",))

        empty_session = SimpleNamespace(
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: []
            ),
            selection=_make_selection_stub(selected_targets=(("space", space),)),
        )
        with _patched_space_boundary_links_from_session():
            self.assertEqual((None, []), resolve_space_region_seed_targets(empty_session))
            self.assertIsNone(build_space_creation_request(empty_session))

        seeded_session = SimpleNamespace(
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    [boundary] if fallback_space is space else []
                )
            ),
            selection=_make_selection_stub(selected_targets=(("space", space),)),
        )
        with _patched_space_boundary_links_from_session():
            self.assertEqual((space, []), resolve_space_region_seed_targets(seeded_session))
            request = build_space_creation_request(seeded_session)
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
            spaces=SimpleNamespace(
                get_selected_space_boundary_links=lambda fallback_space=None: (
                    [boundary] if fallback_space is space else []
                )
            ),
            selection=_make_selection_stub(selected_targets=targets),
        )

        self.assertTrue(should_run_space_preflight_for_targets(targets))
        with _patched_space_boundary_links_from_session():
            self.assertEqual((space, [("wall", wall)]), resolve_space_region_seed_targets(session))
            request = build_space_creation_request(session)
        self.assertIsNotNone(request)
        self.assertIs(space, request["region_seed_space"])
        self.assertEqual([boundary], request["boundaries"])

    def test_activate_opening_target_uses_behavior_policy(self):
        calls = []
        target = SimpleNamespace(Name="Opening001")
        session = SimpleNamespace()

        with patch(
            "bimplan.selection.selection.plan_selection_activation.activate_plan_target",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
        ):
            self.assertTrue(
                activate_opening_target(session, (100, 200), resolved_target=("opening", target))
            )

        self.assertEqual(
            [
                (
                    (session, "opening", (100, 200)),
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
            selection=_make_selection_stub(hovered_target=("wall", target)),
            hover_pick_state=_make_hover_pick_state_stub(last_mouse_pos=(50.0, 60.0)),
            performance=_make_perf_stub(),
        )

        with patch(
            "bimplan.selection.selection.plan_selection_activation.activate_plan_target",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
        ):
            self.assertTrue(activate_semantic_plan_target(session, (50, 60)))

        self.assertEqual(
            [
                (
                    (session, "wall", (50, 60)),
                    {
                        "event_callback": None,
                        "sync_gui_selection": True,
                        "clear_hovered_kinds": ("wall", "symbol", "space", "region"),
                        "resolved_target": _make_plan_target_ref("wall", target),
                        "defer_gui_selection": True,
                        "defer_wall_grips": True,
                    },
                )
            ],
            calls,
        )

    def test_activate_semantic_plan_target_repicks_when_hover_position_mismatches(self):
        calls = []
        hovered = SimpleNamespace(Name="Wall001")
        picked = SimpleNamespace(Name="Wall002")
        session = SimpleNamespace(
            selection=_make_selection_stub(
                hovered_target=("wall", hovered),
                picked_target=("wall", picked),
            ),
            picking=SimpleNamespace(
                pick=lambda _mouse_pos: _make_plan_target_ref("wall", picked),
            ),
            hover_pick_state=_make_hover_pick_state_stub(last_mouse_pos=(10.0, 10.0)),
            performance=_make_perf_stub(),
        )

        with patch(
            "bimplan.selection.selection.plan_selection_activation.activate_plan_target",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
        ):
            self.assertTrue(activate_semantic_plan_target(session, (50, 60)))

        self.assertEqual(
            [
                (
                    (session, "wall", (50, 60)),
                    {
                        "event_callback": None,
                        "sync_gui_selection": True,
                        "clear_hovered_kinds": ("wall", "symbol", "space", "region"),
                        "resolved_target": _make_plan_target_ref("wall", picked),
                        "defer_gui_selection": True,
                        "defer_wall_grips": True,
                    },
                )
            ],
            calls,
        )

    def test_plan_provider_action_context_exposes_typed_target_payloads(self):
        from bimplan.providers.host_targets import ProviderHostTargetRef
        from bimplan.providers.payloads import ProviderPointActionPayload
        from bimplan.selection.target_kinds import PlanTargetRef

        wall = object()
        opening = object()
        context = PlanProviderActionContext(
            _session=SimpleNamespace(doc=None),
            payload=ProviderPointActionPayload(
                tool=object(),
                point=(1.0, 2.0, 0.0),
                placement_point=(1.0, 2.0, 0.0),
                raw_point=(1.0, 2.0, 0.0),
                snap_info={},
                snap_object=wall,
                snap_target=PlanTargetRef("wall", wall),
                snap_document_name="PlanDoc",
                snap_object_name="Wall001",
                snap_component="Edge1",
                snap_subname="Edge1",
                selected_target=PlanTargetRef("opening", opening),
                selected_targets=(PlanTargetRef("opening", opening),),
                hovered_target=PlanTargetRef("wall", wall),
                host_target=ProviderHostTargetRef("wall", wall),
                host_source="selected",
            ),
            document_name="PlanDoc",
            current_tool="Provider Point",
        )

        self.assertEqual(PlanTargetRef("opening", opening), context.get_selected_target())
        self.assertEqual((PlanTargetRef("opening", opening),), context.get_selected_targets())
        self.assertEqual(PlanTargetRef("wall", wall), context.get_hovered_target())
        self.assertEqual(PlanTargetRef("wall", wall), context.get_snap_target())
        self.assertEqual(ProviderHostTargetRef("wall", wall), context.get_host_target())
        self.assertEqual((1.0, 2.0, 0.0), context.get_point())
        self.assertEqual((1.0, 2.0, 0.0), context.get_placement_point())
        self.assertEqual((1.0, 2.0, 0.0), context.get_raw_point())
        self.assertEqual({}, context.get_snap_info())
        self.assertIs(wall, context.get_snap_object())
        self.assertEqual("selected", context.get_host_source())

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
            selection=SimpleNamespace(
                refresh=SimpleNamespace(refresh_primary_selected_plan_target=lambda: None)
            ),
            document_visuals=SimpleNamespace(
                document_is_alive=lambda: True,
                defer_document_visual_updates=lambda: nullcontext(),
                invalidate_document_dependent_plan_visuals=lambda: None,
            ),
            task_panels=SimpleNamespace(refresh_task_panel_status=lambda *args, **kwargs: None),
            providers=SimpleNamespace(
                get_plan_provider_registry=lambda: registry,
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
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            providers=SimpleNamespace(
                plan_provider_refresh_cache_scope=lambda: nullcontext(),
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
            ),
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
            selection=_make_selection_stub(valid=False),
        )
        point = SimpleNamespace(
            documentName=_Field(""),
            objectName=_Field("Socket001"),
            subElementName=_Field("ProviderOverlayPoint:object:0"),
        )

        with patch(
            "bimplan.providers.picking.plan_targets.get_plan_target_for_object",
            return_value=(None, None),
        ):
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
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            providers=SimpleNamespace(
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
            ),
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
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            providers=SimpleNamespace(
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
            ),
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
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            providers=SimpleNamespace(
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
            ),
            performance=_make_perf_stub(),
        )

        self.assertEqual(
            ("object", marker),
            pick_provider_overlay_target_from_objects_info(session, (100, 200)),
        )

    def test_pick_plan_symbol_target_from_overlays_skips_symbols_outside_screen_bounds(self):
        symbol = SimpleNamespace(Name="Symbol001", Document=SimpleNamespace(Name="TestDoc"))
        session = SimpleNamespace(
            doc=SimpleNamespace(Name="TestDoc"),
            view=SimpleNamespace(),
            overlays=SimpleNamespace(
                symbols=SimpleNamespace(
                    get_plan_symbol_instances=lambda: (symbol,),
                    get_symbol_overlay_screen_bounds=lambda _symbol: (
                        300.0,
                        300.0,
                        360.0,
                        360.0,
                    ),
                    get_symbol_overlay_screen_polylines=lambda _symbol: (_ for _ in ()).throw(
                        AssertionError("screen polylines should not be requested")
                    ),
                    get_symbol_overlay_segments=lambda _symbol: (_ for _ in ()).throw(
                        AssertionError("segments should not be requested")
                    ),
                ),
            ),
            visibility=SimpleNamespace(is_plan_symbol_instance=lambda obj: obj is symbol),
            performance=_make_perf_stub(),
        )

        self.assertIsNone(pick_plan_symbol_target_from_overlays(session, (100, 100), radius_px=10))

    def test_pick_plan_opening_target_from_overlays_skips_openings_outside_screen_bounds(self):
        opening = SimpleNamespace(Name="Window001", Document=SimpleNamespace(Name="TestDoc"))
        session = SimpleNamespace(
            doc=SimpleNamespace(Name="TestDoc"),
            view=SimpleNamespace(),
            viewport=SimpleNamespace(
                get_plan_point_from_mouse_pos=lambda _mouse_pos: FreeCAD.Vector()
            ),
            overlays=SimpleNamespace(
                geometry=SimpleNamespace(
                    get_opening_overlay_screen_bounds=lambda _opening: (
                        300.0,
                        300.0,
                        360.0,
                        360.0,
                    ),
                    get_opening_overlay_screen_polylines=lambda _opening: (_ for _ in ()).throw(
                        AssertionError("screen polylines should not be requested")
                    ),
                ),
            ),
            openings=SimpleNamespace(
                is_hosted_opening_object=lambda obj: obj is opening,
                get_plan_opening_instances=lambda: (opening,),
            ),
            performance=_make_perf_stub(),
        )

        with patch(
            "bimplan.picking.overlays.should_skip_opening_by_plan_bounds",
            return_value=False,
        ):
            self.assertIsNone(
                pick_plan_opening_target_from_overlays(session, (100, 100), radius_px=10)
            )

    def test_pick_plan_opening_target_from_overlays_uses_overlay_pick_bounds_not_shape_bounds(self):
        invalid_bound_box = SimpleNamespace(
            XMin=1.7976931348623157e308,
            YMin=1.7976931348623157e308,
            XMax=-1.7976931348623157e308,
            YMax=-1.7976931348623157e308,
        )
        opening = SimpleNamespace(
            Name="Window001",
            Document=SimpleNamespace(Name="TestDoc"),
            Shape=SimpleNamespace(BoundBox=invalid_bound_box),
        )
        session = SimpleNamespace(
            doc=SimpleNamespace(Name="TestDoc"),
            view=SimpleNamespace(),
            viewport=SimpleNamespace(
                get_plan_point_from_mouse_pos=lambda _mouse_pos: FreeCAD.Vector(100.0, 100.0, 0.0),
                get_plan_view_units_per_pixel=lambda: 1.0,
            ),
            overlays=SimpleNamespace(
                geometry=SimpleNamespace(
                    get_opening_pick_bounds=lambda _opening: (50.0, 50.0, 150.0, 150.0),
                    get_opening_overlay_screen_bounds=lambda _opening: (
                        90.0,
                        90.0,
                        110.0,
                        110.0,
                    ),
                    get_opening_overlay_screen_polylines=lambda _opening: (
                        ((95.0, 100.0), (105.0, 100.0)),
                    ),
                ),
            ),
            openings=SimpleNamespace(
                is_hosted_opening_object=lambda obj: obj is opening,
                get_plan_opening_instances=lambda: (opening,),
            ),
            performance=_make_perf_stub(),
        )

        self.assertIs(
            pick_plan_opening_target_from_overlays(session, (100, 100), radius_px=10),
            opening,
        )

    def test_get_plan_target_at_position_falls_back_to_global_opening_pick_when_first_wall_misses(
        self,
    ):
        wall_a = SimpleNamespace(
            Name="WallA",
            Label="Wall A",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        wall_b = SimpleNamespace(
            Name="WallB",
            Label="Wall B",
            Document=SimpleNamespace(Name="TestDoc"),
        )
        opening = SimpleNamespace(
            Name="Window001",
            Label="Opening 001",
            Document=SimpleNamespace(Name="TestDoc"),
        )

        doc = SimpleNamespace(
            Name="TestDoc",
            getObject=lambda name: {
                wall_a.Name: wall_a,
                wall_b.Name: wall_b,
                opening.Name: opening,
            }.get(name),
        )
        sys.modules["FreeCAD"].getDocument = lambda name: doc if name == doc.Name else None

        class _View:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {"Document": doc.Name, "Object": wall_a.Name},
                    {"Document": doc.Name, "Object": wall_b.Name},
                )

        opening_pick_calls = []

        def _pick_opening(_session, _mouse_pos, candidates=None, **_kwargs):
            opening_pick_calls.append(candidates)
            if candidates is not None:
                return None
            return opening

        def _get_plan_pick_target_for_object(_session, obj, parent_obj=None):
            del parent_obj
            if obj is wall_a:
                return ("wall", wall_a)
            if obj is wall_b:
                return ("wall", wall_b)
            return (None, None)

        session = SimpleNamespace(
            doc=doc,
            view=_View(),
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "all"),
            selection=SimpleNamespace(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
                pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
                pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
                pick_plan_space_target_from_footprints=lambda *args, **kwargs: None,
                pick_plan_space_target_from_overlays=lambda *args, **kwargs: None,
            ),
            openings=SimpleNamespace(
                get_wall_hosted_openings=lambda wall: () if wall is wall_a else (opening,)
            ),
            performance=_make_perf_stub(
                describe_target=lambda kind, obj: (kind, getattr(obj, "Name", "")),
            ),
        )

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                side_effect=_get_plan_pick_target_for_object,
            ),
            _patched_plan_target_overlay_pickers(
                pick_plan_opening_target_from_overlays=_pick_opening,
            ),
        ):
            target_ref = get_plan_target_at_position(session, (100, 200))

        self.assertEqual("opening", target_ref.kind)
        self.assertIs(opening, target_ref.obj)
        self.assertEqual([(), None], opening_pick_calls)

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
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "all"),
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

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                return_value=("space", space),
            ),
            _patched_plan_target_overlay_pickers(
                pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (
                    _make_plan_target_ref("provider", marker)
                ),
                pick_plan_space_target_from_footprints=lambda *_args, **_kwargs: space,
                pick_plan_space_target_from_overlays=lambda *_args, **_kwargs: space,
            ),
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
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "electrical"),
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

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                side_effect=_get_plan_pick_target_for_object,
            ),
            _patched_plan_target_overlay_pickers(),
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
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "all"),
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

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                side_effect=_get_plan_pick_target_for_object,
            ),
            _patched_plan_target_overlay_pickers(),
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
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "electrical"),
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

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                return_value=("space", space),
            ),
            _patched_plan_target_overlay_pickers(
                pick_plan_space_target_from_footprints=lambda *_args, **_kwargs: space,
                pick_plan_space_target_from_overlays=lambda *_args, **_kwargs: space,
            ),
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
            providers=SimpleNamespace(get_plan_provider_overlay_mode=lambda: "electrical"),
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

        with (
            patch(
                "bimplan.picking.coordinator.plan_targets.get_plan_pick_target_for_object",
                return_value=("space", space),
            ),
            _patched_plan_target_overlay_pickers(
                pick_plan_space_target_from_footprints=lambda *_args, **_kwargs: space,
                pick_plan_space_target_from_overlays=lambda *_args, **_kwargs: space,
            ),
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
            selection=_make_selection_stub(valid=True),
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
            selection=_make_selection_stub(valid=True),
        )

        with patch(
            "bimplan.selection.selection.plan_selection_gui_sync.is_visible_provider_target_object",
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
            ProviderOverlayLegendItem(
                provider_id="test-provider",
                overlay_key="provider-preview",
                label="Provider Preview",
                color=(0.1, 0.2, 0.3),
                enabled=True,
                category="architecture",
            ),
            ProviderOverlayLegendItem(
                provider_id="test-provider",
                overlay_key="electrical-preview",
                label="Electrical Preview",
                color=(0.9, 0.6, 0.1),
                enabled=True,
                category="electrical",
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

    def test_selection_refresh_skips_static_integration_panel_for_wall_selection(self):
        widget = object.__new__(PlanEditControlsWidget)
        widget.form = object()
        widget.status = object()
        widget.exit_button = object()
        widget._integration_refresh_queued = True
        widget._integration_refresh_generation = 0
        widget._integration_panel_state = PlanProviderSnapshot(
            tools=(SimpleNamespace(key="tool"),),
            overlays=(SimpleNamespace(key="overlay"),),
        )

        refresh_calls = []
        cancel_calls = []

        widget.session = SimpleNamespace(
            current_tool="Select",
            performance=SimpleNamespace(
                plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext()
            ),
            selection=_make_selection_stub(("wall", object())),
            interaction=SimpleNamespace(is_modal_plan_interaction_active=lambda: False),
            status_text=SimpleNamespace(get_provider_selected_objects=lambda: ()),
        )
        widget._set_status_text = lambda _text: None
        widget._refresh_action_context = lambda: None
        widget._refresh_integration_panel = lambda defer=False: refresh_calls.append(bool(defer))
        widget._cancel_queued_integration_panel_refresh = lambda: cancel_calls.append(True)
        widget._hide_space_editor = lambda: None
        widget._hide_region_editor = lambda: None
        widget._hide_window_editor = lambda: None
        widget._apply_modal_interaction_state = lambda _active: None

        with patch.object(
            plan_control_shell.plan_task_panel_view_model,
            "build_status_text_view_model",
            return_value=SimpleNamespace(text="wall"),
        ):
            widget.refresh_selection_from_session()

        self.assertEqual([], refresh_calls)
        self.assertEqual([True], cancel_calls)

    def test_selection_refresh_skips_dynamic_integration_panel_for_wall_selection(self):
        widget = object.__new__(PlanEditControlsWidget)
        widget.form = object()
        widget.status = object()
        widget.exit_button = object()
        widget._integration_refresh_queued = False
        widget._integration_refresh_generation = 0
        widget._integration_panel_state = PlanProviderSnapshot(
            context_panels=(SimpleNamespace(state="single_object"),),
        )

        refresh_calls = []
        cancel_calls = []

        widget.session = SimpleNamespace(
            current_tool="Select",
            performance=SimpleNamespace(
                plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext()
            ),
            selection=_make_selection_stub(("wall", object())),
            interaction=SimpleNamespace(is_modal_plan_interaction_active=lambda: False),
            status_text=SimpleNamespace(get_provider_selected_objects=lambda: ()),
        )
        widget._set_status_text = lambda _text: None
        widget._refresh_action_context = lambda: None
        widget._refresh_integration_panel = lambda defer=False: refresh_calls.append(bool(defer))
        widget._cancel_queued_integration_panel_refresh = lambda: cancel_calls.append(True)
        widget._hide_space_editor = lambda: None
        widget._hide_region_editor = lambda: None
        widget._hide_window_editor = lambda: None
        widget._apply_modal_interaction_state = lambda _active: None

        with patch.object(
            plan_control_shell.plan_task_panel_view_model,
            "build_status_text_view_model",
            return_value=SimpleNamespace(text="wall"),
        ):
            widget.refresh_selection_from_session()

        self.assertEqual([], refresh_calls)
        self.assertEqual([True], cancel_calls)

    def test_task_panel_status_refresh_dispatches_explicit_selection_reason(self):
        panel_calls = []
        lifecycle_calls = []

        session = SimpleNamespace(
            lifecycle_state=SimpleNamespace(tearing_down=False),
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            selection=SimpleNamespace(
                refresh=SimpleNamespace(
                    sanitize_plan_target_references=lambda: lifecycle_calls.append("sanitize")
                )
            ),
            status_text=SimpleNamespace(
                update_input_hints=lambda: lifecycle_calls.append("status")
            ),
            viewport=SimpleNamespace(
                refresh_viewport_status_chip=lambda: lifecycle_calls.append("viewport")
            ),
            task_panel=SimpleNamespace(
                refresh_for_session=lambda reason: panel_calls.append(reason)
            ),
            task_panel_state=SimpleNamespace(aux_task_panels=[]),
            performance=_make_perf_stub(),
            task_panels=SimpleNamespace(
                on_panel_closed=lambda _panel: None,
                detach_aux_task_panel=lambda _panel: None,
            ),
        )

        plan_task_panel_module.refresh_task_panel_status(
            session,
            reason=plan_task_panel_module.TASK_PANEL_REFRESH_SELECTION,
        )

        self.assertEqual(["sanitize", "status", "viewport"], lifecycle_calls)
        self.assertEqual([plan_task_panel_module.TASK_PANEL_REFRESH_SELECTION], panel_calls)

    def test_provider_overlay_mode_refresh_uses_reasoned_panel_dispatch(self):
        panel_calls = []
        lifecycle_calls = []

        session = SimpleNamespace(
            lifecycle_state=SimpleNamespace(tearing_down=False),
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            selection=SimpleNamespace(
                refresh=SimpleNamespace(
                    sanitize_plan_target_references=lambda: lifecycle_calls.append("sanitize")
                )
            ),
            status_text=SimpleNamespace(
                update_input_hints=lambda: lifecycle_calls.append("status")
            ),
            viewport=SimpleNamespace(
                refresh_viewport_status_chip=lambda: lifecycle_calls.append("viewport")
            ),
            task_panel=SimpleNamespace(
                refresh_for_session=lambda reason: panel_calls.append(reason)
            ),
            task_panel_state=SimpleNamespace(aux_task_panels=[]),
            performance=_make_perf_stub(),
            task_panels=SimpleNamespace(
                on_panel_closed=lambda _panel: None,
                detach_aux_task_panel=lambda _panel: None,
            ),
        )

        plan_task_panel_module.refresh_provider_overlay_mode_panels(session)

        self.assertEqual([], lifecycle_calls)
        self.assertEqual(
            [plan_task_panel_module.TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE],
            panel_calls,
        )

    def test_selection_observer_clear_skips_synthetic_gui_selection_sync(self):
        session = SimpleNamespace(
            lifecycle_state=SimpleNamespace(
                tearing_down=False,
                ignore_selection_changes=False,
            ),
            selection_sync_state=_make_selection_sync_state_stub(
                gui_selection_sync_in_progress=True
            ),
            performance=_make_perf_stub(),
        )

        with patch.object(
            session,
            "selection",
            _make_selection_stub(("wall", object())),
            create=True,
        ), patch.object(
            plan_selection_gui_sync,
            "schedule_selection_refresh",
        ) as schedule_refresh:
            plan_selection_gui_sync.selection_observer_clear(session, "TestDoc")

        schedule_refresh.assert_not_called()

    def test_provider_contributions_reuse_document_cache_for_same_context(self):
        selected_targets = []
        session = SimpleNamespace(
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            lifecycle_state=_make_lifecycle_state_stub(),
            performance=_make_perf_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(
                document_cache={},
                refresh_cache=None,
            ),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            selection=SimpleNamespace(
                state=SimpleNamespace(get_selected_plan_targets=lambda: tuple(selected_targets))
            ),
        )
        context = SimpleNamespace(
            document_name="TestDoc",
            active_storey_name="",
            current_tool="Select",
        )

        with patch.object(
            plan_provider_runtime_module,
            "_get_plan_edit_context_or_none",
            return_value=context,
        ), patch.object(
            plan_provider_runtime_module,
            "_collect_plan_provider_contributions_for_method",
            return_value=("overlay",),
        ) as collect:
            self.assertEqual(
                ("overlay",),
                collect_plan_provider_contributions(session, "get_overlays", object()),
            )
            self.assertEqual(
                ("overlay",),
                collect_plan_provider_contributions(session, "get_overlays", object()),
            )

        self.assertEqual(1, collect.call_count)

    def test_provider_contributions_cache_key_tracks_selected_targets(self):
        wall1 = SimpleNamespace(Name="Wall001", Document=SimpleNamespace(Name="TestDoc"))
        wall2 = SimpleNamespace(Name="Wall002", Document=SimpleNamespace(Name="TestDoc"))
        selected_targets = [_make_plan_target_ref("wall", wall1)]
        session = SimpleNamespace(
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            lifecycle_state=_make_lifecycle_state_stub(),
            performance=_make_perf_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(
                document_cache={},
                refresh_cache=None,
            ),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            selection=SimpleNamespace(
                state=SimpleNamespace(get_selected_plan_targets=lambda: tuple(selected_targets))
            ),
        )
        context = SimpleNamespace(
            document_name="TestDoc",
            active_storey_name="",
            current_tool="Select",
        )

        with patch.object(
            plan_provider_runtime_module,
            "_get_plan_edit_context_or_none",
            return_value=context,
        ), patch.object(
            plan_provider_runtime_module,
            "_collect_plan_provider_contributions_for_method",
            return_value=("overlay",),
        ) as collect:
            collect_plan_provider_contributions(session, "get_overlays", object())
            selected_targets[:] = [_make_plan_target_ref("wall", wall2)]
            collect_plan_provider_contributions(session, "get_overlays", object())

        self.assertEqual(2, collect.call_count)

    def test_provider_target_contributions_cache_key_ignores_selected_targets(self):
        wall1 = SimpleNamespace(Name="Wall001", Document=SimpleNamespace(Name="TestDoc"))
        wall2 = SimpleNamespace(Name="Wall002", Document=SimpleNamespace(Name="TestDoc"))
        selected_targets = [_make_plan_target_ref("wall", wall1)]
        session = SimpleNamespace(
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            lifecycle_state=_make_lifecycle_state_stub(),
            performance=_make_perf_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(
                document_cache={},
                refresh_cache=None,
            ),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            selection=SimpleNamespace(
                state=SimpleNamespace(get_selected_plan_targets=lambda: tuple(selected_targets))
            ),
        )
        context = SimpleNamespace(
            document_name="TestDoc",
            active_storey_name="Level001",
            current_tool="Select",
        )

        with patch.object(
            plan_provider_runtime_module,
            "_get_plan_edit_context_or_none",
            return_value=context,
        ), patch.object(
            plan_provider_runtime_module,
            "_collect_plan_provider_contributions_for_method",
            return_value=("target",),
        ) as collect:
            collect_plan_provider_contributions(session, "get_targets", object())
            selected_targets[:] = [_make_plan_target_ref("wall", wall2)]
            collect_plan_provider_contributions(session, "get_targets", object())

        self.assertEqual(1, collect.call_count)

    def test_provider_snapshot_reuses_document_cache_for_same_context(self):
        session = SimpleNamespace(
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            lifecycle_state=_make_lifecycle_state_stub(),
            performance=_make_perf_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(
                document_cache={},
                refresh_cache=None,
            ),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            selection=SimpleNamespace(state=SimpleNamespace(get_selected_plan_targets=lambda: ())),
        )
        context = SimpleNamespace(
            document_name="TestDoc",
            active_storey_name="",
            current_tool="Select",
        )
        calls = []

        def collect(_session, _context, method_name, _normalizer):
            calls.append(method_name)
            if method_name == "get_tools":
                return (SimpleNamespace(key="tool"),)
            if method_name == "get_overlays":
                return (SimpleNamespace(key="overlay"),)
            return ()

        with patch.object(
            plan_provider_runtime_module,
            "_get_plan_edit_context_or_none",
            return_value=context,
        ), patch.object(
            plan_provider_runtime_module,
            "_collect_plan_provider_contributions_for_method",
            side_effect=collect,
        ):
            snapshot1 = collect_plan_provider_snapshot(session)
            snapshot2 = collect_plan_provider_snapshot(session)

        self.assertEqual(
            [
                "get_tools",
                "get_overlays",
                "get_issues",
                "get_context_panels",
                "get_inspector_sections",
            ],
            calls,
        )
        self.assertEqual(snapshot1, snapshot2)
        self.assertEqual(("tool",), tuple(tool.key for tool in snapshot1.tools))

    def test_provider_target_lookup_reuses_document_cache_for_same_storey_context(self):
        target_obj = SimpleNamespace(Name="Fixture001", Document=SimpleNamespace(Name="TestDoc"))
        target = PlanProviderTargetSpec(
            key="fixture-1",
            object_name="Fixture001",
            document_name="TestDoc",
            label="Fixture 1",
            provider_id="provider-a",
        )
        session = SimpleNamespace(
            doc=SimpleNamespace(Name="TestDoc"),
            document_visuals=SimpleNamespace(document_is_alive=lambda: True),
            lifecycle_state=_make_lifecycle_state_stub(),
            provider_runtime_state=_make_provider_runtime_state_stub(
                document_cache={},
                refresh_cache=None,
            ),
            provider_overlay_read_state=_make_provider_overlay_read_state_stub(),
            provider_transient_state=_make_provider_transient_state_stub(),
            selection=SimpleNamespace(state=SimpleNamespace(get_selected_plan_targets=lambda: ())),
        )
        context = SimpleNamespace(
            document_name="TestDoc",
            active_storey_name="Level001",
            current_tool="Select",
        )

        with patch.object(
            plan_provider_runtime_module,
            "_get_plan_edit_context_or_none",
            return_value=context,
        ), patch.object(
            plan_provider_runtime_module,
            "get_plan_provider_targets",
            return_value=(target,),
        ) as get_targets:
            lookup1 = plan_provider_runtime_module._get_plan_provider_target_lookup(session)
            lookup2 = plan_provider_runtime_module._get_plan_provider_target_lookup(session)

        self.assertEqual(1, get_targets.call_count)
        self.assertIs(lookup1, lookup2)
        self.assertIs(target, lookup1[("TestDoc", "Fixture001")])

    def test_plan_controls_dispose_detaches_and_defers_delete(self):
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
        self.assertTrue(form.delete_later_called)
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
                targets=SimpleNamespace(
                    resolve_plan_semantic_object=lambda target: (
                        marker if target == provider_target else None
                    )
                )
            ),
            visibility=SimpleNamespace(get_plan_semantic_object=lambda obj: obj),
            providers=SimpleNamespace(
                get_plan_provider_target_for_object=lambda obj: (
                    provider_target if obj is marker else None
                )
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
            provider_runtime_state=_make_provider_runtime_state_stub(refresh_cache={}),
            providers=SimpleNamespace(get_plan_provider_targets=lambda: (provider_target,)),
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
