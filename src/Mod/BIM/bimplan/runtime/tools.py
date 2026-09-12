# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared runtime tool identifiers for BIM Plan Edit."""

from enum import Enum


class PlanTool(str, Enum):
    SELECT = "Select"
    JOIN = "Join"
    MOVE = "Move"
    MOVE_OPENING = "Move Opening"
    MOVE_SYMBOL = "Move Symbol"
    ROTATE_SYMBOL = "Rotate Symbol"
    MOVE_PROVIDER = "Move Provider"
    MOVE_WALL = "Move Wall"
    SET_SPACE_TEXT = "Set Space Text"
    WINDOW = "Window"
    REGION = "Region"
    PICK_SPACE_REGION = "Pick Space Region"
    PROVIDER_POINT = "Provider Point"
    RECT_WALL = "Rect Wall"
    SEPARATOR = "Separator"
    STRETCH_START = "Stretch Start"
    STRETCH_END = "Stretch End"

    def __str__(self):
        return self.value


def coerce_plan_tool(value):
    if isinstance(value, PlanTool) or value is None:
        return value
    try:
        return PlanTool(value)
    except ValueError:
        return value


class PlanToolHandler:
    """Minimal behavior contract for a Plan Edit tool state."""

    tool_id = None

    def __init__(self, session):
        self.session = session

    def enter(self):
        return False

    def leave(self):
        return False

    def on_mouse_move(self, mouse_pos, event_callback):
        del mouse_pos, event_callback
        return False

    def on_left_mouse_down(self, mouse_pos, event_callback):
        del mouse_pos, event_callback
        return False

    def on_key(self, key, event_callback, coin):
        del key, event_callback, coin
        return False

    def cancel(self):
        return False
