# SPDX-License-Identifier: LGPL-2.1-or-later

"""Screen-space geometry helpers for BIM Plan Edit picking."""

import FreeCAD


def get_screen_distance_sq_to_segment(session, mouse_pos, start, end):
    if not session.view or not mouse_pos:
        return None
    try:
        cursor_x = float(mouse_pos[0])
        cursor_y = float(mouse_pos[1])
    except Exception:
        return None
    try:
        start_x = float(start.x)
        start_y = float(start.y)
        start_z = float(start.z)
        end_x = float(end.x)
        end_y = float(end.y)
        end_z = float(end.z)
    except Exception:
        return None

    projected_points = []
    for step in range(5):
        factor = float(step) / 4.0
        point = FreeCAD.Vector(
            start_x + ((end_x - start_x) * factor),
            start_y + ((end_y - start_y) * factor),
            start_z + ((end_z - start_z) * factor),
        )
        try:
            screen_x, screen_y = session.view.getPointOnScreen(point)
        except Exception:
            return None
        projected_points.append((float(screen_x), float(screen_y)))

    best_distance_sq = None
    cursor_xy = (cursor_x, cursor_y)
    for start_xy, end_xy in zip(projected_points, projected_points[1:]):
        distance_sq = get_screen_distance_sq_to_projected_segment(
            cursor_xy,
            start_xy,
            end_xy,
        )
        if distance_sq is None:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
    return best_distance_sq


def get_screen_distance_sq_to_projected_segment(cursor_xy, start_xy, end_xy):
    try:
        if cursor_xy is None or start_xy is None or end_xy is None:
            return None

        cursor_x = float(cursor_xy[0])
        cursor_y = float(cursor_xy[1])
        start_x = float(start_xy[0])
        start_y = float(start_xy[1])
        end_x = float(end_xy[0])
        end_y = float(end_xy[1])
        dx = end_x - start_x
        dy = end_y - start_y
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            proj_x = start_x
            proj_y = start_y
        else:
            t = ((cursor_x - start_x) * dx + (cursor_y - start_y) * dy) / length_sq
            t = max(0.0, min(1.0, t))
            proj_x = start_x + t * dx
            proj_y = start_y + t * dy
        offset_x = proj_x - cursor_x
        offset_y = proj_y - cursor_y
        return offset_x * offset_x + offset_y * offset_y
    except Exception:
        return None
