# Extension API Model

**Status:** Normative
**Audience:** API designers, model/generator implementers

## Scope

`ExtensionApiModel` is the runtime-neutral semantic contract from which language SDKs, documentation, compatibility checks, and runtime lowerings are derived.

It must not encode WebAssembly-specific transport details.

## Interface identity

An interface has a globally stable identity:

```text
<namespace>.<name>@<major-version>
```

Examples:

```text
org.freecad.document@1
org.freecad.part@1
org.freecad.bim@1
org.example.gears@1
```

The namespace owner is responsible for identity stability.

## Operation identity

Operations use:

```text
<interface-id>/<local-id>
```

Examples:

```text
org.freecad.document@1/get_object
org.freecad.document@1/is_saved
org.freecad.part@1/make_box
```

The stable ID is independent of generated language spelling.

A C++ SDK may expose `makeBox`, Rust may expose `make_box`, and Python may expose `make_box`; all refer to the same semantic operation.

## Interface contents

An interface may define operations, events, value types, resource types, enums, and records needed by those members.

## Operations

A semantic operation should capture at least:

- stable identity;
- source symbol/location where applicable;
- receiver resource, if any;
- parameters;
- return type;
- optional permission;
- semantic effect;
- transaction policy;
- version-introduction metadata;
- property read/write role where applicable.

## Effects

Recommended initial vocabulary:

```text
read
compute
create
modify
```

Do not duplicate the same fact with independently maintained booleans such as `mutates` unless the latter is mechanically derived.

## Values and resources

### Values

Values are portable data copied or transferred by value: primitives, UTF-8 strings, `Vector`, `Rotation`, `Placement`, records, enums, and packed arrays.

### Resources

Resources represent stateful or provider-owned objects: `Document`, `DocumentObject`, `TopoShape`, `Mesh`, future tasks, subscriptions, and provider-defined domain objects.

The semantic model uses `resource`, not `handle`. A runtime backend chooses how to represent the resource reference.

## Existing Python API projection

Existing FreeCAD APIs should be projected through:

```text
.pyi -> PythonApiModel -> ExtensionApiModel
```

Example metadata:

```python
@extension_interface(name="document", version=1)
@extension_type(representation="resource")
class Document:
    @extension_api(
        id="is_saved",
        permission="document.read",
        effect="read",
    )
    def isSaved(self) -> bool: ...
```

Runtime backends consume `ExtensionApiModel`; they must not independently parse `.pyi` decorators.

## Metadata permitted in `.pyi`

Semantic metadata may describe exposure, interface assignment, stable ID, permission, effect, transaction policy, introduced version, value/resource representation, property projection, and exceptional ownership semantics where truly semantic.

The following do **not** belong in `.pyi`:

- opcodes;
- byte encodings;
- WAMR;
- pointer/offset layouts;
- generated language names;
- request/response envelopes.

## Constructors and projection adapters

Python constructor signatures do not always map directly to portable creation operations.

A Python `__init__ -> None` may project into an Extension operation returning a new value/resource. Typed projection adapters are appropriate for these semantic mismatches.

Adapters should remain explicit and small rather than becoming a general-purpose transformation framework.

## Properties

Properties should preserve semantic behavior. A setter has semantic return type `None` even if a lower-level host implementation uses a success flag internally.

SDK generation should expose:

```text
C++    Result<void>
Rust   Result<()>
Python None or exception
```

## Versioning

The interface major version is part of identity. A breaking semantic change requires a new major interface identity.

Backend ABI versions and FreeCAD application versions are separate concepts:

```text
FreeCAD application version
    != Extension interface version
    != backend ABI version
    != SDK package version
```

## Non-projected definitions

The model must support APIs that do not originate from the existing Python API, including commands, events, UI registration, subscriptions, task/lifecycle services, and third-party provided interfaces.

These are not a different “extension-native API”; they are simply Extension API definitions whose authoring source is not a projection of an existing `.pyi` declaration.

## Model growth rule

Before adding another intermediate representation, ask:

> Does this remove real current duplication or prevent a real class of compatibility bugs?

The intended core pipeline is:

```text
PythonApiModel -> ExtensionApiModel -> runtime-specific model
```

For the current sandbox backend:

```text
ExtensionApiModel -> WasmAbiModel
```
