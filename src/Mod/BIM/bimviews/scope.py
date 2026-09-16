# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic object scope for an active BIM view."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BIMViewCategory:
    """A semantic category within a view scope.

    Category population is intentionally deferred to the semantic-scope
    implementation.  Defining the value type here keeps the navigator API
    stable while classification is added incrementally.
    """

    key: str
    label: str
    objects: tuple = ()


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
        return cls(
            definition=definition,
            source=source,
            context_objects=context_objects,
            visible_objects=tuple(visible),
            hidden_objects=tuple(hidden),
        )


def _is_visible(obj):
    try:
        return bool(obj.ViewObject.Visibility)
    except (AttributeError, ReferenceError, RuntimeError):
        return True
