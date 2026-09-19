# SPDX-License-Identifier: LGPL-2.1-or-later

"""Immutable issue manifests and drawing-set comparison."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .publishing import BIMSheetPublishingService
from .service import BIMSheetService


class SheetIssueError(RuntimeError):
    """Raised when a drawing issue cannot be created consistently."""


@dataclass(frozen=True)
class IssueComparison:
    added: tuple
    removed: tuple
    changed: tuple
    unchanged: tuple


class BIMSheetIssueService:
    """Create immutable issue records from current sheet publications."""

    BIM_TYPE = "BIM::SheetIssue"
    PROPERTY_GROUP = "BIM Issue"

    def __init__(self, document, clock=None):
        if document is None:
            raise ValueError("document is required")
        self.document = document
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def issues(self):
        return tuple(sorted(
            (obj for obj in self.document.Objects
             if getattr(obj, "BIMType", "") == self.BIM_TYPE),
            key=lambda obj: (obj.IssueOrder, obj.IssueIdentifier),
        ))

    def create_issue(self, identifier, label="", pages=None):
        identifier = str(identifier).strip()
        if not identifier:
            raise ValueError("issue identifier is required")
        if any(issue.IssueIdentifier == identifier for issue in self.issues()):
            raise SheetIssueError("issue identifier already exists: {}".format(identifier))
        pages = tuple(pages or BIMSheetPublishingService(self.document).ordered_sheets())
        if not pages:
            raise SheetIssueError("issue contains no BIM sheets")
        records = [self._sheet_record(page, identifier) for page in pages]
        numbers = [record["number"] for record in records]
        if len(set(numbers)) != len(numbers):
            raise SheetIssueError("issue contains duplicate sheet numbers")
        issued_at = self._clock().astimezone(timezone.utc).isoformat()
        previous = self.issues()[-1] if self.issues() else None
        next_order = len(self.issues()) + 1
        manifest = {
            "schema": 1,
            "issue": identifier,
            "label": label or identifier,
            "issued_at": issued_at,
            "sheets": records,
        }
        canonical = self.canonical_json(manifest)
        issue = self.document.addObject("App::FeaturePython", "BIMSheetIssue")
        issue.Label = label or identifier
        properties = (
            ("App::PropertyString", "BIMType", "Stable issue object type"),
            ("App::PropertyString", "IssueIdentifier", "Immutable issue identifier"),
            ("App::PropertyString", "IssuedAt", "UTC issue timestamp"),
            ("App::PropertyInteger", "IssueOrder", "Stable issue sequence"),
            ("App::PropertyString", "ManifestJSON", "Canonical issue manifest"),
            ("App::PropertyString", "ManifestSHA256", "Manifest content identity"),
            ("App::PropertyLink", "PreviousIssue", "Previous drawing issue"),
        )
        for property_type, name, description in properties:
            issue.addProperty(property_type, name, self.PROPERTY_GROUP, description)
        issue.BIMType = self.BIM_TYPE
        issue.IssueIdentifier = identifier
        issue.IssuedAt = issued_at
        issue.IssueOrder = next_order
        issue.ManifestJSON = canonical
        issue.ManifestSHA256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        issue.PreviousIssue = previous
        for name in (
            "BIMType", "IssueIdentifier", "IssuedAt", "IssueOrder",
            "ManifestJSON", "ManifestSHA256", "PreviousIssue",
        ):
            issue.setEditorMode(name, 1)
            issue.setPropertyStatus(name, "Immutable")
        return issue

    def compare(self, issue, previous=None):
        self._validate_issue(issue)
        previous = previous if previous is not None else issue.PreviousIssue
        current = self.manifest_for(issue)
        old = self.manifest_for(previous) if previous is not None else {"sheets": []}
        current_by_number = {item["number"]: item for item in current["sheets"]}
        old_by_number = {item["number"]: item for item in old["sheets"]}
        added = tuple(sorted(set(current_by_number) - set(old_by_number)))
        removed = tuple(sorted(set(old_by_number) - set(current_by_number)))
        changed = []
        unchanged = []
        for number in sorted(set(current_by_number) & set(old_by_number)):
            new = current_by_number[number]
            prior = old_by_number[number]
            reasons = []
            if new["revision"] != prior["revision"]:
                reasons.append("revision")
            metadata_keys = ("title", "discipline", "issue", "status", "template")
            if any(new[key] != prior[key] for key in metadata_keys):
                reasons.append("metadata")
            if new["sha256"] != prior["sha256"]:
                reasons.append("output")
            if reasons:
                changed.append((number, tuple(reasons)))
            else:
                unchanged.append(number)
        return IssueComparison(added, removed, tuple(changed), tuple(unchanged))

    def export_manifest(self, issue, path, overwrite=False):
        self._validate_issue(issue)
        path = Path(path)
        if path.exists() and not overwrite:
            raise SheetIssueError("manifest already exists: {}".format(path.name))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(issue.ManifestJSON + "\n", encoding="utf-8")
        return path

    @staticmethod
    def manifest_for(issue):
        return json.loads(issue.ManifestJSON)

    @staticmethod
    def canonical_json(manifest):
        return json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))

    def _sheet_record(self, page, identifier):
        if not BIMSheetService.is_sheet(page):
            raise SheetIssueError("issue contains a non-BIM page")
        number = page.SheetNumber.strip()
        if not number:
            raise SheetIssueError("sheet number is required")
        if str(page.Issue) != identifier:
            raise SheetIssueError(
                "sheet {} issue does not match {}".format(number, identifier)
            )
        required = (
            "LastPublishedAt", "LastPublishedRevision", "LastPublishedIssue",
            "LastPublishedFormat", "LastPublishedPath", "LastPublishedSHA256",
        )
        missing = [name for name in required if name not in page.PropertiesList]
        if missing:
            raise SheetIssueError("sheet {} has not been published".format(number))
        if page.LastPublishedRevision != page.Revision:
            raise SheetIssueError("sheet {} revision changed since publication".format(number))
        if page.LastPublishedIssue != identifier:
            raise SheetIssueError("sheet {} issue changed since publication".format(number))
        return {
            "number": number,
            "title": page.SheetTitle,
            "discipline": str(page.Discipline),
            "revision": page.Revision,
            "issue": page.Issue,
            "status": str(page.SheetStatus),
            "template": page.TemplateIdentity,
            "order": page.SheetOrder,
            "published_at": page.LastPublishedAt,
            "format": page.LastPublishedFormat,
            "path": page.LastPublishedPath,
            "sha256": page.LastPublishedSHA256,
        }

    def _validate_issue(self, issue):
        if issue is None or getattr(issue, "BIMType", "") != self.BIM_TYPE:
            raise TypeError("issue must be a BIM sheet issue")
