// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Base/ByteBuffer.h>

#include <cstring>
#include <string>

TEST(ByteBuffer, defaultConstruction)
{
    Base::ByteBuffer buf;
    EXPECT_TRUE(buf.empty());
    EXPECT_EQ(buf.size(), 0U);
    EXPECT_STREQ(buf.data(), "");
    EXPECT_FALSE(buf.isBorrowed());
}

TEST(ByteBuffer, borrowIsNonOwningUntilMakeOwning)
{
    const std::string backing = std::string("abc\0def", 7);
    Base::ByteBuffer buf = Base::ByteBuffer::borrow(Base::BytesView(backing.data(), backing.size()));

    EXPECT_EQ(buf.size(), 7U);
    EXPECT_TRUE(buf.isBorrowed());
    EXPECT_EQ(std::memcmp(buf.data(), backing.data(), backing.size()), 0);

    buf.makeOwning();
    EXPECT_FALSE(buf.isBorrowed());
    EXPECT_EQ(buf.size(), 7U);
    EXPECT_EQ(std::memcmp(buf.data(), backing.data(), backing.size()), 0);
}

TEST(ByteBuffer, copyOwnsAndPreservesEmbeddedNul)
{
    const std::string backing = std::string("abc\0def", 7);
    Base::ByteBuffer buf = Base::ByteBuffer::copy(Base::BytesView(backing.data(), backing.size()));

    EXPECT_FALSE(buf.isBorrowed());
    EXPECT_EQ(buf.size(), 7U);
    EXPECT_EQ(std::memcmp(buf.data(), backing.data(), backing.size()), 0);
}

TEST(ByteBuffer, copyOnWriteDetachOnMutation)
{
    Base::ByteBuffer a = Base::ByteBuffer::copy("abc");
    Base::ByteBuffer b = a;  // shares backing storage

    EXPECT_EQ(a, b);

    b.append("d");
    EXPECT_NE(a, b);

    EXPECT_EQ(a.size(), 3U);
    EXPECT_EQ(std::string(a.data(), a.size()), "abc");
    EXPECT_EQ(std::string(b.data(), b.size()), "abcd");
}
