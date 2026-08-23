// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include <Base/Console.h>
#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>

#include "WasmManifest.h"
#include "WasmAddonManager.h"
#include "WasmRuntimeFactory.h"
#include "WasmRuntime.h"

#include <cstring>
#include <vector>

namespace Wasm
{

class Module: public Py::ExtensionModule<Module>
{
public:
    Module()
        : Py::ExtensionModule<Module>("Wasm")
    {
        add_varargs_method(
            "getRuntimeInfo",
            &Module::getRuntimeInfo,
            "getRuntimeInfo() -> dict\n\n"
            "Return information about the configured WebAssembly runtime."
        );
        add_varargs_method(
            "validateManifest",
            &Module::validateManifest,
            "validateManifest(path: str) -> dict\n\n"
            "Validate the minimal experimental Wasm addon manifest fields."
        );
        add_varargs_method(
            "loadAddon",
            &Module::loadAddon,
            "loadAddon(path: str, permissions: list[str] = []) -> dict\n\n"
            "Load a Wasm addon package under the supplied host permission policy."
        );
        add_varargs_method(
            "invokeAddon",
            &Module::invokeAddon,
            "invokeAddon(name: str, input: bytes = b\"\") -> bytes\n\n"
            "Invoke a loaded addon entrypoint."
        );
        add_varargs_method(
            "unloadAddon",
            &Module::unloadAddon,
            "unloadAddon(name: str) -> bool\n\n"
            "Unload a previously loaded Wasm addon."
        );
        add_varargs_method(
            "listAddons",
            &Module::listAddons,
            "listAddons() -> list[str]\n\n"
            "Return the names of loaded Wasm addons."
        );
        initialize("This module is the experimental WebAssembly addon runtime module.");
    }

private:
    Py::Object getRuntimeInfo(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }

        const auto runtime = createWasmRuntime();
        const auto info = runtime->info();

        Py::Dict dict;
        dict.setItem("name", Py::String(info.name));
        dict.setItem("available", Py::Boolean(info.available));
        dict.setItem("supports_sandbox", Py::Boolean(info.supportsSandbox));
        dict.setItem("supports_aot", Py::Boolean(info.supportsAot));
        dict.setItem("supports_jit", Py::Boolean(info.supportsJit));
        dict.setItem("supports_hard_timeout", Py::Boolean(info.supportsHardTimeout));
        dict.setItem("api_model", Py::String("freecad_wasm_api.json"));
        return dict;
    }

    Py::Object validateManifest(const Py::Tuple& args)
    {
        const char* path = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &path)) {
            throw Py::Exception();
        }

        const auto manifest = WasmManifest::loadFromFile(path);
        const auto errors = manifest.validate();

        Py::List pyErrors;
        for (const auto& error : errors) {
            pyErrors.append(Py::String(error));
        }

        Py::Dict dict;
        dict.setItem("valid", Py::Boolean(errors.empty()));
        dict.setItem("name", Py::String(manifest.name()));
        dict.setItem("api", Py::String(manifest.api()));
        dict.setItem("entry", Py::String(manifest.entry()));
        dict.setItem("errors", pyErrors);
        return dict;
    }

    Py::Object loadAddon(const Py::Tuple& args)
    {
        const char* path = nullptr;
        PyObject* permissionsObject = Py_None;
        if (!PyArg_ParseTuple(args.ptr(), "s|O", &path, &permissionsObject)) {
            throw Py::Exception();
        }

        const auto permissions = parsePermissions(permissionsObject);
        const auto result = addonManager.load(path, permissions);
        if (!result.ok) {
            throw Py::RuntimeError(result.error);
        }

        const auto manifest = WasmManifest::loadFromFile(path);
        Py::Dict dict;
        dict.setItem("name", Py::String(manifest.name()));
        dict.setItem("api", Py::String(manifest.api()));
        dict.setItem("entry", Py::String(manifest.entry()));
        return dict;
    }

    Py::Object invokeAddon(const Py::Tuple& args)
    {
        const char* name = nullptr;
        PyObject* inputObject = Py_None;
        if (!PyArg_ParseTuple(args.ptr(), "s|O", &name, &inputObject)) {
            throw Py::Exception();
        }
        if (inputObject != Py_None && !PyBytes_Check(inputObject)) {
            throw Py::TypeError("invokeAddon input must be bytes");
        }

        std::vector<std::byte> input;
        if (inputObject != Py_None) {
            char* data = nullptr;
            Py_ssize_t length = 0;
            if (PyBytes_AsStringAndSize(inputObject, &data, &length) < 0) {
                throw Py::Exception();
            }
            input.resize(static_cast<std::size_t>(length));
            if (length != 0) {
                std::memcpy(input.data(), data, static_cast<std::size_t>(length));
            }
        }

        const auto result = addonManager.invoke(name, input);
        if (!result.ok) {
            throw Py::RuntimeError(result.error);
        }
        return Py::Bytes(std::string(reinterpret_cast<const char*>(result.payload.data()),
                                     result.payload.size()));
    }

    Py::Object unloadAddon(const Py::Tuple& args)
    {
        const char* name = nullptr;
        if (!PyArg_ParseTuple(args.ptr(), "s", &name)) {
            throw Py::Exception();
        }
        return Py::Boolean(addonManager.unload(name));
    }

    Py::Object listAddons(const Py::Tuple& args)
    {
        if (!PyArg_ParseTuple(args.ptr(), "")) {
            throw Py::Exception();
        }

        Py::List names;
        for (const auto& name : addonManager.loadedAddons()) {
            names.append(Py::String(name));
        }
        return names;
    }

    static std::vector<std::string> parsePermissions(PyObject* object)
    {
        if (object == Py_None) {
            return {};
        }
        if (!PyList_Check(object) && !PyTuple_Check(object)) {
            throw Py::TypeError("permissions must be a list or tuple of strings");
        }

        std::vector<std::string> permissions;
        const auto size = PySequence_Size(object);
        if (size < 0) {
            throw Py::Exception();
        }
        permissions.reserve(static_cast<std::size_t>(size));
        for (Py_ssize_t index = 0; index < size; ++index) {
            PyObject* item = PySequence_GetItem(object, index);
            if (item == nullptr) {
                throw Py::Exception();
            }
            if (!PyUnicode_Check(item)) {
                Py_DECREF(item);
                throw Py::TypeError("permissions must contain only strings");
            }
            const char* value = PyUnicode_AsUTF8(item);
            if (value == nullptr) {
                Py_DECREF(item);
                throw Py::Exception();
            }
            permissions.emplace_back(value);
            Py_DECREF(item);
        }
        return permissions;
    }

    Wasm::WasmAddonManager addonManager;
};

PyObject* initModule()
{
    return Base::Interpreter().addModule(new Module);
}

}  // namespace Wasm

PyMOD_INIT_FUNC(Wasm)
{
    PyObject* module = Wasm::initModule();
    Base::Console().log("Loading Wasm module... done\n");
    PyMOD_Return(module);
}
