# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def edgeWalker(*args: Any) -> Any: ...
def findOuterWire(*args: Any) -> Any: ...
def findShapeOutline(*args: Any) -> Any: ...
def viewPartAsDxf(*args: Any) -> Any: ...
def viewPartAsSvg(*args: Any) -> Any: ...
def writeDXFView(*args: Any) -> Any: ...
def writeDXFPage(*args: Any) -> Any: ...
def findCentroid(*args: Any) -> Any: ...
def makeExtentDim(*args: Any) -> Any: ...
def makeDistanceDim(*args: Any) -> Any: ...
def makeDistanceDim3d(*args: Any) -> Any: ...
def makeGeomHatch(*args: Any) -> Any: ...
def project(*args: Any) -> Any: ...
def projectEx(*args: Any) -> Any: ...
def projectToSVG(*args: Any, **kwargs: Any) -> Any: ...
def projectToDXF(*args: Any) -> Any: ...
def removeSvgTags(*args: Any) -> Any: ...
def exportSVGEdges(*args: Any) -> Any: ...
def build3dCurves(*args: Any) -> Any: ...
def makeCanonicalPoint(*args: Any) -> Any: ...
def makeLeader(*args: Any) -> Any: ...
def nearestFraction(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCAD import DocumentObjectExtension
from FreeCAD import DocumentObject

from typing import *

# src/Mod/TechDraw/App/CenterLine.pyi:17
class CenterLine:
    """
    CenterLine specifies additional mark up edges in a View

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def clone(self) -> Any:
        """Create a clone of this centerline"""
        ...

    def copy(self) -> Any:
        """Create a copy of this centerline"""
        ...
    Tag: Final[str]
    'Gives the tag of the CenterLine as string.'
    Type: Final[int]
    '0 - face, 1 - 2 line, 2 - 2 point.'
    Mode: int
    '0 - vert/ 1 - horiz/ 2 - aligned.'
    Format: dict[str, Any]
    'The appearance attributes (style, color, weight, visible) for this CenterLine.'
    HorizShift: float
    'The left/right offset for this CenterLine.'
    VertShift: float
    'The up/down offset for this CenterLine.'
    Rotation: float
    'The rotation of the Centerline in degrees.'
    Extension: float
    'The additional length to be added to this CenterLine.'
    Flip: bool
    'Reverse the order of points for 2 point CenterLine.'
    Edges: list[Any]
    'The names of source edges for this CenterLine.'
    Faces: list[Any]
    'The names of source Faces for this CenterLine.'
    Points: list[Any]
    'The names of source Points for this CenterLine.'

# src/Mod/TechDraw/App/CosmeticEdge.pyi:21
class CosmeticEdge:
    """
    CosmeticEdge specifies an extra (cosmetic) edge in Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """
    Tag: Final[str]
    'Gives the tag of the CosmeticEdge as string.'
    Start: PyCXXVector
    'Gives the position of one end of this CosmeticEdge as vector.'
    End: PyCXXVector
    'Gives the position of one end of this CosmeticEdge as vector.'
    Center: PyCXXVector
    'Gives the position of center point of this CosmeticEdge as vector.'
    Radius: float
    'Gives the radius of CosmeticEdge in mm.'
    Format: dict
    'The appearance attributes (style, weight, color, visible) for this CosmeticEdge.'

# src/Mod/TechDraw/App/CosmeticExtension.pyi:14
class CosmeticExtension(DocumentObjectExtension):
    """
    This object represents cosmetic features for a DrawViewPart.

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/CosmeticVertex.pyi:17
class CosmeticVertex:
    """
    CosmeticVertex specifies an extra (cosmetic) vertex in Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def clone(self) -> Any:
        """Create a clone of this CosmeticVertex"""
        ...

    def copy(self) -> Any:
        """Create a copy of this CosmeticVertex"""
        ...
    Tag: Final[str]
    'Gives the tag of the CosmeticVertex as string.'
    Point: Any
    'Gives the position of this CosmeticVertex as vector.'
    Show: bool
    'Show/hide the vertex.'
    Color: Any
    "set/return the vertex's colour using a tuple (rgba)."
    Size: Any
    "set/return the vertex's radius in mm."
    Style: Any
    "set/return the vertex's style as integer."

# src/Mod/TechDraw/App/DrawBrokenView.pyi:16
class DrawBrokenView(DrawViewPart):
    """
    Feature for creating and manipulating Technical Drawing broken views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def mapPoint3dToView(self) -> Any:
        """point2d = mapPoint3dToView(point3d) - returns the position of the 3d point within the broken view."""
        ...

    def mapPoint2dFromView(self) -> Any:
        """point2d = mapPoint2dFromView(point3d) - returns the position of the 2d point within an unbroken view."""
        ...

    def getCompressedCenter(self) -> Any:
        """point3d = getCompressedCenter() - returns the geometric center of the source shapes after break cuts and gap compression."""
        ...

# src/Mod/TechDraw/App/DrawGeomHatch.pyi:15
class DrawGeomHatch(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing GeomHatch areas

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def translateLabel(self) -> Any:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

# src/Mod/TechDraw/App/DrawHatch.pyi:14
class DrawHatch(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Hatch areas

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def translateLabel(self) -> Any:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

# src/Mod/TechDraw/App/DrawLeaderLine.pyi:14
class DrawLeaderLine(DrawView):
    """
    Feature for adding leaders to Technical Drawings

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawPage.pyi:15
class DrawPage(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Pages

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def addView(self) -> Any:
        """addView(DrawView) - Add a View to this Page"""
        ...

    def removeView(self) -> Any:
        """removeView(DrawView) - Remove a View to this Page"""
        ...

    def getViews(self) -> Any:
        """getViews() - returns a list of all the views on page excluding Views inside Collections"""
        ...

    def getAllViews(self) -> Any:
        """getAllViews() - returns a list of all the views on page including Views inside Collections"""
        ...

    def translateLabel(self) -> Any:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

    def requestPaint(self) -> Any:
        """Ask the Gui to redraw this page"""
        ...
    PageWidth: Final[float]
    'Returns the width of this page'
    PageHeight: Final[float]
    'Returns the height of this page'
    PageOrientation: Final[str]
    'Returns the orientation of this page'

# src/Mod/TechDraw/App/DrawParametricTemplate.pyi:16
class DrawParametricTemplate(DrawTemplate):
    """
    Feature for creating and manipulating Technical Drawing Templates

    Author: Luke Parry (l.parry@warwick.ac.uk)
    License: LGPL-2.1-or-later
    """

    def drawLine(self) -> Any:
        """Draw a line"""
        ...
    GeometryCount: Final[int]
    'Number of geometry in template'

# src/Mod/TechDraw/App/DrawProjGroup.pyi:16
class DrawProjGroup(DrawViewCollection):
    """
    Feature for creating and manipulating Technical Drawing Projection Groups

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def addProjection(self) -> Any:
        """addProjection(string projectionType) - Add a new Projection Item to this Group. Returns DocObj."""
        ...

    def removeProjection(self) -> Any:
        """removeProjection(string projectionType) - Remove specified Projection Item from this Group. Returns int number of views in Group."""
        ...

    def purgeProjections(self) -> Any:
        """purgeProjections() - Remove all Projection Items from this Group. Returns int number of views in Group (0)."""
        ...

    def getItemByLabel(self) -> Any:
        """getItemByLabel(string projectionType) - return specified Projection Item"""
        ...

    def getXYPosition(self) -> Any:
        """getXYPosition(string projectionType) - return the AutoDistribute position for specified Projection Item"""
        ...

# src/Mod/TechDraw/App/DrawProjGroupItem.pyi:16
class DrawProjGroupItem(DrawViewPart):
    """
    Feature for creating and manipulating component Views Technical Drawing Projection Groups

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def autoPosition(self) -> Any:
        """autoPosition() - Move to AutoDistribute/Unlocked position on Page. Returns none."""
        ...

# src/Mod/TechDraw/App/DrawRichAnno.pyi:14
class DrawRichAnno(DrawView):
    """
    Feature for adding rich annotation blocks to Technical Drawings

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawSVGTemplate.pyi:16
class DrawSVGTemplate(DrawTemplate):
    """
    Feature for creating and manipulating Technical Drawing SVG Templates

    Author: Luke Parry (l.parry@warwick.ac.uk)
    License: LGPL-2.1-or-later
    """

    def getEditFieldContent(self) -> Any:
        """getEditFieldContent(EditFieldName) - returns the content of a specific Editable Text Field"""
        ...

    def setEditFieldContent(self) -> Any:
        """setEditFieldContent(EditFieldName, NewContent) - sets a specific Editable Text Field to a new value"""
        ...

    def translateLabel(self) -> Any:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

# src/Mod/TechDraw/App/DrawTemplate.pyi:14
class DrawTemplate(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Templates

    Author: Luke Parry (l.parry@warwick.ac.uk)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawTile.pyi:14
class DrawTile(DocumentObject):
    """
    Feature for adding tiles to leader lines

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawTileWeld.pyi:14
class DrawTileWeld(DrawTile):
    """
    Feature for adding welding tiles to leader lines

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawView.pyi:16
class DrawView(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def translateLabel(self) -> Any:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
        No return value.  Replace the current label with a translated version where possible.
        """
        ...

    def getScale(self) -> Any:
        """
        float scale = getScale().  Returns the correct scale for this view.  Handles whether to
        use this view's scale property or a parent's view (as in a projection group).
        """
        ...

    def findParentPage(self) -> Any:
        """
        DrawPage parent = findParentPage().  Returns the parent page that contains this view.
        """
        ...

# src/Mod/TechDraw/App/DrawViewAnnotation.pyi:14
class DrawViewAnnotation(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Annotation Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/DrawViewClip.pyi:16
class DrawViewClip(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Clip Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def addView(self) -> Any:
        """addView(DrawView) - Add a View to this ClipView"""
        ...

    def removeView(self) -> Any:
        """removeView(DrawView) - Remove specified View to this ClipView"""
        ...

    def getChildViewNames(self) -> Any:
        """getChildViewNames() - get a list of the DrawViews in this ClipView"""
        ...

# src/Mod/TechDraw/App/DrawViewCollection.pyi:16
class DrawViewCollection(DrawView):
    """
    Feature for creating and manipulating Technical Drawing View Collections

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def addView(self) -> Any:
        """addView(DrawView object) - Add a new View to this Group. Returns count of views."""
        ...

    def removeView(self) -> Any:
        """removeView(DrawView object) - Remove specified Viewfrom this Group. Returns count of views in Group."""
        ...

# src/Mod/TechDraw/App/DrawViewDimExtent.pyi:16
class DrawViewDimExtent(DrawViewDimension):
    """
    Feature for creating and manipulating Technical Drawing DimExtents

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def tbd(self) -> Any:
        """tbd() - returns tbd."""
        ...

# src/Mod/TechDraw/App/DrawViewDimension.pyi:16
class DrawViewDimension(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Dimensions

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def getRawValue(self) -> Any:
        """getRawValue() - returns Dimension value in mm."""
        ...

    def getText(self) -> Any:
        """getText() - returns Dimension text."""
        ...

    def getLinearPoints(self) -> Any:
        """getLinearPoints() - returns list of points for linear Dimension"""
        ...

    def getArcPoints(self) -> Any:
        """getArcPoints() - returns list of points for circle/arc Dimension"""
        ...

    def getAnglePoints(self) -> Any:
        """getAnglePoints() - returns list of points for angle Dimension"""
        ...

    def getAreaPoints(self) -> Any:
        """getAreaPoints() - returns list of values (center, filled area, actual area) for area Dimension."""
        ...

    def getArrowPositions(self) -> Any:
        """getArrowPositions() - returns list of locations or Dimension Arrowheads. Locations are in unscaled coordinates of parent View"""
        ...

# src/Mod/TechDraw/App/DrawViewPart.pyi:16
class DrawViewPart(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Part Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def getVisibleEdges(self) -> Any:
        """
        getVisibleEdges([conventionalCoords]) - get the visible edges in the View as Part::TopoShapeEdges. Edges are returned
        in conventional coordinates if conventionalCoords is True.  The default is to return Qt inverted Y coordinates.
        """
        ...

    def getVisibleVertexes(self) -> Any:
        """
        getVisibleVertexes() - get the visible vertexes as App.Vector in the View's coordinate system.  App.Vectors are returned
        in conventional coordinates if conventionalCoords is True.  The default is to return Qt inverted Y coordinates.
        """
        ...

    def getHiddenEdges(self) -> Any:
        """
        getHiddenEdges([conventionalCoords]) - get the hidden edges in the View as Part::TopoShapeEdges.  Edges are returned
        in conventional coordinates if conventionalCoords is True.  The default is to return Qt inverted Y coordinates.
        """
        ...

    def getHiddenVertexes(self) -> Any:
        """
        getHiddenVertexes() - get the hidden vertexes as App.Vector in the View's coordinate system.  App.Vectors are returned
        in conventional coordinates if conventionalCoords is True.  The default is to return Qt inverted Y coordinates.
        """
        ...

    def makeCosmeticVertex(self) -> Any:
        """id = makeCosmeticVertex(p1) - add a CosmeticVertex at p1 (View coordinates). Returns unique id vertex."""
        ...

    def makeCosmeticVertex3d(self) -> Any:
        """id = makeCosmeticVertex3d(p1) - add a CosmeticVertex at p1 (3d model coordinates). Returns unique id vertex."""
        ...

    def getCosmeticVertex(self) -> Any:
        """cv = getCosmeticVertex(id) - returns CosmeticVertex with unique id."""
        ...

    def getCosmeticVertexBySelection(self) -> Any:
        """cv = getCosmeticVertexBySelection(name) - returns CosmeticVertex with name (Vertex6).  Used in selections."""
        ...

    def removeCosmeticVertex(self) -> Any:
        """removeCosmeticVertex(cv) - remove CosmeticVertex from View. Returns None."""
        ...

    def clearCosmeticVertices(self) -> Any:
        """clearCosmeticVertices() - remove all CosmeticVertices from the View. Returns None."""
        ...

    def makeCosmeticLine(self) -> Any:
        """tag = makeCosmeticLine(p1, p2) - add a CosmeticEdge from p1 to p2(View coordinates). Returns tag of new CosmeticEdge."""
        ...

    def makeCosmeticLine3D(self) -> Any:
        """tag = makeCosmeticLine3D(p1, p2) - add a CosmeticEdge from p1 to p2(3D coordinates). Returns tag of new CosmeticEdge."""
        ...

    def makeCosmeticCircle(self) -> Any:
        """tag = makeCosmeticCircle(center, radius) - add a CosmeticEdge at center with radius radius(View coordinates). Returns tag of new CosmeticEdge."""
        ...

    def makeCosmeticCircleArc(self) -> Any:
        """tag = makeCosmeticCircleArc(center, radius, start, end) - add a CosmeticEdge at center with radius radius(View coordinates) from start angle to end angle. Returns tag of new CosmeticEdge."""
        ...

    def makeCosmeticCircle3d(self) -> Any:
        """tag = makeCosmeticCircle3d(center, radius) - add a CosmeticEdge at center (3d point) with radius. Returns tag of new CosmeticEdge."""
        ...

    def makeCosmeticCircleArc3d(self) -> Any:
        """tag = makeCosmeticCircleArc3d(center, radius, start, end) - add a CosmeticEdge at center (3d point) with radius from start angle to end angle. Returns tag of new CosmeticEdge."""
        ...

    def getCosmeticEdge(self) -> Any:
        """ce = getCosmeticEdge(id) - returns CosmeticEdge with unique id."""
        ...

    def getCosmeticEdgeBySelection(self) -> Any:
        """ce = getCosmeticEdgeBySelection(name) - returns CosmeticEdge by name (Edge25).  Used in selections"""
        ...

    def removeCosmeticEdge(self) -> Any:
        """removeCosmeticEdge(ce) - remove CosmeticEdge ce from View. Returns None."""
        ...

    def makeCenterLine(self) -> Any:
        """makeCenterLine(subNames, mode) - draw a center line on this viewPart. SubNames is a list of n Faces, 2 Edges or 2 Vertices (ex [Face1,Face2,Face3]. Returns unique tag of added CenterLine."""
        ...

    def getCenterLine(self) -> Any:
        """cl = getCenterLine(id) - returns CenterLine with unique id."""
        ...

    def getCenterLineBySelection(self) -> Any:
        """cl = getCenterLineBySelection(name) - returns CenterLine by name (Edge25).  Used in selections"""
        ...

    def removeCenterLine(self) -> Any:
        """removeCenterLine(cl) - remove CenterLine cl from View. Returns None."""
        ...

    def clearCosmeticEdges(self) -> Any:
        """clearCosmeticEdges() - remove all CosmeticLines from the View. Returns None."""
        ...

    def clearCenterLines(self) -> Any:
        """clearCenterLines() - remove all CenterLines from the View. Returns None."""
        ...

    def clearGeomFormats(self) -> Any:
        """clearGeomFormats() - remove all GeomFormats from the View. Returns None."""
        ...

    def formatGeometricEdge(self) -> Any:
        """formatGeometricEdge(index, style, weight, color, visible). Returns None."""
        ...

    def getEdgeByIndex(self) -> Any:
        """getEdgeByIndex(edgeIndex). Returns Part.TopoShape."""
        ...

    def getEdgeBySelection(self) -> Any:
        """getEdgeBySelection(edgeName). Returns Part.TopoShape."""
        ...

    def getVertexByIndex(self) -> Any:
        """getVertexByIndex(vertexIndex). Returns Part.TopoShape."""
        ...

    def getVertexBySelection(self) -> Any:
        """getVertexBySelection(vertexName). Returns Part.TopoShape."""
        ...

    def projectPoint(self) -> Any:
        """
        projectPoint(vector3d point, [bool invert]). Returns the projection of point in the
        projection coordinate system of this DrawViewPart. Optionally inverts the Y coordinate of the
        result.
        """
        ...

    def getGeometricCenter(self) -> Any:
        """point3d = getGeometricCenter() - returns the geometric center of the source shapes."""
        ...

    def requestPaint(self) -> Any:
        """requestPaint(). Redraw the graphic for this View."""
        ...

# src/Mod/TechDraw/App/DrawViewSymbol.pyi:16
class DrawViewSymbol(DrawView):
    """
    Feature for creating and manipulating Drawing SVG Symbol Views

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def dumpSymbol(self) -> Any:
        """dumpSymbol(fileSpec) - dump the contents of Symbol to a file"""
        ...

# src/Mod/TechDraw/App/DrawWeldSymbol.pyi:14
class DrawWeldSymbol(DrawView):
    """
    Feature for adding welding tiles to leader lines

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

# src/Mod/TechDraw/App/GeomFormat.pyi:17
class GeomFormat:
    """
    GeomFormat specifies appearance parameters for TechDraw Geometry objects

    Author: WandererFan (wandererfan@gmail.com)
    License: LGPL-2.1-or-later
    """

    def clone(self) -> Any:
        """Create a clone of this geomformat"""
        ...

    def copy(self) -> Any:
        """Create a copy of this geomformat"""
        ...
    Tag: Final[str]
    'Gives the tag of the GeomFormat as string.'
