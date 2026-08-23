// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WamrInstance.h"

#include "WasmAbi.h"
#include "WasmHostApi.h"
#include "WamrHostBindings.h"

#include <wasm_export.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <limits>
#include <mutex>
#include <string>
#include <thread>
#include <utility>

struct Wasm::WamrInstance::Impl
{
    wasm_module_t module = nullptr;
    wasm_module_inst_t moduleInstance = nullptr;
    wasm_exec_env_t execEnv = nullptr;
    std::vector<std::uint8_t> wasmBytes;
    WamrInstanceContext context;
    std::shared_ptr<void> runtimeLease;
    std::size_t maxRequestBytes = 0U;
    std::size_t maxResponseBytes = 0U;
    std::int32_t maxInstructions = 0;
    unsigned timeoutMs = 0U;
    ExecutionPolicy executionPolicy = ExecutionPolicy::Sandboxed;
    bool poisoned = false;
    std::mutex callMutex;
};

namespace
{

std::string runtimeException(wasm_module_inst_t moduleInstance, std::string fallback)
{
    const auto* exception = wasm_runtime_get_exception(moduleInstance);
    if (exception != nullptr && exception[0] != '\0') {
        return exception;
    }
    return fallback;
}

Wasm::CallResult failure(std::string error)
{
    return {false, {}, std::move(error)};
}

}  // namespace

Wasm::WamrInstance::WamrInstance(std::unique_ptr<Impl> instanceImpl)
    : impl(std::move(instanceImpl))
{
}

Wasm::WamrInstance::~WamrInstance()
{
    if (impl == nullptr) {
        return;
    }

    impl->context.hostApi.clearTransactions();
    if (impl->execEnv != nullptr) {
        wasm_runtime_destroy_exec_env(impl->execEnv);
    }
    if (impl->moduleInstance != nullptr) {
        wasm_runtime_deinstantiate(impl->moduleInstance);
    }
    if (impl->module != nullptr) {
        wasm_runtime_unload(impl->module);
    }
}

std::unique_ptr<Wasm::WamrInstance> Wasm::WamrInstance::create(
    void* module,
    void* moduleInstance,
    void* execEnv,
    std::vector<std::uint8_t>&& wasmBytes,
    const WasmHostApi& hostApi,
    std::shared_ptr<void> runtimeLease,
    std::size_t maxRequestBytes,
    std::size_t maxResponseBytes,
    std::int32_t maxInstructions,
    unsigned timeoutMs,
    ExecutionPolicy executionPolicy)
{
    auto instanceImpl = std::make_unique<Impl>();
    instanceImpl->module = static_cast<wasm_module_t>(module);
    instanceImpl->moduleInstance = static_cast<wasm_module_inst_t>(moduleInstance);
    instanceImpl->execEnv = static_cast<wasm_exec_env_t>(execEnv);
    instanceImpl->wasmBytes = std::move(wasmBytes);
    instanceImpl->context.hostApi = hostApi;
    instanceImpl->context.permissions = hostApi.permissions();
    instanceImpl->context.maxRequestBytes = maxRequestBytes;
    instanceImpl->context.maxResponseBytes = maxResponseBytes;
    instanceImpl->runtimeLease = std::move(runtimeLease);
    instanceImpl->maxRequestBytes = maxRequestBytes;
    instanceImpl->maxResponseBytes = maxResponseBytes;
    instanceImpl->maxInstructions = maxInstructions;
    instanceImpl->timeoutMs = timeoutMs;
    instanceImpl->executionPolicy = executionPolicy;
    wasm_runtime_set_custom_data(instanceImpl->moduleInstance, &instanceImpl->context);
    return std::unique_ptr<WamrInstance>(new WamrInstance(std::move(instanceImpl)));
}

Wasm::CallResult Wasm::WamrInstance::call(std::string_view exportName,
                                           const std::vector<std::byte>& input)
{
    if (impl == nullptr) {
        return failure("WAMR instance is not initialized");
    }
    if (!impl->context.hostApi.isOnOwnerThread()) {
        return failure("WASM addon invocation must run on the addon owner thread");
    }

    std::lock_guard lock(impl->callMutex);
    if (impl->poisoned) {
        return failure("WAMR instance was terminated and cannot be reused");
    }

    if (exportName.empty()) {
        return failure("WASM export name must not be empty");
    }
    if (input.size() > impl->maxRequestBytes) {
        return failure("WASM call input exceeds the configured request limit");
    }
    if (input.size() > std::numeric_limits<std::int32_t>::max()) {
        return failure("WASM call input exceeds the i32 ABI limit");
    }

    const std::string exportNameString(exportName);
    const auto function = wasm_runtime_lookup_function(
        impl->moduleInstance, exportNameString.c_str());
    if (function == nullptr) {
        return failure("WASM export was not found: " + exportNameString);
    }

    if (wasm_func_get_param_count(function, impl->moduleInstance) != 2U
        || wasm_func_get_result_count(function, impl->moduleInstance) != 1U) {
        return failure("WASM export does not use the FreeCAD byte-buffer ABI");
    }

    wasm_valkind_t parameterTypes[2] = {};
    wasm_valkind_t resultTypes[1] = {};
    wasm_func_get_param_types(function, impl->moduleInstance, parameterTypes);
    wasm_func_get_result_types(function, impl->moduleInstance, resultTypes);
    if (parameterTypes[0] != WASM_I32 || parameterTypes[1] != WASM_I32
        || resultTypes[0] != WASM_I64) {
        return failure("WASM export has an incompatible FreeCAD byte-buffer ABI type");
    }

    const auto releaseInput = [this](std::uint64_t address) {
        if (address == 0U) {
            return;
        }
        wasm_runtime_module_free(impl->moduleInstance, address);
    };
    const auto releaseResponse = [this](std::uint32_t address) {
        const auto allocation = impl->context.responseAllocations.find(address);
        if (allocation == impl->context.responseAllocations.end()) {
            return false;
        }
        impl->context.responseAllocations.erase(allocation);
        wasm_runtime_module_free(impl->moduleInstance, address);
        return true;
    };

    std::uint64_t inputAddress = 0U;
    if (!input.empty()) {
        void* nativeInput = nullptr;
        inputAddress = wasm_runtime_module_malloc(
            impl->moduleInstance, input.size(), &nativeInput);
        if (inputAddress == 0U || nativeInput == nullptr
            || inputAddress > std::numeric_limits<std::uint32_t>::max()) {
            if (inputAddress != 0U) {
                releaseInput(inputAddress);
            }
            return failure("could not allocate WASM call input");
        }
        std::memcpy(nativeInput, input.data(), input.size());
    }

    wasm_val_t arguments[2] = {};
    arguments[0].kind = WASM_I32;
    arguments[0].of.i32 = static_cast<std::int32_t>(inputAddress);
    arguments[1].kind = WASM_I32;
    arguments[1].of.i32 = static_cast<std::int32_t>(input.size());
    wasm_val_t results[1] = {};
    results[0].kind = WASM_I64;

    std::atomic_bool finished = false;
    std::atomic_bool timedOut = false;
    std::condition_variable watchdogCondition;
    std::mutex watchdogMutex;
    std::thread watchdog;
    if (impl->executionPolicy == ExecutionPolicy::Sandboxed) {
        watchdog = std::thread([this,
                                &finished,
                                &timedOut,
                                &watchdogCondition,
                                &watchdogMutex] {
            std::unique_lock lock(watchdogMutex);
            const auto stopped = watchdogCondition.wait_for(
                lock,
                std::chrono::milliseconds(impl->timeoutMs),
                [&finished] { return finished.load(std::memory_order_acquire); });
            if (!stopped && !finished.load(std::memory_order_acquire)) {
                timedOut.store(true, std::memory_order_release);
                wasm_runtime_terminate(impl->moduleInstance);
            }
        });
    }

    bool initializedThreadEnv = false;
    if (!wasm_runtime_thread_env_inited()) {
        initializedThreadEnv = wasm_runtime_init_thread_env();
    }

    bool callOk = false;
    if (initializedThreadEnv || wasm_runtime_thread_env_inited()) {
        wasm_runtime_clear_exception(impl->moduleInstance);
#if defined(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING)
        if (impl->executionPolicy == ExecutionPolicy::Sandboxed) {
            wasm_runtime_set_instruction_count_limit(impl->execEnv, impl->maxInstructions);
        }
#endif
        callOk = wasm_runtime_call_wasm_a(
            impl->execEnv, function, 1U, results, 2U, arguments);
#if defined(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING)
        if (impl->executionPolicy == ExecutionPolicy::Sandboxed) {
            wasm_runtime_set_instruction_count_limit(impl->execEnv, -1);
        }
#endif
    }

    finished.store(true, std::memory_order_release);
    watchdogCondition.notify_one();
    if (watchdog.joinable()) {
        watchdog.join();
    }
    if (initializedThreadEnv) {
        wasm_runtime_destroy_thread_env();
    }

    if (timedOut.load(std::memory_order_acquire)) {
        if (inputAddress != 0U) {
            releaseInput(inputAddress);
        }
        impl->poisoned = true;
        return failure("WASM call timed out");
    }
    if (!callOk) {
        const auto error = runtimeException(impl->moduleInstance, "WASM call failed");
        if (inputAddress != 0U) {
            releaseInput(inputAddress);
        }
        if (error.find("instruction limit exceeded") != std::string::npos) {
            impl->poisoned = true;
            return failure("WASM call exceeded its instruction limit");
        }
        return failure(error);
    }

    const auto packedResponse = static_cast<std::uint64_t>(results[0].of.i64);
    const auto responseAddress = Abi::responseAddress(packedResponse);
    const auto responseLength = Abi::responseLength(packedResponse);
    if (responseLength > impl->maxResponseBytes) {
        if (inputAddress != 0U) {
            releaseInput(inputAddress);
        }
        if (responseAddress != 0U && responseAddress != inputAddress) {
            static_cast<void>(releaseResponse(responseAddress));
        }
        impl->poisoned = true;
        return failure("WASM export response exceeds the configured limit");
    }
    if ((responseLength == 0U && responseAddress != 0U)
        || (responseLength != 0U
            && (responseAddress == 0U
                || !wasm_runtime_validate_app_addr(
                    impl->moduleInstance, responseAddress, responseLength)))) {
        if (inputAddress != 0U) {
            releaseInput(inputAddress);
        }
        impl->poisoned = true;
        return failure("WASM export returned an invalid response buffer");
    }

    std::size_t responseAllocationSize = 0U;
    const bool responseIsInput = responseAddress != 0U && responseAddress == inputAddress;
    if (responseIsInput) {
        responseAllocationSize = input.size();
    } else if (responseAddress != 0U) {
        const auto allocation = impl->context.responseAllocations.find(responseAddress);
        if (allocation == impl->context.responseAllocations.end()) {
            if (inputAddress != 0U) {
                releaseInput(inputAddress);
            }
            impl->poisoned = true;
            return failure("WASM export returned an unowned response buffer");
        }
        responseAllocationSize = allocation->second;
    }
    if (responseLength > responseAllocationSize) {
        if (inputAddress != 0U) {
            releaseInput(inputAddress);
        }
        if (!responseIsInput && responseAddress != 0U) {
            static_cast<void>(releaseResponse(responseAddress));
        }
        impl->poisoned = true;
        return failure("WASM export response exceeds its allocation");
    }

    std::vector<std::byte> payload(responseLength);
    if (responseLength != 0U) {
        const auto* nativeResponse = static_cast<const std::byte*>(
            wasm_runtime_addr_app_to_native(impl->moduleInstance, responseAddress));
        if (nativeResponse == nullptr) {
            if (inputAddress != 0U) {
                releaseInput(inputAddress);
            }
            impl->poisoned = true;
            return failure("WASM export returned an unmappable response buffer");
        }
        std::memcpy(payload.data(), nativeResponse, responseLength);
        if (!responseIsInput) {
            static_cast<void>(releaseResponse(responseAddress));
        }
    }
    if (inputAddress != 0U) {
        releaseInput(inputAddress);
    }

    return {true, std::move(payload), {}};
}
