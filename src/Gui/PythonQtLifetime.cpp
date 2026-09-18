// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PythonQtLifetime.h"

#include <algorithm>
#include <memory>
#include <vector>

#include <QApplication>
#include <QPointer>
#include <QTimer>

#include <Base/Interpreter.h>
#include <Base/PyObjectBase.h>

#include "PythonWrapper.h"

namespace Gui
{
namespace
{

class PendingPythonCall final: public QObject
{
public:
    PendingPythonCall(PyObject* callback, int delay, QObject* context)
        : QObject(qApp)
        , callback(callback)
        , context(context)
        , hasContext(context != nullptr)
    {
        Py_INCREF(callback);
        timer.setSingleShot(true);
        timer.setParent(this);
        connect(&timer, &QTimer::timeout, this, [this] { invoke(); });
        if (context) {
            connect(context, &QObject::destroyed, this, [this] { deleteLater(); });
        }
        timer.start(std::max(0, delay));
    }

    ~PendingPythonCall() override
    {
        releaseCallback();
    }

    void cancel()
    {
        timer.stop();
        releaseCallback();
        deleteLater();
    }

private:
    void invoke()
    {
        if (hasContext && context.isNull()) {
            cancel();
            return;
        }

        PyObject* callable = callback;
        callback = nullptr;
        if (callable && Py_IsInitialized()) {
            Base::PyGILStateLocker lock;
            PyObject* result = PyObject_CallNoArgs(callable);
            if (!result) {
                PyErr_Print();
            }
            else {
                Py_DECREF(result);
            }
            Py_DECREF(callable);
        }
        deleteLater();
    }

    void releaseCallback()
    {
        if (!callback || !Py_IsInitialized()) {
            callback = nullptr;
            return;
        }
        Base::PyGILStateLocker lock;
        Py_CLEAR(callback);
    }

    PyObject* callback {nullptr};
    QPointer<QObject> context;
    bool hasContext {false};
    QTimer timer;
};

class RetainedPythonQObjectTree final: public QObject
{
public:
    explicit RetainedPythonQObjectTree(std::vector<Py::Object>&& wrappers)
        : QObject(qApp)
        , wrappers(std::make_unique<std::vector<Py::Object>>(std::move(wrappers)))
    {}

    ~RetainedPythonQObjectTree() override
    {
        if (wrappers && Py_IsInitialized()) {
            Base::PyGILStateLocker lock;
            wrappers.reset();
        }
        else {
            // During interpreter shutdown it is safer to leak references than
            // to enter an unavailable Python runtime.
            wrappers.release();
        }
    }

private:
    std::unique_ptr<std::vector<Py::Object>> wrappers;
};

void adoptPythonQObjectTree(QObject* root, PythonWrapper& pySide)
{
    if (root->property("_FreeCAD_PythonOwnershipAdopted").toBool()) {
        return;
    }

    root->setProperty("_FreeCAD_PythonOwnershipAdopted", true);
    std::vector<Py::Object> retained;
    pySide.adoptQObjectTree(root, retained);
    auto* holder = new RetainedPythonQObjectTree(std::move(retained));
    QObject::connect(root, &QObject::destroyed, holder, &QObject::deleteLater);
}

}  // namespace

QObject* invokePythonLater(PyObject* callback, int delay, QObject* context)
{
    return new PendingPythonCall(callback, delay, context);
}

bool cancelPythonInvoke(QObject* handle)
{
    auto* pending = dynamic_cast<PendingPythonCall*>(handle);
    if (!pending) {
        return false;
    }
    pending->cancel();
    return true;
}

void deletePythonQObjectLater(PyObject* wrapper)
{
    PythonWrapper pySide;
    Py::Object object(wrapper);
    QObject* root = pySide.toQObject(object);
    if (!root || root->property("_FreeCAD_PythonDeletePending").toBool()) {
        return;
    }

    root->setProperty("_FreeCAD_PythonDeletePending", true);
    adoptPythonQObjectTree(root, pySide);
    root->deleteLater();
}

void adoptPythonQObject(PyObject* wrapper)
{
    PythonWrapper pySide;
    Py::Object object(wrapper);
    QObject* root = pySide.toQObject(object);
    if (!root) {
        return;
    }

    adoptPythonQObjectTree(root, pySide);
}

}  // namespace Gui
