# FreeCAD C++ Extension

This example builds the capability extension used by the runtime integration
tests. It uses the freestanding C++ raw client, so it does not require WASI,
libc++, or a full FreeCAD build. Hosted extensions can use the generated
`FreeCAD::Extension` facade; the freestanding client is the advanced path.

## Requirements

- Clang with `wasm32-unknown-unknown` support
- `wasm-ld`
- CMake 3.16 or newer

## Build

From the FreeCAD source tree:

```sh
cmake -S examples/wasm/cpp -B build-wasm-cpp \
  -DFREECAD_WASM_GUEST_COMPILER="$(command -v clang++)" \
  -DFREECAD_WASM_GUEST_LINKER="$(command -v wasm-ld)"
cmake --build build-wasm-cpp
```

The bundle output is:

```text
build-wasm-cpp/
  freecad-capability-addon.wasm
  manifest.json
```

The source-tree build generates the typed C++ SDK header and the addon uses
the advanced `FreeCAD::Extension::Raw::RawClient` wrapper rather than encoding
ABI operations directly.

To build the installed example against an installed SDK:

```sh
cmake -S "$PREFIX/share/FreeCAD/Wasm/examples/cpp" \
  -B build-wasm-cpp-installed \
  -DCMAKE_PREFIX_PATH="$PREFIX" \
  -DFREECAD_EXTENSION_USE_INSTALLED_SDK=ON \
  -DFREECAD_WASM_GUEST_COMPILER="$(command -v clang++)" \
  -DFREECAD_WASM_GUEST_LINKER="$(command -v wasm-ld)"
cmake --build build-wasm-cpp-installed
```

The addon exports `freecad_addon_entry` and uses only the capabilities listed
in [the WASM ABI](../../../src/Mod/Wasm/ABI.md). The same source is compiled
by the in-tree WAMR fixture, keeping this example and the runtime regression
test on one build path.
