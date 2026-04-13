# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD import DocumentObject

from typing import *

# src/Mod/CAM/App/FeatureArea.pyi:13
class FeatureArea(DocumentObject):
    """
    This class handles Path Area features

    Author: Zheng, Lei (realthunder.dev@gmail.com)
    License: LGPL-2.1-or-later
    """

    def getArea(self) -> Any:
        """Return a copy of the encapsulated Python Area object."""
        ...

    def setParams(self, **kwargs) -> Any:
        """
        Convenient function to configure this feature.

        Call with keywords: setParams(key=value, ...)

        Same usage as Path.Area.setParams(). This function stores the parameters in the properties.
        """
        ...
    WorkPlane: Any
    'The current workplane. If no plane is set, it is derived from the added shapes.'

# src/Mod/CAM/App/FeaturePathCompound.pyi:14
class FeaturePathCompound(DocumentObject):
    """
    This class handles Path Compound features

    Author: Yorik van Havre (yorik@uncreated.net)
    License: LGPL-2.1-or-later
    """

    def addObject(self) -> Any:
        """Add an object to the group"""
        ...

    def removeObject(self) -> Any:
        """Remove an object from the group"""
        ...
