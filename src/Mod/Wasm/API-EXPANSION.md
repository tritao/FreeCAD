# FreeCAD Extension API Expansion

This document defines how the experimental FreeCAD Extension API grows beyond
the current curated surface. Wasm is the current runtime backend, not the
extension author's programming model. It is a design contract, not a promise
that every Python API is suitable for extension exposure.

The broader architecture documentation is indexed at
[`docs/extension/index.md`](../../../docs/extension/index.md).

## Source Of Truth

The dependency direction is fixed:

```text
.pyi declarations and extension metadata
                  |
                  v
        Python API model and type grammar
                  |
                  v
          Extension API model
             /            \
            v              v
      projected APIs   native adapters
             \            /
              v          v
                Wasm ABI model
                       |
          +------------+------------+
          v            v            v
       C++ SDK       Rust SDK    Python SDK
```

`python_api_model` owns Python signatures, types, decorators, and diagnostics.
The extension model adds only extension semantics such as capability, effect,
transaction policy, representation, and interface scope. The Wasm generator
lowers that model to wire types and SDK declarations; it must not become a
second parser for `.pyi` annotations or extension decorator strings.

## Identity Scope

Full operation identities are derived from context instead of repeated on
every entity:

1. `WasmExtensionApi.json` declares the package namespace, currently
   `org.freecad`.
2. A module or class declares an interface name and major version, such as
   `document@1` or `part@1`.
3. A method, attribute access, or adapter declares only a local operation ID,
   such as `is_saved` or `shape_is_valid`.

The canonical identity is derived as:

```text
<namespace>.<interface>@<major>/<local-id>
```

For example, a declaration in the `document@1` interface with local ID
`is_saved` becomes `org.freecad.document@1/is_saved`. Model objects should
carry the interface context and local ID separately; serialized catalogs may
include the derived identity for lookup and diagnostics.

Interface names and local IDs are lowercase, stable, and language-neutral.
Python spelling, C++ naming, Rust naming, wire names, and numeric opcodes are
projections or compatibility aliases, not identity.

## Projections And Adapters

Every exposed operation belongs to exactly one category:

### Direct projection

A direct projection corresponds to a method or property access in the selected
`.pyi` surface. Its parameters, return type, receiver, and overload shape are
derived from the canonical Python API model. Extension metadata supplies the
operation ID, permission, effect, transaction policy, and any representation
classification that Python typing cannot express.

The current direct-projection slice is:

```text
Base.Vector.add, sub, dot, cross
Document.isSaved, getObject, openTransaction,
    commitTransaction, abortTransaction
DocumentObject.Label getter and setter
TopoShape.isNull, isValid, length, area, volume
```

Direct projections must not repeat authored `params` or `returns` in an ABI
catalog. A signature change in the `.pyi` model must flow through all generated
SDKs and update the derived wire fingerprint before an ABI lock is accepted.

### Native adapter

An adapter represents a host concept that is useful to guests but is not a
one-to-one Python declaration, such as addon document creation, `part.make_box`,
handle release, or a wire-specific constructor. Adapters may define their own
wire lowering, but their permission, ownership, transaction, and wire
signature metadata must be explicit.

Adapters must not pretend to be direct projections. They are reviewed as host
API additions and remain as typed declarations in
`src/Tools/wasm_api_model/adapters.py` until a canonical `.pyi` declaration and
extension metadata can replace them.

## Capability And Lifetime Rules

New operations are deny-by-default. A missing permission is not unrestricted
access, and a manifest can request capabilities but cannot grant them. Every
operation proposal must specify:

```text
permission, effect, transaction policy, receiver/resource kind,
parameter and return types, failure behavior, ownership, and thread policy
```

Use `value` for immutable data encoded inline and `resource` for host-owned
objects represented by instance-scoped handles. Handle ownership is a
use-site decision: creation and transfer operations declare whether a token
is owned, borrowed, or consumed. Borrowed handles never cause the guest to
destroy a host object. Owned handles must have one release path and must be
invalidated when the Wasm instance is destroyed.

Document mutation operations require a host-approved `document.modify`
capability and an active transaction. File system, process, socket, GUI,
Coin/Pivy, and unrestricted Python reflection APIs are out of scope for the
initial expansion and require separate capability designs.

## ABI Compatibility

`wasm_abi.lock.toml` is the ABI lock, not a second API declaration. It reserves
numeric operation codes, wire names, and one compatibility signature.
The generated operation JSON is read-only output. Numeric IDs and retired IDs
are never reused. A changed wire
shape, ownership behavior, permission requirement, or failure contract needs
an explicit compatibility decision and catalog signature update.

The compatibility rules are:

1. Additive operations receive new local IDs and new numeric opcodes.
2. A published operation's numeric opcode and wire name do not change.
3. An incompatible interface change requires a new major interface version.
4. Removing an operation moves its lock entry to `abi.retired`; its ID and wire
   name remain reserved.
5. SDKs, host dispatch metadata, and ABI documentation are generated from the
   same merged model and lock.

## Expansion Order

The next API additions should follow increasing host risk:

1. More pure value operations: vector construction and arithmetic, rotations,
   placements, and bounded immutable collections.
2. Read-only document and geometry resources: names, labels, counts, topology
   queries, and bounded property reads.
3. Transaction-scoped document mutation: object creation, property writes, and
   explicit recompute operations with host limits.
4. Carefully bounded import/export adapters, each with dedicated file or
   external-resource permissions and cancellation semantics.
5. GUI, Coin/Pivy, asynchronous tasks, events, and unrestricted Python access
   only after separate capability and threading contracts exist.

Each expansion slice should add the model metadata, one ABI-lock entry per
published operation, generated SDK coverage, host dispatch metadata, and
focused positive and negative policy tests. API breadth is secondary to
keeping the source-of-truth and capability contracts unambiguous.

## Definition Of Done

An operation is ready for publication when its `.pyi` declaration and
extension metadata are sufficient to regenerate the C++, Rust, Python, and
host metadata surfaces without handwritten signature duplication. The ABI
lock has a stable derived identity, numeric opcode, wire name, and one
compatibility signature, and the operation has a test proving both its
permitted behavior and its denial behavior.
