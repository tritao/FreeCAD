// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "../WasmAbi.h"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace Wasm
{

class WasmHostApi;

struct RuntimeInfo
{
    std::string name;
    bool available = false;
    bool supportsSandbox = false;
    bool supportsAot = false;
    bool supportsJit = false;
    // True when the runtime can enforce a hard execution deadline for
    // sandboxed bytecode calls. Native AOT/JIT calls do not provide this.
    bool supportsHardTimeout = false;
};

enum class ExecutionPolicy
{
    Sandboxed,
    TrustedAot,
    TrustedJit,
};

struct RuntimeLimits
{
    std::size_t maxModuleBytes = 16U * 1024U * 1024U;
    std::size_t maxMemoryBytes = 64U * 1024U * 1024U;
    std::size_t maxHostHeapBytes = 8U * 1024U * 1024U;
    std::size_t maxRequestBytes = 8U * 1024U * 1024U;
    std::size_t maxResponseBytes = 8U * 1024U * 1024U;
    std::size_t maxStackBytes = 256U * 1024U;
    // Enforced by the metered interpreter path. Native AOT/JIT execution does
    // not provide a hard instruction or wall-clock deadline in-process.
    std::int32_t maxInstructions = 10'000'000;
    unsigned timeoutMs = 5000U;
    // This is selected by host policy, never by the addon manifest.
    ExecutionPolicy executionPolicy = ExecutionPolicy::Sandboxed;
};

struct CallResult
{
    bool ok = false;
    std::vector<std::byte> payload;
    std::string error;
    Abi::ErrorCode errorCode = Abi::ErrorCode::None;
};

class IWasmInstance
{
public:
    virtual ~IWasmInstance() = default;
    virtual CallResult call(std::string_view exportName, const std::vector<std::byte>& input) = 0;
};

class IWasmRuntime
{
public:
    virtual ~IWasmRuntime() = default;
    virtual RuntimeInfo info() const = 0;
    virtual std::unique_ptr<IWasmInstance> instantiate(const std::filesystem::path& wasmPath,
                                                       const RuntimeLimits& limits,
                                                       WasmHostApi& hostApi) = 0;
};

class NullWasmRuntime final: public IWasmRuntime
{
public:
    RuntimeInfo info() const override;
    std::unique_ptr<IWasmInstance> instantiate(const std::filesystem::path& wasmPath,
                                               const RuntimeLimits& limits,
                                               WasmHostApi& hostApi) override;
};

}  // namespace Wasm
