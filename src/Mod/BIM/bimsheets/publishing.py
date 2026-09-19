# SPDX-License-Identifier: LGPL-2.1-or-later

"""Deterministic and atomic publication of BIM drawing sheets."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import tempfile

from .service import BIMSheetService
from .titleblock import BIMTitleBlockService


class SheetPublicationError(RuntimeError):
    """Raised when a sheet set cannot be safely published."""


@dataclass(frozen=True)
class PublishedSheet:
    page: object
    path: Path
    format: str
    sha256: str


@dataclass(frozen=True)
class SheetPublicationResult:
    sheets: tuple
    published_at: str


class BIMSheetPublishingService:
    """Validate and export BIM sheets without depending on Navigator widgets."""

    PROPERTY_GROUP = "BIM Publication"
    FORMATS = ("pdf", "svg")

    def __init__(self, document, exporter=None, clock=None):
        if document is None:
            raise ValueError("document is required")
        self.document = document
        self._exporter = exporter or self._export_page
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def ordered_sheets(self):
        sheet_service = BIMSheetService(self.document)
        pages = [obj for obj in self.document.Objects if sheet_service.is_sheet(obj)]
        return tuple(sorted(pages, key=lambda page: (
            getattr(page, "SheetOrder", 0),
            getattr(page, "SheetNumber", ""),
            page.Label.casefold(),
        )))

    def publish_sheet(self, page, output_directory, format="pdf", overwrite=False):
        return self._publish((page,), output_directory, format, overwrite)

    def publish_set(self, output_directory, format="pdf", overwrite=False):
        pages = self.ordered_sheets()
        if not pages:
            raise SheetPublicationError("document contains no BIM sheets")
        return self._publish(pages, output_directory, format, overwrite)

    def validate(self, page):
        if not BIMSheetService.is_sheet(page):
            raise SheetPublicationError("page is not a BIM sheet")
        if getattr(page, "Template", None) is None:
            raise SheetPublicationError("sheet has no SVG template")
        title_blocks = BIMTitleBlockService(self.document)
        mapping = title_blocks.mapping_for(page)
        required = {"number", "title"}
        missing = sorted(required - set(mapping))
        if missing:
            raise SheetPublicationError(
                "title block does not map required fields: {}".format(", ".join(missing))
            )
        for view in page.Views:
            if not view.isDerivedFrom("TechDraw::DrawViewArch"):
                continue
            if getattr(view, "BIMViewDefinition", None) is None:
                raise SheetPublicationError(
                    "drawing view {} has no saved BIM view".format(view.Label)
                )
        touched = [obj.Label for obj in (page, page.Template, *page.Views)
                   if "Touched" in getattr(obj, "State", ())]
        if touched:
            raise SheetPublicationError(
                "sheet contains stale objects: {}".format(", ".join(touched))
            )

    def filename_for(self, page, format):
        extension = self._normalize_format(format)
        number = self._filename_part(getattr(page, "SheetNumber", ""))
        title = self._filename_part(getattr(page, "SheetTitle", "") or page.Label)
        stem = " - ".join(part for part in (number, title) if part)
        return "{}.{}".format(stem or page.Name, extension)

    def _publish(self, pages, output_directory, format, overwrite):
        extension = self._normalize_format(format)
        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        self.document.recompute()
        targets = []
        for page in pages:
            BIMTitleBlockService(self.document).synchronize(page)
        self.document.recompute()
        for page in pages:
            self.validate(page)
            targets.append(output_directory / self.filename_for(page, extension))
        if len(set(targets)) != len(targets):
            raise SheetPublicationError("sheet filenames are not unique")
        existing = [path.name for path in targets if path.exists()]
        if existing and not overwrite:
            raise SheetPublicationError(
                "publication would overwrite: {}".format(", ".join(existing))
            )

        staged = []
        try:
            for page, target in zip(pages, targets):
                handle = tempfile.NamedTemporaryFile(
                    prefix=".bim-publish-", suffix="." + extension,
                    dir=output_directory, delete=False,
                )
                stage = Path(handle.name)
                handle.close()
                stage.unlink()
                staged.append((page, stage, target))
                self._exporter(page, stage, extension)
                if not stage.is_file() or stage.stat().st_size == 0:
                    raise SheetPublicationError(
                        "exporter produced no output for {}".format(page.Label)
                    )
            published_at = self._clock().astimezone(timezone.utc).isoformat()
            published = []
            for page, stage, target in staged:
                stage.replace(target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                self._record(page, target, extension, published_at, digest)
                published.append(PublishedSheet(page, target, extension, digest))
            return SheetPublicationResult(tuple(published), published_at)
        finally:
            for _page, stage, _target in staged:
                if stage.exists():
                    stage.unlink()

    def _record(self, page, path, format, published_at, digest):
        properties = (
            ("LastPublishedAt", "UTC timestamp of the latest publication"),
            ("LastPublishedRevision", "Revision included in the latest publication"),
            ("LastPublishedIssue", "Issue included in the latest publication"),
            ("LastPublishedFormat", "File format of the latest publication"),
            ("LastPublishedPath", "Output path of the latest publication"),
            ("LastPublishedSHA256", "SHA-256 identity of the latest publication"),
        )
        for name, description in properties:
            if name not in page.PropertiesList:
                page.addProperty("App::PropertyString", name, self.PROPERTY_GROUP, description)
        page.LastPublishedAt = published_at
        page.LastPublishedRevision = page.Revision
        page.LastPublishedIssue = page.Issue
        page.LastPublishedFormat = format
        page.LastPublishedPath = str(path)
        page.LastPublishedSHA256 = digest
        page.SheetStatus = "Published"

    @staticmethod
    def _normalize_format(format):
        value = str(format).lower().lstrip(".")
        if value not in BIMSheetPublishingService.FORMATS:
            raise ValueError("unsupported publication format: {}".format(format))
        return value

    @staticmethod
    def _filename_part(value):
        value = re.sub(r"[\\/:*?\"<>|]+", "-", str(value)).strip(" .-")
        return re.sub(r"\s+", " ", value)

    @staticmethod
    def _export_page(page, path, format):
        import TechDrawGui

        if format == "pdf":
            TechDrawGui.exportPageAsPdf(page, str(path))
        else:
            TechDrawGui.exportPageAsSvg(page, str(path))
