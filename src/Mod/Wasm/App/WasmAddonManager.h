// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmAddon.h"
#include "WasmHostApi.h"

#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <vector>

namespace Wasm
{

class WasmAddonManager
{
public:
    WasmAddonManager();
    explicit WasmAddonManager(std::unique_ptr<IWasmRuntime> runtime);
    ~WasmAddonManager();

    AddonLoadResult load(const std::filesystem::path& manifestPath,
                         const std::vector<std::string>& grantedPermissions,
                         const RuntimeLimits& limits = {});
    CallResult invoke(std::string_view name, const std::vector<std::byte>& input = {});
    bool unload(std::string_view name);
    std::vector<std::string> loadedAddons() const;

private:
    struct LoadedAddon
    {
        explicit LoadedAddon(std::thread::id ownerThread)
            : hostApi(ownerThread)
        {
        }

        WasmHostApi hostApi;
        WasmAddon addon;
    };

    std::thread::id ownerThread;
    std::unique_ptr<IWasmRuntime> runtime;
    mutable std::mutex mutex;
    std::unordered_map<std::string, std::unique_ptr<LoadedAddon>> addons;
};

}  // namespace Wasm
