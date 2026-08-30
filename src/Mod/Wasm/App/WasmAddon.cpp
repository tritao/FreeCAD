// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmAddon.h"

#include "WasmAbi.h"
#include "WasmHostApi.h"
#include "freecad_wasm_dispatch_metadata.hpp"

#include <exception>
#include <sstream>
#include <utility>

using namespace Wasm;

AddonLoadResult WasmAddon::load(WasmManifest manifest,
                                IWasmRuntime& runtime,
                                WasmHostApi& hostApi,
                                const RuntimeLimits& limits)
{
    const auto errors = manifest.validate();
    if (!errors.empty()) {
        std::ostringstream out;
        for (const auto& error : errors) {
            if (out.tellp() > 0) {
                out << "; ";
            }
            out << error;
        }
        return {false, out.str()};
    }

    if (manifest.abiHash() != Generated::ApiCatalogSignature) {
        return {false,
                "addon ABI hash does not match the host catalog signature"};
    }

    const auto runtimeInfo = runtime.info();
    if (!runtimeInfo.available) {
        return {false, "no WebAssembly runtime is available"};
    }

    switch (limits.executionPolicy) {
    case ExecutionPolicy::Sandboxed:
        if (!runtimeInfo.supportsSandbox || !runtimeInfo.supportsHardTimeout) {
            return {false,
                    "configured WebAssembly runtime does not provide the required sandbox "
                    "and hard execution deadline"};
        }
        break;
    case ExecutionPolicy::TrustedAot:
        if (!runtimeInfo.supportsAot) {
            return {false, "configured WebAssembly runtime does not provide AOT execution"};
        }
        break;
    case ExecutionPolicy::TrustedJit:
        if (!runtimeInfo.supportsJit) {
            return {false, "configured WebAssembly runtime does not provide JIT execution"};
        }
        break;
    }

    std::string entryError;
    const auto entryPath = manifest.resolveEntryPath(&entryError);
    if (!entryPath) {
        return {false, entryError};
    }

    const auto previousPermissions = hostApi.permissions();
    std::vector<std::string> grantedPermissions;
    for (const auto& requestedPermission : manifest.permissions()) {
        if (previousPermissions.contains(requestedPermission)) {
            grantedPermissions.push_back(requestedPermission);
        }
    }
    hostApi.setPermissions(grantedPermissions);

    const auto restorePermissions = [&hostApi, &previousPermissions] {
        std::vector<std::string> permissions(previousPermissions.begin(), previousPermissions.end());
        hostApi.setPermissions(permissions);
    };

    std::unique_ptr<IWasmInstance> newInstance;
    try {
        newInstance = runtime.instantiate(*entryPath, limits, hostApi);
    } catch (const std::exception& error) {
        restorePermissions();
        return {false, std::string("runtime failed to instantiate addon: ") + error.what()};
    } catch (...) {
        restorePermissions();
        return {false, "runtime failed to instantiate addon with an unknown error"};
    }

    if (!newInstance) {
        restorePermissions();
        return {false, "runtime failed to instantiate addon"};
    }

    restorePermissions();
    instance = std::move(newInstance);
    addonManifest = std::move(manifest);
    return {true, {}};
}

AddonLoadResult WasmAddon::load(const std::filesystem::path& manifestPath,
                                IWasmRuntime& runtime,
                                WasmHostApi& hostApi,
                                const RuntimeLimits& limits)
{
    return load(WasmManifest::loadFromFile(manifestPath), runtime, hostApi, limits);
}

CallResult WasmAddon::invoke(const std::vector<std::byte>& input)
{
    if (instance == nullptr) {
        return {false, {}, "WASM addon is not loaded"};
    }
    return instance->call(Abi::AddonEntryExport, input);
}

bool WasmAddon::isLoaded() const
{
    return instance != nullptr;
}

const WasmManifest& WasmAddon::manifest() const
{
    return addonManifest;
}
