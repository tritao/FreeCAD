from Base.Metadata import export, constmethod
from App.DocumentObject import DocumentObject

@export(
    Father="DocumentObject",
    Twin="DrawTemplate",
    TwinPointer="DrawTemplate",
    Include="Mod/TechDraw/App/DrawTemplate.h",
    Namespace="TechDraw",
    FatherInclude="App/DocumentObjectPy.h",
    FatherNamespace="App"
)
class DrawTemplate(DocumentObject):
    """
    Feature for creating and manipulating Technical Drawing Templates

    Author: Luke Parry
    Licence: LGPL
    EMail: l.parry@warwick.ac.uk
    """
    ...