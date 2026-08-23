// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmManifest.h"
#include "WasmPermissions.h"

#include <cctype>
#include <fstream>
#include <sstream>
#include <unordered_set>

#include <nlohmann/json.hpp>

using namespace Wasm;

namespace
{
using Json = nlohmann::json;

struct ParseState
{
    std::vector<std::unordered_set<std::string>> objectKeys;
    std::string duplicateKey;
};

bool isAllowedKey(std::string_view key)
{
    return key == "name" || key == "api" || key == "entry" || key == "permissions";
}

std::string lowerExtension(const std::filesystem::path& path)
{
    std::string extension = path.extension().string();
    std::transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char value) {
        return static_cast<char>(std::tolower(value));
    });
    return extension;
}
}  // namespace

WasmManifest WasmManifest::loadFromFile(const std::filesystem::path& path)
{
    WasmManifest manifest;
    manifest.manifestPath = path;

    std::error_code fileError;
    const auto fileSize = std::filesystem::file_size(path, fileError);
    if (fileError) {
        return manifest;
    }
    if (fileSize > MaxManifestBytes) {
        manifest.parseErrors.emplace_back("manifest exceeds the maximum size");
        return manifest;
    }

    std::ifstream input(path);
    if (!input) {
        return manifest;
    }

    std::ostringstream buffer;
    buffer << input.rdbuf();
    manifest.manifestSource = buffer.str();
    if (manifest.manifestSource.size() > MaxManifestBytes) {
        manifest.parseErrors.emplace_back("manifest exceeds the maximum size");
        manifest.manifestSource.clear();
        return manifest;
    }

    ParseState parseState;
    const auto callback = [&parseState](int,
                                        Json::parse_event_t event,
                                        Json& parsed) {
        if (event == Json::parse_event_t::object_start) {
            parseState.objectKeys.emplace_back();
        } else if (event == Json::parse_event_t::object_end) {
            parseState.objectKeys.pop_back();
        } else if (event == Json::parse_event_t::key && !parseState.objectKeys.empty()) {
            const auto key = parsed.get<std::string>();
            if (!parseState.objectKeys.back().insert(key).second && parseState.duplicateKey.empty()) {
                parseState.duplicateKey = key;
            }
        }
        return true;
    };

    Json source;
    try {
        source = Json::parse(manifest.manifestSource, callback);
    } catch (const Json::parse_error& error) {
        manifest.parseErrors.emplace_back(std::string("manifest is not valid JSON: ") + error.what());
        return manifest;
    }

    if (!parseState.duplicateKey.empty()) {
        manifest.parseErrors.emplace_back(
            "manifest contains duplicate key '" + parseState.duplicateKey + "'");
    }

    if (!source.is_object()) {
        manifest.parseErrors.emplace_back("manifest root must be a JSON object");
        return manifest;
    }

    for (const auto& [key, value] : source.items()) {
        if (!isAllowedKey(key)) {
            manifest.parseErrors.emplace_back("manifest contains unsupported field '" + key + "'");
        }
    }

    const auto readString = [&source, &manifest](const char* key, std::string& target) {
        const auto it = source.find(key);
        if (it == source.end()) {
            return;
        }
        if (!it->is_string()) {
            manifest.parseErrors.emplace_back(std::string("manifest field '") + key + "' must be a string");
            return;
        }
        target = it->get<std::string>();
    };

    readString("name", manifest.manifestName);
    readString("api", manifest.manifestApi);
    readString("entry", manifest.manifestEntry);

    const auto permissions = source.find("permissions");
    if (permissions != source.end()) {
        if (!permissions->is_array()) {
            manifest.parseErrors.emplace_back("manifest field 'permissions' must be an array of strings");
        } else {
            for (const auto& permission : *permissions) {
                if (!permission.is_string()) {
                    manifest.parseErrors.emplace_back(
                        "manifest field 'permissions' must contain only strings");
                    break;
                }
                manifest.manifestPermissions.push_back(permission.get<std::string>());
            }
        }
    }

    return manifest;
}

const std::filesystem::path& WasmManifest::path() const
{
    return manifestPath;
}

const std::string& WasmManifest::source() const
{
    return manifestSource;
}

const std::string& WasmManifest::name() const
{
    return manifestName;
}

const std::string& WasmManifest::api() const
{
    return manifestApi;
}

const std::string& WasmManifest::entry() const
{
    return manifestEntry;
}

const std::vector<std::string>& WasmManifest::permissions() const
{
    return manifestPermissions;
}

std::optional<std::filesystem::path> WasmManifest::resolveEntryPath(std::string* error) const
{
    const auto setError = [error](std::string message) {
        if (error != nullptr) {
            *error = std::move(message);
        }
    };

    if (manifestEntry.empty()) {
        setError("manifest entry is empty");
        return std::nullopt;
    }

    const std::filesystem::path entryPath(manifestEntry);
    if (entryPath.has_root_path()) {
        setError("manifest entry must be relative to the addon directory");
        return std::nullopt;
    }

    std::error_code errorCode;
    const auto addonDirectory = std::filesystem::canonical(manifestPath.parent_path(), errorCode);
    if (errorCode) {
        setError("addon directory cannot be resolved: " + errorCode.message());
        return std::nullopt;
    }

    const auto resolvedEntry = std::filesystem::canonical(addonDirectory / entryPath, errorCode);
    if (errorCode) {
        setError("manifest entry cannot be resolved: " + errorCode.message());
        return std::nullopt;
    }

    const auto relativeEntry = resolvedEntry.lexically_relative(addonDirectory);
    if (relativeEntry.empty() || relativeEntry.is_absolute()) {
        setError("manifest entry resolves outside the addon directory");
        return std::nullopt;
    }
    for (const auto& component : relativeEntry) {
        if (component == "..") {
            setError("manifest entry resolves outside the addon directory");
            return std::nullopt;
        }
    }

    if (!std::filesystem::is_regular_file(resolvedEntry, errorCode) || errorCode) {
        setError("manifest entry is not a regular file");
        return std::nullopt;
    }
    const auto extension = lowerExtension(resolvedEntry);
    if (extension != ".wasm" && extension != ".aot") {
        setError("manifest entry must refer to a .wasm or .aot file");
        return std::nullopt;
    }

    return resolvedEntry;
}

bool WasmManifest::isLoaded() const
{
    return !manifestSource.empty();
}

std::vector<std::string> WasmManifest::validate() const
{
    std::vector<std::string> errors = parseErrors;

    if (!isLoaded()) {
        errors.emplace_back("manifest file is empty or unreadable");
        return errors;
    }

    if (manifestName.empty()) {
        errors.emplace_back("manifest is missing string field 'name'");
    }

    if (manifestApi.empty()) {
        errors.emplace_back("manifest is missing string field 'api'");
    } else if (manifestApi != SupportedApi) {
        errors.emplace_back(
            "manifest declares unsupported API '" + manifestApi + "' (expected '" + SupportedApi + "')");
    }

    if (manifestEntry.empty()) {
        errors.emplace_back("manifest is missing string field 'entry'");
    } else {
        std::string entryError;
        if (!resolveEntryPath(&entryError)) {
            errors.emplace_back(entryError);
        }
    }

    std::unordered_set<std::string> permissions;
    for (const auto& permission : manifestPermissions) {
        if (permission.empty()) {
            errors.emplace_back("manifest permissions must not contain empty strings");
        } else if (!isKnownPermission(permission)) {
            errors.emplace_back("manifest contains unsupported permission '" + permission + "'");
        } else if (!permissions.insert(permission).second) {
            errors.emplace_back("manifest contains duplicate permission '" + permission + "'");
        }
    }

    return errors;
}
