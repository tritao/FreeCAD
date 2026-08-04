#include <gtest/gtest.h>

#include "App/QuantityInput.h"
#include "Base/NumericFormatting.h"

namespace App::QuantityInputTest
{

const Base::NumericLocaleContext enUs {
    "en_US", ".", ",", "+", "-", 3, 3
};

TEST(QuantityInput, EditingAndCommitDistinguishIncompleteNumbers)
{
    const ObjectIdentifier path;
    const QuantityConstraints constraints;

    EXPECT_EQ(
        interpretQuantityInput(
            "-", path, Base::Unit::Length, enUs, InputPhase::Editing, constraints
        ).status,
        InputStatus::Incomplete
    );
    EXPECT_EQ(
        interpretQuantityInput(
            "-", path, Base::Unit::Length, enUs, InputPhase::Commit, constraints
        ).status,
        InputStatus::Invalid
    );
    EXPECT_EQ(
        interpretQuantityInput(
            "1e", path, Base::Unit::Length, enUs, InputPhase::Editing, constraints
        ).status,
        InputStatus::Incomplete
    );
}

TEST(QuantityInput, ReportsGroupingAndUnitDiagnostics)
{
    const ObjectIdentifier path;
    const QuantityConstraints constraints;

    const auto malformed = interpretQuantityInput(
        "12,34,567 mm", path, Base::Unit::Length, enUs, InputPhase::Commit, constraints
    );
    ASSERT_EQ(malformed.status, InputStatus::Invalid);
    ASSERT_TRUE(malformed.diagnostic);
    EXPECT_EQ(malformed.diagnostic->kind, InputDiagnosticKind::MalformedGrouping);

    const auto plainSpace = interpretQuantityInput(
        "12 345 mm", path, Base::Unit::Length, enUs, InputPhase::Commit, constraints
    );
    ASSERT_EQ(plainSpace.status, InputStatus::Invalid);
    ASSERT_TRUE(plainSpace.diagnostic);
    EXPECT_EQ(plainSpace.diagnostic->kind, InputDiagnosticKind::MalformedGrouping);

    QuantityConstraints restricted;
    restricted.requiredUnit = Base::Unit::TimeSpan;
    const auto incompatible = interpretQuantityInput(
        "10 mm", path, Base::Unit::Length, enUs, InputPhase::Commit, restricted
    );
    ASSERT_EQ(incompatible.status, InputStatus::Invalid);
    ASSERT_TRUE(incompatible.diagnostic);
    EXPECT_EQ(incompatible.diagnostic->kind, InputDiagnosticKind::IncompatibleUnit);
}

TEST(QuantityInput, AcceptsGroupedQuantityAndNormalizesIt)
{
    const ObjectIdentifier path;
    const QuantityConstraints constraints;
    const auto result = interpretQuantityInput(
        "12,345.67 mm", path, Base::Unit::Length, enUs, InputPhase::Commit, constraints
    );

    ASSERT_EQ(result.status, InputStatus::Acceptable);
    ASSERT_TRUE(result.quantity);
    EXPECT_DOUBLE_EQ(result.quantity->getValue(), 12345.67);
    EXPECT_EQ(result.normalizedText, "12345.67 mm");
}

}  // namespace App::QuantityInputTest
