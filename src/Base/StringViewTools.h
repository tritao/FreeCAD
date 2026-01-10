// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef FREECAD_BASE_STRINGVIEWTOOLS_H
#define FREECAD_BASE_STRINGVIEWTOOLS_H

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

#endif  // FREECAD_BASE_STRINGVIEWTOOLS_H
