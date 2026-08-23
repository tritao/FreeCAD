// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#if defined(FREECAD_WASM_FREESTANDING)
# include "WasmGuestFreestanding.h"
#else

#include "../WasmAbi.h"

#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#if defined(__wasm__) && defined(__clang__)
# define FREECAD_WASM_IMPORT(module, name) \
    __attribute__((import_module(module), import_name(name)))
#else
# define FREECAD_WASM_IMPORT(module, name)
#endif

extern "C"
{
std::uint32_t freecad_alloc(std::uint32_t size)
    FREECAD_WASM_IMPORT("freecad", "freecad_alloc");
std::uint64_t freecad_dispatch(const std::uint8_t* request, std::uint32_t requestLength)
    FREECAD_WASM_IMPORT("freecad", "freecad_dispatch");
void freecad_release(std::uint32_t responseAddress)
    FREECAD_WASM_IMPORT("freecad", "freecad_release");
}

namespace Wasm
{

namespace Guest
{

using Handle = std::uint64_t;
using AllocFunction = std::uint32_t (*)(std::uint32_t);
using DispatchFunction = std::uint64_t (*)(const std::uint8_t*, std::uint32_t);
using ReleaseFunction = void (*)(std::uint32_t);

struct Vector3
{
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

template<typename T>
struct Result
{
    bool ok = false;
    T value {};
    std::string error;
};

class ResponseBuffer
{
public:
    ResponseBuffer() = default;

    ResponseBuffer(std::uint32_t address, std::uint32_t size, ReleaseFunction release)
        : address(address)
        , size(size)
        , releaseFunction(release)
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
        , releaseFunction(other.releaseFunction)
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
            releaseFunction = other.releaseFunction;
            other.address = 0U;
            other.size = 0U;
        }
        return *this;
    }

    bool valid() const
    {
        return address != 0U && size != 0U;
    }

    std::uint8_t* data() const
    {
        return reinterpret_cast<std::uint8_t*>(static_cast<std::uintptr_t>(address));
    }

    std::uint64_t take()
    {
        if (!valid()) {
            return 0U;
        }
        const auto response = Abi::packResponse(address, size);
        address = 0U;
        size = 0U;
        return response;
    }

private:
    void reset()
    {
        if (address != 0U && releaseFunction != nullptr) {
            releaseFunction(address);
        }
        address = 0U;
        size = 0U;
    }

    std::uint32_t address = 0U;
    std::uint32_t size = 0U;
    ReleaseFunction releaseFunction = nullptr;
};

class Client
{
public:
    explicit Client(DispatchFunction dispatch = freecad_dispatch,
                    ReleaseFunction release = freecad_release,
                    AllocFunction allocate = freecad_alloc)
        : dispatchFunction(dispatch)
        , releaseFunction(release)
        , allocateFunction(allocate)
    {
    }

    Result<Handle> documentNew(std::string_view name) const
    {
        std::string payload;
        if (!appendString(payload, name)) {
            return failure<Handle>("document name exceeds the ABI length limit");
        }
        return callHandle(Abi::Operation::DocumentNew, payload);
    }

    bool documentNew(const char* name, Handle* result) const
    {
        if (name == nullptr || result == nullptr) {
            return false;
        }
        const auto response = documentNew(std::string_view(name));
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<bool> documentIsSaved(Handle document) const
    {
        std::string payload;
        Abi::appendU64(payload, document);
        return callBool(Abi::Operation::DocumentIsSaved, payload);
    }

    bool documentIsSaved(Handle document, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = documentIsSaved(document);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Handle> documentGetObject(Handle document, std::string_view name) const
    {
        std::string payload;
        Abi::appendU64(payload, document);
        if (!appendString(payload, name)) {
            return failure<Handle>("object name exceeds the ABI length limit");
        }
        return callHandle(Abi::Operation::DocumentGetObject, payload);
    }

    bool documentGetObject(Handle document, const char* name, Handle* result) const
    {
        if (name == nullptr || result == nullptr) {
            return false;
        }
        const auto response = documentGetObject(document, std::string_view(name));
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Handle> partMakeBox(double length, double width, double height) const
    {
        std::string payload;
        appendDouble(payload, length);
        appendDouble(payload, width);
        appendDouble(payload, height);
        return callHandle(Abi::Operation::PartMakeBox, payload);
    }

    bool partMakeBox(double length, double width, double height, Handle* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = partMakeBox(length, width, height);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Handle> documentAddObject(Handle document,
                                     Handle shape,
                                     std::string_view name) const
    {
        std::string payload;
        Abi::appendU64(payload, document);
        Abi::appendU64(payload, shape);
        if (!appendString(payload, name)) {
            return failure<Handle>("object name exceeds the ABI length limit");
        }
        return callHandle(Abi::Operation::DocumentAddObject, payload);
    }

    bool documentAddObject(Handle document,
                           Handle shape,
                           const char* name,
                           Handle* result) const
    {
        if (name == nullptr || result == nullptr) {
            return false;
        }
        const auto response = documentAddObject(document, shape, std::string_view(name));
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Vector3> vectorNew(double x, double y, double z) const
    {
        std::string payload;
        appendDouble(payload, x);
        appendDouble(payload, y);
        appendDouble(payload, z);
        return callVector(Abi::Operation::VectorNew, payload);
    }

    bool vectorNew(double x, double y, double z, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = vectorNew(x, y, z);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Vector3> vectorAdd(Vector3 left, Vector3 right) const
    {
        std::string payload;
        appendVector(payload, left);
        appendVector(payload, right);
        return callVector(Abi::Operation::VectorAdd, payload);
    }

    bool vectorAdd(Vector3 left, Vector3 right, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = vectorAdd(left, right);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<double> vectorDot(Vector3 left, Vector3 right) const
    {
        std::string payload;
        appendVector(payload, left);
        appendVector(payload, right);
        return callDouble(Abi::Operation::VectorDot, payload);
    }

    bool vectorDot(Vector3 left, Vector3 right, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = vectorDot(left, right);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<Vector3> vectorCross(Vector3 left, Vector3 right) const
    {
        std::string payload;
        appendVector(payload, left);
        appendVector(payload, right);
        return callVector(Abi::Operation::VectorCross, payload);
    }

    bool vectorCross(Vector3 left, Vector3 right, Vector3* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = vectorCross(left, right);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<bool> topoShapeIsNull(Handle shape) const
    {
        std::string payload;
        Abi::appendU64(payload, shape);
        return callBool(Abi::Operation::TopoShapeIsNull, payload);
    }

    bool topoShapeIsNull(Handle shape, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = topoShapeIsNull(shape);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<bool> topoShapeIsValid(Handle shape) const
    {
        std::string payload;
        Abi::appendU64(payload, shape);
        return callBool(Abi::Operation::TopoShapeIsValid, payload);
    }

    bool topoShapeIsValid(Handle shape, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = topoShapeIsValid(shape);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<double> topoShapeLength(Handle shape) const
    {
        std::string payload;
        Abi::appendU64(payload, shape);
        return callDouble(Abi::Operation::TopoShapeLength, payload);
    }

    bool topoShapeLength(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = topoShapeLength(shape);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<double> topoShapeArea(Handle shape) const
    {
        std::string payload;
        Abi::appendU64(payload, shape);
        return callDouble(Abi::Operation::TopoShapeArea, payload);
    }

    bool topoShapeArea(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = topoShapeArea(shape);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<double> topoShapeVolume(Handle shape) const
    {
        std::string payload;
        Abi::appendU64(payload, shape);
        return callDouble(Abi::Operation::TopoShapeVolume, payload);
    }

    bool topoShapeVolume(Handle shape, double* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = topoShapeVolume(shape);
        if (!response.ok) {
            return false;
        }
        *result = response.value;
        return true;
    }

    Result<bool> release(Handle handle) const
    {
        std::string payload;
        Abi::appendU64(payload, handle);
        const auto result = call(Abi::Operation::HandleRelease, payload);
        if (!result.ok) {
            return {false, false, result.error};
        }
        if (!result.payload.empty()) {
            return {false, false, "handle.release returned an unexpected payload"};
        }
        return {true, true, {}};
    }

    bool release(Handle handle, bool* result) const
    {
        if (result == nullptr) {
            return false;
        }
        const auto response = release(handle);
        *result = response.ok && response.value;
        return response.ok;
    }

    Result<ResponseBuffer> allocateResponse(std::uint32_t size) const
    {
        if (size == 0U) {
            return failure<ResponseBuffer>("response size must be positive");
        }
        if (allocateFunction == nullptr || releaseFunction == nullptr) {
            return failure<ResponseBuffer>("WASM response allocation callbacks are unavailable");
        }
        const auto address = allocateFunction(size);
        if (address == 0U) {
            return failure<ResponseBuffer>("WASM host could not allocate a response buffer");
        }
        return {true, ResponseBuffer(address, size, releaseFunction), {}};
    }

private:
    struct Response
    {
        bool ok = false;
        std::vector<std::uint8_t> payload;
        std::string error;
    };

    template<typename T>
    static Result<T> failure(std::string error)
    {
        return {false, {}, std::move(error)};
    }

    static bool appendString(std::string& output, std::string_view value)
    {
        if (value.size() > std::numeric_limits<std::uint32_t>::max()) {
            return false;
        }
        Abi::appendU32(output, static_cast<std::uint32_t>(value.size()));
        output.append(value);
        return true;
    }

    static void appendDouble(std::string& output, double value)
    {
        std::uint64_t bits = 0U;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        Abi::appendU64(output, bits);
    }

    static void appendVector(std::string& output, Vector3 value)
    {
        appendDouble(output, value.x);
        appendDouble(output, value.y);
        appendDouble(output, value.z);
    }

    Response call(Abi::Operation operation, std::string_view payload) const
    {
        if (dispatchFunction == nullptr || releaseFunction == nullptr) {
            return {false, {}, "WASM host callbacks are unavailable"};
        }
        if (payload.size() > std::numeric_limits<std::uint32_t>::max()) {
            return {false, {}, "WASM host request exceeds the u32 ABI limit"};
        }

        std::string request;
        request.reserve(Abi::RequestHeaderSize + payload.size());
        Abi::appendHeader(request, operation, static_cast<std::uint32_t>(payload.size()));
        request.append(payload);

        const auto response = dispatchFunction(
            reinterpret_cast<const std::uint8_t*>(request.data()),
            static_cast<std::uint32_t>(request.size()));
        const auto address = Abi::responseAddress(response);
        const auto length = Abi::responseLength(response);
        if (length != 0U && address == 0U) {
            return {false, {}, "WASM host returned a null response address"};
        }

        Response result {true, {}, {}};
        if (length != 0U) {
            const auto* responseBytes = reinterpret_cast<const std::uint8_t*>(
                static_cast<std::uintptr_t>(address));
            result.payload.assign(responseBytes, responseBytes + length);
        }
        if (address != 0U) {
            releaseFunction(address);
        }
        return result;
    }

    Result<Handle> callHandle(Abi::Operation operation, std::string_view payload) const
    {
        const auto result = call(operation, payload);
        if (!result.ok) {
            return failure<Handle>(result.error);
        }
        if (result.payload.size() != sizeof(Handle)) {
            return failure<Handle>("WASM host returned an invalid handle payload");
        }

        Handle handle = 0U;
        for (unsigned shift = 0U; shift < 64U; shift += 8U) {
            handle |= static_cast<Handle>(result.payload[shift / 8U]) << shift;
        }
        if (handle == 0U) {
            return failure<Handle>("WASM host returned an invalid handle");
        }
        return {true, handle, {}};
    }

    Result<Vector3> callVector(Abi::Operation operation, std::string_view payload) const
    {
        const auto result = call(operation, payload);
        if (!result.ok) {
            return failure<Vector3>(result.error);
        }
        if (result.payload.size() != sizeof(double) * 3U) {
            return failure<Vector3>("WASM host returned an invalid vector payload");
        }

        Vector3 value;
        std::size_t offset = 0U;
        for (double* component : {&value.x, &value.y, &value.z}) {
            std::uint64_t bits = 0U;
            for (unsigned shift = 0U; shift < 64U; shift += 8U) {
                bits |= static_cast<std::uint64_t>(result.payload[offset++]) << shift;
            }
            std::memcpy(component, &bits, sizeof(bits));
        }
        return {true, value, {}};
    }

    Result<double> callDouble(Abi::Operation operation, std::string_view payload) const
    {
        const auto result = call(operation, payload);
        if (!result.ok) {
            return failure<double>(result.error);
        }
        if (result.payload.size() != sizeof(double)) {
            return failure<double>("WASM host returned an invalid double payload");
        }

        std::uint64_t bits = 0U;
        for (unsigned shift = 0U; shift < 64U; shift += 8U) {
            bits |= static_cast<std::uint64_t>(result.payload[shift / 8U]) << shift;
        }
        double value = 0.0;
        std::memcpy(&value, &bits, sizeof(value));
        return {true, value, {}};
    }

    Result<bool> callBool(Abi::Operation operation, std::string_view payload) const
    {
        const auto result = call(operation, payload);
        if (!result.ok) {
            return failure<bool>(result.error);
        }
        if (result.payload.size() != 1U || result.payload.front() > 1U) {
            return failure<bool>("WASM host returned an invalid bool payload");
        }
        return {true, result.payload.front() != 0U, {}};
    }

    DispatchFunction dispatchFunction;
    ReleaseFunction releaseFunction;
    AllocFunction allocateFunction;
};

}  // namespace Guest

}  // namespace Wasm

#undef FREECAD_WASM_IMPORT

#endif
