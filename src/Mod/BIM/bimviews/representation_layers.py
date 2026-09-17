# SPDX-License-Identifier: LGPL-2.1-or-later

"""Retained contextual rendering layers owned by GUI viewports."""

from dataclasses import dataclass

import BimContextualRendering

from .representation_cache import representation_request_key


@dataclass
class _LayerEntry:
    view: object
    document: object
    request_key: object
    renderer: object
    leases: int = 0
    stale: bool = False


_layers = {}


def acquire(view, request, document):
    key = (id(view), representation_request_key(request))
    entry = _layers.get(key)
    reused = entry is not None and not entry.stale and entry.renderer.root is not None
    if not reused:
        if entry is not None:
            entry.renderer.close()
        entry = _LayerEntry(
            view,
            document,
            key[1],
            BimContextualRendering.ContextualRepresentationRenderer(view),
        )
        _layers[key] = entry
    entry.leases += 1
    entry.renderer.resume()
    return entry.renderer, reused


def release(renderer):
    for key, entry in tuple(_layers.items()):
        if entry.renderer is not renderer:
            continue
        entry.leases = max(0, entry.leases - 1)
        if entry.leases:
            return
        if entry.stale:
            entry.renderer.close()
            _layers.pop(key, None)
        else:
            entry.renderer.suspend()
        return
    renderer.close()


def invalidate_document(document):
    for key, entry in tuple(_layers.items()):
        if entry.document is not document:
            continue
        if entry.leases:
            entry.stale = True
        else:
            entry.renderer.close()
            _layers.pop(key, None)


def close_renderer(renderer):
    for key, entry in tuple(_layers.items()):
        if entry.renderer is renderer:
            entry.renderer.close()
            _layers.pop(key, None)
            return
    renderer.close()
