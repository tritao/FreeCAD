// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmManifest.h"
#include "WasmRuntime.h"

#include <cstddef>
#include <filesystem>
#include <memory>
#include <vector>

namespace Wasm
{

class WasmHostApi;

struct AddonLoadResult
{
    bool ok = false;
    std::string error;
};

class WasmAddon
{
public:
    AddonLoadResult load(WasmManifest manifest,
                         IWasmRuntime& runtime,
                         WasmHostApi& hostApi,
                         const RuntimeLimits& limits = {});
    AddonLoadResult load(const std::filesystem::path& manifestPath,
                         IWasmRuntime& runtime,
                         WasmHostApi& hostApi,
                         const RuntimeLimits& limits = {});

    CallResult invoke(const std::vector<std::byte>& input = {});

    bool isLoaded() const;
    const WasmManifest& manifest() const;

private:
    WasmManifest addonManifest;
    std::unique_ptr<IWasmInstance> instance;
};

}  // namespace Wasm
