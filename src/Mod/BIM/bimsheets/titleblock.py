# SPDX-License-Identifier: LGPL-2.1-or-later

"""Persistent synchronization of BIM sheet metadata into SVG title blocks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TitleBlockSyncResult:
    """Outcome of one title-block synchronization pass."""

    updated: tuple
    missing: tuple


class BIMTitleBlockService:
    """Resolve, persist, inspect, and refresh title-block field mappings."""

    PROPERTY_GROUP = "BIM Title Block"
    METADATA_PROPERTIES = {
        "number": "SheetNumber",
        "title": "SheetTitle",
        "discipline": "Discipline",
        "revision": "Revision",
        "issue": "Issue",
        "issue_date": "IssueDate",
        "status": "SheetStatus",
    }
    FIELD_CANDIDATES = {
        "number": ("drawing_number", "sheet_number", "DrawingNumber", "Drawing Number"),
        "title": ("title", "DrawingTitle1", "drawing_title", "Title"),
        "discipline": ("discipline", "Discipline"),
        "revision": ("revision_index", "revision", "Revision", "Rev"),
        "issue": ("issue", "issue_id", "Issue"),
        "issue_date": ("date_of_issue", "issue_date", "IssueDate", "Date"),
        "status": ("status", "document_status", "Status"),
    }
    TEMPLATE_MAPPINGS = {
        "A4_Landscape_ISO5457_minimal.svg": {
            "number": "drawing_number",
            "title": "title",
            "revision": "revision_index",
            "issue_date": "date_of_issue",
        },
        "ANSIA_Landscape.svg": {
            "number": "drawing_number",
            "title": "DrawingTitle1",
            "revision": "revision_index",
        },
    }

    def __init__(self, document):
        if document is None:
            raise ValueError("document is required")
        self.document = document

    def ensure_mapping(self, page, mapping=None):
        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            raise TypeError("page must be a TechDraw::DrawPage")
        if getattr(page, "Template", None) is None:
            raise ValueError("sheet has no SVG template")
        semantic = dict(mapping) if mapping is not None else self.mapping_for(page)
        if not semantic:
            semantic = self.resolve_mapping(page)
        self._validate_mapping(page.Template, semantic)
        page.EditableTextBindings = {
            self.METADATA_PROPERTIES[key]: field for key, field in semantic.items()
        }
        if "MissingTitleBlockFields" not in page.PropertiesList:
            page.addProperty(
                "App::PropertyStringList",
                "MissingTitleBlockFields",
                self.PROPERTY_GROUP,
                "BIM metadata keys with no compatible SVG field",
            )
            page.setEditorMode("MissingTitleBlockFields", 1)
        page.MissingTitleBlockFields = [
            key for key in self.METADATA_PROPERTIES if key not in semantic
        ]
        return semantic

    def mapping_for(self, page):
        reverse = {value: key for key, value in self.METADATA_PROPERTIES.items()}
        return {
            reverse[property_name]: field
            for property_name, field in dict(page.EditableTextBindings).items()
            if property_name in reverse
        }

    def resolve_mapping(self, page):
        fields = set(page.Template.EditableTexts)
        identity = getattr(page, "TemplateIdentity", "")
        mapping = {
            key: field
            for key, field in self.TEMPLATE_MAPPINGS.get(identity, {}).items()
            if field in fields
        }
        casefolded = {field.casefold(): field for field in fields}
        for key, candidates in self.FIELD_CANDIDATES.items():
            if key in mapping:
                continue
            for candidate in candidates:
                field = casefolded.get(candidate.casefold())
                if field is not None:
                    mapping[key] = field
                    break
        return mapping

    def synchronize(self, page, mapping=None):
        before = dict(page.Template.EditableTexts)
        semantic = self.ensure_mapping(page, mapping)
        after = dict(page.Template.EditableTexts)
        for key, field in semantic.items():
            after[field] = str(getattr(page, self.METADATA_PROPERTIES[key], ""))
        if after != before:
            page.Template.EditableTexts = after
        updated = tuple(
            key
            for key, field in semantic.items()
            if before.get(field) != after.get(field)
        )
        return TitleBlockSyncResult(updated, tuple(page.MissingTitleBlockFields))

    def describe(self, page):
        mapping = self.mapping_for(page)
        return tuple((key, mapping.get(key)) for key in self.METADATA_PROPERTIES)

    @classmethod
    def _validate_mapping(cls, template, mapping):
        unknown_keys = set(mapping) - set(cls.METADATA_PROPERTIES)
        if unknown_keys:
            raise ValueError(
                "unsupported metadata keys: {}".format(", ".join(sorted(unknown_keys)))
            )
        missing = set(mapping.values()) - set(template.EditableTexts)
        if missing:
            raise ValueError(
                "template fields not found: {}".format(", ".join(sorted(missing)))
            )
