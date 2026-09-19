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

    GAP_PROPERTY = "BIMTitleGap"

    def __init__(self, document):
        self.document = document

    def create(self, page, drawing_view, number=None):
        if drawing_view not in page.Views:
            raise ValueError("drawing_view must belong to page")
        number = str(number) if number is not None else self.next_number(page)
        self.validate_number(page, number, drawing_view)
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
        annotation.addProperty(
            "App::PropertyLength",
            self.GAP_PROPERTY,
            "BIM Sheet",
            "Clear spacing between the drawing geometry and its title",
        )
        annotation.BIMTitleGap = getattr(page, "ViewTitleOffset", 12.0)
        annotation.FollowOwnerPosition = True
        annotation.OwnerOffsetY = -annotation.BIMTitleGap
        annotation.TextSize = getattr(page, "ViewTitleTextSize", 3.5)
        font = getattr(page, "ViewTitleFont", "")
        if font:
            annotation.Font = font
        page.addView(annotation)
        annotation.touch()
        return annotation

    @classmethod
    def position_below_view(cls, drawing_view):
        """Place the owned title below the rendered drawing geometry."""

        from .layout import svg_footprint

        annotation = cls.annotation_for(drawing_view)
        if annotation is None:
            return None
        scale = (
            drawing_view.getScale()
            if hasattr(drawing_view, "getScale")
            else float(drawing_view.Scale)
        )
        _width, height = svg_footprint(
            getattr(drawing_view, "Symbol", ""), scale
        )
        line_count = max(
            len(getattr(annotation, "Text", ())),
            len(getattr(annotation, "TextTemplate", ())),
            1,
        )
        title_height = line_count * annotation.TextSize.Value * 1.25
        gap = getattr(annotation, cls.GAP_PROPERTY).Value
        annotation.OwnerOffsetY = -height / 2.0 - gap - title_height / 2.0
        return cls.synchronize_position(annotation)

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

    @staticmethod
    def synchronize_position(annotation):
        """Request native owner-relative position synchronization."""

        owner = getattr(annotation, "Owner", None)
        if owner is None or not getattr(annotation, "FollowOwnerPosition", False):
            return annotation
        annotation.touch()
        return annotation

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
    def validate_number(page, number, drawing_view=None):
        """Require a non-empty placement number unique within one sheet."""

        if not number.strip():
            raise ValueError("view number cannot be empty")
        for view in page.Views:
            if view is drawing_view or not view.isDerivedFrom("TechDraw::DrawViewArch"):
                continue
            if getattr(view, "ViewNumber", "") == number:
                raise ValueError("view number must be unique within the sheet")
