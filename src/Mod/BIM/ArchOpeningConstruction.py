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


@dataclass(frozen=True)
class HostedOpeningSpec:
    """Semantic description of a standard hosted architectural opening."""

    kind: str = "Window"
    width: float = 900.0
    height: float | None = None
    sill_height: float | None = None

    def validated(self):
        kind = str(self.kind or "Window").title()
        if kind not in ("Window", "Door"):
            raise OpeningConstructionError("Hosted opening kind must be Window or Door.")
        width = float(self.width)
        default_height = 1200 if kind == "Window" else 2100
        default_sill = 900 if kind == "Window" else 0
        height = float(self.height if self.height is not None else default_height)
        sill = float(self.sill_height if self.sill_height is not None else default_sill)
        if width <= 0 or height <= 0 or sill < 0:
            raise OpeningConstructionError("Hosted opening dimensions are invalid.")
        return HostedOpeningSpec(kind, width, height, sill)

    def preset_spec(self):
        spec = self.validated()
        return OpeningPresetSpec(
            "Fixed" if spec.kind == "Window" else "Simple door",
            spec.width, spec.height, 50, 50, 50, 50, 50, 0, 0,
        )


def hosted_opening_placement(host, point, spec):
    """Resolve a context-independent placement along a straight wall host."""

    import FreeCAD

    spec = spec.validated()
    proxy = getattr(host, "Proxy", None)
    endpoints = getattr(proxy, "calc_endpoints", lambda _obj: ())(host)
    if len(tuple(endpoints or ())) != 2:
        raise OpeningConstructionError("A straight wall host is required.")
    start, end = (FreeCAD.Vector(value) for value in endpoints)
    axis = end.sub(start)
    axis.z = 0.0
    length = axis.Length
    if length <= 1e-9:
        raise OpeningConstructionError("The wall host has no usable length.")
    axis.normalize()
    requested = FreeCAD.Vector(point)
    requested.z = start.z
    distance = requested.sub(start).dot(axis)
    half_width = spec.width * 0.5
    distance = (
        length * 0.5
        if length < spec.width
        else min(max(distance, half_width), length - half_width)
    )
    base = start.add(FreeCAD.Vector(axis).multiply(distance))
    base.z = start.z + spec.sill_height
    vertical = FreeCAD.Vector(0, 0, 1)
    normal = axis.cross(vertical)
    normal.normalize()
    return FreeCAD.Placement(base, FreeCAD.Rotation(axis, vertical, normal, "XYZ"))


def construct_hosted_opening(
    document,
    host,
    point,
    spec,
    *,
    transaction_name=None,
    add_to_container=None,
    defer_updates=None,
):
    """Construct a standard Window or Door on a wall in any view context."""

    spec = spec.validated()
    return construct_preset_opening(
        document,
        spec.preset_spec(),
        placement=hosted_opening_placement(host, point, spec),
        transaction_name=transaction_name or "Create {}".format(spec.kind),
        hosts=(host,),
        add_to_container=add_to_container,
        defer_updates=defer_updates,
    )


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
    after_hosting=None,
):
    return construct_opening(
        document,
        lambda: create_preset_opening(spec, placement=placement),
        transaction_name=transaction_name,
        hosts=hosts,
        add_to_container=add_to_container,
        defer_updates=defer_updates,
        after_hosting=after_hosting,
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
    after_hosting=None,
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
            if after_hosting is not None:
                after_hosting(opening)
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
