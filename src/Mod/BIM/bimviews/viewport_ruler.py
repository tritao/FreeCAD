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

        BAND = 24
        MAJOR_TICK = 8
        MINOR_TICK = 4

        def __init__(self, host_widget, transform_provider):
            super().__init__(host_widget)
            self.host_widget = host_widget
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
                palette = self.palette()
                band_color = palette.color(QtGui.QPalette.Base)
                band_color.setAlpha(238)
                line_color = palette.color(QtGui.QPalette.Mid)
                text_color = palette.color(QtGui.QPalette.Text)
                painter.fillRect(0, 0, self.width(), self.BAND, band_color)
                painter.fillRect(0, 0, self.BAND, self.height(), band_color)
                painter.setPen(line_color)
                painter.drawLine(self.BAND, self.BAND - 1, self.width(), self.BAND - 1)
                painter.drawLine(self.BAND - 1, self.BAND, self.BAND - 1, self.height())
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
            painter.setPen(line_color)
            for value in tick_values(transform.x_left, transform.x_right, minor):
                x = int(round(transform.pixel_for_x(value)))
                if x < self.BAND or x > self.width():
                    continue
                is_major = round(value / minor) in major_keys
                length = self.MAJOR_TICK if is_major else self.MINOR_TICK
                painter.drawLine(x, self.BAND - 1, x, self.BAND - 1 - length)
                if is_major:
                    painter.setPen(text_color)
                    painter.drawText(x + 3, self.BAND - 10, format_metric(value, major))
                    painter.setPen(line_color)

        def _draw_vertical(self, painter, transform, text_color, line_color):
            major = transform.major_interval
            minor = transform.minor_interval
            major_values = tick_values(transform.y_top, transform.y_bottom, major)
            major_keys = {round(value / minor) for value in major_values}
            painter.setPen(line_color)
            for value in tick_values(transform.y_top, transform.y_bottom, minor):
                y = int(round(transform.pixel_for_y(value)))
                if y < self.BAND or y > self.height():
                    continue
                is_major = round(value / minor) in major_keys
                length = self.MAJOR_TICK if is_major else self.MINOR_TICK
                painter.drawLine(self.BAND - 1, y, self.BAND - 1 - length, y)
                if is_major:
                    painter.save()
                    painter.setPen(text_color)
                    painter.translate(10, y - 3)
                    painter.rotate(-90)
                    painter.drawText(0, 0, format_metric(value, major))
                    painter.restore()
                    painter.setPen(line_color)

        def _draw_corner(self, painter, color):
            painter.setPen(color)
            painter.drawText(3, 10, "X")
            painter.drawText(13, 21, "Y")

        def _draw_cursor(self, painter, transform, color):
            if self.cursor_position is None:
                return
            x, y = self.cursor_position
            if x < self.BAND or y < self.BAND:
                return
            painter.setPen(color)
            top = QtGui.QPolygon(
                (QtCore.QPoint(x - 4, 1), QtCore.QPoint(x + 4, 1), QtCore.QPoint(x, 7))
            )
            left = QtGui.QPolygon(
                (QtCore.QPoint(1, y - 4), QtCore.QPoint(1, y + 4), QtCore.QPoint(7, y))
            )
            painter.setBrush(color)
            painter.drawPolygon(top)
            painter.drawPolygon(left)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawText(x + 7, 10, format_metric(transform.x_at_pixel(x), cursor=True))
            painter.save()
            painter.translate(10, y - 7)
            painter.rotate(-90)
            painter.drawText(0, 0, format_metric(transform.y_at_pixel(y), cursor=True))
            painter.restore()


    class _ViewportEventFilter(QtCore.QObject):
        def __init__(self, controller):
            super().__init__(controller.overlay)
            self.controller = controller

        def eventFilter(self, watched, event):
            event_type = event.type()
            if event_type == QtCore.QEvent.Resize:
                self.controller.overlay.sync_geometry()
            elif event_type == QtCore.QEvent.MouseMove:
                pos = event.position() if hasattr(event, "position") else event.pos()
                self.controller.overlay.set_cursor_position((int(pos.x()), int(pos.y())))
            elif event_type == QtCore.QEvent.Leave:
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

    def attach(self):
        if not FreeCAD.GuiUp or not rulers_enabled() or not self._is_plan_request():
            return False
        graphics_view = self.session.viewport.get_plan_view_widget()
        self.host_widget = graphics_view.viewport() if graphics_view is not None else None
        if self.host_widget is None:
            return False
        self.host_widget.setMouseTracking(True)
        self.overlay = ViewportRulerOverlay(self.host_widget, self._make_transform)
        self.event_filter = _ViewportEventFilter(self)
        self.host_widget.installEventFilter(self.event_filter)
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
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
        self.timer = None
        self.event_filter = None
        self.overlay = None
        self.host_widget = None

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
