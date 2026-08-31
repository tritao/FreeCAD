# Extension Threading and Reentrancy

**Status:** Normative

## Principle

Extension authors should reason about stable scheduling guarantees, not FreeCAD's internal thread identities. The host owns thread affinity for FreeCAD objects, GUI objects, and provider implementations.

## Execution classes

### `serialized`

The operation executes through a serialized host domain suitable for FreeCAD model access and mutation. This is the default unless explicitly specified otherwise.

### `ui`

The operation executes on the FreeCAD GUI thread. UI-facing APIs use this class.

### `concurrent`

The operation is explicitly safe to execute concurrently and does not require serialized FreeCAD model access. Pure value computation may use this class.

## Why not `main_thread=true`

The public contract should avoid exposing implementation-specific thread names where the semantic guarantee is “serialized model access”. A backend may implement `serialized` using FreeCAD's main thread today and a different dispatcher later.

## Caller behavior

A caller may invoke an operation from any runtime thread supported by its SDK. The host is responsible for marshalling the request to the required execution class.

## Event delivery

Default event callback behavior:

- one callback at a time per execution context;
- callbacks are delivered in a host-defined serialized callback domain;
- callbacks are not nested while another callback for the same context is active;
- events generated during a callback are queued.

## Calls from event handlers

An event handler may synchronously call Extension API operations. If those operations generate events, the resulting events are queued and delivered after the current callback returns.

## Provider calls

When third-party provided interfaces are supported, provider calls execute through the provider's execution context. FreeCAD owns runtime crossing, scheduling, failure translation, and dead-provider handling.

Recursive interface-call cycles may need explicit protection. Arbitrary unbounded synchronous reentrancy is not guaranteed.

## Python considerations

The in-process Python binding obeys the same semantic scheduling rules as sandboxed callers. A synchronous binding may block while the host marshals work to the correct domain.

The implementation must respect the GIL and FreeCAD's GUI/model constraints without exposing those mechanics as the public contract.

## Long-running work

Long computations should not occupy the serialized or UI domain unnecessarily. A future task resource should support worker execution with progress/result events and serialized application of results.
