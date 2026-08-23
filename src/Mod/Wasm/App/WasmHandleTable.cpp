// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"
#include "WasmHandleTable.h"

#include <utility>

using namespace Wasm;

HandleId WasmHandleTable::insert(std::string typeName, void* pointer, bool borrowed)
{
    return insert(std::move(typeName), pointer, borrowed, nullptr);
}

HandleId WasmHandleTable::insert(std::string typeName,
                                 void* pointer,
                                 bool borrowed,
                                 ReleaseCallback release,
                                 ValidateCallback validate)
{
    if (pointer == nullptr || (!borrowed && release == nullptr)) {
        return InvalidHandle;
    }

    const HandleId id = nextId++;
    entries.emplace(id,
                    HandleEntry {std::move(typeName), pointer, borrowed, release, std::move(validate)});
    return id;
}

std::optional<HandleEntry> WasmHandleTable::get(HandleId id) const
{
    const auto it = entries.find(id);
    if (it == entries.end()) {
        return std::nullopt;
    }

    if (it->second.validate && !it->second.validate(it->second.pointer)) {
        return std::nullopt;
    }

    return it->second;
}

bool WasmHandleTable::erase(HandleId id)
{
    const auto it = entries.find(id);
    if (it == entries.end()) {
        return false;
    }

    const auto entry = it->second;
    entries.erase(it);
    releaseEntry(entry);
    return true;
}

void WasmHandleTable::clear()
{
    for (const auto& [id, entry] : entries) {
        static_cast<void>(id);
        releaseEntry(entry);
    }
    entries.clear();
}

std::size_t WasmHandleTable::size() const
{
    return entries.size();
}

WasmHandleTable::~WasmHandleTable()
{
    clear();
}

void WasmHandleTable::releaseEntry(const HandleEntry& entry)
{
    if (!entry.borrowed && entry.release != nullptr) {
        entry.release(entry.pointer);
    }
}
