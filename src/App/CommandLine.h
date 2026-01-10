// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#pragma once

#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace App
{

class CommandLineOptions
{
public:
    bool has(std::string_view name) const;
    std::string valueOr(std::string_view name, std::string fallback = {}) const;
    const std::vector<std::string>& values(std::string_view name) const;

    void setFlag(std::string name);
    void setValue(std::string name, std::string value);
    void appendValue(std::string name, std::string value);

    void appendPositional(std::string value);
    const std::vector<std::string>& positional() const;

private:
    std::unordered_set<std::string> flags;
    std::unordered_map<std::string, std::vector<std::string>> options;
    std::vector<std::string> positionalArgs;
};

CommandLineOptions parseCommandLine(int argc, char** argv, const std::string& exeName);

std::string commandLineHelp(const std::string& exeName);

}  // namespace App
