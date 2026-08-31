# WebAssembly Sandbox Backend

**Status:** Backend architecture

## Role

WebAssembly/WAMR is the initial sandbox execution backend for the FreeCAD Extension API.

It is not the public identity of the extension system.

```text
ExtensionApiModel
      |
WasmAbiModel
      |
generated raw guest bindings
      |
WASM module
      |
WAMR
```

## Backend-specific concepts

These should remain WASM-specific because they describe real backend mechanics:

```text
WasmAbiModel
WasmAbiType
WasmHostApi
WasmHandleTable
WasmRuntime
WamrRuntime
WamrInstance
wasm_abi.lock.toml
```

## Generic concepts above the backend

These should not be named after WASM:

```text
Extension
ExtensionManager
ExtensionMetadata
ExtensionPermissions
Extension SDK
PackageMetadata
```

## ABI lowering

`WasmAbiModel` maps semantic operations to numeric opcode, wire name/types, resource ownership, binary signature/fingerprint, and backend response semantics.

The lowering must not feed transport details back into `ExtensionApiModel`.

## Raw versus semantic SDK

The backend generator can produce raw bindings used internally by C++, Rust, and a future sandboxed Python runtime. Normal documentation should show semantic resources/interfaces rather than `freecad_dispatch` calls.

## Portability

A future sandbox backend may coexist with or replace WAMR without invalidating the Extension API. Public compatibility is tied to interface semantics, not WAMR.
