# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Semantic BIM Library asset helpers.

This module is intentionally narrow. It extracts asset descriptors and routes
library definition handling through small provider objects so the BIM Library
does not need to hard-code every asset kind directly in its UI task panel.
"""

import os

import FreeCAD

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


class AssetDescriptor(dict):
    """Mapping-backed asset descriptor used by BIM Library providers."""


def normalize_asset_kind(kind):

    key = "".join(char.lower() for char in str(kind or "") if char.isalnum())
    if key in {"equipment", "furniture", "furnishingelement", "furnishing"}:
        return "equipment"
    return key


def coerce_asset_vector(value):

    if isinstance(value, FreeCAD.Vector):
        return FreeCAD.Vector(value.x, value.y, value.z)
    if isinstance(value, dict):
        try:
            return FreeCAD.Vector(
                float(value.get("x", 0.0)),
                float(value.get("y", 0.0)),
                float(value.get("z", 0.0)),
            )
        except Exception:
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return FreeCAD.Vector(
                float(value[0]),
                float(value[1]),
                float(value[2]) if len(value) > 2 else 0.0,
            )
        except Exception:
            return None
    if isinstance(value, str):
        try:
            parts = [float(part.strip()) for part in value.split(",")]
        except Exception:
            return None
        if len(parts) >= 2:
            return FreeCAD.Vector(parts[0], parts[1], parts[2] if len(parts) > 2 else 0.0)
    return None


def get_asset_manifest_path(path, asset_manifest="asset.json"):

    if not path:
        return None
    if os.path.basename(path).lower() == asset_manifest and os.path.isfile(path):
        return path
    candidate = os.path.join(os.path.dirname(path), asset_manifest)
    if os.path.isfile(candidate):
        return candidate
    return None


def get_asset_representation_data(manifest, primary_key, aliases=()):

    representations = manifest.get("representations", {})
    for key in (primary_key,) + tuple(aliases):
        if key in representations:
            return representations[key]
    for key in (primary_key,) + tuple(aliases):
        if key in manifest:
            return manifest[key]
    return None


def get_asset_representation_path(manifest_path, representation):

    if isinstance(representation, str):
        relpath = representation
    elif isinstance(representation, dict):
        relpath = representation.get("file") or representation.get("path")
    else:
        relpath = None
    if not relpath:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(manifest_path), relpath))


def get_asset_representation_root_name(representation):

    if isinstance(representation, dict):
        return representation.get("root") or representation.get("object")
    return None


def get_asset_plan_contract(manifest, plan_representation=None):

    plan_data = manifest.get("plan", {})
    if not isinstance(plan_data, dict):
        plan_data = {}
    rep_data = plan_representation if isinstance(plan_representation, dict) else {}

    anchor = coerce_asset_vector(
        rep_data.get("anchor")
        or rep_data.get("insertion")
        or plan_data.get("anchor")
        or plan_data.get("insertion")
    )
    facing = coerce_asset_vector(
        rep_data.get("facing")
        or rep_data.get("forward")
        or plan_data.get("facing")
        or plan_data.get("forward")
    )
    return anchor, facing


def get_asset_kind(manifest):

    kind = normalize_asset_kind(manifest.get("kind") or manifest.get("type"))
    if kind:
        return kind

    category = str(manifest.get("category", "") or "").strip().lower()
    if category.startswith("furniture/"):
        return "equipment"

    tags = manifest.get("tags", [])
    if isinstance(tags, (list, tuple, set)):
        normalized_tags = {normalize_asset_kind(tag) for tag in tags}
        if "equipment" in normalized_tags:
            return "equipment"
        if "furniture" in normalized_tags:
            return "equipment"

    return ""


def build_asset_descriptor(
    path,
    clean_path,
    load_manifest,
    get_asset_label,
    asset_manifest="asset.json",
):

    manifest_path = get_asset_manifest_path(path, asset_manifest=asset_manifest)
    if not manifest_path:
        label = os.path.splitext(os.path.basename(path))[0]
        source_path = clean_path(path)
        return AssetDescriptor(
            label=label,
            asset_id=source_path,
            source_path=source_path,
            variant_key="",
            kind="",
            provider_key="static",
            model_path=path,
            model_root=None,
            plan_path=None,
            plan_root=None,
            plan_anchor=None,
            plan_facing=None,
            parameters={},
        )

    manifest = load_manifest(manifest_path)
    model_data = get_asset_representation_data(manifest, "model3d", aliases=("model",))
    plan_data = get_asset_representation_data(
        manifest,
        "plan2d",
        aliases=("plan", "symbol2d", "footprint"),
    )
    plan_anchor, plan_facing = get_asset_plan_contract(manifest, plan_data)
    model_path = get_asset_representation_path(manifest_path, model_data) or path
    kind = get_asset_kind(manifest)
    asset_id = manifest.get("id") or clean_path(manifest_path)
    return AssetDescriptor(
        label=get_asset_label(manifest_path),
        asset_id=asset_id,
        source_path=asset_id,
        variant_key="",
        kind=kind,
        provider_key="equipment" if kind == "equipment" else "static",
        model_path=model_path,
        model_root=get_asset_representation_root_name(model_data),
        plan_path=get_asset_representation_path(manifest_path, plan_data),
        plan_root=get_asset_representation_root_name(plan_data),
        plan_anchor=plan_anchor,
        plan_facing=plan_facing,
        parameters={},
    )


def get_object_type(obj):

    proxy_type = getattr(getattr(obj, "Proxy", None), "Type", "")
    if proxy_type:
        return proxy_type
    try:
        import Draft

        draft_type = Draft.getType(obj)
    except Exception:
        draft_type = ""
    if draft_type:
        return draft_type
    return getattr(obj, "TypeId", "")


def is_equipment_object(obj):

    return get_object_type(obj) == "Equipment"


def ensure_equipment_plan_symbol_property(obj):

    if not is_equipment_object(obj):
        return False
    if "PlanSymbols" not in getattr(obj, "PropertiesList", []):
        obj.addProperty(
            "App::PropertyLinkList",
            "PlanSymbols",
            "Equipment",
            QT_TRANSLATE_NOOP(
                "App::Property", "Optional authored 2D plan symbol objects for this equipment"
            ),
        )
    return True


def get_object_plan_anchor(obj):

    if not obj:
        return FreeCAD.Vector()
    if is_equipment_object(obj):
        try:
            import ArchEquipment

            return ArchEquipment.get_plan_anchor(obj)
        except Exception:
            pass
    return coerce_asset_vector(getattr(obj, "PlanAnchor", None)) or FreeCAD.Vector()


def get_object_plan_facing(obj):

    if not obj:
        return FreeCAD.Vector(1, 0, 0)
    if is_equipment_object(obj):
        try:
            import ArchEquipment

            return ArchEquipment.get_plan_facing(obj)
        except Exception:
            pass
    facing = coerce_asset_vector(getattr(obj, "PlanFacing", None))
    if facing is None:
        return FreeCAD.Vector(1, 0, 0)
    facing.z = 0
    if facing.Length < 1e-9:
        return FreeCAD.Vector(1, 0, 0)
    facing.normalize()
    return facing


def _copy_plan_shape_with_local_placement(shape, placement=None):

    if not shape or shape.isNull():
        return None
    copied_shape = shape.copy()
    if placement is None:
        return copied_shape
    try:
        copied_shape.Placement = placement.multiply(copied_shape.Placement)
    except Exception:
        pass
    return copied_shape


def _compose_preview_placement(parent_placement=None, local_placement=None):

    if parent_placement is None:
        parent_placement = FreeCAD.Placement()
    if local_placement is None:
        return FreeCAD.Placement(parent_placement)
    try:
        return parent_placement.multiply(local_placement)
    except Exception:
        try:
            return FreeCAD.Placement(local_placement)
        except Exception:
            return FreeCAD.Placement(parent_placement)


def _append_object_shapes(obj, shapes, parent_placement=None):

    placement = _compose_preview_placement(parent_placement, getattr(obj, "Placement", None))
    shape = getattr(obj, "Shape", None)
    if shape and not shape.isNull():
        preview_shape = _copy_plan_shape_with_local_placement(shape, placement=placement)
        if preview_shape and not preview_shape.isNull():
            shapes.append(preview_shape)
        return

    for child in getattr(obj, "OutList", []) or []:
        _append_object_shapes(child, shapes, parent_placement=placement)


def get_object_plan_shapes(obj):

    if not obj:
        return []
    try:
        import ArchEquipment

        shapes = list(ArchEquipment.get_plan_representation_shapes(obj))
        if shapes:
            return shapes
    except Exception:
        pass

    base_z = None
    base_shape = getattr(obj, "Shape", None)
    if base_shape and not base_shape.isNull():
        base_z = base_shape.BoundBox.ZMin

    shapes = []
    for plan_obj in getattr(obj, "PlanSymbols", []) or []:
        plan_shapes = []
        _append_object_shapes(plan_obj, plan_shapes)
        for shape in plan_shapes:
            if base_z is not None and abs(shape.BoundBox.ZMin - base_z) > 0.001:
                shape.translate(FreeCAD.Vector(0, 0, base_z - shape.BoundBox.ZMin))
            shapes.append(shape)
    return shapes


class BaseAssetProvider:
    key = "static"

    def apply_plan_contract(self, definition_obj, asset_descriptor):

        return False

    def attach_plan_symbol_roots(self, definition_roots, plan_roots):

        return False

    def normalize_definition_roots(self, panel, doc, asset_group, asset_descriptor, root_objects):

        return root_objects

    def create_shape_symbol_definitions(self, panel, doc, asset_group, asset_descriptor):

        import Part

        panel._ensure_active_document(doc)
        obj = doc.addObject("Part::Feature", "LibraryShape")
        obj.Shape = Part.read(asset_descriptor["model_path"])
        obj.Label = asset_descriptor["label"]
        panel._ensure_library_metadata(
            obj, getattr(asset_group, "LibrarySourcePath", ""), role="instance"
        )
        panel._remove_from_parent_groups(obj)
        asset_group.addObject(obj)
        panel._set_definition_view_state(obj)
        doc.recompute()
        return [obj]

    def create_instance(self, panel, doc, definition_obj):

        link = doc.addObject("App::Link", "Link")
        link.setLink(definition_obj)
        link.Label = panel._next_instance_label(doc, definition_obj.Label)
        return link


class EquipmentAssetProvider(BaseAssetProvider):
    key = "equipment"

    def apply_plan_contract(self, definition_obj, asset_descriptor):

        if not definition_obj:
            return False
        anchor = asset_descriptor.get("plan_anchor")
        facing = asset_descriptor.get("plan_facing")
        if anchor is None and facing is None:
            return False
        try:
            import ArchEquipment

            return bool(
                ArchEquipment.apply_plan_contract(definition_obj, anchor=anchor, facing=facing)
            )
        except Exception:
            return False

    def attach_plan_symbol_roots(self, definition_roots, plan_roots):

        changed = False
        if not plan_roots:
            return changed
        for definition_obj in definition_roots:
            if not ensure_equipment_plan_symbol_property(definition_obj):
                continue
            plan_symbols = [plan_root for plan_root in plan_roots if plan_root != definition_obj]
            current_symbols = list(getattr(definition_obj, "PlanSymbols", []) or [])
            if current_symbols == plan_symbols:
                continue
            definition_obj.PlanSymbols = plan_symbols
            changed = True
        return changed

    def normalize_definition_roots(self, panel, doc, asset_group, asset_descriptor, root_objects):

        if not root_objects:
            return root_objects

        import Arch

        panel._ensure_active_document(doc)
        normalized_roots = []
        source_path = getattr(asset_group, "LibrarySourcePath", "")
        multiple_roots = len(root_objects) > 1

        for root_obj in root_objects:
            if is_equipment_object(root_obj):
                self.apply_plan_contract(root_obj, asset_descriptor)
                normalized_roots.append(root_obj)
                continue

            panel._ensure_library_metadata(root_obj, source_path, role="source")
            panel._remove_from_parent_groups(root_obj, keep={asset_group})
            try:
                if root_obj not in (getattr(asset_group, "Group", []) or []):
                    asset_group.addObject(root_obj)
            except Exception:
                pass
            panel._set_definition_view_state(root_obj)

            if multiple_roots:
                component_label = getattr(root_obj, "Label", None) or getattr(root_obj, "Name", "")
                equipment_label = "{} {}".format(asset_descriptor["label"], component_label).strip()
            else:
                equipment_label = asset_descriptor["label"]

            equipment = Arch.makeEquipment(root_obj, name=equipment_label)
            panel._ensure_library_metadata(equipment, source_path, role="instance")
            self.apply_plan_contract(equipment, asset_descriptor)
            panel._remove_from_parent_groups(equipment, keep={asset_group})
            try:
                if equipment not in (getattr(asset_group, "Group", []) or []):
                    asset_group.addObject(equipment)
            except Exception:
                pass
            panel._set_definition_view_state(equipment)
            panel._retarget_definition_links(doc, root_obj, equipment)
            normalized_roots.append(equipment)

        return normalized_roots

    def create_shape_symbol_definitions(self, panel, doc, asset_group, asset_descriptor):

        import Arch
        import Part

        panel._ensure_active_document(doc)
        obj = Arch.makeEquipment()
        obj.Shape = Part.read(asset_descriptor["model_path"])
        obj.Label = asset_descriptor["label"]
        panel._ensure_library_metadata(
            obj, getattr(asset_group, "LibrarySourcePath", ""), role="instance"
        )
        self.apply_plan_contract(obj, asset_descriptor)
        panel._remove_from_parent_groups(obj)
        asset_group.addObject(obj)
        panel._set_definition_view_state(obj)
        if asset_descriptor["plan_path"] and asset_descriptor["plan_path"].lower().endswith(
            ".fcstd"
        ):
            plan_roots = panel._create_auxiliary_symbol_roots(
                doc,
                asset_group,
                asset_descriptor["plan_path"],
                asset_descriptor["label"],
                asset_descriptor["plan_root"],
            )
            self.attach_plan_symbol_roots([obj], plan_roots)
        doc.recompute()
        return [obj]


_STATIC_PROVIDER = BaseAssetProvider()
_EQUIPMENT_PROVIDER = EquipmentAssetProvider()


def get_provider(asset_descriptor):

    if asset_descriptor.get("provider_key") == _EQUIPMENT_PROVIDER.key:
        return _EQUIPMENT_PROVIDER
    if asset_descriptor.get("kind") == "equipment":
        return _EQUIPMENT_PROVIDER
    return _STATIC_PROVIDER


def get_provider_for_object(obj):

    if is_equipment_object(obj):
        return _EQUIPMENT_PROVIDER
    return _STATIC_PROVIDER


def apply_asset_plan_contract(definition_obj, asset_descriptor):

    return get_provider(asset_descriptor).apply_plan_contract(definition_obj, asset_descriptor)


def apply_asset_plan_contract_to_roots(definition_roots, asset_descriptor):

    changed = False
    for definition_obj in definition_roots or []:
        changed = apply_asset_plan_contract(definition_obj, asset_descriptor) or changed
    return changed


def attach_plan_symbol_roots(definition_roots, plan_roots):

    grouped_roots = {}
    for definition_obj in definition_roots or []:
        provider = get_provider_for_object(definition_obj)
        grouped_roots.setdefault(provider, []).append(definition_obj)

    changed = False
    for provider, provider_roots in grouped_roots.items():
        changed = provider.attach_plan_symbol_roots(provider_roots, plan_roots) or changed
    return changed


def normalize_definition_roots(panel, doc, asset_group, asset_descriptor, root_objects):

    return get_provider(asset_descriptor).normalize_definition_roots(
        panel, doc, asset_group, asset_descriptor, root_objects
    )


def create_shape_symbol_definitions(panel, doc, asset_group, asset_descriptor):

    return get_provider(asset_descriptor).create_shape_symbol_definitions(
        panel, doc, asset_group, asset_descriptor
    )


def create_instance(panel, doc, definition_obj, asset_descriptor=None):

    provider = (
        get_provider(asset_descriptor)
        if asset_descriptor
        else get_provider_for_object(definition_obj)
    )
    return provider.create_instance(panel, doc, definition_obj)
