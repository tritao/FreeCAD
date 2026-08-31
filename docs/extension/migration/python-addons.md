# Migrating Existing Python Addons

**Status:** Guide

## No forced migration

Existing addons remain supported. This guide describes an optional path toward the stable Extension API.

## Stage 0 — existing code

```python
import FreeCAD
import Part
```

Continue using it where needed.

## Stage 1 — adopt portable APIs selectively

```python
import FreeCAD
import freecad_extension as fc

doc = fc.documents.active()
```

An addon can migrate one subsystem at a time.

## Stage 2 — reduce implementation-specific dependencies

Prefer Extension values/resources over raw Qt objects, Coin nodes, direct Python-wrapper internals, and undocumented implementation APIs where the Extension API has sufficient coverage.

## Stage 3 — declare package requirements

```toml
[requires]
extension_api = "1"
interfaces = ["org.freecad.part@1"]
```

Ordinary in-process execution is still allowed.

## Stage 4 — optional sandbox migration

If a future sandboxed Python runtime becomes available and the addon uses a portable API subset, sandboxing can become an execution-profile change rather than a complete FreeCAD API rewrite.

This is an architectural goal, not a guarantee that all existing Python dependencies can run in a sandbox.

## PySide/Pivy

Trusted in-process addons may continue using PySide/Pivy. Sandboxed portable extensions should use stable FreeCAD UI/view services instead of direct Qt/Coin object graphs.

A practical addon may remain in-process indefinitely if it requires implementation-level APIs.

## Security messaging

Switching from legacy calls to `freecad_extension` does not itself sandbox an in-process addon. Only the execution profile determines isolation.
