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
#include <vector>

namespace Base
{

inline std::vector<std::string> splitAnyOf(
    std::string_view text,
    std::string_view delimiters,
    bool keepEmpty = false
)
{
    std::vector<std::string> tokens;
    std::size_t start = 0;

    auto isDelimiter = [delimiters](char c) {
        return delimiters.find(c) != std::string_view::npos;
    };

    for (std::size_t i = 0; i <= text.size(); ++i) {
        if (i == text.size() || isDelimiter(text[i])) {
            if (i != start) {
                tokens.emplace_back(text.substr(start, i - start));
            }
            else if (keepEmpty) {
                tokens.emplace_back();
            }
            start = i + 1;
        }
    }

    return tokens;
}

inline std::vector<std::string> splitChar(std::string_view text, char delimiter, bool keepEmpty = false)
{
    return splitAnyOf(text, std::string_view(&delimiter, 1), keepEmpty);
}

inline std::vector<std::string> splitEscaped(
    std::string_view text,
    char delimiter,
    char quoteChar,
    char escapeChar
)
{
    std::vector<std::string> fields;
    std::string current;
    current.reserve(text.size());

    enum class State
    {
        StartField,
        InField,
        InQuotedField,
        AfterQuote,
    };

    State state = State::StartField;

    auto pushField = [&]() {
        fields.push_back(std::move(current));
        current.clear();
    };

    for (std::size_t i = 0; i < text.size(); ++i) {
        const char c = text[i];

        if (escapeChar != '\0' && c == escapeChar && i + 1 < text.size()) {
            current.push_back(text[++i]);
            if (state == State::StartField) {
                state = State::InField;
            }
            else if (state == State::AfterQuote) {
                state = State::InField;
            }
            continue;
        }

        switch (state) {
            case State::StartField:
                if (c == delimiter) {
                    pushField();
                }
                else if (quoteChar != '\0' && c == quoteChar) {
                    state = State::InQuotedField;
                }
                else {
                    current.push_back(c);
                    state = State::InField;
                }
                break;

            case State::InField:
                if (c == delimiter) {
                    pushField();
                    state = State::StartField;
                }
                else {
                    current.push_back(c);
                }
                break;

            case State::InQuotedField:
                if (quoteChar != '\0' && c == quoteChar) {
                    if (i + 1 < text.size() && text[i + 1] == quoteChar) {
                        current.push_back(quoteChar);
                        ++i;
                    }
                    else {
                        state = State::AfterQuote;
                    }
                }
                else {
                    current.push_back(c);
                }
                break;

            case State::AfterQuote:
                if (c == delimiter) {
                    pushField();
                    state = State::StartField;
                }
                else {
                    current.push_back(c);
                    state = State::InField;
                }
                break;
        }
    }

    pushField();
    return fields;
}

}  // namespace Base
