# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def open(*args: Any) -> Any: ...
def insert(*args: Any) -> Any: ...
def export(*args: Any) -> Any: ...
def read(*args: Any) -> Any: ...
def frdToVTK(*args: Any) -> Any: ...
def readResult(*args: Any) -> Any: ...
def writeResult(*args: Any) -> Any: ...
def getVtkVersion(*args: Any) -> Any: ...
def getVtkVersionNumber(*args: Any) -> Any: ...
def vtkVersionCheck(*args: Any) -> Any: ...
def isVtkCompatible(*args: Any) -> Any: ...
def show(*args: Any) -> Any: ...

# Generated public type stubs from PyCXX binding method tables.
from typing import Any

class _SMESH_Hypothesis:
    def setLibName(self, lib_name: str, /) -> None: ...
    def getLibName(self) -> str: ...
    def setParameters(self, parameters: str, /) -> None: ...
    def getParameters(self) -> str: ...
    def setLastParameters(self, parameters: str, /) -> None: ...
    def getLastParameters(self) -> str: ...
    def clearParameters(self) -> None: ...
    def isAuxiliary(self) -> bool: ...
    def setParametersByMesh(self, mesh: FemMesh, shape: object, /) -> bool: ...

class StdMeshers_Arithmetic1D(_SMESH_Hypothesis):
    def setLength(self, length: float, start: bool, /) -> None: ...
    def getLength(self, start: bool, /) -> float: ...

class StdMeshers_AutomaticLength(_SMESH_Hypothesis):
    def setFineness(self, fineness: float, /) -> None: ...
    def getFineness(self) -> float: ...
    def getLength(self, mesh: FemMesh, shape_or_length: object, /) -> float: ...

class StdMeshers_Deflection1D(_SMESH_Hypothesis):
    def setDeflection(self, deflection: float, /) -> None: ...

class StdMeshers_LayerDistribution(_SMESH_Hypothesis):
    def setLayerDistribution(self) -> None: ...
    def getLayerDistribution(self) -> None: ...

class StdMeshers_LengthFromEdges(_SMESH_Hypothesis):
    def setMode(self, mode: int, /) -> None: ...
    def getMode(self) -> int: ...

class StdMeshers_LocalLength(_SMESH_Hypothesis):
    def setLength(self, length: float, /) -> None: ...
    def getLength(self) -> float: ...
    def setPrecision(self, precision: float, /) -> None: ...
    def getPrecision(self) -> float: ...

class StdMeshers_MaxElementArea(_SMESH_Hypothesis):
    def setMaxArea(self, area: float, /) -> None: ...
    def getMaxArea(self) -> float: ...

class StdMeshers_MaxElementVolume(_SMESH_Hypothesis):
    def setMaxVolume(self, volume: float, /) -> None: ...
    def getMaxVolume(self) -> float: ...

class StdMeshers_MaxLength(_SMESH_Hypothesis):
    def setLength(self, length: float, /) -> None: ...
    def getLength(self) -> float: ...
    def havePreestimatedLength(self) -> bool: ...
    def getPreestimatedLength(self) -> float: ...
    def setPreestimatedLength(self, length: float, /) -> None: ...
    def setUsePreestimatedLength(self, use_preestimated_length: bool, /) -> None: ...
    def getUsePreestimatedLength(self) -> bool: ...

class StdMeshers_NumberOfLayers(_SMESH_Hypothesis):
    def setNumberOfLayers(self, layers: int, /) -> None: ...
    def getNumberOfLayers(self) -> int: ...

class StdMeshers_NumberOfSegments(_SMESH_Hypothesis):
    def setNumberOfSegments(self, segments: int, /) -> None: ...
    def getNumberOfSegments(self) -> int: ...

class StdMeshers_SegmentLengthAroundVertex(_SMESH_Hypothesis):
    def setLength(self, length: float, /) -> None: ...
    def getLength(self) -> float: ...

class StdMeshers_StartEndLength(_SMESH_Hypothesis):
    def setLength(self, length: float, start: bool, /) -> None: ...
    def getLength(self, start: bool, /) -> float: ...

class StdMeshers_NotConformAllowed(_SMESH_Hypothesis):
    pass

class StdMeshers_QuadranglePreference(_SMESH_Hypothesis):
    pass

class StdMeshers_Quadrangle_2D(_SMESH_Hypothesis):
    pass

class StdMeshers_Regular_1D(_SMESH_Hypothesis):
    pass

class StdMeshers_UseExisting_1D(_SMESH_Hypothesis):
    pass

class StdMeshers_UseExisting_2D(_SMESH_Hypothesis):
    pass

class StdMeshers_CompositeSegment_1D(_SMESH_Hypothesis):
    pass

class StdMeshers_MEFISTO_2D(_SMESH_Hypothesis):
    pass

class StdMeshers_Prism_3D(_SMESH_Hypothesis):
    pass

class StdMeshers_Projection_1D(_SMESH_Hypothesis):
    pass

class StdMeshers_Projection_2D(_SMESH_Hypothesis):
    pass

class StdMeshers_Projection_3D(_SMESH_Hypothesis):
    pass

class StdMeshers_ProjectionSource1D(_SMESH_Hypothesis):
    pass

class StdMeshers_ProjectionSource2D(_SMESH_Hypothesis):
    pass

class StdMeshers_ProjectionSource3D(_SMESH_Hypothesis):
    pass

class StdMeshers_QuadraticMesh(_SMESH_Hypothesis):
    pass

class StdMeshers_RadialPrism_3D(_SMESH_Hypothesis):
    pass

class StdMeshers_SegmentAroundVertex_0D(_SMESH_Hypothesis):
    pass

class StdMeshers_Hexa_3D(_SMESH_Hypothesis):
    pass

# Generated public class stubs from binding .pyi specs.
from FreeCAD import ComplexGeoData
from FreeCAD.Base import Vector
from Part import Shape as TopoShape
from FreeCAD.Base import Placement
from Part import Face as TopoShapeFace
from Part import Edge as TopoShapeEdge
from Part import Solid as TopoShapeSolid
from Part import Vertex as TopoShapeVertex
from FreeCAD import GeoFeature
from FreeCAD import DocumentObject
from FreeCAD.Base import Unit

from typing import *

# src/Mod/Fem/App/FemMesh.pyi:24
class FemMesh(ComplexGeoData):
    """
    FemMesh class

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def setShape(self, shape: TopoShape, /) -> None:
        """Set the Part shape to mesh"""
        ...

    def compute(self) -> None:
        """Update the internal mesh structure"""
        ...

    def addHypothesis(self, hypothesis: object, shape: TopoShape, /) -> None:
        """Add hypothesis"""
        ...

    def setStandardHypotheses(self) -> None:
        """Set some standard hypotheses for the whole shape"""
        ...

    def addNode(self, x: float, y: float, z: float, elem_id: int | None=None, /) -> int:
        """Add a node by setting (x,y,z)."""
        ...

    @overload
    def addEdge(self, n1: int, n2: int, /) -> int:
        ...

    @overload
    def addEdge(self, nodes: list[int], elem_id: int | None=None, /) -> int:
        ...

    def addEdge(self, *args) -> int:
        """Add an edge by setting two node indices."""
        ...

    def addEdgeList(self, nodes: list[int], np: list[int], /) -> list[int]:
        """Add list of edges by list of node indices and list of nodes per edge."""
        ...

    @overload
    def addFace(self, n1: int, n2: int, n3: int, /) -> int:
        ...

    @overload
    def addFace(self, nodes: list[int], elem_id: int | None=None, /) -> int:
        ...

    def addFace(self) -> Any:
        """Add a face by setting three node indices."""
        ...

    def addFaceList(self, nodes: list[int], np: list[int], /) -> list[int]:
        """Add list of faces by list of node indices and list of nodes per face."""
        ...

    def addQuad(self, n1: int, n2: int, n3: int, n4: int, /) -> int:
        """Add a quad by setting four node indices."""
        ...

    @overload
    def addVolume(self, n1: int, n2: int, n3: int, n4: int, /) -> int:
        ...

    @overload
    def addVolume(self, nodes: list[int], elem_id: int | None=None, /) -> int:
        ...

    def addVolume(self, *args) -> int:
        """Add a volume by setting an arbitrary number of node indices."""
        ...

    def addVolumeList(self, nodes: list[int], np: list[int], /) -> list[int]:
        """Add list of volumes by list of node indices and list of nodes per volume."""
        ...

    def read(self, file_name: str, /) -> None:
        """
        Read in a various FEM mesh file formats.


        Supported formats: DAT, INP, MED, STL, UNV, VTK, Z88
        """
        ...

    def write(self, file_name: str, /) -> None:
        """
        Write out various FEM mesh file formats.

        Supported formats: BDF, DAT, INP, MED, STL, UNV, VTK, Z88
        """
        ...

    def writeABAQUS(self, fileName: str, elemParam: int, groupParam: bool, volVariant: str='standard', faceVariant: str='shell', edgeVariant: str='beam') -> None:
        """
        Write out as ABAQUS inp.

        elemParam:
            0: All elements
            1: Highest elements only
            2: FEM elements only (only edges not belonging to faces and faces not belonging to volumes)

        groupParam:
            True: Write group data
            False: Do not write group data

        volVariant: Volume elements
            "standard": Tetra4 -> C3D4, Penta6 -> C3D6, Hexa8 -> C3D8, Tetra10 -> C3D10, Penta15 -> C3D15, Hexa20 -> C3D20
            "reduced": Hexa8 -> C3D8R, Hexa20 -> C3D20R
            "incompatible": Hexa8 -> C3D8I
            "modified": Tetra10 -> C3D10T
            "fluid": Tetra4 -> F3D4, Penta6 -> F3D6, Hexa8  -> F3D8

        faceVariant: Face elements
            "shell": Tria3 -> S3, Quad4 -> S4, Tria6 -> S6, Quad8 -> S8
            "shell reduced": Tria3 -> S3, Quad4 -> S4R, Tria6 -> S6, Quad8 -> S8R
            "membrane": Tria3 -> M3D3, Quad4 -> M3D4, Tria6 -> M3D6, Quad8 -> M3D8
            "membrane reduced": Tria3 -> M3D3, Quad4 -> M3D4R, Tria6 -> M3D6, Quad8 -> M3D8R
            "stress": Tria3 -> CPS3, Quad4 -> CPS4, Tria6 -> CPS6, Quad8 -> CPS8
            "stress reduced": Tria3 -> CPS3, Quad4 -> CPS4R, Tria6 -> CPS6, Quad8 -> CPS8R
            "strain": Tria3 -> CPE3, Quad4 -> CPE4, Tria6 -> CPE6, Quad8 -> CPE8
            "strain reduced": Tria3 -> CPE3, Quad4 -> CPE4R, Tria6 -> CPE6, Quad8 -> CPE8R
            "axisymmetric": Tria3 -> CAX3, Quad4 -> CAX4, Tria6 -> CAX6, Quad8 -> CAX8
            "axisymmetric reduced": Tria3 -> CAX3, Quad4 -> CAX4R, Tria6 -> CAX6, Quad8 -> CAX8R

        edgeVariant: Edge elements
            "beam": Seg2 -> B31, Seg3 -> B32
            "beam reduced": Seg2 -> B31R, Seg3 -> B32R
            "truss": Seg2 -> T3D2, eg3 -> T3D3
            "network": Seg3 -> D

        Elements are selected according to CalculiX availability.
        For example if volume variant "modified" is selected, Tetra10 mesh
        elements are assigned to C3D10T and remain elements uses "standard".
        Axisymmetric, plane strain and plane stress elements expect nodes in the plane z=0.
        """
        ...

    def setTransform(self, placement: Placement, /) -> None:
        """Use a Placement object to perform a translation or rotation"""
        ...

    def copy(self) -> FemMesh:
        """Make a copy of this FEM mesh."""
        ...

    def getFacesByFace(self, face: TopoShapeFace, /) -> list[int]:
        """Return a list of face IDs which belong to a TopoFace"""
        ...

    def getEdgesByEdge(self, edge: TopoShapeEdge, /) -> list[int]:
        """Return a list of edge IDs which belong to a TopoEdge"""
        ...

    def getVolumesByFace(self, face: TopoShapeFace, /) -> list[tuple[int, int]]:
        """Return a list of tuples of volume IDs and face IDs which belong to a TopoFace"""
        ...

    def getccxVolumesByFace(self, face: TopoShapeFace, /) -> list[tuple[int, int]]:
        """Return a list of tuples of volume IDs and ccx face numbers which belong to a TopoFace"""
        ...

    def getNodeById(self, node_id: int, /) -> Vector:
        """Get the node position vector by a Node-ID"""
        ...

    def getNodesBySolid(self, shape: TopoShapeSolid, /) -> list[int]:
        """Return a list of node IDs which belong to a TopoSolid"""
        ...

    def getNodesByFace(self, face: TopoShapeFace, /) -> list[int]:
        """Return a list of node IDs which belong to a TopoFace"""
        ...

    def getNodesByEdge(self, edge: TopoShapeEdge, /) -> list[int]:
        """Return a list of node IDs which belong to a TopoEdge"""
        ...

    def getNodesByVertex(self, vertex: TopoShapeVertex, /) -> list[int]:
        """Return a list of node IDs which belong to a TopoVertex"""
        ...

    def getElementNodes(self, elem_id: int, /) -> tuple[int, ...]:
        """Return a tuple of node IDs to a given element ID"""
        ...

    def getNodeElements(self, elem_id: int, elem_type: str='All', /) -> tuple[int, ...]:
        """Return a tuple of specific element IDs associated to a given node ID"""
        ...

    def getGroupName(self, elem_id: int, /) -> str:
        """Return a string of group name to a given group ID"""
        ...

    def getGroupElementType(self, elem_id: int, /) -> str:
        """Return a string of group element type to a given group ID"""
        ...

    def getGroupElements(self, elem_id: int, /) -> tuple[int, ...]:
        """Return a tuple of ElementIDs to a given group ID"""
        ...

    def addGroup(self, name: str, group_type: str, group_id: int=-1, /) -> None:
        """
        Add a group to mesh with specific name and type

        name: string
        group_type: "All", "Node", "Edge", "Face", "Volume", "0DElement", "Ball"
        group_id: int
            Optional group_id is used to force specific id for group, but does
            not work, yet.
        """
        ...

    def addGroupElements(self, group_id: int, elements: list[int], /) -> None:
        """
        Add a tuple of ElementIDs to a given group ID

        group_id: int
        elements: list of int
            Notice that the elements have to be in the mesh.
        """
        ...

    def removeGroup(self, group_id: int, /) -> bool:
        """
        Remove a group with a given group ID
                            removeGroup(groupid)
                            groupid: int
                            Returns boolean."""
        ...

    def renameGroup(self) -> Any:
        """Rename a group with a given group ID
        renameGroup(id, name)
        groupid: int
        name: string"""
        ...

    def getElementType(self, elem_id: int, /) -> str:
        """Return the element type of a given ID"""
        ...

    def getIdByElementType(self, elem_type: str, /) -> tuple[int, ...]:
        """Return a tuple of IDs to a given element type"""
        ...
    Nodes: Final[dict]
    'Dictionary of Nodes by ID (int ID:Vector())'
    NodeCount: Final[int]
    'Number of nodes in the Mesh.'
    Edges: Final[tuple]
    'Tuple of edge IDs'
    EdgesOnly: Final[tuple]
    'Tuple of edge IDs which does not belong to any face (and thus not belong to any volume too)'
    EdgeCount: Final[int]
    'Number of edges in the Mesh.'
    Faces: Final[tuple]
    'Tuple of face IDs'
    FacesOnly: Final[tuple]
    'Tuple of face IDs which does not belong to any volume'
    FaceCount: Final[int]
    'Number of Faces in the Mesh.'
    TriangleCount: Final[int]
    'Number of Triangles in the Mesh.'
    QuadrangleCount: Final[int]
    'Number of Quadrangles in the Mesh.'
    PolygonCount: Final[int]
    'Number of Quadrangles in the Mesh.'
    Volumes: Final[tuple]
    'Tuple of volume IDs'
    VolumeCount: Final[int]
    'Number of Volumes in the Mesh.'
    TetraCount: Final[int]
    'Number of Tetras in the Mesh.'
    HexaCount: Final[int]
    'Number of Hexas in the Mesh.'
    PyramidCount: Final[int]
    'Number of Pyramids in the Mesh.'
    PrismCount: Final[int]
    'Number of Prisms in the Mesh.'
    PolyhedronCount: Final[int]
    'Number of Polyhedrons in the Mesh.'
    SubMeshCount: Final[int]
    'Number of SubMeshs in the Mesh.'
    GroupCount: Final[int]
    'Number of Groups in the Mesh.'
    Groups: Final[tuple]
    'Tuple of Group IDs.'
    Volume: Final[Any]
    'Volume of the mesh.'

# src/Mod/Fem/App/FemPostBranchFilter.pyi:17
class FemPostBranchFilter(FemPostFilter):
    """
    The FemPostBranch class.

    Author: Stefan Tröger (stefantroeger@gmx.net)
    License: LGPL-2.1-or-later
    """

    def getFilter(self) -> Any:
        """Returns all filters, that this pipeline uses (non recursive, result does not contain branch child filters)"""
        ...

    def recomputeChildren(self) -> Any:
        """Recomputes all children of the pipeline"""
        ...

    def getLastPostObject(self) -> Any:
        """Get the last post-processing object"""
        ...

    def holdsPostObject(self) -> Any:
        """Check if this pipeline holds a given post-processing object"""
        ...

# src/Mod/Fem/App/FemPostFilter.pyi:18
class FemPostFilter(FemPostObject):
    """
    The FemPostFilter class.

    Author: Stefan Tröger (stefantroeger@gmx.net)
    License: LGPL-2.1-or-later
    """

    def addFilterPipeline(self, name: str, source: vtkAlgorithm, target: vtkAlgorithm, /) -> None:
        """Registers a new vtk filter pipeline for data processing. Arguments are (name, source algorithm, target algorithm)."""
        ...

    def setActiveFilterPipeline(self, name: str, /) -> None:
        """Sets the filter pipeline that shall be used for data processing. Argument is the name of the filter pipeline to activate."""
        ...

    def getParentPostGroup(self) -> object:
        """Returns the postprocessing group the filter is in (e.g. a pipeline or branch object). None is returned if not in any."""
        ...

    def getInputData(self) -> object:
        """
        Returns the dataset available at the filter's input.
        Note: Can lead to a full recompute of the whole pipeline, hence best to call this only in "execute", where the user expects long calculation cycles.
        """
        ...

    def getInputVectorFields(self) -> list[str]:
        """
        Returns the names of all vector fields available on this filter's input.
        Note: Can lead to a full recompute of the whole pipeline, hence best to call this only in "execute", where the user expects long calculation cycles.
        """
        ...

    def getInputScalarFields(self) -> list[str]:
        """
        Returns the names of all scalar fields available on this filter's input.
        Note: Can lead to a full recompute of the whole pipeline, hence best to call this only in "execute", where the user expects long calculation cycles.
        """
        ...

    def getOutputAlgorithm(self) -> vtkAlgorithm:
        """Returns the filters vtk algorithm currently used as output (the one generating the Data field). Note that the output algorithm may change depending on filter settings."""
        ...

# src/Mod/Fem/App/FemPostObject.pyi:18
class FemPostObject(GeoFeature):
    """
    The FemPostObject class.

    Author: Mario Passaglia (mpassaglia@cbc.uba.ar)
    License: LGPL-2.1-or-later
    """

    def writeVTK(self, file_name: str, /) -> None:
        """
        Write data object to VTK file.

        filename: str
            File extension is automatically detected from data type.
        """
        ...

    def getDataSet(self) -> vtkDataSet:
        """
        Returns the current output dataset.
        For normal filters this is equal to the objects Data property output.
        However, a pipelines Data property could store multiple frames, and hence
        Data can be of type vtkCompositeData, which is not a vtkDataset.

        To simplify implementations this function always returns a vtkDataSet,
        and for a pipeline it will be the dataset of the currently selected frame.

        Note that the returned value could be None, if no data is set at all.
        """
        ...

# src/Mod/Fem/App/FemPostPipeline.pyi:20
class FemPostPipeline(FemPostObject):
    """
    The FemPostPipeline class.

    Author: Stefan Tröger (stefantroeger@gmx.net)
    License: LGPL-2.1-or-later
    """

    @overload
    def read(self, file_name: str, /) -> None:
        ...

    @overload
    def read(self, files: list[str] | tuple[str], values: list[int] | tuple[int], unit: Unit, frame_type: str, /) -> None:
        ...

    def read(self, *args) -> None:
        """
        Reads in a single vtk file or creates a multiframe result by reading in multiple result files.

        If multiframe is wanted, 4 argumenhts are needed:
        1. List of result files each being one frame,
        2. List of values valid for each frame (e.g. [s] if time data),
        3. the unit of the value as FreeCAD.Units.Unit,
        4. the Description of the frame type
        """
        ...

    def scale(self, scale: float, /) -> None:
        """scale the points of a loaded vtk file"""
        ...

    @overload
    def load(self, obj: DocumentObject, /) -> None:
        ...

    @overload
    def load(self, result: list[DocumentObject] | tuple[DocumentObject], values: list[float] | tuple[float], unit: Unit, frame_type: str, /) -> None:
        ...

    def load(self, *args) -> Any:
        """
        Load a single result object or create a multiframe result by loading multiple result frames.

        If multiframe is wanted, 4 argumenhts are needed:
        1. List of result objects each being one frame,
        2. List of values valid for each frame (e.g. [s] if time data),
        3. the unit of the value as FreeCAD.Units.Unit,
        4. the Description of the frame type
        """
        ...

    def getFilter(self) -> list[object]:
        """Returns all filters, that this pipeline uses (non recursive, result does not contain branch child filters)"""
        ...

    def recomputeChildren(self) -> None:
        """Recomputes all children of the pipeline"""
        ...

    def getLastPostObject(self) -> DocumentObject | None:
        """Get the last post-processing object"""
        ...

    def holdsPostObject(self, obj: DocumentObject, /) -> bool:
        """Check if this pipeline holds a given post-processing object"""
        ...

    def renameArrays(self, names: dict[str, str], /) -> None:
        """Change name of data arrays"""
        ...

    def addArrayFromFunction(self, functions: dict[str, str], /) -> None:
        """
        Add new arrays as functions of the current fields.
        The arrays are defined as "func_name": "func" key-value pairs.
        Field names behave similarly to those in the calculator filter.
        """
        ...

    def getOutputAlgorithm(self) -> vtkAlgorithm:
        """Returns the pipeline vtk algorithm, which generates the data passed to the pipelines filters.

        Note that the output algorithm may change depending on pipeline settings.
        """
        ...

    def setTimeInfo(self, frame_type: str, unit: Unit, /) -> None:
        """Set pipeline frame information."""
        ...
