// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Inventor/SoDB.h>
#include <Inventor/SbViewportRegion.h>
#include <Inventor/actions/SoGetBoundingBoxAction.h>
#include <Inventor/actions/SoRayPickAction.h>
#include <Inventor/nodes/SoCube.h>
#include <Inventor/nodes/SoGroup.h>
#include <Inventor/nodes/SoSeparator.h>

#include <App/Application.h>
#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/DocumentObjectGroup.h>
#include <App/ViewDefinition.h>
#include <Gui/Application.h>
#include <Gui/Inventor/SoViewContextElement.h>
#include <Gui/Selection/SoFCUnifiedSelection.h>
#include <Gui/ViewContext.h>
#include <Gui/ViewInstance.h>
#include <Gui/ViewInstance.h>
#include <Gui/ViewProviderDocumentObject.h>
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

TEST_F(ViewProviderDocumentObjectTest, viewContextTraversesHiddenProviderWithoutChangingModeSwitch)
{
    Gui::ViewProviderDocumentObject viewProvider;
    viewProvider.attach(_child);
    auto* mode = new SoSeparator;
    mode->addChild(new SoCube);
    viewProvider.addDisplayMaskMode(mode, "ContextTest");
    viewProvider.setDisplayMaskMode("ContextTest");
    viewProvider.Visibility.setValue(false);
    ASSERT_EQ(viewProvider.getModeSwitch()->whichChild.getValue(), SO_SWITCH_NONE);

    Gui::ViewContext context;
    const auto layer = context.pushLayer();
    ASSERT_TRUE(context.setVisibility(layer, _child, Gui::ViewContext::Visibility::Visible));

    auto* scene = new Gui::SoFCUnifiedSelection;
    scene->ref();
    scene->setViewContext(&context);
    auto* nested = new SoGroup;
    nested->addChild(viewProvider.getRoot());
    scene->addChild(nested);

    SoGetBoundingBoxAction action(SbViewportRegion(100, 100));
    action.apply(scene);
    EXPECT_FALSE(action.getBoundingBox().isEmpty());
    EXPECT_EQ(viewProvider.getModeSwitch()->whichChild.getValue(), SO_SWITCH_NONE);
    scene->unref();
}

TEST_F(ViewProviderDocumentObjectTest, sharedProviderUsesIndependentViewContexts)
{
    Gui::ViewProviderDocumentObject viewProvider;
    viewProvider.attach(_child);
    auto* mode = new SoSeparator;
    mode->addChild(new SoCube);
    viewProvider.addDisplayMaskMode(mode, "ContextTest");
    viewProvider.setDisplayMaskMode("ContextTest");

    Gui::ViewContext hiddenContext;
    const auto hiddenLayer = hiddenContext.pushLayer();
    ASSERT_TRUE(hiddenContext.setVisibility(hiddenLayer, _child, Gui::ViewContext::Visibility::Hidden));
    Gui::ViewContext visibleContext;
    const auto visibleLayer = visibleContext.pushLayer();
    ASSERT_TRUE(
        visibleContext.setVisibility(visibleLayer, _child, Gui::ViewContext::Visibility::Visible)
    );

    auto* hiddenScene = new Gui::SoFCUnifiedSelection;
    hiddenScene->ref();
    hiddenScene->setViewContext(&hiddenContext);
    hiddenScene->addChild(viewProvider.getRoot());
    auto* visibleScene = new Gui::SoFCUnifiedSelection;
    visibleScene->ref();
    visibleScene->setViewContext(&visibleContext);
    visibleScene->addChild(viewProvider.getRoot());

    SoGetBoundingBoxAction hiddenAction(SbViewportRegion(100, 100));
    hiddenAction.apply(hiddenScene);
    EXPECT_TRUE(hiddenAction.getBoundingBox().isEmpty());
    SoGetBoundingBoxAction visibleAction(SbViewportRegion(100, 100));
    visibleAction.apply(visibleScene);
    EXPECT_FALSE(visibleAction.getBoundingBox().isEmpty());

    SoRayPickAction hiddenPick(SbViewportRegion(100, 100));
    hiddenPick.setRay(SbVec3f(0, 0, 5), SbVec3f(0, 0, -1));
    hiddenPick.apply(hiddenScene);
    EXPECT_EQ(hiddenPick.getPickedPoint(), nullptr);
    SoRayPickAction visiblePick(SbViewportRegion(100, 100));
    visiblePick.setRay(SbVec3f(0, 0, 5), SbVec3f(0, 0, -1));
    visiblePick.apply(visibleScene);
    EXPECT_NE(visiblePick.getPickedPoint(), nullptr);

    hiddenScene->unref();
    visibleScene->unref();
}

TEST_F(ViewProviderDocumentObjectTest, auxiliaryRootGateUsesViewerContext)
{
    Gui::ViewProviderDocumentObject viewProvider;
    viewProvider.attach(_child);
    Gui::ViewContext hiddenContext;
    const auto layer = hiddenContext.pushLayer();
    ASSERT_TRUE(hiddenContext.setVisibility(layer, _child, Gui::ViewContext::Visibility::Hidden));

    auto* hiddenGate = new Gui::SoViewContextGate(&viewProvider, new SoCube, &hiddenContext);
    hiddenGate->ref();
    SoGetBoundingBoxAction hiddenAction(SbViewportRegion(100, 100));
    hiddenAction.apply(hiddenGate);
    EXPECT_TRUE(hiddenAction.getBoundingBox().isEmpty());
    hiddenGate->unref();

    Gui::ViewContext visibleContext;
    auto* visibleGate = new Gui::SoViewContextGate(&viewProvider, new SoCube, &visibleContext);
    visibleGate->ref();
    SoGetBoundingBoxAction visibleAction(SbViewportRegion(100, 100));
    visibleAction.apply(visibleGate);
    EXPECT_FALSE(visibleAction.getBoundingBox().isEmpty());
    visibleGate->unref();
}

TEST_F(ViewProviderDocumentObjectTest, auxiliaryRootGateDoesNotRetainViewProvider)
{
    Gui::ViewContext context;
    const auto layer = context.pushLayer();
    ASSERT_TRUE(context.setVisibility(layer, _child, Gui::ViewContext::Visibility::Hidden));

    Gui::SoViewContextGate* gate = nullptr;
    {
        Gui::ViewProviderDocumentObject viewProvider;
        viewProvider.attach(_child);
        gate = new Gui::SoViewContextGate(&viewProvider, new SoCube, &context);
        gate->ref();
    }

    SoGetBoundingBoxAction action(SbViewportRegion(100, 100));
    action.apply(gate);
    EXPECT_TRUE(action.getBoundingBox().isEmpty());
    gate->unref();
}

TEST_F(ViewProviderDocumentObjectTest, viewInstanceKeepsRepresentationViewerLocal)
{
    Gui::ViewProviderDocumentObject viewProvider;
    viewProvider.attach(_child);
    Gui::ViewContext hiddenContext;
    const auto hiddenLayer = hiddenContext.pushLayer();
    ASSERT_TRUE(
        hiddenContext.setVisibility(hiddenLayer, _child, Gui::ViewContext::Visibility::Hidden)
    );

    Gui::ViewInstance instance(&viewProvider, &hiddenContext);
    instance.setRepresentation(new SoCube);
    ASSERT_TRUE(instance.hasRepresentation());

    SoGetBoundingBoxAction hiddenAction(SbViewportRegion(100, 100));
    hiddenAction.apply(instance.getRoot());
    EXPECT_TRUE(hiddenAction.getBoundingBox().isEmpty());

    ASSERT_TRUE(
        hiddenContext.setVisibility(hiddenLayer, _child, Gui::ViewContext::Visibility::Visible)
    );
    SoGetBoundingBoxAction visibleAction(SbViewportRegion(100, 100));
    visibleAction.apply(instance.getRoot());
    EXPECT_FALSE(visibleAction.getBoundingBox().isEmpty());

    instance.clearRepresentation();
    EXPECT_FALSE(instance.hasRepresentation());
}

TEST_F(ViewProviderDocumentObjectTest, twoInstancesCanUseDifferentContexts)
{
    Gui::ViewProviderDocumentObject viewProvider;
    viewProvider.attach(_child);
    Gui::ViewContext hiddenContext;
    const auto hiddenLayer = hiddenContext.pushLayer();
    ASSERT_TRUE(
        hiddenContext.setVisibility(hiddenLayer, _child, Gui::ViewContext::Visibility::Hidden)
    );
    Gui::ViewContext visibleContext;
    const auto visibleLayer = visibleContext.pushLayer();
    ASSERT_TRUE(
        visibleContext.setVisibility(visibleLayer, _child, Gui::ViewContext::Visibility::Visible)
    );

    Gui::ViewInstance hiddenInstance(&viewProvider, &hiddenContext);
    Gui::ViewInstance visibleInstance(&viewProvider, &visibleContext);
    hiddenInstance.setRepresentation(new SoCube);
    visibleInstance.setRepresentation(new SoCube);

    SoGetBoundingBoxAction hiddenAction(SbViewportRegion(100, 100));
    hiddenAction.apply(hiddenInstance.getRoot());
    EXPECT_TRUE(hiddenAction.getBoundingBox().isEmpty());
    SoGetBoundingBoxAction visibleAction(SbViewportRegion(100, 100));
    visibleAction.apply(visibleInstance.getRoot());
    EXPECT_FALSE(visibleAction.getBoundingBox().isEmpty());
}

TEST_F(ViewProviderDocumentObjectTest, viewDefinitionAppliesAndCapturesContextOverrides)
{
    auto* definition = _doc->addObject("App::ViewDefinition", "SavedView");
    auto* viewDefinition = dynamic_cast<App::ViewDefinition*>(definition);
    ASSERT_NE(viewDefinition, nullptr);
    viewDefinition->ForcedHidden.setValues({_child});

    Gui::ViewContext context;
    ASSERT_TRUE(context.applyDefinition(viewDefinition));
    EXPECT_EQ(context.visibility(_child), Gui::ViewContext::Visibility::Hidden);

    viewDefinition->ForcedHidden.setValues({});
    ASSERT_TRUE(context.captureDefinition(viewDefinition));
    ASSERT_EQ(viewDefinition->ForcedHidden.getValues().size(), 1U);
    EXPECT_EQ(viewDefinition->ForcedHidden.getValues().front(), _child);
}

TEST_F(ViewProviderDocumentObjectTest, viewDefinitionCaptureFlattensLayerOverrides)
{
    auto* definition = static_cast<App::ViewDefinition*>(
        _doc->addObject("App::ViewDefinition", "SavedView")
    );

    Gui::ViewContext context;
    const auto olderLayer = context.pushLayer();
    ASSERT_TRUE(
        context.setVisibility(olderLayer, _child, Gui::ViewContext::Visibility::Hidden)
    );
    const auto newerLayer = context.pushLayer();
    ASSERT_TRUE(
        context.setVisibility(newerLayer, _child, Gui::ViewContext::Visibility::Visible)
    );
    ASSERT_EQ(context.visibility(_child), Gui::ViewContext::Visibility::Visible);

    ASSERT_TRUE(context.captureDefinition(definition));
    ASSERT_EQ(definition->ForcedVisible.getValues().size(), 1U);
    EXPECT_EQ(definition->ForcedVisible.getValues().front(), _child);
    EXPECT_TRUE(definition->ForcedHidden.getValues().empty());

    Gui::ViewContext restored;
    ASSERT_TRUE(restored.applyDefinition(definition));
    EXPECT_EQ(restored.visibility(_child), Gui::ViewContext::Visibility::Visible);
}

TEST_F(ViewProviderDocumentObjectTest, viewDefinitionCarriesPersistentClippingReferences)
{
    auto* definition = static_cast<App::ViewDefinition*>(
        _doc->addObject("App::ViewDefinition", "SavedView")
    );
    auto* clipping = static_cast<App::ClippingPlane*>(
        _doc->addObject("App::ClippingPlane", "SectionClip")
    );
    clipping->Offset.setValue(125.0);
    definition->ClippingPlanes.setValues({clipping});

    Gui::ViewContext context;
    ASSERT_TRUE(context.applyDefinition(definition));
    ASSERT_EQ(context.clippingPlanes().size(), 1U);
    EXPECT_EQ(context.clippingPlanes().front(), clipping);

    definition->ClippingPlanes.setValues({});
    ASSERT_TRUE(context.captureDefinition(definition));
    ASSERT_EQ(definition->ClippingPlanes.getValues().size(), 1U);
    EXPECT_EQ(definition->ClippingPlanes.getValues().front(), clipping);
}

TEST_F(ViewProviderDocumentObjectTest, viewDefinitionCarriesCameraAndReferenceFrame)
{
    auto* definition = static_cast<App::ViewDefinition*>(
        _doc->addObject("App::ViewDefinition", "SavedView")
    );
    definition->CameraCodec.setValue("CoinCamera");
    definition->CameraVersion.setValue(1);
    definition->CameraPayload.setValue("PerspectiveCamera { position 1 2 3 }");
    Base::Placement frame(Base::Vector3d(10.0, 20.0, 30.0), Base::Rotation());
    definition->ReferenceFrame.setValue(frame);

    Gui::ViewContext context;
    ASSERT_TRUE(context.applyDefinition(definition));
    EXPECT_EQ(context.cameraState(), definition->CameraPayload.getValue());
    EXPECT_TRUE(context.referenceFrame() == frame);

    context.setCameraState("OrthographicCamera { position 4 5 6 }");
    Base::Placement capturedFrame(Base::Vector3d(-1.0, -2.0, -3.0), Base::Rotation());
    context.setReferenceFrame(capturedFrame);
    ASSERT_TRUE(context.captureDefinition(definition));
    EXPECT_STREQ(definition->CameraPayload.getValue(), "OrthographicCamera { position 4 5 6 }");
    EXPECT_TRUE(definition->ReferenceFrame.getValue() == capturedFrame);
}
