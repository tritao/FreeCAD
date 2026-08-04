// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Base/Exception.h>
#include <Base/NumericFormatting.h>
#include <Base/Quantity.h>

TEST(NumericFormattingTest, createsLocaleSpecificSeparators)
{
    const auto enUs = Base::createNumericLocaleContext("en_US");
    const auto deDe = Base::createNumericLocaleContext("de_DE");
    const auto enIn = Base::createNumericLocaleContext("en_IN");

    EXPECT_EQ(enUs.localeId, "en_US");
    EXPECT_EQ(enUs.decimalSeparator, ".");
    EXPECT_EQ(enUs.groupingSeparator, ",");
    EXPECT_EQ(enUs.positiveSign, "+");
    EXPECT_EQ(enUs.negativeSign, "-");
    EXPECT_EQ(enUs.primaryGroupingSize, 3);
    EXPECT_EQ(enUs.secondaryGroupingSize, 3);

    EXPECT_EQ(deDe.localeId, "de_DE");
    EXPECT_EQ(deDe.decimalSeparator, ",");
    EXPECT_EQ(deDe.groupingSeparator, ".");

    EXPECT_EQ(enIn.localeId, "en_IN");
    EXPECT_EQ(enIn.decimalSeparator, ".");
    EXPECT_EQ(enIn.groupingSeparator, ",");
    EXPECT_EQ(enIn.primaryGroupingSize, 3);
    EXPECT_EQ(enIn.secondaryGroupingSize, 2);
}

TEST(NumericFormattingTest, formatsValuesWithEffectiveSeparators)
{
    const Base::NumericLocaleContext formatting {
        "en_US", ",", "\xC2\xA0", "+", "-", 3, 3
    };

    Base::QuantityFormat fixed(Base::QuantityFormat::Fixed, 2);
    fixed.option = Base::QuantityFormat::None;
    EXPECT_EQ(Base::formatNumericValue(1.5, fixed, formatting), "1,50");

    Base::QuantityFormat grouped(Base::QuantityFormat::Default, 0);
    grouped.option = Base::QuantityFormat::None;
    EXPECT_EQ(
        Base::formatNumericValue(12345.0, grouped, formatting),
        std::string {"12\xC2\xA0"
                     "345"}
    );
}

TEST(NumericFormattingTest, cLocaleUsesDeterministicFallback)
{
    const Base::NumericLocaleContext expected {"en_US_POSIX", ".", ",", "+", "-", 3, 3};
    EXPECT_EQ(Base::createNumericLocaleContext("C"), expected);
}

TEST(NumericFormattingTest, normalizesIcuLocaleIdentifiers)
{
    EXPECT_EQ(Base::normalizeIcuLocaleId(""), "en_US_POSIX");
    EXPECT_EQ(Base::normalizeIcuLocaleId("POSIX"), "en_US_POSIX");
    EXPECT_EQ(Base::normalizeIcuLocaleId("de_DE"), "de_DE");
}

TEST(NumericFormattingTest, rejectsBogusIcuLocaleIdentifiers)
{
    constexpr auto bogusLocale = "not a locale";

    EXPECT_THROW(Base::normalizeIcuLocaleId(bogusLocale), Base::ValueError);
    EXPECT_THROW(Base::createNumericLocaleContext(bogusLocale), Base::ValueError);
    EXPECT_THROW(Base::setIcuDefaultLocale(bogusLocale), Base::ValueError);
}

TEST(NumericFormattingTest, publishedStateIsACompleteSnapshot)
{
    const auto previous = Base::currentNumericLocaleContext();
    const Base::NumericLocaleContext expected {"en_US", ".", ",", "+", "-", 3, 3};

    Base::publishNumericLocaleContext(expected);

    EXPECT_EQ(Base::currentNumericLocaleContext(), expected);
    Base::publishNumericLocaleContext(previous);
}
