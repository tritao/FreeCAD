// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmRuntimeFactory.h"

#if defined(FREECAD_HAS_WAMR)
#include "WamrRuntime.h"
#endif

using namespace Wasm;

std::unique_ptr<IWasmRuntime> Wasm::createWasmRuntime()
{
#if defined(FREECAD_HAS_WAMR)
    return std::make_unique<WamrRuntime>();
#else
    return std::make_unique<NullWasmRuntime>();
#endif
}
