# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def open(*args: Any, **kwargs: Any) -> Any: ...
def insert(*args: Any, **kwargs: Any) -> Any: ...
def export(*args: Any, **kwargs: Any) -> Any: ...
def readDXF(*args: Any) -> Any: ...
def writeDXFShape(*args: Any) -> Any: ...
def writeDXFObject(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from typing import *

# src/Mod/Import/App/StepShape.pyi:16
class StepShape:
    """
    StepShape in Import
    This class gives a interface to retrieve TopoShapes out of an loaded STEP file of any kind.

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def read(self) -> Any:
        """
        Read a STEP file into memory and make it accessible
        """
        ...
