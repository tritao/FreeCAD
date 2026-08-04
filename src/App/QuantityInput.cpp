// SPDX-License-Identifier: LGPL-2.1-or-later

#include "QuantityInput.h"

#include <algorithm>
#include <charconv>
#include <cctype>
#include <limits>
#include <string>

#include <App/Expression.h>
#include <App/ExpressionParser.h>
#include <App/ObjectIdentifier.h>
#include <Base/Exception.h>
#include <Base/NumericFormatting.h>
#include <Base/NumericInput.h>

namespace
{
bool asciiDigit(const char ch)
{
    return ch >= '0' && ch <= '9';
}

std::size_t firstInputCharacter(std::string_view input)
{
    std::size_t position = 0;
    while (position < input.size()
           && std::isspace(static_cast<unsigned char>(input[position]))) {
        ++position;
    }
    return position;
}

bool startsNumericInput(
    std::string_view input,
    const std::size_t position,
    const Base::NumericLocaleContext& locale
)
{
    if (position >= input.size()) {
        return false;
    }
    if (asciiDigit(input[position]) || input[position] == '.') {
        return true;
    }
    if (!locale.decimalSeparator.empty()
        && input.substr(position, locale.decimalSeparator.size()) == locale.decimalSeparator) {
        return true;
    }
    const std::string_view positiveSign {
        locale.positiveSign.data(), locale.positiveSign.size()
    };
    const std::string_view negativeSign {
        locale.negativeSign.data(), locale.negativeSign.size()
    };
    for (const auto sign : {std::string_view {"+"}, std::string_view {"-"}, positiveSign,
                            negativeSign}) {
        if (!sign.empty() && input.substr(position, sign.size()) == sign) {
            return true;
        }
    }
    return false;
}

App::InputDiagnosticKind diagnosticKind(std::string_view message)
{
    if (message.find("grouping") != std::string_view::npos
        || message.find("Whitespace cannot separate digits") != std::string_view::npos) {
        return App::InputDiagnosticKind::MalformedGrouping;
    }
    return App::InputDiagnosticKind::ExpressionSyntax;
}

App::QuantityInputResult invalid(
    App::InputDiagnosticKind kind,
    std::string message,
    const std::size_t offset = 0,
    const std::size_t length = 1
)
{
    App::QuantityInputResult result;
    result.status = App::InputStatus::Invalid;
    result.diagnostic = App::InputDiagnostic {kind, std::move(message), offset, length};
    return result;
}

App::QuantityInputResult incomplete(
    const App::InputPhase phase,
    std::string message,
    const std::size_t offset = 0,
    const std::size_t length = 1
)
{
    if (phase == App::InputPhase::Commit) {
        return invalid(App::InputDiagnosticKind::IncompleteNumber, std::move(message), offset, length);
    }

    App::QuantityInputResult result;
    result.status = App::InputStatus::Incomplete;
    result.diagnostic = App::InputDiagnostic {
        App::InputDiagnosticKind::IncompleteNumber,
        std::move(message),
        offset,
        length
    };
    return result;
}

std::string canonicalQuantityText(const Base::Quantity& quantity)
{
    char number[128] {};
    const auto conversion = std::to_chars(
        std::begin(number), std::end(number), quantity.getValue(), std::chars_format::general,
        std::numeric_limits<double>::max_digits10
    );
    std::string result;
    if (conversion.ec == std::errc {}) {
        result.assign(number, conversion.ptr);
    }
    else {
        result = "nan";
    }
    const auto unit = quantity.getUnit().getString();
    if (!unit.empty()) {
        result += ' ';
        result += unit;
    }
    return result;
}

}  // namespace

App::QuantityInputResult App::interpretQuantityInput(
    const std::string_view input,
    const ObjectIdentifier& path,
    const Base::Unit& defaultUnit,
    const Base::NumericLocaleContext& locale,
    const InputPhase phase,
    const QuantityConstraints& constraints
)
{
    const auto first = firstInputCharacter(input);
    if (first == input.size()) {
        return incomplete(phase, "Enter a quantity", first);
    }

    // Scan an initial numeric token before invoking either parser. This is what preserves the
    // distinction between an unfinished edit ("-", "12,", "1e") and a syntax failure.
    if (startsNumericInput(input, first, locale)) {
        const auto scan = Base::scanLocalizedNumber(
            input.substr(first), locale, Base::NumericSyntaxContext::Standalone
        );
        if (scan.status == Base::LocalizedNumberResult::Status::Incomplete) {
            return incomplete(
                phase,
                scan.diagnostic ? scan.diagnostic->message : "Complete the number",
                first + (scan.diagnostic ? scan.diagnostic->offset : 0),
                scan.diagnostic ? scan.diagnostic->length : 1
            );
        }
        if (scan.status == Base::LocalizedNumberResult::Status::Invalid) {
            const auto message = scan.diagnostic ? scan.diagnostic->message : "Invalid number";
            return invalid(
                diagnosticKind(message),
                message,
                first + (scan.diagnostic ? scan.diagnostic->offset : 0),
                scan.diagnostic ? scan.diagnostic->length : 1
            );
        }
    }

    Base::Quantity quantity;
    std::shared_ptr<Expression> parsedExpression;
    try {
        if (const auto* owner = path.getDocumentObject()) {
            const std::string inputString(input);
            auto parsed = App::ExpressionParser::parseUserInput(
                owner, inputString.c_str(), locale
            );
            parsedExpression = std::shared_ptr<Expression>(std::move(parsed));
            std::unique_ptr<App::Expression> evaluated(parsedExpression->eval());
            auto* number = freecad_cast<NumberExpression*>(evaluated.get());
            if (!number) {
                return invalid(
                    InputDiagnosticKind::Evaluation,
                    "Expression must evaluate to a number"
                );
            }
            quantity = number->getQuantity();
        }
        else {
            quantity = Base::Quantity::parseUserInput(std::string(input), locale);
        }
    }
    catch (const Base::ParserError& error) {
        return invalid(diagnosticKind(error.what()), error.what());
    }
    catch (const Base::UnitsMismatchError& error) {
        return invalid(InputDiagnosticKind::IncompatibleUnit, error.what());
    }
    catch (const Base::Exception& error) {
        return invalid(InputDiagnosticKind::Evaluation, error.what());
    }

    if (quantity.isDimensionless()) {
        quantity.setUnit(defaultUnit);
    }

    if (constraints.requiredUnit && !quantity.isDimensionlessOrUnit(*constraints.requiredUnit)) {
        return invalid(InputDiagnosticKind::IncompatibleUnit, "Incompatible unit");
    }
    if (constraints.minimum && quantity.getValue() < *constraints.minimum) {
        return invalid(InputDiagnosticKind::OutOfRange, "Value is below the allowed range");
    }
    if (constraints.maximum && quantity.getValue() > *constraints.maximum) {
        return invalid(InputDiagnosticKind::OutOfRange, "Value is above the allowed range");
    }

    QuantityInputResult result;
    result.status = InputStatus::Acceptable;
    result.quantity = quantity;
    result.expression = std::move(parsedExpression);
    result.normalizedText = canonicalQuantityText(quantity);
    return result;
}
