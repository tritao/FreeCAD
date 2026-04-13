# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def open(*args: Any) -> Any: ...
def insert(*args: Any) -> Any: ...

# Generated public type stubs from PyCXX binding method tables.
from typing import Any

class _SheetView:
    def selectedRanges(self, *args: Any) -> Any: ...
    def selectedCells(self, *args: Any) -> Any: ...
    def select(self, *args: Any) -> Any: ...
    def currentIndex(self, *args: Any) -> Any: ...
    def setCurrentIndex(self, *args: Any) -> Any: ...
    def getSheet(self, *args: Any) -> Any: ...
    def cast_to_base(self, *args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCADGui import ViewProviderDocumentObject

from typing import *

# src/Mod/Spreadsheet/Gui/ViewProviderSpreadsheet.pyi:17
class ViewProviderSpreadsheet(ViewProviderDocumentObject):
    """
    ViewProviderSheet class

    Author: Jose Luis Cercos Pita (jlcercos@gmail.com)
    License: LGPL-2.1-or-later
    """

    def getView(self) -> Any:
        """Get access to the sheet view"""
        ...

    def showSheetMdi(self) -> None:
        """Create (if necessary) and switch to the Spreadsheet MDI."""
        ...

    def exportAsFile(self) -> None:
        """Export the sheet as a file."""
        ...
