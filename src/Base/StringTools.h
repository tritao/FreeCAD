// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL

#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include <Base/StringViewTools.h>

namespace Base::StringTools
{

inline unsigned char toUpperAscii(unsigned char c) noexcept
{
    if (c >= static_cast<unsigned char>('a') && c <= static_cast<unsigned char>('z')) {
        constexpr auto delta
            = static_cast<unsigned char>('a') - static_cast<unsigned char>('A');
        return static_cast<unsigned char>(c - delta);
    }
    return c;
}

inline void toLowerAsciiInPlace(std::string& value)
{
    for (char& c : value) {
        c = static_cast<char>(Base::StringViewTools::toLowerAscii(static_cast<unsigned char>(c)));
    }
}

inline void toUpperAsciiInPlace(std::string& value)
{
    for (char& c : value) {
        c = static_cast<char>(toUpperAscii(static_cast<unsigned char>(c)));
    }
}

inline std::string toLowerAsciiCopy(std::string_view value)
{
    std::string out(value);
    toLowerAsciiInPlace(out);
    return out;
}

inline std::string toUpperAsciiCopy(std::string_view value)
{
    std::string out(value);
    toUpperAsciiInPlace(out);
    return out;
}

inline void toLowerAsciiInPlace(char* value)
{
    if (!value) {
        return;
    }
    for (char* p = value; *p != '\0'; ++p) {
        *p = static_cast<char>(Base::StringViewTools::toLowerAscii(static_cast<unsigned char>(*p)));
    }
}

inline void toUpperAsciiInPlace(char* value)
{
    if (!value) {
        return;
    }
    for (char* p = value; *p != '\0'; ++p) {
        *p = static_cast<char>(toUpperAscii(static_cast<unsigned char>(*p)));
    }
}

inline void trimInPlace(std::string& value)
{
    const std::string_view view = Base::StringViewTools::trim(value);
    if (view.size() == value.size()) {
        return;
    }
    value.assign(view);
}

inline std::string trimCopy(std::string_view value)
{
    value = Base::StringViewTools::trim(value);
    return std::string(value);
}

inline void replaceAll(std::string& value, std::string_view from, std::string_view to)
{
    if (from.empty()) {
        return;
    }
    std::size_t pos = 0;
    while ((pos = value.find(from, pos)) != std::string::npos) {
        value.replace(pos, from.size(), to);
        pos += to.size();
    }
}

inline bool isDelimiter(char c, std::string_view delims) noexcept
{
    return delims.find(c) != std::string_view::npos;
}

inline void splitAnyOf(std::vector<std::string>& out,
                       std::string_view input,
                       std::string_view delims,
                       bool tokenCompress = true)
{
    out.clear();

    std::size_t start = 0;
    while (start <= input.size()) {
        std::size_t end = start;
        while (end < input.size() && !isDelimiter(input[end], delims)) {
            ++end;
        }

        if (end != start || !tokenCompress) {
            out.emplace_back(input.substr(start, end - start));
        }

        if (end >= input.size()) {
            break;
        }

        start = end + 1;
        if (tokenCompress) {
            while (start < input.size() && isDelimiter(input[start], delims)) {
                ++start;
            }
        }
    }
}

}  // namespace Base::StringTools
