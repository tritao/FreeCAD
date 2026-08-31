# FreeCAD Extension Architecture — Draft Documentation Set

**Status:** Working draft
**Date:** 2026-08-31
**Implementation reference:** `tritao/FreeCAD`, branch `wasm-runtime-bindings`, snapshot `ca90cf9b280b9f3a73c0461f70d6aa3624b6a0fd`

This package turns the extension-architecture design discussion into a coherent documentation set suitable for review, iteration, and eventual adoption as FreeCAD developer documentation.

The central proposal is:

> **FreeCAD should define a stable, language-neutral Extension API that is usable from ordinary in-process Python and from sandboxed runtimes. WebAssembly/WAMR is the initial sandbox backend, not the identity of the extension system.**

This documentation set carries the detailed semantic contracts, SDK guidance, packaging model, lifecycle rules, and backend documentation for the proposed Extension architecture.

## Start here

1. [`decisions.md`](decisions.md) — design-freeze record and deferred decisions.
2. [`architecture.md`](architecture.md) — canonical technical architecture.
3. [`index.md`](index.md) — documentation map.

## Documentation classes

Pages are labelled as one of:

- **Normative** — defines a compatibility or behavioral contract implementations should follow.
- **Architecture** — explains design boundaries and intended structure.
- **Guide** — explains how to use or adopt the system.
- **Backend specification** — defines one runtime-specific implementation contract and does not redefine the Extension API.

This distinction is deliberate. For example, “resources have explicit lifetime semantics” belongs to the public architecture, while “WASM resources lower to opaque integer handles” is a backend detail.

## Core vocabulary

Public/product terminology:

- FreeCAD Extension
- FreeCAD Extension API
- FreeCAD Extension SDK
- Extension interface
- provider / consumer
- value / resource
- execution profile
- attachment
- subscription

Backend/internal terminology remains precise:

- `WasmAbiModel`
- `WasmAbiType`
- `WamrRuntime`
- `WasmHostApi`
- `wasm_abi.lock.toml`
- `freecad_dispatch`
- FCWA / FCWR

## Intent

This is a documentation proposal, not a claim that every documented capability already exists. Each page separates current implementation facts, initial target behavior, and deferred capabilities where appropriate.
