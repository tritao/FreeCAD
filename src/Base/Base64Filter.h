// SPDX-License-Identifier: LGPL-2.1-or-later

/****************************************************************************
 *                                                                          *
 *   Copyright (c) 2019 Zheng Lei (realthunder.dev@gmail.com)               *
 *                                                                          *
 *   This file is part of FreeCAD.                                          *
 *                                                                          *
 *   FreeCAD is free software: you can redistribute it and/or modify it     *
 *   under the terms of the GNU Lesser General Public License as            *
 *   published by the Free Software Foundation, either version 2.1 of the   *
 *   License, or (at your option) any later version.                        *
 *                                                                          *
 *   FreeCAD is distributed in the hope that it will be useful, but         *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of             *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
 *   Lesser General Public License for more details.                        *
 *                                                                          *
 *   You should have received a copy of the GNU Lesser General Public       *
 *   License along with FreeCAD. If not, see                                *
 *   <https://www.gnu.org/licenses/>.                                       *
 *                                                                          *
 ***************************************************************************/

#ifndef FREECAD_BASE_BASE64FILTER_H
#define FREECAD_BASE_BASE64FILTER_H

#include "Base64.h"
#include "FCGlobal.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <istream>
#include <memory>
#include <ostream>
#include <stdexcept>
#include <streambuf>
#include <string>

// NOLINTBEGIN(cppcoreguidelines-pro-bounds-pointer-arithmetic,
// cppcoreguidelines-pro-bounds-constant-array-index, cppcoreguidelines-avoid-magic-numbers,
// readability-magic-numbers)

namespace Base
{

enum class Base64ErrorHandling
{
    throws,
    silent
};

static constexpr int base64DefaultBufferSize {80};

namespace detail
{

class Base64EncoderStreambuf: public std::streambuf
{
public:
    Base64EncoderStreambuf(std::streambuf* downstream, std::size_t line_size)
        : downstream(downstream)
        , line_size(line_size)
    {}

    ~Base64EncoderStreambuf() override
    {
        finalize();
    }

    void finalize()
    {
        if (finalized) {
            return;
        }
        finalized = true;

        if (pending_size != 0) {
            emitEncoded(pending.data(), pending_size);
            pending_size = 0;
        }

        if (line_size && pos) {
            downstream->sputc('\n');
            pos = 0;
        }

        (void)downstream->pubsync();
    }

protected:
    int sync() override
    {
        return downstream->pubsync();
    }

    int_type overflow(int_type c) override
    {
        if (traits_type::eq_int_type(c, traits_type::eof())) {
            return traits_type::not_eof(c);
        }

        const auto byte = static_cast<unsigned char>(traits_type::to_char_type(c));
        pending[pending_size++] = byte;
        if (pending_size == 3) {
            emitEncoded(pending.data(), pending_size);
            pending_size = 0;
        }
        return c;
    }

    std::streamsize xsputn(const char* s, std::streamsize num) override
    {
        std::streamsize written = 0;

        if (num <= 0) {
            return 0;
        }

        if (pending_size != 0) {
            while (written < num && pending_size < 3) {
                pending[pending_size++] = static_cast<unsigned char>(s[written++]);
            }
            if (pending_size == 3) {
                emitEncoded(pending.data(), pending_size);
                pending_size = 0;
            }
        }

        const auto* bytes = reinterpret_cast<const unsigned char*>(s + written);  // NOLINT
        const std::size_t remaining = static_cast<std::size_t>(num - written);
        const std::size_t full = remaining / 3 * 3;
        if (full != 0) {
            emitEncoded(bytes, full);
            written += static_cast<std::streamsize>(full);
        }

        const std::size_t tail = remaining - full;
        for (std::size_t i = 0; i < tail; ++i) {
            pending[pending_size++] = bytes[full + i];
        }

        return num;
    }

private:
    void writeWithLineBreaks(const char* data, std::size_t len)
    {
        if (!line_size) {
            downstream->sputn(data, static_cast<std::streamsize>(len));
            return;
        }

        const char* cur = data;
        const char* end = data + len;
        while (cur != end) {
            const std::size_t room = line_size - pos;
            const std::size_t chunk = std::min<std::size_t>(room, static_cast<std::size_t>(end - cur));
            downstream->sputn(cur, static_cast<std::streamsize>(chunk));
            cur += chunk;
            pos += chunk;
            if (pos == line_size) {
                downstream->sputc('\n');
                pos = 0;
            }
        }
    }

    void emitEncoded(const unsigned char* in, std::size_t len)
    {
        std::string buffer;
        buffer.resize(base64_encode_size(len));
        const std::size_t outLen = base64_encode(buffer.data(), in, len);
        buffer.resize(outLen);
        writeWithLineBreaks(buffer.data(), buffer.size());
    }

private:
    std::streambuf* downstream;
    std::size_t line_size;
    std::size_t pos {0};
    std::size_t pending_size {0};
    std::array<unsigned char, 3> pending {};
    bool finalized {false};
};

class Base64DecoderStreambuf: public std::streambuf
{
public:
    Base64DecoderStreambuf(std::streambuf* upstream, Base64ErrorHandling errHandling)
        : upstream(upstream)
        , errHandling(errHandling)
        , table(base64_decode_table())
    {
        setg(out.data(), out.data(), out.data());
    }

protected:
    int_type underflow() override
    {
        if (gptr() < egptr()) {
            return traits_type::to_int_type(*gptr());
        }

        if (!fill()) {
            return traits_type::eof();
        }
        return traits_type::to_int_type(*gptr());
    }

private:
    int nextChar()
    {
        const auto c = upstream->sbumpc();
        if (traits_type::eq_int_type(c, traits_type::eof())) {
            return -1;
        }
        return static_cast<unsigned char>(traits_type::to_char_type(c));
    }

    bool fill()
    {
        std::array<unsigned char, 4> sextets {};
        std::size_t count = 0;
        int padding = 0;
        bool reachedEof = false;

        while (count < 4) {
            const int c = nextChar();
            if (c < 0) {
                reachedEof = true;
                break;
            }
            if (c == '=') {
                ++padding;
                sextets[count++] = 0;
                continue;
            }

            const signed char decoded = table[static_cast<unsigned char>(c)];
            if (decoded == -2) {
                continue;
            }
            if (decoded < 0) {
                if (errHandling == Base64ErrorHandling::silent) {
                    continue;
                }
                throw std::runtime_error("Invalid character in base64 string");
            }
            sextets[count++] = static_cast<unsigned char>(decoded);
        }

        if (count == 0) {
            return false;
        }

        std::size_t outCount = 0;
        if (padding > 0) {
            outCount = 3 - static_cast<std::size_t>(padding);
        }
        else if (reachedEof && count < 4) {
            if (count == 1) {
                if (errHandling == Base64ErrorHandling::throws) {
                    throw std::runtime_error("Unexpected ending of base64 string");
                }
                return false;
            }
            outCount = count - 1;
            for (; count < 4; ++count) {
                sextets[count] = 0;
            }
        }
        else {
            outCount = 3;
        }

        out[0] = static_cast<char>((sextets[0] << 2) + ((sextets[1] & 0x30) >> 4));
        out[1] = static_cast<char>(((sextets[1] & 0x0f) << 4) + ((sextets[2] & 0x3c) >> 2));
        out[2] = static_cast<char>(((sextets[2] & 0x03) << 6) + sextets[3]);
        setg(out.data(), out.data(), out.data() + static_cast<std::ptrdiff_t>(outCount));
        return true;
    }

private:
    std::streambuf* upstream;
    Base64ErrorHandling errHandling;
    std::array<const signed char, base64DecodeTableSize> table;
    std::array<char, 3> out {};
};

class Base64EncodingOStream: public std::ostream
{
public:
    Base64EncodingOStream(std::ostream& out, std::size_t line_size)
        : std::ostream(nullptr)
        , buf(out.rdbuf(), line_size)
    {
        rdbuf(&buf);
    }

    ~Base64EncodingOStream() override
    {
        buf.finalize();
    }

private:
    Base64EncoderStreambuf buf;
};

class Base64FileEncodingOStream: public std::ostream
{
public:
    Base64FileEncodingOStream(const std::string& filepath, std::size_t line_size)
        : std::ostream(nullptr)
        , file(filepath, std::ios::out | std::ios::binary)
        , buf(file.rdbuf(), line_size)
    {
        if (!file) {
            throw std::runtime_error("Failed to open base64 output file");
        }
        rdbuf(&buf);
    }

    ~Base64FileEncodingOStream() override
    {
        buf.finalize();
    }

private:
    std::ofstream file;
    Base64EncoderStreambuf buf;
};

class Base64DecodingIStream: public std::istream
{
public:
    Base64DecodingIStream(std::istream& in, Base64ErrorHandling errHandling)
        : std::istream(nullptr)
        , buf(in.rdbuf(), errHandling)
    {
        rdbuf(&buf);
    }

private:
    Base64DecoderStreambuf buf;
};

class Base64FileDecodingIStream: public std::istream
{
public:
    Base64FileDecodingIStream(const std::string& filepath, Base64ErrorHandling errHandling)
        : std::istream(nullptr)
        , file(filepath, std::ios::in | std::ios::binary)
        , buf(file.rdbuf(), errHandling)
    {
        if (!file) {
            throw std::runtime_error("Failed to open base64 input file");
        }
        rdbuf(&buf);
    }

private:
    std::ifstream file;
    Base64DecoderStreambuf buf;
};

}  // namespace detail

/** Create an output stream that transforms the input binary data to base64 strings
 *
 * @param out: the downstream output stream that will be fed with base64 string
 * @param line_size: line size of the base64 string. Zero to disable segmenting.
 *
 * @return A unique pointer to an output stream that can transforms the
 * input binary data to base64 strings.
 */
inline std::unique_ptr<std::ostream> create_base64_encoder(
    std::ostream& out,
    std::size_t line_size = base64DefaultBufferSize
)
{
    return std::make_unique<detail::Base64EncodingOStream>(out, line_size);
}

/** Create an output stream that stores the input binary data to file as base64 strings
 *
 * @param filepath: the output file path
 * @param line_size: line size of the base64 string. Zero to disable segmenting.
 *
 * @return A unique pointer to an output stream that can transforms the
 * input binary data to base64 strings.
 */
inline std::unique_ptr<std::ostream> create_base64_encoder(
    const std::string& filepath,
    std::size_t line_size = base64DefaultBufferSize
)
{
    return std::make_unique<detail::Base64FileEncodingOStream>(filepath, line_size);
}

/** Create an input stream that can transform base64 into binary
 *
 * @param in: input upstream.
 * @param line_size: line size of the encoded base64 string. This is
 *                   used just as a suggestion for better buffering.
 * @param silent: whether to throw on invalid non white space character.
 *
 * @return A unique pointer to an input stream that read from the given
 * upstream and transform the read base64 strings into binary data.
 */
inline std::unique_ptr<std::istream> create_base64_decoder(
    std::istream& in,
    std::size_t /*line_size*/ = base64DefaultBufferSize,
    Base64ErrorHandling errHandling = Base64ErrorHandling::silent
)
{
    return std::make_unique<detail::Base64DecodingIStream>(in, errHandling);
}

/** Create an input stream that can transform base64 into binary
 *
 * @param filepath: input file.
 * @param line_size: line size of the encoded base64 string. This is
 *                   used just as a suggestion for better buffering.
 * @param silent: whether to throw on invalid non white space character.
 *
 * @return A unique pointer to an input stream that read from the given
 * file and transform the read base64 strings into binary data.
 */
inline std::unique_ptr<std::istream> create_base64_decoder(
    const std::string& filepath,
    std::size_t /*line_size*/ = base64DefaultBufferSize,
    Base64ErrorHandling errHandling = Base64ErrorHandling::silent
)
{
    return std::make_unique<detail::Base64FileDecodingIStream>(filepath, errHandling);
}

}  // namespace Base

// NOLINTEND(cppcoreguidelines-pro-bounds-pointer-arithmetic,
// cppcoreguidelines-pro-bounds-constant-array-index, cppcoreguidelines-avoid-magic-numbers,
// readability-magic-numbers)

#endif  // FREECAD_BASE_BASE64FILTER_H
