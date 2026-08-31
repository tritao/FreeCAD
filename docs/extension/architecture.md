# Extension Architecture

**Status:** Architecture
**Audience:** FreeCAD core developers, API designers, SDK/backend implementers

## Overview

The Extension system separates **what FreeCAD exposes** from **how extension code executes**.

```text
                          FreeCAD
                             |
                     Extension services
                             |
                     ExtensionApiModel
                             |
          +------------------+------------------+
          |                  |                  |
      CPython SDK        generated SDKs      documentation
          |                  |
     direct binding       runtime lowering
                             |
                         WasmAbiModel
                             |
                            WAMR
```

The same semantic API can therefore be consumed by trusted in-process Python and by sandboxed compiled languages without forcing both through the same transport.

## API sources

Existing public FreeCAD APIs are projected from the normalized Python API:

```text
.pyi
  |
PythonApiModel
  |
ExtensionApiModel
```

Not every future interface has to originate in `.pyi`. Extension-only services, event definitions, lifecycle interfaces, or interfaces authored by non-Python providers may enter the normalized model through other typed authoring mechanisms.

The key rule is **one normalized semantic model**, not one mandatory source syntax.

## Providers

FreeCAD installations may have interfaces from multiple sources:

```text
core:
  org.freecad.document@1
  org.freecad.geometry@1
  org.freecad.ui@1

Part:
  org.freecad.part@1

Draft:
  org.freecad.draft@1

BIM:
  org.freecad.bim@1
```

A built-in module can be both consumer and provider:

```text
BIM
 |
 +-- consumes org.freecad.document@1
 +-- consumes org.freecad.ui@1
 |
 `-- provides org.freecad.bim@1
```

This does not imply BIM itself must run in a sandbox.

## Runtime boundary

A runtime backend receives a semantic operation and lowers it into whatever mechanism is appropriate.

For ordinary Python:

```text
freecad_extension
      |
      v
FreeCAD Extension service implementation
```

For the current sandbox backend:

```text
language facade
      |
raw generated WASM binding
      |
WasmAbiModel contract
      |
freecad_dispatch
      |
FreeCAD Extension service implementation
```

The service implementation should be shared conceptually so threading, lifetime, validation, and transaction semantics do not diverge across execution profiles.

## Public and private API layers

The SDK should have two conceptual layers.

```text
extension author
      |
      v
ergonomic semantic facade
      |
      v
raw runtime binding
      |
      v
runtime backend
```

The semantic facade exposes interfaces and resources:

```python
doc = fc.documents.active()
obj = doc.get_object("Box")
obj.label = "Bracket"
```

The raw binding may expose transport-shaped methods, opaque tokens, codecs, or generated operation identifiers. It is an advanced/internal surface.

## Cross-runtime communication

There is no privileged “Python-to-WASM bridge”.

All runtimes interact through the same FreeCAD-owned concepts:

```text
       Python                 WASM
          \                   /
           \                 /
            Extension services
                 |
            FreeCAD model
```

When third-party provided interfaces are introduced:

```text
consumer runtime
      |
interface registry
      |
provider runtime
```

FreeCAD remains responsible for scheduling, validation, security, lifetime, and error translation.

## Why this architecture

It avoids four major forms of coupling:

1. **language coupling** — API semantics are not separately designed for Python, C++, and Rust;
2. **runtime coupling** — Extension code does not depend on WAMR concepts;
3. **implementation coupling** — portable APIs do not expose arbitrary Qt/Coin/Python/C++ objects;
4. **package coupling** — extension identity does not live only in Cargo, CMake, or Python metadata.

## Long-term direction

The Extension API can become FreeCAD's preferred stable extension surface without replacing the existing Python API.

That supports a gradual path:

```text
existing addon
   |
uses current Python API
   |
optionally adopts Extension API
   |
still ordinary CPython
   |
optionally chooses sandboxed execution later
```

The same API can also become the mechanism by which built-in modules publish stable functionality to external consumers.
