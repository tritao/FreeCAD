// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <App/ExpressionTokenizer.h>

TEST(ExpressionTokenizer, ReturnsFullPrefixAtEnd)
{
    App::ExpressionTokenizer tokenizer;
    const std::string prefix = "Box.Length";
    const std::string completion = tokenizer.perform(prefix, /*posBytes*/ 10);

    EXPECT_EQ(completion, "Box.Length");

    int start = -1;
    int end = -1;
    tokenizer.getPrefixRange(start, end);
    EXPECT_EQ(start, 0);
    EXPECT_EQ(end, 10);
}

TEST(ExpressionTokenizer, TruncatesToSeparatorWhenCursorAtTokenStart)
{
    App::ExpressionTokenizer tokenizer;
    const std::string prefix = "Box.Length";
    const std::string completion = tokenizer.perform(prefix, /*posBytes*/ 4);  // "Box.|Length"

    EXPECT_EQ(completion, "Box.");

    int start = -1;
    int end = -1;
    tokenizer.getPrefixRange(start, end);
    EXPECT_EQ(start, 0);
    EXPECT_EQ(end, 10);  // replaces the rest of the token after cursor
}

TEST(ExpressionTokenizer, HandlesUtf8AtEndUsingByteCursorPositions)
{
    App::ExpressionTokenizer tokenizer;
    const std::string prefix = u8"α.β";
    const std::string completion = tokenizer.perform(prefix, /*posBytes*/ prefix.size());

    EXPECT_EQ(completion, prefix);

    int start = -1;
    int end = -1;
    tokenizer.getPrefixRange(start, end);
    EXPECT_EQ(start, 0);
    EXPECT_EQ(end, static_cast<int>(prefix.size()));
}

TEST(ExpressionTokenizer, ReturnsEmptyOnTrailingSpace)
{
    App::ExpressionTokenizer tokenizer;
    const std::string prefix = "Box. ";
    const std::string completion = tokenizer.perform(prefix, /*posBytes*/ 5);
    EXPECT_TRUE(completion.empty());
}
