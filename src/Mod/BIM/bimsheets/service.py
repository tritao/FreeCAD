# SPDX-License-Identifier: LGPL-2.1-or-later

"""Application-layer contract for BIM drawing sheets."""

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class BIMSheetMetadata:
    """Stable metadata exposed by a BIM-enabled TechDraw page."""

    number: str = ""
    title: str = ""
    discipline: str = "General"
    revision: str = ""
    issue: str = ""
    issue_date: str = ""
    status: str = "Work in Progress"
    template_identity: str = ""
    order: int = 0


class BIMSheetService:
    """Create and identify TechDraw pages participating in a BIM sheet set."""

    SCHEMA_VERSION = 1
    PROPERTY_GROUP = "BIM Sheet"
    DISCIPLINES = (
        "General",
        "Architectural",
        "Structural",
        "Mechanical",
        "Electrical",
        "Plumbing",
        "Civil",
        "Landscape",
    )
    STATUSES = (
        "Work in Progress",
        "Shared",
        "Published",
        "Archived",
    )

    _STRING_PROPERTIES = (
        ("SheetNumber", "Drawing-set sheet number"),
        ("SheetTitle", "Drawing-set sheet title"),
        ("Revision", "Current sheet revision"),
        ("Issue", "Current sheet issue identifier"),
        ("IssueDate", "Current sheet issue date"),
        ("TemplateIdentity", "Stable identity of the sheet template"),
    )

    def __init__(self, document):
        if document is None:
            raise ValueError("document is required")
        self.document = document

    @staticmethod
    def is_sheet(page):
        """Return whether *page* implements the BIM sheet contract."""

        return bool(
            page is not None
            and page.isDerivedFrom("TechDraw::DrawPage")
            and "BIMSheetSchemaVersion" in page.PropertiesList
            and page.BIMSheetSchemaVersion >= 1
        )

    def ensure_metadata(self, page, metadata=None):
        """Add the sheet contract to a page and optionally apply metadata."""

        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            raise TypeError("page must be a TechDraw::DrawPage")

        group = self.PROPERTY_GROUP
        if "BIMSheetSchemaVersion" not in page.PropertiesList:
            page.addProperty(
                "App::PropertyInteger",
                "BIMSheetSchemaVersion",
                group,
                "BIM sheet metadata schema version",
            )
            page.BIMSheetSchemaVersion = self.SCHEMA_VERSION
            page.setEditorMode("BIMSheetSchemaVersion", 1)
        for name, description in self._STRING_PROPERTIES:
            if name not in page.PropertiesList:
                page.addProperty("App::PropertyString", name, group, description)
        if "Discipline" not in page.PropertiesList:
            page.addProperty(
                "App::PropertyEnumeration",
                "Discipline",
                group,
                "Drawing discipline",
            )
            page.Discipline = list(self.DISCIPLINES)
        if "SheetStatus" not in page.PropertiesList:
            page.addProperty(
                "App::PropertyEnumeration",
                "SheetStatus",
                group,
                "Drawing-set publication status",
            )
            page.SheetStatus = list(self.STATUSES)
        if "SheetOrder" not in page.PropertiesList:
            page.addProperty(
                "App::PropertyInteger",
                "SheetOrder",
                group,
                "Stable sheet ordering key",
            )

        if metadata is not None:
            self.apply_metadata(page, metadata)
        return page

    def apply_metadata(self, page, metadata):
        """Apply a metadata value object to an initialized sheet."""

        self.ensure_metadata(page)
        if metadata.discipline not in self.DISCIPLINES:
            raise ValueError(
                "unsupported sheet discipline: {}".format(metadata.discipline)
            )
        if metadata.status not in self.STATUSES:
            raise ValueError("unsupported sheet status: {}".format(metadata.status))
        page.SheetNumber = metadata.number
        page.SheetTitle = metadata.title
        page.Discipline = metadata.discipline
        page.Revision = metadata.revision
        page.Issue = metadata.issue
        page.IssueDate = metadata.issue_date
        page.SheetStatus = metadata.status
        page.TemplateIdentity = metadata.template_identity
        page.SheetOrder = metadata.order
        return page

    def metadata_for(self, page):
        """Read the normalized metadata of a BIM sheet."""

        if not self.is_sheet(page):
            raise ValueError("page is not a BIM sheet")
        return BIMSheetMetadata(
            number=page.SheetNumber,
            title=page.SheetTitle,
            discipline=str(page.Discipline),
            revision=page.Revision,
            issue=page.Issue,
            issue_date=page.IssueDate,
            status=str(page.SheetStatus),
            template_identity=page.TemplateIdentity,
            order=page.SheetOrder,
        )

    def create_sheet(self, template_path, metadata=None, name="Page"):
        """Create a BIM-enabled TechDraw page and its SVG template."""

        template_path = str(template_path)
        if not template_path:
            raise ValueError("template_path is required")
        page = self.document.addObject("TechDraw::DrawPage", name)
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "Template")
        template.Template = template_path
        page.Template = template
        values = metadata or BIMSheetMetadata(
            title=Path(template_path).stem,
            template_identity=Path(template_path).name,
        )
        if not values.template_identity:
            values = replace(values, template_identity=Path(template_path).name)
        self.ensure_metadata(page, values)
        page.Label = values.title or Path(template_path).stem
        return page
