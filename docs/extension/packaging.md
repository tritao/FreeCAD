# Extension Packaging

**Status:** Normative proposal

## Goals

Packaging should be language-independent, minimize author-maintained metadata, allow compatibility inspection before execution, separate semantic metadata from runtime-generated details, and coexist with existing FreeCAD addon metadata.

## Canonical new metadata

The proposed human-authored file is:

```text
freecad-extension.toml
```

TOML is used because the data is small, declarative, human-maintained, and useful across CMake, Cargo, Python, and future toolchains.

It must not become a general build system.

## Minimal example

```toml
schema = 1

[extension]
id = "org.example.gears"
name = "Gears"
version = "1.0.0"

[requires]
extension_api = "1"

[permissions]
required = [
  "document.modify",
]
```

## Identity

`extension.id` is globally stable and machine-oriented. `name` is display text and may change without changing identity.

Package version describes the extension release, not the Extension API version.

## Requirements

The package may declare:

```toml
[requires]
extension_api = "1"
interfaces = [
  "org.freecad.part@1",
  "org.freecad.bim@1",
]
```

Exact version-range syntax should stay simple initially. Interface major-version identity already carries the most important compatibility boundary.

## Permissions

Requested sandbox capabilities are declared once in package metadata. Do not duplicate them independently in Cargo, CMake, generated manifests, and catalog metadata.

## Generated runtime metadata

Build/package tooling owns:

```text
artifact filename
runtime backend
entrypoint/export name
backend ABI fingerprint
wire ABI version
compiler target
generated SDK compatibility hash
```

Authors should not copy an ABI hash by hand.

## Runtime package output

A sandboxed compiled package may conceptually contain:

```text
MyExtension/
  package metadata
  extension.wasm
  generated runtime manifest
  assets/
```

The exact archive/container format is separate from the authoring metadata schema.

## Build-system integration

Language build systems consume `freecad-extension.toml` rather than redefining extension identity.

CMake:

```cmake
freecad_add_extension(MyExtension
    SOURCES MyExtension.cpp
)
```

Cargo and Python tooling can locate the same project-level file.

## Legacy `package.xml`

Existing addons continue to use `package.xml`.

AddonManager should normalize both forms:

```text
package.xml ----------------\
                             -> PackageMetadata -> AddonManager
freecad-extension.toml -----/
```

Do not require a new extension to maintain two independent files containing the same name, version, compatibility, and dependency data.

Transitional tools may generate compatibility metadata where necessary.

## Multi-language extensions

A shared metadata file naturally supports:

```text
MyExtension/
  freecad-extension.toml
  core/
    Cargo.toml
  ui/
    pyproject.toml
  native/
    CMakeLists.txt
```

One extension retains one identity.

## Built-in modules

Built-in modules are not required to have `freecad-extension.toml` merely because they provide Extension interfaces. Provider metadata can be compiled/registered directly.

## Schema evolution

`schema = 1` versions the TOML file format. Package schema version, Extension API version, interface versions, and backend ABI version remain separate.
