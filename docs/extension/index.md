# FreeCAD Extension Developer Documentation

**Status:** Architecture index

The FreeCAD Extension system defines a stable application-facing API that can be consumed from multiple languages and execution profiles.

## Reading paths

### Architecture reviewer

1. [Decisions](decisions.md)
2. [Architecture](architecture.md)
3. [API model](api-model.md)
4. [Execution model](execution-model.md)
5. [Interfaces](interfaces.md)
6. [Events](events.md)
7. [Packaging](packaging.md)
8. [AddonManager](addon-manager.md)

### SDK implementer

1. [API model](api-model.md)
2. [SDK overview](sdk/overview.md)
3. [Execution model](execution-model.md)
4. [Lifecycle](lifecycle.md)
5. [Threading](threading.md)
6. [WASM backend overview](runtime/wasm/overview.md)

### Addon author

1. [SDK overview](sdk/overview.md)
2. language guide: [C++](sdk/cpp.md), [Rust](sdk/rust.md), or [Python](sdk/python.md)
3. [Packaging](packaging.md)
4. [Permissions](permissions.md)
5. [Events](events.md)

### Built-in module maintainer

1. [Built-in module providers](providers/builtin-modules.md)
2. [Interfaces](interfaces.md)
3. [API model](api-model.md)
4. [Built-in module migration](migration/builtin-modules.md)

## Document map

| Document | Class | Purpose |
| --- | --- | --- |
| [decisions.md](decisions.md) | Architecture | Design freeze and deferred choices |
| [glossary.md](glossary.md) | Normative vocabulary | Stable terminology |
| [architecture.md](architecture.md) | Architecture | Canonical system structure |
| [api-model.md](api-model.md) | Normative | Interfaces, operations, types, IDs and versioning |
| [execution-model.md](execution-model.md) | Architecture / normative | Execution profiles and dispatch boundaries |
| [lifecycle.md](lifecycle.md) | Normative | Context, attachment and resource lifetime |
| [threading.md](threading.md) | Normative | Scheduling, serialization and reentrancy |
| [events.md](events.md) | Normative | Subscription and event-delivery semantics |
| [interfaces.md](interfaces.md) | Normative | Providers, consumers and interface resolution |
| [permissions.md](permissions.md) | Normative | Security-relevant capabilities |
| [packaging.md](packaging.md) | Normative | Package metadata and artifacts |
| [addon-manager.md](addon-manager.md) | Architecture / guide | Discovery, install, compatibility and trust UX |
| [sdk/overview.md](sdk/overview.md) | Architecture / guide | Generated SDK organization |
| [sdk/cpp.md](sdk/cpp.md) | Guide | C++ developer experience |
| [sdk/rust.md](sdk/rust.md) | Guide | Rust developer experience |
| [sdk/python.md](sdk/python.md) | Guide | In-process and future sandbox Python |
| [providers/builtin-modules.md](providers/builtin-modules.md) | Architecture / guide | Draft/BIM/etc. as interface providers |
| [providers/third-party.md](providers/third-party.md) | Architecture / future | Third-party provided interfaces |
| [migration/python-addons.md](migration/python-addons.md) | Guide | Incremental migration from legacy Python |
| [migration/builtin-modules.md](migration/builtin-modules.md) | Guide | Incremental built-in adoption |
| [runtime/wasm/overview.md](runtime/wasm/overview.md) | Backend architecture | WASM lowering boundary |
| [runtime/wasm/abi.md](runtime/wasm/abi.md) | Backend specification | Current binary ABI |
| [runtime/wasm/implementation.md](runtime/wasm/implementation.md) | Implementation notes | Current branch mapping |
| [security.md](security.md) | Architecture / normative | Trust and sandbox security |
| [ui-and-view.md](ui-and-view.md) | Architecture | Portable UI/view direction |
| [roadmap.md](roadmap.md) | Architecture / planning | Suggested implementation order |
| [review-checklist.md](review-checklist.md) | Guide | Review questions for API/runtime changes |

## Public versus backend vocabulary

Public code and documentation should normally say:

```text
Extension
Extension API
Extension SDK
Extension interface
resource
execution profile
```

Backend code should retain technically accurate names where the concept is genuinely WASM-specific:

```text
WasmAbiModel
WamrRuntime
WasmHostApi
WasmHandleTable
```

The goal is not to erase WebAssembly from the implementation. The goal is to prevent one backend from defining the identity of the public extensibility model.
