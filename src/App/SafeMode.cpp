// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2024 Benjamin Nauck <benjamin@nauck.se>                 *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Library General Public License (LGPL)   *
 *   as published by the Free Software Foundation; either version 2 of     *
 *   the License, or (at your option) any later version.                   *
 *   for detail see the LICENCE text file.                                 *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful,            *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with FreeCAD; if not, write to the Free Software        *
 *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
 *   USA                                                                   *
 *                                                                         *
 ***************************************************************************/

#include <cstdint>
#include <filesystem>
#include <string>
#include <system_error>

#include "Application.h"
#include "FCConfig.h"

#include "SafeMode.h"

namespace fs = std::filesystem;

static fs::path tempDir;

static bool _createTemporaryBaseDir()
{
    std::error_code error;
    const fs::path base = fs::temp_directory_path(error);
    if (error) {
        return false;
    }

    auto suffix = static_cast<std::uint64_t>(App::Application::uniqueInstanceId());

    for (int attempt = 0; attempt < 64; ++attempt) {
        fs::path candidate = base / ("FreeCADSafeMode-" + std::to_string(suffix));
        if (fs::create_directory(candidate, error) && !error) {
            tempDir = std::move(candidate);
            return true;
        }
        error.clear();
        suffix ^= suffix << 7U;
        suffix ^= suffix >> 9U;
        suffix += static_cast<std::uint64_t>(attempt) + 1U;
    }

    return false;
}

static void _replaceDirs()
{
    auto& config = App::GetApplication().Config();

    auto const temp_base = tempDir.string();
    auto const dirs = {
        "UserAppData",
        "UserConfigPath",
        "UserCachePath",
        "AppTempPath",
        "UserMacroPath",
        "UserHomePath",
    };

    for (auto const d : dirs) {
        auto const path = temp_base + PATHSEP + d + PATHSEP;
        std::error_code error;
        fs::create_directories(fs::path(temp_base) / d, error);
        config[d] = path;
    }
}

void SafeMode::StartSafeMode()
{
    if (_createTemporaryBaseDir()) {
        _replaceDirs();
    }
}

bool SafeMode::SafeModeEnabled()
{
    return !tempDir.empty();
}

void SafeMode::Destruct()
{
    if (tempDir.empty()) {
        return;
    }
    std::error_code error;
    fs::remove_all(tempDir, error);
    tempDir.clear();
}
