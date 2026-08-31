# Extension Architecture Glossary

**Status:** Normative vocabulary

## Extension

A third-party or built-in component that consumes the FreeCAD Extension API. An external extension may have an installable package and an execution profile. A built-in module may consume the API without being packaged as an Extension.

## Extension API

The stable, language-neutral public FreeCAD API intended for extension development.

It is independent of execution backend.

## Extension SDK

A language-specific developer package exposing the Extension API with language-native ergonomics.

## Extension interface

A versioned namespace of related operations, events, value types, and resource types.

Example:

```text
org.freecad.document@1
```

## Operation

A request from a consumer to an interface provider.

Example:

```text
org.freecad.document@1/get_object
```

## Event

A provider-originated notification delivered to subscribers through FreeCAD-managed event delivery.

## Provider

The implementation responsible for an interface. A provider may be FreeCAD core, a built-in module, or eventually a third-party extension.

## Consumer

Code that resolves and invokes an interface or subscribes to its events.

## Value

Portable data with value semantics. Examples include vectors, placements, records, enums, strings, and packed arrays.

## Resource

A reference to state or an object whose lifetime is managed by a provider or execution context. Examples include documents and topological shapes.

A resource is a semantic concept. A WASM backend may lower it to an opaque handle, but “handle” is not the public API type.

## Execution profile

The trust/runtime mode used to execute extension code.

Initial profiles:

- in-process;
- sandboxed.

## Execution context

The host-managed lifetime and scheduling context for running extension code.

## Attachment

A relationship between extension state and a FreeCAD scope such as the application, a document, or a view.

## Subscription

A resource representing registration for event delivery.

## ExtensionApiModel

The runtime-neutral normalized model of Extension interfaces.

## PythonApiModel

The normalized representation of FreeCAD's public Python API used to project existing APIs into `ExtensionApiModel`.

## WasmAbiModel

The backend-specific model that lowers Extension operations into the current WebAssembly binary ABI.

## Runtime backend

An implementation that executes extension code and realizes the Extension API contract. WAMR/WebAssembly is the initial sandbox backend.

## Legacy Python API

The existing FreeCAD Python API used through modules such as `FreeCAD` and `Part`. “Legacy” in this documentation describes architectural lineage; it does not imply scheduled removal.
