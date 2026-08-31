# Python Extension API Guide

**Status:** Guide / architecture

## Recommended import

```python
import freecad_extension as fc
```

Avoid:

```python
from freecad_extension import FreeCAD
```

because the package already identifies the API and another `FreeCAD` root object is redundant.

## In-process use

```python
import freecad_extension as fc

doc = fc.documents.active()
box = fc.part.make_box(10, 20, 30)

with doc.transaction("Create box"):
    obj = doc.add_object(box, "Box")
    obj.label = "Bracket"
```

This binding should call the Extension service implementation directly, not serialize through the WASM request envelope.

## Relationship to `import FreeCAD`

Existing code remains valid. The Extension API offers a designed portable surface, not an immediate replacement.

An addon may mix APIs while migrating, although portable code should minimize implementation-specific dependencies.

## Exceptions and resources

Python exposes semantic failures as exceptions. Property setters return `None`. Resource objects carry their host/runtime context internally; integer handles are not public.

## Events

```python
def changed(event):
    print(event.object)

subscription = fc.documents.object_changed.subscribe(changed)
```

Callbacks follow the same queued/non-reentrant rules as other runtimes.

## Sandboxed Python

A future sandboxed Python profile should aim to expose the same semantic package/API. The specific runtime strategy is deliberately not fixed here.

WAMR executes WebAssembly modules; it does not directly execute arbitrary CPython source.

## Typing

The package should ship high-quality generated type information from `ExtensionApiModel` for editors and static analysis.
