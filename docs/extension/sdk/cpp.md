# C++ Extension SDK Guide

**Status:** Guide

## Target experience

```cpp
#include <FreeCAD/Extension.hpp>

using namespace FreeCAD::Extension;

int run(Context& fc)
{
    auto doc = fc.documents().active();
    auto box = fc.part().makeBox(10.0, 20.0, 30.0);

    auto tx = doc.transaction("Create box");
    auto object = doc.addObject(box, "Box");
    object.setLabel("Bracket");
    tx.commit();
    return 0;
}
```

Exact spelling may evolve; this is the intended abstraction level.

## Build integration

```cmake
find_package(FreeCADExtensionSDK CONFIG REQUIRED)

freecad_add_extension(MyExtension
    SOURCES MyExtension.cpp
)
```

The helper should own sandbox target configuration, compiler target, exports, linker flags, generated raw SDK, ABI fingerprint injection, and package staging.

## Namespace

Recommended public namespace:

```cpp
FreeCAD::Extension
```

Advanced/raw APIs may live under `FreeCAD::Extension::Raw` or remain private generated implementation.

## Resources and errors

Use RAII/move-only ownership where appropriate. Borrowed host resources do not own the corresponding FreeCAD object. Stale resources return defined errors.

A small `Result<T>`-style API is suitable for freestanding/sandboxed builds. A later throwing facade should map the same semantic error categories.

## Freestanding constraints

The initial WASM backend may use `wasm32-unknown-unknown`, `-fno-exceptions`, `-fno-rtti`, and `-nostdlib`. Those are backend/toolchain concerns, not Extension API concepts.

## Distribution

An installed SDK can provide:

```text
include/FreeCAD/Extension/
lib/cmake/FreeCADExtensionSDK/
share/FreeCAD/Extension/
```
