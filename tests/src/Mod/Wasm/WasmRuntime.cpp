// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include "WasmAddon.h"
#include "WasmAddonManager.h"
#include "WasmAbi.h"
#include "freecad_wasm_dispatch_metadata.hpp"
#include "Guest/WasmGuest.h"
#include "WasmHandleTable.h"
#include "WasmHostApi.h"
#include "WasmManifest.h"
#include "WasmRuntimeFactory.h"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#if defined(FREECAD_WASM_HAS_PART)
# include <src/App/InitApplication.h>
# include <App/Application.h>
# include <App/Document.h>
# include <Mod/Part/App/PartFeature.h>
#endif

namespace
{

class TemporaryAddon
{
public:
    TemporaryAddon()
    {
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        root = std::filesystem::temp_directory_path()
            / ("freecad-wasm-test-" + std::to_string(stamp));
        addonDirectory = root / "addon";
        std::filesystem::create_directories(addonDirectory);
    }

    ~TemporaryAddon()
    {
        std::error_code error;
        std::filesystem::remove_all(root, error);
    }

    void writeFile(const std::filesystem::path& path, const std::string& contents)
    {
        std::filesystem::create_directories(path.parent_path());
        std::ofstream output(path);
        ASSERT_TRUE(output.good());
        output << contents;
    }

    void writeBinary(const std::filesystem::path& path,
                     const std::vector<unsigned char>& contents)
    {
        std::filesystem::create_directories(path.parent_path());
        std::ofstream output(path, std::ios::binary);
        ASSERT_TRUE(output.good());
        output.write(reinterpret_cast<const char*>(contents.data()), contents.size());
        ASSERT_TRUE(output.good());
    }

    std::filesystem::path writeManifest(const std::string& contents)
    {
        const auto path = addonDirectory / "manifest.json";
        writeFile(path, contents);
        return path;
    }

    std::filesystem::path root;
    std::filesystem::path addonDirectory;
};

bool containsError(const std::vector<std::string>& errors, const std::string& expected)
{
    return std::any_of(errors.begin(), errors.end(), [&expected](const auto& error) {
        return error.find(expected) != std::string::npos;
    });
}

std::string binaryRequest(Wasm::Abi::Operation operation, std::string_view payload = {})
{
    std::string request;
    request.reserve(Wasm::Abi::RequestHeaderSize + payload.size());
    Wasm::Abi::appendHeader(
        request, operation, static_cast<std::uint32_t>(payload.size()));
    request += payload;
    return request;
}

std::string stringPayload(std::string_view value)
{
    std::string payload;
    Wasm::Abi::appendU32(payload, static_cast<std::uint32_t>(value.size()));
    payload.append(value);
    return payload;
}

std::string stringFromPayload(std::string_view payload)
{
    if (payload.size() < sizeof(std::uint32_t)) {
        return {};
    }
    std::uint32_t length = 0U;
    for (unsigned shift = 0U; shift < 32U; shift += 8U) {
        length |= static_cast<std::uint32_t>(
                      static_cast<unsigned char>(payload[shift / 8U]))
            << shift;
    }
    if (length != payload.size() - sizeof(std::uint32_t)) {
        return {};
    }
    return std::string(payload.substr(sizeof(std::uint32_t)));
}

std::string doublePayload(double first, double second, double third)
{
    std::string payload;
    std::uint64_t bits = 0U;
    for (const auto value : {first, second, third}) {
        std::memcpy(&bits, &value, sizeof(bits));
        Wasm::Abi::appendU64(payload, bits);
    }
    return payload;
}

std::string vectorPairPayload(double first,
                              double second,
                              double third,
                              double fourth,
                              double fifth,
                              double sixth)
{
    std::string payload = doublePayload(first, second, third);
    std::uint64_t bits = 0U;
    for (const auto value : {fourth, fifth, sixth}) {
        std::memcpy(&bits, &value, sizeof(bits));
        Wasm::Abi::appendU64(payload, bits);
    }
    return payload;
}

double doubleFromPayload(std::string_view payload, std::size_t offset = 0U)
{
    if (offset > payload.size() || payload.size() - offset < sizeof(double)) {
        return 0.0;
    }
    std::uint64_t bits = 0U;
    for (unsigned shift = 0U; shift < 64U; shift += 8U) {
        bits |= static_cast<std::uint64_t>(
                    static_cast<unsigned char>(payload[offset + shift / 8U]))
            << shift;
    }
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

std::string handlePayload(Wasm::HandleId handle)
{
    std::string payload;
    Wasm::Abi::appendU64(payload, handle);
    return payload;
}

Wasm::HandleId handleFromPayload(std::string_view payload)
{
    if (payload.size() != sizeof(Wasm::HandleId)) {
        return Wasm::InvalidHandle;
    }

    Wasm::HandleId handle = 0U;
    for (unsigned shift = 0U; shift < 64U; shift += 8U) {
        handle |= static_cast<Wasm::HandleId>(
                      static_cast<unsigned char>(payload[shift / 8U]))
            << shift;
    }
    return handle;
}

std::vector<std::byte> asBytes(std::string_view value)
{
    std::vector<std::byte> bytes(value.size());
    if (!value.empty()) {
        std::memcpy(bytes.data(), value.data(), value.size());
    }
    return bytes;
}

#if defined(FREECAD_HAS_WAMR)
void appendLeb128(std::vector<unsigned char>& output, std::uint32_t value)
{
    do {
        auto byte = static_cast<unsigned char>(value & 0x7fU);
        value >>= 7U;
        if (value != 0U) {
            byte |= 0x80U;
        }
        output.push_back(byte);
    } while (value != 0U);
}

void appendSignedLeb128(std::vector<unsigned char>& output, std::int64_t value)
{
    bool more = true;
    while (more) {
        auto byte = static_cast<unsigned char>(value & 0x7f);
        value >>= 7;
        const bool negative = (byte & 0x40U) != 0U;
        more = !((value == 0 && !negative) || (value == -1 && negative));
        if (more) {
            byte |= 0x80U;
        }
        output.push_back(byte);
    }
}

void appendName(std::vector<unsigned char>& output, std::string_view value)
{
    appendLeb128(output, static_cast<std::uint32_t>(value.size()));
    output.insert(output.end(), value.begin(), value.end());
}

void appendSection(std::vector<unsigned char>& output,
                   unsigned char sectionId,
                   const std::vector<unsigned char>& payload)
{
    output.push_back(sectionId);
    appendLeb128(output, static_cast<std::uint32_t>(payload.size()));
    output.insert(output.end(), payload.begin(), payload.end());
}

std::vector<unsigned char> unknownImportFixture()
{
    std::vector<unsigned char> module {
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
    };

    appendSection(module, 1U, {1U, 0x60U, 0U, 0U});

    std::vector<unsigned char> imports;
    appendLeb128(imports, 1U);
    appendName(imports, "wasi_snapshot_preview1");
    appendName(imports, "fd_write");
    imports.push_back(0U);
    appendLeb128(imports, 0U);
    appendSection(module, 2U, imports);
    return module;
}

std::vector<unsigned char> wrongImportSignatureFixture()
{
    std::vector<unsigned char> module {
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
    };

    // freecad_log must have the (i32, i32) -> () ABI. This import has no
    // parameters and is rejected before WAMR instantiation.
    appendSection(module, 1U, {1U, 0x60U, 0U, 0U});

    std::vector<unsigned char> imports;
    appendLeb128(imports, 1U);
    appendName(imports, "freecad");
    appendName(imports, "freecad_log");
    imports.push_back(0U);
    appendLeb128(imports, 0U);
    appendSection(module, 2U, imports);
    return module;
}

std::vector<unsigned char> dispatchFixture()
{
    // A minimal guest that forwards its byte-buffer arguments to the host.
    return {
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
        0x01, 0x07, 0x01, 0x60, 0x02, 0x7f, 0x7f, 0x01, 0x7e,
        0x02, 0x1c, 0x01,
        0x07, 0x66, 0x72, 0x65, 0x65, 0x63, 0x61, 0x64,
        0x10, 0x66, 0x72, 0x65, 0x65, 0x63, 0x61, 0x64, 0x5f,
        0x64, 0x69, 0x73, 0x70, 0x61, 0x74, 0x63, 0x68,
        0x00, 0x00,
        0x03, 0x02, 0x01, 0x00,
        0x05, 0x03, 0x01, 0x00, 0x01,
        0x07, 0x15, 0x02,
        0x08, 0x64, 0x69, 0x73, 0x70, 0x61, 0x74, 0x63, 0x68, 0x00, 0x01,
        0x06, 0x6d, 0x65, 0x6d, 0x6f, 0x72, 0x79, 0x02, 0x00,
        0x0a, 0x0a, 0x01, 0x08, 0x00, 0x20, 0x00, 0x20, 0x01, 0x10, 0x00, 0x0b,
    };
}

std::vector<unsigned char> unownedResponseFixture()
{
    std::vector<unsigned char> module {
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
    };

    appendSection(module, 1U, {1U, 0x60U, 0x02U, 0x7fU, 0x7fU, 0x01U, 0x7eU});
    appendSection(module, 3U, {1U, 0U});
    appendSection(module, 5U, {1U, 0U, 1U});

    std::vector<unsigned char> exports;
    appendLeb128(exports, 2U);
    appendName(exports, "bad");
    exports.push_back(0U);
    appendLeb128(exports, 0U);
    appendName(exports, "memory");
    exports.push_back(2U);
    appendLeb128(exports, 0U);
    appendSection(module, 7U, exports);

    std::vector<unsigned char> body {0U, 0x42U};
    appendSignedLeb128(body, static_cast<std::int64_t>(Wasm::Abi::packResponse(64U, 1U)));
    body.push_back(0x0bU);
    std::vector<unsigned char> code {1U};
    appendLeb128(code, static_cast<std::uint32_t>(body.size()));
    code.insert(code.end(), body.begin(), body.end());
    appendSection(module, 10U, code);
    return module;
}
#endif

class FakeInstance final: public Wasm::IWasmInstance
{
public:
    Wasm::CallResult call(std::string_view, const std::vector<std::byte>&) override
    {
        return {true, {}, {}};
    }
};

class FakeRuntime final: public Wasm::IWasmRuntime
{
public:
    Wasm::RuntimeInfo info() const override
    {
        return {"fake", true, sandboxed, false, false, hardTimeout};
    }

    std::unique_ptr<Wasm::IWasmInstance> instantiate(const std::filesystem::path& path,
                                                      const Wasm::RuntimeLimits&,
                                                      Wasm::WasmHostApi&) override
    {
        instantiatedPath = path;
        if (failInstantiation) {
            return {};
        }
        return std::make_unique<FakeInstance>();
    }

    bool sandboxed = true;
    bool hardTimeout = true;
    bool failInstantiation = false;
    std::filesystem::path instantiatedPath;
};

struct GuestCapture
{
    static std::uint32_t allocate(std::uint32_t)
    {
        return 0U;
    }

    static std::uint64_t dispatch(const std::uint8_t* request, std::uint32_t length)
    {
        lastRequest.assign(reinterpret_cast<const char*>(request), length);
        return 0U;
    }

    static void release(std::uint32_t)
    {
    }

    static std::string lastRequest;
};

std::string GuestCapture::lastRequest;

struct OwnedValue
{
    int* releases;
};

void releaseOwnedValue(void* pointer)
{
    auto* value = static_cast<OwnedValue*>(pointer);
    ++(*value->releases);
    delete value;
}

}  // namespace

TEST(WasmManifestTest, ParsesAndValidatesStrictManifest)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.wasm", "wasm");
    const auto manifestPath = files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":"entry.wasm","permissions":["console.log"]})");

    const auto manifest = Wasm::WasmManifest::loadFromFile(manifestPath);

    EXPECT_TRUE(manifest.validate().empty());
    EXPECT_EQ(manifest.name(), "Example");
    EXPECT_EQ(manifest.api(), Wasm::WasmManifest::SupportedApi);
    ASSERT_EQ(manifest.permissions().size(), 1U);
    EXPECT_EQ(manifest.permissions().front(), "console.log");
    ASSERT_TRUE(manifest.resolveEntryPath());
    EXPECT_EQ(*manifest.resolveEntryPath(), std::filesystem::canonical(files.addonDirectory / "entry.wasm"));
}

TEST(WasmManifestTest, RejectsMalformedDuplicateAndWrongTypeFields)
{
    TemporaryAddon files;

    const auto malformed = Wasm::WasmManifest::loadFromFile(
        files.writeManifest(R"({"name":"Example","api":"org.freecad.wasm.api@0")"));
    EXPECT_FALSE(malformed.validate().empty());
    EXPECT_TRUE(containsError(malformed.validate(), "not valid JSON"));

    const auto duplicate = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","name":"Other","api":"org.freecad.wasm.api@0","entry":"entry.wasm"})"));
    EXPECT_TRUE(containsError(duplicate.validate(), "duplicate key 'name'"));

    const auto wrongType = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":42})"));
    EXPECT_TRUE(containsError(wrongType.validate(), "field 'entry' must be a string"));

    const auto unsupportedPermission = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":"entry.wasm","permissions":["filesystem.read"]})"));
    EXPECT_TRUE(containsError(unsupportedPermission.validate(), "unsupported permission"));
}

TEST(WasmManifestTest, RejectsOversizedManifest)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.wasm", "wasm");
    const auto oversized = std::string(Wasm::WasmManifest::MaxManifestBytes + 1U, ' ');
    const auto manifest = Wasm::WasmManifest::loadFromFile(files.writeManifest(oversized));

    EXPECT_TRUE(containsError(manifest.validate(), "maximum size"));
}

TEST(WasmManifestTest, RejectsUnsupportedApiAndEscapingEntries)
{
    TemporaryAddon files;
    files.writeFile(files.root / "outside.wasm", "wasm");

    const auto unsupported = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@99","entry":"../outside.wasm"})"));
    const auto unsupportedErrors = unsupported.validate();
    EXPECT_TRUE(containsError(unsupportedErrors, "unsupported API"));
    EXPECT_TRUE(containsError(unsupportedErrors, "outside the addon directory"));

    const auto absolute = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        std::string(R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":")")
        + std::filesystem::absolute(files.root / "outside.wasm").generic_string() + R"("})"));
    EXPECT_TRUE(containsError(absolute.validate(), "must be relative"));
}

TEST(WasmAddonTest, FailedReloadPreservesPreviousAddon)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.wasm", "wasm");
    const auto validPath = files.writeManifest(
        R"({"name":"First","api":"org.freecad.wasm.api@0","entry":"entry.wasm"})");
    const auto validManifest = Wasm::WasmManifest::loadFromFile(validPath);

    Wasm::WasmAddon addon;
    Wasm::WasmHostApi hostApi;
    FakeRuntime runtime;

    EXPECT_TRUE(addon.load(validManifest, runtime, hostApi).ok);
    EXPECT_TRUE(addon.isLoaded());
    EXPECT_EQ(addon.manifest().name(), "First");

    const auto invalidManifest = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Broken","api":"org.freecad.wasm.api@99","entry":"entry.wasm"})"));
    EXPECT_FALSE(addon.load(invalidManifest, runtime, hostApi).ok);
    EXPECT_TRUE(addon.isLoaded());
    EXPECT_EQ(addon.manifest().name(), "First");

    runtime.failInstantiation = true;
    EXPECT_FALSE(addon.load(validManifest, runtime, hostApi).ok);
    EXPECT_TRUE(addon.isLoaded());
    EXPECT_EQ(addon.manifest().name(), "First");
}

TEST(WasmAddonTest, InvokeRequiresLoadedAddon)
{
    Wasm::WasmAddon addon;

    const auto result = addon.invoke();
    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("not loaded"), std::string::npos);
}

TEST(WasmAddonManagerTest, LoadsInvokesListsAndUnloadsAddons)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.wasm", "wasm");
    const auto manifestPath = files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":"entry.wasm"})");

    Wasm::WasmAddonManager manager(std::make_unique<FakeRuntime>());
    const auto load = manager.load(manifestPath, {"console.log"});
    ASSERT_TRUE(load.ok) << load.error;
    EXPECT_EQ(manager.loadedAddons(), std::vector<std::string> {"Example"});

    const auto invocation = manager.invoke("Example");
    EXPECT_TRUE(invocation.ok) << invocation.error;
    EXPECT_FALSE(manager.invoke("Missing").ok);
    EXPECT_TRUE(manager.unload("Example"));
    EXPECT_TRUE(manager.loadedAddons().empty());
    EXPECT_FALSE(manager.unload("Example"));
}

TEST(WasmAddonTest, RequiresSandboxByDefault)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.wasm", "wasm");
    const auto manifest = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":"entry.wasm"})"));

    Wasm::WasmAddon addon;
    Wasm::WasmHostApi hostApi;
    FakeRuntime runtime;
    runtime.sandboxed = false;

    const auto result = addon.load(manifest, runtime, hostApi);
    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("required sandbox"), std::string::npos);
}

TEST(WasmAddonTest, TrustedPoliciesRequireTheirRuntimeCapability)
{
    TemporaryAddon files;
    files.writeFile(files.addonDirectory / "entry.aot", "aot");
    const auto manifest = Wasm::WasmManifest::loadFromFile(files.writeManifest(
        R"({"name":"Example","api":"org.freecad.wasm.api@0","entry":"entry.aot"})"));

    Wasm::WasmAddon addon;
    Wasm::WasmHostApi hostApi;
    FakeRuntime runtime;
    Wasm::RuntimeLimits limits;
    limits.executionPolicy = Wasm::ExecutionPolicy::TrustedAot;

    const auto result = addon.load(manifest, runtime, hostApi, limits);
    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("AOT execution"), std::string::npos);
}

TEST(WasmHostApiTest, DeniesCapabilitiesByDefault)
{
    Wasm::WasmHostApi hostApi;

    const auto denied = hostApi.dispatch("freecad.log:hello");
    EXPECT_FALSE(denied.ok);
    EXPECT_NE(denied.error.find("console.log"), std::string::npos);
    EXPECT_EQ(denied.errorCode, Wasm::Abi::ErrorCode::PermissionDenied);

    hostApi.setPermissions({"console.log"});
    EXPECT_TRUE(hostApi.dispatch("freecad.log:hello").ok);
}

TEST(WasmHostApiTest, ValidatesVersionedBinaryRequests)
{
    Wasm::WasmHostApi hostApi;
    Wasm::WasmHandleTable handles;

    const auto request = binaryRequest(Wasm::Abi::Operation::DocumentNew,
                                       stringPayload("BinaryRequest"));
    const auto bytes = asBytes(request);

    const auto denied = hostApi.dispatch(bytes, hostApi.permissions(), handles);
    EXPECT_FALSE(denied.ok);
    EXPECT_NE(denied.error.find("document.create"), std::string::npos);
    EXPECT_EQ(denied.errorCode, Wasm::Abi::ErrorCode::PermissionDenied);

    auto unsupportedVersion = request;
    unsupportedVersion[4] = static_cast<char>(Wasm::Abi::RequestVersion + 1U);
    const auto malformed = hostApi.dispatch(
        asBytes(unsupportedVersion), hostApi.permissions(), handles);
    EXPECT_FALSE(malformed.ok);
    EXPECT_NE(malformed.error.find("version"), std::string::npos);
    EXPECT_EQ(malformed.errorCode, Wasm::Abi::ErrorCode::InvalidRequest);
}

TEST(WasmHostApiTest, UsesGeneratedOperationMetadataForDispatch)
{
    ASSERT_FALSE(Wasm::Generated::OperationMetadataTable.empty());
    for (const auto& metadata : Wasm::Generated::OperationMetadataTable) {
        EXPECT_EQ(metadata.operation,
                  static_cast<Wasm::Abi::Operation>(metadata.id));
        EXPECT_FALSE(metadata.name.empty());
        EXPECT_FALSE(metadata.wireName.empty());
        EXPECT_FALSE(metadata.origin.empty());
        EXPECT_FALSE(metadata.parametersJson.empty());
        EXPECT_FALSE(metadata.returnsJson.empty());
        EXPECT_EQ(Wasm::Generated::findOperationMetadata(metadata.id), &metadata);
    }
    EXPECT_EQ(Wasm::Generated::findOperationMetadata(0xffU), nullptr);
}

TEST(WasmHostApiTest, RejectsOperationsMissingFromGeneratedMetadata)
{
    Wasm::WasmHostApi hostApi;
    Wasm::WasmHandleTable handles;

    const auto result = hostApi.dispatch(
        asBytes(binaryRequest(static_cast<Wasm::Abi::Operation>(0xffU))),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("unsupported WASM host operation"), std::string::npos);
    EXPECT_EQ(result.errorCode, Wasm::Abi::ErrorCode::Unsupported);
}

TEST(WasmHostApiTest, RejectsCallsFromNonOwnerThreads)
{
    Wasm::WasmHostApi hostApi;
    hostApi.setPermissions({"console.log"});

    Wasm::HostCallResult result;
    std::thread worker([&hostApi, &result] {
        result = hostApi.dispatch("freecad.log:cross-thread");
    });
    worker.join();

    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("owner thread"), std::string::npos);
}

TEST(WasmGuestTest, EncodesThePublishedHostProtocol)
{
    Wasm::Guest::Client guest(
        &GuestCapture::dispatch, &GuestCapture::release, &GuestCapture::allocate);

    const auto document = guest.documentNew("GuestDocument");
    EXPECT_FALSE(document.ok);
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentNew,
                            stringPayload("GuestDocument")));

    bool saved = false;
    EXPECT_FALSE(guest.documentIsSaved(11U, &saved));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentIsSaved,
                            handlePayload(11U)));

    Wasm::Guest::Handle queriedObject = 0U;
    EXPECT_FALSE(guest.documentGetObject(11U, "Box", &queriedObject));
    std::string getObjectPayload = handlePayload(11U);
    getObjectPayload += stringPayload("Box");
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentGetObject, getObjectPayload));

    bool transaction = false;
    EXPECT_FALSE(guest.documentOpenTransaction(11U, "Edit", &transaction));
    std::string transactionPayload = handlePayload(11U);
    transactionPayload += stringPayload("Edit");
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction, transactionPayload));

    EXPECT_FALSE(guest.documentCommitTransaction(11U, &transaction));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentCommitTransaction,
                            handlePayload(11U)));

    EXPECT_FALSE(guest.documentAbortTransaction(11U, &transaction));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentAbortTransaction,
                            handlePayload(11U)));

    char label[32] = {};
    std::uint32_t labelLength = 0U;
    EXPECT_FALSE(guest.documentObjectGetLabel(22U, label, sizeof(label), &labelLength));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentObjectGetLabel,
                            handlePayload(22U)));

    EXPECT_FALSE(guest.documentObjectSetLabel(22U, "Edited", &transaction));
    std::string setLabelPayload = handlePayload(22U);
    setLabelPayload += stringPayload("Edited");
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel, setLabelPayload));

    const auto box = guest.partMakeBox(1.0, 2.0, 3.0);
    EXPECT_FALSE(box.ok);
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::PartMakeBox,
                            doublePayload(1.0, 2.0, 3.0)));

    const auto object = guest.documentAddObject(11U, 22U, "Box");
    EXPECT_FALSE(object.ok);
    std::string objectPayload;
    Wasm::Abi::appendU64(objectPayload, 11U);
    Wasm::Abi::appendU64(objectPayload, 22U);
    objectPayload += stringPayload("Box");
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::DocumentAddObject, objectPayload));

    const auto released = guest.release(22U);
    EXPECT_FALSE(released.ok);
    EXPECT_EQ(released.errorCode, Wasm::Abi::ErrorCode::Protocol);
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::HandleRelease, handlePayload(22U)));

    Wasm::Guest::Vector3 vector;
    EXPECT_FALSE(guest.vectorNew(1.0, 2.0, 3.0, &vector));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::VectorNew,
                            doublePayload(1.0, 2.0, 3.0)));

    const Wasm::Guest::Vector3 left {1.0, 2.0, 3.0};
    const Wasm::Guest::Vector3 right {4.0, 5.0, 6.0};
    EXPECT_FALSE(guest.vectorAdd(left, right, &vector));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::VectorAdd,
                            vectorPairPayload(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)));

    double dot = 0.0;
    EXPECT_FALSE(guest.vectorDot(left, right, &dot));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::VectorDot,
                            vectorPairPayload(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)));

    double length = 0.0;
    EXPECT_FALSE(guest.topoShapeLength(22U, &length));
    EXPECT_EQ(GuestCapture::lastRequest,
              binaryRequest(Wasm::Abi::Operation::TopoShapeLength,
                            handlePayload(22U)));
}

TEST(WasmHostApiTest, ExecutesVectorOperationsFromPyiSurface)
{
    Wasm::WasmHostApi hostApi;
    hostApi.setPermissions({"geometry.compute"});
    Wasm::WasmHandleTable handles;

    const auto left = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::VectorNew,
                              doublePayload(1.0, 2.0, 3.0))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(left.ok) << left.error;
    EXPECT_EQ(left.payload.size(), sizeof(double) * 3U);
    EXPECT_DOUBLE_EQ(doubleFromPayload(left.payload, 0U), 1.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(left.payload, sizeof(double)), 2.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(left.payload, sizeof(double) * 2U), 3.0);

    const auto sum = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::VectorAdd,
                              vectorPairPayload(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(sum.ok) << sum.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(sum.payload, 0U), 5.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(sum.payload, sizeof(double)), 7.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(sum.payload, sizeof(double) * 2U), 9.0);

    const auto dot = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::VectorDot,
                              vectorPairPayload(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(dot.ok) << dot.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(dot.payload), 32.0);

    const auto cross = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::VectorCross,
                              vectorPairPayload(1.0, 2.0, 3.0, 4.0, 5.0, 6.0))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(cross.ok) << cross.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(cross.payload, 0U), -3.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(cross.payload, sizeof(double)), 6.0);
    EXPECT_DOUBLE_EQ(doubleFromPayload(cross.payload, sizeof(double) * 2U), -3.0);
}

#if defined(FREECAD_WASM_HAS_PART)

#if defined(FREECAD_WASM_CAPABILITY_FIXTURE)

TEST(WamrRuntimeTest, ExecutesCompiledCapabilityGuest)
{
    tests::initApplication();

    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "freecad-capability-addon.wasm";
    std::error_code copyError;
    std::filesystem::copy_file(FREECAD_WASM_CAPABILITY_FIXTURE,
                                wasmPath,
                                std::filesystem::copy_options::overwrite_existing,
                                copyError);
    ASSERT_FALSE(copyError) << copyError.message();
    const auto manifestPath = files.addonDirectory / "manifest.json";
    copyError.clear();
    std::filesystem::copy_file(FREECAD_WASM_CAPABILITY_MANIFEST,
                                manifestPath,
                                std::filesystem::copy_options::overwrite_existing,
                                copyError);
    ASSERT_FALSE(copyError) << copyError.message();

    constexpr const char* documentName = "GuestCapabilityExample";
    if (App::GetApplication().getDocument(documentName) != nullptr) {
        ASSERT_TRUE(App::GetApplication().closeDocument(documentName));
    }

    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 64U * 1024U;
    limits.maxInstructions = 100'000;
    limits.timeoutMs = 100U;

    Wasm::WasmAddonManager deniedManager;
    const auto deniedLoad = deniedManager.load(manifestPath, {"geometry.compute"}, limits);
    ASSERT_TRUE(deniedLoad.ok) << deniedLoad.error;
    const auto denied = deniedManager.invoke("CapabilityExample");
    EXPECT_FALSE(denied.ok);
    EXPECT_NE(denied.error.find("failed host operation"), std::string::npos);
    EXPECT_EQ(App::GetApplication().getDocument(documentName), nullptr);

    Wasm::WasmAddonManager manager;
    const auto load = manager.load(
        manifestPath,
        {"document.create",
         "document.read",
         "document.modify",
         "geometry.create",
         "geometry.compute",
         "geometry.read"},
        limits);
    ASSERT_TRUE(load.ok) << load.error;
    EXPECT_EQ(manager.loadedAddons(), std::vector<std::string> {"CapabilityExample"});

    const auto result = manager.invoke("CapabilityExample");
    ASSERT_TRUE(result.ok) << result.error;
    const std::vector<std::byte> expectedResponse {std::byte {'O'}, std::byte {'K'}};
    EXPECT_EQ(result.payload, expectedResponse);

    auto* document = App::GetApplication().getDocument(documentName);
    ASSERT_NE(document, nullptr);
    auto* object = document->getObject("Box");
    ASSERT_NE(object, nullptr);
    auto* feature = dynamic_cast<Part::Feature*>(object);
    ASSERT_NE(feature, nullptr);
    EXPECT_FALSE(feature->Shape.getValue().IsNull());

    EXPECT_TRUE(manager.unload("CapabilityExample"));
    EXPECT_TRUE(App::GetApplication().closeDocument(documentName));
}

#if defined(FREECAD_WASM_AOT_FIXTURE)

TEST(WamrRuntimeTest, ExecutesMatchingAotCapabilityGuest)
{
    tests::initApplication();

    TemporaryAddon files;
    const auto aotPath = files.addonDirectory / "capability.aot";
    std::error_code copyError;
    std::filesystem::copy_file(FREECAD_WASM_AOT_FIXTURE,
                                aotPath,
                                std::filesystem::copy_options::overwrite_existing,
                                copyError);
    ASSERT_FALSE(copyError) << copyError.message();
    const auto manifestPath = files.writeManifest(
        R"({"name":"AotCapabilityExample","api":"org.freecad.wasm.api@0","entry":"capability.aot","permissions":["document.create","document.read","document.modify","geometry.create","geometry.compute","geometry.read"]})");

    constexpr const char* documentName = "GuestCapabilityExample";
    if (App::GetApplication().getDocument(documentName) != nullptr) {
        ASSERT_TRUE(App::GetApplication().closeDocument(documentName));
    }

    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 64U * 1024U;
    limits.executionPolicy = Wasm::ExecutionPolicy::TrustedAot;
    limits.timeoutMs = 0U;

    Wasm::WasmAddonManager manager;
    const auto load = manager.load(
        manifestPath,
        {"document.create",
         "document.read",
         "document.modify",
         "geometry.create",
         "geometry.compute",
         "geometry.read"},
        limits);
    ASSERT_TRUE(load.ok) << load.error;

    const auto result = manager.invoke("AotCapabilityExample");
    ASSERT_TRUE(result.ok) << result.error;
    const std::vector<std::byte> expectedResponse {std::byte {'O'}, std::byte {'K'}};
    EXPECT_EQ(result.payload, expectedResponse);

    EXPECT_TRUE(manager.unload("AotCapabilityExample"));
    EXPECT_TRUE(App::GetApplication().closeDocument(documentName));
}

#endif

#endif

#if defined(FREECAD_WASM_RUST_CAPABILITY_FIXTURE)

TEST(WamrRuntimeTest, ExecutesRustCapabilityGuest)
{
    tests::initApplication();

    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "rust-capability.wasm";
    std::error_code copyError;
    std::filesystem::copy_file(FREECAD_WASM_RUST_CAPABILITY_FIXTURE,
                                wasmPath,
                                std::filesystem::copy_options::overwrite_existing,
                                copyError);
    ASSERT_FALSE(copyError) << copyError.message();
    const auto manifestPath = files.writeManifest(
        R"({"name":"RustCapabilityExample","api":"org.freecad.wasm.api@0","entry":"rust-capability.wasm","permissions":["document.create","document.read","document.modify","geometry.create","geometry.compute","geometry.read"]})");

    constexpr const char* documentName = "RustCapabilityExample";
    if (App::GetApplication().getDocument(documentName) != nullptr) {
        ASSERT_TRUE(App::GetApplication().closeDocument(documentName));
    }

    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 256U * 1024U;
    limits.maxInstructions = 100'000;
    limits.timeoutMs = 100U;

    Wasm::WasmAddonManager deniedManager;
    const auto deniedLoad = deniedManager.load(manifestPath, {}, limits);
    ASSERT_TRUE(deniedLoad.ok) << deniedLoad.error;
    const auto denied = deniedManager.invoke("RustCapabilityExample");
    EXPECT_FALSE(denied.ok);
    EXPECT_NE(denied.error.find("failed host operation"), std::string::npos);
    EXPECT_EQ(App::GetApplication().getDocument(documentName), nullptr);

    Wasm::WasmAddonManager manager;
    const auto load = manager.load(
        manifestPath,
        {"document.create",
         "document.read",
         "document.modify",
         "geometry.create",
         "geometry.compute",
         "geometry.read"},
        limits);
    ASSERT_TRUE(load.ok) << load.error;

    const auto result = manager.invoke("RustCapabilityExample");
    ASSERT_TRUE(result.ok) << result.error;
    const std::vector<std::byte> expectedResponse {std::byte {'O'}, std::byte {'K'}};
    EXPECT_EQ(result.payload, expectedResponse);

    auto* document = App::GetApplication().getDocument(documentName);
    ASSERT_NE(document, nullptr);
    auto* object = document->getObject("RustBox");
    ASSERT_NE(object, nullptr);
    auto* feature = dynamic_cast<Part::Feature*>(object);
    ASSERT_NE(feature, nullptr);
    EXPECT_FALSE(feature->Shape.getValue().IsNull());

    EXPECT_TRUE(manager.unload("RustCapabilityExample"));
    EXPECT_TRUE(App::GetApplication().closeDocument(documentName));
}

#endif

TEST(WasmHostApiTest, CreatesDocumentsShapesAndFeaturesWithInstanceHandles)
{
    tests::initApplication();

    Wasm::WasmHostApi hostApi;
    hostApi.setPermissions({"document.create",
                            "document.read",
                            "document.modify",
                            "geometry.create",
                            "geometry.compute",
                            "geometry.read"});
    Wasm::WasmHandleTable handles;

    const auto proposedName = App::GetApplication().getUniqueDocumentName("WasmCapability");
    const auto documentResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentNew,
                              stringPayload(proposedName))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(documentResult.ok) << documentResult.error;
    const auto documentHandle = handleFromPayload(documentResult.payload);
    ASSERT_NE(documentHandle, Wasm::InvalidHandle);

    const auto savedResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentIsSaved,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(savedResult.ok) << savedResult.error;
    ASSERT_EQ(savedResult.payload.size(), 1U);
    EXPECT_EQ(static_cast<unsigned char>(savedResult.payload.front()), 0U);

    const auto boxResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::PartMakeBox,
                              doublePayload(2.0, 3.0, 4.0))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(boxResult.ok) << boxResult.error;
    const auto shapeHandle = handleFromPayload(boxResult.payload);
    ASSERT_NE(shapeHandle, Wasm::InvalidHandle);

    std::string addObjectPayload;
    Wasm::Abi::appendU64(addObjectPayload, documentHandle);
    Wasm::Abi::appendU64(addObjectPayload, shapeHandle);
    addObjectPayload += stringPayload("Box");

    const auto addOutsideTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentAddObject, addObjectPayload)),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(addOutsideTransactionResult.ok);
    EXPECT_NE(addOutsideTransactionResult.error.find("active transaction"), std::string::npos);

    std::string addTransactionPayload = handlePayload(documentHandle);
    addTransactionPayload += stringPayload("Add object");
    const auto addTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction,
                              addTransactionPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(addTransactionResult.ok) << addTransactionResult.error;

    const auto objectResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentAddObject, addObjectPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(objectResult.ok) << objectResult.error;
    const auto objectHandle = handleFromPayload(objectResult.payload);
    ASSERT_NE(objectHandle, Wasm::InvalidHandle);

    const auto addCommitResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentCommitTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(addCommitResult.ok) << addCommitResult.error;

    const auto duplicateCommitResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentCommitTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(duplicateCommitResult.ok);
    EXPECT_NE(duplicateCommitResult.error.find("active transaction"), std::string::npos);

    std::string getObjectPayload = handlePayload(documentHandle);
    getObjectPayload += stringPayload("Box");
    const auto queriedObjectResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentGetObject, getObjectPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(queriedObjectResult.ok) << queriedObjectResult.error;
    const auto queriedObjectHandle = handleFromPayload(queriedObjectResult.payload);
    ASSERT_NE(queriedObjectHandle, Wasm::InvalidHandle);

    const auto labelResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectGetLabel,
                              handlePayload(objectHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(labelResult.ok) << labelResult.error;
    EXPECT_EQ(stringFromPayload(labelResult.payload), "Box");

    std::string setLabelPayload = handlePayload(objectHandle);
    setLabelPayload += stringPayload("ConfiguredBox");
    const auto setLabelOutsideTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel,
                              setLabelPayload)),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(setLabelOutsideTransactionResult.ok);
    EXPECT_NE(setLabelOutsideTransactionResult.error.find("active transaction"), std::string::npos);

    std::string openTransactionPayload = handlePayload(documentHandle);
    openTransactionPayload += stringPayload("Set label");
    const auto openTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction,
                              openTransactionPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(openTransactionResult.ok) << openTransactionResult.error;
    ASSERT_EQ(static_cast<unsigned char>(openTransactionResult.payload.front()), 1U);

    std::string nestedTransactionPayload = handlePayload(documentHandle);
    nestedTransactionPayload += stringPayload("Nested label");
    const auto nestedOpenResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction,
                              nestedTransactionPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(nestedOpenResult.ok) << nestedOpenResult.error;

    const auto setLabelResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel,
                              setLabelPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(setLabelResult.ok) << setLabelResult.error;
    ASSERT_EQ(static_cast<unsigned char>(setLabelResult.payload.front()), 1U);

    const auto commitTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentCommitTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(commitTransactionResult.ok) << commitTransactionResult.error;
    ASSERT_EQ(static_cast<unsigned char>(commitTransactionResult.payload.front()), 1U);

    const auto outerCommitTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentCommitTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(outerCommitTransactionResult.ok) << outerCommitTransactionResult.error;

    std::string rollbackPayload = handlePayload(documentHandle);
    rollbackPayload += stringPayload("Rollback label");
    const auto rollbackOpenResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction,
                              rollbackPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(rollbackOpenResult.ok) << rollbackOpenResult.error;

    std::string temporaryLabelPayload = handlePayload(objectHandle);
    temporaryLabelPayload += stringPayload("TemporaryBox");
    const auto temporaryLabelResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel,
                              temporaryLabelPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(temporaryLabelResult.ok) << temporaryLabelResult.error;

    const auto abortTransactionResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentAbortTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(abortTransactionResult.ok) << abortTransactionResult.error;

    const auto duplicateAbortResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentAbortTransaction,
                              handlePayload(documentHandle))),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(duplicateAbortResult.ok);
    EXPECT_NE(duplicateAbortResult.error.find("active transaction"), std::string::npos);

    const auto rolledBackLabelResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectGetLabel,
                              handlePayload(objectHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(rolledBackLabelResult.ok) << rolledBackLabelResult.error;
    EXPECT_EQ(stringFromPayload(rolledBackLabelResult.payload), "ConfiguredBox");

    const auto shapeNullResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeIsNull,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(shapeNullResult.ok) << shapeNullResult.error;
    ASSERT_EQ(shapeNullResult.payload.size(), 1U);
    EXPECT_EQ(static_cast<unsigned char>(shapeNullResult.payload.front()), 0U);

    const auto shapeValidResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeIsValid,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(shapeValidResult.ok) << shapeValidResult.error;
    ASSERT_EQ(shapeValidResult.payload.size(), 1U);
    EXPECT_EQ(static_cast<unsigned char>(shapeValidResult.payload.front()), 1U);

    const auto shapeLengthResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeLength,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(shapeLengthResult.ok) << shapeLengthResult.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(shapeLengthResult.payload), 72.0);

    const auto shapeAreaResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeArea,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(shapeAreaResult.ok) << shapeAreaResult.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(shapeAreaResult.payload), 52.0);

    const auto shapeVolumeResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeVolume,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(shapeVolumeResult.ok) << shapeVolumeResult.error;
    EXPECT_DOUBLE_EQ(doubleFromPayload(shapeVolumeResult.payload), 24.0);

    Wasm::WasmHostApi deniedHost;
    deniedHost.setPermissions({"document.create", "geometry.create"});
    const auto deniedDocumentRead = deniedHost.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentIsSaved,
                              handlePayload(documentHandle))),
        deniedHost.permissions(),
        handles);
    EXPECT_FALSE(deniedDocumentRead.ok);
    EXPECT_NE(deniedDocumentRead.error.find("document.read"), std::string::npos);

    const auto deniedGeometryRead = deniedHost.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::TopoShapeIsValid,
                              handlePayload(shapeHandle))),
        deniedHost.permissions(),
        handles);
    EXPECT_FALSE(deniedGeometryRead.ok);
    EXPECT_NE(deniedGeometryRead.error.find("geometry.read"), std::string::npos);

    const auto deniedDocumentModify = deniedHost.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel,
                              setLabelPayload)),
        deniedHost.permissions(),
        handles);
    EXPECT_FALSE(deniedDocumentModify.ok);
    EXPECT_NE(deniedDocumentModify.error.find("document.modify"), std::string::npos);

    std::string cleanupTransactionPayload = handlePayload(documentHandle);
    cleanupTransactionPayload += stringPayload("Cleanup");
    const auto cleanupOpenResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentOpenTransaction,
                              cleanupTransactionPayload)),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(cleanupOpenResult.ok) << cleanupOpenResult.error;
    hostApi.clearTransactions();
    const auto cleanupLabelResult = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentObjectSetLabel,
                              setLabelPayload)),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(cleanupLabelResult.ok);
    EXPECT_NE(cleanupLabelResult.error.find("active transaction"), std::string::npos);

    const auto objectEntry = handles.get(objectHandle);
    ASSERT_TRUE(objectEntry.has_value());
    const auto* object = static_cast<const Part::Feature*>(objectEntry->pointer);
    ASSERT_NE(object, nullptr);
    EXPECT_FALSE(object->Shape.getShape().getShape().IsNull());

    const auto releaseShape = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::HandleRelease,
                              handlePayload(shapeHandle))),
        hostApi.permissions(),
        handles);
    ASSERT_TRUE(releaseShape.ok) << releaseShape.error;

    const auto expiredShape = hostApi.dispatch(
        asBytes(binaryRequest(Wasm::Abi::Operation::DocumentAddObject, addObjectPayload)),
        hostApi.permissions(),
        handles);
    EXPECT_FALSE(expiredShape.ok);
    EXPECT_NE(expiredShape.error.find("expired handle"), std::string::npos);

    const auto documentEntry = handles.get(documentHandle);
    ASSERT_TRUE(documentEntry.has_value());
    const auto* document = static_cast<const App::Document*>(documentEntry->pointer);
    ASSERT_NE(document, nullptr);
    const std::string documentName = document->getName();

    ASSERT_TRUE(App::GetApplication().closeDocument(documentName.c_str()));
    EXPECT_FALSE(handles.get(documentHandle).has_value());
    EXPECT_FALSE(handles.get(objectHandle).has_value());
    EXPECT_TRUE(handles.erase(objectHandle));
    EXPECT_TRUE(handles.erase(queriedObjectHandle));
    EXPECT_TRUE(handles.erase(documentHandle));
}

#endif

TEST(WasmHandleTableTest, ReleasesOwnedEntriesExactlyOnce)
{
    int releases = 0;
    Wasm::WasmHandleTable table;
    const auto handle = table.insert("OwnedValue", new OwnedValue {&releases}, false, releaseOwnedValue);

    ASSERT_NE(handle, Wasm::InvalidHandle);
    EXPECT_TRUE(table.erase(handle));
    EXPECT_EQ(releases, 1);
    EXPECT_FALSE(table.erase(handle));

    const auto second = table.insert("OwnedValue", new OwnedValue {&releases}, false, releaseOwnedValue);
    ASSERT_NE(second, Wasm::InvalidHandle);
    table.clear();
    EXPECT_EQ(releases, 2);
}

TEST(WasmHandleTableTest, RejectsOwnedEntriesWithoutReleaseCallback)
{
    Wasm::WasmHandleTable table;
    int value = 0;

    EXPECT_EQ(table.insert("Value", &value, false), Wasm::InvalidHandle);
}

#if defined(FREECAD_HAS_WAMR)

TEST(WamrRuntimeTest, RejectsInstantiationFromNonOwnerThread)
{
    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::WasmHostApi hostApi;
    bool instantiateRejected = false;
    std::thread worker([&runtime, &hostApi, &instantiateRejected] {
        instantiateRejected = !runtime->instantiate("missing.wasm", {}, hostApi);
    });
    worker.join();

    EXPECT_TRUE(instantiateRejected);
}

TEST(WamrRuntimeTest, RejectsImportsOutsideTheFreeCadHostAbi)
{
    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "unknown-import.wasm";
    files.writeBinary(wasmPath, unknownImportFixture());

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::WasmHostApi hostApi;
    EXPECT_FALSE(runtime->instantiate(wasmPath, {}, hostApi));
}

TEST(WamrRuntimeTest, RejectsNativeArtifactsAcrossTheSandboxBoundary)
{
    TemporaryAddon files;
    const auto aotPath = files.addonDirectory / "native.aot";
    files.writeFile(aotPath, "not-an-aot-module");

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::WasmHostApi hostApi;
    Wasm::RuntimeLimits limits;
    EXPECT_FALSE(runtime->instantiate(aotPath, limits, hostApi));
}

TEST(WamrRuntimeTest, RejectsHostImportsWithWrongSignatures)
{
    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "wrong-import-signature.wasm";
    files.writeBinary(wasmPath, wrongImportSignatureFixture());

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::WasmHostApi hostApi;
    EXPECT_FALSE(runtime->instantiate(wasmPath, {}, hostApi));
}

TEST(WamrRuntimeTest, ExecutesByteBufferExportsAndPoisonsTimedOutInstances)
{
    TemporaryAddon files;
    // The fixture exports echo and spin with the FreeCAD byte-buffer ABI and
    // contains one page of linear memory for WAMR's address validation.
    const std::vector<unsigned char> fixture {
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
        0x01, 0x0c, 0x02,
        0x60, 0x02, 0x7f, 0x7f, 0x01, 0x7e,
        0x60, 0x02, 0x7f, 0x7f, 0x00,
        0x02, 0x17, 0x01,
        0x07, 0x66, 0x72, 0x65, 0x65, 0x63, 0x61, 0x64,
        0x0b, 0x66, 0x72, 0x65, 0x65, 0x63, 0x61, 0x64, 0x5f, 0x6c, 0x6f, 0x67,
        0x00, 0x01,
        0x03, 0x04, 0x03, 0x00, 0x00, 0x00,
        0x05, 0x05, 0x01, 0x01, 0x01, 0x80, 0x08,
        0x07, 0x1e, 0x04,
        0x04, 0x65, 0x63, 0x68, 0x6f, 0x00, 0x01,
        0x04, 0x73, 0x70, 0x69, 0x6e, 0x00, 0x02,
        0x03, 0x6c, 0x6f, 0x67, 0x00, 0x03,
        0x06, 0x6d, 0x65, 0x6d, 0x6f, 0x72, 0x79, 0x02, 0x00,
        0x0a, 0x2a, 0x03,
        0x0c, 0x00, 0x20, 0x01, 0xad, 0x42, 0x20, 0x86, 0x20, 0x00, 0xad, 0x84, 0x0b,
        0x08, 0x00, 0x03, 0x40, 0x0c, 0x00, 0x0b, 0x00, 0x0b,
        0x12, 0x00, 0x20, 0x00, 0x20, 0x01, 0x10, 0x00, 0x20, 0x01, 0xad, 0x42, 0x20,
        0x86, 0x20, 0x00, 0xad, 0x84, 0x0b,
    };
    const auto wasmPath = files.addonDirectory / "fixture.wasm";
    files.writeBinary(wasmPath, fixture);

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);
    EXPECT_TRUE(runtime->info().supportsSandbox);

    Wasm::WasmHostApi hostApi;
    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 64U * 1024U;
    limits.maxRequestBytes = 2U;
    limits.maxResponseBytes = 2U;
    limits.maxInstructions = 1000;
    limits.timeoutMs = 100U;
    auto instance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(instance);

    const std::vector<std::byte> input {
        std::byte {'o'}, std::byte {'k'}, std::byte {'!'}
    };
    const auto oversizedRequest = instance->call("echo", input);
    EXPECT_FALSE(oversizedRequest.ok);
    EXPECT_NE(oversizedRequest.error.find("request limit"), std::string::npos);

    limits.maxRequestBytes = 64U * 1024U;
    instance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(instance);
    const auto echoed = instance->call("echo", input);
    EXPECT_FALSE(echoed.ok);
    EXPECT_NE(echoed.error.find("response exceeds"), std::string::npos);

    limits.maxResponseBytes = 64U * 1024U;
    instance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(instance);
    const auto allowedEcho = instance->call("echo", input);
    ASSERT_TRUE(allowedEcho.ok) << allowedEcho.error;
    EXPECT_EQ(allowedEcho.payload, input);

    const auto deniedLog = instance->call("log", input);
    EXPECT_FALSE(deniedLog.ok);
    EXPECT_NE(deniedLog.error.find("console.log"), std::string::npos);

    hostApi.setPermissions({"console.log"});
    const auto unchangedPermissions = instance->call("log", input);
    EXPECT_FALSE(unchangedPermissions.ok);

    auto allowedInstance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(allowedInstance);
    const auto logged = allowedInstance->call("log", input);
    ASSERT_TRUE(logged.ok) << logged.error;
    EXPECT_EQ(logged.payload, input);

    const auto timedOut = allowedInstance->call("spin", {});
    EXPECT_FALSE(timedOut.ok);
#if defined(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING)
    EXPECT_NE(timedOut.error.find("instruction limit"), std::string::npos);
#else
    EXPECT_NE(timedOut.error.find("timed out"), std::string::npos);
#endif

    const auto poisoned = allowedInstance->call("echo", input);
    EXPECT_FALSE(poisoned.ok);
    EXPECT_NE(poisoned.error.find("cannot be reused"), std::string::npos);

#if defined(FREECAD_WAMR_SUPPORTS_JIT)
    Wasm::RuntimeLimits jitLimits = limits;
    jitLimits.maxInstructions = 1000;
    jitLimits.timeoutMs = 0U;
    jitLimits.executionPolicy = Wasm::ExecutionPolicy::TrustedJit;
    auto jitInstance = runtime->instantiate(wasmPath, jitLimits, hostApi);
    ASSERT_TRUE(jitInstance);
    const auto jitEcho = jitInstance->call("echo", input);
    ASSERT_TRUE(jitEcho.ok) << jitEcho.error;
    EXPECT_EQ(jitEcho.payload, input);
#else
    Wasm::RuntimeLimits unboundedLimits = limits;
    unboundedLimits.timeoutMs = 0U;
    EXPECT_FALSE(runtime->instantiate(wasmPath, unboundedLimits, hostApi));
#endif

    auto noTimeoutLimits = limits;
    noTimeoutLimits.timeoutMs = 0U;
    EXPECT_FALSE(runtime->instantiate(wasmPath, noTimeoutLimits, hostApi));
}

TEST(WamrRuntimeTest, RejectsUnownedExportResponses)
{
    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "unowned-response.wasm";
    files.writeBinary(wasmPath, unownedResponseFixture());

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::WasmHostApi hostApi;
    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 64U * 1024U;
    limits.maxInstructions = 1000;
    limits.timeoutMs = 100U;
    auto instance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(instance);

    const auto result = instance->call("bad", {});
    EXPECT_FALSE(result.ok);
    EXPECT_NE(result.error.find("unowned response buffer"), std::string::npos);
}

#if defined(FREECAD_WASM_HAS_PART)

TEST(WamrRuntimeTest, DispatchesVersionedCapabilitiesWithInstanceLocalHandles)
{
    tests::initApplication();

    TemporaryAddon files;
    const auto wasmPath = files.addonDirectory / "dispatch.wasm";
    files.writeBinary(wasmPath, dispatchFixture());

    auto runtime = Wasm::createWasmRuntime();
    ASSERT_TRUE(runtime);
    ASSERT_TRUE(runtime->info().available);

    Wasm::RuntimeLimits limits;
    limits.maxMemoryBytes = 64U * 1024U;
    limits.maxInstructions = 1000;
    limits.timeoutMs = 100U;

    Wasm::WasmHostApi deniedHostApi;
    auto deniedInstance = runtime->instantiate(wasmPath, limits, deniedHostApi);
    ASSERT_TRUE(deniedInstance);
    const auto documentName = App::GetApplication().getUniqueDocumentName("WasmDispatch");
    const auto documentRequest = binaryRequest(
        Wasm::Abi::Operation::DocumentNew, stringPayload(documentName));
    const auto denied = deniedInstance->call("dispatch", asBytes(documentRequest));
    EXPECT_FALSE(denied.ok);
    EXPECT_NE(denied.error.find("document.create"), std::string::npos);
    EXPECT_EQ(denied.errorCode, Wasm::Abi::ErrorCode::PermissionDenied);

    Wasm::WasmHostApi hostApi;
    hostApi.setPermissions({"document.create", "document.modify", "geometry.create"});
    auto instance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(instance);

    const auto malformed = instance->call("dispatch", asBytes("not-a-wasm-request"));
    EXPECT_FALSE(malformed.ok);
    EXPECT_NE(malformed.error.find("magic"), std::string::npos);
    EXPECT_EQ(malformed.errorCode, Wasm::Abi::ErrorCode::InvalidRequest);

    const auto documentResult = instance->call("dispatch", asBytes(documentRequest));
    ASSERT_TRUE(documentResult.ok) << documentResult.error;
    const auto documentHandle = handleFromPayload(
        std::string_view(reinterpret_cast<const char*>(documentResult.payload.data()),
                         documentResult.payload.size()));
    ASSERT_NE(documentHandle, Wasm::InvalidHandle);

    const auto boxRequest = binaryRequest(
        Wasm::Abi::Operation::PartMakeBox, doublePayload(2.0, 3.0, 4.0));
    const auto boxResult = instance->call("dispatch", asBytes(boxRequest));
    ASSERT_TRUE(boxResult.ok) << boxResult.error;
    const auto shapeHandle = handleFromPayload(
        std::string_view(reinterpret_cast<const char*>(boxResult.payload.data()),
                         boxResult.payload.size()));
    ASSERT_NE(shapeHandle, Wasm::InvalidHandle);

    std::string transactionPayload = handlePayload(documentHandle);
    transactionPayload += stringPayload("Add object");
    const auto transactionRequest = binaryRequest(
        Wasm::Abi::Operation::DocumentOpenTransaction, transactionPayload);
    const auto transactionResult = instance->call(
        "dispatch", asBytes(transactionRequest));
    ASSERT_TRUE(transactionResult.ok) << transactionResult.error;

    std::string addObjectPayload;
    Wasm::Abi::appendU64(addObjectPayload, documentHandle);
    Wasm::Abi::appendU64(addObjectPayload, shapeHandle);
    addObjectPayload += stringPayload("Box");
    const auto objectRequest = binaryRequest(
        Wasm::Abi::Operation::DocumentAddObject, addObjectPayload);
    const auto objectResult = instance->call("dispatch", asBytes(objectRequest));
    ASSERT_TRUE(objectResult.ok) << objectResult.error;

    const auto commitRequest = binaryRequest(
        Wasm::Abi::Operation::DocumentCommitTransaction, handlePayload(documentHandle));
    const auto commitResult = instance->call("dispatch", asBytes(commitRequest));
    ASSERT_TRUE(commitResult.ok) << commitResult.error;

    auto isolatedInstance = runtime->instantiate(wasmPath, limits, hostApi);
    ASSERT_TRUE(isolatedInstance);
    const auto crossInstance = isolatedInstance->call("dispatch", asBytes(objectRequest));
    EXPECT_FALSE(crossInstance.ok);
    EXPECT_NE(crossInstance.error.find("expired handle"), std::string::npos);

    const auto releaseShapeRequest = binaryRequest(
        Wasm::Abi::Operation::HandleRelease, handlePayload(shapeHandle));
    const auto releaseShape = instance->call("dispatch", asBytes(releaseShapeRequest));
    ASSERT_TRUE(releaseShape.ok) << releaseShape.error;

    const auto expiredShape = instance->call("dispatch", asBytes(objectRequest));
    EXPECT_FALSE(expiredShape.ok);
    EXPECT_NE(expiredShape.error.find("expired handle"), std::string::npos);

    const auto releaseObjectRequest = binaryRequest(
        Wasm::Abi::Operation::HandleRelease,
        std::string_view(reinterpret_cast<const char*>(objectResult.payload.data()),
                         objectResult.payload.size()));
    const auto releaseObject = instance->call("dispatch", asBytes(releaseObjectRequest));
    ASSERT_TRUE(releaseObject.ok) << releaseObject.error;

    const auto releaseDocumentRequest = binaryRequest(
        Wasm::Abi::Operation::HandleRelease,
        std::string_view(reinterpret_cast<const char*>(documentResult.payload.data()),
                         documentResult.payload.size()));
    const auto releaseDocument = instance->call("dispatch", asBytes(releaseDocumentRequest));
    ASSERT_TRUE(releaseDocument.ok) << releaseDocument.error;

    EXPECT_TRUE(App::GetApplication().closeDocument(documentName.c_str()));
}

#endif

#endif
