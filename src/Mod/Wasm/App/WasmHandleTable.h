// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>

namespace Wasm
{

using HandleId = std::uint64_t;
using ReleaseCallback = void (*)(void*);
using ValidateCallback = std::function<bool(void*)>;

constexpr HandleId InvalidHandle = 0;

struct HandleEntry
{
    std::string typeName;
    void* pointer = nullptr;
    bool borrowed = true;
    ReleaseCallback release = nullptr;
    ValidateCallback validate;
};

class WasmHandleTable
{
public:
    ~WasmHandleTable();

    HandleId insert(std::string typeName, void* pointer, bool borrowed = true);
    HandleId insert(std::string typeName,
                    void* pointer,
                    bool borrowed,
                    ReleaseCallback release,
                    ValidateCallback validate = {});
    std::optional<HandleEntry> get(HandleId id) const;
    bool erase(HandleId id);
    void clear();
    std::size_t size() const;

private:
    static void releaseEntry(const HandleEntry& entry);

    HandleId nextId = 1;
    std::unordered_map<HandleId, HandleEntry> entries;
};

}  // namespace Wasm
