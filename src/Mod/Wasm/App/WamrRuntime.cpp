// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WamrRuntime.h"

#include "WasmAbi.h"
#include "WamrHostBindings.h"
#include "WamrInstance.h"

#include <wasm_export.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <span>
#include <limits>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace
{

std::mutex runtimeMutex;
std::size_t runtimeUsers = 0U;
bool runtimeInitialized = false;
bool bindingsRegistered = false;

void releaseRuntime()
{
    std::lock_guard lock(runtimeMutex);
    if (runtimeUsers == 0U) {
        return;
    }

    --runtimeUsers;
    if (runtimeUsers == 0U) {
        if (bindingsRegistered) {
            static_cast<void>(Wasm::unregisterWamrHostBindings());
            bindingsRegistered = false;
        }
        if (runtimeInitialized) {
            wasm_runtime_destroy();
            runtimeInitialized = false;
        }
    }
}

std::shared_ptr<void> acquireRuntime()
{
    std::lock_guard lock(runtimeMutex);
    if (runtimeUsers == 0U) {
        if (!wasm_runtime_init()) {
            return {};
        }
        runtimeInitialized = true;
        if (!Wasm::registerWamrHostBindings()) {
            wasm_runtime_destroy();
            runtimeInitialized = false;
            return {};
        }
        bindingsRegistered = true;
    }

    ++runtimeUsers;
    return {reinterpret_cast<void*>(1), [](void*) { releaseRuntime(); }};
}

bool checkedUint32(std::size_t value, std::uint32_t* result)
{
    if (value > std::numeric_limits<std::uint32_t>::max()) {
        return false;
    }
    *result = static_cast<std::uint32_t>(value);
    return true;
}

bool isAllowedImport(const wasm_import_t& import)
{
    if (import.kind != WASM_IMPORT_EXPORT_KIND_FUNC
        || import.module_name == nullptr || import.name == nullptr
        || std::string_view(import.module_name) != Wasm::Abi::HostModule) {
        return false;
    }

    const std::string_view name(import.name);
    return name == Wasm::Abi::AllocImport
        || name == Wasm::Abi::DispatchImport
        || name == Wasm::Abi::LogImport
        || name == Wasm::Abi::ReleaseImport;
}

bool hasSignature(const wasm_import_t& import,
                  std::span<const wasm_valkind_t> parameters,
                  std::span<const wasm_valkind_t> results)
{
    if (import.u.func_type == nullptr
        || wasm_func_type_get_param_count(import.u.func_type) != parameters.size()
        || wasm_func_type_get_result_count(import.u.func_type) != results.size()) {
        return false;
    }

    for (std::uint32_t index = 0; index < parameters.size(); ++index) {
        if (wasm_func_type_get_param_valkind(import.u.func_type, index) != parameters[index]) {
            return false;
        }
    }
    for (std::uint32_t index = 0; index < results.size(); ++index) {
        if (wasm_func_type_get_result_valkind(import.u.func_type, index) != results[index]) {
            return false;
        }
    }
    return true;
}

bool hasAllowedSignature(const wasm_import_t& import)
{
    constexpr std::array<wasm_valkind_t, 2> twoI32 {WASM_I32, WASM_I32};
    constexpr std::array<wasm_valkind_t, 1> oneI32 {WASM_I32};
    constexpr std::array<wasm_valkind_t, 1> oneI64 {WASM_I64};
    constexpr std::array<wasm_valkind_t, 0> noValues {};

    const std::string_view name(import.name);
    if (name == Wasm::Abi::AllocImport) {
        return hasSignature(import, oneI32, oneI32);
    }
    if (name == Wasm::Abi::LogImport) {
        return hasSignature(import, twoI32, noValues);
    }
    if (name == Wasm::Abi::DispatchImport) {
        return hasSignature(import, twoI32, oneI64);
    }
    if (name == Wasm::Abi::ReleaseImport) {
        return hasSignature(import, oneI32, noValues);
    }
    return false;
}

bool validateImports(wasm_module_t module)
{
    const auto importCount = wasm_runtime_get_import_count(module);
    if (importCount < 0) {
        return false;
    }

    for (std::int32_t index = 0; index < importCount; ++index) {
        wasm_import_t import {};
        wasm_runtime_get_import_type(module, index, &import);
        if (!isAllowedImport(import) || !hasAllowedSignature(import)) {
            return false;
        }
    }
    return true;
}

std::string lowerExtension(const std::filesystem::path& path)
{
    auto extension = path.extension().string();
    std::transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char value) {
        return static_cast<char>(std::tolower(value));
    });
    return extension;
}

}  // namespace

Wasm::WamrRuntime::WamrRuntime()
    : runtimeLease(acquireRuntime())
{
}

Wasm::WamrRuntime::~WamrRuntime() = default;

Wasm::RuntimeInfo Wasm::WamrRuntime::info() const
{
#if defined(FREECAD_WAMR_SUPPORTS_AOT)
    constexpr bool supportsAot = true;
#else
    constexpr bool supportsAot = false;
#endif
#if defined(FREECAD_WAMR_SUPPORTS_JIT)
    constexpr bool supportsJit = true;
#else
    constexpr bool supportsJit = false;
#endif
#if defined(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING)
    constexpr bool supportsInstructionMetering = true;
#else
    constexpr bool supportsInstructionMetering = false;
#endif
    return {"wamr", runtimeLease != nullptr, runtimeLease != nullptr, supportsAot, supportsJit,
            supportsInstructionMetering, runtimeLease != nullptr};
}

std::unique_ptr<Wasm::IWasmInstance> Wasm::WamrRuntime::instantiate(
    const std::filesystem::path& wasmPath,
    const RuntimeLimits& limits,
    WasmHostApi& hostApi)
{
    if (runtimeLease == nullptr || !hostApi.isOnOwnerThread()) {
        return {};
    }

    const auto extension = lowerExtension(wasmPath);
    switch (limits.executionPolicy) {
    case ExecutionPolicy::Sandboxed:
        // Native artifacts cannot be interrupted by WAMR's interpreter
        // metering, so only portable bytecode is accepted across the hard
        // sandbox boundary.
        if (extension != ".wasm") {
            return {};
        }
        break;
    case ExecutionPolicy::TrustedAot:
        if (extension != ".aot") {
            return {};
        }
        break;
    case ExecutionPolicy::TrustedJit:
        if (extension != ".wasm") {
            return {};
        }
        break;
    }

    const auto maxResponseBytes = std::min(limits.maxResponseBytes, limits.maxMemoryBytes);
    if (limits.maxModuleBytes == 0U || limits.maxMemoryBytes == 0U
        || limits.maxHostHeapBytes == 0U || limits.maxRequestBytes == 0U
        || maxResponseBytes == 0U
        || limits.maxStackBytes == 0U) {
        return {};
    }
    if (limits.executionPolicy == ExecutionPolicy::Sandboxed
        && (limits.maxInstructions <= 0 || limits.timeoutMs == 0U)) {
        return {};
    }

    std::error_code fileError;
    const auto fileSize = std::filesystem::file_size(wasmPath, fileError);
    if (fileError || fileSize == 0U || fileSize > limits.maxModuleBytes
        || fileSize > std::numeric_limits<std::uint32_t>::max()) {
        return {};
    }

    std::uint32_t stackSize = 0U;
    std::uint32_t hostHeapSize = 0U;
    if (!checkedUint32(limits.maxStackBytes, &stackSize)
        || !checkedUint32(limits.maxHostHeapBytes, &hostHeapSize)) {
        return {};
    }

    constexpr std::uint64_t wasmPageSize = 64U * 1024U;
    const auto maxMemoryBytes = static_cast<std::uint64_t>(limits.maxMemoryBytes);
    const auto maxMemoryPages = maxMemoryBytes / wasmPageSize
        + (maxMemoryBytes % wasmPageSize == 0U ? 0U : 1U);
    if (maxMemoryPages == 0U
        || maxMemoryPages > std::numeric_limits<std::uint32_t>::max()) {
        return {};
    }

    std::vector<std::uint8_t> wasmBytes(static_cast<std::size_t>(fileSize));
    std::ifstream input(wasmPath, std::ios::binary);
    if (!input.good()
        || !input.read(reinterpret_cast<char*>(wasmBytes.data()), wasmBytes.size())) {
        return {};
    }

    char errorBuffer[512] = {};
    auto module = wasm_runtime_load(
        wasmBytes.data(), static_cast<std::uint32_t>(wasmBytes.size()), errorBuffer, sizeof(errorBuffer));
    if (module == nullptr) {
        return {};
    }
    if (!validateImports(module)) {
        wasm_runtime_unload(module);
        return {};
    }

    InstantiationArgs2* args = nullptr;
    if (!wasm_runtime_instantiation_args_create(&args)) {
        wasm_runtime_unload(module);
        return {};
    }
    wasm_runtime_instantiation_args_set_default_stack_size(args, stackSize);
    wasm_runtime_instantiation_args_set_host_managed_heap_size(args, hostHeapSize);
    wasm_runtime_instantiation_args_set_max_memory_pages(
        args, static_cast<std::uint32_t>(maxMemoryPages));

    auto moduleInstance = wasm_runtime_instantiate_ex2(
        module, args, errorBuffer, sizeof(errorBuffer));
    wasm_runtime_instantiation_args_destroy(args);
    if (moduleInstance == nullptr) {
        wasm_runtime_unload(module);
        return {};
    }

#if defined(FREECAD_WAMR_SUPPORTS_JIT)
    // Keep sandboxed bytecode on the metered interpreter path. LLVM JIT is an
    // explicit performance mode for callers that do not require the sandbox.
    const auto runningMode = limits.executionPolicy == ExecutionPolicy::TrustedJit
        ? Mode_LLVM_JIT
        : Mode_Interp;
    if (!wasm_runtime_set_running_mode(moduleInstance, runningMode)) {
        wasm_runtime_deinstantiate(moduleInstance);
        wasm_runtime_unload(module);
        return {};
    }
#endif

    auto execEnv = wasm_runtime_create_exec_env(moduleInstance, stackSize);
    if (execEnv == nullptr) {
        wasm_runtime_deinstantiate(moduleInstance);
        wasm_runtime_unload(module);
        return {};
    }

    return WamrInstance::create(module,
                                moduleInstance,
                                execEnv,
                                std::move(wasmBytes),
                                hostApi,
                                runtimeLease,
                                limits.maxRequestBytes,
                                maxResponseBytes,
                                limits.maxInstructions,
                                limits.timeoutMs,
                                limits.executionPolicy);
}
