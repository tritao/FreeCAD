// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef BASE_BYTESVIEW_H
#define BASE_BYTESVIEW_H

#include <cstddef>
#include <string_view>

namespace Base
{

/// Non-owning view over a byte sequence (may contain embedded NULs).
using BytesView = std::string_view;

inline BytesView bytesView(const char* data, std::size_t size)
{
    if (size == 0U) {
        return {};
    }
    return {data, size};
}

}  // namespace Base

#endif  // BASE_BYTESVIEW_H

