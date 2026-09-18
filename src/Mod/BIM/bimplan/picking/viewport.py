# SPDX-License-Identifier: LGPL-2.1-or-later

"""Coin viewport-pixel boundary helpers for BIM Plan Edit picking."""

from typing import NamedTuple


class ViewportPixel(NamedTuple):
    """A position in Coin viewport/device pixels, with its origin at bottom-left."""

    x: float
    y: float


def viewport_pixel(value):
    """Normalize a two-component value to the Plan Edit pointer contract."""

    if isinstance(value, ViewportPixel):
        return value
    return ViewportPixel(float(value[0]), float(value[1]))


def coin_pixel(value):
    """Return the integral pixel pair expected by Coin and View3D pick APIs."""

    pixel = viewport_pixel(value)
    return int(round(pixel.x)), int(round(pixel.y))


def ray_pick_action(render_manager, pixel, *, radius_px, pick_all=True):
    """Run the single supported native Coin ray-pick path for Plan Edit."""

    from pivy import coin

    x, y = coin_pixel(pixel)
    action = coin.SoRayPickAction(render_manager.getViewportRegion())
    action.setPoint(coin.SbVec2s(x, y))
    action.setRadius(float(radius_px))
    action.setPickAll(bool(pick_all))
    action.apply(render_manager.getSceneGraph())
    # The action owns its picked-point list, so callers retain this object while
    # inspecting paths and details from the result.
    return action


def objects_info(view, pixel):
    """Query document objects using the same viewport-pixel contract."""

    return list(view.getObjectsInfo(coin_pixel(pixel)) or ())
