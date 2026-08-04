// SPDX-License-Identifier: LGPL-2.1-or-later

#include "NumericInput.h"

#include <charconv>
#include <cmath>
#include <cctype>
#include <limits>
#include <string>
#include <string_view>
#include <vector>

#include "Exception.h"
#include "NumericFormatting.h"

namespace
{
bool startsAt(std::string_view text, std::size_t position, std::string_view value)
{
    return !value.empty() && position + value.size() <= text.size()
        && text.substr(position, value.size()) == value;
}

bool asciiDigit(const char ch)
{
    return ch >= '0' && ch <= '9';
}

bool boundary(const char ch)
{
    return std::isspace(static_cast<unsigned char>(ch)) || ch == '(' || ch == ')' || ch == '['
        || ch == ']' || ch == '<' || ch == '>' || ch == '+' || ch == '-' || ch == '*' || ch == '/'
        || ch == '^' || ch == ';';
}

bool structuralComma(const Base::NumericSyntaxContext syntax)
{
    return syntax == Base::NumericSyntaxContext::FunctionArgument;
}

Base::LocalizedNumberResult invalid(
    std::string message,
    const std::size_t offset,
    const std::size_t consumed
)
{
    Base::LocalizedNumberResult result;
    result.status = Base::LocalizedNumberResult::Status::Invalid;
    result.consumedBytes = consumed;
    result.diagnostic = Base::NumericDiagnostic {std::move(message), offset, 1};
    return result;
}

Base::LocalizedNumberResult incomplete(
    std::string message,
    const std::size_t offset,
    const std::size_t consumed,
    std::string canonical
)
{
    Base::LocalizedNumberResult result;
    result.status = Base::LocalizedNumberResult::Status::Incomplete;
    result.consumedBytes = consumed;
    result.canonicalText = std::move(canonical);
    result.diagnostic = Base::NumericDiagnostic {std::move(message), offset, 1};
    return result;
}

bool decimalAt(
    std::string_view input,
    const std::size_t position,
    const Base::NumericLocaleContext& locale,
    const Base::NumericSyntaxContext syntax,
    std::size_t& length
)
{
    length = 0;
    if (structuralComma(syntax) && (locale.decimalSeparator == "," || locale.decimalSeparator == ";")) {
        return false;
    }
    if (startsAt(input, position, locale.decimalSeparator)) {
        length = locale.decimalSeparator.size();
        return true;
    }
    if (input[position] == '.' && locale.decimalSeparator != ".") {
        length = 1;
        return true;
    }
    return input[position] == '.';
}

bool groupingAt(
    std::string_view input,
    const std::size_t position,
    const Base::NumericLocaleContext& locale,
    const Base::NumericSyntaxContext syntax,
    const bool alreadyGrouped,
    std::size_t& length
)
{
    length = 0;
    if (syntax == Base::NumericSyntaxContext::FunctionArgument
        && (locale.groupingSeparator == "," || locale.groupingSeparator == ";")) {
        return false;
    }
    if (!startsAt(input, position, locale.groupingSeparator)) {
        return false;
    }

    // In comma-decimal locales the canonical dot is also commonly the grouping symbol. Keep a
    // lone dot as canonical decimal syntax unless the rest of the token proves that it is a
    // localized grouping separator followed by a localized decimal or another group.
    if (!alreadyGrouped && locale.groupingSeparator == "." && locale.decimalSeparator != ".") {
        const auto groupStart = position + locale.groupingSeparator.size();
        std::size_t digitCount = 0;
        while (groupStart + digitCount < input.size()
               && asciiDigit(input[groupStart + digitCount])) {
            ++digitCount;
        }
        const auto afterGroup = groupStart + digitCount;
        if (digitCount != static_cast<std::size_t>(locale.primaryGroupingSize)
            || (!startsAt(input, afterGroup, locale.decimalSeparator)
                && !startsAt(input, afterGroup, locale.groupingSeparator))) {
            return false;
        }
    }

    length = locale.groupingSeparator.size();
    if (locale.groupingSeparator == " " && (position + length >= input.size()
                                              || !asciiDigit(input[position + length]))) {
        return false;
    }
    return true;
}

bool validGrouping(const std::vector<int>& groups, const Base::NumericLocaleContext& locale)
{
    if (groups.size() < 2 || locale.primaryGroupingSize <= 0 || locale.secondaryGroupingSize <= 0) {
        return false;
    }
    if (groups.back() != locale.primaryGroupingSize) {
        return false;
    }
    for (std::size_t i = 1; i + 1 < groups.size(); ++i) {
        if (groups[i] != locale.secondaryGroupingSize) {
            return false;
        }
    }
    return groups.front() > 0 && groups.front() <= locale.secondaryGroupingSize;
}

bool signAt(
    std::string_view input,
    const std::size_t position,
    const Base::NumericLocaleContext& locale,
    std::size_t& length,
    char& canonical
)
{
    length = 0;
    canonical = 0;
    if (startsAt(input, position, locale.negativeSign)) {
        length = locale.negativeSign.size();
        canonical = '-';
        return true;
    }
    if (startsAt(input, position, locale.positiveSign)) {
        length = locale.positiveSign.size();
        canonical = '+';
        return true;
    }
    if (input[position] == '-' || input[position] == '+') {
        length = 1;
        canonical = input[position];
        return true;
    }
    return false;
}

}  // namespace

Base::LocalizedNumberResult Base::scanLocalizedNumber(
    const std::string_view input,
    const NumericLocaleContext& locale,
    const NumericSyntaxContext syntax
)
{
    if (input.empty()) {
        return incomplete("Expected a number", 0, 0, {});
    }

    std::size_t position = 0;
    std::string canonical;
    canonical.reserve(input.size());

    std::size_t signLength = 0;
    char sign = 0;
    if (signAt(input, position, locale, signLength, sign)) {
        canonical.push_back(sign);
        position += signLength;
        if (position == input.size() || boundary(input[position])) {
            return incomplete("Expected digits after sign", position, position, canonical);
        }
    }

    std::vector<int> groups;
    int digitsInGroup = 0;
    int totalDigits = 0;
    bool grouped = false;

    while (position < input.size()) {
        if (asciiDigit(input[position])) {
            canonical.push_back(input[position++]);
            ++digitsInGroup;
            ++totalDigits;
            continue;
        }

        std::size_t separatorLength = 0;
        if (groupingAt(input, position, locale, syntax, grouped, separatorLength)) {
            if (digitsInGroup == 0) {
                return invalid("Grouping separator must follow digits", position, position);
            }
            groups.push_back(digitsInGroup);
            digitsInGroup = 0;
            grouped = true;
            position += separatorLength;
            if (position == input.size() || !asciiDigit(input[position])) {
                return incomplete("Expected digits after grouping separator", position, position, canonical);
            }
            continue;
        }
        break;
    }

    if (totalDigits == 0) {
        std::size_t decimalLength = 0;
        if (!decimalAt(input, position, locale, syntax, decimalLength)) {
            return invalid("Expected a numeric digit", position, position);
        }
        canonical.push_back('.');
        position += decimalLength;
        if (position == input.size() || !asciiDigit(input[position])) {
            return incomplete("Expected digits after decimal separator", position, position, canonical);
        }
        while (position < input.size() && asciiDigit(input[position])) {
            canonical.push_back(input[position++]);
            ++totalDigits;
        }
    }
    else {
        if (grouped) {
            groups.push_back(digitsInGroup);
            if (!validGrouping(groups, locale)) {
                return invalid("Malformed grouping separator placement", position, position);
            }
        }

        std::size_t decimalLength = 0;
        if (position < input.size() && decimalAt(input, position, locale, syntax, decimalLength)) {
            canonical.push_back('.');
            position += decimalLength;
            if (position == input.size() || !asciiDigit(input[position])) {
                return incomplete("Expected digits after decimal separator", position, position, canonical);
            }
            while (position < input.size() && asciiDigit(input[position])) {
                canonical.push_back(input[position++]);
            }
        }
    }

    if (position < input.size() && (input[position] == 'e' || input[position] == 'E')) {
        canonical.push_back('e');
        ++position;
        std::size_t exponentSignLength = 0;
        char exponentSign = 0;
        if (position < input.size() && signAt(input, position, locale, exponentSignLength, exponentSign)) {
            canonical.push_back(exponentSign);
            position += exponentSignLength;
        }
        const auto exponentStart = position;
        while (position < input.size() && asciiDigit(input[position])) {
            canonical.push_back(input[position++]);
        }
        if (position == exponentStart) {
            return incomplete("Expected exponent digits", position, position, canonical);
        }
    }

    if (position < input.size()) {
        if (std::isspace(static_cast<unsigned char>(input[position]))) {
            auto next = position;
            while (next < input.size()
                   && std::isspace(static_cast<unsigned char>(input[next]))) {
                ++next;
            }
            if (next < input.size() && asciiDigit(input[next])) {
                return invalid(
                    "Whitespace cannot separate digits in a numeric token", position, position
                );
            }
        }

        std::size_t separatorLength = 0;
        if (decimalAt(input, position, locale, syntax, separatorLength)
            || groupingAt(input, position, locale, syntax, grouped, separatorLength)) {
            return invalid("Unexpected numeric separator", position, position);
        }
    }

    double value = 0.0;
    const auto conversion = std::from_chars(
        canonical.data(), canonical.data() + canonical.size(), value, std::chars_format::general
    );
    if (conversion.ec == std::errc::result_out_of_range) {
        return invalid("Numeric value is out of range", 0, position);
    }
    if (conversion.ec != std::errc {} || conversion.ptr != canonical.data() + canonical.size()
        || !std::isfinite(value)) {
        return invalid("Invalid numeric literal", 0, position);
    }

    LocalizedNumberResult result;
    result.status = LocalizedNumberResult::Status::Complete;
    result.value = value;
    result.canonicalText = std::move(canonical);
    result.consumedBytes = position;
    return result;
}
