// SPDX-License-Identifier: LGPL-2.1-or-later

#include "NumericLocale.h"

#include <utility>

#include <QStringList>

#include <Base/NumericFormatting.h>

namespace
{
std::string toUtf8(const QString& text)
{
    const QByteArray utf8 = text.toUtf8();
    return std::string(utf8.constData(), utf8.size());
}

std::pair<int, int> groupingSizes(const QLocale& locale)
{
    const QString separator = locale.groupSeparator();
    const QString formatted = locale.toString(123456789.0, 'f', 0);
    const auto groups = formatted.split(separator, Qt::KeepEmptyParts);
    if (separator.isEmpty() || groups.size() < 2) {
        return {0, 0};
    }

    const int primary = groups.back().size();
    const int secondary = groups.size() > 2 ? groups[groups.size() - 2].size() : primary;
    return {primary, secondary};
}
}  // namespace

Base::NumericLocaleContext Gui::numericLocaleContextFor(const QLocale& locale)
{
    const auto [primary, secondary] = groupingSizes(locale);
    const QString localeName = locale.name();

    return {
        Base::normalizeIcuLocaleId(toUtf8(localeName)),
        toUtf8(QString(locale.decimalPoint())),
        toUtf8(QString(locale.groupSeparator())),
        toUtf8(QString(locale.positiveSign())),
        toUtf8(QString(locale.negativeSign())),
        primary,
        secondary
    };
}
