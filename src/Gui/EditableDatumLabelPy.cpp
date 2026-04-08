/***************************************************************************
 *   Copyright (c) 2026 Joao Matos <joao@tritao.eu>                        *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 51 Franklin Street,      *
 *   Fifth Floor, Boston, MA  02110-1301, USA                              *
 *                                                                         *
 ***************************************************************************/

#include <array>
#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>

#include <Base/Console.h>
#include <Base/Interpreter.h>
#include <Base/PlacementPy.h>
#include <Base/PyWrapParseTupleAndKeywords.h>
#include <Base/VectorPy.h>

#include "EditableDatumLabel.h"
#include "EditableDatumLabelPy.h"
#include "PythonWrapper.h"
#include "View3DInventor.h"
#include "View3DPy.h"
#include "View3DViewerPy.h"


using namespace Gui;

namespace
{

const SbColor defaultEditableDatumLabelColor(1.0F, 0.149F, 0.0F);

std::string normalizeToken(std::string value)
{
    value.erase(
        std::remove_if(
            value.begin(),
            value.end(),
            [](unsigned char ch) { return ch == '_' || ch == '-' || std::isspace(ch); }
        ),
        value.end()
    );
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

EditableDatumLabel* asLabel(EditableDatumLabelPy* self)
{
    if (!self || !self->getEditableDatumLabelPtr()) {
        throw Py::RuntimeError("EditableDatumLabel is deleted");
    }
    return self->getEditableDatumLabelPtr();
}

Base::Placement asPlacement(PyObject* pyPlacement)
{
    if (!PyObject_TypeCheck(pyPlacement, &Base::PlacementPy::Type)) {
        throw Py::TypeError("placement must be a Base.Placement");
    }

    return *static_cast<Base::PlacementPy*>(pyPlacement)->getPlacementPtr();
}

Base::Vector3d asVector(PyObject* pyVector)
{
    if (!PyObject_TypeCheck(pyVector, &Base::VectorPy::Type)) {
        throw Py::TypeError("point must be a Base.Vector");
    }

    return *static_cast<Base::VectorPy*>(pyVector)->getVectorPtr();
}

SbColor asColor(PyObject* pyColor)
{
    if (pyColor == Py_None) {
        return defaultEditableDatumLabelColor;
    }

    Py::Sequence sequence(Py::Object(pyColor, false));
    if (sequence.length() != 3) {
        throw Py::TypeError("color must be a sequence of three floats");
    }

    const float r = static_cast<float>(Py::Float(sequence[0]).as_double());
    const float g = static_cast<float>(Py::Float(sequence[1]).as_double());
    const float b = static_cast<float>(Py::Float(sequence[2]).as_double());
    return {r, g, b};
}

SoDatumLabel::Type asLabelType(PyObject* pyType)
{
    std::string labelType = normalizeToken(Py::String(pyType).as_std_string());
    if (labelType == "angle") {
        return SoDatumLabel::ANGLE;
    }
    if (labelType == "distance") {
        return SoDatumLabel::DISTANCE;
    }
    if (labelType == "distancex") {
        return SoDatumLabel::DISTANCEX;
    }
    if (labelType == "distancey") {
        return SoDatumLabel::DISTANCEY;
    }
    if (labelType == "radius") {
        return SoDatumLabel::RADIUS;
    }
    if (labelType == "diameter") {
        return SoDatumLabel::DIAMETER;
    }
    if (labelType == "symmetric") {
        return SoDatumLabel::SYMMETRIC;
    }
    if (labelType == "arclength") {
        return SoDatumLabel::ARCLENGTH;
    }

    throw Py::ValueError("unknown label type");
}

EditableDatumLabel::Function asFunction(PyObject* pyFunction)
{
    std::string function = normalizeToken(Py::String(pyFunction).as_std_string());
    if (function == "positioning") {
        return EditableDatumLabel::Function::Positioning;
    }
    if (function == "dimensioning") {
        return EditableDatumLabel::Function::Dimensioning;
    }
    if (function == "forced") {
        return EditableDatumLabel::Function::Forced;
    }

    throw Py::ValueError("unknown EditableDatumLabel function");
}

Py::Object functionToPyObject(EditableDatumLabel::Function function)
{
    switch (function) {
        case EditableDatumLabel::Function::Positioning:
            return Py::String("positioning");
        case EditableDatumLabel::Function::Dimensioning:
            return Py::String("dimensioning");
        case EditableDatumLabel::Function::Forced:
            return Py::String("forced");
    }

    return Py::String("positioning");
}

void invokeCallback(PyObject* callback)
{
    if (!callback) {
        return;
    }

    Base::PyGILStateLocker lock;
    try {
        Py::Callable method(callback);
        method.apply(Py::Tuple());
    }
    catch (const Py::Exception&) {
        PyErr_Print();
    }
}

void invokeCallback(PyObject* callback, double value)
{
    if (!callback) {
        return;
    }

    Base::PyGILStateLocker lock;
    try {
        Py::Callable method(callback);
        Py::Tuple args(1);
        args.setItem(0, Py::Float(value));
        method.apply(args);
    }
    catch (const Py::Exception&) {
        PyErr_Print();
    }
}

void replaceCallback(PyObject*& slot, PyObject* callback)
{
    if (callback == Py_None) {
        callback = nullptr;
    }
    else if (!PyCallable_Check(callback)) {
        throw Py::TypeError("callback must be callable or None");
    }

    Base::PyGILStateLocker lock;
    Py_XINCREF(callback);
    Py_XDECREF(slot);
    slot = callback;
}

}  // namespace


EditableDatumLabelPy::EditableDatumLabelPy(Py::PythonClassInstance* self, Py::Tuple& args, Py::Dict& kwds)
    : Py::PythonClass<EditableDatumLabelPy>::PythonClass(self, args, kwds)
    , label(nullptr)
    , valueChangedCallback(nullptr)
    , editingFinishedCallback(nullptr)
    , editingCanceledCallback(nullptr)
    , parameterUnsetCallback(nullptr)
    , finishEditingCallback(nullptr)
{
    static const std::array<const char*, 6>
        keywords {"viewer", "placement", "color", "autoDistance", "avoidMouseCursor", nullptr};

    PyObject* pyViewer = nullptr;
    PyObject* pyPlacement = nullptr;
    PyObject* pyColor = Py_None;
    PyObject* pyAutoDistance = Py_False;
    PyObject* pyAvoidMouseCursor = Py_False;

    if (!Base::Wrapped_ParseTupleAndKeywords(
            args.ptr(),
            kwds.ptr(),
            "OO|OOO",
            keywords,
            &pyViewer,
            &pyPlacement,
            &pyColor,
            &pyAutoDistance,
            &pyAvoidMouseCursor
        )) {
        throw Py::Exception();
    }

    label = new EditableDatumLabel(
        asViewer(pyViewer),
        asPlacement(pyPlacement),
        asColor(pyColor),
        PyObject_IsTrue(pyAutoDistance) == 1,
        PyObject_IsTrue(pyAvoidMouseCursor) == 1
    );

    QObject::connect(label, &EditableDatumLabel::valueChanged, label, [this](double value) {
        invokeCallback(this->valueChangedCallback, value);
    });
    QObject::connect(label, &EditableDatumLabel::editingFinished, label, [this](double value) {
        invokeCallback(this->editingFinishedCallback, value);
    });
    QObject::connect(label, &EditableDatumLabel::editingCanceled, label, [this](double value) {
        invokeCallback(this->editingCanceledCallback, value);
    });
    QObject::connect(label, &EditableDatumLabel::parameterUnset, label, [this]() {
        invokeCallback(this->parameterUnsetCallback);
    });
    QObject::connect(label, &EditableDatumLabel::finishEditingOnAllOVPs, label, [this]() {
        invokeCallback(this->finishEditingCallback);
    });
}

View3DInventorViewer* EditableDatumLabelPy::asViewer(PyObject* pyViewer)
{
    if (PyObject_TypeCheck(pyViewer, View3DInventorPy::type_object())) {
        auto* viewPy = dynamic_cast<View3DInventorPy*>(Py::getPythonExtensionBase(pyViewer));
        if (!viewPy) {
            throw Py::RuntimeError("Cannot resolve View3DInventor Python wrapper");
        }
        auto* view = viewPy->getView3DInventorPtr();
        if (!view || !view->getViewer()) {
            throw Py::RuntimeError("Cannot use a deleted View3DInventor");
        }
        return view->getViewer();
    }

    if (!PyObject_TypeCheck(pyViewer, View3DInventorViewerPy::type_object())) {
        throw Py::TypeError("viewer must be a View3DInventor or View3DInventorViewer");
    }

    auto* viewerPy = dynamic_cast<View3DInventorViewerPy*>(Py::getPythonExtensionBase(pyViewer));
    if (!viewerPy) {
        throw Py::RuntimeError("Cannot resolve View3DInventorViewer Python wrapper");
    }
    if (!viewerPy->_viewer) {
        throw Py::RuntimeError("Cannot use a deleted View3DInventorViewer");
    }

    return viewerPy->_viewer;
}

EditableDatumLabelPy::~EditableDatumLabelPy()
{
    {
        Base::PyGILStateLocker lock;
        Py_XDECREF(valueChangedCallback);
        Py_XDECREF(editingFinishedCallback);
        Py_XDECREF(editingCanceledCallback);
        Py_XDECREF(parameterUnsetCallback);
        Py_XDECREF(finishEditingCallback);
    }

    delete label;
    label = nullptr;
}

PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, activate)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, deactivate)
PYCXX_KEYWORDS_METHOD_DECL(EditableDatumLabelPy, startEdit)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, stopEdit)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, isActive)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, isInEdit)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, getValue)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setSpinboxValue)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setPlacement)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setColor)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setPoints)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setFocus)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setFocusToSpinbox)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, clearSelection)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelType)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelDistance)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelStartAngle)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelRange)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelRecommendedDistance)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLabelAutoDistanceReverse)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setSpinboxVisibleToMouse)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setLockedAppearance)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, resetLockedState)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, updateGeometry)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, getFunction)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setValueChangedCallback)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setEditingFinishedCallback)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setEditingCanceledCallback)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setParameterUnsetCallback)
PYCXX_VARARGS_METHOD_DECL(EditableDatumLabelPy, setFinishEditingCallback)

void EditableDatumLabelPy::init_type()
{
    behaviors().name("Gui.EditableDatumLabel");
    behaviors().doc("Python binding class for EditableDatumLabel");
    behaviors().supportRepr();

    PYCXX_ADD_VARARGS_METHOD(activate, activate, "activate()");
    PYCXX_ADD_VARARGS_METHOD(deactivate, deactivate, "deactivate()");
    PYCXX_ADD_KEYWORDS_METHOD(
        startEdit,
        startEdit,
        "startEdit(value, eventFilter=None, visibleToMouse=False)"
    );
    PYCXX_ADD_VARARGS_METHOD(stopEdit, stopEdit, "stopEdit()");
    PYCXX_ADD_VARARGS_METHOD(isActive, isActive, "isActive()");
    PYCXX_ADD_VARARGS_METHOD(isInEdit, isInEdit, "isInEdit()");
    PYCXX_ADD_VARARGS_METHOD(getValue, getValue, "getValue()");
    PYCXX_ADD_VARARGS_METHOD(setSpinboxValue, setSpinboxValue, "setSpinboxValue(value)");
    PYCXX_ADD_VARARGS_METHOD(setPlacement, setPlacement, "setPlacement(placement)");
    PYCXX_ADD_VARARGS_METHOD(setColor, setColor, "setColor((r, g, b))");
    PYCXX_ADD_VARARGS_METHOD(setPoints, setPoints, "setPoints(p1, p2)");
    PYCXX_ADD_VARARGS_METHOD(setFocus, setFocus, "setFocus()");
    PYCXX_ADD_VARARGS_METHOD(setFocusToSpinbox, setFocusToSpinbox, "setFocusToSpinbox()");
    PYCXX_ADD_VARARGS_METHOD(clearSelection, clearSelection, "clearSelection()");
    PYCXX_ADD_VARARGS_METHOD(
        setLabelType,
        setLabelType,
        "setLabelType(label_type, function='positioning')"
    );
    PYCXX_ADD_VARARGS_METHOD(setLabelDistance, setLabelDistance, "setLabelDistance(distance)");
    PYCXX_ADD_VARARGS_METHOD(setLabelStartAngle, setLabelStartAngle, "setLabelStartAngle(angle)");
    PYCXX_ADD_VARARGS_METHOD(setLabelRange, setLabelRange, "setLabelRange(range)");
    PYCXX_ADD_VARARGS_METHOD(
        setLabelRecommendedDistance,
        setLabelRecommendedDistance,
        "setLabelRecommendedDistance()"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setLabelAutoDistanceReverse,
        setLabelAutoDistanceReverse,
        "setLabelAutoDistanceReverse(bool)"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setSpinboxVisibleToMouse,
        setSpinboxVisibleToMouse,
        "setSpinboxVisibleToMouse(bool)"
    );
    PYCXX_ADD_VARARGS_METHOD(setLockedAppearance, setLockedAppearance, "setLockedAppearance(bool)");
    PYCXX_ADD_VARARGS_METHOD(resetLockedState, resetLockedState, "resetLockedState()");
    PYCXX_ADD_VARARGS_METHOD(updateGeometry, updateGeometry, "updateGeometry()");
    PYCXX_ADD_VARARGS_METHOD(getFunction, getFunction, "getFunction()");
    PYCXX_ADD_VARARGS_METHOD(
        setValueChangedCallback,
        setValueChangedCallback,
        "setValueChangedCallback(callable_or_none)"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setEditingFinishedCallback,
        setEditingFinishedCallback,
        "setEditingFinishedCallback(callable_or_none)"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setEditingCanceledCallback,
        setEditingCanceledCallback,
        "setEditingCanceledCallback(callable_or_none)"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setParameterUnsetCallback,
        setParameterUnsetCallback,
        "setParameterUnsetCallback(callable_or_none)"
    );
    PYCXX_ADD_VARARGS_METHOD(
        setFinishEditingCallback,
        setFinishEditingCallback,
        "setFinishEditingCallback(callable_or_none)"
    );

    behaviors().readyType();
}

Py::Object EditableDatumLabelPy::repr()
{
    std::stringstream s;
    s << "<EditableDatumLabel at " << label << ">";
    return Py::String(s.str());
}

Py::Object EditableDatumLabelPy::activate(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->activate();
    return Py::None();
}

Py::Object EditableDatumLabelPy::deactivate(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->deactivate();
    return Py::None();
}

Py::Object EditableDatumLabelPy::startEdit(const Py::Tuple& args, const Py::Dict& kwds)
{
    static const std::array<const char*, 4> keywords {"value", "eventFilter", "visibleToMouse", nullptr};

    double value = 0.0;
    PyObject* pyFilter = Py_None;
    PyObject* pyVisible = Py_False;
    if (!Base::Wrapped_ParseTupleAndKeywords(
            args.ptr(),
            kwds.ptr(),
            "d|OO",
            keywords,
            &value,
            &pyFilter,
            &pyVisible
        )) {
        throw Py::Exception();
    }

    QObject* filter = nullptr;
    if (pyFilter != Py_None) {
        PythonWrapper wrap;
        wrap.loadWidgetsModule();
        filter = wrap.toQObject(Py::Object(pyFilter, false));
        if (!filter) {
            throw Py::TypeError("eventFilter must be a QObject or None");
        }
    }

    asLabel(this)->startEdit(value, filter, PyObject_IsTrue(pyVisible) == 1);
    return Py::None();
}

Py::Object EditableDatumLabelPy::stopEdit(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->stopEdit();
    return Py::None();
}

Py::Object EditableDatumLabelPy::isActive(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    return Py::Boolean(asLabel(this)->isActive());
}

Py::Object EditableDatumLabelPy::isInEdit(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    return Py::Boolean(asLabel(this)->isInEdit());
}

Py::Object EditableDatumLabelPy::getValue(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    return Py::Float(asLabel(this)->getValue());
}

Py::Object EditableDatumLabelPy::setSpinboxValue(const Py::Tuple& args)
{
    double value = 0.0;
    if (!PyArg_ParseTuple(args.ptr(), "d", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setSpinboxValue(value);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setPlacement(const Py::Tuple& args)
{
    PyObject* pyPlacement = nullptr;
    if (!PyArg_ParseTuple(args.ptr(), "O!", &Base::PlacementPy::Type, &pyPlacement)) {
        throw Py::Exception();
    }
    asLabel(this)->setPlacement(asPlacement(pyPlacement));
    return Py::None();
}

Py::Object EditableDatumLabelPy::setColor(const Py::Tuple& args)
{
    PyObject* pyColor = nullptr;
    if (!PyArg_ParseTuple(args.ptr(), "O", &pyColor)) {
        throw Py::Exception();
    }
    asLabel(this)->setColor(asColor(pyColor));
    return Py::None();
}

Py::Object EditableDatumLabelPy::setPoints(const Py::Tuple& args)
{
    PyObject* pyP1 = nullptr;
    PyObject* pyP2 = nullptr;
    if (
        !PyArg_ParseTuple(args.ptr(), "O!O!", &Base::VectorPy::Type, &pyP1, &Base::VectorPy::Type, &pyP2)
    ) {
        throw Py::Exception();
    }
    asLabel(this)->setPoints(asVector(pyP1), asVector(pyP2));
    return Py::None();
}

Py::Object EditableDatumLabelPy::setFocus(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->setFocus();
    return Py::None();
}

Py::Object EditableDatumLabelPy::setFocusToSpinbox(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->setFocusToSpinbox();
    return Py::None();
}

Py::Object EditableDatumLabelPy::clearSelection(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->clearSelection();
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelType(const Py::Tuple& args)
{
    PyObject* pyType = nullptr;
    PyObject* pyFunction = nullptr;
    if (!PyArg_ParseTuple(args.ptr(), "O|O", &pyType, &pyFunction)) {
        throw Py::Exception();
    }

    EditableDatumLabel::Function function = EditableDatumLabel::Function::Positioning;
    if (pyFunction) {
        function = asFunction(pyFunction);
    }

    asLabel(this)->setLabelType(asLabelType(pyType), function);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelDistance(const Py::Tuple& args)
{
    double value = 0.0;
    if (!PyArg_ParseTuple(args.ptr(), "d", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setLabelDistance(value);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelStartAngle(const Py::Tuple& args)
{
    double value = 0.0;
    if (!PyArg_ParseTuple(args.ptr(), "d", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setLabelStartAngle(value);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelRange(const Py::Tuple& args)
{
    double value = 0.0;
    if (!PyArg_ParseTuple(args.ptr(), "d", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setLabelRange(value);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelRecommendedDistance(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->setLabelRecommendedDistance();
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLabelAutoDistanceReverse(const Py::Tuple& args)
{
    PyObject* value = Py_False;
    if (!PyArg_ParseTuple(args.ptr(), "O", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setLabelAutoDistanceReverse(PyObject_IsTrue(value) == 1);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setSpinboxVisibleToMouse(const Py::Tuple& args)
{
    PyObject* value = Py_False;
    if (!PyArg_ParseTuple(args.ptr(), "O", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setSpinboxVisibleToMouse(PyObject_IsTrue(value) == 1);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setLockedAppearance(const Py::Tuple& args)
{
    PyObject* value = Py_False;
    if (!PyArg_ParseTuple(args.ptr(), "O", &value)) {
        throw Py::Exception();
    }
    asLabel(this)->setLockedAppearance(PyObject_IsTrue(value) == 1);
    return Py::None();
}

Py::Object EditableDatumLabelPy::resetLockedState(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->resetLockedState();
    return Py::None();
}

Py::Object EditableDatumLabelPy::updateGeometry(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    asLabel(this)->updateGeometry();
    return Py::None();
}

Py::Object EditableDatumLabelPy::getFunction(const Py::Tuple& args)
{
    if (!PyArg_ParseTuple(args.ptr(), "")) {
        throw Py::Exception();
    }
    return functionToPyObject(asLabel(this)->getFunction());
}

Py::Object EditableDatumLabelPy::setValueChangedCallback(const Py::Tuple& args)
{
    PyObject* callback = Py_None;
    if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
        throw Py::Exception();
    }
    replaceCallback(valueChangedCallback, callback);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setEditingFinishedCallback(const Py::Tuple& args)
{
    PyObject* callback = Py_None;
    if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
        throw Py::Exception();
    }
    replaceCallback(editingFinishedCallback, callback);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setEditingCanceledCallback(const Py::Tuple& args)
{
    PyObject* callback = Py_None;
    if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
        throw Py::Exception();
    }
    replaceCallback(editingCanceledCallback, callback);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setParameterUnsetCallback(const Py::Tuple& args)
{
    PyObject* callback = Py_None;
    if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
        throw Py::Exception();
    }
    replaceCallback(parameterUnsetCallback, callback);
    return Py::None();
}

Py::Object EditableDatumLabelPy::setFinishEditingCallback(const Py::Tuple& args)
{
    PyObject* callback = Py_None;
    if (!PyArg_ParseTuple(args.ptr(), "O", &callback)) {
        throw Py::Exception();
    }
    replaceCallback(finishEditingCallback, callback);
    return Py::None();
}
