// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <QLocale>

#include <Base/NumericFormatting.h>

namespace Gui
{

/** Build a complete numeric-locale context from this widget's QLocale. */
GuiExport Base::NumericLocaleContext numericLocaleContextFor(const QLocale& locale);

}  // namespace Gui
