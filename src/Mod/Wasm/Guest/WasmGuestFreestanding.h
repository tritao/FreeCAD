// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

// This variant intentionally avoids libc, libc++, and a Wasm system runtime.
// It is suitable for small WAMR guests built with -ffreestanding.

#if defined(__wasm__) && defined(__clang__)
# define FREECAD_WASM_IMPORT(module, name) \
    __attribute__((import_module(module), import_name(name)))
#else
# define FREECAD_WASM_IMPORT(module, name)
#endif

extern "C"
{
using FreeCADWasmU8 = unsigned char;
using FreeCADWasmU32 = unsigned int;
using FreeCADWasmU64 = unsigned long long;

FreeCADWasmU32 freecad_alloc(FreeCADWasmU32 size)
    FREECAD_WASM_IMPORT("freecad", "freecad_alloc");
FreeCADWasmU64 freecad_dispatch(const FreeCADWasmU8* request,
                                FreeCADWasmU32 requestLength)
    FREECAD_WASM_IMPORT("freecad", "freecad_dispatch");
void freecad_release(FreeCADWasmU32 responseAddress)
    FREECAD_WASM_IMPORT("freecad", "freecad_release");
}

namespace Wasm
{

namespace Guest
{

using Handle = FreeCADWasmU64;

class ResponseBuffer
{
public:
    ResponseBuffer() = default;

    ResponseBuffer(FreeCADWasmU32 address, FreeCADWasmU32 size)
        : address(address)
        , size(size)
    {
    }

    ~ResponseBuffer()
    {
        reset();
    }

    ResponseBuffer(const ResponseBuffer&) = delete;
    ResponseBuffer& operator=(const ResponseBuffer&) = delete;

    ResponseBuffer(ResponseBuffer&& other) noexcept
        : address(other.address)
        , size(other.size)
    {
        other.address = 0U;
        other.size = 0U;
    }

    ResponseBuffer& operator=(ResponseBuffer&& other) noexcept
    {
        if (this != &other) {
            reset();
            address = other.address;
            size = other.size;
            other.address = 0U;
            other.size = 0U;
        }
        return *this;
    }

    bool valid() const
    {
        return address != 0U && size != 0U;
    }

    FreeCADWasmU8* data() const
    {
        return reinterpret_cast<FreeCADWasmU8*>(address);
    }

    FreeCADWasmU64 take()
    {
        if (!valid()) {
            return 0U;
        }
        const auto response = static_cast<FreeCADWasmU64>(address)
            | (static_cast<FreeCADWasmU64>(size) << 32U);
        address = 0U;
        size = 0U;
        return response;
    }

private:
    void reset()
    {
        if (address != 0U) {
            freecad_release(address);
        }
        address = 0U;
        size = 0U;
    }

    FreeCADWasmU32 address = 0U;
    FreeCADWasmU32 size = 0U;
};

class Client
{
public:
    ResponseBuffer allocateResponse(FreeCADWasmU32 size) const
    {
        return ResponseBuffer(freecad_alloc(size), size);
    }

    bool documentNew(const char* name, Handle* result) const
    {
        if (result == nullptr) {
            return false;
        }

        const auto nameLength = stringLength(name);
        if (name == nullptr || nameLength > MaxStringLength) {
            return false;
        }
        resetRequest(1U, 4U + nameLength);
        appendU32(nameLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(name), nameLength);
        return call(result);
    }

    bool partMakeBox(double length, double width, double height, Handle* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(2U, 24U);
        appendDouble(length);
        appendDouble(width);
        appendDouble(height);
        return call(result);
    }

    bool documentAddObject(Handle document,
                           Handle shape,
                           const char* name,
                           Handle* result) const
    {
        if (result == nullptr) {
            return false;
        }

        const auto nameLength = stringLength(name);
        if (name == nullptr || nameLength > MaxStringLength) {
            return false;
        }
        resetRequest(3U, 20U + nameLength);
        appendU64(document);
        appendU64(shape);
        appendU32(nameLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(name), nameLength);
        return call(result);
    }

    bool release(Handle handle) const
    {
        resetRequest(4U, 8U);
        appendU64(handle);
        const auto response = freecad_dispatch(request, requestLength);
        const auto address = static_cast<FreeCADWasmU32>(response);
        const auto length = static_cast<FreeCADWasmU32>(response >> 32U);
        if (address != 0U) {
            freecad_release(address);
        }
        return length == 0U;
    }

private:
    static constexpr FreeCADWasmU32 MaxRequestSize = 512U;
    static constexpr FreeCADWasmU32 MaxStringLength = 128U;

    static FreeCADWasmU32 stringLength(const char* value)
    {
        if (value == nullptr) {
            return 0U;
        }

        FreeCADWasmU32 length = 0U;
        while (length < MaxStringLength + 1U && value[length] != '\0') {
            ++length;
        }
        return length;
    }

    static void resetRequest(FreeCADWasmU8 operation, FreeCADWasmU32 payloadLength)
    {
        request[0] = 'F';
        request[1] = 'C';
        request[2] = 'W';
        request[3] = 'A';
        request[4] = 1U;
        request[5] = operation;
        request[6] = 0U;
        request[7] = 0U;
        request[8] = static_cast<FreeCADWasmU8>(payloadLength);
        request[9] = static_cast<FreeCADWasmU8>(payloadLength >> 8U);
        request[10] = static_cast<FreeCADWasmU8>(payloadLength >> 16U);
        request[11] = static_cast<FreeCADWasmU8>(payloadLength >> 24U);
        requestLength = 12U;
    }

    static void appendBytes(const FreeCADWasmU8* bytes, FreeCADWasmU32 length)
    {
        for (FreeCADWasmU32 index = 0U; index < length; ++index) {
            request[requestLength++] = bytes[index];
        }
    }

    static void appendU32(FreeCADWasmU32 value)
    {
        for (FreeCADWasmU32 shift = 0U; shift < 32U; shift += 8U) {
            request[requestLength++] = static_cast<FreeCADWasmU8>(value >> shift);
        }
    }

    static void appendU64(FreeCADWasmU64 value)
    {
        for (FreeCADWasmU32 shift = 0U; shift < 64U; shift += 8U) {
            request[requestLength++] = static_cast<FreeCADWasmU8>(value >> shift);
        }
    }

    static void appendDouble(double value)
    {
        union
        {
            double value;
            FreeCADWasmU64 bits;
        } encoded {value};
        appendU64(encoded.bits);
    }

    static bool call(Handle* result)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto address = static_cast<FreeCADWasmU32>(response);
        const auto length = static_cast<FreeCADWasmU32>(response >> 32U);
        if (length != 8U || address == 0U) {
            if (address != 0U) {
                freecad_release(address);
            }
            return false;
        }

        const auto* bytes = reinterpret_cast<const FreeCADWasmU8*>(
            static_cast<FreeCADWasmU32>(address));
        *result = 0U;
        for (FreeCADWasmU32 shift = 0U; shift < 64U; shift += 8U) {
            *result |= static_cast<Handle>(bytes[shift / 8U]) << shift;
        }
        freecad_release(address);
        return *result != 0U;
    }

    inline static FreeCADWasmU8 request[MaxRequestSize] = {};
    inline static FreeCADWasmU32 requestLength = 0U;
};

}  // namespace Guest

}  // namespace Wasm

#undef FREECAD_WASM_IMPORT
