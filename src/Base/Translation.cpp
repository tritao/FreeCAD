// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026                                                   *
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

#include "Translation.h"

#include <mutex>

namespace Base::Translation
{

namespace
{
std::mutex handlerMutex;
TranslateHandler translateHandler;
InstallTranslatorHandler installTranslatorHandler;
RemoveTranslatorsHandler removeTranslatorsHandler;
}  // namespace

void setTranslateHandler(TranslateHandler handler)
{
    std::lock_guard<std::mutex> lock(handlerMutex);
    translateHandler = std::move(handler);
}

void setInstallTranslatorHandler(InstallTranslatorHandler handler)
{
    std::lock_guard<std::mutex> lock(handlerMutex);
    installTranslatorHandler = std::move(handler);
}

void setRemoveTranslatorsHandler(RemoveTranslatorsHandler handler)
{
    std::lock_guard<std::mutex> lock(handlerMutex);
    removeTranslatorsHandler = std::move(handler);
}

std::string translate(
    std::string_view context,
    std::string_view sourceText,
    std::string_view disambiguation,
    int n
)
{
    TranslateHandler handler;
    {
        std::lock_guard<std::mutex> lock(handlerMutex);
        handler = translateHandler;
    }

    if (handler) {
        return handler(context, sourceText, disambiguation, n);
    }

    return std::string(sourceText);
}

bool installTranslator(std::string_view filename)
{
    InstallTranslatorHandler handler;
    {
        std::lock_guard<std::mutex> lock(handlerMutex);
        handler = installTranslatorHandler;
    }

    if (!handler) {
        return false;
    }

    return handler(filename);
}

bool removeTranslators(const std::vector<std::string>& filenames)
{
    RemoveTranslatorsHandler handler;
    {
        std::lock_guard<std::mutex> lock(handlerMutex);
        handler = removeTranslatorsHandler;
    }

    if (!handler) {
        return false;
    }

    return handler(filenames);
}

}  // namespace Base::Translation

