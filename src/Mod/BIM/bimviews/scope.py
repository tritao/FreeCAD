# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic object scope for an active BIM view."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BIMViewCategory:
    """A semantic category within a view scope."""

    key: str
    label: str
    objects: tuple = ()
    visible_objects: tuple = ()
    hidden_objects: tuple = ()


@dataclass(frozen=True)
class BIMViewScope:
    """Objects belonging to a BIM view, independent of navigator widgets."""

    definition: object = None
    source: object = None
    context_objects: tuple = ()
    visible_objects: tuple = ()
    hidden_objects: tuple = ()
    categories: tuple = ()

    @classmethod
    def from_objects(cls, objects, *, definition=None, source=None):
        context_objects = tuple(dict.fromkeys(objects or ()))
        forced_visible = set(getattr(definition, "ForcedVisible", ()) or ())
        forced_hidden = set(getattr(definition, "ForcedHidden", ()) or ())
        visible = []
        hidden = []
        for obj in context_objects:
            if obj in forced_hidden:
                hidden.append(obj)
            elif obj in forced_visible or _is_visible(obj):
                visible.append(obj)
            else:
                hidden.append(obj)
        categories = _categorize(context_objects, visible, hidden)
        return cls(
            definition=definition,
            source=source,
            context_objects=context_objects,
            visible_objects=tuple(visible),
            hidden_objects=tuple(hidden),
            categories=categories,
        )


def _is_visible(obj):
    try:
        return bool(obj.ViewObject.Visibility)
    except (AttributeError, ReferenceError, RuntimeError):
        return True


_CATEGORY_DEFINITIONS = (
    ("Walls", "Walls", {"Wall", "CurtainWall"}),
    ("Doors", "Doors", {"Door"}),
    ("Windows", "Windows", {"Window"}),
    ("Slabs", "Slabs", {"Slab"}),
    ("Roofs", "Roofs", {"Roof"}),
    ("Spaces", "Spaces", {"Space"}),
    ("Furniture", "Furniture", {"Furniture", "FurnishingElement"}),
    (
        "Structure",
        "Structure",
        {"Beam", "Column", "Footing", "Member", "Pile", "Plate", "Structure"},
    ),
    (
        "MEP",
        "MEP",
        {
            "CableCarrierSegment",
            "DuctSegment",
            "FlowController",
            "FlowFitting",
            "FlowSegment",
            "Pipe",
            "PipeFitting",
        },
    ),
    ("Annotations", "Annotations", {"Annotation", "Dimension", "Label", "Text"}),
)


def _categorize(objects, visible, hidden):
    visible_set = set(visible)
    hidden_set = set(hidden)
    semantic_types = {obj: _semantic_type(obj) for obj in objects}

    categories = []
    for key, label, category_types in _CATEGORY_DEFINITIONS:
        members = tuple(obj for obj in objects if semantic_types[obj] in category_types)
        if not members:
            continue
        categories.append(
            BIMViewCategory(
                key=key,
                label=label,
                objects=members,
                visible_objects=tuple(obj for obj in members if obj in visible_set),
                hidden_objects=tuple(obj for obj in members if obj in hidden_set),
            )
        )
    return tuple(categories)


def _semantic_type(obj):
    ifc_type = str(getattr(obj, "IfcType", "") or "").replace(" ", "")
    if ifc_type and ifc_type not in {"BuildingElementProxy", "Undefined"}:
        return ifc_type
    try:
        import Draft

        draft_type = str(Draft.getType(obj) or "").replace(" ", "")
    except (AttributeError, ImportError, RuntimeError):
        draft_type = ""
    aliases = {
        "CurtainWall": "CurtainWall",
        "Structure": "Structure",
        "Wall": "Wall",
        "Window": "Window",
    }
    return aliases.get(draft_type, draft_type)
