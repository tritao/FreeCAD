# FreeCAD Wasm Host ABI

The experimental guest ABI is intentionally small. Guest modules import only
the functions below from the `freecad` module:

| Import | Signature | Purpose |
| --- | --- | --- |
| `freecad_alloc` | `(i32) -> i32` | Allocate a host-owned guest response buffer |
| `freecad_dispatch` | `(i32, i32) -> i64` | Dispatch a versioned binary host request |
| `freecad_release` | `(i32) -> void` | Release a response buffer returned by the host |
| `freecad_log` | `(i32, i32) -> void` | Write a permitted log message |

Addon entrypoints use the byte-buffer signature `(i32 input_ptr, i32
input_len) -> i64`. The low 32 bits of the return value contain the guest
address of the response, and the high 32 bits contain its byte length. A zero
length response has no buffer to release.
Response addresses are single-use host allocations; `freecad_release` rejects
addresses that were not returned by `freecad_dispatch` or `freecad_alloc` for
the same instance.
Request and response sizes are bounded by the instance runtime limits.
Addon entrypoints may return either the input buffer or a buffer obtained from
`freecad_alloc`. Returning an arbitrary guest-memory address is rejected. The
host copies the response and releases tracked allocations after the call.

## Request Envelope

All `freecad_dispatch` requests use little-endian fields:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | Magic bytes `FCWA` |
| 4 | 1 | ABI version, currently `1` |
| 5 | 1 | Operation code |
| 6 | 2 | Flags, currently `0` |
| 8 | 4 | Payload length in bytes |
| 12 | n | Operation payload |

The payload length must exactly match the remaining request size. Unknown
versions, flags, operations, malformed payloads, and denied capabilities fail
the host call. In WAMR these failures are surfaced as a Wasm exception; guest
code must not continue using a failed call's result.

## Operations

| Code | Operation | Permission | Payload | Response |
| ---: | --- | --- | --- | --- |
| 1 | `document.new` | `document.create` | `u32 name_length`, UTF-8 name | `u64` document handle |
| 2 | `part.make_box` | `geometry.create` | three `f64` dimensions | `u64` shape handle |
| 3 | `document.add_object` | `document.modify` | `u64` document handle, `u64` shape handle, `u32 name_length`, UTF-8 name | `u64` document object handle |
| 4 | `handle.release` | none | `u64` handle | empty |
| 5 | `base.vector.new` | `geometry.compute` | three `f64` coordinates | three `f64` coordinates |
| 6 | `base.vector.add` | `geometry.compute` | two inline vectors | one inline vector |
| 7 | `base.vector.dot` | `geometry.compute` | two inline vectors | one `f64` |
| 8 | `base.vector.cross` | `geometry.compute` | two inline vectors | one inline vector |
| 9 | `document.is_saved` | `document.read` | `u64` document handle | one `u8` boolean (`0` or `1`) |
| 10 | `document.get_object` | `document.read` | `u64` document handle, `u32` name length, UTF-8 name | `u64` document object handle |
| 11 | `part.topo_shape.is_null` | `geometry.read` | `u64` shape handle | one `u8` boolean (`0` or `1`) |
| 12 | `part.topo_shape.is_valid` | `geometry.read` | `u64` shape handle | one `u8` boolean (`0` or `1`) |
| 13 | `part.topo_shape.length` | `geometry.read` | `u64` shape handle | one `f64` |
| 14 | `part.topo_shape.area` | `geometry.read` | `u64` shape handle | one `f64` |
| 15 | `part.topo_shape.volume` | `geometry.read` | `u64` shape handle | one `f64` |

Handles are opaque and scoped to the instance that created them. Document and
document-object handles are borrowed references to host-owned objects. Shape handles
created by `part.make_box` are owned by the instance until released or until
the instance is destroyed.
`Base.Vector` is an inline value encoded as three little-endian `f64` values;
it is not represented by a host handle.

## Guest SDK

`Guest/WasmGuest.h` provides a small C++ client for the protocol. It uses the
same import names and can be included by a Wasm guest built with Clang. The
`examples/wasm/cpp/CapabilityAddon.cpp` example creates a document, box, and
feature using only the declared capabilities.
The hosted client exposes `allocateResponse(size)`, which returns a move-only
RAII `ResponseBuffer`; write the response through `data()` and transfer
ownership to the host with `take()`. Dropping the buffer releases it without
returning it from the entrypoint.

For freestanding guests without WASI or libc++, define
`FREECAD_WASM_FREESTANDING=1` to select `Guest/WasmGuestFreestanding.h`. The
example is built this way in the WAMR integration test and exports the byte-
buffer entrypoint `freecad_addon_entry`.

`Guest/FreeCADWasmGuest.cmake` provides the reusable `freecad_wasm_addon()`
CMake function used by that test. The same source can be built without a full
FreeCAD configure using `examples/wasm/cpp`; see its README for the required
Clang and `wasm-ld` settings. The build generates
`freecad_wasm_api.hpp`, stages `manifest.json` beside the Wasm module, and can
consume either the source-tree SDK or an installed `FreeCADWasmGuest` package.

`Guest/examples/CapabilityAddon.rs` is a matching `no_std` Rust guest. It uses
the generated Rust client and therefore the same imports, request envelope,
handle lifecycle, and response ownership rules as the C++ example. The WAMR
test build compiles it when
`rustc --target wasm32-unknown-unknown` is available, providing a language-
neutral ABI regression test without enabling WASI.

The build also emits `freecad_wasm_api.hpp` and `freecad_wasm_api.rs` from the
same versioned API model. These files provide typed handle wrappers, model
metadata, and typed transport facades for the declared operations. Both
facades use the narrow host ABI, so generated declarations cannot bypass host
policy. The generated C++ header delegates to `Wasm::Guest::Client`; the Rust
SDK is a `no_std` client with bounded request buffers. Operation IDs,
permissions, and mutation metadata remain in the neutral API model.
Operations that reference a `.pyi` symbol are validated against the selected
Python API model during generation. The initial value-type projection covers
`Base.Vector`; host-owned classes remain explicit handles. The current curated
read-only slice includes document state/object lookup and basic `TopoShape`
validity and mass-property queries, with `document.read` and `geometry.read`
kept separate from mutation permissions.

The host remains responsible for granting permissions from addon policy. The
guest request cannot grant itself additional capabilities. `WasmAddon` loads
the manifest and grants the intersection of requested permissions and the
host policy, then invokes the fixed `freecad_addon_entry` export.

## Python Module

The experimental `Wasm` module keeps loaded addons alive in a process-local
manager:

```python
import Wasm

metadata = Wasm.loadAddon(
    "/path/to/addon/manifest.json",
    ["document.create", "document.read", "document.modify",
     "geometry.create", "geometry.compute", "geometry.read"],
)
response = Wasm.invokeAddon(metadata["name"], b"")
Wasm.unloadAddon(metadata["name"])
```

`Wasm.loadAddon(path, permissions)` returns manifest metadata and applies the
supplied host permission policy. `Wasm.invokeAddon(name, input)` returns the
guest response as `bytes`; `Wasm.listAddons()` returns loaded addon names; and
`Wasm.unloadAddon(name)` removes an addon. Load and invocation failures raise
`RuntimeError`.

## Runtime Profiles and Provisioning

Addon manifests do not select a native runtime or execution mode. The FreeCAD
deployment selects a WAMR profile so an addon cannot request a different native
code-generation policy:

| Profile | Behavior |
| --- | --- |
| `INTERP` | Classic interpreter with instruction metering |
| `AOT` | Metered interpreter for sandboxed `.wasm`; trusted `.aot` execution is performance-only |
| `JIT` | Metered interpreter for sandboxed calls; trusted LLVM JIT is performance-only |

Pixi provisions these profiles as separate environments:

```sh
pixi run -e wasm configure-debug
pixi run -e wasm-aot configure-debug
pixi run -e wasm-jit configure-debug
```

The corresponding local rattler recipes are `package/wamr`,
`package/wamr-aot`, `package/wamr-jit`, and `package/wamr-compiler`. They share
the profile-specific build scripts and pin the same WAMR source archive. A
non-Pixi build can use an installed package with
`-DFREECAD_WAMR_PROVIDER=PACKAGE`, point at a source checkout with
`-DFREECAD_WAMR_PROVIDER=SOURCE -DFREECAD_WAMR_ROOT=...`, or use the verified
`FETCH` fallback.

All profiles disable WASI, multi-module loading, shared memory, threads, and
the mini-loader. The runtime rejects imports outside the explicitly registered
`freecad.*` function allowlist. WAMR's memory isolation is therefore combined
with FreeCAD's deny-by-default capability policy; it is not a general-purpose
WASI environment. All profiles compile instruction metering, and sandboxed
calls use the metered interpreter path. Native AOT/JIT execution cannot be
hard-interrupted in-process, so `.aot` artifacts and opt-in JIT calls are
outside the hard sandbox boundary and require an explicitly non-sandboxed
policy. Guest calls and host capability operations are confined to the
addon's owner thread; thread marshalling is a host integration responsibility,
not a guest escape hatch.

The portable addon artifact is a `.wasm` module. AOT and JIT are host policy
choices, not manifest fields or guest-visible runtime choices. `.aot` entries
are accepted only for an explicitly trusted AOT policy.

## Python Boundary

The native `Wasm` Python module manages FreeCAD addon instances; it does not
embed Pyodide. Pyodide is a separate browser/web adapter concern and should
reuse this capability contract rather than gain direct filesystem, process, or
WASI access. Native Python execution inside WAMR would be a separate backend
and must not weaken the existing host permission boundary.
