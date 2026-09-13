# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent construction services for BIM openings."""

from contextlib import nullcontext
from dataclasses import dataclass


class OpeningConstructionError(RuntimeError):
    """Raised when an opening candidate cannot be constructed safely."""


@dataclass(frozen=True)
class OpeningConstructionSpec:
    width: float | None = None
    height: float | None = None
    ifc_type: str = "Window"
    hole_depth: float | None = None
    parts: tuple = ()
    name: str = "Window"

    def validated(self):
        width = None if self.width is None else float(self.width)
        height = None if self.height is None else float(self.height)
        if width is not None and width <= 0.0:
            raise OpeningConstructionError("Opening width must be greater than zero.")
        if height is not None and height <= 0.0:
            raise OpeningConstructionError("Opening height must be greater than zero.")
        return OpeningConstructionSpec(
            width=width,
            height=height,
            ifc_type=str(self.ifc_type or "Window"),
            hole_depth=self.hole_depth,
            parts=tuple(self.parts or ()),
            name=str(self.name or "Window"),
        )


@dataclass(frozen=True)
class OpeningPresetSpec:
    preset: str
    width: float
    height: float
    h1: float
    h2: float
    h3: float
    w1: float
    w2: float
    o1: float
    o2: float

    def validated(self):
        values = tuple(
            float(value)
            for value in (
                self.width, self.height, self.h1, self.h2, self.h3,
                self.w1, self.w2, self.o1, self.o2,
            )
        )
        if any(value <= 0.0 for value in values[:2]):
            raise OpeningConstructionError(
                "Opening preset width and height must be greater than zero."
            )
        if any(value <= 0.0 for value in (values[2], values[3], values[5], values[6])):
            raise OpeningConstructionError(
                "Opening preset frame dimensions must be greater than zero."
            )
        return OpeningPresetSpec(str(self.preset), *values)


def create_opening_from_base(base, spec):
    """Create and configure an opening before it is assigned to any host."""

    import Arch

    spec = spec.validated()
    kwargs = {"baseobj": base, "name": spec.name}
    if spec.width is not None:
        kwargs["width"] = spec.width
    if spec.height is not None:
        kwargs["height"] = spec.height
    opening = Arch.makeWindow(**kwargs)
    if opening is None:
        raise OpeningConstructionError("Unable to create opening.")
    if hasattr(opening, "IfcType"):
        opening.IfcType = spec.ifc_type
    if spec.width is not None and hasattr(opening, "Width"):
        opening.Width = spec.width
    if spec.height is not None and hasattr(opening, "Height"):
        opening.Height = spec.height
    if spec.hole_depth is not None and hasattr(opening, "HoleDepth"):
        opening.HoleDepth = float(spec.hole_depth)
    if spec.parts and hasattr(opening, "WindowParts"):
        opening.WindowParts = list(spec.parts)
    return opening


def create_preset_opening(spec, placement=None):
    """Create one validated built-in Window or Door preset."""

    import Arch

    spec = spec.validated()
    return Arch.makeWindowPreset(
        spec.preset,
        width=spec.width,
        height=spec.height,
        h1=spec.h1,
        h2=spec.h2,
        h3=spec.h3,
        w1=spec.w1,
        w2=spec.w2,
        o1=spec.o1,
        o2=spec.o2,
        placement=placement,
    )


def construct_preset_opening(
    document,
    spec,
    *,
    placement=None,
    transaction_name,
    hosts=(),
    add_to_container=None,
    defer_updates=None,
):
    return construct_opening(
        document,
        lambda: create_preset_opening(spec, placement=placement),
        transaction_name=transaction_name,
        hosts=hosts,
        add_to_container=add_to_container,
        defer_updates=defer_updates,
    )


def has_built_shape(opening):
    shape = getattr(opening, "Shape", None)
    if not shape:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return False


def assign_hosts(opening, hosts):
    """Assign unique hosts after the opening has built successfully."""

    unique = []
    for host in tuple(hosts or ()):
        if host is not None and host not in unique:
            unique.append(host)
    if not unique:
        return opening
    if not hasattr(opening, "Hosts"):
        raise OpeningConstructionError("Opening does not support hosts.")
    opening.Hosts = unique
    return opening


def construct_opening(
    document,
    build_opening,
    *,
    transaction_name,
    hosts=(),
    add_to_container=None,
    defer_updates=None,
    require_built_shape=True,
):
    """Build, validate, host, and atomically commit an opening."""

    if document is None:
        raise OpeningConstructionError("No document is available.")
    update_scope = defer_updates() if defer_updates is not None else nullcontext()
    document.openTransaction(transaction_name)
    try:
        with update_scope:
            opening = build_opening()
            if opening is None:
                raise OpeningConstructionError("Unable to create opening.")
            document.recompute()
            if require_built_shape and not has_built_shape(opening):
                raise OpeningConstructionError("Opening did not build before hosting.")
            assign_hosts(opening, hosts)
            if add_to_container is not None:
                add_to_container(opening)
            document.recompute()
            for host in tuple(hosts or ()):
                if host not in tuple(getattr(opening, "Hosts", ()) or ()):
                    raise OpeningConstructionError("Opening was not hosted.")
        document.commitTransaction()
        return opening
    except Exception:
        try:
            document.abortTransaction()
        except Exception:
            pass
        raise


def construct_opening_from_base(
    document,
    base,
    spec,
    *,
    transaction_name,
    hosts=(),
    add_to_container=None,
    defer_updates=None,
):
    return construct_opening(
        document,
        lambda: create_opening_from_base(base, spec),
        transaction_name=transaction_name,
        hosts=hosts,
        add_to_container=add_to_container,
        defer_updates=defer_updates,
    )
