# SPDX-License-Identifier: LGPL-2.1-or-later

"""Generic provider contracts for semantic actions in BIM view contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from . import profiles


@dataclass(frozen=True)
class ContextualActionSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""
    handle_key: str = ""
    handle_subelement: str = ""
    source: object = None


@dataclass(frozen=True)
class ContextualToolSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""
    group: str = ""
    priority: int = 0
    interaction: object = "immediate"
    prompt: str = ""
    default_host_target: tuple = ()


@dataclass(frozen=True)
class ContextualInspectorSection:
    key: str
    title: str
    body: str = ""
    provider_id: str = ""
    actions: Tuple[ContextualActionSpec, ...] = ()
    role: str = ""
    collapsed: bool = False


@dataclass(frozen=True)
class ContextualProviderContext:
    representation_context: object
    selected_sources: tuple = ()
    view: object = None
    capabilities: tuple = ()
    profile: object = None

    def supports(self, capability):
        policy = self.profile or profiles.profile_for(self.representation_context)
        return policy.supports(capability)

    def get_selected_sources(self):
        return tuple(self.selected_sources or ())

    def get_capabilities(self, source=None):
        entries = tuple(self.capabilities or ())
        if source is None:
            return entries
        return tuple(
            capability
            for capability in entries
            if getattr(capability, "source", None) is source
        )

    def get_document(self):
        for source in self.get_selected_sources():
            document = getattr(source, "Document", None)
            if document is not None:
                return document
        return None


class ContextualProvider:
    provider_id = ""
    display_name = ""

    def get_provider_id(self):
        provider_id = str(getattr(self, "provider_id", "") or "").strip()
        return provider_id or self.__class__.__name__

    def get_display_name(self):
        display_name = str(getattr(self, "display_name", "") or "").strip()
        return display_name or self.get_provider_id()

    def get_actions(self, context) -> Sequence[ContextualActionSpec]:
        del context
        return ()

    def get_tools(self, context) -> Sequence[ContextualToolSpec]:
        del context
        return ()

    def get_inspector_sections(
        self, context
    ) -> Sequence[ContextualInspectorSection]:
        del context
        return ()

    def execute_action(self, action_key, context, commands=None, payload=None):
        del action_key, context, commands, payload
        return False

    def execute_tool(self, tool_key, context, commands=None, payload=None):
        del tool_key, context, commands, payload
        return False


class SemanticEditProvider(ContextualProvider):
    """Expose semantic edit capabilities as contextual actions."""

    provider_id = "semantic-edits"
    display_name = "Semantic Edits"

    def get_actions(self, context):
        actions = []
        for capability in context.get_capabilities():
            source = getattr(capability, "source", None)
            source_name = str(getattr(source, "Name", "") or "source")
            for handle in tuple(getattr(capability, "edit_handles", ()) or ()):
                operation = handle.operation
                actions.append(
                    ContextualActionSpec(
                        key="{}.{}.{}".format(
                            source_name,
                            operation.key,
                            handle.subelement or handle.role,
                        ),
                        label=operation.label,
                        tooltip="Edit {} in the current {} context".format(
                            operation.property_name or handle.role,
                            context.representation_context.purpose.value,
                        ),
                        enabled=operation.is_available(source),
                        provider_id=self.provider_id,
                        handle_key=operation.key,
                        handle_subelement=handle.subelement,
                        source=source,
                    )
                )
        return tuple(actions)

    def get_inspector_sections(self, context):
        purpose = context.representation_context.purpose.value
        return tuple(
            ContextualInspectorSection(
                key=str(getattr(source, "Name", "") or id(source)),
                title=str(getattr(source, "Label", "") or getattr(source, "Name", "Object")),
                body="{} semantic editing · {} available action(s)".format(
                    purpose,
                    sum(
                        len(getattr(capability, "edit_handles", ()) or ())
                        for capability in context.get_capabilities(source)
                    ),
                ),
                provider_id=self.provider_id,
            )
            for source in context.get_selected_sources()
        )


class HostedOpeningCreationProvider(ContextualProvider):
    """Offer the same hosted opening construction in every BIM view context."""

    provider_id = "hosted-opening-creation"
    display_name = "Hosted Openings"

    @staticmethod
    def _selected_wall(context):
        for source in context.get_selected_sources():
            proxy = getattr(source, "Proxy", None)
            if callable(getattr(proxy, "calc_endpoints", None)):
                return source
        return None

    def get_actions(self, context):
        if not context.supports("insert-opening"):
            return ()
        wall = self._selected_wall(context)
        if wall is None:
            return ()
        purpose = context.representation_context.purpose.value
        return tuple(
            ContextualActionSpec(
                key="create-{}".format(kind.lower()),
                label="Create {}".format(kind),
                tooltip="Place a hosted {} in the current {} context".format(
                    kind.lower(), purpose
                ),
                provider_id=self.provider_id,
                source=wall,
            )
            for kind in ("Window", "Door")
        )

    def execute_action(self, action_key, context, commands=None, payload=None):
        del payload
        kinds = {"create-window": "Window", "create-door": "Door"}
        kind = kinds.get(str(action_key))
        wall = self._selected_wall(context)
        if kind is None or wall is None or commands is None:
            return False
        return commands.begin_hosted_opening_creation(kind, wall)


class WallCreationProvider(ContextualProvider):
    provider_id = "wall-creation"
    display_name = "Walls"

    def get_actions(self, context):
        if not context.supports("create-wall"):
            return ()
        return (ContextualActionSpec(
            key="create-wall", label="Create Wall",
            tooltip="Draw a wall in the current {} context".format(
                context.representation_context.purpose.value
            ), provider_id=self.provider_id,
        ),)

    def execute_action(self, action_key, context, commands=None, payload=None):
        del context, payload
        return bool(action_key == "create-wall" and commands and commands.begin_wall_creation())
