# SPDX-License-Identifier: LGPL-2.1-or-later

"""Reusable target resolution for BIM sheet commands."""


class BIMSheetTargetResolver:
    """Resolve a sheet only when the user's context is unambiguous."""

    def __init__(self, document, sheet_predicate):
        self.document = document
        self.is_sheet = sheet_predicate

    def resolve(self, *, active_page=None, selected=()):
        if self._is_document_sheet(active_page):
            return active_page
        selected_sheets = [obj for obj in selected if self._is_document_sheet(obj)]
        if len(selected_sheets) == 1:
            return selected_sheets[0]
        sheets = [obj for obj in self.document.Objects if self.is_sheet(obj)]
        return sheets[0] if len(sheets) == 1 else None

    def _is_document_sheet(self, obj):
        return (
            getattr(obj, "Document", None) is self.document
            and self.is_sheet(obj)
        )
