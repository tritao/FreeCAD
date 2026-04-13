# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def read(*args: Any) -> Any: ...
def open(*args: Any) -> Any: ...
def insert(*args: Any) -> Any: ...
def export(*args: Any, **kwargs: Any) -> Any: ...
def show(*args: Any) -> Any: ...
def createBox(*args: Any) -> Any: ...
def createPlane(*args: Any) -> Any: ...
def createSphere(*args: Any) -> Any: ...
def createEllipsoid(*args: Any) -> Any: ...
def createCylinder(*args: Any) -> Any: ...
def createCone(*args: Any) -> Any: ...
def createTorus(*args: Any) -> Any: ...
def calculateEigenTransform(*args: Any) -> Any: ...
def polynomialFit(*args: Any) -> Any: ...
def minimumVolumeOrientedBox(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCAD import ComplexGeoData
from FreeCAD import GeoFeature

from typing import *

# src/Mod/Mesh/App/Edge.pyi:16
class Edge:
    """
    Edge in mesh
    This is an edge of a facet in a MeshObject. You can get it by e.g. iterating over the facets of a
    mesh and calling getEdge(index).

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    License: LGPL-2.1-or-later
    """

    def intersectWithEdge(self) -> Any:
        """intersectWithEdge(Edge) -> list
        Get a list of intersection points with another edge."""
        ...

    def isParallel(self) -> Any:
        """isParallel(Edge) -> bool
        Checks if the two edges are parallel."""
        ...

    def isCollinear(self) -> Any:
        """isCollinear(Edge) -> bool
        Checks if the two edges are collinear."""
        ...

    def unbound(self) -> Any:
        """method unbound()
        Cut the connection to a MeshObject. The edge becomes
        free and is more or less a simple edge.
        After calling unbound() no topological operation will
        work!"""
        ...
    Index: Final[int]
    'The index of this edge of the facet'
    Points: Final[list]
    'A list of points of the edge'
    PointIndices: Final[tuple]
    'The index tuple of point vertices of the mesh this edge is built of'
    NeighbourIndices: Final[tuple]
    'The index tuple of neighbour facets of the mesh this edge is adjacent with'
    Length: Final[float]
    'The length of the edge'
    Bound: Final[bool]
    'Bound state of the edge'

# src/Mod/Mesh/App/Facet.pyi:16
class Facet:
    """
    Facet in mesh
    This is a facet in a MeshObject. You can get it by e.g. iterating a
    mesh. The facet has a connection to its mesh and allows therefore
    topological operations. It is also possible to create an unbounded facet e.g. to create
    a mesh. In this case the topological operations will fail. The same is
    when you cut the bound to the mesh by calling unbound().

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def unbound(self) -> Any:
        """method unbound()
        Cut the connection to a MeshObject. The facet becomes
        free and is more or less a simple facet.
        After calling unbound() no topological operation will
        work!"""
        ...

    def intersect(self) -> Any:
        """intersect(Facet) -> list
        Get a list of intersection points with another triangle."""
        ...

    def isDegenerated(self) -> Any:
        """isDegenerated([float]) -> boolean
        Returns true if the facet is degenerated, otherwise false."""
        ...

    def isDeformed(self) -> Any:
        """isDegenerated(MinAngle, MaxAngle) -> boolean
        Returns true if the facet is deformed, otherwise false.
        A triangle is considered deformed if an angle is less than MinAngle
        or higher than MaxAngle.
        The two angles are given in radian."""
        ...

    def getEdge(self) -> Any:
        """getEdge(int) -> Edge
        Returns the edge of the facet."""
        ...
    Index: Final[int]
    'The index of this facet in the MeshObject'
    Bound: Final[bool]
    'Bound state of the facet'
    Normal: Final[Any]
    'Normal vector of the facet.'
    Points: Final[list]
    'A list of points of the facet'
    PointIndices: Final[tuple]
    'The index tuple of point vertices of the mesh this facet is built of'
    NeighbourIndices: Final[tuple]
    'The index tuple of neighbour facets of the mesh this facet is adjacent with'
    Area: Final[float]
    'The area of the facet'
    AspectRatio: Final[float]
    'The aspect ratio of the facet computed by longest edge and its height'
    AspectRatio2: Final[float]
    'The aspect ratio of the facet computed by radius of circum-circle and in-circle'
    Roundness: Final[float]
    'The roundness of the facet'
    CircumCircle: Final[tuple]
    'The center and radius of the circum-circle'
    InCircle: Final[tuple]
    'The center and radius of the in-circle'

# src/Mod/Mesh/App/Mesh.pyi:24
class Mesh(ComplexGeoData):
    """
    Mesh() -- Create an empty mesh object.

    This class allows one to manipulate the mesh object by adding new facets, deleting facets, importing from an STL file,
    transforming the mesh and much more.
    For a complete overview of what can be done see also the documentation of mesh.
    A mesh object cannot be added to an existing document directly. Therefore the document must create an object
    with a property class that supports meshes.
    Example:
    m = Mesh.Mesh()
    ... # Manipulate the mesh
    d = FreeCAD.activeDocument() # Get a reference to the actie document
    f = d.addObject("Mesh::Feature", "Mesh") # Create a mesh feature
    f.Mesh = m # Assign the mesh object to the internal property
    d.recompute()

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def read(self, **kwargs) -> Any:
        """Read in a mesh object from file.
        mesh.read(Filename='mymesh.stl')
        mesh.read(Stream=file,Format='STL')"""
        ...

    def write(self, **kwargs) -> Any:
        """Write the mesh object into file.
        mesh.write(Filename='mymesh.stl',[Format='STL',Name='Object name',Material=colors])
        mesh.write(Stream=file,Format='STL',[Name='Object name',Material=colors])"""
        ...

    def writeInventor(self) -> Any:
        """Write the mesh in OpenInventor format to a string."""
        ...

    def copy(self) -> Any:
        """Create a copy of this mesh"""
        ...

    def offset(self) -> Any:
        """Move the point along their normals"""
        ...

    def offsetSpecial(self) -> Any:
        """Move the point along their normals"""
        ...

    def crossSections(self) -> Any:
        """Get cross-sections of the mesh through several planes"""
        ...

    def unite(self) -> Any:
        """Union of this and the given mesh object."""
        ...

    def intersect(self) -> Any:
        """Intersection of this and the given mesh object."""
        ...

    def difference(self) -> Any:
        """Difference of this and the given mesh object."""
        ...

    def inner(self) -> Any:
        """Get the part inside of the intersection"""
        ...

    def outer(self) -> Any:
        """Get the part outside the intersection"""
        ...

    def section(self, **kwargs) -> Any:
        """Get the section curves of this and the given mesh object.
        lines = mesh.section(mesh2, [ConnectLines=True, MinDist=0.0001])"""
        ...

    def translate(self) -> Any:
        """Apply a translation to the mesh"""
        ...

    def rotate(self) -> Any:
        """Apply a rotation to the mesh"""
        ...

    def transform(self) -> Any:
        """Apply a transformation to the mesh"""
        ...

    def transformToEigen(self) -> Any:
        """Transform the mesh to its eigenbase"""
        ...

    def getEigenSystem(self) -> Any:
        """Get Eigen base of the mesh"""
        ...

    def addFacet(self) -> Any:
        """Add a facet to the mesh"""
        ...

    def addFacets(self) -> Any:
        """Add a list of facets to the mesh"""
        ...

    def removeFacets(self) -> Any:
        """Remove a list of facet indices from the mesh"""
        ...

    def removeNeedles(self) -> Any:
        """Remove all edges that are smaller than a given length"""
        ...

    def removeFullBoundaryFacets(self) -> Any:
        """Remove facets whose all three points are on the boundary"""
        ...

    def getInternalFacets(self) -> Any:
        """Builds a list of facet indices with triangles that are inside a volume mesh"""
        ...

    def rebuildNeighbourHood(self) -> Any:
        """Repairs the neighbourhood which might be broken"""
        ...

    def addMesh(self) -> Any:
        """Combine this mesh with another mesh."""
        ...

    def setPoint(self) -> Any:
        """setPoint(int, Vector)
        Sets the point at index."""
        ...

    def movePoint(self) -> Any:
        """movePoint(int, Vector)
        This method moves the point in the mesh along the
        given vector. This affects the geometry of the mesh.
        Be aware that moving points may cause self-intersections."""
        ...

    def getPointNormals(self) -> Any:
        """getPointNormals()
        Get the normals of the points."""
        ...

    def addSegment(self) -> Any:
        """Add a list of facet indices that describes a segment to the mesh"""
        ...

    def countSegments(self) -> Any:
        """Get the number of segments which may also be 0"""
        ...

    def getSegment(self) -> Any:
        """Get a list of facet indices that describes a segment"""
        ...

    def getSeparateComponents(self) -> Any:
        """Returns a list containing the different
        components (separated areas) of the mesh as separate meshes

        import Mesh
        for c in mesh.getSeparatecomponents():
        Mesh.show(c)"""
        ...

    def getFacetSelection(self) -> Any:
        """Get a list of the indices of selected facets"""
        ...

    def getPointSelection(self) -> Any:
        """Get a list of the indices of selected points"""
        ...

    def meshFromSegment(self) -> Any:
        """Create a mesh from segment"""
        ...

    def clear(self) -> Any:
        """Clear the mesh"""
        ...

    def isSolid(self) -> Any:
        """Check if the mesh is a solid"""
        ...

    def hasNonManifolds(self) -> Any:
        """Check if the mesh has non-manifolds"""
        ...

    def removeNonManifolds(self) -> Any:
        """Remove non-manifolds"""
        ...

    def removeNonManifoldPoints(self) -> Any:
        """Remove non-manifold points"""
        ...

    def hasSelfIntersections(self) -> Any:
        """Check if the mesh intersects itself"""
        ...

    def getSelfIntersections(self) -> Any:
        """Returns a tuple of indices of intersecting triangles"""
        ...

    def fixSelfIntersections(self) -> Any:
        """Repair self-intersections"""
        ...

    def removeFoldsOnSurface(self) -> Any:
        """Remove folds on surfaces"""
        ...

    def hasNonUniformOrientedFacets(self) -> Any:
        """Check if the mesh has facets with inconsistent orientation"""
        ...

    def countNonUniformOrientedFacets(self) -> Any:
        """Get the number of wrong oriented facets"""
        ...

    def getNonUniformOrientedFacets(self) -> Any:
        """Get a tuple of wrong oriented facets"""
        ...

    def hasInvalidPoints(self) -> Any:
        """Check if the mesh has points with invalid coordinates (NaN)"""
        ...

    def removeInvalidPoints(self) -> Any:
        """Remove points with invalid coordinates (NaN)"""
        ...

    def hasPointsOnEdge(self) -> Any:
        """Check if points lie on edges"""
        ...

    def removePointsOnEdge(self, **kwargs) -> Any:
        """removePointsOnEdge(FillBoundary=False)
        Remove points that lie on edges.
        If FillBoundary is True then the holes by removing the affected facets
        will be re-filled."""
        ...

    def hasInvalidNeighbourhood(self) -> Any:
        """Check if the mesh has invalid neighbourhood indices"""
        ...

    def hasPointsOutOfRange(self) -> Any:
        """Check if the mesh has point indices that are out of range"""
        ...

    def hasFacetsOutOfRange(self) -> Any:
        """Check if the mesh has facet indices that are out of range"""
        ...

    def hasCorruptedFacets(self) -> Any:
        """Check if the mesh has corrupted facets"""
        ...

    def countComponents(self) -> Any:
        """Get the number of topologic independent areas"""
        ...

    def removeComponents(self) -> Any:
        """Remove components with less or equal to number of given facets"""
        ...

    def fixIndices(self) -> Any:
        """Repair any invalid indices"""
        ...

    def fixCaps(self) -> Any:
        """Repair caps by swapping the edge"""
        ...

    def fixDeformations(self) -> Any:
        """Repair deformed facets"""
        ...

    def fixDegenerations(self) -> Any:
        """Remove degenerated facets"""
        ...

    def removeDuplicatedPoints(self) -> Any:
        """Remove duplicated points"""
        ...

    def removeDuplicatedFacets(self) -> Any:
        """Remove duplicated facets"""
        ...

    def refine(self) -> Any:
        """Refine the mesh"""
        ...

    def splitEdges(self) -> Any:
        """Split all edges"""
        ...

    def splitEdge(self) -> Any:
        """Split edge"""
        ...

    def splitFacet(self) -> Any:
        """Split facet"""
        ...

    def swapEdge(self) -> Any:
        """Swap the common edge with the neighbour"""
        ...

    def collapseEdge(self) -> Any:
        """Remove an edge and both facets that share this edge"""
        ...

    def collapseFacet(self) -> Any:
        """Remove a facet"""
        ...

    def collapseFacets(self) -> Any:
        """Remove a list of facets"""
        ...

    def insertVertex(self) -> Any:
        """Insert a vertex into a facet"""
        ...

    def snapVertex(self) -> Any:
        """Insert a new facet at the border"""
        ...

    def printInfo(self) -> Any:
        """Get detailed information about the mesh"""
        ...

    def foraminate(self) -> Any:
        """Get a list of facet indices and intersection points"""
        ...

    def cut(self) -> Any:
        """Cuts the mesh with a given closed polygon
        cut(list, int) -> None
        The argument list is an array of points, a polygon
        The argument int is the mode: 0=inner, 1=outer"""
        ...

    def trim(self) -> Any:
        """Trims the mesh with a given closed polygon
        trim(list, int) -> None
        The argument list is an array of points, a polygon
        The argument int is the mode: 0=inner, 1=outer"""
        ...

    def trimByPlane(self) -> Any:
        """Trims the mesh with a given plane
        trimByPlane(Vector, Vector) -> None
        The plane is defined by a base and normal vector. Depending on the
        direction of the normal the part above or below will be kept."""
        ...

    def harmonizeNormals(self) -> Any:
        """Adjust wrong oriented facets"""
        ...

    def flipNormals(self) -> Any:
        """Flip the mesh normals"""
        ...

    def fillupHoles(self) -> Any:
        """Fillup holes"""
        ...

    def smooth(self, **kwargs) -> Any:
        """Smooth the mesh
        smooth([iteration=1,maxError=FLT_MAX])"""
        ...

    def decimate(self) -> Any:
        """Decimate the mesh
        decimate(tolerance(Float), reduction(Float))
        tolerance: maximum error
        reduction: reduction factor must be in the range [0.0,1.0]
        Example:
        mesh.decimate(0.5, 0.1) # reduction by up to 10 percent
        mesh.decimate(0.5, 0.9) # reduction by up to 90 percent"""
        ...

    def mergeFacets(self) -> Any:
        """Merge facets to optimize topology"""
        ...

    def optimizeTopology(self) -> Any:
        """Optimize the edges to get nicer facets"""
        ...

    def optimizeEdges(self) -> Any:
        """Optimize the edges to get nicer facets"""
        ...

    def nearestFacetOnRay(self) -> Any:
        """nearestFacetOnRay(tuple, tuple) -> dict
        Get the index and intersection point of the nearest facet to a ray.
        The first parameter is a tuple of three floats the base point of the ray,
        the second parameter is ut uple of three floats for the direction.
        The result is a dictionary with an index and the intersection point or
        an empty dictionary if there is no intersection."""
        ...

    def getPlanarSegments(self) -> Any:
        """getPlanarSegments(dev,[min faces=0]) -> list
        Get all planes of the mesh as segment.
        In the worst case each triangle can be regarded as single
        plane if none of its neighbours is coplanar."""
        ...

    def getSegmentsOfType(self) -> Any:
        """getSegmentsOfType(type, dev,[min faces=0]) -> list
        Get all segments of type.
        Type can be Plane, Cylinder or Sphere"""
        ...

    def getSegmentsByCurvature(self) -> Any:
        """getSegmentsByCurvature(list) -> list
        The argument list gives a list if tuples where it defines the preferred maximum curvature,
        the preferred minimum curvature, the tolerances and the number of minimum faces for the segment.
        Example:
        c=(1.0, 0.0, 0.1, 0.1, 500) # search for a cylinder with radius 1.0
        p=(0.0, 0.0, 0.1, 0.1, 500) # search for a plane
        mesh.getSegmentsByCurvature([c,p])"""
        ...

    def getCurvaturePerVertex(self) -> Any:
        """getCurvaturePerVertex() -> list
        The items in the list contains minimum and maximum curvature with their directions
        """
        ...
    Points: Final[list]
    'A collection of the mesh points\nWith this attribute it is possible to get access to the points of the mesh\nfor p in mesh.Points:\n\tprint p.x, p.y, p.z'
    CountPoints: Final[int]
    'Return the number of vertices of the mesh object.'
    CountEdges: Final[int]
    'Return the number of edges of the mesh object.'
    Facets: Final[list]
    'A collection of facets\nWith this attribute it is possible to get access to the facets of the mesh\nfor p in mesh.Facets:\n\tprint p'
    CountFacets: Final[int]
    'Return the number of facets of the mesh object.'
    Topology: Final[tuple]
    'Return the points and face indices as tuple.'
    Area: Final[float]
    'Return the area of the mesh object.'
    Volume: Final[float]
    'Return the volume of the mesh object.'

# src/Mod/Mesh/App/MeshFeature.pyi:18
class Feature(GeoFeature):
    """
    The Mesh::Feature class handles meshes.
    The Mesh.MeshFeature() function is for internal use only and cannot be used to create instances of this class.
    Therefore you must have a reference to a document, e.g. 'd' then you can create an instance with
    d.addObject("Mesh::Feature").

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    License: LGPL-2.1-or-later
    """

    def countPoints(self) -> Any:
        """Return the number of vertices of the mesh object"""
        ...

    def countFacets(self) -> Any:
        """Return the number of facets of the mesh object"""
        ...

    def harmonizeNormals(self) -> Any:
        """Adjust wrong oriented facets"""
        ...

    def smooth(self) -> Any:
        """Smooth the mesh data"""
        ...

    def decimate(self) -> Any:
        """
        Decimate the mesh
        decimate(tolerance(Float), reduction(Float))
        tolerance: maximum error
        reduction: reduction factor must be in the range [0.0,1.0]
        Example:
        mesh.decimate(0.5, 0.1) # reduction by up to 10 percent
        mesh.decimate(0.5, 0.9) # reduction by up to 90 percent

        or

        decimate(targwt size(int))
        mesh.decimate(mesh.CountFacets/2)
        """
        ...

    def removeNonManifolds(self) -> Any:
        """Remove non-manifolds"""
        ...

    def removeNonManifoldPoints(self) -> Any:
        """Remove non-manifold points"""
        ...

    def fixIndices(self) -> Any:
        """Repair any invalid indices"""
        ...

    def fixDegenerations(self) -> Any:
        """Remove degenerated facets"""
        ...

    def removeDuplicatedFacets(self) -> Any:
        """Remove duplicated facets"""
        ...

    def removeDuplicatedPoints(self) -> Any:
        """Remove duplicated points"""
        ...

    def fixSelfIntersections(self) -> Any:
        """Repair self-intersections"""
        ...

    def removeFoldsOnSurface(self) -> Any:
        """Remove folds on surfaces"""
        ...

    def removeInvalidPoints(self) -> Any:
        """Remove points with invalid coordinates (NaN)"""
        ...

# src/Mod/Mesh/App/MeshPoint.pyi:16
class MeshPoint:
    """
    Point in mesh
    This is a point in a MeshObject. You can get it by e.g. iterating a
    mesh. The point has a connection to its mesh and allows therefore
    topological operations. It is also possible to create an unbounded mesh point e.g. to create
    a mesh. In this case the topological operations will fail. The same is
    when you cut the bound to the mesh by calling unbound().

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    License: LGPL-2.1-or-later
    """

    def unbound(self) -> Any:
        """method unbound()
        Cut the connection to a MeshObject. The point becomes
        free and is more or less a simple vector/point.
        After calling unbound() no topological operation will
        work!"""
        ...
    Index: Final[int]
    'The index of this point in the MeshObject'
    Bound: Final[bool]
    'Bound state of the point'
    Normal: Final[Any]
    'Normal vector of the point computed by the surrounding mesh.'
    Vector: Final[Any]
    'Vector of the point.'
    x: Final[float]
    'The X component of the point.'
    y: Final[float]
    'The Y component of the point.'
    z: Final[float]
    'The Z component of the point.'
