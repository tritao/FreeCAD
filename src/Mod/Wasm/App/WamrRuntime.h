// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmRuntime.h"

#include <memory>

namespace Wasm
{

class WamrRuntime final: public IWasmRuntime
{
public:
    WamrRuntime();
    ~WamrRuntime() override;

    RuntimeInfo info() const override;
    std::unique_ptr<IWasmInstance> instantiate(const std::filesystem::path& wasmPath,
                                               const RuntimeLimits& limits,
                                               WasmHostApi& hostApi) override;

private:
    std::shared_ptr<void> runtimeLease;
};

}  // namespace Wasm
