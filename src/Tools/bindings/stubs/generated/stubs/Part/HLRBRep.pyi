# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from typing import *

# src/Mod/Part/App/HLRBRep/HLRBRep_Algo.pyi:23
class Algo:
    """
    Algo() -> HLRBRep_Algo

    A framework to compute a shape as seen in a projection
    plane. This is done by calculating the visible and the hidden parts
    of the shape. HLRBRep_Algo works with three types of entity:

    - shapes to be visualized
    - edges in these shapes (these edges are the basic entities which will be
      visualized or hidden), and
    - faces in these shapes which hide the edges.

    HLRBRep_Algo is based on the principle of comparing each edge of the shape to
    be visualized with each of its faces, and calculating the visible and the
    hidden parts of each edge. For a given projection, HLRBRep_Algo calculates a
    set of lines characteristic of the object being represented. It is also used in
    conjunction with the HLRBRep_HLRToShape extraction utilities, which reconstruct
    a new, simplified shape from a selection of calculation results. This new shape
    is made up of edges, which represent the shape visualized in the
    projection. HLRBRep_Algo takes the shape itself into account whereas
    HLRBRep_PolyAlgo works with a polyhedral simplification of the shape. When you
    use HLRBRep_Algo, you obtain an exact result, whereas, when you use
    HLRBRep_PolyAlgo, you reduce computation time but obtain polygonal segments. In
    the case of complicated shapes, HLRBRep_Algo may be time-consuming. An
    HLRBRep_Algo object provides a framework for:

    - defining the point of view
    - identifying the shape or shapes to be visualized
    - calculating the outlines
    - calculating the visible and hidden lines of the shape. Warning
    - Superimposed lines are not eliminated by this algorithm.
    - There must be no unfinished objects inside the shape you wish to visualize.
    - Points are not treated.
    - Note that this is not the sort of algorithm used in generating shading, which
      calculates the visible and hidden parts of each face in a shape to be
      visualized by comparing each face in the shape with every other face in the
      same shape.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def add(self, S, nbIso: int=0, /) -> None:
        """
        add(S, nbIso=0)

        Adds the shape S to this framework, and specifies the number of isoparameters
        nbiso desired in visualizing S.  You may add as many shapes as you wish.  Use
        the function add once for each shape.
        """
        ...

    def remove(self, i: int, /) -> None:
        """
        remove(i)

        Remove the shape of index i from this framework.
        """
        ...

    def index(self, S, /) -> int:
        """
        index(S) ->  int

        Return the index of the Shape S and return 0 if the Shape S is not found.
        """
        ...

    def outLinedShapeNullify(self) -> None:
        """
        outlinedShapeNullify()

        Nullify all the results of OutLiner from HLRTopoBRep.
        """
        ...

    def setProjector(self, Origin: tuple[float, float, float]=(0, 0, 0), ZDir: tuple[float, float, float]=(0, 0, 0), XDir: tuple[float, float, float]=(0, 0, 0), focus: float=float('nan')) -> None:
        """
        setProjector(Origin=(0, 0, 0), ZDir=(0,0,0), XDir=(0,0,0), focus=NaN)

        Set the projector.  With focus left to NaN, an axonometric projector is
        created.  Otherwise, a perspective projector is created with focus focus.
        """
        ...

    def nbShapes(self) -> int:
        """
        nbShapes()

        Returns the number of shapes in the collection.  It does not modify the
        object's state and is used to retrieve the count of shapes.
        """
        ...

    def showAll(self, i: int=-1, /) -> None:
        """
        showAll(i=-1)

        If i < 1, then set all the edges to visible.
        Otherwise, set to visible all the edges of the shape of index i.
        """
        ...

    def hide(self, i: int=-1, j: int=-1, /) -> None:
        """
        hide(i=-1, j=-1)

        If i < 1, hide all of the datastructure.
        Otherwise, if j < 1, hide the shape of index i.
        Otherwise, hide the shape of index i by the shape of index j.
        """
        ...

    def hideAll(self, i: int=-1, /) -> None:
        """
        hideAll(i=-1)

        If i < 1, hide all the edges.
        Otherwise, hide all the edges of shape of index i.
        """
        ...

    def partialHide(self) -> None:
        """
        partialHide()

        Own hiding of all the shapes of the DataStructure without hiding by each other.
        """
        ...

    def select(self, i: int=-1, /) -> None:
        """
        select(i=-1)

        If i < 1, select all the DataStructure.
        Otherwise, only select the shape of index i.
        """
        ...

    def selectEdge(self, i: int, /) -> None:
        """
        selectEdge(i)

        Select only the edges of the shape of index i.
        """
        ...

    def selectFace(self, i: int, /) -> None:
        """
        selectFace(i)

        Select only the faces of the shape of index i.
        """
        ...

    def initEdgeStatus(self) -> None:
        """
        initEdgeStatus()

        Init the status of the selected edges depending of the back faces of a closed
        shell.
        """
        ...

    def update(self) -> None:
        """
        update()

        Update the DataStructure.
        """
        ...

# src/Mod/Part/App/HLRBRep/HLRBRep_PolyAlgo.pyi:25
class PolyAlgo:
    """
    PolyAlgo() -> HLRBRep_PolyAlgo

    A framework to compute the shape as seen in a projection
    plane. This is done by calculating the visible and the hidden parts of the
    shape. HLRBRep_PolyAlgo works with three types of entity:

    - shapes to be visualized (these shapes must have already been triangulated.)
    - edges in these shapes (these edges are defined as polygonal lines on the
      triangulation of the shape, and are the basic entities which will be visualized
      or hidden), and
    - triangles in these shapes which hide the edges.

    HLRBRep_PolyAlgo is based on the principle of comparing each edge of the shape
    to be visualized with each of the triangles produced by the triangulation of
    the shape, and calculating the visible and the hidden parts of each edge. For a
    given projection, HLRBRep_PolyAlgo calculates a set of lines characteristic of
    the object being represented. It is also used in conjunction with the
    HLRBRep_PolyHLRToShape extraction utilities, which reconstruct a new,
    simplified shape from a selection of calculation results. This new shape is
    made up of edges, which represent the shape visualized in the
    projection. HLRBRep_PolyAlgo works with a polyhedral simplification of the
    shape whereas HLRBRep_Algo takes the shape itself into account. When you use
    HLRBRep_Algo, you obtain an exact result, whereas, when you use
    HLRBRep_PolyAlgo, you reduce computation time but obtain polygonal segments. An
    HLRBRep_PolyAlgo object provides a framework for:

    - defining the point of view
    - identifying the shape or shapes to be visualized
    - calculating the outlines
    - calculating the visible and hidden lines of the shape. Warning
    - Superimposed lines are not eliminated by this algorithm.
    - There must be no unfinished objects inside the shape you wish to visualize.
    - Points are not treated.
    - Note that this is not the sort of algorithm used in generating shading, which
      calculates the visible and hidden parts of each face in a shape to be
      visualized by comparing each face in the shape with every other face in the
      same shape.
    """

    def load(self, S: TopoShape, /) -> None:
        """
        load(S)

        Loads the shape S into this framework. Warning S must have already been triangulated.
        """
        ...

    def remove(self, i: int, /) -> None:
        """
        remove(i)

        Remove the shape of index i from this framework.
        """
        ...

    def nbShapes(self) -> int:
        """
        nbShapes()

        Returns the number of shapes in the collection.  It does not modify the
        object's state and is used to retrieve the count of shapes.
        """
        ...

    def shape(self, i: int, /) -> TopoShape:
        """
        shape(i) -> TopoShape

        Return the shape of index i.
        """
        ...

    def index(self, S: TopoShape, /) -> int:
        """
        index(S) ->  int

        Return the index of the Shape S.
        """
        ...

    def setProjector(self, Origin: tuple[float, float, float]=(0.0, 0.0, 0.0), ZDir: tuple[float, float, float]=(0.0, 0.0, 0.0), XDir: tuple[float, float, float]=(0.0, 0.0, 0.0), focus: float=float('nan')) -> None:
        """
        setProjector(Origin=(0, 0, 0), ZDir=(0,0,0), XDir=(0,0,0), focus=NaN)

        Set the projector.  With focus left to NaN, an axonometric projector is
        created.  Otherwise, a perspective projector is created with focus focus.
        """
        ...

    def update(self) -> None:
        """
        update()

        Launches calculation of outlines of the shape visualized by this
        framework. Used after setting the point of view and defining the shape or
        shapes to be visualized.
        """
        ...

    def initHide(self) -> None:
        """
        initHide()
        """
        ...

    def moreHide(self) -> None:
        """
        moreHide()
        """
        ...

    def nextHide(self) -> None:
        """
        nextHide()
        """
        ...

    def initShow(self) -> None:
        """
        initShow()
        """
        ...

    def moreShow(self) -> None:
        """
        moreShow()
        """
        ...

    def nextShow(self) -> None:
        """
        nextShow()
        """
        ...

    def outLinedShape(self, S: TopoShape, /) -> TopoShape:
        """
        outLinedShape(S) -> TopoShape

        Make a shape with the internal outlines in each face of shape S.
        """
        ...
    TolAngular: float = ...
    TolCoef: float = ...

# src/Mod/Part/App/HLRBRep/HLRToShape.pyi:18
class HLRToShape:
    """
    HLRToShape(algo: HLRBRep_Algo) -> HLRBRep_HLRToShape

    A framework for filtering the computation results of an HLRBRep_Algo algorithm
    by extraction. From the results calculated by the algorithm on a shape, a
    filter returns the type of edge you want to identify. You can choose any of the
    following types of output:
    - visible sharp edges
    - hidden sharp edges
    - visible smooth edges
    - hidden smooth edges
    - visible sewn edges
    - hidden sewn edges
    - visible outline edges
    - hidden outline edges
    - visible isoparameters and
    - hidden isoparameters.

    Sharp edges present a C0 continuity (non G1). Smooth edges present a G1
    continuity (non G2). Sewn edges present a C2 continuity. The result is composed
    of 2D edges in the projection plane of the view which the algorithm has worked
    with. These 2D edges are not included in the data structure of the visualized
    shape. In order to obtain a complete image, you must combine the shapes given
    by each of the chosen filters. The construction of the shape does not call a
    new computation of the algorithm, but only reads its internal results. The
    methods of this shape are almost identic to those of the HLRBrep_PolyHLRToShape
    class.
    """

    def vCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        vCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible sharp edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def Rg1LineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        Rg1LineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible smooth edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def RgNLineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        RgNLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible sewn edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def outLineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        outLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible outline edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def outLineVCompound3d(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        outLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible outline edges in 3D for either shape
        Shape or for all added shapes (Shape=None).
        """
        ...

    def isoLineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        isoLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible isoparameters for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def hCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        hCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden sharp edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def Rg1LineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        Rg1LineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden smooth edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def RgNLineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        RgNLineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden sewn edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def outLineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        outLineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden outline edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def isoLineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        isoLineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden isoparameters for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def compoundOfEdges(self, Type: int, Visible: bool, In3D: bool, Shape: Optional[TopoShape]=None) -> TopoShape:
        """
        compoundOfEdges(Type: int, Visible: bool, In3D: bool, Shape=None) -> TopoShape

        Returns compound of resulting edges of required type and visibility, taking
        into account the kind of space (2d or 3d).  If Shape=None, return it for all
        added shapes, otherwise return it for shape Shape.
        """
        ...

# src/Mod/Part/App/HLRBRep/PolyHLRToShape.pyi:19
class PolyHLRToShape:
    """
    PolyHLRToShape(algo: HLRBRep_PolyAlgo) -> HLRBRep_PolyHLRToShape

    A framework for filtering the computation results of an HLRBRep_PolyAlgo
    algorithm by extraction.  From the results calculated by the algorithm on a
    shape, a filter returns the type of edge you want to identify.  You can choose
    any of the following types of output:
    - visible sharp edges
    - hidden sharp edges
    - visible smooth edges
    - hidden smooth edges
    - visible sewn edges
    - hidden sewn edges
    - visible outline edges
    - hidden outline edges
    - visible isoparameters and
    - hidden isoparameters.

    Sharp edges present a C0 continuity (non G1). Smooth edges present a G1
    continuity (non G2). Sewn edges present a C2 continuity. The result is composed
    of 2D edges in the projection plane of the view which the algorithm has worked
    with. These 2D edges are not included in the data structure of the visualized
    shape. In order to obtain a complete image, you must combine the shapes given
    by each of the chosen filters. The construction of the shape does not call a
    new computation of the algorithm, but only reads its internal results.
    """

    def update(self, algo: PolyAlgo, /) -> None:
        """
        update(algo: HLRBRep_PolyAlgo)
        """
        ...

    def show(self) -> None:
        """
        show()
        """
        ...

    def hide(self) -> None:
        """
        hide()
        """
        ...

    def vCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        vCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible sharp edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def Rg1LineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        Rg1LineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible smooth edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def RgNLineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        RgNLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible sewn edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def outLineVCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        outLineVCompound(Shape=None) -> TopoShape

        Sets the extraction filter for visible outline edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def hCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        hCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden sharp edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def Rg1LineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        Rg1LineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden smooth edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...

    def RgNLineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        RgNLineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden sewn edges for either shape Shape or for
        all added shapes (Shape=None).
        """
        ...

    def outLineHCompound(self, Shape: Optional[TopoShape]=None, /) -> TopoShape:
        """
        outLineHCompound(Shape=None) -> TopoShape

        Sets the extraction filter for hidden outline edges for either shape Shape or
        for all added shapes (Shape=None).
        """
        ...
