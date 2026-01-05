// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Python.h>

#include "Base/Translation.h"
#include "Base/Translate.h"

namespace
{

PyObject* getTranslateModule()
{
    PyObject* module = PyImport_ImportModule("__Translate__");
    if (module) {
        return module;
    }

    PyErr_Clear();
    static Base::Translate* translateModule = new Base::Translate();  // NOLINT
    (void)translateModule;

    module = PyImport_ImportModule("__Translate__");
    return module;
}

PyObject* callTranslate(PyObject* module, const char* context, const char* source)
{
    PyObject* func = PyObject_GetAttrString(module, "translate");
    if (!func) {
        return nullptr;
    }
    PyObject* args = Py_BuildValue("(ss)", context, source);
    PyObject* ret = PyObject_CallObject(func, args);
    Py_DECREF(args);
    Py_DECREF(func);
    return ret;
}

}  // namespace

TEST(TranslateModule, TranslateUsesHandlerOrFallback)
{
    Py_Initialize();

    Base::Translation::setTranslateHandler({});

    PyObject* module = getTranslateModule();
    ASSERT_NE(nullptr, module);

    PyObject* retA = callTranslate(module, "Ctx", "Hello");
    ASSERT_NE(nullptr, retA);
    ASSERT_TRUE(PyUnicode_Check(retA));
    EXPECT_STREQ("Hello", PyUnicode_AsUTF8(retA));
    Py_DECREF(retA);

    Base::Translation::setTranslateHandler(
        [](std::string_view, std::string_view, std::string_view, int) { return std::string("Bonjour"); }
    );

    PyObject* retB = callTranslate(module, "Ctx", "Hello");
    ASSERT_NE(nullptr, retB);
    ASSERT_TRUE(PyUnicode_Check(retB));
    EXPECT_STREQ("Bonjour", PyUnicode_AsUTF8(retB));
    Py_DECREF(retB);

    Py_DECREF(module);
    Base::Translation::setTranslateHandler({});
}

TEST(TranslateModule, InstallAndRemoveUseHandlers)
{
    Py_Initialize();

    std::vector<std::string> installed;
    std::vector<std::string> removed;

    Base::Translation::setInstallTranslatorHandler([&installed](std::string_view filename) {
        installed.push_back(std::string(filename));
        return true;
    });
    Base::Translation::setRemoveTranslatorsHandler([&removed](const std::vector<std::string>& filenames) {
        removed = filenames;
        return true;
    });

    PyObject* module = getTranslateModule();
    ASSERT_NE(nullptr, module);

    PyObject* funcInstall = PyObject_GetAttrString(module, "installTranslator");
    ASSERT_NE(nullptr, funcInstall);
    PyObject* argsInstall = Py_BuildValue("(s)", "a.qm");
    PyObject* retInstall = PyObject_CallObject(funcInstall, argsInstall);
    Py_DECREF(argsInstall);
    Py_DECREF(funcInstall);
    ASSERT_NE(nullptr, retInstall);
    EXPECT_TRUE(PyObject_IsTrue(retInstall));
    Py_DECREF(retInstall);

    PyObject* funcRemove = PyObject_GetAttrString(module, "removeTranslators");
    ASSERT_NE(nullptr, funcRemove);
    PyObject* argsRemove = PyTuple_New(0);
    PyObject* retRemove = PyObject_CallObject(funcRemove, argsRemove);
    Py_DECREF(argsRemove);
    Py_DECREF(funcRemove);
    ASSERT_NE(nullptr, retRemove);
    EXPECT_TRUE(PyObject_IsTrue(retRemove));
    Py_DECREF(retRemove);

    Py_DECREF(module);

    EXPECT_EQ(std::vector<std::string>({"a.qm"}), installed);
    EXPECT_EQ(std::vector<std::string>({"a.qm"}), removed);

    Base::Translation::setInstallTranslatorHandler({});
    Base::Translation::setRemoveTranslatorsHandler({});
}
