// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <array>
#include <string_view>

namespace Wasm
{

inline constexpr std::array<std::string_view, 5> KnownPermissions {
    "console.log",
    "document.create",
    "document.modify",
    "geometry.create",
    "geometry.compute",
};

inline bool isKnownPermission(std::string_view permission)
{
    for (const auto knownPermission : KnownPermissions) {
        if (knownPermission == permission) {
            return true;
        }
    }
    return false;
}

}  // namespace Wasm
