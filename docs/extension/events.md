# Extension Events

**Status:** Normative

## Overview

Events are first-class members of Extension interfaces. An event is not a raw callback pointer, Python signal object, Qt signal, or WASM export. It is a stable semantic notification delivered by FreeCAD.

Example:

```text
org.freecad.document@1

operations:
  get_object
  add_object

events:
  object_added
  object_removed
  object_changed
  transaction_committed
```

## Subscription API

Python:

```python
sub = fc.documents.object_changed.subscribe(on_object_changed)
...
sub.close()
```

Rust and C++ should expose equivalent language-native subscription resources.

## Delivery rules

Default delivery is:

- asynchronous with respect to the state change that created the event;
- queued;
- non-reentrant per execution context;
- serialized per execution context;
- ordered within one provider stream unless an event explicitly allows coalescing.

## Transaction-aware delivery

Document APIs should prefer meaningful post-commit events over every transient internal mutation.

```text
transaction starts
  set label
  set placement
  change property
  recompute
transaction commits
        |
        v
coherent events delivered
```

## Event reliability classes

### Lossless edge event

Every occurrence matters, e.g. `document_closed`, `command_invoked`, `task_finished`.

### Coalescible state event

Only the latest observable state may matter when a consumer falls behind, e.g. `selection_changed`, `camera_changed`, `object_changed`.

Coalescing policy belongs to the event definition.

## Payloads

Payloads use portable Extension API values/resources. They do not contain arbitrary `PyObject*`, `QObject*`, `SoNode*`, or C++ pointers.

## Failure handling

An exception or provider/runtime error in one subscriber must not corrupt the event dispatcher. The host should report the failure, apply a defined repeated-failure policy, and continue unrelated delivery where safe.

Sandbox termination automatically removes its subscriptions.

## Backpressure

The host may bound queues. Coalescible events can replace obsolete queued state; lossless events must not be silently dropped.

## Provider-defined events

A provided interface publishes events exactly like a core interface. Consumers do not need to know whether the provider implementation is C++, Python, or WASM.
