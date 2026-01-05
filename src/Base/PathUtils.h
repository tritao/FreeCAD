// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef BASE_PATHUTILS_H
#define BASE_PATHUTILS_H

#include <filesystem>
#include <optional>
#include <string>
#include <string_view>

#ifndef FC_GLOBAL_H
# include <FCGlobal.h>
#endif

namespace Base
{

struct BaseExport NormalizePathOptions
{
    bool makeAbsolute {true};
    bool weaklyCanonical {true};
    bool createParentDirectories {false};
};

/// Convert a UTF-8 encoded string to a platform filesystem path.
/// On Windows this produces a wide path.
std::filesystem::path pathFromUtf8(std::string_view utf8);

/// Best-effort normalize a path (absolute + weakly_canonical) and optionally create parents.
/// Returns std::nullopt if normalization fails.
std::optional<std::filesystem::path> normalizePath(
    const std::filesystem::path& path,
    const NormalizePathOptions& options = {}
);

}  // namespace Base

#endif  // BASE_PATHUTILS_H

