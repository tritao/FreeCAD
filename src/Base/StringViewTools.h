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

#include <algorithm>
#include <cstddef>
#include <ranges>
#include <string_view>

namespace Base::StringViewTools
{

inline std::string_view trim(std::string_view view)
{
    while (!view.empty()) {
        const char c = view.front();
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v') {
            view.remove_prefix(1);
            continue;
        }
        break;
    }

    while (!view.empty()) {
        const char c = view.back();
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v') {
            view.remove_suffix(1);
            continue;
        }
        break;
    }

    return view;
}

inline unsigned char toLowerAscii(unsigned char c)
{
    if (c >= static_cast<unsigned char>('A') && c <= static_cast<unsigned char>('Z')) {
        constexpr auto delta = static_cast<unsigned char>('a') - static_cast<unsigned char>('A');
        return static_cast<unsigned char>(c + delta);
    }
    return c;
}

inline bool iequalsAscii(std::string_view a, std::string_view b)
{
    return std::ranges::equal(a, b, [](char ca, char cb) {
        return toLowerAscii(static_cast<unsigned char>(ca))
            == toLowerAscii(static_cast<unsigned char>(cb));
    });
}

}  // namespace Base::StringViewTools
