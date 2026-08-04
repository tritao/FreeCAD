// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <optional>
#include <string>
#include <string_view>

#include <FCGlobal.h>

namespace Base
{
struct NumericLocaleContext;

enum class NumericSyntaxContext
{
    Standalone,
    Expression,
    FunctionArgument
};

struct BaseExport NumericDiagnostic
{
    std::string message;
    std::size_t offset {};
    std::size_t length {};
};

struct BaseExport LocalizedNumberResult
{
    enum class Status
    {
        Complete,
        Incomplete,
        Invalid
    };

    Status status {Status::Invalid};
    double value {};
    std::string canonicalText;
    std::size_t consumedBytes {};
    std::optional<NumericDiagnostic> diagnostic;
};

/** Scan exactly one localized numeric token without asking ICU to decide token boundaries. */
BaseExport LocalizedNumberResult scanLocalizedNumber(
    std::string_view input,
    const NumericLocaleContext& locale,
    NumericSyntaxContext syntax
);

}  // namespace Base
