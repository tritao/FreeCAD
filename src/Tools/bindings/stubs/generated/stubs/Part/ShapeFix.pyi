# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def sameParameter(*args: Any) -> Any: ...
def encodeRegularity(*args: Any) -> Any: ...
def removeSmallEdges(*args: Any) -> Any: ...
def fixVertexPosition(*args: Any) -> Any: ...
def leastEdgeSize(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from Part import Edge as TopoShapeEdge
from Part import Shape as TopoShape
from Part import Face as TopoShapeFace
from Part import Shell as TopoShapeShell
from Part import Compound as TopoShapeCompound

from typing import *

# src/Mod/Part/App/ShapeFix/ShapeFix_Edge.pyi:23
class Edge:
    """
    Fixing invalid edge

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def fixRemovePCurve(self) -> bool:
        """
        Removes the pcurve(s) of the edge if it does not match the
        vertices
        Check is done
        Use    : It is to be called when pcurve of an edge can be wrong
        (e.g., after import from IGES)
        Returns: True, if does not match, removed (status DONE)
        False, (status OK) if matches or (status FAIL) if no pcurve,
        nothing done.
        """
        ...

    def fixRemoveCurve3d(self) -> bool:
        """
        Removes 3d curve of the edge if it does not match the vertices
        Returns: True,  if does not match, removed (status DONE)
        False, (status OK) if matches or (status FAIL) if no 3d curve,
        nothing done.
        """
        ...

    def fixAddPCurve(self) -> bool:
        """
        Adds pcurve(s) of the edge if missing (by projecting 3d curve)
        Parameter isSeam indicates if the edge is a seam.
        The parameter 'prec' defines the precision for calculations.
        If it is 0 (default), the tolerance of the edge is taken.
        Remark : This method is rather for internal use since it accepts parameter
        'surfana' for optimization of computations
        Use    : It is to be called after FixRemovePCurve (if removed) or in any
        case when edge can have no pcurve
        Returns: True if pcurve was added, else False
        Status :
        OK   : Pcurve exists
        FAIL1: No 3d curve
        FAIL2: fail during projecting
        DONE1: Pcurve was added
        DONE2: specific case of pcurve going through degenerated point on
        sphere encountered during projection (see class
        ShapeConstruct_ProjectCurveOnSurface for more info).
        """
        ...

    def fixAddCurve3d(self) -> bool:
        """
        Tries to build 3d curve of the edge if missing
        Use    : It is to be called after FixRemoveCurve3d (if removed) or in any
        case when edge can have no 3d curve
        Returns: True if 3d curve was added, else False
        Status :
        OK   : 3d curve exists
        FAIL1: BRepLib::BuildCurve3d() has failed
        DONE1: 3d curve was added.
        """
        ...

    def fixVertexTolerance(self) -> bool:
        """
        Increases the tolerances of the edge vertices to comprise
        the ends of 3d curve and pcurve on the given face
        (first method) or all pcurves stored in an edge (second one)
        Returns: True, if tolerances have been increased, otherwise False
        Status:
        OK   : the original tolerances have not been changed
        DONE1: the tolerance of first vertex has been increased
        DONE2: the tolerance of last  vertex has been increased.
        """
        ...

    def fixReversed2d(self) -> bool:
        """
        Fixes edge if pcurve is directed opposite to 3d curve
        Check is done by call to the function
        ShapeAnalysis_Edge::CheckCurve3dWithPCurve()
        Warning: For seam edge this method will check and fix the pcurve in only
        one direction. Hence, it should be called twice for seam edge:
        once with edge orientation FORWARD and once with REVERSED.
        Returns: False if nothing done, True if reversed (status DONE)
        Status:  OK    - pcurve OK, nothing done
        FAIL1 - no pcurve
        FAIL2 - no 3d curve
        DONE1 - pcurve was reversed.
        """
        ...

    def fixSameParameter(self) -> bool:
        """
        Tries to make edge SameParameter and sets corresponding
        tolerance and SameParameter flag.
        First, it makes edge same range if SameRange flag is not set.
        If flag SameParameter is set, this method calls the
        function ShapeAnalysis_Edge::CheckSameParameter() that
        calculates the maximal deviation of pcurves of the edge from
        its 3d curve. If deviation > tolerance, the tolerance of edge
        is increased to a value of deviation. If deviation < tolerance
        nothing happens.

        If flag SameParameter is not set, this method chooses the best
        variant (one that has minimal tolerance), either
        a. only after computing deviation (as above) or
        b. after calling standard procedure BRepLib::SameParameter
        and computing deviation (as above). If 'tolerance' > 0, it is
        used as parameter for BRepLib::SameParameter, otherwise,
        tolerance of the edge is used.

        Use    : Is to be called after all pcurves and 3d curve of the edge are
        correctly computed
        Remark : SameParameter flag is always set to True after this method
        Returns: True, if something done, else False
        Status : OK    - edge was initially SameParameter, nothing is done
        FAIL1 - computation of deviation of pcurves from 3d curve has failed
        FAIL2 - BRepLib::SameParameter() has failed
        DONE1 - tolerance of the edge was increased
        DONE2 - flag SameParameter was set to True (only if
        BRepLib::SameParameter() did not set it)
        DONE3 - edge was modified by BRepLib::SameParameter() to SameParameter
        DONE4 - not used anymore
        DONE5 - if the edge resulting from BRepLib has been chosen, i.e. variant b. above
        (only for edges with not set SameParameter).
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_EdgeConnect.pyi:17
class EdgeConnect:
    """
    Root class for fixing operations

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    @overload
    def add(self, edge1: TopoShapeEdge, edge2: TopoShapeEdge, /) -> None:
        ...

    @overload
    def add(self, shape: TopoShape, /) -> None:
        ...

    def add(self, *args, **kwargs) -> None:
        """
        add(edge, edge)
        Adds information on connectivity between start vertex
        of second edge and end vertex of first edge taking
        edges orientation into account

        add(shape)
        Adds connectivity information for the whole shape.
        """
        ...

    def build(self) -> None:
        """
        Builds shared vertices, updates their positions and tolerances
        """
        ...

    def clear(self) -> None:
        """
        Clears internal data structure
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Face.pyi:17
class Face(Root):
    """
    Class for fixing operations on faces

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    FixWireMode: bool = ...
    'Mode for applying fixes of ShapeFix_Wire'
    FixOrientationMode: bool = ...
    '\n    Mode for applying fixes of orientation\n    If True, wires oriented to border limited square\n    '
    FixAddNaturalBoundMode: bool = ...
    '\n    If true, natural boundary is added on faces that miss them.\n    Default is False for faces with single wire (they are\n    handled by FixOrientation in that case) and True for others.\n    '
    FixMissingSeamMode: bool = ...
    'If True, tries to insert seam if missing'
    FixSmallAreaWireMode: bool = ...
    'If True, drops small wires'
    RemoveSmallAreaFaceMode: bool = ...
    'If True, drops small wires'
    FixIntersectingWiresMode: bool = ...
    'Mode for applying fixes of intersecting wires'
    FixLoopWiresMode: bool = ...
    'Mode for applying fixes of loop wires'
    FixSplitFaceMode: bool = ...
    'Mode for applying fixes of split face'
    AutoCorrectPrecisionMode: bool = ...
    'Mode for applying auto-corrected precision'
    FixPeriodicDegeneratedMode: bool = ...
    'Mode for applying periodic degeneration'

    def init(self) -> None:
        """
        Initializes by face
        """
        ...

    def fixWireTool(self):
        """
        Returns tool for fixing wires
        """
        ...

    def clearModes(self) -> None:
        """
        Sets all modes to default
        """
        ...

    def add(self) -> None:
        """
        Add a wire to current face using BRep_Builder.
        Wire is added without taking into account orientation of face
        (as if face were FORWARD)
        """
        ...

    def fixOrientation(self) -> bool:
        """
        Fixes orientation of wires on the face
        It tries to make all wires lie outside all others (according
        to orientation) by reversing orientation of some of them.
        If face lying on sphere or torus has single wire and
        AddNaturalBoundMode is True, that wire is not reversed in
        any case (supposing that natural bound will be added).
        Returns True if wires were reversed
        """
        ...

    def fixAddNaturalBound(self) -> bool:
        """
        Adds natural boundary on face if it is missing.
        Two cases are supported:
         - face has no wires
         - face lies on geometrically double-closed surface
        (sphere or torus) and none of wires is left-oriented
        Returns True if natural boundary was added
        """
        ...

    def fixMissingSeam(self) -> bool:
        """
        Detects and fixes the special case when face on a closed
        surface is given by two wires closed in 3d but with gap in 2d.
        In that case it creates a new wire from the two, and adds a
        missing seam edge
        Returns True if missing seam was added
        """
        ...

    def fixSmallAreaWire(self) -> bool:
        """
        Detects wires with small area (that is less than
        100*Precision.PConfusion(). Removes these wires if they are internal.
        Returns True if at least one small wire removed, False nothing is done.
        """
        ...

    def fixLoopWire(self) -> None:
        """
        Detects if wire has a loop and fixes this situation by splitting on the few parts.
        """
        ...

    def fixIntersectingWires(self) -> None:
        """
        Detects and fixes the special case when face has more than one wire
        and this wires have intersection point
        """
        ...

    def fixWiresTwoCoincidentEdges(self) -> None:
        """
        If wire contains two coincidence edges it must be removed
        """
        ...

    def fixPeriodicDegenerated(self) -> None:
        """
        Fixes topology for a specific case when face is composed
        by a single wire belting a periodic surface. In that case
        a degenerated edge is reconstructed in the degenerated pole
        of the surface. Initial wire gets consistent orientation.
        Must be used in couple and before FixMissingSeam routine
        """
        ...

    def perform(self) -> None:
        """
        Iterates on subshapes and performs fixes
        """
        ...

    def face(self) -> TopoShapeFace:
        """
        Returns a face which corresponds to the current state
        """
        ...

    def result(self) -> Union[TopoShapeFace, TopoShapeShell]:
        """
        Returns resulting shape (Face or Shell if split)
        To be used instead of face() if FixMissingSeam involved
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_FaceConnect.pyi:14
class FaceConnect:
    """
    Rebuilds connectivity between faces in shell

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def add(self, face, /) -> None:
        """
        add(face, face)
        """
        ...

    def build(self, shell, sewtolerance, fixtolerance, /) -> None:
        """
        build(shell, sewtolerance, fixtolerance)
        """
        ...

    def clear(self) -> None:
        """
        Clears internal data structure
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_FixSmallFace.pyi:15
class FixSmallFace(Root):
    """
    Class for fixing operations on faces

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes by shape
        """
        ...

    def perform(self) -> None:
        """
        Fixing case of spot face
        """
        ...

    def fixSpotFace(self) -> None:
        """
        Fixing case of spot face, if tol = -1 used local tolerance
        """
        ...

    def replaceVerticesInCaseOfSpot(self) -> None:
        """
        Compute average vertex and replacing vertices by new one
        """
        ...

    def removeFacesInCaseOfSpot(self) -> None:
        """
        Remove spot face from compound
        """
        ...

    def fixStripFace(self) -> None:
        """
        Fixing case of strip face, if tol = -1 used local tolerance
        """
        ...

    def removeFacesInCaseOfStrip(self) -> None:
        """
        Remove strip face from compound
        """
        ...

    def fixSplitFace(self) -> TopoShape:
        """
        Fixes cases related to split faces within the given shape.
        It may return a modified shape after fixing the issues.
        """
        ...

    def fixFace(self) -> None:
        """
        Fixes issues related to the specified face and returns the modified face.
        """
        ...

    def fixShape(self) -> None:
        """
        Fixes issues in the overall geometric shape.
        This function likely encapsulates higher-level fixes that involve multiple faces or elements.
        """
        ...

    def shape(self) -> TopoShape:
        """
        Returns the current state of the geometric shape after potential modifications.
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_FixSmallSolid.pyi:14
class FixSmallSolid(Root):
    """
    Fixing solids with small size

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def setFixMode(self, theMode: int, /) -> None:
        """
        Set working mode for operator:
        - theMode = 0 use both WidthFactorThreshold and VolumeThreshold parameters
        - theMode = 1 use only WidthFactorThreshold parameter
        - theMode = 2 use only VolumeThreshold parameter
        """
        ...

    def setVolumeThreshold(self) -> None:
        """
        Set or clear volume threshold for small solids
        """
        ...

    def setWidthFactorThreshold(self) -> None:
        """
        Set or clear width factor threshold for small solids
        """
        ...

    def remove(self) -> None:
        """
        Remove small solids from the given shape
        """
        ...

    def merge(self) -> None:
        """
        Merge small solids in the given shape to adjacent non-small ones
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_FreeBounds.pyi:16
class FreeBounds:
    """
    This class is intended to output free bounds of the shape

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def closedWires(self) -> TopoShapeCompound:
        """
        Returns compound of closed wires out of free edges
        """
        ...

    def openWires(self) -> TopoShapeCompound:
        """
        Returns compound of open wires out of free edges
        """
        ...

    def shape(self) -> TopoShape:
        """
        Returns modified source shape
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Root.pyi:23
class Root:
    """
    Root class for fixing operations

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Precision: float = ...
    'Basic precision value'
    MinTolerance: float = ...
    'Minimal allowed tolerance'
    MaxTolerance: float = ...
    'Maximal allowed tolerance'

    def limitTolerance(self) -> float:
        """
        Returns tolerance limited by [MinTolerance,MaxTolerance]
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Shape.pyi:15
class Shape(Root):
    """
    Class for fixing operations on shapes

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    FixSolidMode: bool = ...
    'Mode for applying fixes of ShapeFix_Solid'
    FixFreeShellMode: bool = ...
    'Mode for applying fixes of ShapeFix_Shell'
    FixFreeFaceMode: bool = ...
    'Mode for applying fixes of ShapeFix_Face'
    FixFreeWireMode: bool = ...
    'Mode for applying fixes of ShapeFix_Wire'
    FixSameParameterMode: bool = ...
    'Mode for applying ShapeFix::SameParameter after all fixes'
    FixVertexPositionMode: bool = ...
    'Mode for applying ShapeFix::FixVertexPosition before all fixes'
    FixVertexTolMode: bool = ...
    'Mode for fixing tolerances of vertices on whole shape'

    def init(self) -> None:
        """
        Initializes by shape
        """
        ...

    def perform(self) -> None:
        """
        Iterates on sub- shape and performs fixes
        """
        ...

    def shape(self) -> TopoShape:
        """
        Returns resulting shape
        """
        ...

    def fixSolidTool(self) -> object:
        """
        Returns tool for fixing solids
        """
        ...

    def fixShellTool(self) -> object:
        """
        Returns tool for fixing shells
        """
        ...

    def fixFaceTool(self) -> object:
        """
        Returns tool for fixing faces
        """
        ...

    def fixWireTool(self) -> object:
        """
        Returns tool for fixing wires
        """
        ...

    def fixEdgeTool(self) -> object:
        """
        Returns tool for fixing edges
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_ShapeTolerance.pyi:16
class ShapeTolerance:
    """
    Modifies tolerances of sub-shapes (vertices, edges, faces)

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    @overload
    def limitTolerance(self, shape: TopoShape, tmin: float, /) -> None:
        ...

    @overload
    def limitTolerance(self, shape: TopoShape, tmin: float, tmax: float, ShapeEnum: str=None, /) -> None:
        ...

    def limitTolerance(self, shape: TopoShape, tmin: float, tmax: float=0, ShapeEnum: str=None, /) -> None:
        """
        limitTolerance(shape, tmin, [tmax=0, ShapeEnum=SHAPE])
        """
        ...

    @overload
    def setTolerance(self, shape: TopoShape, precision: float, /) -> None:
        ...

    @overload
    def setTolerance(self, shape: TopoShape, precision: float, ShapeEnum: str=None, /) -> None:
        ...

    def setTolerance(self, shape: TopoShape, precision: float, ShapeEnum: str=None, /) -> None:
        """
        setTolerance(shape, precision, [ShapeEnum=SHAPE])
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Shell.pyi:16
class Shell(Root):
    """
    Root class for fixing operations

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    FixOrientationMode: bool = ...
    'Mode for applying fixes of orientation of faces'
    FixFaceMode: bool = ...
    'Mode for applying fixes using ShapeFix_Face'

    def init(self) -> None:
        """
        Initializes by shell
        """
        ...

    def fixFaceTool(self) -> None:
        """
        Returns tool for fixing faces
        """
        ...

    def perform(self) -> None:
        """
        Iterates on subshapes and performs fixes
        """
        ...

    def shell(self) -> None:
        """
        Returns fixed shell (or subset of oriented faces)
        """
        ...

    def numberOfShells(self) -> None:
        """
        Returns the number of obtained shells
        """
        ...

    def shape(self) -> None:
        """
        In case of multiconnexity returns compound of fixed shells and one shell otherwise
        """
        ...

    def errorFaces(self) -> None:
        """
        Returns not oriented subset of faces
        """
        ...

    def fixFaceOrientation(self) -> None:
        """
        Fixes orientation of faces in shell.
        Changes orientation of face in the shell, if it is oriented opposite
        to neighbouring faces. If it is not possible to orient all faces in the
        shell (like in case of mebious band), this method orients only subset
        of faces. Other faces are stored in Error compound.
        Modes :
        isAccountMultiConex - mode for account cases of multiconnexity.
        If this mode is equal to Standard_True, separate shells will be created
        in the cases of multiconnexity. If this mode is equal to Standard_False,
        one shell will be created without account of multiconnexity. By default - Standard_True;
        NonManifold - mode for creation of non-manifold shells.
        If this mode is equal to Standard_True one non-manifold will be created from shell
        contains multishared edges. Else if this mode is equal to Standard_False only
        manifold shells will be created. By default - Standard_False.
        """
        ...

    def setNonManifoldFlag(self) -> None:
        """
        Sets NonManifold flag
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Solid.pyi:16
class Solid(Root):
    """
    Root class for fixing operations

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    FixShellMode: bool = ...
    'Mode for applying fixes of ShapeFix_Shell'
    FixShellOrientationMode: bool = ...
    '\n    Mode for applying analysis and fixes of\n    orientation of shells in the solid\n    '
    CreateOpenSolidMode: bool = ...
    'Mode for creation of solids'

    def init(self) -> None:
        """
        Initializes by solid
        """
        ...

    def perform(self) -> None:
        """
        Iterates on subshapes and performs fixes
        """
        ...

    def solidFromShell(self) -> None:
        """
        Calls MakeSolid and orients the solid to be not infinite
        """
        ...

    def solid(self) -> None:
        """
        Returns resulting solid
        """
        ...

    def shape(self) -> None:
        """
        In case of multiconnexity returns compound of fixed solids
        else returns one solid
        """
        ...

    def fixShellTool(self) -> None:
        """
        Returns tool for fixing shells
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_SplitCommonVertex.pyi:14
class SplitCommonVertex(Root):
    """
    Class for fixing operations on shapes

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes by shape
        """
        ...

    def perform(self) -> None:
        """
        Iterates on sub- shape and performs fixes
        """
        ...

    def shape(self) -> object:
        """
        Returns resulting shape
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_SplitTool.pyi:15
class SplitTool:
    """
    Tool for splitting and cutting edges

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def splitEdge(self) -> None:
        """
        Split edge on two new edges using new vertex
        """
        ...

    def cutEdge(self) -> None:
        """
        Cut edge by parameters pend and cut
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Wire.pyi:16
class Wire(Root):
    """
    Class for fixing operations on wires

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes by wire, face, precision
        """
        pass

    def fixEdgeTool(self) -> None:
        """
        Returns tool for fixing wires
        """
        pass

    def clearModes(self) -> None:
        """
        Sets all modes to default
        """
        pass

    def clearStatuses(self) -> None:
        """
        Clears all statuses
        """
        pass

    def load(self) -> None:
        """
        Load data for the wire, and drops all fixing statuses
        """
        pass

    def setFace(self) -> None:
        """
        Set working face for the wire
        """
        pass

    def setSurface(self, surface: object, Placement: object=..., /) -> None:
        """
        setSurface(surface, [Placement])
        Set surface for the wire
        """
        pass

    def setMaxTailAngle(self) -> None:
        """
        Sets the maximal allowed angle of the tails in radians
        """
        pass

    def setMaxTailWidth(self) -> None:
        """
        Sets the maximal allowed width of the tails
        """
        pass

    def isLoaded(self) -> None:
        """
        Tells if the wire is loaded
        """
        pass

    def isReady(self) -> None:
        """
        Tells if the wire and face are loaded
        """
        pass

    def numberOfEdges(self) -> None:
        """
        Returns number of edges in the working wire
        """
        pass

    def wire(self) -> None:
        """
        Makes the resulting Wire (by basic Brep_Builder)
        """
        pass

    def wireAPIMake(self) -> None:
        """
        Makes the resulting Wire (by BRepAPI_MakeWire)
        """
        pass

    def face(self) -> None:
        """
        Returns working face
        """
        pass

    def perform(self) -> None:
        """
        Iterates on subshapes and performs fixes
        """
        pass

    def fixReorder(self) -> None:
        """
        Performs an analysis and reorders edges in the wire
        """
        pass

    def fixSmall(self) -> None:
        """
        Applies fixSmall(...) to all edges in the wire
        """
        pass

    def fixConnected(self, num: int, /) -> None:
        """
        Applies fixConnected(num) to all edges in the wire
        Connection between first and last edges is treated only if
        flag ClosedMode is True
        If prec is -1 then maxTolerance() is taken.
        """
        pass

    def fixEdgeCurves(self) -> None:
        """
        Groups the fixes dealing with 3d and pcurves of the edges
        """
        pass

    def fixDegenerated(self) -> None:
        """
        Applies fixDegenerated(...) to all edges in the wire
        """
        pass

    def fixSelfIntersection(self) -> None:
        """
        Applies FixSelfIntersectingEdge(num) and
         FixIntersectingEdges(num) to all edges in the wire and
         FixIntersectingEdges(num1, num2) for all pairs num1 and num2
         and removes wrong edges if any
        """
        pass

    def fixLacking(self) -> None:
        """
        Applies FixLacking(num) to all edges in the wire
        Connection between first and last edges is treated only if
        flag ClosedMode is True
        If 'force' is False (default), test for connectness is done with
        precision of vertex between edges, else it is done with minimal
        value of vertex tolerance and Analyzer.Precision().
        Hence, 'force' will lead to inserting lacking edges in replacement
        of vertices which have big tolerances.
        """
        pass

    def fixClosed(self) -> None:
        """
        Fixes a wire to be well closed
        """
        pass

    def fixGaps3d(self, num: int, /) -> None:
        """
        Fixes gaps between ends of 3d curves on adjacent edges
        """
        pass

    def fixGaps2d(self, num: int, /) -> None:
        """
        Fixes gaps between ends of pcurves on adjacent edges
        """
        pass

    def fixSeam(self) -> None:
        """
        Fixes seam edges
        """
        pass

    def fixShifted(self) -> None:
        """
        Fixes edges which have pcurves shifted by whole parameter
        range on the closed surface
        """
        pass

    def fixNotchedEdges(self) -> None:
        """
        Fixes Notch edges.Check if there are notch edges in 2d and fix it
        """
        pass

    def fixGap3d(self, num: int, /) -> None:
        """
        Fixes gap between ends of 3d curves on num-1 and num-th edges
        """
        pass

    def fixGap2d(self, num: int, /) -> None:
        """
        Fixes gap between ends of pcurves on num-1 and num-th edges
        """
        pass

    def fixTails(self) -> None:
        """
        Fixes issues related to 'tails' in the geometry.
        Tails are typically small, undesired protrusions or deviations in the curves or edges that need correction.
        This method examines the geometry and applies corrective actions to eliminate or reduce the presence of tails.
        """
        pass
    ModifyTopologyMode: bool = ...
    'Mode for modifying topology of the wire'
    ModifyGeometryMode: bool = ...
    'Mode for modifying geometry of vertexes and edges'
    ModifyRemoveLoopMode: bool = ...
    'Mode for modifying edges'
    ClosedWireMode: bool = ...
    '\n    Mode which defines whether the wire\n    is to be closed (by calling methods like fixDegenerated()\n    and fixConnected() for last and first edges)\n    '
    PreferencePCurveMode: bool = ...
    "\n    Mode which defines whether the 2d 'True'\n    representation of the wire is preferable over 3d one in the\n    case of ambiguity in FixEdgeCurves\n    "
    FixGapsByRangesMode: bool = ...
    '\n    Mode which defines whether tool\n    tries to fix gaps first by changing curves ranges (i.e.\n    using intersection, extrema, projections) or not\n    '
    FixReorderMode: bool = ...
    "\n    Mode which performs an analysis and reorders edges in the wire using class WireOrder.\n    Flag 'theModeBoth' determines the use of miscible mode if necessary.\n    "
    FixSmallMode: bool = ...
    'Mode which applies FixSmall(num) to all edges in the wire'
    FixConnectedMode: bool = ...
    "\n    Mode which applies FixConnected(num) to all edges in the wire\n    Connection between first and last edges is treated only if\n    flag ClosedMode is True\n    If 'prec' is -1 then MaxTolerance() is taken.\n    "
    FixEdgeCurvesMode: bool = ...
    '\n    Mode which groups the fixes dealing with 3d and pcurves of the edges.\n    The order of the fixes and the default behaviour are:\n    ShapeFix_Edge::FixReversed2d\n    ShapeFix_Edge::FixRemovePCurve (only if forced)\n    ShapeFix_Edge::FixAddPCurve\n    ShapeFix_Edge::FixRemoveCurve3d (only if forced)\n    ShapeFix_Edge::FixAddCurve3d\n    FixSeam,\n    FixShifted,\n    ShapeFix_Edge::FixSameParameter\n    '
    FixDegeneratedMode: bool = ...
    '\n    Mode which applies FixDegenerated(num) to all edges in the wire\n    Connection between first and last edges is treated only if\n    flag ClosedMode is True\n    '
    FixSelfIntersectionMode: bool = ...
    '\n    Mode which applies FixSelfIntersectingEdge(num) and\n    FixIntersectingEdges(num) to all edges in the wire and\n    FixIntersectingEdges(num1, num2) for all pairs num1 and num2\n    and removes wrong edges if any\n    '
    FixLackingMode: bool = ...
    "\n    Mode which applies FixLacking(num) to all edges in the wire\n    Connection between first and last edges is treated only if\n    flag ClosedMode is True\n    If 'force' is False (default), test for connectness is done with\n    precision of vertex between edges, else it is done with minimal\n    value of vertex tolerance and Analyzer.Precision().\n    Hence, 'force' will lead to inserting lacking edges in replacement\n    of vertices which have big tolerances.\n    "
    FixGaps3dMode: bool = ...
    '\n    Mode which fixes gaps between ends of 3d curves on adjacent edges\n    myPrecision is used to detect the gaps.\n    '
    FixGaps2dMode: bool = ...
    '\n    Mode whixh fixes gaps between ends of pcurves on adjacent edges\n    myPrecision is used to detect the gaps.\n    '
    FixReversed2dMode: bool = ...
    'Mode which fixes the reversed in 2d'
    FixRemovePCurveMode: bool = ...
    'Mode which removePCurve in 2d'
    FixAddPCurveMode: bool = ...
    'Mode which fixes addCurve in 2d'
    FixRemoveCurve3dMode: bool = ...
    'Mode which fixes removeCurve in 3d '
    FixAddCurve3dMode: bool = ...
    'Mode which fixes addCurve in 3d'
    FixSeamMode: bool = ...
    'Mode which fixes Seam '
    FixShiftedMode: bool = ...
    'Mode which fixes Shifted'
    FixSameParameterMode: bool = ...
    'Mode which fixes sameParameter in 2d'
    FixVertexToleranceMode: bool = ...
    'Mode which fixes VertexTolerence in 2d'
    FixNotchedEdgesMode: bool = ...
    'Mode which fixes NotchedEdges in 2d'
    FixSelfIntersectingEdgeMode: bool = ...
    'Mode which fixes SelfIntersectionEdge in 2d'
    FixIntersectingEdgesMode: bool = ...
    'Mode which fixes IntersectingEdges in 2d'
    FixNonAdjacentIntersectingEdgesMode: bool = ...
    'Mode which fixes NonAdjacentIntersectingEdges in 2d'
    FixTailMode: bool = ...
    'Mode which fixes Tails in 2d'

# src/Mod/Part/App/ShapeFix/ShapeFix_WireVertex.pyi:14
class WireVertex:
    """
    Fixing disconnected edges in the wire

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Loads the wire, ininializes internal analyzer with the given precision
        """
        ...

    def wire(self) -> object:
        """
        Returns resulting wire
        """
        ...

    def fixSame(self) -> int:
        """
        Returns the count of fixed vertices, 0 if none
        """
        ...

    def fix(self) -> int:
        """
        Fixes all statuses except Disjoined, i.e. the cases in which a
        common value has been set, with or without changing parameters
        Returns the count of fixed vertices, 0 if none
        """
        ...

# src/Mod/Part/App/ShapeFix/ShapeFix_Wireframe.pyi:16
class Wireframe(Root):
    """
    Provides methods for fixing wireframe of shape

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    ModeDropSmallEdges: bool = ...
    'Returns mode managing removing small edges'
    LimitAngle: float = ...
    'Limit angle for merging edges'

    def clearStatuses(self) -> None:
        """
        Clears all statuses
        """
        ...

    def load(self) -> None:
        """
        Loads a shape, resets statuses
        """
        ...

    def fixWireGaps(self) -> None:
        """
        Fixes gaps between ends of curves of adjacent edges
        """
        ...

    def fixSmallEdges(self) -> None:
        """
        Fixes small edges in shape by merging adjacent edges
        """
        ...

    def shape(self) -> None:
        ...
