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
