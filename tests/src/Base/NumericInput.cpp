// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Base/NumericFormatting.h>
#include <Base/NumericInput.h>

namespace
{
Base::NumericLocaleContext locale(
    const char* localeId,
    const char* decimal,
    const char* grouping,
    int primary = 3,
    int secondary = 3
)
{
    return {localeId, decimal, grouping, "+", "-", primary, secondary};
}

void expectComplete(
    const Base::LocalizedNumberResult& result,
    double value,
    std::string_view canonical,
    std::size_t consumed
)
{
    EXPECT_EQ(result.status, Base::LocalizedNumberResult::Status::Complete);
    EXPECT_DOUBLE_EQ(result.value, value);
    EXPECT_EQ(result.canonicalText, canonical);
    EXPECT_EQ(result.consumedBytes, consumed);
    EXPECT_FALSE(result.diagnostic.has_value());
}
}  // namespace

TEST(NumericInputTest, canonicalAndLocalizedDecimals)
{
    const auto de = locale("de_DE", ",", ".");
    expectComplete(Base::scanLocalizedNumber("1,25 mm", de, Base::NumericSyntaxContext::Standalone),
                   1.25,
                   "1.25",
                   4);
    expectComplete(
        Base::scanLocalizedNumber("12.345,67 mm", de, Base::NumericSyntaxContext::Standalone),
        12345.67,
        "12345.67",
        9
    );
    expectComplete(Base::scanLocalizedNumber("1.25 mm", de, Base::NumericSyntaxContext::Standalone),
                   1.25,
                   "1.25",
                   4);
}

TEST(NumericInputTest, westernGroupingAndScientificNotation)
{
    const auto en = locale("en_US", ".", ",");
    expectComplete(
        Base::scanLocalizedNumber("1,234.5 mm", en, Base::NumericSyntaxContext::Standalone),
        1234.5,
        "1234.5",
        7
    );
    expectComplete(
        Base::scanLocalizedNumber("1,234e5 mm", en, Base::NumericSyntaxContext::Standalone),
        123400000.0,
        "1234e5",
        7
    );
}

TEST(NumericInputTest, indianGroupingUsesSecondarySize)
{
    const auto enIn = locale("en_IN", ".", ",", 3, 2);
    expectComplete(
        Base::scanLocalizedNumber("12,34,567 mm", enIn, Base::NumericSyntaxContext::Standalone),
        1234567.0,
        "1234567",
        9
    );
}

TEST(NumericInputTest, malformedGroupingIsInvalid)
{
    const auto en = locale("en_US", ".", ",");
    const auto result = Base::scanLocalizedNumber(
        "12,34,567", en, Base::NumericSyntaxContext::Standalone
    );

    EXPECT_EQ(result.status, Base::LocalizedNumberResult::Status::Invalid);
    ASSERT_TRUE(result.diagnostic.has_value());
    EXPECT_NE(result.diagnostic->message.find("grouping"), std::string::npos);
}

TEST(NumericInputTest, multipleDecimalsAndIncompleteExponentsAreDiagnosed)
{
    const auto en = locale("en_US", ".", ",");
    const auto multipleDecimals = Base::scanLocalizedNumber(
        "1.2.3", en, Base::NumericSyntaxContext::Standalone
    );
    EXPECT_EQ(multipleDecimals.status, Base::LocalizedNumberResult::Status::Invalid);

    const auto incompleteExponent = Base::scanLocalizedNumber(
        "1e", en, Base::NumericSyntaxContext::Standalone
    );
    EXPECT_EQ(incompleteExponent.status, Base::LocalizedNumberResult::Status::Incomplete);
}

TEST(NumericInputTest, negativeAndLocalizedSigns)
{
    const auto en = locale("en_US", ".", ",");
    expectComplete(
        Base::scanLocalizedNumber("-1,234.5 mm", en, Base::NumericSyntaxContext::Standalone),
        -1234.5,
        "-1234.5",
        8
    );

    auto fa = Base::createNumericLocaleContext("fa_IR");
    const std::string input = fa.negativeSign + "1" + fa.decimalSeparator + "25 mm";
    const auto localized = Base::scanLocalizedNumber(
        input, fa, Base::NumericSyntaxContext::Standalone
    );
    EXPECT_EQ(localized.status, Base::LocalizedNumberResult::Status::Complete);
    EXPECT_DOUBLE_EQ(localized.value, -1.25);
    EXPECT_EQ(localized.canonicalText, "-1.25");
}

TEST(NumericInputTest, exactGroupingSymbolsAreRequired)
{
    const auto en = locale("en_US", ".", ",");
    const auto plainSpace = Base::scanLocalizedNumber(
        "12 345", en, Base::NumericSyntaxContext::Standalone
    );
    EXPECT_EQ(plainSpace.status, Base::LocalizedNumberResult::Status::Invalid);
    ASSERT_TRUE(plainSpace.diagnostic.has_value());
    EXPECT_NE(plainSpace.diagnostic->message.find("Whitespace"), std::string::npos);

    const auto narrowSpace = locale("fr_FR", ",", "\xC2\xA0");
    expectComplete(
        Base::scanLocalizedNumber("12\xC2\xA0345", narrowSpace, Base::NumericSyntaxContext::Standalone),
        12345.0,
        "12345",
        7
    );
}

TEST(NumericInputTest, FunctionArgumentsTakePrecedenceOverCommaGrouping)
{
    const auto en = locale("en_US", ".", ",");
    const auto firstArgument = Base::scanLocalizedNumber(
        "1,234", en, Base::NumericSyntaxContext::FunctionArgument
    );
    expectComplete(firstArgument, 1.0, "1", 1);

    const auto groupedArgument = locale("space", ".", " ");
    expectComplete(
        Base::scanLocalizedNumber(
            "1 234; 2", groupedArgument, Base::NumericSyntaxContext::FunctionArgument
        ),
        1234.0,
        "1234",
        5
    );
}
