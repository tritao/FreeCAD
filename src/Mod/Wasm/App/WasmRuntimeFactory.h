// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmRuntime.h"

#include <memory>

namespace Wasm
{

std::unique_ptr<IWasmRuntime> createWasmRuntime();

}  // namespace Wasm
