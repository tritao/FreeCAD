# Built-in Modules as Extension Interface Providers

**Status:** Architecture / guide

## Principle

A built-in FreeCAD module can provide a stable Extension interface without becoming a sandboxed extension package.

This is the preferred path for optional-domain APIs such as:

```text
org.freecad.part@1
org.freecad.draft@1
org.freecad.bim@1
org.freecad.fem@1
org.freecad.cam@1
org.freecad.techdraw@1
```

## Provider shape

```text
existing BIM Python/C++ implementation
           |
      provider adapter
           |
   org.freecad.bim@1
```

The adapter maps stable Extension semantics onto the existing implementation.

## Consuming core interfaces

A built-in module may also consume public core interfaces:

```text
BIM
 |
 +-- consumes org.freecad.document@1
 +-- consumes org.freecad.ui@1
 `-- provides org.freecad.bim@1
```

This provides useful dogfooding. It is not necessary to rewrite every internal operation through the Extension API.

## Draft example

Draft might initially expose a deliberately small surface:

```text
org.freecad.draft@1

create_wire(points, closed) -> DocumentObject
create_circle(center, radius) -> DocumentObject
upgrade(objects) -> list[DocumentObject]

events:
  object_created
```

The exact API should be designed for stability rather than mechanically exposing every existing function.

## BIM example

```text
org.freecad.bim@1

create_wall(...)
create_building(...)
get_spatial_container(object)
assign_material(...)

events:
  spatial_structure_changed
```

This lets ordinary Python and sandboxed C++/Rust consumers share the same BIM contract.

## Optional installation

If an interface is unavailable, consumers receive a normal interface-unavailable result.

Packages can declare:

```toml
[requires]
interfaces = ["org.freecad.bim@1"]
```

so AddonManager can preflight dependencies.

## API design responsibility

A built-in provider should choose stable semantic types, avoid leaking Qt/Coin/Python internals, define resource lifetime, threading class and events, and honor declared major-version compatibility.

The Extension interface may intentionally be smaller and cleaner than the module's complete implementation API.

## Why built-ins should participate

This creates a public API that FreeCAD itself uses, making regressions and poor ergonomics visible earlier. It also prevents the Extension API from becoming an isolated “sandbox API”.
