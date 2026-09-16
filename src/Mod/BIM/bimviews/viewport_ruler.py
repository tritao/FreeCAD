# SPDX-License-Identifier: LGPL-2.1-or-later

"""Screen-space rulers for planar BIM view contexts."""

import FreeCAD

from ArchRepresentation import RepresentationPurpose
from .ruler_model import RulerTransform, format_metric, tick_values


PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
SHOW_RULERS_PARAM = "ShowViewRulers"


def rulers_enabled():
    return PARAMS.GetBool(SHOW_RULERS_PARAM, True)


if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui

    class ViewportRulerOverlay(QtGui.QWidget):
        """Transparent input-pass-through overlay painted over a 3D viewport."""

        TOP_BAND = 28
        LEFT_BAND = 46
        MAJOR_TICK = 8
        MINOR_TICK = 4
        LABEL_GAP = 8
        BAND_COLOR = (248, 248, 246)
        LINE_COLOR = (195, 199, 202)
        TEXT_COLOR = (52, 56, 60)

        def __init__(self, host_widget, transform_provider, content_widget=None):
            super().__init__(host_widget)
            self.host_widget = host_widget
            self.content_widget = content_widget or host_widget
            self._transform_provider = transform_provider
            self.transform = None
            self.cursor_position = None
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
            self.setGeometry(host_widget.rect())
            self.show()
            self.raise_()

        def sync_geometry(self):
            self.setGeometry(self.host_widget.rect())
            self.raise_()
            self.refresh_transform()

        def refresh_transform(self):
            self.transform = self._transform_provider()
            self.update()

        def set_cursor_position(self, position):
            self.cursor_position = position
            self.update()

        def clear_cursor(self):
            if self.cursor_position is not None:
                self.cursor_position = None
                self.update()

        def paintEvent(self, _event):
            transform = self.transform
            if transform is None:
                return
            painter = QtGui.QPainter(self)
            try:
                painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
                band_color = QtGui.QColor(*self.BAND_COLOR)
                line_color = QtGui.QColor(*self.LINE_COLOR)
                text_color = QtGui.QColor(*self.TEXT_COLOR)
                painter.fillRect(0, 0, self.width(), self.TOP_BAND, band_color)
                painter.fillRect(0, 0, self.LEFT_BAND, self.height(), band_color)
                painter.setPen(line_color)
                painter.drawLine(
                    self.LEFT_BAND, self.TOP_BAND - 1, self.width(), self.TOP_BAND - 1
                )
                painter.drawLine(
                    self.LEFT_BAND - 1, self.TOP_BAND, self.LEFT_BAND - 1, self.height()
                )
                self._draw_horizontal(painter, transform, text_color, line_color)
                self._draw_vertical(painter, transform, text_color, line_color)
                self._draw_corner(painter, text_color)
                self._draw_cursor(painter, transform, text_color)
            finally:
                painter.end()

        def _draw_horizontal(self, painter, transform, text_color, line_color):
            major = transform.major_interval
            minor = transform.minor_interval
            major_values = tick_values(transform.x_left, transform.x_right, major)
            major_keys = {round(value / minor) for value in major_values}
            origin_x, _origin_y = self._content_origin()
            cursor_x = self._cursor_overlay_position()[0] if self.cursor_position else None
            cursor_rect = self._horizontal_cursor_rect(painter, transform, cursor_x)
            last_label_right = -10000
            painter.setPen(line_color)
            for value in tick_values(transform.x_left, transform.x_right, minor):
                x = origin_x + int(round(transform.pixel_for_x(value)))
                if x < self.LEFT_BAND or x > self.width():
                    continue
                is_major = round(value / minor) in major_keys
                length = self.MAJOR_TICK if is_major else self.MINOR_TICK
                painter.drawLine(x, self.TOP_BAND - 1, x, self.TOP_BAND - 1 - length)
                if is_major:
                    label = self._tick_label(value, major)
                    width = painter.fontMetrics().horizontalAdvance(label)
                    label_rect = QtCore.QRect(x + 4, 3, width + 2, self.TOP_BAND - 12)
                    if label_rect.left() <= last_label_right + self.LABEL_GAP:
                        continue
                    if cursor_rect is not None and label_rect.intersects(cursor_rect):
                        continue
                    painter.setPen(text_color)
                    painter.drawText(
                        label_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, label
                    )
                    last_label_right = label_rect.right()
                    painter.setPen(line_color)

        def _draw_vertical(self, painter, transform, text_color, line_color):
            major = transform.major_interval
            minor = transform.minor_interval
            major_values = tick_values(transform.y_top, transform.y_bottom, major)
            major_keys = {round(value / minor) for value in major_values}
            _origin_x, origin_y = self._content_origin()
            cursor_y = self._cursor_overlay_position()[1] if self.cursor_position else None
            cursor_rect = self._vertical_cursor_rect(painter, transform, cursor_y)
            last_label_bottom = -10000
            painter.setPen(line_color)
            for value in tick_values(transform.y_top, transform.y_bottom, minor):
                y = origin_y + int(round(transform.pixel_for_y(value)))
                if y < self.TOP_BAND or y > self.height():
                    continue
                is_major = round(value / minor) in major_keys
                length = self.MAJOR_TICK if is_major else self.MINOR_TICK
                painter.drawLine(self.LEFT_BAND - 1, y, self.LEFT_BAND - 1 - length, y)
                if is_major:
                    label = self._tick_label(value, major)
                    label_rect = QtCore.QRect(3, y - 9, self.LEFT_BAND - 13, 18)
                    if label_rect.top() <= last_label_bottom + 2:
                        continue
                    if cursor_rect is not None and label_rect.intersects(cursor_rect):
                        continue
                    painter.setPen(text_color)
                    painter.drawText(
                        label_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, label
                    )
                    last_label_bottom = label_rect.bottom()
                    painter.setPen(line_color)

        def _draw_corner(self, painter, color):
            painter.setPen(color)
            painter.drawText(6, 11, "X →")
            painter.drawText(6, 23, "Y ↓")
            painter.drawText(self.LEFT_BAND - 13, 18, "m")

        def _draw_cursor(self, painter, transform, color):
            if self.cursor_position is None:
                return
            x, y = self._cursor_overlay_position()
            if x < self.LEFT_BAND or y < self.TOP_BAND:
                return
            accent = self.palette().color(QtGui.QPalette.Highlight)
            painter.setPen(accent)
            top = QtGui.QPolygon(
                (QtCore.QPoint(x - 4, 1), QtCore.QPoint(x + 4, 1), QtCore.QPoint(x, 7))
            )
            left = QtGui.QPolygon(
                (QtCore.QPoint(1, y - 4), QtCore.QPoint(1, y + 4), QtCore.QPoint(7, y))
            )
            painter.setBrush(accent)
            painter.drawPolygon(top)
            painter.drawPolygon(left)
            for rect, label in (
                (
                    self._horizontal_cursor_rect(painter, transform, x),
                    self._cursor_label(transform.x_at_pixel(self.cursor_position[0])),
                ),
                (
                    self._vertical_cursor_rect(painter, transform, y),
                    self._cursor_label(transform.y_at_pixel(self.cursor_position[1])),
                ),
            ):
                painter.fillRect(rect, accent)
                painter.setPen(self.palette().color(QtGui.QPalette.HighlightedText))
                painter.drawText(rect.adjusted(5, 0, -5, 0), QtCore.Qt.AlignCenter, label)
                painter.setPen(accent)

        def _content_origin(self):
            if self.content_widget is self.host_widget:
                return 0, 0
            global_origin = self.content_widget.mapToGlobal(QtCore.QPoint(0, 0))
            point = self.mapFromGlobal(global_origin)
            return point.x(), point.y()

        def _cursor_overlay_position(self):
            x, y = self.cursor_position
            origin_x, origin_y = self._content_origin()
            return origin_x + x, origin_y + y

        @staticmethod
        def _tick_label(value, interval):
            text = format_metric(value, interval)
            return text.rsplit(" ", 1)[0]

        @staticmethod
        def _cursor_label(value):
            return format_metric(value, cursor=True).rsplit(" ", 1)[0]

        def _horizontal_cursor_rect(self, painter, transform, x):
            if x is None:
                return None
            label = self._cursor_label(transform.x_at_pixel(self.cursor_position[0]))
            width = painter.fontMetrics().horizontalAdvance(label) + 12
            left = max(self.LEFT_BAND + 2, min(x + 7, self.width() - width - 2))
            return QtCore.QRect(left, 3, width, self.TOP_BAND - 9)

        def _vertical_cursor_rect(self, painter, transform, y):
            if y is None:
                return None
            label = self._cursor_label(transform.y_at_pixel(self.cursor_position[1]))
            width = max(
                self.LEFT_BAND - 10,
                painter.fontMetrics().horizontalAdvance(label) + 12,
            )
            top = max(
                self.TOP_BAND + 2,
                min(y - 10, self.height() - 22),
            )
            return QtCore.QRect(3, top, width, 20)


    class _ViewportEventFilter(QtCore.QObject):
        def __init__(self, controller):
            super().__init__(controller.overlay)
            self.controller = controller

        def eventFilter(self, watched, event):
            event_type = event.type()
            if event_type in (QtCore.QEvent.Resize, QtCore.QEvent.Move):
                self.controller.overlay.sync_geometry()
            elif (
                watched is self.controller.host_widget
                and event_type == QtCore.QEvent.MouseMove
            ):
                pos = event.position() if hasattr(event, "position") else event.pos()
                self.controller.overlay.set_cursor_position((int(pos.x()), int(pos.y())))
            elif (
                watched is self.controller.host_widget
                and event_type == QtCore.QEvent.Leave
            ):
                self.controller.overlay.clear_cursor()
            return QtCore.QObject.eventFilter(self, watched, event)


class ViewportRulerController:
    """Own a ruler overlay for one active planar BIM view."""

    def __init__(self, session, request=None):
        self.session = session
        self.request = request
        self.host_widget = None
        self.overlay = None
        self.event_filter = None
        self.timer = None
        self._projection_key = None
        self.graphics_view = None
        self._old_viewport_margins = None

    def attach(self):
        if not FreeCAD.GuiUp or not rulers_enabled() or not self._is_plan_request():
            return False
        graphics_view = self.session.viewport.get_plan_view_widget()
        self.graphics_view = graphics_view
        self.host_widget = graphics_view.viewport() if graphics_view is not None else None
        if self.host_widget is None:
            return False
        try:
            self._old_viewport_margins = graphics_view.viewportMargins()
        except AttributeError:
            self._old_viewport_margins = QtCore.QMargins(0, 0, 0, 0)
        graphics_view.setViewportMargins(
            ViewportRulerOverlay.LEFT_BAND, ViewportRulerOverlay.TOP_BAND, 0, 0
        )
        self.host_widget.setMouseTracking(True)
        self.overlay = ViewportRulerOverlay(
            graphics_view, self._make_transform, self.host_widget
        )
        self.event_filter = _ViewportEventFilter(self)
        self.host_widget.installEventFilter(self.event_filter)
        graphics_view.installEventFilter(self.event_filter)
        self.timer = QtCore.QTimer(self.overlay)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.refresh_if_needed)
        self.timer.start()
        self.overlay.refresh_transform()
        return True

    def set_request(self, request):
        self.request = request
        visible = rulers_enabled() and self._is_plan_request()
        if self.overlay is None and visible:
            self.attach()
        elif self.overlay is not None:
            self.overlay.setVisible(visible)
            self.overlay.refresh_transform()

    def refresh_if_needed(self):
        key = self.session.viewport.get_plan_projection_cache_key()
        if key != self._projection_key:
            self._projection_key = key
            if self.overlay is not None:
                self.overlay.refresh_transform()

    def close(self):
        if self.timer is not None:
            self.timer.stop()
        if self.host_widget is not None and self.event_filter is not None:
            try:
                self.host_widget.removeEventFilter(self.event_filter)
            except RuntimeError:
                pass
        if self.graphics_view is not None and self.event_filter is not None:
            try:
                self.graphics_view.removeEventFilter(self.event_filter)
            except RuntimeError:
                pass
        if self.graphics_view is not None and self._old_viewport_margins is not None:
            margins = self._old_viewport_margins
            self.graphics_view.setViewportMargins(
                margins.left(), margins.top(), margins.right(), margins.bottom()
            )
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
        self.timer = None
        self.event_filter = None
        self.overlay = None
        self.host_widget = None
        self.graphics_view = None
        self._old_viewport_margins = None

    def _is_plan_request(self):
        return getattr(self.request, "purpose", None) == RepresentationPurpose.PLAN

    def _local_point(self, mouse_position):
        point = self.session.viewport.get_plan_point_from_mouse_pos(mouse_position)
        if point is None:
            return None
        frame = getattr(self.request, "reference_frame", None)
        if frame is None:
            source = getattr(self.request, "source", None)
            frame = getattr(source, "Placement", None)
        return frame.inverse().multVec(point) if frame is not None else point

    def _make_transform(self):
        if not self._is_plan_request() or self.host_widget is None:
            return None
        width = self.host_widget.width()
        height = self.host_widget.height()
        if width <= 0 or height <= 0:
            return None
        left = self._local_point((0, height // 2))
        right = self._local_point((width, height // 2))
        top = self._local_point((width // 2, height))
        bottom = self._local_point((width // 2, 0))
        units_per_pixel = self.session.viewport.get_plan_view_units_per_pixel()
        if any(point is None for point in (left, right, top, bottom)) or not units_per_pixel:
            return None
        return RulerTransform(
            left.x,
            right.x,
            top.y,
            bottom.y,
            float(width),
            float(height),
            float(units_per_pixel),
        )
