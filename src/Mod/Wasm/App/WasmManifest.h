// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <cstddef>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace Wasm
{

class WasmManifest
{
public:
    static constexpr const char* SupportedApi = "org.freecad.wasm.api@0";
    static constexpr std::size_t MaxManifestBytes = 64U * 1024U;

    static WasmManifest loadFromFile(const std::filesystem::path& path);

    const std::filesystem::path& path() const;
    const std::string& source() const;
    const std::string& name() const;
    const std::string& api() const;
    const std::string& entry() const;
    const std::vector<std::string>& permissions() const;

    std::optional<std::filesystem::path> resolveEntryPath(std::string* error = nullptr) const;

    bool isLoaded() const;
    std::vector<std::string> validate() const;

private:
    std::filesystem::path manifestPath;
    std::string manifestSource;
    std::string manifestName;
    std::string manifestApi;
    std::string manifestEntry;
    std::vector<std::string> manifestPermissions;
    std::vector<std::string> parseErrors;
};

}  // namespace Wasm
