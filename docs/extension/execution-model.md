# Extension Execution Model

**Status:** Architecture with normative guarantees

## Principle

The Extension API is independent of where extension code executes. An execution profile determines trust and runtime mechanics, not API identity.

## In-process profile

The in-process profile covers ordinary CPython code and trusted built-in integrations.

Characteristics:

- executes inside the FreeCAD process;
- can use the stable Extension API;
- may also use existing implementation-level APIs;
- is not a security sandbox;
- should invoke Extension services directly rather than routing through a binary guest ABI.

A package using unrestricted in-process Python must be treated as having process-level authority.

## Sandboxed profile

The initial sandboxed profile is WebAssembly/WAMR.

Characteristics:

- only explicitly exposed host capabilities are available;
- resources are represented through runtime-safe references;
- permissions can be enforced at the host boundary;
- runtime memory/execution limits may be applied;
- SDKs can be generated for multiple source languages.

## Semantic equivalence

When both profiles expose an operation, observable FreeCAD semantics should match: validation, transaction expectations, scheduling guarantees, event consequences, semantic return value, and FreeCAD-side error category.

Transport failures may be backend-specific.

## Service boundary

Preferred implementation:

```text
CPython facade --------\
                        > Extension service implementation -> FreeCAD internals
WASM host dispatch ----/
```

Do not independently reimplement application semantics in each SDK/backend.

## Reentrancy

Default rule:

- event delivery is queued;
- an execution context processes one event callback at a time;
- new events generated while handling an event are queued for later delivery;
- synchronous API operations called by the current handler are allowed.

Provider-to-provider calls may require cycle detection or bounded reentrancy when third-party interfaces are implemented.

## Failures

The public error model should distinguish invalid arguments, unavailable interfaces/resources, permission denied, invalid lifecycle state, operation failure, and cancellation/timeout where supported.

A malformed guest-memory request is not a portable semantic error and may terminate the sandboxed context.

## Alternate backends

A future backend could be another WebAssembly runtime, the Component Model, an out-of-process RPC sandbox, or another capability runtime. Such a backend should lower `ExtensionApiModel` without changing normal extension source code.
