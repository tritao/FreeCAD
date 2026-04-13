# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from Part import BodyBase
from Part import Feature as PartFeature

from typing import *

# src/Mod/PartDesign/App/Body.pyi:13
class Body(BodyBase):
    """
    PartDesign body class

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    VisibleFeature: Final[object] = ...
    'Return the visible feature of this body'

    def insertObject(self, feature: object, target: object, after: bool=False, /) -> None:
        """
        Insert the feature into the body after the given feature.

        @param feature  The feature to insert into the body
        @param target   The feature relative which one should be inserted the given.
          If target is NULL than insert into the end if where is InsertBefore
          and into the begin if where is InsertAfter.
        @param after    if true insert the feature after the target. Default is false.

        @note the method doesn't modify the Tip unlike addObject()
        """
        ...

# src/Mod/PartDesign/App/Feature.pyi:13
class Feature(PartFeature):
    """
    This is the father of all PartDesign object classes

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """

    @overload
    def getBaseObject(self) -> Optional[object]:
        """
        getBaseObject: returns feature this one fuses itself to, or None. Normally, this should be the same as BaseFeature property, except for legacy workflow. In legacy workflow, it will look up the support of referenced sketch.
        """
        ...

    def getBaseObject(self) -> Optional[object]:
        """
        getBaseObject: returns feature this one fuses itself to, or None. Normally, this should be the same as BaseFeature property, except for legacy workflow. In legacy workflow, it will look up the support of referenced sketch.
        """
        ...
