// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmRuntime.h"

using namespace Wasm;

RuntimeInfo NullWasmRuntime::info() const
{
    return {"none", false, false, false, false};
}

std::unique_ptr<IWasmInstance> NullWasmRuntime::instantiate(const std::filesystem::path&,
                                                           const RuntimeLimits&,
                                                           WasmHostApi&)
{
    return {};
}
