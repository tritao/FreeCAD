# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document model presented by the BIM Navigator UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SavedViewGroup:
    """One stable UI group of saved view definitions."""

    key: str
    label: str
    views: tuple


class BIMViewManagerModel:
    """Query BIM navigation data without depending on Qt widgets."""

    _GROUPS = (
        ("Plan", "Floor Plans"),
        ("Model", "3D Views"),
        ("Section", "Sections"),
        ("Elevation", "Elevations"),
    )

    def __init__(self, document, legacy_view_predicate=None):
        self.document = document
        self._legacy_view_predicate = legacy_view_predicate or (lambda _obj: False)

    @staticmethod
    def is_saved_view(obj):
        return bool(obj and obj.isDerivedFrom("App::ViewDefinition"))

    def saved_views(self):
        return tuple(obj for obj in self.document.Objects if self.is_saved_view(obj))

    def saved_view_groups(self):
        grouped = {purpose: [] for purpose, _label in self._GROUPS}
        for view in self.saved_views():
            purpose = str(getattr(view, "Purpose", "") or "Model").strip().title()
            grouped.setdefault(purpose, []).append(view)
        result = []
        for purpose, label in self._GROUPS:
            views = tuple(sorted(grouped[purpose], key=lambda obj: obj.Label.casefold()))
            if views:
                result.append(SavedViewGroup(purpose, label, views))
        return tuple(result)

    def pages(self):
        return tuple(
            obj
            for obj in self.document.Objects
            if obj.isDerivedFrom("TechDraw::DrawPage")
        )

    def legacy_views(self):
        views = []
        for page in self.pages():
            for draw_view in getattr(page, "Views", ()):
                source = getattr(draw_view, "Source", None)
                if source is not None and source not in views:
                    views.append(source)
        for obj in self.document.Objects:
            if self._legacy_view_predicate(obj) and obj not in views:
                views.append(obj)
        return tuple(views)
