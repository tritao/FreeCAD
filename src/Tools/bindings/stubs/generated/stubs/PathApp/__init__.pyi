# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def write(*args: Any) -> Any: ...
def read(*args: Any) -> Any: ...
def show(*args: Any) -> Any: ...
def fromShape(*args: Any) -> Any: ...
def fromShapes(*args: Any, **kwargs: Any) -> Any: ...
def sortWires(*args: Any, **kwargs: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCAD.Base import BaseClass
import PathApp
from FreeCAD.Base import Persistence

from typing import *

# src/Mod/CAM/App/Area.pyi:14
class Area(BaseClass):
    """
    FreeCAD python wrapper of libarea

    Path.Area(key=value ...)

    The constructor accepts the same parameters as setParams(...) to configure the object
    All arguments are optional.

    Author: Zheng, Lei (realthunder.dev@gmail.com)
    License: LGPL-2.1-or-later
    """

    def add(self, **kwargs) -> Any:
        """"""
        ...

    def setPlane(self) -> None:
        """
        Set the working plane.

        The supplied shape does not need to be planar. Area will try to find planar
        sub-shape (face, wire or edge). If more than one planar sub-shape is found, it
        will prefer the top plane parallel to XY0 plane. If no working plane are set,
        Area will try to find a working plane from the added children shape using the
        same algorithm
        """
        ...

    def getShape(self, **kwargs) -> Any:
        """
        Return the resulting shape

        * index (-1): the index of the section. -1 means all sections. No effect on planar shape.
        * rebuild: clean the internal cache and rebuild
        """
        ...

    def makeOffset(self, **kwargs) -> Any:
        """Make an offset of the shape."""
        ...

    def makePocket(self, **kwargs) -> Any:
        """Generate pocket toolpath of the shape."""
        ...

    def makeSections(self, **kwargs) -> Any:
        """Make a list of area holding the sectioned children shapes on given heights."""
        ...

    def getRestArea(self) -> Any:
        """Rest machining: Gets the area left to be machined, assuming some of this area has already been cleared by previous tool paths."""
        ...

    def toTopoShape(self) -> Any:
        """Convert the Area object to a TopoShape."""
        ...

    def setParams(self, **kwargs) -> Any:
        """Set algorithm parameters."""
        ...

    def setDefaultParams(self, **kwargs) -> Any:
        """Static method to set the default parameters of all following Path.Area, plus the following additional parameters."""
        ...

    def getDefaultParams(self) -> Any:
        """Static method to return the current default parameters."""
        ...

    def getParamsDesc(self, **kwargs) -> Any:
        """Returns a list of supported parameters and their descriptions."""
        ...

    def getParams(self) -> Any:
        """Get current algorithm parameters as a dictionary."""
        ...

    def abort(self, **kwargs) -> Any:
        """Abort the current operation."""
        ...
    Sections: Final[list]
    'List of sections in this area.'
    Workplane: Any
    'The current workplane. If no plane is set, it is derived from the added shapes.'
    Shapes: Final[list]
    'A list of tuple: [(shape,op), ...] containing the added shapes together with their operation code'

# src/Mod/CAM/App/Command.pyi:14
class Command(Persistence):
    """
    Command([name],[parameters],[annotations]): Represents a basic Gcode command
    name (optional) is the name of the command, ex. G1
    parameters (optional) is a dictionary containing string:number
    pairs, or a placement, or a vector
    annotations (optional) is a dictionary containing string:string or string:number pairs
    """

    def toGCode(self) -> str:
        """returns a GCode representation of the command"""
        ...

    def setFromGCode(self, gcode: str, /) -> None:
        """sets the path from the contents of the given GCode string"""
        ...

    def transform(self, placement: 'PathApp.Placement', /) -> Command:
        """returns a copy of this command transformed by the given placement"""
        ...

    def addAnnotations(self, annotations, /) -> 'Command':
        """addAnnotations(annotations): adds annotations from dictionary or string and returns self for chaining"""
        ...
    Name: str
    'The name of the command'
    Parameters: dict[str, float]
    'The parameters of the command'
    Annotations: dict[str, str]
    'The annotations of the command'
    Placement: 'PathApp.Placement'
    'The coordinates of the endpoint of the command'

# src/Mod/CAM/App/Path.pyi:19
class Path(Persistence):
    """
    Path([commands]): Represents a basic Gcode path
    commands (optional) is a list of Path commands

    Author: Yorik van Havre (yorik@uncreated.net)
    License: LGPL-2.1-or-later
    """

    @overload
    def addCommands(self, command: Command, /) -> Path:
        ...

    @overload
    def addCommands(self, commands: list[Command], /) -> Path:
        ...

    def addCommands(self, arg: Union[Command, list[Command]], /) -> Path:
        """adds a command or a list of commands at the end of the path"""
        ...

    def insertCommand(self, command: Command, pos: int=-1, /) -> Path:
        """
        adds a command at the given position or at the end of the path
        """
        ...

    def deleteCommand(self, pos: int=-1, /) -> Path:
        """
        deletes the command found at the given position or from the end of the path
        """
        ...

    def setFromGCode(self, gcode: str, /) -> None:
        """sets the contents of the path from a gcode string"""
        ...

    def getClearedArea(self) -> Any:
        """Gets the area cleared when a tool of the specified diameter follows the gcode represented in the path, ignoring cleared space above zmax and path segments that don't affect space within the x/y space of bbox."""
        ...

    def toGCode(self) -> str:
        """returns a gcode string representing the path"""
        ...

    def copy(self) -> Path:
        """returns a copy of this path"""
        ...

    def getCycleTime(self, h_feed: float, v_feed: float, h_rapid: float, v_rapid: float, /) -> float:
        """return the cycle time estimation for this path in s"""
        ...
    Length: Final[float]
    'the total length of this path in mm'
    Size: Final[int]
    'the number of commands in this path'
    Commands: list
    'the list of commands of this path'
    Center: Any
    'the center position for all rotational parameters'
    BoundBox: Final[Any]
    'the extent of this path'
