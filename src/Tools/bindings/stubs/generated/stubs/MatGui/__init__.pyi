# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import BaseClass

from typing import *

# src/Mod/Material/Gui/MaterialTreeWidget.pyi:19
class MaterialTreeWidget(BaseClass):
    """
    Material tree widget.
    """
    UUID: str = ...
    'Material UUID.'
    expanded: bool = ...
    'Expand material tree.'
    IncludeFavorites: bool = ...
    'Include favorites in the material list.'
    IncludeRecent: bool = ...
    'Include recently used materials in the material list.'
    IncludeEmptyFolders: bool = ...
    'Include empty folders in the material list.'
    IncludeEmptyLibraries: bool = ...
    'Include empty libraries in the material list.'
    IncludeLegacy: bool = ...
    'Include legacy materials in the material list.'

    def setFilter(self) -> None:
        """
        Set the material filter or list of filters.
        """
        ...

    def selectFilter(self) -> None:
        """
        Set the current material filter.
        """
        ...
