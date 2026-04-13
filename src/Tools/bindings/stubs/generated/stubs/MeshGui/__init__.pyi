# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def convertToSTL(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCADGui import ViewProviderGeometryObject

from typing import *

# src/Mod/Mesh/Gui/ViewProviderMesh.pyi:13
class ViewProviderMesh(ViewProviderGeometryObject):
    """
    This is the ViewProvider base class

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    License: LGPL-2.1-or-later
    """

    def setSelection(self) -> Any:
        """Select list of facets"""
        ...

    def addSelection(self) -> Any:
        """Add list of facets to selection"""
        ...

    def removeSelection(self) -> Any:
        """Remove list of facets from selection"""
        ...

    def invertSelection(self) -> Any:
        """Invert the selection"""
        ...

    def clearSelection(self) -> Any:
        """Clear the selection"""
        ...

    def highlightSegments(self) -> Any:
        """Highlights the segments of a mesh with a given list of colors.
        The number of elements of this list must be equal to the number of mesh segments.
        """
        ...
