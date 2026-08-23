// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "WasmHandleTable.h"
#include "WasmPermissions.h"

#include <cstddef>
#include <span>
#include <string>
#include <string_view>
#include <thread>
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
    bool ok = false;
    std::string payload;
    std::string error;
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
    void clearTransactions();

private:
    struct TransactionState
    {
        std::string name;
        std::size_t depth = 0U;
    };

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
