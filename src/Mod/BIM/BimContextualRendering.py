# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local Coin rendering for renderer-independent BIM representations."""

from dataclasses import dataclass

import FreeCAD
from pivy import coin

import ArchRepresentation


def _xyz(point):
    return float(point.x), float(point.y), float(point.z)


def _node_key(node):
    try:
        return int(node.getNodeId())
    except (AttributeError, RuntimeError, TypeError):
        return id(node)


def _line_appearance(representation, role, color, line_width):
    """Resolve shared line color and width for scalar and batched geometry."""

    category_widths = {
        ArchRepresentation.ProjectedLineCategory.SILHOUETTE.value: 1.35,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_HARD.value: 1.0,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_SMOOTH.value: 0.75,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_SEAM.value: 0.75,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_ISO.value: 0.6,
        "PlanHatch": 0.35,
    }
    profile = getattr(getattr(representation, "request", None), "presentation_profile", {})
    if role == ArchRepresentation.ProjectedLineCategory.SILHOUETTE.value:
        category_widths[role] = float(
            profile.get("silhouette_line_width", category_widths[role])
        )
    elif role:
        category_widths[role] = float(
            profile.get("visible_line_width", category_widths.get(role, 1.0))
        )
    resolved_color = (0.35, 0.35, 0.35) if role == "PlanHatch" else color
    return resolved_color, float(line_width) * category_widths.get(role, 1.0)


def ray_from_view(view, mouse_pos):
    """Convert a viewer pixel into a normalized world-space BIM edit ray."""

    from bimplan.picking.viewport import coin_pixel

    near_point, far_point = view.projectPointToLine(coin_pixel(mouse_pos))
    return ArchRepresentation.BIMEditRay(
        FreeCAD.Vector(near_point),
        FreeCAD.Vector(far_point).sub(FreeCAD.Vector(near_point)),
    )


@dataclass(frozen=True)
class ContextualNodeMapping:
    source: object
    subelement: str | None
    role: str | None
    geometry: object


@dataclass(frozen=True)
class _GeometryBinding:
    """Mutable Coin fields retained for one rendered semantic geometry item."""

    kind: str
    group: object
    material: object
    style: object
    coordinates: object
    primitive: object


@dataclass(frozen=True)
class _HandleBinding:
    """Retained Coin glyph for one semantic edit handle."""

    glyph: object
    handle: object


class ContextualRepresentationRenderer:
    """Own contextual representation nodes in one viewer and context layer."""

    def __init__(self, view, *, replace_source=True, render_representation=True):
        self.view = view
        self.replace_source = bool(replace_source)
        self.render_representation = bool(render_representation)
        self.layer = view.pushViewContextLayer()
        self.scene = view.getSceneGraph()
        self.root = coin.SoSwitch()
        self.root.whichChild = coin.SO_SWITCH_ALL
        self.root.ref()
        self.scene.addChild(self.root)
        self._object_nodes = {}
        self._representations = {}
        self._geometry_bindings = {}
        self._handle_bindings = {}
        self._node_mappings = {}
        self._handle_position_fields = {}
        self._handle_color_fields = {}
        self._handle_switches = {}
        self._preview_nodes = {}
        self._preview_replaced_sources = set()
        self._preview_groups = {}
        self._preview_label_nodes = {}
        self._preview_label_parts = {}
        self._visible_handle_sources = set()
        self._hidden_sources = set()
        self._deferred_footprint_sources = set()

    def _defer_source_footprint(self, source):
        if source in self._deferred_footprint_sources:
            return
        view_object = getattr(source, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object is not None else None
        defer = getattr(proxy, "deferFootprintRefresh", None)
        if callable(defer) and defer():
            self._deferred_footprint_sources.add(source)

    def _resume_source_footprint(self, source):
        if source not in self._deferred_footprint_sources:
            return
        self._deferred_footprint_sources.discard(source)
        view_object = getattr(source, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object is not None else None
        resume = getattr(proxy, "resumeFootprintRefresh", None)
        if callable(resume):
            resume(view_object)

    def set_representation(self, representation):
        """Install or update one object's viewer-local representation."""

        source = representation.source
        if self._representations.get(source) is representation:
            return self._object_nodes[source]
        if source in self._object_nodes and self._update_representation(representation):
            return self._object_nodes[source]
        handles_were_visible = source in self._visible_handle_sources
        self.remove_representation(source, restore_visibility=False)
        if handles_were_visible:
            self._visible_handle_sources.add(source)
        root = coin.SoSwitch()
        root.whichChild = coin.SO_SWITCH_ALL
        geometry_bindings = []
        if self.render_representation:
            self._append_faces(root, representation, bindings=geometry_bindings)
            self._append_lines(root, representation, bindings=geometry_bindings)
        handle_bindings = []
        handle_switch = self._append_edit_handles(
            root, representation, bindings=handle_bindings
        )
        if handle_switch is not None:
            self._handle_switches[source] = handle_switch
            self._apply_handle_visibility(source)
        self.root.addChild(root)
        self._object_nodes[source] = root
        self._representations[source] = representation
        self._geometry_bindings[source] = tuple(geometry_bindings)
        self._handle_bindings[source] = tuple(handle_bindings)
        self._apply_source_visibility(source)
        if self.replace_source:
            self.view.setViewVisibility(self.layer, source, "Hidden")
            self._defer_source_footprint(source)
        return root

    def remove_representation(self, source, restore_visibility=True):
        self._clear_preview_geometry(source)
        node = self._object_nodes.pop(source, None)
        self._representations.pop(source, None)
        self._geometry_bindings.pop(source, None)
        self._handle_bindings.pop(source, None)
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
                self._resume_source_footprint(source)
                self.view.setViewVisibility(self.layer, source, "Inherit")

    def mapping_for_node(self, node):
        return self._node_mappings.get(_node_key(node))

    def pick_mapping(self, mouse_pos, project_point, radius_px=4):
        """Pick rendered semantic geometry through the neutral representation contract."""

        if not self.render_representation or mouse_pos is None or not callable(project_point):
            return None
        mapping = self._ray_pick_mapping(mouse_pos, radius_px)
        if mapping is not None:
            return mapping
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

    def _ray_pick_mapping(self, mouse_pos, radius_px):
        """Resolve identity from the exact Coin node visible under the cursor."""

        try:
            from bimplan.picking.viewport import ray_pick_action

            render_manager = self.view.getViewer().getSoRenderManager()
            action = ray_pick_action(render_manager, mouse_pos, radius_px=radius_px)
            for picked_point in action.getPickedPointList():
                path = picked_point.getPath()
                for index in range(path.getLength() - 1, -1, -1):
                    mapping = self._node_mappings.get(_node_key(path.getNode(index)))
                    if mapping is not None:
                        return mapping
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            return None
        return None

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

    def representation_for(self, source):
        """Return the currently installed representation for *source*."""

        return self._representations.get(source)

    def query_snap(self, point, tolerance, request=None):
        """Resolve a semantic snap against this viewer's live representations."""

        return ArchRepresentation.query_representation_snap(
            tuple(self._representations.values()), point, tolerance, request=request
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

    def suspend(self):
        """Hide this retained layer and reveal its document sources."""

        if self.root is None:
            return False
        self.clear_preview()
        self.set_visible_handle_sources(())
        self.root.whichChild = coin.SO_SWITCH_NONE
        if self.replace_source:
            for source in self._representations:
                self._resume_source_footprint(source)
                self.view.setViewVisibility(self.layer, source, "Inherit")
        return True

    def resume(self):
        """Show this retained layer and replace its document sources."""

        if self.root is None:
            return False
        self.root.whichChild = coin.SO_SWITCH_ALL
        if self.replace_source:
            for source in self._representations:
                self.view.setViewVisibility(self.layer, source, "Hidden")
                self._defer_source_footprint(source)
        return True

    def close(self):
        root = self.root
        if root is None:
            return
        try:
            self.clear_preview()
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        for source in tuple(self._deferred_footprint_sources):
            self._resume_source_footprint(source)
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
            self._geometry_bindings.clear()
            self._handle_bindings.clear()
            self._node_mappings.clear()
            self._handle_position_fields.clear()
            self._handle_color_fields.clear()
            self._handle_switches.clear()
            self._preview_nodes.clear()
            self._preview_label_nodes.clear()
            self._preview_label_parts.clear()
            self._preview_replaced_sources.clear()
            self._preview_groups.clear()
            self._visible_handle_sources.clear()
            self._hidden_sources.clear()
            self._deferred_footprint_sources.clear()
            root.unref()
            self.root = None

    def set_preview_state(self, state, valid=True):
        """Atomically realize all representations belonging to one edit state."""

        self._clear_preview_geometry()
        styles = {
            ArchRepresentation.BIMPreviewStyle.AVAILABLE: ((0.12, 0.38, 0.95), 0.65, 2.0),
            ArchRepresentation.BIMPreviewStyle.EMPHASIZED: ((0.90, 0.42, 0.05), 0.42, 3.0),
            ArchRepresentation.BIMPreviewStyle.MUTED: ((0.45, 0.45, 0.45), 0.78, 1.5),
            ArchRepresentation.BIMPreviewStyle.INVALID: ((0.9, 0.05, 0.05), 0.65, 2.0),
        }
        pending = []
        for entry in state.entries:
            representation = entry.representation
            replace_committed = entry.replace_committed
            source = representation.source
            node = coin.SoSeparator()
            node.ref()
            color, transparency, line_width = styles.get(
                entry.style,
                styles[ArchRepresentation.BIMPreviewStyle.AVAILABLE],
            )
            if not valid:
                color, transparency, line_width = styles[ArchRepresentation.BIMPreviewStyle.INVALID]
            entry_color = (0.82, 0.82, 0.82) if replace_committed and valid else color
            entry_transparency = 0.0 if replace_committed and valid else transparency
            self._append_faces(
                node,
                representation,
                color=entry_color,
                transparency=entry_transparency,
                record_mappings=False,
            )
            self._append_lines(
                node,
                representation,
                color=(0.08, 0.08, 0.08) if replace_committed and valid else color,
                line_width=line_width,
                record_mappings=False,
            )
            if node.getNumChildren() == 0:
                node.unref()
                continue
            pending.append((source, node, replace_committed))
        for source, node, replace_committed in pending:
            if valid and replace_committed and source in self._object_nodes:
                self._object_nodes[source].whichChild = coin.SO_SWITCH_NONE
                self._preview_replaced_sources.add(source)
            self.root.addChild(node)
            self._preview_nodes[source] = node
        if pending:
            self._preview_groups[state.primary_source] = tuple(item[0] for item in pending)
        return bool(pending)

    def set_edit_label(self, source, text, point, valid=True):
        """Show one viewer-local constant-pixel measurement label."""

        if source is None or not text:
            self.clear_edit_label(source)
            return False
        parts = self._preview_label_parts.get(source)
        if parts is None:
            label_type = coin.SoType.fromName("SoFrameLabel")
            if label_type.isBad():
                raise RuntimeError("SoFrameLabel is not registered")
            node = coin.SoAnnotation()
            node.ref()
            pick_style = coin.SoPickStyle()
            pick_style.style = coin.SoPickStyle.UNPICKABLE
            translation = coin.SoTranslation()
            label = label_type.createInstance()
            label.horAlignment = coin.SoImage.CENTER
            label.vertAlignment = coin.SoImage.HALF
            label.justification = 2
            label.pixelOffset.setValue(0, -18)
            label.backgroundOpacity = 0.9
            node.addChild(pick_style)
            node.addChild(translation)
            node.addChild(label)
            self.root.addChild(node)
            self._preview_label_nodes[source] = node
            self._preview_label_parts[source] = (translation, label)
            parts = (translation, label)
        translation, label = parts
        translation.translation = _xyz(point)
        label.string.setValue(str(text))
        label.borderColor = (0.95, 0.35, 0.05) if valid else (0.9, 0.05, 0.05)
        label.backgroundColor = (0.12, 0.12, 0.12) if valid else (0.28, 0.02, 0.02)
        return True

    def clear_edit_label(self, source=None):
        targets = (
            tuple(self._preview_label_nodes)
            if source is None
            else ((source,) if source in self._preview_label_nodes else ())
        )
        for target in targets:
            node = self._preview_label_nodes.pop(target, None)
            self._preview_label_parts.pop(target, None)
            if node is not None:
                if self.root is not None:
                    self.root.removeChild(node)
                node.unref()

    def clear_preview(self, source=None):
        """Remove viewer-local preview nodes without touching document state."""

        self.clear_edit_label(source)
        return self._clear_preview_geometry(source)

    def _clear_preview_geometry(self, source=None):
        """Remove preview geometry while retaining any live edit label."""

        sources = (
            tuple(self._preview_nodes)
            if source is None
            else self._preview_groups.pop(source, (source,))
        )
        if source is None:
            self._preview_groups.clear()
        changed = False
        for item in sources:
            node = self._preview_nodes.pop(item, None)
            if node is not None and self.root is not None:
                self.root.removeChild(node)
                node.unref()
                changed = True
        restore = tuple(item for item in sources if item in self._preview_replaced_sources)
        for item in restore:
            node = self._object_nodes.get(item)
            if node is not None:
                node.whichChild = coin.SO_SWITCH_ALL
            self._preview_replaced_sources.discard(item)
        return changed

    def _record_node(self, node, representation, geometry):
        mapping = representation.mapping_for(geometry)
        if mapping is not None:
            self._node_mappings[_node_key(node)] = ContextualNodeMapping(
                mapping.source,
                mapping.subelement,
                mapping.role,
                mapping.geometry,
            )

    @staticmethod
    def _set_values(field, values):
        """Replace an SoMField value without retaining a stale trailing range."""

        field.setNum(len(values))
        if values:
            field.setValues(0, len(values), values)

    def _representation_payloads(self, representation):
        """Return normalized payloads in the same order as the Coin subtree."""

        payloads = []
        for face in representation.cut_geometry:
            try:
                mesh = representation.face_mesh_for(face)
                vertices, triangles = mesh.vertices, mesh.triangles
            except Exception:
                continue
            if not vertices or not triangles:
                continue
            indices = []
            for triangle in triangles:
                indices.extend((*triangle, -1))
            payloads.append(
                ("face", face, [_xyz(point) for point in vertices], indices, None)
            )
        for geometry in representation.projected_geometry:
            if isinstance(geometry, ArchRepresentation.BIMLineBatch):
                if not geometry.vertices or not geometry.segments:
                    continue
                indices = []
                for first, second in geometry.segments:
                    indices.extend((first, second, -1))
                payloads.append(
                    (
                        "line_batch",
                        geometry,
                        [_xyz(point) for point in geometry.vertices],
                        indices,
                        None,
                    )
                )
                continue
            try:
                points = [_xyz(point) for point in geometry]
            except Exception:
                continue
            if len(points) >= 2:
                payloads.append(("line", geometry, points, None, [len(points)]))
        return payloads

    def _update_representation(self, representation):
        """Update a structurally compatible source without replacing its subtree."""

        source = representation.source
        bindings = self._geometry_bindings.get(source, ())
        payloads = (
            self._representation_payloads(representation)
            if self.render_representation
            else []
        )
        handles = tuple(representation.edit_handles)
        handle_bindings = self._handle_bindings.get(source, ())
        if (
            len(bindings) != len(payloads)
            or any(
                binding.kind != payload[0]
                for binding, payload in zip(bindings, payloads)
            )
        ):
            return False

        self._clear_preview_geometry(source)
        for binding, (_, geometry, points, indices, vertex_counts) in zip(
            bindings, payloads
        ):
            self._set_values(binding.coordinates.point, points)
            if indices is not None:
                self._set_values(binding.primitive.coordIndex, indices)
            else:
                self._set_values(binding.primitive.numVertices, vertex_counts)
            mapping = representation.mapping_for(geometry)
            role = getattr(mapping, "role", None)
            if binding.style is not None:
                color, width = _line_appearance(
                    representation, role, (0.1, 0.1, 0.1), 2.0
                )
                binding.material.diffuseColor = color
                binding.style.lineWidth = width
            self._node_mappings.pop(_node_key(binding.group), None)
            self._record_node(binding.group, representation, geometry)

        if len(handle_bindings) == len(handles):
            self._update_handle_bindings(source, handle_bindings, handles)
        else:
            self._replace_handle_bindings(source, representation)
        self._representations[source] = representation
        self._apply_source_visibility(source)
        self._apply_handle_visibility(source)
        return True

    def _update_handle_bindings(self, source, bindings, handles):
        for binding, handle in zip(bindings, handles):
            old_handle = binding.handle
            self._handle_position_fields.pop((old_handle.source, id(old_handle)), None)
            self._handle_color_fields.pop((old_handle.source, id(old_handle)), None)
            glyph = binding.glyph
            glyph.position = _xyz(handle.point)
            glyph.color = (0.95, 0.35, 0.05)
            glyph.glyph = str(getattr(handle, "glyph", "Circle")).upper()
            glyph.size = int(getattr(handle, "glyph_size", 9))
            glyph.iconName = str(getattr(handle, "icon_name", ""))
            self._handle_position_fields[(handle.source, id(handle))] = glyph.position
            self._handle_color_fields[(handle.source, id(handle))] = glyph.color
            self._node_mappings[_node_key(glyph)] = ContextualNodeMapping(
                handle.source, handle.subelement, handle.role, handle
            )
        self._handle_bindings[source] = tuple(
            _HandleBinding(binding.glyph, handle)
            for binding, handle in zip(bindings, handles)
        )

    def _replace_handle_bindings(self, source, representation):
        """Rebuild only handles when their semantic structure has changed."""

        root = self._object_nodes[source]
        old_switch = self._handle_switches.pop(source, None)
        for binding in self._handle_bindings.pop(source, ()):
            handle = binding.handle
            self._handle_position_fields.pop((handle.source, id(handle)), None)
            self._handle_color_fields.pop((handle.source, id(handle)), None)
            self._node_mappings.pop(_node_key(binding.glyph), None)
        if old_switch is not None:
            root.removeChild(old_switch)
        bindings = []
        handle_switch = self._append_edit_handles(
            root, representation, bindings=bindings
        )
        self._handle_bindings[source] = tuple(bindings)
        if handle_switch is not None:
            self._handle_switches[source] = handle_switch

    def _append_faces(
        self,
        root,
        representation,
        *,
        color=(0.82, 0.82, 0.82),
        transparency=0.0,
        record_mappings=True,
        bindings=None,
    ):
        for face in representation.cut_geometry:
            try:
                mesh = representation.face_mesh_for(face)
                vertices, triangles = mesh.vertices, mesh.triangles
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
            if bindings is not None:
                bindings.append(
                    _GeometryBinding("face", group, material, None, coordinates, faces)
                )
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
        bindings=None,
    ):
        for geometry in representation.projected_geometry:
            if isinstance(geometry, ArchRepresentation.BIMLineBatch):
                self._append_line_batch(
                    root,
                    representation,
                    geometry,
                    color=color,
                    line_width=line_width,
                    record_mappings=record_mappings,
                    bindings=bindings,
                )
                continue
            try:
                points = [_xyz(point) for point in geometry]
            except Exception:
                continue
            if len(points) < 2:
                continue
            group = coin.SoSeparator()
            mapping = representation.mapping_for(geometry)
            role = getattr(mapping, "role", None)
            resolved_color, resolved_width = _line_appearance(
                representation, role, color, line_width
            )
            material = coin.SoMaterial()
            material.diffuseColor = resolved_color
            group.addChild(material)
            style = coin.SoDrawStyle()
            style.lineWidth = resolved_width
            group.addChild(style)
            coordinates = coin.SoCoordinate3()
            coordinates.point.setValues(0, len(points), points)
            group.addChild(coordinates)
            lines = coin.SoLineSet()
            lines.numVertices.setValues(0, 1, [len(points)])
            group.addChild(lines)
            root.addChild(group)
            if bindings is not None:
                bindings.append(
                    _GeometryBinding(
                        "line", group, material, style, coordinates, lines
                    )
                )
            if record_mappings:
                self._record_node(group, representation, geometry)

    def _append_line_batch(
        self,
        root,
        representation,
        geometry,
        *,
        color,
        line_width,
        record_mappings,
        bindings=None,
    ):
        """Render one semantic line batch through a single Coin node group."""

        if not geometry.vertices or not geometry.segments:
            return
        mapping = representation.mapping_for(geometry)
        role = getattr(mapping, "role", None)
        resolved_color, resolved_width = _line_appearance(
            representation, role, color, line_width
        )
        group = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor = resolved_color
        group.addChild(material)
        style = coin.SoDrawStyle()
        style.lineWidth = resolved_width
        group.addChild(style)
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(
            0, len(geometry.vertices), [_xyz(point) for point in geometry.vertices]
        )
        group.addChild(coordinates)
        lines = coin.SoIndexedLineSet()
        indices = []
        for first, second in geometry.segments:
            indices.extend((first, second, -1))
        lines.coordIndex.setValues(0, len(indices), indices)
        group.addChild(lines)
        root.addChild(group)
        if bindings is not None:
            bindings.append(
                _GeometryBinding(
                    "line_batch", group, material, style, coordinates, lines
                )
            )
        if record_mappings:
            self._record_node(group, representation, geometry)

    def _append_edit_handles(self, root, representation, bindings=None):
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
            if bindings is not None:
                bindings.append(_HandleBinding(glyph, handle))
            self._node_mappings[_node_key(glyph)] = ContextualNodeMapping(
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
