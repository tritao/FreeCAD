// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmHandleTable.h"
#include "../WasmAbi.h"
#include "WasmPermissions.h"

#include <cstddef>
#include <span>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace App
{
class Document;
}

namespace Wasm
{

struct HostCallResult
{
    HostCallResult() = default;

    HostCallResult(bool success,
                   std::string responsePayload,
                   std::string errorMessage,
                   Abi::ErrorCode code = Abi::ErrorCode::None)
        : ok(success)
        , payload(std::move(responsePayload))
        , error(std::move(errorMessage))
        , errorCode(success || code != Abi::ErrorCode::None ? code : inferErrorCode(error))
    {
    }

    static Abi::ErrorCode inferErrorCode(std::string_view errorMessage)
    {
        if (errorMessage.find("not granted") != std::string_view::npos) {
            return Abi::ErrorCode::PermissionDenied;
        }
        if (errorMessage.find("handle") != std::string_view::npos) {
            return Abi::ErrorCode::InvalidHandle;
        }
        if (errorMessage.find("unsupported") != std::string_view::npos
            || errorMessage.find("not available") != std::string_view::npos) {
            return Abi::ErrorCode::Unsupported;
        }
        if (errorMessage.find("exceeds") != std::string_view::npos) {
            return Abi::ErrorCode::LimitExceeded;
        }
        return Abi::ErrorCode::HostFailure;
    }

    bool ok = false;
    std::string payload;
    std::string error;
    Abi::ErrorCode errorCode = Abi::ErrorCode::None;
};

class WasmHostApi
{
public:
    using PermissionSet = std::unordered_set<std::string>;

    explicit WasmHostApi(std::thread::id ownerThread = std::this_thread::get_id());

    HostCallResult dispatch(std::string_view request);
    HostCallResult dispatch(std::string_view request, const PermissionSet& permissions);
    HostCallResult dispatch(std::span<const std::byte> request,
                            const PermissionSet& permissions,
                            WasmHandleTable& handles);
    HostCallResult log(std::string_view message);
    HostCallResult log(std::string_view message, const PermissionSet& permissions);

    void setPermissions(const std::vector<std::string>& permissions);
    const PermissionSet& permissions() const;
    bool isOnOwnerThread() const;
    static bool hasOperationHandler(Abi::Operation operation);
    void clearTransactions();

private:
    using OperationHandler = HostCallResult (WasmHostApi::*)(
        Abi::Operation,
        std::span<const std::byte>,
        WasmHandleTable&);

    struct TransactionState
    {
        std::string name;
        std::size_t depth = 0U;
    };

    static OperationHandler handlerFor(Abi::Operation operation);
    HostCallResult dispatchVectorOperation(Abi::Operation operation,
                                           std::span<const std::byte> payload,
                                           WasmHandleTable& handles);
    HostCallResult dispatchDocumentOperation(Abi::Operation operation,
                                              std::span<const std::byte> payload,
                                              WasmHandleTable& handles);
    HostCallResult dispatchDocumentObjectOperation(Abi::Operation operation,
                                                    std::span<const std::byte> payload,
                                                    WasmHandleTable& handles);
    HostCallResult dispatchTopoShapeOperation(Abi::Operation operation,
                                              std::span<const std::byte> payload,
                                              WasmHandleTable& handles);
    HostCallResult dispatchHandleOperation(Abi::Operation operation,
                                           std::span<const std::byte> payload,
                                           WasmHandleTable& handles);

    static bool hasPermission(const PermissionSet& permissions, std::string_view permission);
    bool hasActiveTransaction(const App::Document* document) const;
    void beginTransaction(App::Document* document);
    void endTransaction(App::Document* document);
    void clearTransactionsFor(App::Document* document);

    std::thread::id ownerThread;
    PermissionSet allowedPermissions;
    std::unordered_map<const App::Document*, TransactionState> transactions;
};

}  // namespace Wasm
