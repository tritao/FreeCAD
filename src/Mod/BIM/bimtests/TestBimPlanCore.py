# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest
import sys
from types import ModuleType, SimpleNamespace

if "FreeCAD" not in sys.modules:
    try:
        import FreeCAD  # noqa: F401
    except ModuleNotFoundError:
        freecad_module = ModuleType("FreeCAD")
        freecad_module.Qt = SimpleNamespace(
            translate=lambda _context, text: text,
        )
        sys.modules["FreeCAD"] = freecad_module

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
from bimplan.picking import get_provider_overlay_target_from_edit_node
from bimplan.provider_runtime import normalize_plan_provider_overlay
from bimplan.providers import (
    PlanEditProvider,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanOverlayTargetSpec,
)
from bimplan.registry import PlanEditRegistry
from bimplan.semantics import PlanSemanticRecord
from bimplan.targets import PlanTarget
from bimplan.transactions import PlanEditTransaction


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
            marker_kind=" diamond_filled ",
            point_targets=(
                {
                    "document_name": " PlanDoc ",
                    "object_name": " Socket001 ",
                    "target_kind": " object ",
                },
                {"object_name": "Ignored"},
            ),
        )

        normalized = normalize_plan_provider_overlay("test-provider", overlay)

        self.assertEqual("test-provider", normalized.provider_id)
        self.assertEqual(((1.0, 2.0, 3.0),), normalized.points)
        self.assertEqual("diamond", normalized.marker_kind)
        self.assertEqual(
            (
                PlanOverlayTargetSpec(
                    document_name="PlanDoc",
                    object_name="Socket001",
                    target_kind="object",
                ),
            ),
            normalized.point_targets,
        )

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
