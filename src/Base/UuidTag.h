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

#include <array>
#include <cstddef>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>

namespace Base
{

class UuidTag
{
public:
    using Bytes = std::array<std::uint8_t, 16>;

    constexpr UuidTag() noexcept = default;

    explicit constexpr UuidTag(const Bytes& bytes) noexcept
        : bytes_(bytes)
    {}

    static UuidTag randomV4()
    {
        // Thread-local generator avoids the mutex/valgrind-related patterns used by Boost.
        static thread_local std::mt19937_64 gen([] {
            std::random_device rd;
            std::seed_seq seq {rd(), rd(), rd(), rd(), rd(), rd(), rd(), rd()};
            return std::mt19937_64(seq);
        }());

        std::uniform_int_distribution<std::uint32_t> dist(0U, 0xFFFFFFFFU);
        Bytes bytes {};
        for (std::size_t i = 0; i < bytes.size(); i += 4) {
            const std::uint32_t v = dist(gen);
            bytes[i + 0] = static_cast<std::uint8_t>((v >> 24U) & 0xFFU);
            bytes[i + 1] = static_cast<std::uint8_t>((v >> 16U) & 0xFFU);
            bytes[i + 2] = static_cast<std::uint8_t>((v >> 8U) & 0xFFU);
            bytes[i + 3] = static_cast<std::uint8_t>((v >> 0U) & 0xFFU);
        }

        // Force RFC4122 version 4 and variant 1 bits.
        bytes[6] = static_cast<std::uint8_t>((bytes[6] & 0x0FU) | 0x40U);
        bytes[8] = static_cast<std::uint8_t>((bytes[8] & 0x3FU) | 0x80U);

        return UuidTag(bytes);
    }

    static UuidTag fromString(std::string_view text)
    {
        Bytes bytes {};
        if (!tryParse(text, bytes)) {
            throw std::runtime_error("invalid uuid");
        }
        return UuidTag(bytes);
    }

    std::string toString() const
    {
        std::string out;
        out.resize(36);

        auto hexChar = [](std::uint8_t nibble) -> char {
            return nibble < 10 ? static_cast<char>('0' + nibble)
                               : static_cast<char>('a' + (nibble - 10));
        };

        auto writeByte = [&](std::size_t pos, std::uint8_t byte) {
            out[pos + 0] = hexChar(static_cast<std::uint8_t>((byte >> 4U) & 0x0FU));
            out[pos + 1] = hexChar(static_cast<std::uint8_t>((byte >> 0U) & 0x0FU));
        };

        // Canonical RFC4122 format: 8-4-4-4-12 lowercase hex.
        writeByte(0, bytes_[0]);
        writeByte(2, bytes_[1]);
        writeByte(4, bytes_[2]);
        writeByte(6, bytes_[3]);
        out[8] = '-';
        writeByte(9, bytes_[4]);
        writeByte(11, bytes_[5]);
        out[13] = '-';
        writeByte(14, bytes_[6]);
        writeByte(16, bytes_[7]);
        out[18] = '-';
        writeByte(19, bytes_[8]);
        writeByte(21, bytes_[9]);
        out[23] = '-';
        writeByte(24, bytes_[10]);
        writeByte(26, bytes_[11]);
        writeByte(28, bytes_[12]);
        writeByte(30, bytes_[13]);
        writeByte(32, bytes_[14]);
        writeByte(34, bytes_[15]);

        return out;
    }

    constexpr const Bytes& bytes() const noexcept
    {
        return bytes_;
    }

    constexpr bool isNil() const noexcept
    {
        for (auto b : bytes_) {
            if (b != 0U) {
                return false;
            }
        }
        return true;
    }

    constexpr auto begin() const noexcept
    {
        return bytes_.begin();
    }

    constexpr auto end() const noexcept
    {
        return bytes_.end();
    }

    friend constexpr bool operator==(const UuidTag&, const UuidTag&) noexcept = default;

    friend constexpr bool operator<(const UuidTag& a, const UuidTag& b) noexcept
    {
        return a.bytes_ < b.bytes_;
    }

private:
    static int hexValue(char ch) noexcept
    {
        if (ch >= '0' && ch <= '9') {
            return ch - '0';
        }
        if (ch >= 'a' && ch <= 'f') {
            return 10 + (ch - 'a');
        }
        if (ch >= 'A' && ch <= 'F') {
            return 10 + (ch - 'A');
        }
        return -1;
    }

    static bool tryParse(std::string_view text, Bytes& out) noexcept
    {
        if (text.size() == 38 && text.front() == '{' && text.back() == '}') {
            text.remove_prefix(1);
            text.remove_suffix(1);
        }
        if (text.size() != 36) {
            return false;
        }
        if (text[8] != '-' || text[13] != '-' || text[18] != '-' || text[23] != '-') {
            return false;
        }

        auto readByte = [&](std::size_t pos, std::uint8_t& byte) -> bool {
            const int hi = hexValue(text[pos]);
            const int lo = hexValue(text[pos + 1]);
            if (hi < 0 || lo < 0) {
                return false;
            }
            byte = static_cast<std::uint8_t>((hi << 4) | lo);
            return true;
        };

        static constexpr std::array<std::size_t, 16> positions = {
            0,
            2,
            4,
            6,  // 8
            9,
            11,  // 4
            14,
            16,  // 4
            19,
            21,  // 4
            24,
            26,
            28,
            30,
            32,
            34  // 12
        };

        for (std::size_t i = 0; i < out.size(); ++i) {
            if (!readByte(positions[i], out[i])) {
                return false;
            }
        }
        return true;
    }

    Bytes bytes_ {};
};

struct UuidTagHash
{
    std::size_t operator()(const UuidTag& uuid) const noexcept
    {
        std::size_t h = 14695981039346656037ULL;
        for (std::uint8_t b : uuid.bytes()) {
            h ^= static_cast<std::size_t>(b);
            h *= 1099511628211ULL;
        }
        return h;
    }
};

}  // namespace Base
