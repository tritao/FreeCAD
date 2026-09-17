# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime state for one BIM representation in one viewport.

The persistent :class:`App::ViewDefinition` describes a saved view.  This
small object is its live counterpart: it records which viewport is displaying
the view and exposes capability queries to interaction code.  Keeping this
boundary independent of the Plan Edit controller lets PLAN, SECTION,
ELEVATION and MODEL runtimes share the same lifecycle later on.
"""

from dataclasses import dataclass, field

from ArchRepresentation import RepresentationPurpose


_PLANAR_PURPOSES = frozenset(
    (
        RepresentationPurpose.PLAN,
        RepresentationPurpose.SECTION,
        RepresentationPurpose.ELEVATION,
    )
)


@dataclass
class BIMViewRuntime:
    """Live state for a BIM view assigned to a single viewport.

    ``session`` is deliberately opaque.  The runtime layer must not depend on
    the Plan Edit controller, so the existing controller can adopt this object
    without making the generic view model depend on plan-specific modules.
    """

    view: object
    request: object = None
    session: object = field(default=None, repr=False)
    closed: bool = False

    @property
    def purpose(self):
        return getattr(self.request, "purpose", None)

    @property
    def is_planar(self):
        return self.purpose in _PLANAR_PURPOSES

    @property
    def reference_frame(self):
        return getattr(self.request, "reference_frame", None)

    @property
    def capabilities(self):
        """Return stable capability names for the active representation."""

        if self.closed:
            return frozenset()
        if self.is_planar:
            return frozenset(
                (
                    "planar",
                    "planar_editing",
                    "grid",
                    "rulers",
                    "orthographic_navigation",
                )
            )
        return frozenset(("model", "model_editing"))

    def supports(self, capability):
        """Return whether this runtime supports an interaction capability."""

        return capability in self.capabilities

    def supports_tool(self, tool):
        """Return whether a BIM tool can target this representation runtime.

        Selection is valid in every live representation.  The current Plan
        tool set is planar; model-specific tools can add their own capability
        names as the model editing runtime grows.
        """

        tool_name = getattr(tool, "value", tool)
        if str(tool_name or "") == "Select":
            return self.supports("planar_editing") or self.supports("model_editing")
        return self.supports("planar_editing")

    def accepts_view(self, view):
        """Return whether an input event belongs to this runtime's viewport."""

        return not self.closed and view is self.view

    def set_request(self, request):
        """Update the representation displayed by this viewport."""

        if self.closed:
            return False
        self.request = request
        return True

    def close(self):
        """Detach the runtime from its viewport and release live references."""

        if self.closed:
            return False
        self.closed = True
        self.request = None
        self.view = None
        self.session = None
        return True
