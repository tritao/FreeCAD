from Base.Metadata import export
from App.DocumentObject import DocumentObject
from TechDraw.App.DrawView import DrawView
from typing import Final, List

@export(
    Include="Mod/TechDraw/App/DrawPage.h",
)
class DrawPage(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Pages

    Author: WandererFan (wandererfan@gmail.com)
    Licence: LGPL
    """

    PageWidth: Final[float] = 0.0
    """Returns the width of this page"""

    PageHeight: Final[float] = 0.0
    """Returns the height of this page"""

    PageOrientation: Final[str] = ""
    """Returns the orientation of this page"""

    def addView(self, DrawView: DrawView) -> None:
        """
        addView(DrawView) - Add a View to this Page
        """
        ...

    def removeView(self, DrawView: DrawView) -> None:
        """
        removeView(DrawView) - Remove a View to this Page
        """
        ...

    def getViews(self) -> List[DrawView]:
        """
        getViews() - returns a list of all the views on page excluding Views inside Collections
        """
        ...

    def getAllViews(self) -> List[DrawView]:
        """
        getAllViews() - returns a list of all the views on page including Views inside Collections
        """
        ...

    def translateLabel(self, translationContext: str, objectBaseName: str, objectUniqueName: str) -> None:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

    def requestPaint(self) -> None:
        """
        Ask the Gui to redraw this page
        """
        ...
