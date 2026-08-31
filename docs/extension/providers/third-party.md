# Third-party Provided Interfaces

**Status:** Future architecture; not required for initial v1

## Goal

A third-party extension should eventually be able to provide a stable interface to other extensions.

Example:

```text
org.example.gears@1

operations:
  create_gear
  inspect_gear

events:
  gear_created
  gear_changed
```

## Why this matters

It gives FreeCAD one cross-extension mechanism that works across Python→Python, Python→WASM, WASM→Python, WASM→WASM, and built-in→third-party calls without exposing runtime objects directly.

## Registration

A provider package declares its provided interfaces in generated/package metadata. The loader validates identity, interface schema, provider conflict, implementation availability, and permissions before registration.

## Consumer resolution

Consumers resolve through FreeCAD and never receive a provider runtime pointer.

## Resource routing

Provider-defined resources use FreeCAD-managed references. Method calls on such a resource are routed back to its owning provider execution context.

## Security

A provider cannot automatically grant authority it does not possess.

The first provider implementation should choose a simple authority rule and document it. Full capability delegation between extensions is deferred.

## Interface publication format

The package should include a generated inspectable interface description so AddonManager and tooling can reason about it without executing provider code.

Authoring syntax may be language-specific while normalizing to the common model.

## Initial limits

Start with:

- one provider per exact interface major version;
- synchronous operations;
- portable values/resources only;
- queued events;
- no arbitrary callback arguments;
- no provider-selection algorithms.

Async task resources can be added later.
