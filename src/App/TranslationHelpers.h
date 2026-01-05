// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef APP_TRANSLATIONHELPERS_H
#define APP_TRANSLATIONHELPERS_H

#include <string>

#include <Base/Translation.h>

// Declares a Qt-free `tr()` compatible helper for App classes.
// When no translation handler is installed, this returns the source text.
#define FC_APP_DECLARE_TR_FUNCTIONS(contextLiteral) \
public: \
    static std::string tr(const char* sourceText, const char* disambiguation = nullptr, int n = -1) \
    { \
        return ::Base::Translation::translate( \
            contextLiteral, \
            sourceText ? sourceText : "", \
            disambiguation ? disambiguation : "", \
            n \
        ); \
    }

#endif  // APP_TRANSLATIONHELPERS_H

