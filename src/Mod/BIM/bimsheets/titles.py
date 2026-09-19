# SPDX-License-Identifier: LGPL-2.1-or-later

"""Persistent titles for saved BIM views placed on TechDraw sheets."""


def format_scale(scale):
    """Return a stable architectural scale label for a numeric scale."""

    scale = float(scale)
    if scale <= 0:
        return ""
    if scale < 1:
        return "1:{:g}".format(1.0 / scale)
    return "{:g}:1".format(scale)


class BIMSheetViewTitleService:
    """Create and query numbered title annotations for sheet placements."""

    def __init__(self, document):
        self.document = document

    def create(self, page, drawing_view, number=None):
        if drawing_view not in page.Views:
            raise ValueError("drawing_view must belong to page")
        number = str(number) if number is not None else self.next_number(page)
        self._validate_number(page, number, drawing_view)
        drawing_view.ViewNumber = number
        annotation = self.document.addObject(
            "TechDraw::DrawViewAnnotation", "BIMViewTitle"
        )
        annotation.Label = "View {} Title".format(number)
        annotation.Owner = drawing_view
        annotation.TextTemplate = [
            "{ViewNumber}  {ViewTitle|BIMViewDefinition.Label|Label}",
            "{Scale}",
        ]
        annotation.FollowOwnerPosition = True
        annotation.OwnerOffsetY = -getattr(page, "ViewTitleOffset", 12.0)
        annotation.TextSize = getattr(page, "ViewTitleTextSize", 3.5)
        font = getattr(page, "ViewTitleFont", "")
        if font:
            annotation.Font = font
        page.addView(annotation)
        annotation.touch()
        return annotation

    @staticmethod
    def annotation_for(drawing_view):
        document = getattr(drawing_view, "Document", None)
        if document is None:
            return None
        return next(
            (
                obj
                for obj in document.Objects
                if obj.isDerivedFrom("TechDraw::DrawViewAnnotation")
                and getattr(obj, "Owner", None) is drawing_view
            ),
            None,
        )

    def remove(self, drawing_view):
        annotation = self.annotation_for(drawing_view)
        if annotation is None:
            return
        page = annotation.findParentPage()
        if page is not None:
            page.removeView(annotation)
        self.document.removeObject(annotation.Name)

    def next_number(self, page):
        used = {
            int(view.ViewNumber)
            for view in page.Views
            if view.isDerivedFrom("TechDraw::DrawViewArch")
            and getattr(view, "ViewNumber", "").isdigit()
        }
        candidate = 1
        while candidate in used:
            candidate += 1
        return str(candidate)

    @staticmethod
    def _validate_number(page, number, drawing_view=None):
        if not number.strip():
            raise ValueError("view number cannot be empty")
        for view in page.Views:
            if view is drawing_view or not view.isDerivedFrom("TechDraw::DrawViewArch"):
                continue
            if getattr(view, "ViewNumber", "") == number:
                raise ValueError("view number must be unique within the sheet")
