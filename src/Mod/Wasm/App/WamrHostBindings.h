// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmHandleTable.h"
#include "WasmHostApi.h"

#include <cstddef>
#include <cstdint>
#include <unordered_map>

namespace Wasm
{

struct WamrInstanceContext
{
    WasmHostApi hostApi;
    WasmHostApi::PermissionSet permissions;
    WasmHandleTable handles;
    std::unordered_map<std::uint32_t, std::size_t> responseAllocations;
    std::size_t maxRequestBytes = 0U;
    std::size_t maxResponseBytes = 0U;
};

bool registerWamrHostBindings();
bool unregisterWamrHostBindings();

}  // namespace Wasm
