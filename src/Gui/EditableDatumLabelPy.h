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

#pragma once

#include <CXX/Extensions.hxx>

namespace Gui
{

class EditableDatumLabel;
class View3DInventorViewer;

class EditableDatumLabelPy: public Py::PythonClass<EditableDatumLabelPy>
{
public:
    static void init_type();  // announce properties and methods

    EditableDatumLabelPy(Py::PythonClassInstance* self, Py::Tuple& args, Py::Dict& kwds);
    ~EditableDatumLabelPy() override;

    Py::Object repr() override;

    Py::Object activate(const Py::Tuple&);
    Py::Object deactivate(const Py::Tuple&);
    Py::Object startEdit(const Py::Tuple&, const Py::Dict&);
    Py::Object stopEdit(const Py::Tuple&);
    Py::Object isActive(const Py::Tuple&);
    Py::Object isInEdit(const Py::Tuple&);
    Py::Object getValue(const Py::Tuple&);
    Py::Object setSpinboxValue(const Py::Tuple&);
    Py::Object setPlacement(const Py::Tuple&);
    Py::Object setColor(const Py::Tuple&);
    Py::Object setPoints(const Py::Tuple&);
    Py::Object setFocus(const Py::Tuple&);
    Py::Object setFocusToSpinbox(const Py::Tuple&);
    Py::Object clearSelection(const Py::Tuple&);
    Py::Object setLabelType(const Py::Tuple&);
    Py::Object setLabelDistance(const Py::Tuple&);
    Py::Object setLabelStartAngle(const Py::Tuple&);
    Py::Object setLabelRange(const Py::Tuple&);
    Py::Object setLabelRecommendedDistance(const Py::Tuple&);
    Py::Object setLabelAutoDistanceReverse(const Py::Tuple&);
    Py::Object setSpinboxVisibleToMouse(const Py::Tuple&);
    Py::Object setLockedAppearance(const Py::Tuple&);
    Py::Object resetLockedState(const Py::Tuple&);
    Py::Object updateGeometry(const Py::Tuple&);
    Py::Object getFunction(const Py::Tuple&);

    Py::Object setValueChangedCallback(const Py::Tuple&);
    Py::Object setEditingFinishedCallback(const Py::Tuple&);
    Py::Object setEditingCanceledCallback(const Py::Tuple&);
    Py::Object setParameterUnsetCallback(const Py::Tuple&);
    Py::Object setFinishEditingCallback(const Py::Tuple&);

    EditableDatumLabel* getEditableDatumLabelPtr() const
    {
        return label;
    }

private:
    static View3DInventorViewer* asViewer(PyObject* pyViewer);

    EditableDatumLabel* label;
    PyObject* valueChangedCallback;
    PyObject* editingFinishedCallback;
    PyObject* editingCanceledCallback;
    PyObject* parameterUnsetCallback;
    PyObject* finishEditingCallback;
};

}  // namespace Gui
