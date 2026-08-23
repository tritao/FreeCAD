// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

namespace Wasm
{

namespace Abi
{

inline constexpr const char* HostModule = "freecad";
inline constexpr const char* AllocImport = "freecad_alloc";
inline constexpr const char* DispatchImport = "freecad_dispatch";
inline constexpr const char* LogImport = "freecad_log";
inline constexpr const char* ReleaseImport = "freecad_release";
inline constexpr const char* AddonEntryExport = "freecad_addon_entry";

inline constexpr std::array<std::uint8_t, 4> RequestMagic {'F', 'C', 'W', 'A'};
inline constexpr std::uint8_t RequestVersion = 1U;
inline constexpr std::size_t RequestHeaderSize = 12U;

enum class Operation : std::uint8_t
{
    DocumentNew = 1,
    PartMakeBox = 2,
    DocumentAddObject = 3,
    HandleRelease = 4,
};

inline void appendU32(std::string& output, std::uint32_t value)
{
    for (unsigned shift = 0U; shift < 32U; shift += 8U) {
        output.push_back(static_cast<char>((value >> shift) & 0xffU));
    }
}

inline void appendU64(std::string& output, std::uint64_t value)
{
    for (unsigned shift = 0U; shift < 64U; shift += 8U) {
        output.push_back(static_cast<char>((value >> shift) & 0xffU));
    }
}

inline void appendHeader(std::string& output, Operation operation, std::uint32_t payloadSize)
{
    output.append(reinterpret_cast<const char*>(RequestMagic.data()), RequestMagic.size());
    output.push_back(static_cast<char>(RequestVersion));
    output.push_back(static_cast<char>(operation));
    output.push_back('\0');
    output.push_back('\0');
    appendU32(output, payloadSize);
}

// Exported addon calls use (i32 input_ptr, i32 input_len) -> i64. The low
// word is the response address and the high word is its byte length.
inline constexpr std::uint64_t packResponse(std::uint32_t address, std::uint32_t length)
{
    return static_cast<std::uint64_t>(address)
        | (static_cast<std::uint64_t>(length) << 32U);
}

inline constexpr std::uint32_t responseAddress(std::uint64_t response)
{
    return static_cast<std::uint32_t>(response);
}

inline constexpr std::uint32_t responseLength(std::uint64_t response)
{
    return static_cast<std::uint32_t>(response >> 32U);
}

}  // namespace Abi

}  // namespace Wasm
