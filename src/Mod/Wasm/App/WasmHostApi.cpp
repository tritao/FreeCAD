// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmHostApi.h"

#include "WasmAbi.h"

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
    return {false, {}, std::move(error)};
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

    const auto operation = static_cast<Abi::Operation>(std::to_integer<std::uint8_t>(request[5]));
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

    const auto payload = request.subspan(Abi::RequestHeaderSize);
    switch (operation) {
    case Abi::Operation::VectorNew: {
        if (!hasPermission(permissions, "geometry.compute")) {
            return {false, {}, "host capability 'geometry.compute' is not granted"};
        }
        if (payload.size() != sizeof(double) * 3U) {
            return malformedRequest("base.vector.new expects three f64 values");
        }

        std::size_t payloadOffset = 0U;
        Base::Vector3d value;
        if (!readVector(payload, payloadOffset, value) || !std::isfinite(value.x)
            || !std::isfinite(value.y) || !std::isfinite(value.z)) {
            return malformedRequest("base.vector.new expects finite f64 values");
        }
        return {true, vectorPayload(value), {}};
    }
    case Abi::Operation::VectorAdd: {
        if (!hasPermission(permissions, "geometry.compute")) {
            return {false, {}, "host capability 'geometry.compute' is not granted"};
        }
        if (payload.size() != sizeof(double) * 6U) {
            return malformedRequest("base.vector.add expects two vector values");
        }

        std::size_t payloadOffset = 0U;
        Base::Vector3d left;
        Base::Vector3d right;
        if (!readVector(payload, payloadOffset, left) || !readVector(payload, payloadOffset, right)) {
            return malformedRequest("base.vector.add has an invalid vector payload");
        }
        return {true, vectorPayload(left + right), {}};
    }
    case Abi::Operation::VectorDot: {
        if (!hasPermission(permissions, "geometry.compute")) {
            return {false, {}, "host capability 'geometry.compute' is not granted"};
        }
        if (payload.size() != sizeof(double) * 6U) {
            return malformedRequest("base.vector.dot expects two vector values");
        }

        std::size_t payloadOffset = 0U;
        Base::Vector3d left;
        Base::Vector3d right;
        if (!readVector(payload, payloadOffset, left) || !readVector(payload, payloadOffset, right)) {
            return malformedRequest("base.vector.dot has an invalid vector payload");
        }
        return {true, doublePayload(left.Dot(right)), {}};
    }
    case Abi::Operation::VectorCross: {
        if (!hasPermission(permissions, "geometry.compute")) {
            return {false, {}, "host capability 'geometry.compute' is not granted"};
        }
        if (payload.size() != sizeof(double) * 6U) {
            return malformedRequest("base.vector.cross expects two vector values");
        }

        std::size_t payloadOffset = 0U;
        Base::Vector3d left;
        Base::Vector3d right;
        if (!readVector(payload, payloadOffset, left) || !readVector(payload, payloadOffset, right)) {
            return malformedRequest("base.vector.cross has an invalid vector payload");
        }
        return {true, vectorPayload(left.Cross(right)), {}};
    }
    case Abi::Operation::DocumentNew: {
        if (!hasPermission(permissions, "document.create")) {
            return {false, {}, "host capability 'document.create' is not granted"};
        }

        std::size_t payloadOffset = 0U;
        std::string name;
        if (!readString(payload, payloadOffset, name) || payloadOffset != payload.size()
            || name.empty() || name.find('\0') != std::string::npos) {
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
    case Abi::Operation::PartMakeBox: {
#ifndef FREECAD_WASM_HAS_PART
        return {false, {}, "Part capability is not available in this build"};
#else
        if (!hasPermission(permissions, "geometry.create")) {
            return {false, {}, "host capability 'geometry.create' is not granted"};
        }
        if (payload.size() != sizeof(double) * 3U) {
            return malformedRequest("part.make_box expects three f64 values");
        }

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
#endif
    }
    case Abi::Operation::DocumentAddObject: {
#ifndef FREECAD_WASM_HAS_PART
        return {false, {}, "Part capability is not available in this build"};
#else
        if (!hasPermission(permissions, "document.modify")) {
            return {false, {}, "host capability 'document.modify' is not granted"};
        }

        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::uint64_t shapeHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readU64(payload, payloadOffset, shapeHandle)
            || !readString(payload, payloadOffset, name)
            || payloadOffset != payload.size() || name.empty()
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
        if (!hasPermission(permissions, "document.read")) {
            return {false, {}, "host capability 'document.read' is not granted"};
        }
        if (payload.size() != sizeof(std::uint64_t)) {
            return malformedRequest("document.is_saved expects one document handle");
        }

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
        if (!hasPermission(permissions, "document.read")) {
            return {false, {}, "host capability 'document.read' is not granted"};
        }

        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readString(payload, payloadOffset, name)
            || payloadOffset != payload.size() || name.empty()
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
        if (!hasPermission(permissions, "document.modify")) {
            return {false, {}, "host capability 'document.modify' is not granted"};
        }

        std::size_t payloadOffset = 0U;
        std::uint64_t documentHandle = InvalidHandle;
        std::string name;
        if (!readU64(payload, payloadOffset, documentHandle)
            || !readString(payload, payloadOffset, name)
            || payloadOffset != payload.size() || name.empty()
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
            return {true, boolPayload(document->openTransaction(name) != 0), {}};
        }
        catch (const Base::Exception& exception) {
            return {false,
                    {},
                    std::string("document.open_transaction failed: ") + exception.what()};
        }
    }
    case Abi::Operation::DocumentCommitTransaction:
    case Abi::Operation::DocumentAbortTransaction: {
        if (!hasPermission(permissions, "document.modify")) {
            return {false, {}, "host capability 'document.modify' is not granted"};
        }
        if (payload.size() != sizeof(std::uint64_t)) {
            return malformedRequest("document transaction control expects one document handle");
        }

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
        try {
            if (operation == Abi::Operation::DocumentCommitTransaction) {
                document->commitTransaction();
            }
            else {
                document->abortTransaction();
            }
            return {true, boolPayload(true), {}};
        }
        catch (const Base::Exception& exception) {
            return {false, {}, std::string("document transaction control failed: ") + exception.what()};
        }
    }
    case Abi::Operation::DocumentObjectGetLabel: {
        if (!hasPermission(permissions, "document.read")) {
            return {false, {}, "host capability 'document.read' is not granted"};
        }
        if (payload.size() != sizeof(std::uint64_t)) {
            return malformedRequest("document.object.get_label expects one object handle");
        }

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
        if (!hasPermission(permissions, "document.modify")) {
            return {false, {}, "host capability 'document.modify' is not granted"};
        }

        std::size_t payloadOffset = 0U;
        std::uint64_t objectHandle = InvalidHandle;
        std::string label;
        if (!readU64(payload, payloadOffset, objectHandle)
            || !readString(payload, payloadOffset, label)
            || payloadOffset != payload.size() || label.find('\0') != std::string::npos) {
            return malformedRequest("document.object.set_label has an invalid payload");
        }
        std::string error;
        auto* object = getHandle<App::DocumentObject>(
            handles, objectHandle, "FreeCAD.DocumentObject", error);
        if (object == nullptr) {
            return {false, {}, error};
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
    case Abi::Operation::TopoShapeIsNull:
    case Abi::Operation::TopoShapeIsValid:
    case Abi::Operation::TopoShapeLength:
    case Abi::Operation::TopoShapeArea:
    case Abi::Operation::TopoShapeVolume: {
#ifndef FREECAD_WASM_HAS_PART
        return {false, {}, "Part capability is not available in this build"};
#else
        if (!hasPermission(permissions, "geometry.read")) {
            return {false, {}, "host capability 'geometry.read' is not granted"};
        }
        if (payload.size() != sizeof(std::uint64_t)) {
            return malformedRequest("part.topo_shape query expects one shape handle");
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
            return {false, {}, "unsupported Part query"};
        }
#endif
    }
    case Abi::Operation::HandleRelease: {
        if (payload.size() != sizeof(std::uint64_t)) {
            return malformedRequest("handle.release expects one u64 handle");
        }
        std::size_t payloadOffset = 0U;
        std::uint64_t handle = InvalidHandle;
        if (!readU64(payload, payloadOffset, handle) || !handles.erase(handle)) {
            return {false, {}, "invalid or expired handle"};
        }
        return {true, {}, {}};
    }
    default:
        return {false, {}, "unsupported WASM host operation"};
    }
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
