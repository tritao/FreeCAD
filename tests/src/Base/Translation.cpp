// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include "Base/Translation.h"

TEST(Translation, FallbackReturnsSource)
{
    Base::Translation::setTranslateHandler({});
    EXPECT_EQ(
        std::string("Hello"),
        Base::Translation::translate("Ctx", "Hello")
    );
}

TEST(Translation, TranslateHandlerOverrides)
{
    Base::Translation::setTranslateHandler(
        [](std::string_view context, std::string_view source, std::string_view disambig, int n) {
            EXPECT_EQ("Ctx", context);
            EXPECT_EQ("Hello", source);
            EXPECT_EQ("", disambig);
            EXPECT_EQ(-1, n);
            return std::string("Bonjour");
        }
    );

    EXPECT_EQ(
        std::string("Bonjour"),
        Base::Translation::translate("Ctx", "Hello")
    );
    Base::Translation::setTranslateHandler({});
}

TEST(Translation, InstallRemoveHandlersDefaultToFalse)
{
    Base::Translation::setInstallTranslatorHandler({});
    Base::Translation::setRemoveTranslatorsHandler({});
    EXPECT_FALSE(Base::Translation::installTranslator("some.qm"));
    EXPECT_FALSE(Base::Translation::removeTranslators({}));
}

TEST(Translation, InstallRemoveHandlersCalled)
{
    std::string installed;
    std::vector<std::string> removed;

    Base::Translation::setInstallTranslatorHandler([&installed](std::string_view filename) {
        installed = std::string(filename);
        return true;
    });
    Base::Translation::setRemoveTranslatorsHandler([&removed](const std::vector<std::string>& filenames) {
        removed = filenames;
        return true;
    });

    EXPECT_TRUE(Base::Translation::installTranslator("a.qm"));
    EXPECT_EQ(std::string("a.qm"), installed);

    const std::vector<std::string> files {"a.qm", "b.qm"};
    EXPECT_TRUE(Base::Translation::removeTranslators(files));
    EXPECT_EQ(files, removed);

    Base::Translation::setInstallTranslatorHandler({});
    Base::Translation::setRemoveTranslatorsHandler({});
}

