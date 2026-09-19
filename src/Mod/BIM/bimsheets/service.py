# SPDX-License-Identifier: LGPL-2.1-or-later

"""Application-layer contract for BIM drawing sheets."""

from dataclasses import dataclass, replace
from pathlib import Path

from .layout import (
    BIMSheetLayout,
    PlacementFootprint,
    SheetMargins,
)
from .footprints import BIMSheetFootprintProvider


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
    margin_left: float = 10.0
    margin_top: float = 10.0
    margin_right: float = 10.0
    margin_bottom: float = 10.0


class BIMSheetService:
    """Create and identify TechDraw pages participating in a BIM sheet set."""

    SCHEMA_VERSION = 4
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
    _MARGIN_PROPERTIES = (
        ("PrintableMarginLeft", "Left printable margin"),
        ("PrintableMarginTop", "Top printable margin"),
        ("PrintableMarginRight", "Right printable margin"),
        ("PrintableMarginBottom", "Bottom printable margin"),
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
        elif page.BIMSheetSchemaVersion < self.SCHEMA_VERSION:
            page.BIMSheetSchemaVersion = self.SCHEMA_VERSION
        for name, description in self._STRING_PROPERTIES:
            if name not in page.PropertiesList:
                page.addProperty("App::PropertyString", name, group, description)
        for name, description in self._MARGIN_PROPERTIES:
            if name not in page.PropertiesList:
                page.addProperty("App::PropertyLength", name, group, description)
                setattr(page, name, 10.0)
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
        if "ViewTitleTextSize" not in page.PropertiesList:
            page.addProperty("App::PropertyLength", "ViewTitleTextSize", group,
                             "Default text size for view titles")
            page.ViewTitleTextSize = 3.5
        if "ViewTitleOffset" not in page.PropertiesList:
            page.addProperty("App::PropertyLength", "ViewTitleOffset", group,
                             "Default vertical offset for view titles")
            page.ViewTitleOffset = 12.0
        if "ViewTitleFont" not in page.PropertiesList:
            page.addProperty("App::PropertyString", "ViewTitleFont", group,
                             "Optional font override for view titles")

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
        page.PrintableMarginLeft = metadata.margin_left
        page.PrintableMarginTop = metadata.margin_top
        page.PrintableMarginRight = metadata.margin_right
        page.PrintableMarginBottom = metadata.margin_bottom
        if getattr(page, "Template", None) is not None:
            from .titleblock import BIMTitleBlockService

            BIMTitleBlockService(self.document).synchronize(page)
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
            margin_left=page.PrintableMarginLeft.Value,
            margin_top=page.PrintableMarginTop.Value,
            margin_right=page.PrintableMarginRight.Value,
            margin_bottom=page.PrintableMarginBottom.Value,
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

    def layout_view(
        self,
        page,
        drawing_view,
        *,
        position=None,
        size=None,
        margins=None,
        gap=5.0,
    ):
        """Position a new drawing view without moving existing page views."""

        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            raise TypeError("page must be a TechDraw::DrawPage")
        if drawing_view not in page.Views:
            raise ValueError("drawing_view must belong to page")
        margins = margins or self.margins_for(page)
        engine = BIMSheetLayout(page.PageWidth, page.PageHeight, margins, gap)
        footprint = (
            PlacementFootprint.centered(*size)
            if size is not None
            else self._view_footprint(drawing_view)
        )
        occupied = self._occupied_footprints(page, drawing_view)
        x, y = engine.place_anchor(footprint, occupied, position)
        drawing_view.X = x
        drawing_view.Y = y
        return footprint.at(x, y)

    def validate_view_layout(
        self,
        page,
        drawing_view,
        *,
        position,
        scale=None,
        title_offset=None,
        title_size=None,
        view_number=None,
        view_title=None,
        gap=5.0,
    ):
        """Validate edited placement geometry without mutating the document."""

        footprint = BIMSheetFootprintProvider().for_view(
            drawing_view,
            scale=scale,
            title_offset=title_offset,
            title_size=title_size,
            view_number=view_number,
            view_title=view_title,
        )
        occupied = self._occupied_footprints(page, drawing_view)
        engine = BIMSheetLayout(
            page.PageWidth, page.PageHeight, self.margins_for(page), gap
        )
        x, y = engine.place_anchor(footprint, occupied, position)
        return footprint.at(x, y)

    @staticmethod
    def margins_for(page):
        """Return persisted printable margins or conservative defaults."""

        names = (
            "PrintableMarginLeft",
            "PrintableMarginTop",
            "PrintableMarginRight",
            "PrintableMarginBottom",
        )
        if all(name in page.PropertiesList for name in names):
            return SheetMargins(*(getattr(page, name).Value for name in names))
        return SheetMargins()

    @staticmethod
    def _view_footprint(drawing_view):
        return BIMSheetFootprintProvider().for_view(drawing_view)

    def _occupied_footprints(self, page, excluded_view):
        return tuple(
            self._view_footprint(view).at(view.X.Value, view.Y.Value)
            for view in page.Views
            if view is not excluded_view and not self._is_owned_title(view)
        )

    @staticmethod
    def _is_owned_title(view):
        owner = getattr(view, "Owner", None)
        return (
            view.isDerivedFrom("TechDraw::DrawViewAnnotation")
            and owner is not None
            and owner.isDerivedFrom("TechDraw::DrawViewArch")
        )
