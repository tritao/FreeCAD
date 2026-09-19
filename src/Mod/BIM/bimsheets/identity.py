# SPDX-License-Identifier: LGPL-2.1-or-later

"""Stable user-facing identity and numbering for BIM drawing sheets."""

import re


class BIMSheetIdentityService:
    """Allocate discipline numbers and format sheet labels consistently."""

    UNTITLED_TITLE = "Untitled Sheet"
    DISCIPLINE_PREFIXES = {
        "General": "G",
        "Architectural": "A",
        "Structural": "S",
        "Mechanical": "M",
        "Electrical": "E",
        "Plumbing": "P",
        "Civil": "C",
        "Landscape": "L",
    }

    def __init__(self, document, sheet_predicate):
        self.document = document
        self.is_sheet = sheet_predicate

    def next_number(self, discipline="General"):
        """Return the first available three-digit number for a discipline."""

        prefix = self.DISCIPLINE_PREFIXES.get(str(discipline), "G")
        pattern = re.compile(r"^{}-(\d+)$".format(re.escape(prefix)))
        used = {
            int(match.group(1))
            for obj in self.document.Objects
            if self.is_sheet(obj)
            for match in (pattern.match(str(getattr(obj, "SheetNumber", "")).strip()),)
            if match is not None
        }
        candidate = 1
        while candidate in used:
            candidate += 1
        return "{}-{:03d}".format(prefix, candidate)

    @classmethod
    def display_label(cls, number, title):
        number = str(number).strip()
        title = str(title).strip() or cls.UNTITLED_TITLE
        return "{} — {}".format(number, title) if number else title
