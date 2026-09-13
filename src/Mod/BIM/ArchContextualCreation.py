# SPDX-License-Identifier: LGPL-2.1-or-later

"""Architectural creation providers for the generic contextual editor."""

import FreeCAD
import Part

import ArchOpeningConstruction
import ArchRepresentation
import ArchWallConstruction
from bimcontextual.actions import (
    ContextualActionSpec,
    ContextualProvider,
    SemanticEditProvider,
)


class _CreationInteraction:
    def __init__(self, facilities):
        self.facilities = facilities
        self.preview_source = object()

    def clear_preview(self):
        self.facilities.clear_preview(self.preview_source)

    def finish(self):
        self.clear_preview()
        self.facilities.clear_value_input()
        self.facilities.resume_interaction()

    def show_shape(self, shape, role):
        representation = ArchRepresentation.BIMRepresentation(
            source=self.preview_source,
            context=self.facilities.context,
        )
        for index, face in enumerate(shape.Faces, start=1):
            representation.add_geometry(
                "cut_geometry", face, role, "Face{}".format(index)
            )
        self.facilities.present_preview(self.preview_source, representation)


class WallCreationInteraction(_CreationInteraction):
    """Acquire a wall segment and construct it through the wall domain service."""

    def __init__(self, facilities, spec=None):
        super().__init__(facilities)
        self.spec = spec or ArchWallConstruction.WallConstructionSpec(200, 2500)
        self.start_point = None
        self.direction = None

    def start(self):
        self.start_point = None
        self.direction = None
        self.facilities.request_point(self.accept_point, title="Wall start")
        return True

    def accept_point(self, point, _obj=None):
        if point is None:
            self.start_point = None
            self.direction = None
            self.finish()
            return None
        if self.start_point is None:
            self.start_point = FreeCAD.Vector(point)
            self.facilities.request_point(
                self.accept_point,
                move_callback=self.preview,
                title="Wall end",
            )
            return None
        try:
            walls = ArchWallConstruction.construct_wall_run(
                self.facilities.document,
                (self.start_point, point),
                self.spec,
                transaction_name="Create Wall",
                auto_join=False,
            )
            return walls[0]
        except Exception as exc:
            self.facilities.show_feedback(exc)
            return None
        finally:
            self.start_point = None
            self.direction = None
            self.finish()

    def preview(self, point, _info=None):
        if self.start_point is None or point is None:
            return
        vector = FreeCAD.Vector(point).sub(self.start_point)
        if vector.Length < ArchWallConstruction.MINIMUM_WALL_LENGTH:
            self.clear_preview()
            return
        spec = self.spec.validated()
        shape = Part.makeBox(vector.Length, spec.width, spec.height)
        shape.Placement = FreeCAD.Placement(
            self.start_point,
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), vector),
        )
        self.show_shape(shape, "WallPreview")
        self.direction = FreeCAD.Vector(vector).normalize()
        self.facilities.set_value_input(
            label="Wall length",
            unit="Length",
            value=vector.Length,
            callback=self.commit_length,
        )

    def commit_length(self, value):
        if self.start_point is None or self.direction is None:
            return None
        end = self.start_point.add(
            FreeCAD.Vector(self.direction).multiply(float(value))
        )
        return self.accept_point(end)


class HostedOpeningCreationInteraction(_CreationInteraction):
    """Acquire an opening location and construct it through the opening service."""

    def __init__(self, facilities, wall, kind):
        super().__init__(facilities)
        self.wall = wall
        self.spec = ArchOpeningConstruction.HostedOpeningSpec(kind=kind)

    def start(self):
        if self.wall is None:
            return False
        kind = self.spec.validated().kind
        self.facilities.request_point(
            self.accept_point,
            title="{} location".format(kind),
            move_callback=self.preview,
        )
        return True

    def preview(self, point, _info=None):
        if point is None:
            return
        spec = self.spec.validated()
        shape = Part.makeBox(spec.width, 200, spec.height)
        shape.Placement = ArchOpeningConstruction.hosted_opening_placement(
            self.wall, point, spec
        )
        self.show_shape(shape, "OpeningPreview")

    def accept_point(self, point, _obj=None):
        if point is None:
            self.finish()
            return None
        try:
            spec = self.spec.validated()
            opening = ArchOpeningConstruction.construct_hosted_opening(
                self.facilities.document,
                self.wall,
                point,
                spec,
                transaction_name="Create {}".format(spec.kind),
            )
            self.facilities.select_source(opening)
            return opening
        except Exception as exc:
            self.facilities.show_feedback(exc)
            return None
        finally:
            self.finish()


class HostedOpeningCreationProvider(ContextualProvider):
    provider_id = "hosted-opening-creation"
    display_name = "Hosted Openings"

    def __init__(self):
        self._interaction = None

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
        self._interaction = HostedOpeningCreationInteraction(commands, wall, kind)
        return self._interaction.start()


class WallCreationProvider(ContextualProvider):
    provider_id = "wall-creation"
    display_name = "Walls"

    def __init__(self):
        self._interaction = None

    def get_actions(self, context):
        if not context.supports("create-wall"):
            return ()
        return (
            ContextualActionSpec(
                key="create-wall",
                label="Create Wall",
                tooltip="Draw a wall in the current {} context".format(
                    context.representation_context.purpose.value
                ),
                provider_id=self.provider_id,
            ),
        )

    def execute_action(self, action_key, context, commands=None, payload=None):
        del context, payload
        if action_key != "create-wall" or commands is None:
            return False
        self._interaction = WallCreationInteraction(commands)
        return self._interaction.start()


def architectural_contextual_providers():
    """Return fresh semantic and creation providers for an architectural session."""

    return (
        SemanticEditProvider(),
        HostedOpeningCreationProvider(),
        WallCreationProvider(),
    )
