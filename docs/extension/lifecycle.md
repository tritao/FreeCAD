# Extension Lifecycle and Attachment

**Status:** Normative

## Goals

The lifecycle model must avoid global singleton assumptions, give resources/subscriptions deterministic cleanup, support application/document/view-related state, work across in-process and sandboxed runtimes, and permit runtime backends to choose their own instance strategy.

## Execution context

An **execution context** is the host-managed unit that owns runtime state, subscriptions, and runtime-scoped resources for extension code.

An external extension normally has at least one application-level execution context.

The public model does not require `one extension == one WASM instance`; that is backend policy.

## Attachments

Extension state may be attached to:

```text
application
document
view
task/command
```

An attachment expresses semantic lifetime, not necessarily a separate runtime instance.

## Lifecycle notifications

The API should eventually expose lifecycle events/services equivalent to extension start, document open/close, view create/close, and application shutdown. These should use the ordinary event system instead of runtime-specific magic exports.

## Resource lifetime

Typical cases:

### Host-owned borrowed resource

Example: an open `Document`. It becomes invalid when the host object closes or the owning context ends.

### Extension/provider-owned resource

Example: a provider-created computation object. It may be explicitly closed, or the host releases it when the execution context ends.

### Value

No external lifetime. The value is copied/transferred.

## Invalid resources

Using a resource after its semantic lifetime ends must produce a deterministic invalid-resource failure, not undefined behavior.

Runtime backends must prevent stale references from resolving to unrelated objects.

## Subscription lifetime

A subscription ends when explicitly closed, the subscribed scope ends, the provider unloads, or the owning execution context ends.

## Runtime unload

Unloading an extension releases owned host resources, subscriptions, provider registrations, attachment state, and runtime instances/memory.

The runtime must not depend on guest cleanup code running successfully to preserve FreeCAD correctness.
