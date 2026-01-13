#include <gtest/gtest.h>

#include <Base/Sha1.h>

#include <array>
#include <cstdint>
#include <string>

namespace
{

std::string toHex(const std::array<std::uint8_t, 20>& digest)
{
    static constexpr char kHex[] = "0123456789abcdef";
    std::string out;
    out.resize(digest.size() * 2);
    for (std::size_t i = 0; i < digest.size(); ++i) {
        out[i * 2 + 0] = kHex[(digest[i] >> 4U) & 0x0FU];
        out[i * 2 + 1] = kHex[(digest[i] >> 0U) & 0x0FU];
    }
    return out;
}

}  // namespace

TEST(Sha1, EmptyString)
{
    const auto digest = Base::sha1Digest({});
    EXPECT_EQ(toHex(digest), "da39a3ee5e6b4b0d3255bfef95601890afd80709");
}

TEST(Sha1, Abc)
{
    const auto digest = Base::sha1Digest("abc");
    EXPECT_EQ(toHex(digest), "a9993e364706816aba3e25717850c26c9cd0d89d");
}

