// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Inventor/SoDB.h>

#include <App/Application.h>
#include <App/Document.h>
#include <App/DocumentObjectGroup.h>
#include <Gui/Application.h>
#include <Gui/ViewProviderDocumentObjectGroup.h>

#include <src/App/InitApplication.h>

namespace
{

class ViewProviderDocumentObjectTest: public ::testing::Test
{
protected:
    static void SetUpTestSuite()
    {
        tests::initApplication();
        Gui::Application::initApplication();
        if (!Gui::Application::Instance) {
            static Gui::Application app(false);
        }
        if (!SoDB::isInitialized()) {
            Gui::Application::initOpenInventor();
        }
    }

    void SetUp() override
    {
        App::DocumentInitFlags createFlags;
        createFlags.createView = false;
        _docName = App::GetApplication().getUniqueDocumentName("view_provider_test");
        _doc = App::GetApplication().newDocument(_docName.c_str(), "testUser", createFlags);
        _group = static_cast<App::DocumentObjectGroup*>(
            _doc->addObject("App::DocumentObjectGroup", "Group")
        );
        _child = _doc->addObject("App::FeatureTest", "Child");
        _group->addObject(_child);
    }

    void TearDown() override
    {
        if (App::GetApplication().getDocument(_docName.c_str())) {
            App::GetApplication().closeDocument(_docName.c_str());
        }
    }

    void attachGroupViewProvider(Gui::ViewProviderDocumentObjectGroup& viewProvider)
    {
        viewProvider.attach(_group);
    }

    std::string _docName;
    App::Document* _doc {};
    App::DocumentObjectGroup* _group {};
    App::DocumentObject* _child {};
};

}  // namespace

TEST_F(ViewProviderDocumentObjectTest, groupVisibilityPropagatesToChildren)
{
    Gui::ViewProviderDocumentObjectGroup viewProvider;
    attachGroupViewProvider(viewProvider);

    viewProvider.Visibility.setValue(false);

    EXPECT_FALSE(_group->Visibility.getValue());
    EXPECT_FALSE(_child->Visibility.getValue());

    viewProvider.Visibility.setValue(true);

    EXPECT_TRUE(_group->Visibility.getValue());
    EXPECT_TRUE(_child->Visibility.getValue());
}

TEST_F(ViewProviderDocumentObjectTest, temporaryVisibilityDoesNotPropagateToChildren)
{
    Gui::ViewProviderDocumentObjectGroup viewProvider;
    attachGroupViewProvider(viewProvider);

    viewProvider.setTemporaryVisibility(false);

    EXPECT_FALSE(viewProvider.Visibility.getValue());
    EXPECT_TRUE(_group->Visibility.getValue());
    EXPECT_TRUE(_child->Visibility.getValue());
}
