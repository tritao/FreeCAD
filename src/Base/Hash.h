// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef BASE_HASH_H
#define BASE_HASH_H

#include <cstddef>
#include <cstdint>

namespace Base
{

inline void fnv1a64Append(std::size_t& seed, const void* data, std::size_t size) noexcept
{
    constexpr std::uint64_t offsetBasis = 14695981039346656037ULL;
    constexpr std::uint64_t prime = 1099511628211ULL;

    std::uint64_t hash = seed == 0U ? offsetBasis : static_cast<std::uint64_t>(seed);
    const auto* bytes = static_cast<const unsigned char*>(data);
    for (std::size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= prime;
    }
    seed = static_cast<std::size_t>(hash);
}

inline std::size_t fnv1a64(const void* data, std::size_t size) noexcept
{
    std::size_t seed = 0U;
    fnv1a64Append(seed, data, size);
    return seed;
}

}  // namespace Base

#endif  // BASE_HASH_H

