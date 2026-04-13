# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def setActiveAnalysis(*args: Any) -> Any: ...
def getActiveAnalysis(*args: Any) -> Any: ...
def open(*args: Any) -> Any: ...
def insert(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCADGui import ViewProviderGeometryObject
from FreeCADGui import ViewProviderDocumentObject
from FreeCADGui import ViewProviderExtension

from typing import *

# src/Mod/Fem/Gui/ViewProviderFemConstraint.pyi:15
class ViewProviderFemConstraint(ViewProviderGeometryObject):
    """
    This is the ViewProviderFemConstraint class

    Author: Mario Passaglia (mpassaglia@cbc.uba.ar)
    License: LGPL-2.1-or-later
    """

    def loadSymbol(self, file_name: str, /) -> Any:
        """
        Load constraint symbol from Open Inventor file.
        The file structure should be as follows:
        A separator containing a separator with the symbol used in
        multiple copies at points on the surface and an optional
        separator with a symbol excluded from multiple copies.

        file_name : str
            Open Inventor file.
        """
        ...
    SymbolNode: Final[Any]
    'A pivy SoSeparator with the nodes of the constraint symbols'
    ExtraSymbolNode: Final[Any]
    'A pivy SoSeparator with the nodes of the constraint extra symbols'
    RotateSymbol: bool
    'Apply rotation on copies of the constraint symbol'

# src/Mod/Fem/Gui/ViewProviderFemMesh.pyi:15
class ViewProviderFemMesh(ViewProviderGeometryObject):
    """
    ViewProviderFemMesh class

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def applyDisplacement(self) -> Any:
        """"""
        ...

    def resetNodeColor(self) -> Any:
        """Reset color set by method setNodeColorByScalars."""
        ...

    def resetNodeDisplacement(self) -> Any:
        """Reset displacements set by method setNodeDisplacementByVectors."""
        ...

    def resetHighlightedNodes(self) -> Any:
        """Reset highlighted nodes."""
        ...

    def setNodeColorByScalars(self) -> Any:
        """Sets mesh node colors using element list and value list."""
        ...

    def setNodeDisplacementByVectors(self) -> Any:
        """"""
        ...
    NodeColor: dict
    'Postprocessing color of the nodes. The faces between the nodes get interpolated.'
    ElementColor: dict
    'Postprocessing color of the elements. All faces of the element get the same color.'
    NodeDisplacement: dict
    'Postprocessing color of the nodes. The faces between the nodes get interpolated.'
    HighlightedNodes: list
    'List of nodes which get highlighted.'
    VisibleElementFaces: Final[list]
    'List of elements and faces which are actually shown. These are all surface faces of the mesh.'

# src/Mod/Fem/Gui/ViewProviderFemPostFilter.pyi:18
class ViewProviderFemPostFilter(ViewProviderDocumentObject):
    """
    ViewProviderFemPostPipeline class

    Author: Stefan Tröger (stefantroeger@gmx.net)
    License: LGPL-2.1-or-later
    """

    def createDisplayTaskWidget(self) -> Any:
        """Returns the display option task panel for a post processing edit task dialog."""
        ...

    def createExtractionTaskWidget(self) -> Any:
        """Returns the data extraction task panel for a post processing edit task dialog."""
        ...

# src/Mod/Fem/Gui/ViewProviderFemPostPipeline.pyi:15
class ViewProviderFemPostPipeline(ViewProviderDocumentObject):
    """
    ViewProviderFemPostPipeline class

    Author: Uwe Stöhr (uwestoehr@lyx.org)
    License: LGPL-2.1-or-later
    """

    def transformField(self) -> Any:
        """Scales values of given result mesh field by given factor"""
        ...

    def updateColorBars(self) -> Any:
        """Update coloring of pipeline and its childs"""
        ...

# src/Mod/Fem/Gui/ViewProviderShapeExtension.pyi:9
class ViewProviderShapeExtension(ViewProviderExtension):
    """
    Extension class which adds visualizations for FEM shape objects
    Author: Stefan Tröger (stefantroeger@gmx.net)
    Licence: LGPL
    """

    def createControlWidget(self) -> Any:
        """
        Creates a QWidget which allows manipulation of the shape properties
        """
        ...
