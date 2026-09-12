# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local Coin rendering for renderer-independent BIM representations."""

from dataclasses import dataclass

from pivy import coin


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

    def __init__(self, view):
        self.view = view
        self.layer = view.pushViewContextLayer()
        self.scene = view.getSceneGraph()
        self.root = coin.SoSeparator()
        self.root.ref()
        self.scene.addChild(self.root)
        self._object_nodes = {}
        self._representations = {}
        self._node_mappings = {}

    def set_representation(self, representation):
        """Replace one object's viewer-local representation."""

        source = representation.source
        if self._representations.get(source) is representation:
            return self._object_nodes[source]
        self.remove_representation(source, restore_visibility=False)
        root = coin.SoSeparator()
        self._append_faces(root, representation)
        self._append_lines(root, representation)
        self.root.addChild(root)
        self._object_nodes[source] = root
        self._representations[source] = representation
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
            self.view.setViewVisibility(self.layer, source, "Inherit")

    def mapping_for_node(self, node):
        return self._node_mappings.get(id(node))

    @property
    def sources(self):
        return tuple(self._representations)

    def close(self):
        if self.root is None:
            return
        self.scene.removeChild(self.root)
        self.view.removeViewContextLayer(self.layer)
        self._object_nodes.clear()
        self._representations.clear()
        self._node_mappings.clear()
        self.root.unref()
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

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
