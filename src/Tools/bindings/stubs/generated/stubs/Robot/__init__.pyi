# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def simulateToFile(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCAD.Base import Persistence
from FreeCAD import DocumentObject

from typing import *

# src/Mod/Robot/App/Robot6Axis.pyi:16
class Robot6Axis(Persistence):
    """
    Robot6Axis class

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def check(self) -> Any:
        """Checks the shape and report errors in the shape structure.
        This is a more detailed check as done in isValid()."""
        ...
    Axis1: float
    'Pose of Axis 1 in degrees'
    Axis2: float
    'Pose of Axis 2 in degrees'
    Axis3: float
    'Pose of Axis 3 in degrees'
    Axis4: float
    'Pose of Axis 4 in degrees'
    Axis5: float
    'Pose of Axis 5 in degrees'
    Axis6: float
    'Pose of Axis 6 in degrees'
    Tcp: Any
    'Tool center point frame. Where the tool of the robot is'
    Base: Any
    'Actual Base system in respect to the robot world system'

# src/Mod/Robot/App/RobotObject.pyi:15
class RobotObject(DocumentObject):
    """
    Robot document object

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    License: LGPL-2.1-or-later
    """

    def getRobot(self) -> Any:
        """Returns a copy of the robot. Be aware, the robot behaves the same
        like the robot of the object but is a copy!"""
        ...

# src/Mod/Robot/App/Trajectory.pyi:16
class Trajectory(Persistence):
    """
    Trajectory class

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def insertWaypoints(self) -> Any:
        """adds one or a list of waypoint to the end of the trajectory"""
        ...

    def position(self) -> Any:
        """returns a Frame to a given time in the trajectory"""
        ...

    def velocity(self) -> Any:
        """returns the velocity to a given time in the trajectory"""
        ...

    def deleteLast(self) -> Any:
        """
        deleteLast(n) - delete n waypoints at the end
        deleteLast()  - delete the last waypoint
        """
        ...
    Duration: Final[float]
    'duration of the trajectory'
    Length: Final[float]
    'length of the trajectory'
    Waypoints: list
    'waypoints of this trajectory'

# src/Mod/Robot/App/Waypoint.pyi:16
class Waypoint(Persistence):
    """
    Waypoint class

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """
    Name: str
    'Name of the waypoint'
    Type: str
    'Type of the waypoint[PTP|LIN|CIRC|WAIT]'
    Pos: Any
    'End position (destination) of the waypoint'
    Cont: bool
    'Control the continuity to the next waypoint in the trajectory'
    Velocity: float
    'Control the velocity to the next waypoint in the trajectory\nIn Case of PTP 0-100% Axis speed\nIn Case of LIN m/s\nIn Case of WAIT s wait time'
    Tool: int
    'Describe which tool frame to use for that point'
    Base: int
    'Describe which Base frame to use for that point'
