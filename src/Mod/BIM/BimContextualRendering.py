# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local Coin rendering for renderer-independent BIM representations."""

from dataclasses import dataclass

from pivy import coin

import ArchRepresentation


def _xyz(point):
    return float(point.x), float(point.y), float(point.z)


@dataclass(frozen=True)
class ContextualNodeMapping:
    source: object
    subelement: str | None
    role: str | None
    geometry: object


class ContextualRepresentationRenderer:
    """Own contextual representation nodes in one viewer and context layer."""

    def __init__(self, view, *, replace_source=True):
        self.view = view
        self.replace_source = bool(replace_source)
        self.layer = view.pushViewContextLayer()
        self.scene = view.getSceneGraph()
        self.root = coin.SoSeparator()
        self.root.ref()
        self.scene.addChild(self.root)
        self._object_nodes = {}
        self._representations = {}
        self._node_mappings = {}
        self._hidden_sources = set()

    def set_representation(self, representation):
        """Replace one object's viewer-local representation."""

        source = representation.source
        if self._representations.get(source) is representation:
            return self._object_nodes[source]
        self.remove_representation(source, restore_visibility=False)
        root = coin.SoSwitch()
        root.whichChild = coin.SO_SWITCH_ALL
        self._append_faces(root, representation)
        self._append_lines(root, representation)
        self.root.addChild(root)
        self._object_nodes[source] = root
        self._representations[source] = representation
        self._apply_source_visibility(source)
        if self.replace_source:
            self.view.setViewVisibility(self.layer, source, "Hidden")
        return root

    def remove_representation(self, source, restore_visibility=True):
        node = self._object_nodes.pop(source, None)
        self._representations.pop(source, None)
        if node is not None:
            self.root.removeChild(node)
            stale = [key for key, value in self._node_mappings.items() if value.source is source]
            for key in stale:
                self._node_mappings.pop(key, None)
        if restore_visibility:
            self._hidden_sources.discard(source)
            if self.replace_source:
                self.view.setViewVisibility(self.layer, source, "Inherit")

    def mapping_for_node(self, node):
        return self._node_mappings.get(id(node))

    def pick_mapping(self, mouse_pos, project_point, radius_px=4):
        """Pick rendered semantic geometry through the neutral query contract."""

        if mouse_pos is None or not callable(project_point):
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

    @property
    def sources(self):
        return tuple(self._representations)

    def query_snap(self, point, tolerance, request=None):
        """Resolve a semantic snap against this viewer's live representations."""

        return ArchRepresentation.query_representation_snap(
            tuple(self._representations.values()), point, tolerance, request=request
        )

    def set_source_visible(self, source, visible):
        hidden_before = source in self._hidden_sources
        if visible:
            self._hidden_sources.discard(source)
        else:
            self._hidden_sources.add(source)
        self._apply_source_visibility(source)
        return hidden_before == bool(visible)

    def close(self):
        root = self.root
        if root is None:
            return
        try:
            self.scene.removeChild(root)
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        try:
            self.view.removeViewContextLayer(self.layer)
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        finally:
            self._object_nodes.clear()
            self._representations.clear()
            self._node_mappings.clear()
            self._hidden_sources.clear()
            root.unref()
            self.root = None

    def _record_node(self, node, representation, geometry):
        mapping = representation.mapping_for(geometry)
        if mapping is not None:
            self._node_mappings[id(node)] = ContextualNodeMapping(
                mapping.source,
                mapping.subelement,
                mapping.role,
                mapping.geometry,
            )

    def _append_faces(self, root, representation):
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
            material.diffuseColor = (0.82, 0.82, 0.82)
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
            self._record_node(group, representation, face)

    def _append_lines(self, root, representation):
        for geometry in representation.projected_geometry:
            try:
                points = [_xyz(point) for point in geometry]
            except Exception:
                continue
            if len(points) < 2:
                continue
            group = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor = (0.1, 0.1, 0.1)
            group.addChild(material)
            style = coin.SoDrawStyle()
            style.lineWidth = 2.0
            group.addChild(style)
            coordinates = coin.SoCoordinate3()
            coordinates.point.setValues(0, len(points), points)
            group.addChild(coordinates)
            lines = coin.SoLineSet()
            lines.numVertices.setValues(0, 1, [len(points)])
            group.addChild(lines)
            root.addChild(group)
            self._record_node(group, representation, geometry)

    def _apply_source_visibility(self, source):
        node = self._object_nodes.get(source)
        if node is not None:
            node.whichChild = (
                coin.SO_SWITCH_NONE if source in self._hidden_sources else coin.SO_SWITCH_ALL
            )

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
