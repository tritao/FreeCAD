// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmRuntime.h"

#include <cstdint>
#include <memory>
#include <vector>

namespace Wasm
{

class WamrInstance final: public IWasmInstance
{
public:
    ~WamrInstance() override;

    CallResult call(std::string_view exportName,
                    const std::vector<std::byte>& input) override;

private:
    friend class WamrRuntime;

    struct Impl;

    static std::unique_ptr<WamrInstance> create(void* module,
                                                void* moduleInstance,
                                                void* execEnv,
                                                std::vector<std::uint8_t>&& wasmBytes,
                                                const WasmHostApi& hostApi,
                                                std::shared_ptr<void> runtimeLease,
                                                std::size_t maxRequestBytes,
                                                std::size_t maxResponseBytes,
                                                std::int32_t maxInstructions,
                                                unsigned timeoutMs,
                                                ExecutionPolicy executionPolicy);

    explicit WamrInstance(std::unique_ptr<Impl> impl);

    std::unique_ptr<Impl> impl;
};

}  // namespace Wasm
