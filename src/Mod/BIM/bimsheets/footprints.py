# SPDX-License-Identifier: LGPL-2.1-or-later

"""Sheet-space footprint measurement for TechDraw placements."""

from .layout import PlacementFootprint, svg_footprint
from .titles import format_scale


def _value(value):
    return float(getattr(value, "Value", value))


class BIMSheetFootprintProvider:
    """Measure a placed view and its owned title around the view anchor."""

    def for_view(
        self,
        drawing_view,
        *,
        scale=None,
        title_offset=None,
        title_size=None,
        view_number=None,
        view_title=None,
    ):
        scale = (
            float(scale)
            if scale is not None
            else drawing_view.getScale()
            if hasattr(drawing_view, "getScale")
            else 1.0
        )
        width, height = svg_footprint(
            getattr(drawing_view, "Symbol", ""), scale
        )
        result = PlacementFootprint.centered(width, height)
        annotation = self._annotation_for(drawing_view)
        if annotation is None:
            return result

        size = (
            float(title_size)
            if title_size is not None
            else _value(getattr(annotation, "TextSize", 3.5))
        )
        offset_x = _value(getattr(annotation, "OwnerOffsetX", 0.0))
        offset_y = (
            -abs(float(title_offset))
            if title_offset is not None
            else _value(getattr(annotation, "OwnerOffsetY", 0.0))
        )
        lines = self._title_lines(
            drawing_view,
            scale,
            view_number=view_number,
            view_title=view_title,
        )
        title_width = max((len(line) for line in lines), default=1) * size * 0.6
        title_height = max(len(lines), 1) * size * 1.25
        title = PlacementFootprint(
            offset_x - title_width / 2.0,
            offset_y - title_height / 2.0,
            offset_x + title_width / 2.0,
            offset_y + title_height / 2.0,
        )
        return result.union(title)

    @staticmethod
    def _annotation_for(drawing_view):
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

    @staticmethod
    def _title_lines(drawing_view, scale, *, view_number=None, view_title=None):
        number = str(
            getattr(drawing_view, "ViewNumber", "")
            if view_number is None
            else view_number
        ).strip()
        title = str(
            getattr(drawing_view, "ViewTitle", "")
            if view_title is None
            else view_title
        ).strip()
        if not title:
            definition = getattr(drawing_view, "BIMViewDefinition", None)
            title = str(
                getattr(definition, "Label", "")
                or getattr(drawing_view, "Label", "")
            ).strip()
        heading = "  ".join(value for value in (number, title) if value)
        return heading, format_scale(scale)
