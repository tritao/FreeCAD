# Architecture Decision Freeze

**Status:** Architecture
**Purpose:** drafting source of truth

This page records the decisions that should remain consistent across this documentation set. It also separates deliberately deferred work from questions that would otherwise create contradictory documentation.

## Frozen decisions

### D1 — One stable Extension API

FreeCAD defines a stable, language-neutral **Extension API**. It is not a WASM-specific API.

### D2 — Extension API available to ordinary CPython

The same semantic API is exposed to trusted in-process Python. In-process bindings should use direct FreeCAD service calls rather than serializing through a WASM transport.

Recommended import:

```python
import freecad_extension as fc
```

The package should not export a redundant root object requiring:

```python
from freecad_extension import FreeCAD
```

### D3 — Existing Python API remains supported

`import FreeCAD`, `Part`, PySide, Pivy, and existing addon conventions remain supported. The Extension API is additive and may gradually become the recommended API for new portable extension code.

### D4 — Built-in modules need not become extension packages

Part, Draft, BIM, FEM, CAM, TechDraw, and other built-ins may consume and provide Extension interfaces without being sandboxed or installed through AddonManager.

Where practical, built-in modules should dogfood public Extension APIs. They may continue to use privileged/private APIs where needed.

### D5 — Existing APIs project from `.pyi`

Existing FreeCAD API signatures should be projected through:

```text
.pyi -> PythonApiModel -> ExtensionApiModel
```

Semantic extension metadata may live in `.pyi`. Runtime transport facts may not.

### D6 — `ExtensionApiModel` is runtime-neutral

`ExtensionApiModel` owns stable semantic concepts.

`WasmAbiModel` is a backend-specific lowering and should retain its WASM name. It should **not** be renamed to `ExtensionAbiModel`.

### D7 — Interfaces are the main API unit

An interface has a stable identity such as:

```text
org.freecad.document@1
```

and may contain operations, events, values, and resources.

Operation IDs use:

```text
org.freecad.document@1/get_object
```

### D8 — Events are first-class interface members

Events are not ad-hoc runtime callbacks. They use explicit subscriptions and FreeCAD-managed delivery.

Initial semantics:

- queued;
- non-reentrant;
- serialized per execution context;
- deterministic subscription cleanup;
- commit-oriented/coalesced when intermediate model states should not be exposed.

### D9 — Cross-runtime communication goes through FreeCAD

Python and WASM do not normally exchange arbitrary runtime objects directly.

Communication occurs through:

- shared FreeCAD resources;
- Extension interface operations;
- Extension events;
- later, provided interfaces.

### D10 — Third-party provided interfaces are designed now, implemented later

The semantic model should support third-party providers. Initial v1 delivery need not block on arbitrary third-party interface publication.

Core and built-in-module interfaces are sufficient to prove the model first.

### D11 — Conservative threading semantics

The public API defines execution classes, not raw FreeCAD thread IDs.

Initial classes:

- `serialized`
- `ui`
- `concurrent`

Default: `serialized`.

### D12 — One language-neutral package metadata source

New-style extensions use `freecad-extension.toml` as the proposed canonical human-authored metadata format.

It is intentionally small. Runtime-specific facts are generated.

Legacy `package.xml` remains supported.

AddonManager normalizes both into an internal `PackageMetadata` representation.

### D13 — Permissions are coarse and security-relevant

Initial vocabulary should stay small. Recommended starting set:

```text
document.read
document.modify
filesystem.read
filesystem.write
network
process
ui
```

Pure computation should normally not need a permission.

### D14 — Permissions are only a security boundary when enforceable

Sandboxed extensions can be constrained by host permissions.

Ordinary in-process Python cannot be made safe merely by gating Extension API calls because it has process-level access. AddonManager must distinguish “sandboxed with declared permissions” from “trusted in-process”.

### D15 — One Extension SDK product, language-specific packages

Public distribution:

```text
C++    FreeCADExtensionSDK
Rust   freecad-extension-sdk
Python freecad_extension
```

Each language gets an ergonomic semantic facade. A raw transport layer may exist underneath.

### D16 — Hide WASM at the product boundary, not internally

Rename product-level concepts such as:

```text
WasmAddon         -> Extension
WasmAddonManager  -> ExtensionManager
WasmManifest      -> ExtensionMetadata / ExtensionManifest
WasmPermissions   -> ExtensionPermissions
```

Keep backend concepts such as:

```text
WasmAbiModel
WasmHostApi
WasmHandleTable
WamrRuntime
```

### D17 — AddonManager remains the ecosystem entry point

New-style extensions should integrate with AddonManager rather than creating a separate marketplace or manager.

## Deferred decisions

These are intentionally not frozen as v1 requirements.

### Async tasks

The API should leave room for a semantic `Task` resource but does not need a complete async/await model initially.

### Multiple providers for one interface identity

Initial resolution should assume at most one active provider for an exact interface major version. Provider priorities and multicast dispatch are deferred.

### Sandboxed Python implementation

The Python semantic API should be designed now. The specific Python-to-WASM/runtime strategy is a later runtime decision.

### Zero-copy bulk data

Initial bulk APIs may copy packed arrays. Shared-memory and zero-copy designs should be benchmark-driven.

### Automatic permission inference

Tooling may eventually infer a candidate permission set from API usage, but explicit package permission declarations remain the portable source of intent.

### Extension-defined interface authoring syntax

The normalized semantic model is more important than a single authoring syntax. Built-in interfaces can come from `.pyi`; Rust/C++ providers should not be forced to hand-author fake Python stubs.

## Review triggers

A new architectural review is warranted if a proposal would:

- make WASM concepts part of the runtime-neutral API;
- require legacy Python addons to migrate;
- require built-in modules to become sandboxed packages;
- bypass FreeCAD for cross-runtime object communication;
- duplicate semantic API definitions per language;
- introduce fine-grained permission strings matching individual methods;
- couple package identity to one language build system.
