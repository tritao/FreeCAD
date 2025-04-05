from Base.Metadata import export, constmethod
from typing import Final
from TechDraw.DrawView import DrawView

@export(
    Father="DrawViewPy",
    Name="DrawViewAnnotationPy",
    Twin="DrawViewAnnotation",
    TwinPointer="DrawViewAnnotation",
    Include="Mod/TechDraw/App/DrawViewAnnotation.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw"
)
class DrawViewAnnotation(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Annotation Views

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """
    ...