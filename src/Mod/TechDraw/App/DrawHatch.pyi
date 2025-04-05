from Base.Metadata import export, constmethod
from App.DocumentObject import DocumentObject
from typing import Final


@export(
    Father="DocumentObject",
    Twin="DrawHatch",
    TwinPointer="DrawHatch",
    Include="Mod/TechDraw/App/DrawHatch.h",
    Namespace="TechDraw",
    FatherInclude="App/DocumentObjectPy.h",
    FatherNamespace="App"
)
class DrawHatch(DocumentObject):
    """
    Author: WandererFan (Licence: LGPL, EMail: wandererfan@gmail.com)
    Feature for creating and manipulating Technical Drawing Hatch areas
    """

    def translateLabel(self, translationContext: str, objectBaseName: str, objectUniqueName: str) -> None:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
         No return value.  Replace the current label with a translated version where possible.
        """
        ...