from Metadata import export
from App.DocumentObject import DocumentObject
from typing import Any, overload, Final


@export(
    Father="DocumentObject",
    Twin="DrawGeomHatch",
    TwinPointer="DrawGeomHatch",
    Include="Mod/TechDraw/App/DrawGeomHatch.h",
    Namespace="TechDraw",
    FatherInclude="App/DocumentObject.h",
    FatherNamespace="App",
)
class DrawGeomHatch(DocumentObject):
    """
    Author Licence="LGPL" Name="WandererFan" EMail="wandererfan@gmail.com"
    Feature for creating and manipulating Technical Drawing GeomHatch areas
    """

    def translateLabel(self, translationContext: Any, objectBaseName: Any, objectUniqueName: Any) -> None:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
         No return value.  Replace the current label with a translated version where possible.
        """
        ...