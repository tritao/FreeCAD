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

#ifndef BASE_TRANSLATION_H
#define BASE_TRANSLATION_H

#include <functional>
#include <string>
#include <string_view>
#include <vector>

#ifndef FC_GLOBAL_H
# include <FCGlobal.h>
#endif

namespace Base::Translation
{

using TranslateHandler = std::function<std::string(
    std::string_view context,
    std::string_view sourceText,
    std::string_view disambiguation,
    int n
)>;

using InstallTranslatorHandler = std::function<bool(std::string_view filename)>;
using RemoveTranslatorsHandler = std::function<bool(const std::vector<std::string>& filenames)>;

BaseExport void setTranslateHandler(TranslateHandler handler);
BaseExport void setInstallTranslatorHandler(InstallTranslatorHandler handler);
BaseExport void setRemoveTranslatorsHandler(RemoveTranslatorsHandler handler);

BaseExport std::string translate(
    std::string_view context,
    std::string_view sourceText,
    std::string_view disambiguation = {},
    int n = -1
);

BaseExport bool installTranslator(std::string_view filename);
BaseExport bool removeTranslators(const std::vector<std::string>& filenames);

}  // namespace Base::Translation

#endif  // BASE_TRANSLATION_H

