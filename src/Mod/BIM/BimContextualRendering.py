# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local Coin rendering for renderer-independent BIM representations."""

from dataclasses import dataclass

import FreeCAD
from pivy import coin

import ArchRepresentation


def _xyz(point):
    return float(point.x), float(point.y), float(point.z)


def ray_from_view(view, mouse_pos):
    """Convert a viewer pixel into a normalized world-space BIM edit ray."""

    pixel = _screen_pixel_for_ray(view, mouse_pos)
    near_point, far_point = view.projectPointToLine(pixel)
    return ArchRepresentation.BIMEditRay(
        FreeCAD.Vector(near_point),
        FreeCAD.Vector(far_point).sub(FreeCAD.Vector(near_point)),
    )


def _screen_pixel_for_ray(view, mouse_pos):
    """Map projected overlay pixels to the view-volume ray coordinate system.

    FreeCAD's world-to-screen helper and camera ray helper can use slightly
    different viewport mappings. Calibrate the affine transform through the
    focal plane so an overlay point and the ray for its mouse pixel agree.
    """

    step = 1000.0

    def project_focal_pixel(pixel):
        focal_point = view.getPointOnFocalPlane(pixel)
        return view.getPointOnScreen(focal_point)

    origin = (0, 0)
    screen_origin = project_focal_pixel(origin)
    screen_x = project_focal_pixel((int(step), 0))
    screen_y = project_focal_pixel((0, int(step)))
    ax = (float(screen_x[0]) - screen_origin[0]) / step
    ay = (float(screen_y[0]) - screen_origin[0]) / step
    bx = (float(screen_x[1]) - screen_origin[1]) / step
    by = (float(screen_y[1]) - screen_origin[1]) / step
    determinant = ax * by - ay * bx
    if abs(determinant) <= 1e-10:
        return int(mouse_pos[0]), int(mouse_pos[1])

    dx = float(mouse_pos[0]) - screen_origin[0]
    dy = float(mouse_pos[1]) - screen_origin[1]
    pixel_x = (dx * by - ay * dy) / determinant
    pixel_y = (ax * dy - dx * bx) / determinant
    return round(pixel_x), round(pixel_y)


@dataclass(frozen=True)
class ContextualNodeMapping:
    source: object
    subelement: str | None
    role: str | None
    geometry: object


class ContextualRepresentationRenderer:
    """Own contextual representation nodes in one viewer and context layer."""

    def __init__(self, view, *, replace_source=True, render_representation=True):
        self.view = view
        self.replace_source = bool(replace_source)
        self.render_representation = bool(render_representation)
        self.layer = view.pushViewContextLayer()
        self.scene = view.getSceneGraph()
        self.root = coin.SoSeparator()
        self.root.ref()
        self.scene.addChild(self.root)
        self._object_nodes = {}
        self._representations = {}
        self._node_mappings = {}
        self._handle_position_fields = {}
        self._handle_color_fields = {}
        self._handle_switches = {}
        self._preview_nodes = {}
        self._visible_handle_sources = set()
        self._hidden_sources = set()

    def set_representation(self, representation):
        """Replace one object's viewer-local representation."""

        source = representation.source
        if self._representations.get(source) is representation:
            return self._object_nodes[source]
        handles_were_visible = source in self._visible_handle_sources
        self.remove_representation(source, restore_visibility=False)
        if handles_were_visible:
            self._visible_handle_sources.add(source)
        root = coin.SoSwitch()
        root.whichChild = coin.SO_SWITCH_ALL
        if self.render_representation:
            self._append_faces(root, representation)
            self._append_lines(root, representation)
        handle_switch = self._append_edit_handles(root, representation)
        if handle_switch is not None:
            self._handle_switches[source] = handle_switch
            self._apply_handle_visibility(source)
        self.root.addChild(root)
        self._object_nodes[source] = root
        self._representations[source] = representation
        self._apply_source_visibility(source)
        if self.replace_source:
            self.view.setViewVisibility(self.layer, source, "Hidden")
        return root

    def remove_representation(self, source, restore_visibility=True):
        self.clear_preview(source)
        node = self._object_nodes.pop(source, None)
        self._representations.pop(source, None)
        if node is not None:
            self.root.removeChild(node)
            stale = [key for key, value in self._node_mappings.items() if value.source is source]
            for key in stale:
                self._node_mappings.pop(key, None)
            stale_handles = [key for key in self._handle_position_fields if key[0] is source]
            for key in stale_handles:
                self._handle_position_fields.pop(key, None)
                self._handle_color_fields.pop(key, None)
            self._handle_switches.pop(source, None)
            if restore_visibility:
                self._visible_handle_sources.discard(source)
        if restore_visibility:
            self._hidden_sources.discard(source)
            if self.replace_source:
                self.view.setViewVisibility(self.layer, source, "Inherit")

    def mapping_for_node(self, node):
        return self._node_mappings.get(id(node))

    def pick_mapping(self, mouse_pos, project_point, radius_px=4):
        """Pick rendered semantic geometry through the neutral representation contract."""

        if (
            not self.render_representation
            or mouse_pos is None
            or not callable(project_point)
        ):
            return None
        result = ArchRepresentation.query_representation_pick(
            tuple(self._representations.values()),
            mouse_pos,
            project_point,
            radius_px,
        )
        if result is None:
            return None
        target = result.target
        return ContextualNodeMapping(
            target.source,
            target.subelement,
            target.role,
            target.geometry,
        )

    def pick_edit_handle(self, mouse_pos, project_point, radius_px=8):
        """Return the nearest visible semantic edit handle in screen space."""

        if mouse_pos is None or not callable(project_point):
            return None
        cursor_x, cursor_y = float(mouse_pos[0]), float(mouse_pos[1])
        tolerance_squared = float(radius_px) ** 2
        winner = None
        winner_distance = None
        for source in self._visible_handle_sources:
            representation = self._representations.get(source)
            if representation is None:
                continue
            for handle in representation.edit_handles:
                try:
                    screen_x, screen_y = project_point(handle.point)
                except Exception:
                    continue
                distance = (float(screen_x) - cursor_x) ** 2 + (float(screen_y) - cursor_y) ** 2
                if distance <= tolerance_squared and (
                    winner_distance is None or distance < winner_distance
                ):
                    winner = handle
                    winner_distance = distance
        return winner

    @property
    def sources(self):
        return tuple(self._representations)

    def query_snap(self, point, tolerance, context=None):
        """Resolve a semantic snap against this viewer's live representations."""

        return ArchRepresentation.query_representation_snap(
            tuple(self._representations.values()), point, tolerance, context=context
        )

    def edit_handles_for(self, source):
        representation = self._representations.get(source)
        if representation is None:
            return ()
        return tuple(representation.edit_handles)

    def set_visible_handle_sources(self, sources):
        """Show semantic edit handles only for the active semantic sources."""

        visible = {source for source in sources if source in self._representations}
        if visible == self._visible_handle_sources:
            return False
        affected = self._visible_handle_sources | visible
        self._visible_handle_sources = visible
        for source in affected:
            self._apply_handle_visibility(source)
        return True

    def set_source_visible(self, source, visible):
        hidden_before = source in self._hidden_sources
        if visible:
            self._hidden_sources.discard(source)
        else:
            self._hidden_sources.add(source)
        self._apply_source_visibility(source)
        return hidden_before == bool(visible)

    def close(self):
        if self.root is None:
            return
        self.clear_preview()
        self.scene.removeChild(self.root)
        self.view.removeViewContextLayer(self.layer)
        self._object_nodes.clear()
        self._representations.clear()
        self._node_mappings.clear()
        self._handle_position_fields.clear()
        self._handle_color_fields.clear()
        self._handle_switches.clear()
        self._visible_handle_sources.clear()
        self._hidden_sources.clear()
        self.root.unref()
        self.root = None

    def set_preview_shape(self, source, shape):
        """Realize one transient shape with Part's preview renderer."""

        self.clear_preview(source)
        if source is None or shape is None or shape.isNull():
            return False
        preview_type = coin.SoType.fromName("SoPreviewShape")
        if preview_type.isBad():
            raise RuntimeError("SoPreviewShape is not registered")
        view_object = getattr(source, "ViewObject", None)
        update_shape = getattr(view_object, "updatePreviewShape", None)
        if not callable(update_shape):
            raise RuntimeError("Source ViewProvider cannot tessellate preview shapes")
        node = preview_type.createInstance()
        node.ref()
        node.color = (0.12, 0.38, 0.95)
        node.transparency = 0.65
        node.lineWidth = 2.0
        update_shape(shape, node)
        self.root.addChild(node)
        self._preview_nodes[source] = node
        return True

    def set_preview_representation(self, source, representation, valid=True):
        """Realize renderer-neutral preview geometry without making it pickable."""

        self.clear_preview(source)
        if source is None or representation is None:
            return False
        node = coin.SoSeparator()
        node.ref()
        color = (0.12, 0.38, 0.95) if valid else (0.9, 0.05, 0.05)
        self._append_faces(
            node,
            representation,
            color=color,
            transparency=0.65,
            record_mappings=False,
        )
        self._append_lines(
            node,
            representation,
            color=color,
            line_width=2.0,
            record_mappings=False,
        )
        if node.getNumChildren() == 0:
            node.unref()
            return False
        self.root.addChild(node)
        self._preview_nodes[source] = node
        return True

    def clear_preview(self, source=None):
        """Remove viewer-local preview nodes without touching document state."""

        sources = tuple(self._preview_nodes) if source is None else (source,)
        changed = False
        for item in sources:
            node = self._preview_nodes.pop(item, None)
            if node is not None and self.root is not None:
                self.root.removeChild(node)
                node.unref()
                changed = True
        return changed

    def _record_node(self, node, representation, geometry):
        mapping = representation.mapping_for(geometry)
        if mapping is not None:
            self._node_mappings[id(node)] = ContextualNodeMapping(
                mapping.source,
                mapping.subelement,
                mapping.role,
                mapping.geometry,
            )

    def _append_faces(
        self,
        root,
        representation,
        *,
        color=(0.82, 0.82, 0.82),
        transparency=0.0,
        record_mappings=True,
    ):
        for face in representation.cut_geometry:
            try:
                vertices, triangles = face.tessellate(0.25)
            except Exception:
                continue
            if not vertices or not triangles:
                continue
            group = coin.SoSeparator()
            light_model = coin.SoLightModel()
            light_model.model = coin.SoLightModel.BASE_COLOR
            group.addChild(light_model)
            material = coin.SoMaterial()
            material.diffuseColor = color
            material.transparency = float(transparency)
            group.addChild(material)
            coordinates = coin.SoCoordinate3()
            coordinates.point.setValues(0, len(vertices), [_xyz(point) for point in vertices])
            group.addChild(coordinates)
            faces = coin.SoIndexedFaceSet()
            indices = []
            for triangle in triangles:
                indices.extend((*triangle, -1))
            faces.coordIndex.setValues(0, len(indices), indices)
            group.addChild(faces)
            root.addChild(group)
            if record_mappings:
                self._record_node(group, representation, face)

    def _append_lines(
        self,
        root,
        representation,
        *,
        color=(0.1, 0.1, 0.1),
        line_width=2.0,
        record_mappings=True,
    ):
        for geometry in representation.projected_geometry:
            try:
                points = [_xyz(point) for point in geometry]
            except Exception:
                continue
            if len(points) < 2:
                continue
            group = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor = color
            group.addChild(material)
            style = coin.SoDrawStyle()
            style.lineWidth = float(line_width)
            group.addChild(style)
            coordinates = coin.SoCoordinate3()
            coordinates.point.setValues(0, len(points), points)
            group.addChild(coordinates)
            lines = coin.SoLineSet()
            lines.numVertices.setValues(0, 1, [len(points)])
            group.addChild(lines)
            root.addChild(group)
            if record_mappings:
                self._record_node(group, representation, geometry)

    def _append_edit_handles(self, root, representation):
        if not representation.edit_handles:
            return None
        handle_switch = coin.SoSwitch()
        handle_switch.whichChild = coin.SO_SWITCH_NONE
        glyph_type = coin.SoType.fromName("SoFCOverlayGlyph")
        if glyph_type.isBad():
            raise RuntimeError("SoFCOverlayGlyph is not registered")
        for handle in representation.edit_handles:
            glyph = glyph_type.createInstance()
            glyph.position = _xyz(handle.point)
            glyph.color = (0.95, 0.35, 0.05)
            glyph.glyph = str(getattr(handle, "glyph", "Circle")).upper()
            glyph.size = int(getattr(handle, "glyph_size", 9))
            glyph.iconName = str(getattr(handle, "icon_name", ""))
            key = (handle.source, id(handle))
            self._handle_position_fields[key] = glyph.position
            self._handle_color_fields[key] = glyph.color
            handle_switch.addChild(glyph)
            self._node_mappings[id(glyph)] = ContextualNodeMapping(
                handle.source,
                handle.subelement,
                handle.role,
                handle,
            )
        root.addChild(handle_switch)
        return handle_switch

    def _apply_handle_visibility(self, source):
        handle_switch = self._handle_switches.get(source)
        if handle_switch is not None:
            handle_switch.whichChild = (
                coin.SO_SWITCH_ALL
                if source in self._visible_handle_sources
                else coin.SO_SWITCH_NONE
            )

    def _apply_source_visibility(self, source):
        node = self._object_nodes.get(source)
        if node is not None:
            node.whichChild = (
                coin.SO_SWITCH_NONE if source in self._hidden_sources else coin.SO_SWITCH_ALL
            )

    def preview_handle(self, handle, point):
        position = self._handle_position_fields.get((handle.source, id(handle)))
        if position is None:
            return False
        position.setValue(_xyz(point))
        return True

    def set_handle_state(self, handle, state):
        color = self._handle_color_fields.get((handle.source, id(handle)))
        if color is None:
            return False
        colors = {
            "normal": (0.95, 0.35, 0.05),
            "active": (1.0, 0.75, 0.05),
            "invalid": (0.9, 0.05, 0.05),
            "constrained": (0.5, 0.5, 0.5),
        }
        color.setValue(colors.get(str(state), colors["normal"]))
        return True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class ContextualInteractionRenderer(ContextualRepresentationRenderer):
    """Render semantic interaction overlays without replacing source objects."""

    def __init__(self, view):
        super().__init__(view, replace_source=False, render_representation=False)
