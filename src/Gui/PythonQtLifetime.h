// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <FCGlobal.h>
#include <QtCore/qglobal.h>

struct _object;
using PyObject = _object;

QT_BEGIN_NAMESPACE
class QObject;
QT_END_NAMESPACE

namespace Gui
{

GuiExport QObject* invokePythonLater(PyObject* callback, int delay, QObject* context);
GuiExport bool cancelPythonInvoke(QObject* handle);
GuiExport void adoptPythonQObject(PyObject* wrapper);
GuiExport void deletePythonQObjectLater(PyObject* wrapper);

}  // namespace Gui
