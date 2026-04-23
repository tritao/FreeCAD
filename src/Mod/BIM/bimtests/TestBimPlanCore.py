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

from bimplan.context import PlanEditContext
from bimplan.lifecycle import activate_select_tool, begin_teardown, finish, shutdown
from bimplan.overlays import providers as provider_overlays
from bimplan.picking import (
    get_hovered_plan_target,
    get_plan_target_at_position,
    get_provider_overlay_target_from_edit_node,
    pick_provider_overlay_target_from_objects_info,
    pick_provider_overlay_target_from_overlays,
)
from bimplan.provider_runtime import (
    get_plan_provider_target_for_object,
    normalize_plan_provider_overlay,
)
from bimplan.providers import (
    PlanEditProvider,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlaySpec,
    PlanOverlayMarkerKind,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanProviderTargetSpec,
)
from bimplan.registry import PlanEditRegistry
from bimplan.semantics import PlanSemanticRecord
from bimplan.selection import (
    activate_opening_target,
    activate_semantic_plan_target,
    resolve_selected_target_for_gui_object,
)
from bimplan.spaces import (
    begin_space_region_pick,
    get_space_creation_request,
    get_space_region_seed_targets,
    should_run_space_preflight_for_targets,
)
from bimplan.target_dispatch import (
    queue_restore_selected_target,
    set_hovered_target,
    validate_plan_target,
)
from bimplan.targets import PlanTarget, get_plan_target_for_object, make_plan_target_record
from bimplan.transactions import PlanEditTransaction
from bimplan.ui.controls import PlanEditControlsWidget


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


class _DummyProvider(PlanEditProvider):
    def __init__(self, provider_id):
        self.provider_id = provider_id


class TestBimPlanCore(unittest.TestCase):
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
            _clear_space_region_pick_overlays=lambda: calls.append("clear-pick-overlays"),
            _create_space_from_region_candidate=lambda *args, **kwargs: (
                calls.append(("create", args, kwargs)) or created_space
            ),
            _register_plan_object=lambda space: calls.append(("register", space)),
            _restore_selected_space=lambda space: calls.append(("restore", space)),
            _clear_wall_grips=lambda: calls.append("clear-wall-grips"),
            _clear_hovered_plan_targets=lambda **kwargs: calls.append(("clear-hovered", kwargs)),
            _refresh_primary_selected_plan_target=lambda: calls.append("refresh-primary"),
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
            _get_selected_space_boundary_links=lambda fallback_space=None: (
                boundaries if fallback_space is None else ()
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
            _get_selected_space_boundary_links=lambda fallback_space=None: [],
        )
        self.assertEqual((None, []), get_space_region_seed_targets(empty_session))
        self.assertIsNone(get_space_creation_request(empty_session))

        seeded_session = SimpleNamespace(
            _get_selected_plan_targets=lambda: [("space", space)],
            _get_selected_space_boundary_links=lambda fallback_space=None: (
                [boundary] if fallback_space is space else []
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
            _get_selected_space_boundary_links=lambda fallback_space=None: (
                [boundary] if fallback_space is space else []
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
            _get_hovered_plan_target=lambda: ("wall", target),
            _hover_pick_dirty=False,
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_target=lambda kind, obj: (kind, getattr(obj, "Name", None)),
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
            _clear_viewport_status_chip=lambda: calls.append("chip"),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            _cancel_window_tool=lambda refresh=True: calls.append(("window", refresh)),
            _cancel_plan_region_tool=lambda refresh=True: calls.append(("plan-region", refresh)),
            _cancel_provider_point_tool=lambda refresh=True: calls.append(
                ("provider-point", refresh)
            ),
            _cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                ("wall-edit", restore, refresh)
            ),
            _cancel_pending_edit=lambda: calls.append("pending"),
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

    def test_shutdown_uses_cleanup_profile(self):
        calls = []
        panel = SimpleNamespace(
            mark_closed=lambda: calls.append("mark_closed"),
            detach=lambda: calls.append("detach"),
            close=lambda: calls.append("close"),
        )
        session = SimpleNamespace(
            _document_is_alive=lambda: True,
            _tearing_down=False,
            task_panel=panel,
            current_tool="Move Symbol",
            _clear_viewport_status_chip=lambda: calls.append("chip"),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            _cancel_space_separator_tool=lambda refresh=True: calls.append(("separator", refresh)),
            _cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                ("wall-edit", restore, refresh)
            ),
            _cancel_pending_edit=lambda: calls.append("pending"),
            _cancel_symbol_handle_point_pick=lambda: calls.append("symbol-handle"),
            restore_state=lambda: calls.append("restore-state"),
            doc=SimpleNamespace(recompute=lambda: calls.append("recompute")),
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
            _document_is_alive=lambda: True,
            _tearing_down=True,
            task_panel=None,
            current_tool="Move Symbol",
            _clear_viewport_status_chip=lambda: calls.append("chip"),
            _clear_input_hints=lambda: calls.append("hints"),
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _cancel_rect_wall_tool=lambda refresh=True: calls.append(("rect-wall", refresh)),
            _cancel_space_separator_tool=lambda refresh=True: calls.append(("separator", refresh)),
            _cancel_wall_edit=lambda restore=True, refresh=True: calls.append(
                ("wall-edit", restore, refresh)
            ),
            _cancel_pending_edit=lambda: calls.append("pending"),
            _cancel_symbol_handle_point_pick=lambda: calls.append("symbol-handle"),
            _discard_runtime_references=lambda: calls.append("discard-runtime"),
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
            _queue_restore_selected_space=lambda obj: restored.append(obj),
        )

        self.assertTrue(validate_plan_target(session, "space", target))
        self.assertTrue(queue_restore_selected_target(session, "space", target))
        self.assertEqual([target], restored)

    def test_target_dispatch_uses_policy_for_hover_sync(self):
        calls = []
        target = SimpleNamespace(Name="Opening001")
        session = SimpleNamespace(
            hovered_opening=None,
            _is_selected_plan_target=lambda kind, obj=None: False,
            _sync_selected_wall_opening_context_overlay=lambda: calls.append("context"),
            _sync_hovered_opening_overlay=lambda: calls.append("hover"),
        )

        self.assertTrue(set_hovered_target(session, "opening", target))
        self.assertIs(session.hovered_opening, target)
        self.assertEqual(["context", "hover"], calls)
        self.assertFalse(set_hovered_target(session, "opening", target))

    def test_finish_uses_current_tool_dispatch_before_fallback_actions(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Move Provider",
            _cancel_provider_handle_point_pick=lambda: calls.append("move-provider"),
            _has_active_provider_point_tool=lambda: True,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            _has_active_embedded_tool=lambda: True,
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _has_active_wall_edit=lambda: True,
            _cancel_wall_edit=lambda: calls.append("wall-edit"),
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
            _has_active_embedded_tool=lambda: True,
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _has_active_wall_edit=lambda: True,
            _cancel_wall_edit=lambda: calls.append("wall-edit"),
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
            _has_active_embedded_tool=lambda: False,
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _has_active_rect_wall_tool=lambda: False,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _has_active_wall_edit=lambda: False,
            _cancel_wall_edit=lambda: calls.append("wall-edit"),
            shutdown=lambda close_dialog=True: ("shutdown", close_dialog),
        )

        self.assertEqual(("shutdown", False), finish(session, close_dialog=False))
        self.assertEqual([], calls)

    def test_activate_select_tool_stops_after_current_tool_cancel(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Move Symbol",
            _cancel_symbol_handle_point_pick=lambda: calls.append("symbol"),
            _cancel_space_region_pick=lambda: calls.append("space-region"),
            _has_active_provider_point_tool=lambda: True,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            _has_active_embedded_tool=lambda: True,
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _has_active_window_tool=lambda: True,
            _cancel_window_tool=lambda: calls.append("window"),
            _has_active_plan_region_tool=lambda: True,
            _cancel_plan_region_tool=lambda: calls.append("plan-region"),
            _has_active_space_separator_tool=lambda: True,
            _cancel_space_separator_tool=lambda: calls.append("separator"),
            _cancel_wall_edit=lambda: calls.append("wall-edit"),
            _cancel_join_tool=lambda: calls.append("join"),
        )

        activate_select_tool(session)

        self.assertEqual(["symbol"], calls)

    def test_activate_select_tool_runs_ordered_cleanup_actions(self):
        calls = []
        session = SimpleNamespace(
            current_tool="Select",
            _cancel_symbol_handle_point_pick=lambda: calls.append("symbol"),
            _cancel_space_region_pick=lambda: calls.append("space-region"),
            _has_active_provider_point_tool=lambda: False,
            _cancel_provider_point_tool=lambda: calls.append("provider-point"),
            _has_active_embedded_tool=lambda: True,
            _cancel_embedded_tool=lambda: calls.append("embedded"),
            _has_active_rect_wall_tool=lambda: True,
            _cancel_rect_wall_tool=lambda: calls.append("rect-wall"),
            _has_active_window_tool=lambda: False,
            _cancel_window_tool=lambda: calls.append("window"),
            _has_active_plan_region_tool=lambda: True,
            _cancel_plan_region_tool=lambda: calls.append("plan-region"),
            _has_active_space_separator_tool=lambda: True,
            _cancel_space_separator_tool=lambda: calls.append("separator"),
            _cancel_wall_edit=lambda: calls.append("wall-edit"),
            _cancel_join_tool=lambda: calls.append("join"),
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
            _get_document_object_key=lambda obj: (
                getattr(getattr(obj, "Document", None), "Name", None),
                getattr(obj, "Name", None),
            ),
            _scaled_line_width=lambda width: float(width),
            _scaled_marker_size=lambda size: float(size),
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
            _get_plan_target_for_object=lambda _obj: (None, None),
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
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_object=lambda obj: getattr(obj, "Name", ""),
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
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_object=lambda obj: getattr(obj, "Name", ""),
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
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_object=lambda obj: getattr(obj, "Name", ""),
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
            _pick_provider_overlay_target_from_overlays=lambda mouse_pos, radius_px=16: (
                "provider",
                marker,
            ),
            _pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
            _pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            _get_wall_hosted_openings=lambda *_args, **_kwargs: (),
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_object=lambda obj: getattr(obj, "Name", ""),
            _plan_perf_describe_target=lambda kind, obj: (
                kind,
                getattr(obj, "Name", ""),
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
            _pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
            _pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_overlays=lambda *args, **kwargs: None,
            _get_wall_hosted_openings=lambda *_args, **_kwargs: (),
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_target=lambda kind, obj: (
                kind,
                getattr(obj, "Name", ""),
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
            _pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
            _pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_overlays=lambda *args, **kwargs: None,
            _get_wall_hosted_openings=lambda *_args, **_kwargs: (),
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_target=lambda kind, obj: (
                kind,
                getattr(obj, "Name", ""),
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
            _pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
            _pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
            _pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            _get_wall_hosted_openings=lambda *_args, **_kwargs: (),
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_target=lambda kind, obj: (
                kind,
                getattr(obj, "Name", ""),
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
            _pick_provider_overlay_target_from_overlays=lambda *_args, **_kwargs: (None, None),
            _pick_plan_opening_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_symbol_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_polylines=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_footprints=lambda *args, **kwargs: None,
            _pick_plan_region_target_from_overlays=lambda *args, **kwargs: None,
            _pick_plan_space_target_from_footprints=lambda *args, **kwargs: space,
            _pick_plan_space_target_from_overlays=lambda *args, **kwargs: space,
            _get_wall_hosted_openings=lambda *_args, **_kwargs: (),
            _plan_perf_trace_span=lambda *_args, **_kwargs: nullcontext(),
            _plan_perf_count=lambda *_args, **_kwargs: None,
            _plan_perf_set_fields=lambda **_kwargs: None,
            _plan_perf_describe_target=lambda kind, obj: (
                kind,
                getattr(obj, "Name", ""),
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
            _get_plan_target_for_object=lambda _selected: ("symbol", marker),
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
            _get_plan_target_for_object=lambda _selected: ("symbol", marker),
        )

        with patch(
            "bimplan.selection.plan_provider_targets.is_plan_provider_target_visible_for_mode",
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
        widget = object.__new__(PlanEditControlsWidget)
        widget.session = SimpleNamespace(get_plan_provider_overlay_mode=lambda: "architecture")
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
            widget._filter_provider_overlay_legend_items_for_mode(items),
        )
        self.assertEqual(
            (items[1],),
            widget._filter_provider_overlay_legend_items_for_mode(items, active_mode="electrical"),
        )
        self.assertEqual(
            items,
            widget._filter_provider_overlay_legend_items_for_mode(items, active_mode="all"),
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
            _get_plan_target_kind_for_object=lambda obj: "provider" if obj is marker else None,
            _get_plan_provider_target_for_object=lambda obj: (
                provider_target if obj is marker else None
            ),
            _get_plan_semantic_object=lambda obj: obj,
            resolve_plan_semantic_object=lambda target: (
                marker if target == provider_target else None
            ),
            _get_plan_target_state_key=lambda kind, obj: (kind, getattr(obj, "Name", "")),
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
