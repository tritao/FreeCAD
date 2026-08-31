# Extension Security Model

**Status:** Architecture / normative where stated

## Threat boundary

The sandbox protects FreeCAD only if privileged capabilities are reachable exclusively through controlled host interfaces.

WebAssembly memory isolation by itself does not prevent an extension from modifying documents, reading files, or accessing the network if unrestricted host calls are exposed.

## Sandboxed profile

The sandboxed profile should combine:

```text
runtime memory isolation
restricted host imports
resource validation
coarse permissions
bounded memory/execution
lifecycle cleanup
transaction cleanup
```

## Resource safety

Opaque backend references must be scoped to an execution context, validated before host access, invalidated when semantic lifetime ends, and protected from stale-reference reuse.

## Host input validation

All boundary data is untrusted. The host validates request structure, lengths/offsets, enums, UTF-8 where required, resource references, and semantic parameter constraints.

## In-process trust

The in-process Python profile is trusted code. The Extension API may improve stability and portability, but it does not remove Python's process authority.

Security UX must not conflate API usage with sandboxing.

## Denial of service

The sandbox should eventually support limits for memory, execution time/fuel where supported, event queue size, resource counts, and log/output volume.

Limits are runtime policy and can evolve independently from interface identity.

## Fault containment

A malformed or crashing sandboxed extension should terminate/disable its execution context without corrupting FreeCAD host memory. Owned resources and subscriptions must still be cleaned up by the host.
