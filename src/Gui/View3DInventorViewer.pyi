# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import Literal, Optional, Tuple

from Base.Metadata import export
from Base.PyObjectBase import PyObjectBase

RGB = Tuple[float, float, float]
GradientMode = Literal["NONE", "LINEAR", "RADIAL"]

@export(Include="Gui/View3DInventorViewer.h")
class View3DInventorViewer(PyObjectBase):
    """
    Python wrapper for the low-level 3D viewer object returned by `view.getViewer()`.

    This is a Gui-side helper surface for advanced viewer control and temporary
    session overrides such as BIM Plan Edit.
    """

    def setBackgroundColor(self, red: float, green: float, blue: float, /) -> None: ...
    def getBackgroundColor(self) -> RGB:
        """
        Return the current effective viewer background color as RGB floats.
        """
        ...

    def setGradientBackground(self, mode: GradientMode, /) -> None: ...
    def getGradientBackground(self) -> GradientMode:
        """
        Return the current effective background gradient mode.
        """
        ...

    def setGradientBackgroundColor(
        self,
        fromColor: RGB,
        toColor: RGB,
        midColor: Optional[RGB] = None,
        /,
    ) -> None: ...
    def setBackgroundAppearanceOverride(
        self,
        mode: GradientMode,
        background: RGB,
        fromColor: RGB,
        toColor: RGB,
        midColor: Optional[RGB] = None,
        /,
    ) -> None:
        """
        Temporarily override the effective viewer background appearance without
        changing the stored preference-backed base appearance.
        """
        ...

    def clearBackgroundAppearanceOverride(self) -> None: ...
    def setEnabledNaviCube(self, enabled: bool, /) -> None: ...
    def isEnabledNaviCube(self) -> bool: ...
    def setNaviCubeEnabledOverride(self, enabled: bool, /) -> None:
        """
        Temporarily override the effective NaviCube enabled state without
        changing the stored preference-backed base state.
        """
        ...

    def clearNaviCubeEnabledOverride(self) -> None: ...
