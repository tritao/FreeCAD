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

struct Vector3
{
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

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

        if (name == nullptr) {
            return false;
        }
        const auto nameLength = stringLength(name);
        if (nameLength > MaxStringLength) {
            return false;
        }
        resetRequest(1U, 4U + nameLength);
        appendU32(nameLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(name), nameLength);
        return call(result);
    }

    bool documentIsSaved(Handle document, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(9U, 8U);
        appendU64(document);
        return call(result);
    }

    bool documentGetObject(Handle document, const char* name, Handle* result) const
    {
        if (result == nullptr) {
            return false;
        }

        if (name == nullptr) {
            return false;
        }
        const auto nameLength = stringLength(name);
        if (nameLength > MaxStringLength) {
            return false;
        }
        resetRequest(10U, 12U + nameLength);
        appendU64(document);
        appendU32(nameLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(name), nameLength);
        return call(result);
    }

    bool documentOpenTransaction(Handle document, const char* name, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        if (name == nullptr) {
            return false;
        }
        const auto nameLength = stringLength(name);
        if (nameLength > MaxStringLength) {
            return false;
        }
        resetRequest(16U, 12U + nameLength);
        appendU64(document);
        appendU32(nameLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(name), nameLength);
        return call(result);
    }

    bool documentCommitTransaction(Handle document, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(17U, 8U);
        appendU64(document);
        return call(result);
    }

    bool documentAbortTransaction(Handle document, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(18U, 8U);
        appendU64(document);
        return call(result);
    }

    bool documentObjectGetLabel(Handle object,
                                char* result,
                                FreeCADWasmU32 capacity,
                                FreeCADWasmU32* length) const
    {
        if (length == nullptr || (capacity != 0U && result == nullptr)) {
            return false;
        }
        resetRequest(19U, 8U);
        appendU64(object);
        return callString(result, capacity, length);
    }

    bool documentObjectSetLabel(Handle object, const char* label, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        if (label == nullptr) {
            return false;
        }
        const auto labelLength = stringLength(label);
        if (labelLength > MaxStringLength) {
            return false;
        }
        resetRequest(20U, 12U + labelLength);
        appendU64(object);
        appendU32(labelLength);
        appendBytes(reinterpret_cast<const FreeCADWasmU8*>(label), labelLength);
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

    bool vectorNew(double x, double y, double z, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(5U, 24U);
        appendDouble(x);
        appendDouble(y);
        appendDouble(z);
        return call(result);
    }

    bool vectorAdd(Vector3 left, Vector3 right, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(6U, 48U);
        appendVector(left);
        appendVector(right);
        return call(result);
    }

    bool vectorDot(Vector3 left, Vector3 right, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(7U, 48U);
        appendVector(left);
        appendVector(right);
        return call(result);
    }

    bool vectorCross(Vector3 left, Vector3 right, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(8U, 48U);
        appendVector(left);
        appendVector(right);
        return call(result);
    }

    bool topoShapeIsNull(Handle shape, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(11U, 8U);
        appendU64(shape);
        return call(result);
    }

    bool topoShapeIsValid(Handle shape, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(12U, 8U);
        appendU64(shape);
        return call(result);
    }

    bool topoShapeLength(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(13U, 8U);
        appendU64(shape);
        return call(result);
    }

    bool topoShapeArea(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(14U, 8U);
        appendU64(shape);
        return call(result);
    }

    bool topoShapeVolume(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        resetRequest(15U, 8U);
        appendU64(shape);
        return call(result);
    }

    bool release(Handle handle) const
    {
        resetRequest(4U, 8U);
        appendU64(handle);
        const auto response = freecad_dispatch(request, requestLength);
        const auto* payload = responsePayload(response, 0U);
        if (payload != nullptr) {
            freecad_release(static_cast<FreeCADWasmU32>(response));
        }
        return payload != nullptr;
    }

private:
    static constexpr FreeCADWasmU32 MaxRequestSize = 512U;
    static constexpr FreeCADWasmU32 MaxStringLength = 128U;
    static constexpr FreeCADWasmU32 ResponseHeaderSize = 12U;

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

    static void appendVector(Vector3 value)
    {
        appendDouble(value.x);
        appendDouble(value.y);
        appendDouble(value.z);
    }

    static bool call(Handle* result)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto* bytes = responsePayload(response, 8U);
        if (bytes == nullptr) {
            return false;
        }

        *result = 0U;
        for (FreeCADWasmU32 shift = 0U; shift < 64U; shift += 8U) {
            *result |= static_cast<Handle>(bytes[shift / 8U]) << shift;
        }
        freecad_release(static_cast<FreeCADWasmU32>(response));
        return *result != 0U;
    }

    static bool call(Vector3* result)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto* bytes = responsePayload(response, 24U);
        if (bytes == nullptr) {
            return false;
        }

        FreeCADWasmU64 components[3] = {};
        for (unsigned component = 0U; component < 3U; ++component) {
            for (FreeCADWasmU32 shift = 0U; shift < 64U; shift += 8U) {
                components[component] |=
                    static_cast<FreeCADWasmU64>(bytes[component * 8U + shift / 8U]) << shift;
            }
        }
        union
        {
            FreeCADWasmU64 bits;
            double value;
        } decoded {};
        decoded.bits = components[0];
        result->x = decoded.value;
        decoded.bits = components[1];
        result->y = decoded.value;
        decoded.bits = components[2];
        result->z = decoded.value;
        freecad_release(static_cast<FreeCADWasmU32>(response));
        return true;
    }

    static bool call(double* result)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto* bytes = responsePayload(response, 8U);
        if (bytes == nullptr) {
            return false;
        }

        union
        {
            FreeCADWasmU64 bits;
            double value;
        } decoded {};
        decoded.bits = 0U;
        for (FreeCADWasmU32 shift = 0U; shift < 64U; shift += 8U) {
            decoded.bits |= static_cast<FreeCADWasmU64>(bytes[shift / 8U]) << shift;
        }
        *result = decoded.value;
        freecad_release(static_cast<FreeCADWasmU32>(response));
        return true;
    }

    static bool call(bool* result)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto* bytes = responsePayload(response, 1U);
        if (bytes == nullptr) {
            return false;
        }

        if (bytes[0] > 1U) {
            freecad_release(static_cast<FreeCADWasmU32>(response));
            return false;
        }
        *result = bytes[0] != 0U;
        freecad_release(static_cast<FreeCADWasmU32>(response));
        return true;
    }

    static bool callString(char* result,
                           FreeCADWasmU32 capacity,
                           FreeCADWasmU32* length)
    {
        const auto response = freecad_dispatch(request, requestLength);
        const auto responseLength = static_cast<FreeCADWasmU32>(response >> 32U);
        if (responseLength < ResponseHeaderSize + 4U) {
            const auto address = static_cast<FreeCADWasmU32>(response);
            if (address != 0U) {
                freecad_release(address);
            }
            return false;
        }
        const auto* bytes = responsePayload(response, responseLength - ResponseHeaderSize);
        if (bytes == nullptr) {
            return false;
        }

        FreeCADWasmU32 valueLength = 0U;
        for (FreeCADWasmU32 shift = 0U; shift < 32U; shift += 8U) {
            valueLength |= static_cast<FreeCADWasmU32>(bytes[shift / 8U]) << shift;
        }
        if (valueLength != responseLength - ResponseHeaderSize - 4U || valueLength > capacity
            || (valueLength != 0U && result == nullptr)) {
            freecad_release(static_cast<FreeCADWasmU32>(response));
            return false;
        }
        for (FreeCADWasmU32 index = 0U; index < valueLength; ++index) {
            result[index] = static_cast<char>(bytes[4U + index]);
        }
        *length = valueLength;
        freecad_release(static_cast<FreeCADWasmU32>(response));
        return true;
    }

    static const FreeCADWasmU8* responsePayload(FreeCADWasmU64 response,
                                                 FreeCADWasmU32 expectedLength)
    {
        const auto address = static_cast<FreeCADWasmU32>(response);
        const auto length = static_cast<FreeCADWasmU32>(response >> 32U);
        if (address == 0U || length < ResponseHeaderSize) {
            if (address != 0U) {
                freecad_release(address);
            }
            return nullptr;
        }
        const auto* bytes = reinterpret_cast<const FreeCADWasmU8*>(address);
        if (bytes[0] != 'F' || bytes[1] != 'C' || bytes[2] != 'W' || bytes[3] != 'R'
            || bytes[4] != 1U || bytes[5] != 0U || bytes[7] != 0U
            || bytes[8] != static_cast<FreeCADWasmU8>(length - ResponseHeaderSize)
            || bytes[9] != static_cast<FreeCADWasmU8>((length - ResponseHeaderSize) >> 8U)
            || bytes[10] != static_cast<FreeCADWasmU8>((length - ResponseHeaderSize) >> 16U)
            || bytes[11] != static_cast<FreeCADWasmU8>((length - ResponseHeaderSize) >> 24U)
            || expectedLength != length - ResponseHeaderSize) {
            freecad_release(address);
            return nullptr;
        }
        return bytes + ResponseHeaderSize;
    }

    inline static FreeCADWasmU8 request[MaxRequestSize] = {};
    inline static FreeCADWasmU32 requestLength = 0U;
};

}  // namespace Guest

}  // namespace Wasm

#undef FREECAD_WASM_IMPORT
