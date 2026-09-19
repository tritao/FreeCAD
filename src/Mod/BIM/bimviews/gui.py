# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI view selection for BIM saved-view activation."""


_VIEW_3D_TYPE = "Gui::View3DInventor"


def is_3d_view(view):
    """Return whether *view* can apply a persisted view definition."""

    return view is not None and hasattr(view, "applyViewDefinition")


def ensure_active_3d_view(document):
    """Activate and return a 3D viewport belonging to *document*.

    A TechDraw page and a 3D viewport are sibling MDI views.  Saved BIM views
    target the latter, so switching from a sheet must first restore a viewport
    for the same document.  Reuse the document's primary viewport and create
    one only when the document no longer has one.
    """

    import FreeCADGui

    try:
        gui_document = FreeCADGui.getDocument(document.Name)
    except (AttributeError, ReferenceError, RuntimeError) as exc:
        raise RuntimeError(
            "Cannot activate a BIM view without an open GUI document"
        ) from exc
    if gui_document is None:
        raise RuntimeError("Cannot activate a BIM view without an open GUI document")

    active_view = gui_document.activeView()
    if is_3d_view(active_view):
        return active_view

    try:
        views = tuple(gui_document.mdiViewsOfType(_VIEW_3D_TYPE))
        target_view = views[0] if views else gui_document.createView(_VIEW_3D_TYPE)
        if not is_3d_view(target_view):
            raise RuntimeError("The GUI document could not provide a 3D viewport")
        FreeCADGui.getMainWindow().setActiveWindow(target_view)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as exc:
        raise RuntimeError(
            "Unable to activate a 3D viewport for BIM view activation"
        ) from exc

    activated_view = gui_document.activeView()
    if not is_3d_view(activated_view):
        raise RuntimeError("The 3D viewport did not become active")
    return activated_view
