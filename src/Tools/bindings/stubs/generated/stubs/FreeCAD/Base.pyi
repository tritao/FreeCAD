# Generated public type stubs from PyCXX binding method tables.

from __future__ import annotations
from typing import Any
from typing import Sequence, overload

class ProgressIndicator:

    def start(self, *args: Any) -> Any:
        ...

    def next(self, *args: Any) -> Any:
        ...

    def stop(self, *args: Any) -> Any:
        ...
import FreeCAD
from enum import IntEnum
from typing import *

class Axis:
    """
    Base.Axis class.

    An Axis defines a direction and a position (base) in 3D space.

    The following constructors are supported:

    Axis()
    Empty constructor.

    Axis(axis)
    Copy constructor.
    axis : Base.Axis

    Axis(base, direction)
    Define from a position and a direction.
    base : Base.Vector
    direction : Base.Vector
    """
    Base: Vector = ...
    'Base position vector of the Axis.'
    Direction: Vector = ...
    'Direction vector of the Axis.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, axis: Axis) -> None:
        ...

    @overload
    def __init__(self, base: Vector, direction: Vector) -> None:
        ...

    def copy(self) -> Axis:
        """
        Returns a copy of this Axis.
        """
        ...

    def move(self, vector: Vector, /) -> None:
        """
        Move the axis base along the given vector.

        vector : Base.Vector
            Vector by which to move the axis.
        """
        ...

    def multiply(self, placement: Placement, /) -> Axis:
        """
        Multiply this axis by a placement.

        placement : Base.Placement
            Placement by which to multiply the axis.
        """
        ...

    def reversed(self) -> Axis:
        """
        Compute the reversed axis. This returns a new Base.Axis with
        the original direction reversed.
        """
        ...

class BaseClass:
    """
    This is the base class

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    TypeId: Final[str] = ''
    'Is the type of the FreeCAD object with module domain'
    Module: Final[str] = ''
    'Module in which this class is defined'

    def isDerivedFrom(self, typeName: str, /) -> bool:
        """
        Returns true if given type is a father
        """
        ...

    def getAllDerivedFrom(self) -> List[object]:
        """
        Returns all descendants
        """
        ...

class BoundBox:
    """
    Base.BoundBox class.

    This class represents a bounding box.
    A bounding box is a rectangular cuboid which is a way to describe outer
    boundaries and is obtained from a lot of 3D types.
    It is often used to check if a 3D entity lies in the range of another object.
    Checking for bounding interference first can save a lot of computing time!
    An invalid BoundBox is represented by inconsistent values at each direction:
    The maximum float value of the system at the minimum coordinates, and the
    opposite value at the maximum coordinates.

    The following constructors are supported:

    BoundBox()
    Empty constructor. Returns an invalid BoundBox.

    BoundBox(boundBox)
    Copy constructor.
    boundBox : Base.BoundBox

    BoundBox(xMin, yMin=0, zMin=0, xMax=0, yMax=0, zMax=0)
    Define from the minimum and maximum values at each direction.
    xMin : float
        Minimum value at x-coordinate.
    yMin : float
        Minimum value at y-coordinate.
    zMin : float
        Minimum value at z-coordinate.
    xMax : float
        Maximum value at x-coordinate.
    yMax : float
        Maximum value at y-coordinate.
    zMax : float
        Maximum value at z-coordinate.

    App.BoundBox(min, max)
    Define from two containers representing the minimum and maximum values of the
    coordinates in each direction.
    min : Base.Vector, tuple
        Minimum values of the coordinates.
    max : Base.Vector, tuple
        Maximum values of the coordinates.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Center: Final[Any] = ...
    'Center point of the bounding box.'
    XMax: float = 0.0
    'The maximum x boundary position.'
    YMax: float = 0.0
    'The maximum y boundary position.'
    ZMax: float = 0.0
    'The maximum z boundary position.'
    XMin: float = 0.0
    'The minimum x boundary position.'
    YMin: float = 0.0
    'The minimum y boundary position.'
    ZMin: float = 0.0
    'The minimum z boundary position.'
    XLength: Final[float] = 0.0
    'Length of the bounding box in x direction.'
    YLength: Final[float] = 0.0
    'Length of the bounding box in y direction.'
    ZLength: Final[float] = 0.0
    'Length of the bounding box in z direction.'
    DiagonalLength: Final[float] = 0.0
    'Diagonal length of the bounding box.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, boundBox: 'BoundBox') -> None:
        ...

    @overload
    def __init__(self, xMin: float, yMin: float=0, zMin: float=0, xMax: float=0, yMax: float=0, zMax: float=0) -> None:
        ...

    @overload
    def __init__(self, min: Union[Vector, Tuple[float, float, float]], max: Union[Vector, Tuple[float, float, float]]) -> None:
        ...

    def setVoid(self) -> None:
        """
        Invalidate the bounding box.
        """
        ...

    def isValid(self) -> bool:
        """
        Checks if the bounding box is valid.
        """
        ...

    @overload
    def add(self, minMax: Vector, /) -> None:
        ...

    @overload
    def add(self, minMax: Tuple[float, float, float], /) -> None:
        ...

    @overload
    def add(self, x: float, y: float, z: float, /) -> None:
        ...

    def add(self, *args: Any, **kwargs: Any) -> None:
        """
        Increase the maximum values or decrease the minimum values of this BoundBox by
        replacing the current values with the given values, so the bounding box can grow
        but not shrink.

        minMax : Base.Vector, tuple
            Values to enlarge at each direction.
        x : float
            Value to enlarge at x-direction.
        y : float
            Value to enlarge at y-direction.
        z : float
            Value to enlarge at z-direction.
        """
        ...

    def getPoint(self, index: int, /) -> Vector:
        """
        Get the point of the given index.
        The index must be in the range of [0, 7].

        index : int
        """
        ...

    def getEdge(self, index: int, /) -> Tuple[Vector, ...]:
        """
        Get the edge points of the given index.
        The index must be in the range of [0, 11].

        index : int
        """
        ...

    @overload
    def closestPoint(self, point: Vector, /) -> Vector:
        ...

    @overload
    def closestPoint(self, x: float, y: float, z: float, /) -> Vector:
        ...

    def closestPoint(self, *args: Any, **kwargs: Any) -> Vector:
        """
        Get the closest point of the bounding box to the given point.

        point : Base.Vector, tuple
            Coordinates of the given point.
        x : float
            X-coordinate of the given point.
        y : float
            Y-coordinate of the given point.
        z : float
            Z-coordinate of the given point.
        """
        ...

    @overload
    def intersect(self, boundBox2: 'BoundBox', /) -> bool:
        ...

    @overload
    def intersect(self, base: Union[Vector, Tuple[float, float, float]], dir: Union[Vector, Tuple[float, float, float]], /) -> bool:
        ...

    def intersect(self, *args: Any) -> bool:
        """
        Checks if the given object intersects with this bounding box. That can be
        another bounding box or a line specified by base and direction.

        boundBox2 : Base.BoundBox
        base : Base.Vector, tuple
        dir : Base.Vector, tuple
        """
        ...

    def intersected(self, boundBox2: 'BoundBox', /) -> 'BoundBox':
        """
        Returns the intersection of this and the given bounding box.

        boundBox2 : Base.BoundBox
        """
        ...

    def united(self, boundBox2: 'BoundBox', /) -> 'BoundBox':
        """
        Returns the union of this and the given bounding box.

        boundBox2 : Base.BoundBox
        """
        ...

    def enlarge(self, variation: float, /) -> None:
        """
        Decrease the minimum values and increase the maximum values by the given value.
        A negative value shrinks the bounding box.

        variation : float
        """
        ...

    def getIntersectionPoint(self, base: Vector, dir: Vector, epsilon: float=0.0001, /) -> Vector:
        """
        Calculate the intersection point of a line with the bounding box.
        The base point must lie inside the bounding box, if not an exception is thrown.

        base : Base.Vector
            Base point of the line.
        dir : Base.Vector
            Direction of the line.
        epsilon : float
            Bounding box size tolerance.
        """
        ...

    @overload
    def move(self, displacement: Vector, /) -> None:
        ...

    @overload
    def move(self, displacement: Tuple[float, float, float], /) -> None:
        ...

    @overload
    def move(self, x: float, y: float, z: float, /) -> None:
        ...

    def move(self, *args: Any, **kwargs: Any) -> None:
        """
        Move the bounding box by the given values.

        displacement : Base.Vector, tuple
            Displacement at each direction.
        x : float
            Displacement at x-direction.
        y : float
            Displacement at y-direction.
        z : float
            Displacement at z-direction.
        """
        ...

    @overload
    def scale(self, factor: Vector, /) -> None:
        ...

    @overload
    def scale(self, factor: Tuple[float, float, float], /) -> None:
        ...

    @overload
    def scale(self, x: float, y: float, z: float, /) -> None:
        ...

    def scale(self, *args: Any, **kwargs: Any) -> None:
        """
        Scale the bounding box by the given values.

        factor : Base.Vector, tuple
            Factor scale at each direction.
        x : float
            Scale at x-direction.
        y : float
            Scale at y-direction.
        z : float
            Scale at z-direction.
        """
        ...

    def transformed(self, matrix: Matrix, /) -> 'BoundBox':
        """
        Returns a new BoundBox containing the transformed rectangular cuboid
        represented by this BoundBox.

        matrix : Base.Matrix
            Transformation matrix.
        """
        ...

    def isCutPlane(self, base: Vector, normal: Vector, /) -> bool:
        """
        Check if the plane specified by base and normal intersects (cuts) this bounding
        box.

        base : Base.Vector
        normal : Base.Vector
        """
        ...

    @overload
    def isInside(self, object: Vector, /) -> bool:
        ...

    @overload
    def isInside(self, object: 'BoundBox', /) -> bool:
        ...

    @overload
    def isInside(self, x: float, y: float, z: float, /) -> bool:
        ...

    def isInside(self, *args: Any) -> bool:
        """
        Check if a point or a bounding box is inside this bounding box.

        object : Base.Vector, Base.BoundBox
            Object to check if it is inside this bounding box.
        x : float
            X-coordinate of the point to check.
        y : float
            Y-coordinate of the point to check.
        z : float
            Z-coordinate of the point to check.
        """
        ...

class CoordinateSystem:
    """
    Base.CoordinateSystem class.

    An orthonormal right-handed coordinate system in 3D space.

    CoordinateSystem()
    Empty constructor.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Axis: 'FreeCAD.Base.Axis' = ...
    'Set or get axis.'
    XDirection: Vector = ...
    'Set or get X-direction.'
    YDirection: Vector = ...
    'Set or get Y-direction.'
    ZDirection: Vector = ...
    'Set or get Z-direction.'
    Position: Vector = ...
    'Set or get position.'

    def setAxes(self, axis: 'Union[FreeCAD.Base.Axis, Vector]', xDir: Vector, /) -> None:
        """
        Set axis or Z-direction, and X-direction.
        The X-direction is determined from the orthonormal compononent of `xDir`
        with respect to `axis` direction.

        axis : Base.Axis, Base.Vector
        xDir : Base.Vector
        """
        ...

    def displacement(self, coordSystem2: 'CoordinateSystem', /) -> Placement:
        """
        Computes the placement from this to the passed coordinate system `coordSystem2`.

        coordSystem2 : Base.CoordinateSystem
        """
        ...

    def transformTo(self, vector: Vector, /) -> Vector:
        """
        Computes the coordinates of the point in coordinates of this coordinate system.

        vector : Base.Vector
        """
        ...

    def transform(self, trans: Union[Rotation, Placement], /) -> None:
        """
        Applies a transformation on this coordinate system.

        trans : Base.Rotation, Base.Placement
        """
        ...

    def setPlacement(self, placement: Placement, /) -> None:
        """
        Set placement to the coordinate system.

        placement : Base.Placement
        """
        ...

class ScaleType(IntEnum):
    Other = -1
    NoScaling = 0
    NonUniformRight = 1
    NonUniformLeft = 2
    Uniform = 3

class Matrix:
    """
    Base.Matrix class.

    A 4x4 Matrix.
    In particular, this matrix can represent an affine transformation, that is,
    given a 3D vector `x`, apply the transformation y = M*x + b, where the matrix
    `M` is a linear map and the vector `b` is a translation.
    `y` can be obtained using a linear transformation represented by the 4x4 matrix
    `A` conformed by the augmented 3x4 matrix (M|b), augmented by row with
    (0,0,0,1), therefore: (y, 1) = A*(x, 1).

    The following constructors are supported:

    Matrix()
    Empty constructor.

    Matrix(matrix)
    Copy constructor.
    matrix : Base.Matrix.

    Matrix(*coef)
    Define from 16 coefficients of the 4x4 matrix.
    coef : sequence of float
        The sequence can have up to 16 elements which complete the matrix by rows.

    Matrix(vector1, vector2, vector3, vector4)
    Define from four 3D vectors which represent the columns of the 3x4 submatrix,
    useful to represent an affine transformation. The fourth row is made up by
    (0,0,0,1).
    vector1 : Base.Vector
    vector2 : Base.Vector
    vector3 : Base.Vector
    vector4 : Base.Vector
        Default to (0,0,0). Optional.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    A11: float = 0.0
    'The (1,1) matrix element.'
    A12: float = 0.0
    'The (1,2) matrix element.'
    A13: float = 0.0
    'The (1,3) matrix element.'
    A14: float = 0.0
    'The (1,4) matrix element.'
    A21: float = 0.0
    'The (2,1) matrix element.'
    A22: float = 0.0
    'The (2,2) matrix element.'
    A23: float = 0.0
    'The (2,3) matrix element.'
    A24: float = 0.0
    'The (2,4) matrix element.'
    A31: float = 0.0
    'The (3,1) matrix element.'
    A32: float = 0.0
    'The (3,2) matrix element.'
    A33: float = 0.0
    'The (3,3) matrix element.'
    A34: float = 0.0
    'The (3,4) matrix element.'
    A41: float = 0.0
    'The (4,1) matrix element.'
    A42: float = 0.0
    'The (4,2) matrix element.'
    A43: float = 0.0
    'The (4,3) matrix element.'
    A44: float = 0.0
    'The (4,4) matrix element.'
    A: Sequence[float] = []
    'The matrix elements.'

    @overload
    def move(self, vector: Vector, /) -> None:
        ...

    @overload
    def move(self, x: float, y: float, z: float, /) -> None:
        ...

    def move(self, *args) -> None:
        """
        Move the matrix along a vector, equivalent to left multiply the matrix
        by a pure translation transformation.

        vector : Base.Vector, tuple
        x : float
            `x` translation.
        y : float
            `y` translation.
        z : float
            `z` translation.
        """
        ...

    @overload
    def scale(self, vector: Vector, /) -> None:
        ...

    @overload
    def scale(self, x: float, y: float, z: float, /) -> None:
        ...

    @overload
    def scale(self, factor: float, /) -> None:
        ...

    def scale(self, *args) -> None:
        """
        Scale the first three rows of the matrix.

        vector : Base.Vector
        x : float
            First row factor scale.
        y : float
            Second row factor scale.
        z : float
            Third row factor scale.
        factor : float
            global factor scale.
        """
        ...

    def hasScale(self, tol: float=0, /) -> ScaleType:
        """
        Return an enum value of ScaleType. Possible values are:
        Uniform, NonUniformLeft, NonUniformRight, NoScaling or Other
        if it's not a scale matrix.

        tol : float
        """
        ...

    def decompose(self) -> Tuple['Matrix', 'Matrix', 'Matrix', 'Matrix']:
        """
        Return a tuple of matrices representing shear, scale, rotation and move.
        So that matrix = move * rotation * scale * shear.
        """
        ...

    def nullify(self) -> None:
        """
        Make this the null matrix.
        """
        ...

    def isNull(self) -> bool:
        """
        Check if this is the null matrix.
        """
        ...

    def unity(self) -> None:
        """
        Make this matrix to unity (4D identity matrix).
        """
        ...

    def isUnity(self, tol: float=0.0, /) -> bool:
        """
        Check if this is the unit matrix (4D identity matrix).
        """
        ...

    def transform(self, vector: Vector, matrix2: 'Matrix', /) -> None:
        """
        Transform the matrix around a given point.
        Equivalent to left multiply the matrix by T*M*T_inv, where M is `matrix2`, T the
        translation generated by `vector` and T_inv the inverse translation.
        For example, if `matrix2` is a rotation, the result is the transformation generated
        by the current matrix followed by a rotation around the point represented by `vector`.

        vector : Base.Vector
        matrix2 : Base.Matrix
        """
        ...

    def col(self, index: int, /) -> Vector:
        """
        Return the vector of a column, that is, the vector generated by the three
        first elements of the specified column.

        index : int
            Required column index.
        """
        ...

    def setCol(self, index: int, vector: Vector, /) -> None:
        """
        Set the vector of a column, that is, the three first elements of the specified
        column by index.

        index : int
            Required column index.
        vector : Base.Vector
        """
        ...

    def row(self, index: int, /) -> Vector:
        """
        Return the vector of a row, that is, the vector generated by the three
        first elements of the specified row.

        index : int
            Required row index.
        """
        ...

    def setRow(self, index: int, vector: Vector, /) -> None:
        """
        Set the vector of a row, that is, the three first elements of the specified
        row by index.

        index : int
            Required row index.
        vector : Base.Vector
        """
        ...

    def diagonal(self) -> Vector:
        """
        Return the diagonal of the 3x3 leading principal submatrix as vector.
        """
        ...

    def setDiagonal(self, vector: Vector, /) -> None:
        """
        Set the diagonal of the 3x3 leading principal submatrix.

        vector : Base.Vector
        """
        ...

    def rotateX(self, angle: float, /) -> None:
        """
        Rotate around X axis.

        angle : float
            Angle in radians.
        """
        ...

    def rotateY(self, angle: float, /) -> None:
        """
        Rotate around Y axis.

        angle : float
            Angle in radians.
        """
        ...

    def rotateZ(self, angle: float, /) -> None:
        """
        Rotate around Z axis.

        angle : float
            Angle in radians.
        """
        ...

    @overload
    def multiply(self, matrix: 'Matrix', /) -> 'Matrix':
        ...

    @overload
    def multiply(self, vector: Vector, /) -> Vector:
        ...

    def multiply(self, obj: Union['Matrix', Vector], /) -> Union['Matrix', Vector]:
        """
        Right multiply the matrix by the given object.
        If the argument is a vector, this is augmented to the 4D vector (`vector`, 1).

        matrix : Base.Matrix
        vector : Base.Vector
        """
        ...

    def multVec(self, vector: Vector, /) -> Vector:
        """
        Compute the transformed vector using the matrix.

        vector : Base.Vector
        """
        ...

    def invert(self) -> None:
        """
        Compute the inverse matrix in-place, if possible.
        """
        ...

    def inverse(self) -> 'Matrix':
        """
        Compute the inverse matrix, if possible.
        """
        ...

    def transpose(self) -> None:
        """
        Transpose the matrix in-place.
        """
        ...

    def transposed(self) -> 'Matrix':
        """
        Returns a transposed copy of this matrix.
        """
        ...

    def determinant(self) -> float:
        """
        Compute the determinant of the matrix.
        """
        ...

    def isOrthogonal(self, tol: float=1e-06, /) -> float:
        """
        Checks if the matrix is orthogonal, i.e. M * M^T = k*I and returns
        the multiple of the identity matrix. If it's not orthogonal 0 is returned.

        tol : float
            Tolerance used to check orthogonality.
        """
        ...

    def submatrix(self, dim: int, /) -> 'Matrix':
        """
        Get the leading principal submatrix of the given dimension.
        The (4 - `dim`) remaining dimensions are completed with the
        corresponding identity matrix.

        dim : int
            Dimension parameter must be in the range [1,4].
        """
        ...

    def analyze(self) -> str:
        """
        Analyzes the type of transformation.
        """
        ...

class Persistence(BaseClass):
    """
    Base.Persistence class.

    Class to dump and restore the content of an object.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Content: Final[str] = ''
    'Content of the object in XML representation.'
    MemSize: Final[int] = 0
    'Memory size of the object in bytes.'

    def dumpContent(self, Compression: int=3) -> bytearray:
        """
        Dumps the content of the object, both the XML representation and the additional
        data files required, into a byte representation.

        Compression : int
            Set the data compression level in the range [0,9]. Set to 0 for no compression.
        """
        ...

    def restoreContent(self, obj: object, /) -> None:
        """
        Restore the content of the object from a byte representation as stored by `dumpContent`.
        It could be restored from any Python object implementing the buffer protocol.

        obj : buffer
            Object with buffer protocol support.
        """
        ...

class Placement:
    """
    Base.Placement class.

    A Placement defines an orientation (rotation) and a position (base) in 3D space.
    It is used when no scaling or other distortion is needed.

    The following constructors are supported:

    Placement()
    Empty constructor.

    Placement(placement)
    Copy constructor.
    placement : Base.Placement

    Placement(matrix)
    Define from a 4D matrix consisting of rotation and translation.
    matrix : Base.Matrix

    Placement(base, rotation)
    Define from position and rotation.
    base : Base.Vector
    rotation : Base.Rotation

    Placement(base, rotation, center)
    Define from position and rotation with center.
    base : Base.Vector
    rotation : Base.Rotation
    center : Base.Vector

    Placement(base, axis, angle)
    define position and rotation.
    base : Base.Vector
    axis : Base.Vector
    angle : float
    """
    Base: Vector = ...
    'Vector to the Base Position of the Placement.'
    'Orientation of the placement expressed as rotation.'
    'Set/get matrix representation of the placement.'

    def copy(self) -> 'Placement':
        """
        Returns a copy of this placement.
        """
        ...

    def move(self, vector: Vector, /) -> None:
        """
        Move the placement along a vector.

        vector : Base.Vector
            Vector by which to move the placement.
        """
        ...

    def translate(self, vector: Vector, /) -> None:
        """
        Alias to move(), to be compatible with TopoShape.translate().

        vector : Base.Vector
            Vector by which to move the placement.
        """
        ...

    @overload
    def rotate(self, center: Sequence[float], axis: Sequence[float], angle: float, *, comp: bool=False) -> None:
        ...

    @overload
    def rotate(self, center: Vector, axis: Vector, angle: float, *, comp: bool=False) -> None:
        """
        Rotate the current placement around center and axis with the given angle.
        This method is compatible with TopoShape.rotate() if the (optional) keyword
        argument comp is True (default=False).

        center : Base.Vector, sequence of float
            Rotation center.
        axis : Base.Vector, sequence of float
            Rotation axis.
        angle : float
            Rotation angle in degrees.
        comp : bool
            optional keyword only argument, if True (default=False),
        behave like TopoShape.rotate() (i.e. the resulting placements are interchangeable).
        """

    def rotate(self, *args, **kwargs) -> None:
        ...

    def multiply(self, placement: 'Placement', /) -> 'Placement':
        """
        Right multiply this placement with another placement.
        Also available as `*` operator.

        placement : Base.Placement
            Placement by which to multiply this placement.
        """
        ...

    def multVec(self, vector: Vector, /) -> Vector:
        """
        Compute the transformed vector using the placement.

        vector : Base.Vector
            Vector to be transformed.
        """
        ...

    def inverse(self) -> 'Placement':
        """
        Compute the inverse placement.
        """
        ...

    def pow(self, t: float, shorten: bool=True, /) -> 'Placement':
        """
        Raise this placement to real power using ScLERP interpolation.
        Also available as `**` operator.

        t : float
            Real power.
        shorten : bool
            If True, ensures rotation quaternion is net positive to make
            the path shorter.
        """
        ...

    def sclerp(self, placement2: 'Placement', t: float, shorten: bool=True, /) -> 'Placement':
        """
        Screw Linear Interpolation (ScLERP) between this placement and `placement2`.
        Interpolation is a continuous motion along a helical path parametrized by `t`
        made of equal transforms if discretized.
        If quaternions of rotations of the two placements differ in sign, the interpolation
        will take a long path.

        placement2 : Base.Placement
        t : float
            Parameter of helical path. t=0 returns this placement, t=1 returns
            `placement2`. t can also be outside of [0, 1] range for extrapolation.
        shorten : bool
            If True, the signs are harmonized before interpolation and the interpolation
            takes the shorter path.
        """
        ...

    def slerp(self, placement2: 'Placement', t: float, /) -> 'Placement':
        """
        Spherical Linear Interpolation (SLERP) between this placement and `placement2`.
        This function performs independent interpolation of rotation and movement.
        Result of such interpolation might be not what application expects, thus this tool
        might be considered for simple cases or for interpolating between small intervals.
        For more complex cases you better use the advanced sclerp() function.

        placement2 : Base.Placement
        t : float
            Parameter of the path. t=0 returns this placement, t=1 returns `placement2`.
        """
        ...

    def isIdentity(self, tol: float=0.0, /) -> bool:
        """
        Returns True if the placement has no displacement and no rotation.
        Matrix representation is the 4D identity matrix.
        tol : float
            Tolerance used to check for identity.
            If tol is negative or zero, no tolerance is used.
        """
        ...

    def isSame(self, other: 'Placement', tol: float=0.0, /) -> bool:
        """
        Checks whether this and the given placement are the same.
        The default tolerance is set to 0.0
        """
        ...
    Rotation: 'FreeCAD.Base.Rotation' = ...
    Matrix: 'FreeCAD.Base.Matrix' = ...

    @overload
    def __init__(self, matrix: 'FreeCAD.Base.Matrix') -> None:
        ...

    @overload
    def __init__(self, base: Vector, rotation: 'FreeCAD.Base.Rotation') -> None:
        ...

    @overload
    def __init__(self, base: Vector, rotation: 'FreeCAD.Base.Rotation', center: Vector) -> None:
        ...

    @overload
    def __mul__(self, vector: Vector, /) -> Vector:
        ...

    @overload
    def __mul__(self, rotation: 'FreeCAD.Base.Rotation', /) -> 'Placement':
        ...

    @overload
    def __mul__(self, matrix: 'FreeCAD.Base.Matrix', /) -> 'FreeCAD.Base.Matrix':
        ...

    @overload
    def __mul__(self, placement: 'Placement', /) -> 'Placement':
        ...

    def toMatrix(self) -> 'FreeCAD.Base.Matrix':
        ...

class Precision:
    """
    This is the Precision class

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    @staticmethod
    def angular() -> float:
        """
        Returns the recommended precision value when checking the equality of two angles (given in radians)
        """
        ...

    @staticmethod
    def confusion() -> float:
        """
        Returns the recommended precision value when checking coincidence of two points in real space
        """
        ...

    @staticmethod
    def squareConfusion() -> float:
        """
        Returns square of confusion
        """
        ...

    @staticmethod
    def intersection() -> float:
        """
        Returns the precision value in real space, frequently used by intersection algorithms
        """
        ...

    @staticmethod
    def approximation() -> float:
        """
        Returns the precision value in real space, frequently used by approximation algorithms
        """
        ...

    @staticmethod
    def parametric() -> float:
        """
        Convert a real space precision to a parametric space precision
        """
        ...

    @staticmethod
    def isInfinite() -> bool:
        """
        Returns True if R may be considered as an infinite number
        """
        ...

    @staticmethod
    def isPositiveInfinite() -> bool:
        """
        Returns True if R may  be considered as a positive infinite number
        """
        ...

    @staticmethod
    def isNegativeInfinite() -> bool:
        """
        Returns True if R may  be considered as a negative infinite number
        """
        ...

    @staticmethod
    def infinite() -> float:
        """
        Returns a  big number that  can  be  considered as infinite
        """
        ...

class Quantity:
    """
    Quantity
    defined by a value and a unit.

    The following constructors are supported:
    Quantity() -- empty constructor
    Quantity(Value) -- empty constructor
    Quantity(Value,Unit) -- empty constructor
    Quantity(Quantity) -- copy constructor
    Quantity(string) -- arbitrary mixture of numbers and chars defining a Quantity

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Value: float = ...
    'Numeric Value of the Quantity (in internal system mm,kg,s)'
    Unit: 'FreeCAD.Base.Unit' = ...
    'Unit of the Quantity'
    UserString: Final[str] = ...
    'Unit of the Quantity'
    Format: dict = ...
    'Format of the Quantity'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, value: float) -> None:
        ...

    @overload
    def __init__(self, value: float, unit: 'FreeCAD.Base.Unit') -> None:
        ...

    @overload
    def __init__(self, quantity: 'Quantity') -> None:
        ...

    @overload
    def __init__(self, string: str) -> None:
        ...

    @overload
    def toStr(self, /) -> str:
        ...

    @overload
    def toStr(self, decimals: int, /) -> str:
        ...

    def toStr(self, decimals: int=..., /) -> str:
        """
        Returns a string representation rounded to number of decimals. If no decimals are specified then
        the internal precision is used
        """
        ...

    def getUserPreferred(self) -> Tuple['Quantity', str]:
        """
        Returns a quantity with the translation factor and a string with the prevered unit
        """
        ...

    @overload
    def getValueAs(self, unit: str, /) -> float:
        ...

    @overload
    def getValueAs(self, translation: float, unit_signature: int, /) -> float:
        ...

    @overload
    def getValueAs(self, unit: 'FreeCAD.Base.Unit', /) -> float:
        ...

    @overload
    def getValueAs(self, quantity: 'Quantity', /) -> float:
        ...

    def getValueAs(self, *args) -> float:
        """
        Returns a floating point value as the provided unit

        Following parameters are allowed:
        getValueAs('m/s')  # unit string to parse
        getValueAs(2.45,1) # translation value and unit signature
        getValueAs(FreeCAD.Units.Pascal) # predefined standard units
        getValueAs(Qantity('N/m^2')) # a quantity
        getValueAs(Unit(0,1,0,0,0,0,0,0)) # a unit
        """
        ...

    @overload
    def __round__(self, /) -> int:
        ...

    @overload
    def __round__(self, ndigits: int, /) -> float:
        ...

    def __round__(self, ndigits: int=..., /) -> Union[int, float]:
        """
        Returns the Integral closest to x, rounding half toward even.
        When an argument is passed, work like built-in round(x, ndigits).
        """
        ...

class Rotation:
    """
    Base.Rotation class.

    A Rotation using a quaternion.

    The following constructors are supported:

    Rotation()
    Empty constructor.

    Rotation(rotation)
    Copy constructor.

    Rotation(Axis, Radian)
    Rotation(Axis, Degree)
    Define from an axis and an angle (in radians or degrees according to the keyword).
    Axis : Base.Vector
    Radian : float
    Degree : float

    Rotation(vector_start, vector_end)
    Define from two vectors (rotation from/to vector).
    vector_start : Base.Vector
    vector_end : Base.Vector

    Rotation(angle1, angle2, angle3)
    Define from three floats (Euler angles) as yaw-pitch-roll in XY'Z'' convention.
    angle1 : float
    angle2 : float
    angle3 : float

    Rotation(seq, angle1, angle2, angle3)
    Define from one string and three floats (Euler angles) as Euler rotation
    of a given type. Call toEulerAngles() for supported sequence types.
    seq : str
    angle1 : float
    angle2 : float
    angle3 : float

    Rotation(x, y, z, w)
    Define from four floats (quaternion) where the quaternion is specified as:
    q = xi+yj+zk+w, i.e. the last parameter is the real part.
    x : float
    y : float
    z : float
    w : float

    Rotation(dir1, dir2, dir3, seq)
    Define from three vectors that define rotated axes directions plus an optional
    3-characher string of capital letters 'X', 'Y', 'Z' that sets the order of
    importance of the axes (e.g., 'ZXY' means z direction is followed strictly,
    x is used but corrected if necessary, y is ignored).
    dir1 : Base.Vector
    dir2 : Base.Vector
    dir3 : Base.Vector
    seq : str

    Rotation(matrix)
    Define from a matrix rotation in the 4D representation.
    matrix : Base.Matrix

    Rotation(*coef)
    Define from 16 or 9 elements which represent the rotation in the 4D matrix
    representation or in the 3D matrix representation, respectively.
    coef : sequence of float

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Q: Tuple[float, ...] = ()
    'The rotation elements (as quaternion).'
    Axis: object = ...
    'The rotation axis of the quaternion.'
    RawAxis: Final[object] = ...
    'The rotation axis without normalization.'
    Angle: float = 0.0
    'The rotation angle of the quaternion.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, rotation: 'Rotation') -> None:
        ...

    @overload
    def __init__(self, axis: Vector, angle: float) -> None:
        ...

    @overload
    def __init__(self, vector_start: Vector, vector_end: Vector) -> None:
        ...

    @overload
    def __init__(self, angle1: float, angle2: float, angle3: float) -> None:
        ...

    @overload
    def __init__(self, seq: str, angle1: float, angle2: float, angle3: float) -> None:
        ...

    @overload
    def __init__(self, x: float, y: float, z: float, w: float) -> None:
        ...

    @overload
    def __init__(self, dir1: Vector, dir2: Vector, dir3: Vector, seq: str) -> None:
        ...

    @overload
    def __init__(self, matrix: Matrix) -> None:
        ...

    @overload
    def __init__(self, *coef: float) -> None:
        ...

    def invert(self) -> None:
        """
        Sets the rotation to its inverse.
        """
        ...

    def inverted(self) -> 'Rotation':
        """
        Returns the inverse of the rotation.
        """
        ...

    def isSame(self, rotation: 'Rotation', tol: float=0, /) -> bool:
        """
        Checks if `rotation` perform the same transformation as this rotation.

        rotation : Base.Rotation
        tol : float
            Tolerance used to compare both rotations.
            If tol is negative or zero, no tolerance is used.
        """
        ...

    def multiply(self, rotation: 'Rotation', /) -> 'Rotation':
        """
        Right multiply this rotation with another rotation.

        rotation : Base.Rotation
            Rotation by which to multiply this rotation.
        """
        ...

    @overload
    def __mul__(self, vector: Vector, /) -> Vector:
        ...

    @overload
    def __mul__(self, matrix: Matrix, /) -> Matrix:
        ...

    @overload
    def __mul__(self, placement: Placement, /) -> Placement:
        ...

    @overload
    def __mul__(self, rotation: Rotation, /) -> Rotation:
        ...

    def multVec(self, vector: Vector, /) -> Vector:
        """
        Compute the transformed vector using the rotation.

        vector : Base.Vector
            Vector to be transformed.
        """
        ...

    def slerp(self, rotation2: 'Rotation', t: float, /) -> 'Rotation':
        """
        Spherical Linear Interpolation (SLERP) of this rotation and `rotation2`.

        t : float
            Parameter of the path. t=0 returns this rotation, t=1 returns `rotation2`.
        """
        ...

    def setYawPitchRoll(self, angle1: float, angle2: float, angle3: float, /) -> None:
        """
        Set the Euler angles of this rotation as yaw-pitch-roll in XY'Z'' convention.

        angle1 : float
            Angle around yaw axis in degrees.
        angle2 : float
            Angle around pitch axis in degrees.
        angle3 : float
            Angle around roll axis in degrees.
        """
        ...

    def getYawPitchRoll(self) -> Tuple[float, float, float]:
        """
        Get the Euler angles of this rotation as yaw-pitch-roll in XY'Z'' convention.
        The angles are given in degrees.
        """
        ...

    def setEulerAngles(self, seq: str, angle1: float, angle2: float, angle3: float, /) -> None:
        """
        Set the Euler angles in a given sequence for this rotation.
        The angles must be given in degrees.

        seq : str
            Euler sequence name. All possible values given by toEulerAngles().
        angle1 : float
        angle2 : float
        angle3 : float
        """
        ...

    def toEulerAngles(self, seq: str='', /) -> List[float]:
        """
        Get the Euler angles in a given sequence for this rotation.

        seq : str
            Euler sequence name. If not given, the function returns
            all possible values of `seq`. Optional.
        """
        ...

    def toMatrix(self) -> Matrix:
        """
        Convert the rotation to a 4D matrix representation.
        """
        ...

    def isNull(self) -> bool:
        """
        Returns True if all values in the quaternion representation are zero.
        """
        ...

    def isIdentity(self, tol: float=0, /) -> bool:
        """
        Returns True if the rotation equals the 4D identity matrix.
        tol : float
            Tolerance used to check for identity.
            If tol is negative or zero, no tolerance is used.
        """
        ...

class TypeId:
    """
    BaseTypePy class.

    This class provides functionality related to type management in the Base module. It's not intended for direct instantiation but for accessing type information and creating instances of various types. Instantiation is possible for classes that inherit from the Base::BaseClass class and are not abstract.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Name: Final[str] = ''
    'The name of the type id.'
    Key: Final[int] = 0
    'The key of the type id.'
    Module: Final[str] = ''
    'Module in which this class is defined.'

    @staticmethod
    def fromName(name: str, /) -> 'Type':
        """
        Returns a type object by name.

        name : str
        """
        ...

    @staticmethod
    def fromKey(key: int, /) -> 'Type':
        """
        Returns a type id object by key.

        key : int
        """
        ...

    @staticmethod
    def getNumTypes() -> int:
        """
        Returns the number of type ids created so far.
        """
        ...

    @staticmethod
    def getBadType() -> 'Type':
        """
        Returns an invalid type id.
        """
        ...

    @staticmethod
    def getAllDerivedFrom(type: str, /) -> List[str]:
        """
        Returns all descendants from the given type id.

        type : str, Base.BaseType
        """
        ...

    def getParent(self) -> 'Type':
        """
        Returns the parent type id.
        """
        ...

    def isBad(self) -> bool:
        """
        Checks if the type id is invalid.
        """
        ...

    def isDerivedFrom(self, type: str, /) -> bool:
        """
        Returns true if given type id is a father of this type id.

        type : str, Base.BaseType
        """
        ...

    def getAllDerived(self) -> List[object]:
        """
        Returns all descendants from this type id.
        """
        ...

    def createInstance(self) -> object:
        """
        Creates an instance of this type id.
        """
        ...

    @staticmethod
    def createInstanceByName(name: str, load: bool=False, /) -> object:
        """
        Creates an instance of the named type id.

        name : str
        load : bool
            Load named type id module.
        """
        ...

class Unit:
    """
    Unit
    defines a unit type, calculate and compare.

    The following constructors are supported:
    Unit()                        -- empty constructor
    Unit(i1,i2,i3,i4,i5,i6,i7,i8) -- unit signature
    Unit(Quantity)                -- copy unit from Quantity
    Unit(Unit)                    -- copy constructor
    Unit(string)                  -- parse the string for units

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, i1: float, i2: float, i3: float, i4: float, i5: float, i6: float, i7: float, i8: float) -> None:
        ...

    @overload
    def __init__(self, quantity: Quantity) -> None:
        ...

    @overload
    def __init__(self, unit: Unit) -> None:
        ...

    @overload
    def __init__(self, string: str) -> None:
        ...
    TypeId: Final[str] = ...
    "holds the unit type as a string, e.g. 'Area'."
    Signature: Final[Tuple] = ...
    'Returns the signature.'

class Vector:
    """
    Base.Vector class.

    This class represents a 3D float vector.
    Useful to represent points in the 3D space.

    The following constructors are supported:

    Vector(x=0, y=0, z=0)
    x : float
    y : float
    z : float

    Vector(vector)
    Copy constructor.
    vector : Base.Vector

    Vector(seq)
    Define from a sequence of float.
    seq : sequence of float.

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    Length: float = 0.0
    'Gets or sets the length of this vector.'
    x: float = 0.0
    'Gets or sets the X component of this vector.'
    y: float = 0.0
    'Gets or sets the Y component of this vector.'
    z: float = 0.0
    'Gets or sets the Z component of this vector.'

    @overload
    def __init__(self, x: float=0, y: float=0, z: float=0) -> None:
        ...

    @overload
    def __init__(self, vector: 'Vector') -> None:
        ...

    @overload
    def __init__(self, seq: Sequence[float]) -> None:
        ...

    def __reduce__(self) -> tuple:
        """
        Serialization of Vector objects.
        """
        ...

    def add(self, vector2: 'Vector', /) -> 'Vector':
        """
        Returns the sum of this vector and `vector2`.

        vector2 : Base.Vector
        """
        ...

    def sub(self, vector2: 'Vector', /) -> 'Vector':
        """
        Returns the difference of this vector and `vector2`.

        vector2 : Base.Vector
        """
        ...

    def negative(self) -> 'Vector':
        """
        Returns the negative (opposite) of this vector.
        """
        ...

    def scale(self, x: float, y: float, z: float, /) -> 'Vector':
        """
        Scales in-place this vector by the given factor in each component.

        x : float
            x-component factor scale.
        y : float
            y-component factor scale.
        z : float
            z-component factor scale.
        """
        ...

    def multiply(self, factor: float, /) -> 'Vector':
        """
        Multiplies in-place each component of this vector by a single factor.
        Equivalent to scale(factor, factor, factor).

        factor : float
        """
        ...

    def dot(self, vector2: 'Vector', /) -> float:
        """
        Returns the scalar product (dot product) between this vector and `vector2`.

        vector2 : Base.Vector
        """
        ...

    def cross(self, vector2: 'Vector', /) -> 'Vector':
        """
        Returns the vector product (cross product) between this vector and `vector2`.

        vector2 : Base.Vector
        """
        ...

    def isOnLineSegment(self, vector1: 'Vector', vector2: 'Vector', /) -> bool:
        """
        Checks if this vector is on the line segment generated by `vector1` and `vector2`.

        vector1 : Base.Vector
        vector2 : Base.Vector
        """
        ...

    def getAngle(self, vector2: 'Vector', /) -> float:
        """
        Returns the angle in radians between this vector and `vector2`.

        vector2 : Base.Vector
        """
        ...

    def normalize(self) -> 'Vector':
        """
        Normalizes in-place this vector to the length of 1.0.
        """
        ...

    def isEqual(self, vector2: 'Vector', tol: float=0, /) -> bool:
        """
        Checks if the distance between the points represented by this vector
        and `vector2` is less or equal to the given tolerance.

        vector2 : Base.Vector
        tol : float
        """
        ...

    def isParallel(self, vector2: 'Vector', tol: float=0, /) -> bool:
        """
        Checks if this vector and `vector2` are
        parallel less or equal to the given tolerance.

        vector2 : Base.Vector
        tol : float
        """
        ...

    def isNormal(self, vector2: 'Vector', tol: float=0, /) -> bool:
        """
        Checks if this vector and `vector2` are
        normal less or equal to the given tolerance.

        vector2 : Base.Vector
        tol : float
        """
        ...

    def projectToLine(self, point: 'Vector', dir: 'Vector', /) -> 'Vector':
        """
        Projects `point` on a line that goes through the origin with the direction `dir`.
        The result is the vector from `point` to the projected point.
        The operation is equivalent to dir_n.cross(dir_n.cross(point)), where `dir_n` is
        the vector `dir` normalized.
        The method modifies this vector instance according to result and does not
        depend on the vector itself.

        point : Base.Vector
        dir : Base.Vector
        """
        ...

    def projectToPlane(self, base: 'Vector', normal: 'Vector', /) -> 'Vector':
        """
        Projects in-place this vector on a plane defined by a base point
        represented by `base` and a normal defined by `normal`.

        base : Base.Vector
        normal : Base.Vector
        """
        ...

    def distanceToPoint(self, point2: 'Vector', /) -> float:
        """
        Returns the distance to another point represented by `point2`.
        .
        point : Base.Vector
        """
        ...

    def distanceToLine(self, base: 'Vector', dir: 'Vector', /) -> float:
        """
        Returns the distance between the point represented by this vector
        and a line defined by a base point represented by `base` and a
        direction `dir`.

        base : Base.Vector
        dir : Base.Vector
        """
        ...

    def distanceToLineSegment(self, point1: 'Vector', point2: 'Vector', /) -> 'Vector':
        """
        Returns the vector between the point represented by this vector and the point
        on the line segment with the shortest distance. The line segment is defined by
        `point1` and `point2`.

        point1 : Base.Vector
        point2 : Base.Vector
        """
        ...

    def distanceToPlane(self, base: 'Vector', normal: 'Vector', /) -> float:
        """
        Returns the distance between this vector and a plane defined by a
        base point represented by `base` and a normal defined by `normal`.

        base : Base.Vector
        normal : Base.Vector
        """
        ...

    def __add__(self, vector2: 'Vector', /) -> 'Vector':
        ...

    def __sub__(self, vector2: 'Vector', /) -> 'Vector':
        ...

    @overload
    def __mul__(self, factor: float, /) -> 'Vector':
        ...

    @overload
    def __mul__(self, vector2: 'Vector', /) -> float:
        ...

    def __rmul__(self, factor: float, /) -> 'Vector':
        ...

    def __truediv__(self, factor: float, /) -> 'Vector':
        ...
