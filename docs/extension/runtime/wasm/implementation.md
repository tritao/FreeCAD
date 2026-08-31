# Current WASM Implementation Mapping

**Status:** Implementation notes
**Snapshot:** `tritao/FreeCAD`, branch `wasm-runtime-bindings`, SHA `ca90cf9b280b9f3a73c0461f70d6aa3624b6a0fd`

This page maps the current experimental branch to the proposed architecture. File names are implementation facts, not public naming commitments.

## Semantic/model pipeline

```text
.pyi + extension metadata
        |
PythonApiModel
        |
ExtensionApiModel
        |
typed adapter declarations
        |
WasmAbiModel
        ^
wasm_abi.lock.toml
```

Generated artifacts include ABI JSON and C++/Rust/Python guest bindings.

## Typed WASM model

Current implementation lives under `src/Tools/wasm_api_model/` with typed model, adapter, lock, and type modules.

This is appropriately backend-specific and should remain named as such.

## Product-level names to migrate

Current implementation contains concepts equivalent to:

```text
WasmAddon
WasmAddonManager
WasmManifest
WasmPermissions
```

These should become generic Extension-layer concepts where they are not genuinely backend-specific.

## Backend names to keep

```text
WasmAbi
WasmHostApi
WasmHandleTable
WasmRuntime
WamrRuntime
WamrInstance
WamrHostBindings
```

## SDK generation

The next step is to separate:

```text
raw generated transport binding
            |
ergonomic semantic Extension SDK
```

The semantic facade should be driven primarily by `ExtensionApiModel`; the raw binding remains driven by `WasmAbiModel`.

## Host dispatch

Recommended generated metadata:

```cpp
struct OperationDescriptor {
    Operation opcode;
    Permission permission;
    TransactionPolicy transaction;
    bool mutates;
    OperationHandler handler;
};
```

Generate drift-prone metadata and registration; keep actual FreeCAD operation bodies handwritten.

## Current architecture judgment

The branch has enough model structure. Further work should prioritize ergonomic SDKs, generic public naming, an in-process Python binding, real API coverage, host descriptor generation, and package/AddonManager integration rather than additional generic IR layers.
