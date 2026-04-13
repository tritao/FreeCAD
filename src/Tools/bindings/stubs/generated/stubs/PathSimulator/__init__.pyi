# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import BaseClass
from FreeCAD.Base import Placement
from Part import Shape as TopoShape
from Mesh import Mesh
from PathApp import Command

from typing import *

# src/Mod/CAM/PathSimulator/App/PathSim.pyi:21
class PathSim(BaseClass):
    """
    FreeCAD python wrapper of PathSimulator

    PathSimulator.PathSim():

    Create a path simulator object

    Author: Shai Seger (shaise_at_g-mail)
    License: LGPL-2.1-or-later
    """

    def BeginSimulation(self, stock: TopoShape, resolution: float) -> None:
        """
        Start a simulation process on a box shape stock with given resolution
        """
        ...

    def SetToolShape(self, tool: TopoShape, resolution: float, /) -> None:
        """
        Set the shape of the tool to be used for simulation
        """
        ...

    def GetResultMesh(self) -> tuple[Mesh, Mesh]:
        """
        Return the current mesh result of the simulation.
        """
        ...

    def ApplyCommand(self, placement: Placement, command: Command) -> Placement:
        """
        Apply a single path command on the stock starting from placement.
        """
        ...
    Tool: Final[Any]
    'Return current simulation tool.'
