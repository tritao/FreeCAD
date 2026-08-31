# Extension Architecture Roadmap

**Status:** Architecture / planning

## Phase 0 — history and model cleanup

- rewrite branch-only experimental history into architectural dependency order;
- preserve the upstream base exactly;
- reduce duplication in `WasmAbiModel`;
- use enums for closed vocabularies;
- shrink `wasm_abi.lock.toml` to compatibility facts.

## Phase 1 — public naming and SDK boundary

- introduce generic Extension terminology;
- keep WASM naming in backend implementation;
- define public C++/Rust/Python names;
- split raw generated bindings from semantic facades;
- organize APIs around interfaces/resources rather than a flat client.

## Phase 2 — useful core API

Expand:

```text
Document
DocumentObject
Placement
Rotation
Vector
TopoShape
transactions
bulk topology/geometry data
```

Benchmark host-call overhead and bulk transfer patterns.

## Phase 3 — in-process Python binding

Expose the same semantic Extension API through ordinary FreeCAD CPython. Ensure threading, errors, transactions, events, and resource semantics match sandboxed callers.

## Phase 4 — packaging and AddonManager

- define `freecad-extension.toml` schema;
- normalize legacy/new metadata into `PackageMetadata`;
- preflight API/interface dependencies;
- distinguish sandboxed versus trusted in-process execution;
- install compiled artifacts;
- manage permission deltas.

## Phase 5 — lifecycle and events

- execution context and attachment APIs;
- deterministic subscription resources;
- queued/non-reentrant event dispatcher;
- transaction-aware/coalesced document events.

## Phase 6 — built-in module interfaces

Pilot one or two modules such as Part, Draft, or BIM. Keep interfaces small and stability-oriented.

## Phase 7 — UI services

Design portable commands, panels, selection, camera, overlays, and gizmos without exposing arbitrary Qt/Coin object graphs.

## Phase 8 — third-party provided interfaces

- package-published interface schema;
- provider registration;
- provider execution-context dispatch;
- provider-defined resources;
- interface dependencies in AddonManager;
- provider events.

Start with one active provider per exact interface major version.

## Phase 9 — tasks and async

Introduce a semantic task resource only after concrete long-running APIs demand it.

## Phase 10 — additional runtimes

Evaluate sandboxed Python, additional source-language SDKs, alternate WebAssembly runtimes, Component Model, and out-of-process sandboxing.

## Success criterion

Adding an operation should trend toward:

```text
1. declare/project semantic operation
2. update backend compatibility lock if required
3. implement one host/provider handler
4. regenerate SDKs/docs
```

Adding a language should primarily require another SDK/backend renderer, not a new FreeCAD API design.
