# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent semantic operations for hosted architectural openings."""


def _opening_proxy(opening):
    for owner in (opening, getattr(opening, "ViewObject", None)):
        proxy = getattr(owner, "Proxy", None)
        if proxy is not None and all(
            callable(getattr(proxy, name, None))
            for name in (
                "get_hosted_opening_move_context",
                "project_hosted_opening_move_point",
            )
        ):
            return proxy
    return None


def move_hosted_opening(opening, point, anchor="center"):
    """Move an opening along its host using its semantic move projection."""

    if opening is None or point is None:
        return False

    import FreeCAD

    proxy = _opening_proxy(opening)
    get_context = getattr(proxy, "get_hosted_opening_move_context", None)
    project_point = getattr(proxy, "project_hosted_opening_move_point", None)
    if not callable(get_context) or not callable(project_point):
        return False
    move_context = get_context() or {}
    projected = project_point(point, anchor=anchor)
    if projected is None:
        return False

    target = getattr(opening, "Base", None) or opening
    current_placement = getattr(target, "Placement", None)
    if current_placement is None:
        return False

    center = move_context.get("center_point")
    if center is None:
        return False
    # Move by the requested semantic-center delta. Opening profiles are not
    # required to be centered on their placement origin, so reconstructing an
    # absolute placement from that offset can drift after profile recompute.
    placement = FreeCAD.Placement(current_placement)
    placement.Base = placement.Base.add(
        FreeCAD.Vector(projected).sub(FreeCAD.Vector(center))
    )
    target.Placement = placement

    if target is not opening:
        invalidate_compilation = getattr(
            getattr(opening, "Proxy", None), "invalidateExactCompilation", None
        )
        if callable(invalidate_compilation):
            invalidate_compilation()
        touch = getattr(opening, "touch", None)
        if callable(touch):
            touch()
    for host in tuple(getattr(opening, "Hosts", ()) or ()):
        touch = getattr(host, "touch", None)
        if callable(touch):
            touch()
    return True
