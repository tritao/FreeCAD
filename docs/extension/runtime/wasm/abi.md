# WebAssembly Binary ABI

**Status:** Backend specification snapshot
**Reference snapshot:** `wasm-runtime-bindings` at `ca90cf9b280b9f3a73c0461f70d6aa3624b6a0fd`

This page documents the current backend shape. It is not the public Extension API contract and may evolve under its own compatibility rules.

## Guest imports

```text
freecad_alloc    (i32) -> i32
freecad_dispatch (i32, i32) -> i64
freecad_release  (i32) -> void
freecad_log      (i32, i32) -> void
```

## Extension entrypoint

Current shape:

```text
(i32 input_ptr, i32 input_len) -> i64
```

The packed return carries address and length. Public tooling should hide this detail.

## Request envelope

```text
offset  size  field
0       4     magic "FCWA"
4       1     ABI version
5       1     operation code
6       2     flags
8       4     payload length
12      N     payload
```

## Response envelope

```text
offset  size  field
0       4     magic "FCWR"
4       1     ABI version
5       1     status
6       1     error code
7       1     flags
8       4     payload length
12      N     payload/error
```

A valid semantic `false` is distinct from operation failure.

## Primitive encoding

Current concepts include:

```text
bool      -> u8
f64       -> IEEE f64
string    -> u32 length + UTF-8 bytes
resource  -> opaque u64 token
Vector    -> 3 x f64 inline
None      -> empty payload
```

## Resources

Tokens are execution-context scoped and validated by the host. Host-owned and extension-owned resource lifetimes remain semantic concepts above the raw token.

## Errors

Current backend categories include invalid request, permission denied, invalid resource/handle, unsupported, limit exceeded, host failure, and protocol error.

Invalid guest memory may terminate/trap the sandbox instead of becoming a semantic API error.

## Operation locking

Published mapping is recorded in `wasm_abi.lock.toml`.

Recommended eventual lock shape:

```toml
[operations."org.freecad.document@1/is_saved"]
opcode = 9
wire_name = "document.is_saved"
signature = "sha256:..."
```

Generated language method names and source dependency lists should not be compatibility facts unless there is a specific reason to freeze them.

## Opcode width

The current one-byte opcode caps the direct global space at 255. This is acceptable for the experiment but must not leak into `ExtensionApiModel`.

## Bulk data

The next useful ABI additions are likely bytes and packed arrays (`f64`, `Vector3`, `u32`). Prefer straightforward copying first; zero-copy should be benchmark-driven.
