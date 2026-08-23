// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmAddonManager.h"

#include "WasmRuntimeFactory.h"

#include <algorithm>
#include <thread>
#include <utility>

Wasm::WasmAddonManager::WasmAddonManager()
    : WasmAddonManager(createWasmRuntime())
{
}

Wasm::WasmAddonManager::WasmAddonManager(std::unique_ptr<IWasmRuntime> runtimeValue)
    : ownerThread(std::this_thread::get_id()), runtime(std::move(runtimeValue))
{
}

Wasm::WasmAddonManager::~WasmAddonManager() = default;

Wasm::AddonLoadResult Wasm::WasmAddonManager::load(
    const std::filesystem::path& manifestPath,
    const std::vector<std::string>& grantedPermissions,
    const RuntimeLimits& limits)
{
    if (std::this_thread::get_id() != ownerThread) {
        return {false, "WASM addon loading must run on the addon owner thread"};
    }
    if (runtime == nullptr) {
        return {false, "no WebAssembly runtime is available"};
    }

    for (const auto& permission : grantedPermissions) {
        if (!isKnownPermission(permission)) {
            return {false, "host policy contains unsupported permission '" + permission + "'"};
        }
    }

    auto candidate = std::make_unique<LoadedAddon>(ownerThread);
    candidate->hostApi.setPermissions(grantedPermissions);
    const auto result = candidate->addon.load(
        manifestPath, *runtime, candidate->hostApi, limits);
    if (!result.ok) {
        return result;
    }

    const auto name = candidate->addon.manifest().name();
    std::lock_guard lock(mutex);
    addons.insert_or_assign(name, std::move(candidate));
    return {true, {}};
}

Wasm::CallResult Wasm::WasmAddonManager::invoke(
    std::string_view name, const std::vector<std::byte>& input)
{
    if (std::this_thread::get_id() != ownerThread) {
        return {false, {}, "WASM addon invocation must run on the addon owner thread"};
    }

    std::lock_guard lock(mutex);
    const auto it = addons.find(std::string(name));
    if (it == addons.end()) {
        return {false, {}, "WASM addon is not loaded: " + std::string(name)};
    }
    return it->second->addon.invoke(input);
}

bool Wasm::WasmAddonManager::unload(std::string_view name)
{
    if (std::this_thread::get_id() != ownerThread) {
        return false;
    }

    std::lock_guard lock(mutex);
    return addons.erase(std::string(name)) != 0U;
}

std::vector<std::string> Wasm::WasmAddonManager::loadedAddons() const
{
    std::lock_guard lock(mutex);
    std::vector<std::string> names;
    names.reserve(addons.size());
    for (const auto& [name, addon] : addons) {
        names.push_back(name);
    }
    std::sort(names.begin(), names.end());
    return names;
}
