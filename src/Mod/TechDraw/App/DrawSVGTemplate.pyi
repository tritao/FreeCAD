from Base.Metadata import export

@export(
    Father="DrawTemplate",
    Name="DrawSVGTemplate",
    Twin="DrawSVGTemplate",
    TwinPointer="DrawSVGTemplate",
    Include="Mod/TechDraw/App/DrawSVGTemplate.h",
    Namespace="TechDraw",
    FatherInclude="DrawTemplatePy.h",
    FatherNamespace="TechDraw",
)
class DrawSVGTemplate(DrawTemplate):
    """
    DrawSVGTemplate class.

    Feature for creating and manipulating Technical Drawing SVG Templates
    Author: Luke Parry (l.parry@warwick.ac.uk)
    Licence: LGPL
    """

    def getEditFieldContent(self, EditFieldName: str) -> str:
        """
        getEditFieldContent(EditFieldName) - returns the content of a specific Editable Text Field

        EditFieldName : str
            Name of the editable text field.
        """
        ...

    def setEditFieldContent(self, EditFieldName: str, NewContent: str) -> None:
        """
        setEditFieldContent(EditFieldName, NewContent) - sets a specific Editable Text Field to a new value

        EditFieldName : str
            Name of the editable text field.
        NewContent : str
            New value to be set.
        """
        ...

    def translateLabel(self, translationContext: str, objectBaseName: str, objectUniqueName: str) -> None:
        """
        translateLabel(translationContext, objectBaseName, objectUniqueName).
         No return value.  Replace the current label with a translated version where possible.
        
        translationContext : str
            The context for translation.
        objectBaseName : str
            The base name of the object.
        objectUniqueName : str
            The unique name of the object.
        """
        ...