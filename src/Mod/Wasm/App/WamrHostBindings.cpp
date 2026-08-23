// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WamrHostBindings.h"

#include "WasmAbi.h"
#include "WasmHostApi.h"

#include <wasm_export.h>

#include <cstdint>
#include <iterator>
#include <limits>
#include <span>
#include <string>
#include <string_view>

namespace
{

Wasm::WamrInstanceContext* contextFor(wasm_exec_env_t execEnv)
{
    const auto moduleInstance = wasm_runtime_get_module_inst(execEnv);
    if (moduleInstance == nullptr) {
        return nullptr;
    }

    return static_cast<Wasm::WamrInstanceContext*>(
        wasm_runtime_get_custom_data(moduleInstance));
}

void setHostException(wasm_exec_env_t execEnv, const std::string& error)
{
    const auto moduleInstance = wasm_runtime_get_module_inst(execEnv);
    if (moduleInstance != nullptr) {
        wasm_runtime_set_exception(moduleInstance, error.c_str());
    }
}

Wasm::Abi::ErrorCode errorCodeFor(const Wasm::HostCallResult& result)
{
    if (result.errorCode != Wasm::Abi::ErrorCode::None) {
        return result.errorCode;
    }

    const std::string_view error = result.error;
    if (error.find("not granted") != std::string_view::npos) {
        return Wasm::Abi::ErrorCode::PermissionDenied;
    }
    if (error.find("handle") != std::string_view::npos) {
        return Wasm::Abi::ErrorCode::InvalidHandle;
    }
    if (error.find("unsupported") != std::string_view::npos
        || error.find("not available") != std::string_view::npos) {
        return Wasm::Abi::ErrorCode::Unsupported;
    }
    return Wasm::Abi::ErrorCode::HostFailure;
}

void freecadLog(wasm_exec_env_t execEnv, const std::uint8_t* text, std::uint32_t length)
{
    if (length != 0U && text == nullptr) {
        setHostException(execEnv, "freecad_log received an invalid text pointer");
        return;
    }

    auto* context = contextFor(execEnv);
    if (context == nullptr) {
        setHostException(execEnv, "freecad_log has no instance context");
        return;
    }
    if (length > context->maxRequestBytes) {
        setHostException(execEnv, "freecad_log input exceeds the configured request limit");
        return;
    }

    const auto result = context->hostApi.log(
        std::string_view(reinterpret_cast<const char*>(text), length), context->permissions);
    if (!result.ok) {
        setHostException(execEnv, result.error);
    }
}

std::int32_t freecadAlloc(wasm_exec_env_t execEnv, std::uint32_t size)
{
    auto* context = contextFor(execEnv);
    if (context == nullptr) {
        setHostException(execEnv, "freecad_alloc has no instance context");
        return 0;
    }
    if (size == 0U) {
        return 0;
    }
    if (size > context->maxResponseBytes) {
        setHostException(execEnv, "freecad_alloc exceeds the configured response limit");
        return 0;
    }

    const auto moduleInstance = wasm_runtime_get_module_inst(execEnv);
    void* nativeAddress = nullptr;
    const auto rawAddress = wasm_runtime_module_malloc(moduleInstance, size, &nativeAddress);
    if (rawAddress == 0U || nativeAddress == nullptr) {
        setHostException(execEnv, "freecad_alloc could not allocate its response");
        return 0;
    }
    if (rawAddress > std::numeric_limits<std::uint32_t>::max()) {
        wasm_runtime_module_free(moduleInstance, rawAddress);
        setHostException(execEnv, "freecad_alloc address is not wasm32");
        return 0;
    }

    const auto address = static_cast<std::uint32_t>(rawAddress);
    if (!context->responseAllocations.emplace(address, size).second) {
        wasm_runtime_module_free(moduleInstance, rawAddress);
        setHostException(execEnv, "freecad_alloc returned a duplicate address");
        return 0;
    }
    return static_cast<std::int32_t>(address);
}

std::int64_t freecadDispatch(wasm_exec_env_t execEnv,
                             const std::uint8_t* request,
                             std::uint32_t requestLength)
{
    if (requestLength != 0U && request == nullptr) {
        setHostException(execEnv, "freecad_dispatch received an invalid request pointer");
        return 0;
    }

    auto* context = contextFor(execEnv);
    if (context == nullptr) {
        setHostException(execEnv, "freecad_dispatch has no instance context");
        return 0;
    }
    if (requestLength > context->maxRequestBytes) {
        setHostException(execEnv, "freecad_dispatch input exceeds the configured request limit");
        return 0;
    }

    const auto requestBytes = requestLength == 0U
        ? std::span<const std::byte> {}
        : std::span<const std::byte>(reinterpret_cast<const std::byte*>(request), requestLength);
    const auto result = context->hostApi.dispatch(
        requestBytes, context->permissions, context->handles);
    const auto errorCode = result.ok ? Wasm::Abi::ErrorCode::None : errorCodeFor(result);
    const std::string response = Wasm::Abi::makeResponse(
        result.ok ? Wasm::Abi::ResponseStatus::Success : Wasm::Abi::ResponseStatus::Error,
        errorCode,
        result.ok ? std::string_view(result.payload) : std::string_view(result.error));
    if (response.size() > context->maxResponseBytes) {
        setHostException(execEnv, "freecad_dispatch response exceeds the configured limit");
        return 0;
    }
    if (response.size() > std::numeric_limits<std::uint32_t>::max()) {
        setHostException(execEnv, "freecad_dispatch response is too large");
        return 0;
    }

    const auto moduleInstance = wasm_runtime_get_module_inst(execEnv);
    std::uint32_t responseAddress = 0U;
    if (!response.empty()) {
        const auto rawResponseAddress = wasm_runtime_module_dup_data(
            moduleInstance, response.data(), response.size());
        if (rawResponseAddress == 0U) {
            setHostException(execEnv, "freecad_dispatch could not allocate its response");
            return 0;
        }
        if (rawResponseAddress > std::numeric_limits<std::uint32_t>::max()) {
            wasm_runtime_module_free(moduleInstance, rawResponseAddress);
            setHostException(execEnv, "freecad_dispatch response address is not wasm32");
            return 0;
        }
        responseAddress = static_cast<std::uint32_t>(rawResponseAddress);
    }

    if (responseAddress != 0U
        && !context->responseAllocations.emplace(responseAddress, response.size()).second) {
        wasm_runtime_module_free(moduleInstance, responseAddress);
        setHostException(execEnv, "freecad_dispatch returned a duplicate response address");
        return 0;
    }

    return static_cast<std::int64_t>(Wasm::Abi::packResponse(
        static_cast<std::uint32_t>(responseAddress),
        static_cast<std::uint32_t>(response.size())));
}

void freecadRelease(wasm_exec_env_t execEnv, std::uint32_t address)
{
    const auto moduleInstance = wasm_runtime_get_module_inst(execEnv);
    auto* context = contextFor(execEnv);
    if (moduleInstance == nullptr || context == nullptr) {
        setHostException(execEnv, "freecad_release has no instance context");
        return;
    }
    if (address == 0U) {
        return;
    }
    if (context->responseAllocations.erase(address) == 0U) {
        setHostException(execEnv, "freecad_release received an unknown response address");
        return;
    }
    wasm_runtime_module_free(moduleInstance, address);
}

NativeSymbol nativeSymbols[] = {
    {Wasm::Abi::AllocImport, reinterpret_cast<void*>(freecadAlloc), "(i)i", nullptr},
    {Wasm::Abi::LogImport, reinterpret_cast<void*>(freecadLog), "(*~)", nullptr},
    {Wasm::Abi::DispatchImport,
     reinterpret_cast<void*>(freecadDispatch),
     "(*~)I",
     nullptr},
    {Wasm::Abi::ReleaseImport,
     reinterpret_cast<void*>(freecadRelease),
     "(i)",
     nullptr},
};

}  // namespace

bool Wasm::registerWamrHostBindings()
{
    return wasm_runtime_register_natives(
        Abi::HostModule,
        nativeSymbols,
        static_cast<std::uint32_t>(std::size(nativeSymbols)));
}

bool Wasm::unregisterWamrHostBindings()
{
    return wasm_runtime_unregister_natives(Abi::HostModule, nativeSymbols);
}
