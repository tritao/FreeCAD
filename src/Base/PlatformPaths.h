// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef BASE_PLATFORMPATHS_H
#define BASE_PLATFORMPATHS_H

#include <filesystem>
#include <optional>
#include <string>

#ifndef FC_GLOBAL_H
# include <FCGlobal.h>
#endif

namespace Base
{

struct BaseExport StandardPaths
{
    std::filesystem::path home;
    std::filesystem::path config;
    std::filesystem::path data;
    std::filesystem::path cache;
    std::filesystem::path temp;
};

/// Returns platform default locations for home/config/data/cache/temp.
///
/// Notes:
/// - On Linux/BSD follows XDG_*_HOME when set, otherwise defaults under HOME.
/// - On macOS uses ~/Library/{Preferences,Application Support,Caches}.
/// - On Windows uses known folders (RoamingAppData/LocalAppData/Profile) with env fallbacks.
StandardPaths standardPaths();

std::optional<std::string> getenvString(const char* key);

/// Returns canonical(path) if it exists, otherwise returns the input unchanged.
std::filesystem::path canonicalIfExists(const std::filesystem::path& path);

/// Best-effort absolute path of the current executable given argv[0].
/// On POSIX, searches PATH when argv0 has no directory separator.
std::filesystem::path resolveExecutablePath(const char* argv0);

}  // namespace Base

#endif  // BASE_PLATFORMPATHS_H

