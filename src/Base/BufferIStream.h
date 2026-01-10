// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL

#pragma once

#include <cstddef>
#include <istream>
#include <streambuf>

namespace Base
{

class BufferIStreambuf: public std::streambuf
{
public:
    BufferIStreambuf(const char* data, std::size_t size)
    {
        char* begin = const_cast<char*>(data);
        setg(begin, begin, begin + static_cast<std::ptrdiff_t>(size));
    }
};

class BufferIStream: public std::istream
{
public:
    BufferIStream(const char* data, std::size_t size)
        : std::istream(nullptr)
        , buf(data, size)
    {
        rdbuf(&buf);
    }

private:
    BufferIStreambuf buf;
};

}  // namespace Base
