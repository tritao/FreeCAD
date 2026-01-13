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

#include <string_view>

namespace Base
{

namespace detail
{
constexpr unsigned char toLowerAscii(unsigned char c)
{
    if (c >= 'A' && c <= 'Z') {
        return static_cast<unsigned char>(c - 'A' + 'a');
    }
    return c;
}

constexpr bool iequalsAscii(std::string_view a, std::string_view b)
{
    if (a.size() != b.size()) {
        return false;
    }
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (toLowerAscii(static_cast<unsigned char>(a[i]))
            != toLowerAscii(static_cast<unsigned char>(b[i]))) {
            return false;
        }
    }
    return true;
}
}  // namespace detail

constexpr bool equals(std::string_view a, std::string_view b)
{
    return a == b;
}

constexpr bool iequals(std::string_view a, std::string_view b)
{
    return detail::iequalsAscii(a, b);
}

constexpr bool startsWith(std::string_view s, std::string_view prefix)
{
    return s.starts_with(prefix);
}

constexpr bool endsWith(std::string_view s, std::string_view suffix)
{
    return s.ends_with(suffix);
}

constexpr bool contains(std::string_view s, std::string_view needle)
{
    return s.find(needle) != std::string_view::npos;
}

constexpr bool istartsWith(std::string_view s, std::string_view prefix)
{
    if (prefix.size() > s.size()) {
        return false;
    }
    return detail::iequalsAscii(s.substr(0, prefix.size()), prefix);
}

constexpr bool iendsWith(std::string_view s, std::string_view suffix)
{
    if (suffix.size() > s.size()) {
        return false;
    }
    return detail::iequalsAscii(s.substr(s.size() - suffix.size()), suffix);
}

inline bool icontains(std::string_view s, std::string_view needle)
{
    if (needle.empty()) {
        return true;
    }
    if (needle.size() > s.size()) {
        return false;
    }

    for (std::size_t i = 0; i + needle.size() <= s.size(); ++i) {
        if (detail::iequalsAscii(s.substr(i, needle.size()), needle)) {
            return true;
        }
    }
    return false;
}

}  // namespace Base
