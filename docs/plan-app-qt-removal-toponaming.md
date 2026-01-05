# App Qt Removal: Topo-Naming Data Structures (MappedName / IndexedName / StringHasher / ElementMap)

## Goal
Remove Qt types from App’s public topo-naming APIs while preserving current semantics and performance characteristics. This unblocks:

- Headless / non-Qt App builds (eventually)
- Emscripten/WASM targets (long-term)
- Cleaner layer boundaries (Qt in Gui, not in core data structures)

Scope in this plan:

- `Data::MappedName`
- `Data::IndexedName`
- `App::StringID` / `App::StringHasher`
- `Data::ElementMap`

Non-goals (for this slice):

- Removing all Qt from `FreeCADApp` (paths/settings/branding/etc)
- Changing serialization formats for element maps or string tables

## Current problems (what makes Qt removal hard)
- Qt types are exposed directly in headers (`QByteArray`, `QHash`, `QVector`, `QString`), causing dependency leakage.
- Core semantics rely on Qt’s byte storage behavior:
  - “borrow for lookup, copy on insert” patterns (`fromRawData`, `NoCopy` option)
  - cheap copy / shared backing storage (Qt implicit sharing)
  - raw-bytes behavior (embedded NULs)
- These types sit on a hot path (topological naming / element map lookups), so naive `std::string` replacement risks performance regressions.

## Invariants / behavior to preserve
- Byte payloads may contain embedded NULs; APIs must operate on `(data,size)`, not C-strings.
- Borrowed-view operations must remain possible for parsing / lookup without allocating.
- Persisted storage must become owning before the borrowed memory can go out of scope.
- Existing on-disk formats for:
  - `ElementMap2` streams
  - `StringHasher` streams
  remain readable/writable without changes.

## Design: Qt-free byte primitives in Base
To avoid re-inventing ad-hoc “byte string” wrappers in App (and to keep future reuse possible), introduce two core types in `src/Base/`:

- `Base::BytesView`: a non-owning view over bytes (backed by `std::string_view`).
- `Base::ByteBuffer`: a small value type that can be either:
  - owning (shared backing store with copy-on-write semantics), or
  - explicitly borrowed (no ownership, must be made owning before persistence/mutation).

Notes:
- Since the project is currently C++17, we should not rely on C++20 heterogeneous lookup in `std::unordered_map`; instead, we can construct cheap borrowed `ByteBuffer` keys for lookups when needed.

## Implementation plan (commit sequence)

### Commit 1: docs — add this plan
Acceptance:
- `docs/plan-app-qt-removal-toponaming.md` exists and reflects the intended sequence and invariants.

### Commit 2: base — add `Base::BytesView` + `Base::ByteBuffer` + tests
Files:
- `src/Base/BytesView.h`
- `src/Base/ByteBuffer.h` (header-only unless build time forces a `.cpp`)
- `tests/src/Base/ByteBuffer.cpp`
- `tests/src/Base/CMakeLists.txt` updated to include the new test file

Acceptance:
- `ByteBuffer::borrow(...)` creates a non-owning instance.
- `makeOwning()` deep-copies when borrowed.
- Copy-on-write: mutating one copy does not affect another.
- Embedded-NUL payloads are preserved.

### Commit 3: app — refactor `Data::IndexedName` off Qt
Changes:
- Replace `IndexedName(const QByteArray&)` with `IndexedName(Base::BytesView)` (or similar).
- Replace the Qt-based interning helper (`Data::ByteArray` + `qHash`) with `std::string` storage in the interning set.
- Remove Qt includes from `src/App/IndexedName.h`.

Tests:
- Update `tests/src/App/IndexedName.cpp` to stop using `QByteArray` and to keep the “interned pointer reuse” assertion.

Acceptance:
- `src/App/IndexedName.h` has no Qt includes.
- All IndexedName unit tests pass with the new API.

### Commit 4: app — refactor `Data::MappedName` off Qt
Changes:
- Replace `QByteArray` members with `Base::ByteBuffer` (data + postfix).
- Replace APIs returning `QByteArray` with view/buffer equivalents.
- Keep `fromRawData` semantics via `Base::ByteBuffer::borrow(...)`.
- Replace `qHash`-based hashing with byte hashing.

Tests:
- Update `tests/src/App/MappedName.cpp` to use the new API and preserve semantics checks (raw vs owning, sharing, etc).

Acceptance:
- `src/App/MappedName.h` has no Qt includes.
- Existing `MappedName` unit tests preserve intent.

### Commit 5: app — refactor `App::StringID` / `App::StringHasher` off Qt
Changes:
- Replace `QByteArray` with `Base::ByteBuffer`.
- Replace `QVector` with `std::vector`.
- Replace `QCryptographicHash(Sha1)` with a Qt-free SHA1 implementation (e.g. `boost::uuids::detail::sha1`).
- Replace Qt base64 helpers with `src/Base/Base64.h`.
- Update Python wrappers accordingly (`StringHasherPyImp`).

Tests:
- Update `tests/src/App/StringHasher.cpp` to drop Qt usage, and add known-vector tests for SHA1/base64 behavior.

Acceptance:
- `src/App/StringHasher.h` has no Qt includes.
- Serialization formats remain compatible (no intentional changes).

### Commit 6: app — refactor `Data::ElementMap` off Qt
Changes:
- Replace `MappedChildElements::postfix` with `Base::ByteBuffer`.
- Replace `QHash<QByteArray,...>` with `std::unordered_map<Base::ByteBuffer,...>`.
- Replace temporary key creation (`toRawBytes`) with view/slice usage (`BytesView` / borrowed `ByteBuffer`) to avoid allocations.

Tests:
- Update `tests/src/App/ElementMap.cpp` accordingly.

Acceptance:
- `src/App/ElementMap.h` has no Qt includes.
- Element map tests still cover lookup/erase/serialization behaviors.

## Rollback / risk management
- Keep each commit narrowly scoped to one header/API family plus its tests.
- Avoid persistence format changes until we can run upgrade/compat tests on real documents.
- Benchmark later: once functionally correct, run targeted perf checks in topo-naming heavy workflows (separate effort).

