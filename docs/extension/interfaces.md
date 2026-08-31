# Extension Interfaces and Providers

**Status:** Normative architecture; third-party publication is initially deferred

## Interface model

An Extension interface is a stable versioned contract containing identity, operations, events, value types, and resource types.

Examples:

```text
org.freecad.document@1
org.freecad.part@1
org.freecad.bim@1
org.example.gears@1
```

## Provider registry

FreeCAD maintains a logical registry:

```text
org.freecad.document@1 -> Core
org.freecad.part@1     -> Part
org.freecad.bim@1      -> BIM
```

Later:

```text
org.example.gears@1    -> Gears extension
```

Consumers resolve an interface through FreeCAD, not by importing or linking directly to the provider implementation.

## Resolution

A dynamic API may conceptually support:

```python
bim = fc.interfaces.require("org.freecad.bim@1")
```

Resolution can fail because the interface is missing, the major version is unavailable, the provider is disabled/failed, or required permission is unavailable.

## One provider initially

For an exact interface identity and major version, the initial model assumes one active provider. Competing providers are a configuration conflict.

Provider ranking, service selection, and multicast RPC are deferred.

## Built-in providers

Built-in modules can register providers directly. The implementation may remain ordinary Python/C++ code.

## Third-party providers

A third-party extension should eventually be able to provide `org.example.gears@1`. A consumer depends on the interface, not on the provider's runtime language.

FreeCAD performs dispatch:

```text
consumer
   |
interface registry
   |
provider execution context
   |
provider implementation
```

This is the preferred Python-to-WASM, WASM-to-Python, and extension-to-extension communication path.

## Portable interface types

Provider contracts use primitives, strings/bytes, records, enums, arrays, Extension values/resources, and provider-defined values/resources.

They may not expose arbitrary Python objects, Qt objects, Coin nodes, C++ pointers, or raw guest-memory addresses.

## Provider-defined resources

A provider may return a resource such as `SliceJob`. FreeCAD keeps the consumer reference associated with its owning provider and routes subsequent resource operations back to that provider.

## Provider lifetime

When a provider unloads, new resolution fails, provider resources become invalid, subscriptions close, and consumers receive deterministic unavailable/invalid-resource failures.

## Dependencies

Packages may declare required interfaces:

```toml
[requires]
interfaces = [
  "org.freecad.part@1",
  "org.freecad.bim@1",
]
```

AddonManager and the loader can perform compatibility checks before code execution.

## Authoring interfaces

No single source syntax is required by the architecture. Built-in projected APIs can come from `.pyi`; Rust/C++ provider tooling may use native declarations or generated schema tooling. All paths normalize into the common interface model.

Forcing non-Python authors to hand-write fake Python stubs purely as IDL is not required.

## Initial rollout

Recommended order: core interfaces, built-in module interfaces, consumer-side dependency handling, events, third-party publication, provider-defined resources, then advanced async services.
