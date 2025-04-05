from Base.Metadata import export, constmethod
from typing import Final, List, overload
from Base.Vector import Vector
from Part.TopoShapePy import TopoShape

from DrawView import DrawView

@export(
    Father="DrawView",
    Twin="DrawViewPart",
    TwinPointer="DrawViewPart",
    Include="Mod/TechDraw/App/DrawViewPart.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw",
)
class DrawViewPart(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Part Views

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """

    def getVisibleEdges(self) -> List[TopoShape]:
        """
        getVisibleEdges() - get the visible edges in the View as Part::TopoShapeEdges
        """
        ...

    def getVisibleVertexes(self) -> List[Vector]:
        """
        getVisibleVertexes() - get the visible vertexes as App.Vector in the View's coordinate system.
        """
        ...

    def getHiddenEdges(self) -> List[TopoShape]:
        """
        getHiddenEdges() - get the hidden edges in the View as Part::TopoShapeEdges
        """
        ...

    def getHiddenVertexes(self) -> List[Vector]:
        """
        getHiddenVertexes() - get the hidden vertexes as App.Vector in the View's coordinate system.
        """
        ...

    def makeCosmeticVertex(self, p1: Vector) -> int:
        """
        id = makeCosmeticVertex(p1) - add a CosmeticVertex at p1 (View coordinates). Returns unique id vertex.
        """
        ...

    def makeCosmeticVertex3d(self, p1: Vector) -> int:
        """
        id = makeCosmeticVertex3d(p1) - add a CosmeticVertex at p1 (3d model coordinates). Returns unique id vertex.
        """
        ...

    def getCosmeticVertex(self, id: int) -> object:
        """
        cv = getCosmeticVertex(id) - returns CosmeticVertex with unique id.
        """
        ...

    def getCosmeticVertexBySelection(self, name: str) -> object:
        """
        cv = getCosmeticVertexBySelection(name) - returns CosmeticVertex with name (Vertex6).  Used in selections.
        """
        ...

    def removeCosmeticVertex(self, cv: object) -> None:
        """
        removeCosmeticVertex(cv) - remove CosmeticVertex from View. Returns None.
        """
        ...

    def clearCosmeticVertices(self) -> None:
        """
        clearCosmeticVertices() - remove all CosmeticVertices from the View. Returns None.
        """
        ...

    def makeCosmeticLine(self, p1: Vector, p2: Vector) -> int:
        """
        tag = makeCosmeticLine(p1, p2) - add a CosmeticEdge from p1 to p2(View coordinates). Returns tag of new CosmeticEdge.
        """
        ...

    def makeCosmeticLine3D(self, p1: Vector, p2: Vector) -> int:
        """
        tag = makeCosmeticLine3D(p1, p2) - add a CosmeticEdge from p1 to p2(3D coordinates). Returns tag of new CosmeticEdge.
        """
        ...

    def makeCosmeticCircle(self, center: Vector, radius: float) -> int:
        """
        tag = makeCosmeticCircle(center, radius) - add a CosmeticEdge at center with radius radius(View coordinates). Returns tag of new CosmeticEdge.
        """
        ...

    def makeCosmeticCircleArc(self, center: Vector, radius: float, start: float, end: float) -> int:
        """
        tag = makeCosmeticCircleArc(center, radius, start, end) - add a CosmeticEdge at center with radius radius(View coordinates) from start angle to end angle. Returns tag of new CosmeticEdge.
        """
        ...

    def makeCosmeticCircle3d(self, center: Vector, radius: float) -> int:
        """
        tag = makeCosmeticCircle3d(center, radius) - add a CosmeticEdge at center (3d point) with radius. Returns tag of new CosmeticEdge.
        """
        ...

    def makeCosmeticCircleArc3d(self, center: Vector, radius: float, start: float, end: float) -> int:
        """
        tag = makeCosmeticCircleArc3d(center, radius, start, end) - add a CosmeticEdge at center (3d point) with radius from start angle to end angle. Returns tag of new CosmeticEdge.
        """
        ...

    def getCosmeticEdge(self, id: int) -> object:
        """
        ce = getCosmeticEdge(id) - returns CosmeticEdge with unique id.
        """
        ...

    def getCosmeticEdgeBySelection(self, name: str) -> object:
        """
        ce = getCosmeticEdgeBySelection(name) - returns CosmeticEdge by name (Edge25).  Used in selections
        """
        ...

    def removeCosmeticEdge(self, ce: object) -> None:
        """
        removeCosmeticEdge(ce) - remove CosmeticEdge ce from View. Returns None.
        """
        ...

    def makeCenterLine(self, subNames: List[str], mode: int) -> int:
        """
        makeCenterLine(subNames, mode) - draw a center line on this viewPart. SubNames is a list of n Faces, 2 Edges or 2 Vertices (ex [Face1,Face2,Face3]. Returns unique tag of added CenterLine.
        """
        ...

    def getCenterLine(self, id: int) -> object:
        """
        cl = getCenterLine(id) - returns CenterLine with unique id.
        """
        ...

    def getCenterLineBySelection(self, name: str) -> object:
        """
        cl = getCenterLineBySelection(name) - returns CenterLine by name (Edge25).  Used in selections
        """
        ...

    def removeCenterLine(self, cl: object) -> None:
        """
        removeCenterLine(cl) - remove CenterLine cl from View. Returns None.
        """
        ...

    def clearCosmeticEdges(self) -> None:
        """
        clearCosmeticEdges() - remove all CosmeticLines from the View. Returns None.
        """
        ...

    def clearCenterLines(self) -> None:
        """
        clearCenterLines() - remove all CenterLines from the View. Returns None.
        """
        ...

    def clearGeomFormats(self) -> None:
        """
        clearGeomFormats() - remove all GeomFormats from the View. Returns None.
        """
        ...

    def formatGeometricEdge(self, index: int, style: int, weight: float, color: int, visible: bool) -> None:
        """
        formatGeometricEdge(index, style, weight, color, visible). Returns None.
        """
        ...

    def getEdgeByIndex(self, edgeIndex: int) -> TopoShape:
        """
        getEdgeByIndex(edgeIndex). Returns Part.TopoShape.
        """
        ...

    def getEdgeBySelection(self, edgeName: str) -> TopoShape:
        """
        getEdgeBySelection(edgeName). Returns Part.TopoShape.
        """
        ...

    def getVertexByIndex(self, vertexIndex: int) -> TopoShape:
        """
        getVertexByIndex(vertexIndex). Returns Part.TopoShape.
        """
        ...

    def getVertexBySelection(self, vertexName: str) -> TopoShape:
        """
        getVertexBySelection(vertexName). Returns Part.TopoShape.
        """
        ...

    def projectPoint(self, point: Vector, invert: bool = False) -> Vector:
        """
        projectPoint(vector3d point, [bool invert]). Returns the projection of point in the
        projection coordinate system of this DrawViewPart. Optionally inverts the Y coordinate of the
        result.
        """
        ...

    def getGeometricCenter(self) -> Vector:
        """
        point3d = getGeometricCenter() - returns the geometric center of the source shapes.
        """
        ...

    def requestPaint(self) -> None:
        """
        requestPaint(). Redraw the graphic for this View.
        """
        ...