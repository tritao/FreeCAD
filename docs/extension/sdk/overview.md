# Extension SDK Overview

**Status:** Architecture / guide

## One SDK product

FreeCAD should present one product: **FreeCAD Extension SDK**, with language-specific packages generated from the same semantic API.

```text
ExtensionApiModel
      |
      +-- C++ semantic facade
      +-- Rust semantic facade
      +-- Python semantic facade
      |
      `-- runtime-specific raw bindings
```

## Two layers

### Public semantic facade

Resource- and interface-oriented, language-native API:

```text
Document.get_object()
TopoShape.volume()
Vector.dot()
fc.part.make_box()
```

### Raw runtime binding

Generated transport used underneath the semantic facade. It may contain operation IDs, codecs, wire errors, opaque tokens, and host imports.

Normal authors should rarely need it.

## API organization

Avoid one enormous flat `Client`.

Prefer:

```text
fc.documents
fc.geometry
fc.part
fc.selection
fc.ui
fc.interfaces
```

and resource methods such as `Document.get_object()` and `TopoShape.volume()`.

## Resource context

A resource object carries enough SDK/runtime context internally to make calls. Authors should not pass integer handles.

## Errors

Expose language-native errors:

```text
C++    Result<T> and/or optional throwing facade
Rust   Result<T, Error>
Python exceptions
```

Transport failures remain beneath the semantic error model.

## Ownership

Expose language-native lifetime behavior: RAII for C++, `Drop`/explicit close for Rust, and context managers/`close()` for Python where appropriate.

## Transactions

Python:

```python
with doc.transaction("Edit"):
    obj.label = "Bracket"
```

Rust and C++ should have equivalent scoped transaction helpers.

## Distribution

Two forms are recommended:

1. bundled with FreeCAD, authoritative for that installation;
2. standalone release packages for CI/editors/build farms.

Standalone packages should be generated from tagged FreeCAD/API releases and not evolve independently.
