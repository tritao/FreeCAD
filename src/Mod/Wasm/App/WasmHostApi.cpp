// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmHostApi.h"

#include "WasmAbi.h"
#include "freecad_wasm_dispatch_metadata.hpp"

#include <App/Application.h>
#include <App/Document.h>
#include <App/DocumentObject.h>
#include <Base/Console.h>
#include <Base/Exception.h>
#include <Base/Vector3D.h>

#ifdef FREECAD_WASM_HAS_PART
# include <Mod/Part/App/PartFeature.h>
# include <Mod/Part/App/TopoShape.h>
# include <BRepGProp.hxx>
# include <BRepPrimAPI_MakeBox.hxx>
# include <GProp_GProps.hxx>
# include <Standard_Failure.hxx>
#endif

#include <algorithm>
#include <cmath>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <utility>

using namespace Wasm;

namespace
{

using ByteSpan = std::span<const std::byte>;

bool readU32(ByteSpan bytes, std::size_t& offset, std::uint32_t& value)
{
    if (offset > bytes.size() || bytes.size() - offset < sizeof(value)) {
        return false;
    }

    value = 0U;
    for (unsigned shift = 0U; shift < 32U; shift += 8U) {
        value |= static_cast<std::uint32_t>(
                     std::to_integer<std::uint8_t>(bytes[offset++]))
            << shift;
    }
    return true;
}

bool readU64(ByteSpan bytes, std::size_t& offset, std::uint64_t& value)
{
    if (offset > bytes.size() || bytes.size() - offset < sizeof(value)) {
        return false;
    }

    value = 0U;
    for (unsigned shift = 0U; shift < 64U; shift += 8U) {
        value |= static_cast<std::uint64_t>(
                     std::to_integer<std::uint8_t>(bytes[offset++]))
            << shift;
    }
    return true;
}

bool readDouble(ByteSpan bytes, std::size_t& offset, double& value)
{
    std::uint64_t bits = 0U;
    if (!readU64(bytes, offset, bits)) {
        return false;
    }
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&value, &bits, sizeof(value));
    return true;
}

bool readVector(ByteSpan bytes, std::size_t& offset, Base::Vector3d& value)
{
    return readDouble(bytes, offset, value.x) && readDouble(bytes, offset, value.y)
        && readDouble(bytes, offset, value.z);
}

bool readString(ByteSpan bytes, std::size_t& offset, std::string& value)
{
    std::uint32_t length = 0U;
    if (!readU32(bytes, offset, length)
        || offset > bytes.size()
        || length > bytes.size() - offset) {
        return false;
    }

    value.assign(reinterpret_cast<const char*>(bytes.data() + offset), length);
    offset += length;
    return true;
}

std::string handlePayload(Wasm::HandleId handle)
{
    std::string payload;
    payload.reserve(sizeof(handle));
    Wasm::Abi::appendU64(payload, handle);
    return payload;
}

void appendDouble(std::string& output, double value)
{
    std::uint64_t bits = 0U;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    Wasm::Abi::appendU64(output, bits);
}

std::string vectorPayload(const Base::Vector3d& value)
{
    std::string payload;
    payload.reserve(sizeof(double) * 3U);
    appendDouble(payload, value.x);
    appendDouble(payload, value.y);
    appendDouble(payload, value.z);
    return payload;
}

std::string doublePayload(double value)
{
    std::string payload;
    payload.reserve(sizeof(double));
    appendDouble(payload, value);
    return payload;
}

std::string boolPayload(bool value)
{
    return std::string(1, value ? '\1' : '\0');
}

std::string stringPayload(std::string_view value)
{
    std::string payload;
    payload.reserve(sizeof(std::uint32_t) + value.size());
    Abi::appendU32(payload, static_cast<std::uint32_t>(value.size()));
    payload.append(value);
    return payload;
}

HostCallResult malformedRequest(std::string error)
{
    return {false, {}, std::move(error), Wasm::Abi::ErrorCode::InvalidRequest};
}

HostCallResult malformedResponse(std::string error)
{
    return {false, {}, std::move(error), Wasm::Abi::ErrorCode::Protocol};
}

bool validateWireValue(ByteSpan payload,
                       Generated::WireType type,
                       std::size_t& offset,
                       std::string_view label,
                       std::string& error)
{
    if (type == Generated::WireType::None) {
        return true;
    }

    if (type == Generated::WireType::String) {
        std::uint32_t length = 0U;
        if (!readU32(payload, offset, length)
            || length > payload.size() - offset) {
            error = std::string(label) + " has an invalid string length";
            return false;
        }
        offset += length;
        return true;
    }

    std::size_t valueSize = 0U;
    switch (type) {
    case Generated::WireType::Bool:
        valueSize = sizeof(std::uint8_t);
        break;
    case Generated::WireType::Int64:
    case Generated::WireType::Float64:
    case Generated::WireType::Handle:
        valueSize = sizeof(std::uint64_t);
        break;
    case Generated::WireType::Vector3F64:
        valueSize = sizeof(double) * 3U;
        break;
    case Generated::WireType::None:
    case Generated::WireType::String:
        break;
    }

    if (valueSize == 0U || offset > payload.size()
        || valueSize > payload.size() - offset) {
        error = std::string(label) + " is truncated";
        return false;
    }
    if (type == Generated::WireType::Bool
        && std::to_integer<std::uint8_t>(payload[offset]) > 1U) {
        error = std::string(label) + " is not a canonical boolean";
        return false;
    }
    offset += valueSize;
    return true;
}

bool validateRequestPayload(const Generated::OperationMetadata& metadata,
                            ByteSpan payload,
                            std::string& error)
{
    std::size_t offset = 0U;
    for (const auto& parameter : metadata.parameters) {
        std::string valueError;
        if (!validateWireValue(payload, parameter.type, offset, parameter.name, valueError)) {
            error = std::string(metadata.wireName) + " parameter '"
                + std::string(parameter.name) + "': " + valueError;
            return false;
        }
    }
    if (offset != payload.size()) {
        error = std::string(metadata.wireName) + " has trailing payload bytes";
        return false;
    }
    return true;
}

bool validateResponsePayload(const Generated::OperationMetadata& metadata,
                             ByteSpan payload,
                             std::string& error)
{
    std::size_t offset = 0U;
    std::string valueError;
    if (!validateWireValue(payload,
                           metadata.returnType,
                           offset,
                           "response",
                           valueError)) {
        error = std::string(metadata.wireName) + " response: " + valueError;
        return false;
    }
    if (offset != payload.size()) {
        error = std::string(metadata.wireName) + " response has trailing payload bytes";
        return false;
    }
    return true;
}

#ifdef FREECAD_WASM_HAS_PART
void releaseTopoShape(void* pointer)
{
    delete static_cast<Part::TopoShape*>(pointer);
}
#endif

template<typename T>
T* getHandle(const Wasm::WasmHandleTable& handles,
             std::uint64_t handle,
             std::string_view expectedType,
             std::string& error)
{
    const auto entry = handles.get(handle);
    if (!entry) {
        error = "invalid or expired handle";
        return nullptr;
    }
    if (entry->typeName != expectedType) {
        error = "handle type mismatch: expected " + std::string(expectedType);
        return nullptr;
    }
    if (entry->pointer == nullptr) {
        error = "handle has no native object";
        return nullptr;
    }
    return static_cast<T*>(entry->pointer);
}

Wasm::ValidateCallback documentValidator(std::string documentName)
{
    return [documentName = std::move(documentName)](void* pointer) {
        return App::GetApplication().getDocument(documentName.c_str()) == pointer;
    };
}

Wasm::ValidateCallback objectValidator(std::string documentName, std::string objectName)
{
    return [documentName = std::move(documentName), objectName = std::move(objectName)](void* pointer) {
        auto* document = App::GetApplication().getDocument(documentName.c_str());
        return document != nullptr && document->getObject(objectName.c_str()) == pointer;
    };
}

}  // namespace

WasmHostApi::WasmHostApi(std::thread::id ownerThreadValue)
    : ownerThread(ownerThreadValue)
{
}

HostCallResult WasmHostApi::dispatch(std::string_view request)
{
    return dispatch(request, allowedPermissions);
}

HostCallResult WasmHostApi::dispatch(std::string_view request,
                                     const PermissionSet& permissions)
{
    if (!isOnOwnerThread()) {
        return {false, {}, "WASM host calls must run on the addon owner thread"};
    }

    constexpr std::string_view logPrefix = "freecad.log:";
    if (request.starts_with(logPrefix)) {
        return log(request.substr(logPrefix.size()), permissions);
    }

    return {false, {}, "unsupported host call"};
}

HostCallResult WasmHostApi::dispatch(std::span<const std::byte> request,
                                     const PermissionSet& permissions,
                                     WasmHandleTable& handles)
{
    if (!isOnOwnerThread()) {
        return {false, {}, "WASM host calls must run on the addon owner thread"};
    }

    if (request.size() < Abi::RequestHeaderSize) {
        return malformedRequest("WASM host request is shorter than its header");
    }
    if (!std::equal(Abi::RequestMagic.begin(),
                    Abi::RequestMagic.end(),
                    reinterpret_cast<const std::uint8_t*>(request.data()))) {
        return malformedRequest("WASM host request has an invalid magic value");
    }

    const auto version = std::to_integer<std::uint8_t>(request[4]);
    if (version != Abi::RequestVersion) {
        return malformedRequest("unsupported WASM host ABI version");
    }

    const auto operationId = std::to_integer<std::uint8_t>(request[5]);
    const auto operation = static_cast<Abi::Operation>(operationId);
    const auto* metadata = Generated::findOperationMetadata(operationId);
    if (metadata == nullptr) {
        return {false,
                {},
                "unsupported WASM host operation",
                Abi::ErrorCode::Unsupported};
    }
    const auto flags = std::to_integer<std::uint8_t>(request[6])
        | (static_cast<std::uint16_t>(std::to_integer<std::uint8_t>(request[7])) << 8U);
    if (flags != 0U) {
        return malformedRequest("WASM host request uses unsupported flags");
    }

    std::size_t offset = 8U;
    std::uint32_t payloadSize = 0U;
    if (!readU32(request, offset, payloadSize)
        || payloadSize != request.size() - Abi::RequestHeaderSize) {
        return malformedRequest("WASM host request has an invalid payload length");
    }

    if (!metadata->permission.empty()
        && !hasPermission(permissions, metadata->permission)) {
        return {false,
                {},
                "host capability '" + std::string(metadata->permission)
                    + "' is not granted",
                Abi::ErrorCode::PermissionDenied};
    }

    const auto payload = request.subspan(Abi::RequestHeaderSize);
    const auto handler = handlerFor(operation);
    if (handler == nullptr) {
        return {false,
                {},
                "WASM operation has no registered host handler",
                Abi::ErrorCode::Unsupported};
    }
    std::string payloadError;
    if (!validateRequestPayload(*metadata, payload, payloadError)) {
        return malformedRequest(std::move(payloadError));
    }
    auto result = (this->*handler)(operation, payload, handles);
    if (!result.ok) {
        return result;
    }

    const auto responsePayload = ByteSpan(
        reinterpret_cast<const std::byte*>(result.payload.data()), result.payload.size());
    std::string responseError;
    if (!validateResponsePayload(*metadata, responsePayload, responseError)) {
        return malformedResponse(std::move(responseError));
    }
    return result;
}

WasmHostApi::OperationHandler WasmHostApi::handlerFor(Abi::Operation operation)
{
    switch (operation) {
    case Abi::Operation::VectorNew:
    case Abi::Operation::VectorAdd:
    case Abi::Operation::VectorDot:
    case Abi::Operation::VectorCross:
        return &WasmHostApi::dispatchVectorOperation;
    case Abi::Operation::DocumentNew:
    case Abi::Operation::DocumentAddObject:
    case Abi::Operation::DocumentIsSaved:
    case Abi::Operation::DocumentGetObject:
    case Abi::Operation::DocumentOpenTransaction:
    case Abi::Operation::DocumentCommitTransaction:
    case Abi::Operation::DocumentAbortTransaction:
        return &WasmHostApi::dispatchDocumentOperation;
    case Abi::Operation::DocumentObjectGetLabel:
    case Abi::Operation::DocumentObjectSetLabel:
        return &WasmHostApi::dispatchDocumentObjectOperation;
    case Abi::Operation::PartMakeBox:
    case Abi::Operation::TopoShapeIsNull:
    case Abi::Operation::TopoShapeIsValid:
    case Abi::Operation::TopoShapeLength:
    case Abi::Operation::TopoShapeArea:
    case Abi::Operation::TopoShapeVolume:
        return &WasmHostApi::dispatchTopoShapeOperation;
    case Abi::Operation::HandleRelease:
        return &WasmHostApi::dispatchHandleOperation;
    default:
        return nullptr;
    }
}

bool WasmHostApi::hasOperationHandler(Abi::Operation operation)
{
    return handlerFor(operation) != nullptr;
}

HostCallResult WasmHostApi::dispatchVectorOperation(Abi::Operation operation,
                                                    std::span<const std::byte> payload,
                                                    WasmHandleTable&)
{
    if (operation == Abi::Operation::VectorNew) {
        std::size_t payloadOffset = 0U;
        Base::Vector3d value;
        if (!readVector(payload, payloadOffset, value) || !std::isfinite(value.x)
            || !std::isfinite(value.y) || !std::isfinite(value.z)) {
            return malformedRequest("base.vector.new expects finite f64 values");
        }
        return {true, vectorPayload(value), {}};
    }

    std::size_t payloadOffset = 0U;
    Base::Vector3d left;
    Base::Vector3d right;
    if (!readVector(payload, payloadOffset, left) || !readVector(payload, payloadOffset, right)) {
        return malformedRequest("base.vector operation has an invalid vector payload");
    }
    switch (operation) {
    case Abi::Operation::VectorAdd:
        return {true, vectorPayload(left + right), {}};
    case Abi::Operation::VectorDot:
        return {true, doublePayload(left.Dot(right)), {}};
    case Abi::Operation::VectorCross:
        return {true, vectorPayload(left.Cross(right)), {}};
    default:
        return {false, {}, "unsupported vector operation", Abi::ErrorCode::Unsupported};
    }
}

HostCallResult WasmHostApi::dispatchDocumentOperation(Abi::Operation operation,
                                                       std::span<const std::byte> payload,
                                                       WasmHandleTable& handles)
{
    switch (operation) {
    case Abi::Operation::DocumentNew: {
        std::size_t payloadOffset = 0U;
        std::string name;
        if (!readString(payload, payloadOffset, name) || name.empty()
            || name.find('\0') != std::string::npos) {
            return malformedRequest("document.new has an invalid name payload");
        }

        try {
            auto* document = App::GetApplication().newDocument(name.c_str(), name.c_str());
            if (document == nullptr) {
                return {false, {}, "document.new could not create the document"};
            }
            const auto handle = handles.insert("App::Document",
                                               document,
                                               true,
                                               nullptr,
                                               documentValidator(document->getName()));
            if (handle == InvalidHandle) {
                App::GetApplication().closeDocument(document);
                return {false, {}, "document.new could not allocate a handle"};
            }
            return {true, handlePayload(handle), {}};
        }
        catch (const std::exception& error) {
            return {false, {}, std::string("document.new failed: ") + error.what()};
        }
        catch (const Base::Exception& error) {
            return {false, {}, std::string("document.new failed: ") + error.what()};
        }
    }
    case Abi::Operation::DocumentAddObject: {
#ifndef FREECAD_WASM_HAS_PART
        return {false, {}, "Part capability is not available in this build"};
#else
        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::uint64_t shapeHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readU64(payload, payloadOffset, shapeHandle)
            || !readString(payload, payloadOffset, name) || name.empty()
            || name.find('\0') != std::string::npos) {
            return malformedRequest("document.add_object has an invalid payload");
        }

        std::string error;
        auto* document = getHandle<App::Document>(
            handles, documentHandle, "App::Document", error);
        if (document == nullptr) {
            return {false, {}, error};
        }
        auto* shape = getHandle<Part::TopoShape>(
            handles, shapeHandle, "Part::TopoShape", error);
        if (shape == nullptr) {
            return {false, {}, error};
        }
        if (!hasActiveTransaction(document)) {
            return {false, {}, "document.add_object requires an active transaction"};
        }

        try {
            auto* object = document->addObject<Part::Feature>(name.c_str());
            if (object == nullptr) {
                return {false, {}, "document.add_object could not create the feature"};
            }
            object->Shape.setValue(*shape);
            const auto handle = handles.insert("FreeCAD.DocumentObject",
                                               object,
                                               true,
                                               nullptr,
                                               objectValidator(object->getDocument()->getName(),
                                                               object->getNameInDocument()));
            if (handle == InvalidHandle) {
                return {false, {}, "document.add_object could not allocate a handle"};
            }
            return {true, handlePayload(handle), {}};
        }
        catch (const Standard_Failure& exception) {
            return {false,
                    {},
                    std::string("document.add_object failed: ") + exception.GetMessageString()};
        }
        catch (const Base::Exception& exception) {
            return {false,
                    {},
                    std::string("document.add_object failed: ") + exception.what()};
        }
#endif
    }
    case Abi::Operation::DocumentIsSaved: {
        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        if (!readU64(payload, payloadOffset, documentHandle)) {
            return malformedRequest("document.is_saved has an invalid handle payload");
        }

        std::string error;
        auto* document = getHandle<App::Document>(
            handles, documentHandle, "App::Document", error);
        if (document == nullptr) {
            return {false, {}, error};
        }
        return {true, boolPayload(document->isSaved()), {}};
    }
    case Abi::Operation::DocumentGetObject: {
        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readString(payload, payloadOffset, name) || name.empty()
            || name.find('\0') != std::string::npos) {
            return malformedRequest("document.get_object has an invalid payload");
        }

        std::string error;
        auto* document = getHandle<App::Document>(
            handles, documentHandle, "App::Document", error);
        if (document == nullptr) {
            return {false, {}, error};
        }
        auto* object = document->getObject(name.c_str());
        if (object == nullptr) {
            return {false, {}, "document.get_object could not find the object"};
        }

        const auto handle = handles.insert("FreeCAD.DocumentObject",
                                           object,
                                           true,
                                           nullptr,
                                           objectValidator(document->getName(),
                                                           object->getNameInDocument()));
        if (handle == InvalidHandle) {
            return {false, {}, "document.get_object could not allocate a handle"};
        }
        return {true, handlePayload(handle), {}};
    }
    case Abi::Operation::DocumentOpenTransaction: {
        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readString(payload, payloadOffset, name) || name.empty()
            || name.find('\0') != std::string::npos) {
            return malformedRequest("document.open_transaction has an invalid payload");
        }

        std::string error;
        auto* document = getHandle<App::Document>(
            handles, documentHandle, "App::Document", error);
        if (document == nullptr) {
            return {false, {}, error};
        }
        try {
            const auto transactionId = document->openTransaction(name);
            if (transactionId == 0) {
                return {true, boolPayload(false), {}};
            }
            beginTransaction(document);
            return {true, boolPayload(true), {}};
        }
        catch (const Base::Exception& exception) {
            return {false,
                    {},
                    std::string("document.open_transaction failed: ") + exception.what()};
        }
    }
    case Abi::Operation::DocumentCommitTransaction:
    case Abi::Operation::DocumentAbortTransaction: {
        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        if (!readU64(payload, payloadOffset, documentHandle)) {
            return malformedRequest("document transaction control has an invalid handle payload");
        }

        std::string error;
        auto* document = getHandle<App::Document>(
            handles, documentHandle, "App::Document", error);
        if (document == nullptr) {
            return {false, {}, error};
        }
        if (!hasActiveTransaction(document)) {
            return {false,
                    {},
                    operation == Abi::Operation::DocumentCommitTransaction
                        ? "document.commit_transaction requires an active transaction"
                        : "document.abort_transaction requires an active transaction"};
        }
        try {
            if (operation == Abi::Operation::DocumentCommitTransaction) {
                document->commitTransaction();
            }
            else {
                document->abortTransaction();
            }
            endTransaction(document);
            return {true, boolPayload(true), {}};
        }
        catch (const Base::Exception& exception) {
            return {false, {}, std::string("document transaction control failed: ") + exception.what()};
        }
    }
    default:
        return {false, {}, "unsupported document operation", Abi::ErrorCode::Unsupported};
    }
}

HostCallResult WasmHostApi::dispatchDocumentObjectOperation(
    Abi::Operation operation,
    std::span<const std::byte> payload,
    WasmHandleTable& handles)
{
    switch (operation) {
    case Abi::Operation::DocumentObjectGetLabel: {
        std::size_t payloadOffset = 0U;
        std::uint64_t objectHandle = InvalidHandle;
        if (!readU64(payload, payloadOffset, objectHandle)) {
            return malformedRequest("document.object.get_label has an invalid handle payload");
        }
        std::string error;
        auto* object = getHandle<App::DocumentObject>(
            handles, objectHandle, "FreeCAD.DocumentObject", error);
        if (object == nullptr) {
            return {false, {}, error};
        }
        return {true, stringPayload(object->Label.getValue()), {}};
    }
    case Abi::Operation::DocumentObjectSetLabel: {
        std::size_t payloadOffset = 0U;
        std::uint64_t objectHandle = InvalidHandle;
        std::string label;
        if (!readU64(payload, payloadOffset, objectHandle)
            || !readString(payload, payloadOffset, label)
            || label.find('\0') != std::string::npos) {
            return malformedRequest("document.object.set_label has an invalid payload");
        }
        std::string error;
        auto* object = getHandle<App::DocumentObject>(
            handles, objectHandle, "FreeCAD.DocumentObject", error);
        if (object == nullptr) {
            return {false, {}, error};
        }
        auto* document = object->getDocument();
        if (document == nullptr || !hasActiveTransaction(document)) {
            return {false, {}, "document.object.set_label requires an active transaction"};
        }
        try {
            object->Label.setValue(label);
            return {true, boolPayload(true), {}};
        }
        catch (const Base::Exception& exception) {
            return {false,
                    {},
                    std::string("document.object.set_label failed: ") + exception.what()};
        }
    }
    default:
        return {false,
                {},
                "unsupported document object operation",
                Abi::ErrorCode::Unsupported};
    }
}

HostCallResult WasmHostApi::dispatchTopoShapeOperation(Abi::Operation operation,
                                                        std::span<const std::byte> payload,
                                                        WasmHandleTable& handles)
{
#ifndef FREECAD_WASM_HAS_PART
    return {false, {}, "Part capability is not available in this build"};
#else
    if (operation == Abi::Operation::PartMakeBox) {
        std::size_t payloadOffset = 0U;
        double length = 0.0;
        double width = 0.0;
        double height = 0.0;
        if (!readDouble(payload, payloadOffset, length)
            || !readDouble(payload, payloadOffset, width)
            || !readDouble(payload, payloadOffset, height)
            || !std::isfinite(length) || !std::isfinite(width) || !std::isfinite(height)
            || length <= 0.0 || width <= 0.0 || height <= 0.0) {
            return malformedRequest("part.make_box dimensions must be finite and positive");
        }

        try {
            const auto shape = BRepPrimAPI_MakeBox(length, width, height).Shape();
            auto ownedShape = std::make_unique<Part::TopoShape>(shape);
            auto* shapePointer = ownedShape.get();
            const auto handle = handles.insert(
                "Part::TopoShape", shapePointer, false, releaseTopoShape);
            if (handle == InvalidHandle) {
                return {false, {}, "part.make_box could not allocate a handle"};
            }
            ownedShape.release();
            return {true, handlePayload(handle), {}};
        }
        catch (const Standard_Failure& error) {
            return {false, {}, std::string("part.make_box failed: ") + error.GetMessageString()};
        }
    }

    std::size_t payloadOffset = 0U;
    std::uint64_t shapeHandle = InvalidHandle;
    if (!readU64(payload, payloadOffset, shapeHandle)) {
        return malformedRequest("part.topo_shape query has an invalid handle payload");
    }

    std::string error;
    auto* shape = getHandle<Part::TopoShape>(
        handles, shapeHandle, "Part::TopoShape", error);
    if (shape == nullptr) {
        return {false, {}, error};
    }

    switch (operation) {
    case Abi::Operation::TopoShapeIsNull:
        return {true, boolPayload(shape->isNull()), {}};
    case Abi::Operation::TopoShapeIsValid:
        return {true, boolPayload(shape->isValid()), {}};
    case Abi::Operation::TopoShapeLength: {
        if (shape->isNull()) {
            return {false, {}, "part.topo_shape.length cannot query a null shape"};
        }
        GProp_GProps properties;
        BRepGProp::LinearProperties(shape->getShape(), properties);
        return {true, doublePayload(properties.Mass()), {}};
    }
    case Abi::Operation::TopoShapeArea: {
        if (shape->isNull()) {
            return {false, {}, "part.topo_shape.area cannot query a null shape"};
        }
        GProp_GProps properties;
        BRepGProp::SurfaceProperties(shape->getShape(), properties);
        return {true, doublePayload(properties.Mass()), {}};
    }
    case Abi::Operation::TopoShapeVolume: {
        if (shape->isNull()) {
            return {false, {}, "part.topo_shape.volume cannot query a null shape"};
        }
        GProp_GProps properties;
        BRepGProp::VolumeProperties(shape->getShape(), properties);
        return {true, doublePayload(properties.Mass()), {}};
    }
    default:
        return {false, {}, "unsupported Part query", Abi::ErrorCode::Unsupported};
    }
#endif
}

HostCallResult WasmHostApi::dispatchHandleOperation(Abi::Operation operation,
                                                    std::span<const std::byte> payload,
                                                    WasmHandleTable& handles)
{
    if (operation != Abi::Operation::HandleRelease) {
        return {false, {}, "unsupported handle operation", Abi::ErrorCode::Unsupported};
    }
    std::size_t payloadOffset = 0U;
    std::uint64_t handle = InvalidHandle;
    if (!readU64(payload, payloadOffset, handle)) {
        return {false, {}, "invalid or expired handle"};
    }
    const auto entry = handles.get(handle);
    if (!entry.has_value()) {
        return {false, {}, "invalid or expired handle"};
    }
    if (entry->typeName == "App::Document") {
        clearTransactionsFor(static_cast<App::Document*>(entry->pointer));
    }
    if (!handles.erase(handle)) {
        return {false, {}, "invalid or expired handle"};
    }
    return {true, {}, {}};
}

HostCallResult WasmHostApi::log(std::string_view message)
{
    return log(message, allowedPermissions);
}

HostCallResult WasmHostApi::log(std::string_view message, const PermissionSet& permissions)
{
    if (!isOnOwnerThread()) {
        return {false, {}, "WASM host calls must run on the addon owner thread"};
    }

    if (!hasPermission(permissions, "console.log")) {
        return {false, {}, "host capability 'console.log' is not granted"};
    }

    Base::Console().message("%.*s\n", static_cast<int>(message.size()), message.data());
    return {true, "null", {}};
}

bool WasmHostApi::hasActiveTransaction(const App::Document* document) const
{
    const auto transaction = transactions.find(document);
    return transaction != transactions.end() && transaction->second.depth != 0U;
}

void WasmHostApi::beginTransaction(App::Document* document)
{
    auto& transaction = transactions[document];
    transaction.name = document->getName();
    ++transaction.depth;
}

void WasmHostApi::endTransaction(App::Document* document)
{
    const auto transaction = transactions.find(document);
    if (transaction == transactions.end()) {
        return;
    }
    if (transaction->second.depth > 1U) {
        --transaction->second.depth;
    }
    else {
        transactions.erase(transaction);
    }
}

void WasmHostApi::clearTransactionsFor(App::Document* document)
{
    const auto transaction = transactions.find(document);
    if (transaction == transactions.end()) {
        return;
    }

    const auto* currentDocument = App::GetApplication().getDocument(
        transaction->second.name.c_str());
    if (currentDocument == document) {
        for (std::size_t index = 0U; index < transaction->second.depth; ++index) {
            try {
                document->abortTransaction();
            }
            catch (...) {
                break;
            }
        }
    }
    transactions.erase(transaction);
}

void WasmHostApi::clearTransactions()
{
    for (const auto& [document, transaction] : transactions) {
        const auto* currentDocument = App::GetApplication().getDocument(
            transaction.name.c_str());
        if (currentDocument != document) {
            continue;
        }
        for (std::size_t index = 0U; index < transaction.depth; ++index) {
            try {
                document->abortTransaction();
            }
            catch (...) {
                break;
            }
        }
    }
    transactions.clear();
}

void WasmHostApi::setPermissions(const std::vector<std::string>& permissions)
{
    allowedPermissions.clear();
    for (const auto& permission : permissions) {
        if (isKnownPermission(permission)) {
            allowedPermissions.insert(permission);
        }
    }
}

const WasmHostApi::PermissionSet& WasmHostApi::permissions() const
{
    return allowedPermissions;
}

bool WasmHostApi::isOnOwnerThread() const
{
    return std::this_thread::get_id() == ownerThread;
}

bool WasmHostApi::hasPermission(const PermissionSet& permissions, std::string_view permission)
{
    return permissions.find(std::string(permission)) != permissions.end();
}
