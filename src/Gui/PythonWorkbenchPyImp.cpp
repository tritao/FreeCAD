/***************************************************************************
 *   Copyright (c) 2007 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include <array>
#include <optional>

// generated out of PythonWorkbench.pyi
#include <Base/PyWrapParseTupleAndKeywords.h>

#include "PythonWorkbenchPy.h"
#include "PythonWorkbenchPy.cpp"

using namespace Gui;

namespace
{
std::optional<long> parseToolbarOptionValue(PyObject* value, const char* optionName)
{
    if (!value || value == Py_None) {
        return std::nullopt;
    }
    if (!PyLong_Check(value)) {
        throw Py::TypeError(std::string(optionName) + " must be an integer enum value");
    }

    const long rawValue = PyLong_AsLong(value);
    if (PyErr_Occurred()) {
        throw Py::Exception();
    }

    return rawValue;
}

std::optional<ToolBarItem::Tier> parseToolbarTierOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "tier");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::Tier::Recommended):
            return ToolBarItem::Tier::Recommended;
        case static_cast<long>(ToolBarItem::Tier::Secondary):
            return ToolBarItem::Tier::Secondary;
        case static_cast<long>(ToolBarItem::Tier::Advanced):
            return ToolBarItem::Tier::Advanced;
        case static_cast<long>(ToolBarItem::Tier::Contextual):
            return ToolBarItem::Tier::Contextual;
    }

    throw Py::ValueError("tier has an invalid enum value");
}

std::optional<ToolBarItem::DefaultVisibility> parseToolbarVisibilityOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "visibility");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::DefaultVisibility::Visible):
            return ToolBarItem::DefaultVisibility::Visible;
        case static_cast<long>(ToolBarItem::DefaultVisibility::Hidden):
            return ToolBarItem::DefaultVisibility::Hidden;
        case static_cast<long>(ToolBarItem::DefaultVisibility::Unavailable):
            return ToolBarItem::DefaultVisibility::Unavailable;
    }

    throw Py::ValueError("visibility has an invalid enum value");
}

std::optional<ToolBarItem::Host> parseToolbarHostOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "host");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::Host::MainWindow):
            return ToolBarItem::Host::MainWindow;
        case static_cast<long>(ToolBarItem::Host::ActiveView):
            return ToolBarItem::Host::ActiveView;
        case static_cast<long>(ToolBarItem::Host::Panel):
            return ToolBarItem::Host::Panel;
    }

    throw Py::ValueError("host has an invalid enum value");
}

std::optional<ToolBarItem::PanelRole> parseToolbarPanelRoleOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "panel_role");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::PanelRole::None):
            return ToolBarItem::PanelRole::None;
        case static_cast<long>(ToolBarItem::PanelRole::ModelTree):
            return ToolBarItem::PanelRole::ModelTree;
    }

    throw Py::ValueError("panel_role has an invalid enum value");
}

std::optional<ToolBarItem::PanelPlacement> parseToolbarPanelPlacementOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "panel_placement");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::PanelPlacement::Top):
            return ToolBarItem::PanelPlacement::Top;
        case static_cast<long>(ToolBarItem::PanelPlacement::Bottom):
            return ToolBarItem::PanelPlacement::Bottom;
    }

    throw Py::ValueError("panel_placement has an invalid enum value");
}

std::optional<ToolBarItem::ViewHostRequirement> parseToolbarViewHostRequirementOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "view_host_requirement");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::ViewHostRequirement::AnyView):
            return ToolBarItem::ViewHostRequirement::AnyView;
        case static_cast<long>(ToolBarItem::ViewHostRequirement::View3D):
            return ToolBarItem::ViewHostRequirement::View3D;
    }

    throw Py::ValueError("view_host_requirement has an invalid enum value");
}

std::optional<ToolBarItem::ViewPresentation> parseToolbarViewPresentationOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "view_presentation");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::ViewPresentation::Docked):
            return ToolBarItem::ViewPresentation::Docked;
        case static_cast<long>(ToolBarItem::ViewPresentation::CenteredOverlay):
            return ToolBarItem::ViewPresentation::CenteredOverlay;
    }

    throw Py::ValueError("view_presentation has an invalid enum value");
}

std::optional<ToolBarItem::ViewOverlayEdge> parseToolbarViewOverlayEdgeOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "view_overlay_edge");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::ViewOverlayEdge::Top):
            return ToolBarItem::ViewOverlayEdge::Top;
        case static_cast<long>(ToolBarItem::ViewOverlayEdge::Bottom):
            return ToolBarItem::ViewOverlayEdge::Bottom;
        case static_cast<long>(ToolBarItem::ViewOverlayEdge::Left):
            return ToolBarItem::ViewOverlayEdge::Left;
        case static_cast<long>(ToolBarItem::ViewOverlayEdge::Right):
            return ToolBarItem::ViewOverlayEdge::Right;
    }

    throw Py::ValueError("view_overlay_edge has an invalid enum value");
}

std::optional<ToolBarItem::ViewOverlayEdgePersistence> parseToolbarViewOverlayEdgePersistenceOption(
    PyObject* value
)
{
    const auto rawValue = parseToolbarOptionValue(value, "view_overlay_edge_persistence");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::ViewOverlayEdgePersistence::ByScope):
            return ToolBarItem::ViewOverlayEdgePersistence::ByScope;
        case static_cast<long>(ToolBarItem::ViewOverlayEdgePersistence::Shared):
            return ToolBarItem::ViewOverlayEdgePersistence::Shared;
        case static_cast<long>(ToolBarItem::ViewOverlayEdgePersistence::Contextual):
            return ToolBarItem::ViewOverlayEdgePersistence::Contextual;
    }

    throw Py::ValueError("view_overlay_edge_persistence has an invalid enum value");
}

std::optional<ToolBarItem::Size> parseToolbarSizeOption(PyObject* value)
{
    const auto rawValue = parseToolbarOptionValue(value, "size");
    if (!rawValue) {
        return std::nullopt;
    }

    switch (*rawValue) {
        case static_cast<long>(ToolBarItem::Size::Default):
            return ToolBarItem::Size::Default;
        case static_cast<long>(ToolBarItem::Size::Slim):
            return ToolBarItem::Size::Slim;
    }

    throw Py::ValueError("size has an invalid enum value");
}
}  // namespace

/** @class PythonWorkbenchPy
 * The workbench Python class provides additional methods for manipulation of python
 * workbench objects.
 * From the view of Python PythonWorkbenchPy is also derived from WorkbenchPy as in C++.
 * @see Workbench
 * @see WorkbenchPy
 * @see PythonWorkbench
 * @author Werner Mayer
 */

// returns a string which represent the object e.g. when printed in python
std::string PythonWorkbenchPy::representation() const
{
    return {"<Workbench object>"};
}

/** Appends a new menu */
PyObject* PythonWorkbenchPy::appendMenu(PyObject* args)
{
    PY_TRY
    {
        PyObject* pPath;
        PyObject* pItems;
        if (!PyArg_ParseTuple(args, "OO", &pPath, &pItems)) {
            return nullptr;
        }

        // menu path
        std::list<std::string> path;
        if (PyList_Check(pPath)) {
            int nDepth = PyList_Size(pPath);
            for (int j = 0; j < nDepth; ++j) {
                PyObject* item = PyList_GetItem(pPath, j);
                if (PyUnicode_Check(item)) {
                    const char* pItem = PyUnicode_AsUTF8(item);
                    path.emplace_back(pItem);
                }
                else {
                    continue;
                }
            }
        }
        else if (PyUnicode_Check(pPath)) {
            const char* pItem = PyUnicode_AsUTF8(pPath);
            path.emplace_back(pItem);
        }
        else {
            PyErr_SetString(
                PyExc_AssertionError,
                "Expected either a string or a stringlist as first argument"
            );
            return nullptr;
        }

        // menu items
        std::list<std::string> items;
        if (PyList_Check(pItems)) {
            int nItems = PyList_Size(pItems);
            for (int i = 0; i < nItems; ++i) {
                PyObject* item = PyList_GetItem(pItems, i);
                if (PyUnicode_Check(item)) {
                    const char* pItem = PyUnicode_AsUTF8(item);
                    items.emplace_back(pItem);
                }
                else {
                    continue;
                }
            }
        }
        else if (PyUnicode_Check(pItems)) {
            const char* pItem = PyUnicode_AsUTF8(pItems);
            items.emplace_back(pItem);
        }
        else {
            PyErr_SetString(
                PyExc_AssertionError,
                "Expected either a string or a stringlist as first argument"
            );
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->appendMenu(path, items);

        Py_Return;
    }
    PY_CATCH;
}

/** Removes a menu */
PyObject* PythonWorkbenchPy::removeMenu(PyObject* args)
{
    PY_TRY
    {
        char* psMenu;
        if (!PyArg_ParseTuple(args, "s", &psMenu)) {
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->removeMenu(psMenu);
        Py_Return;
    }
    PY_CATCH;
}

/** Appends new context menu items */
PyObject* PythonWorkbenchPy::appendContextMenu(PyObject* args)
{
    PY_TRY
    {
        PyObject* pPath;
        PyObject* pItems;
        if (!PyArg_ParseTuple(args, "OO", &pPath, &pItems)) {
            return nullptr;
        }

        // menu path
        std::list<std::string> path;
        if (PyList_Check(pPath)) {
            int nDepth = PyList_Size(pPath);
            for (int j = 0; j < nDepth; ++j) {
                PyObject* item = PyList_GetItem(pPath, j);
                if (PyUnicode_Check(item)) {
                    const char* pItem = PyUnicode_AsUTF8(item);
                    path.emplace_back(pItem);
                }
                else {
                    continue;
                }
            }
        }
        else if (PyUnicode_Check(pPath)) {
            const char* pItem = PyUnicode_AsUTF8(pPath);
            path.emplace_back(pItem);
        }
        else {
            PyErr_SetString(
                PyExc_AssertionError,
                "Expected either a string or a stringlist as first argument"
            );
            return nullptr;
        }

        // menu items
        std::list<std::string> items;
        if (PyList_Check(pItems)) {
            int nItems = PyList_Size(pItems);
            for (int i = 0; i < nItems; ++i) {
                PyObject* item = PyList_GetItem(pItems, i);
                if (PyUnicode_Check(item)) {
                    const char* pItem = PyUnicode_AsUTF8(item);
                    items.emplace_back(pItem);
                }
                else {
                    continue;
                }
            }
        }
        else if (PyUnicode_Check(pItems)) {
            const char* pItem = PyUnicode_AsUTF8(pItems);
            items.emplace_back(pItem);
        }
        else {
            PyErr_SetString(
                PyExc_AssertionError,
                "Expected either a string or a stringlist as first argument"
            );
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->appendContextMenu(path, items);

        Py_Return;
    }
    PY_CATCH;
}

/** Removes a context menu */
PyObject* PythonWorkbenchPy::removeContextMenu(PyObject* args)
{
    PY_TRY
    {
        char* psMenu;
        if (!PyArg_ParseTuple(args, "s", &psMenu)) {
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->removeContextMenu(psMenu);
        Py_Return;
    }
    PY_CATCH;
}

/** Appends a new toolbar */
PyObject* PythonWorkbenchPy::appendToolbar(PyObject* args, PyObject* kwd)
{
    PY_TRY
    {
        static constexpr std::array<const char*, 14> keywords = {
            "name",
            "items",
            "key",
            "tier",
            "visibility",
            "host",
            "panel_role",
            "panel_placement",
            "view_host_requirement",
            "view_presentation",
            "view_overlay_edge",
            "view_overlay_edge_persistence",
            "size",
            nullptr,
        };

        PyObject* pObject = nullptr;
        char* psToolBar = nullptr;
        const char* key = nullptr;
        PyObject* tier = nullptr;
        PyObject* visibility = nullptr;
        PyObject* host = nullptr;
        PyObject* panelRole = nullptr;
        PyObject* panelPlacement = nullptr;
        PyObject* viewHostRequirement = nullptr;
        PyObject* viewPresentation = nullptr;
        PyObject* viewOverlayEdge = nullptr;
        PyObject* viewOverlayEdgePersistence = nullptr;
        PyObject* size = nullptr;
        if (!Base::Wrapped_ParseTupleAndKeywords(
                args,
                kwd,
                "sO|zOOOOOOOOOO:appendToolbar",
                keywords,
                &psToolBar,
                &pObject,
                &key,
                &tier,
                &visibility,
                &host,
                &panelRole,
                &panelPlacement,
                &viewHostRequirement,
                &viewPresentation,
                &viewOverlayEdge,
                &viewOverlayEdgePersistence,
                &size
            )) {
            return nullptr;
        }
        if (!psToolBar || psToolBar[0] == '\0') {
            throw Py::ValueError("name must not be empty");
        }
        if (key && key[0] == '\0') {
            throw Py::ValueError("key must not be empty");
        }
        if (!PyList_Check(pObject)) {
            PyErr_SetString(PyExc_AssertionError, "Expected a list as second argument");
            return nullptr;
        }

        std::list<std::string> items;
        int nSize = PyList_Size(pObject);
        for (int i = 0; i < nSize; ++i) {
            PyObject* item = PyList_GetItem(pObject, i);
            if (PyUnicode_Check(item)) {
                const char* pItem = PyUnicode_AsUTF8(item);
                items.emplace_back(pItem);
            }
            else {
                continue;
            }
        }
        PythonBaseWorkbench::ToolBarOptions options;
        if (key) {
            options.key = key;
        }
        options.tier = parseToolbarTierOption(tier);
        options.visibility = parseToolbarVisibilityOption(visibility);
        options.host = parseToolbarHostOption(host);
        options.panelRole = parseToolbarPanelRoleOption(panelRole);
        options.panelPlacement = parseToolbarPanelPlacementOption(panelPlacement);
        options.viewHostRequirement = parseToolbarViewHostRequirementOption(viewHostRequirement);
        options.viewPresentation = parseToolbarViewPresentationOption(viewPresentation);
        options.viewOverlayEdge = parseToolbarViewOverlayEdgeOption(viewOverlayEdge);
        options.viewOverlayEdgePersistence = parseToolbarViewOverlayEdgePersistenceOption(
            viewOverlayEdgePersistence
        );
        options.size = parseToolbarSizeOption(size);
        getPythonBaseWorkbenchPtr()->appendToolbar(psToolBar, items, options);

        Py_Return;
    }
    PY_CATCH;
}

/** Removes a toolbar */
PyObject* PythonWorkbenchPy::removeToolbar(PyObject* args)
{
    PY_TRY
    {
        char* psToolBar;
        if (!PyArg_ParseTuple(args, "s", &psToolBar)) {
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->removeToolbar(psToolBar);
        Py_Return;
    }
    PY_CATCH;
}

/** Appends a new command bar */
PyObject* PythonWorkbenchPy::appendCommandbar(PyObject* args)
{
    PY_TRY
    {
        PyObject* pObject;
        char* psToolBar;
        if (!PyArg_ParseTuple(args, "sO", &psToolBar, &pObject)) {
            return nullptr;
        }
        if (!PyList_Check(pObject)) {
            PyErr_SetString(PyExc_AssertionError, "Expected a list as second argument");
            return nullptr;
        }

        std::list<std::string> items;
        int nSize = PyList_Size(pObject);
        for (int i = 0; i < nSize; ++i) {
            PyObject* item = PyList_GetItem(pObject, i);
            if (PyUnicode_Check(item)) {
                const char* pItem = PyUnicode_AsUTF8(item);
                items.emplace_back(pItem);
            }
            else {
                continue;
            }
        }

        getPythonBaseWorkbenchPtr()->appendCommandbar(psToolBar, items);

        Py_Return;
    }
    PY_CATCH;
}

/** Removes a command bar */
PyObject* PythonWorkbenchPy::removeCommandbar(PyObject* args)
{
    PY_TRY
    {
        char* psToolBar;
        if (!PyArg_ParseTuple(args, "s", &psToolBar)) {
            return nullptr;
        }

        getPythonBaseWorkbenchPtr()->removeCommandbar(psToolBar);
        Py_Return;
    }
    PY_CATCH;
}

PyObject* PythonWorkbenchPy::getCustomAttributes(const char*) const
{
    return nullptr;
}

int PythonWorkbenchPy::setCustomAttributes(const char*, PyObject*)
{
    return 0;
}

// deprecated methods

PyObject* PythonWorkbenchPy::AppendMenu(PyObject* args)
{
    return appendMenu(args);
}

PyObject* PythonWorkbenchPy::RemoveMenu(PyObject* args)
{
    return removeMenu(args);
}

PyObject* PythonWorkbenchPy::ListMenus(PyObject* args)
{
    return listMenus(args);
}

PyObject* PythonWorkbenchPy::AppendContextMenu(PyObject* args)
{
    return appendContextMenu(args);
}

PyObject* PythonWorkbenchPy::RemoveContextMenu(PyObject* args)
{
    return removeContextMenu(args);
}

PyObject* PythonWorkbenchPy::AppendToolbar(PyObject* args)
{
    return appendToolbar(args, nullptr);
}

PyObject* PythonWorkbenchPy::RemoveToolbar(PyObject* args)
{
    return removeToolbar(args);
}

PyObject* PythonWorkbenchPy::ListToolbars(PyObject* args)
{
    return listToolbars(args);
}

PyObject* PythonWorkbenchPy::AppendCommandbar(PyObject* args)
{
    return appendCommandbar(args);
}

PyObject* PythonWorkbenchPy::RemoveCommandbar(PyObject* args)
{
    return removeCommandbar(args);
}

PyObject* PythonWorkbenchPy::ListCommandbars(PyObject* args)
{
    return listCommandbars(args);
}
