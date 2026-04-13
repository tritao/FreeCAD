# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from typing import *

# src/Mod/PartDesign/Gui/ViewProvider.pyi:14
class ViewProvider:
    """
    This is the father of all PartDesign ViewProvider classes

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """

    def setBodyMode(self, mode: bool, /) -> None:
        """
        body mode means that the object is part of a body
        and that the body is used to set the visual properties, not the features. Hence
        setting body mode to true will hide most viewprovider properties.
        """
        ...

    def makeTemporaryVisible(self, visible: bool, /) -> None:
        """
        makes this viewprovider visible in the
        scene graph without changing any properties, not the visibility one and also not
        the display mode. This can be used to show the shape of this viewprovider from
        other viewproviders without doing anything to the document and properties.
        """
        ...
