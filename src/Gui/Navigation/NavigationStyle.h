// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <Gui/Navigation/NavigationStyleBase.h>
#include <Gui/Navigation/MappedNavigationStyle.h>
#include <Gui/Navigation/MayaGestureNavigationStyle.h>

// NOLINTBEGIN(cppcoreguidelines-avoid*, readability-avoid-const-params-in-decls)
namespace Gui
{

class GuiExport InventorNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    InventorNavigationStyle();
    ~InventorNavigationStyle() override;
    std::string userFriendlyName() const override;
    ClarifySelectionMode clarifySelectionMode() const override
    {
        return ClarifySelectionMode::Ctrl;
    }

protected:
    const NavigationProfile& profile() const override;
    void processStyleButtonEvent(EventContext& context) override;
    void adjustResolvedMode(EventContext& context) override;
    bool shouldPropagate(const EventContext& context) const override;
};

class GuiExport CADNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    CADNavigationStyle();
    ~CADNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
    void processStyleButtonEvent(EventContext& context) override;
    void adjustResolvedMode(EventContext& context) override;
};

class GuiExport RevitNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    RevitNavigationStyle();
    ~RevitNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
};

class GuiExport BlenderNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    BlenderNavigationStyle();
    ~BlenderNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
};

class GuiExport SolidWorksNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    SolidWorksNavigationStyle();
    ~SolidWorksNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
};

class GuiExport TouchpadNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    TouchpadNavigationStyle();
    ~TouchpadNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
    bool shouldForceRotationWhenButtonAdded(const EventContext& context) const override;
    bool shouldProcessMouseButtonEvent(const SoEvent* event) const override;
    void processStyleButtonEvent(EventContext& context) override;
    bool processStylePointerMotionEvent(EventContext& context) override;
    void adjustResolvedMode(EventContext& context) override;

private:
    SbBool blockPan {false};  // Used to block the first pan in a mouse movement to prevent big jumps
};

class GuiExport OpenCascadeNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    OpenCascadeNavigationStyle();
    ~OpenCascadeNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
    void processStyleButtonEvent(EventContext& context) override;
    bool processStylePointerMotionEvent(EventContext& context) override;
    void zoomByCursor(const SbVec2f& thispos, const SbVec2f& prevpos) override;
};

class GuiExport OpenSCADNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    OpenSCADNavigationStyle();
    ~OpenSCADNavigationStyle() override;
    ClarifySelectionMode clarifySelectionMode() const override
    {
        return ClarifySelectionMode::Ctrl;
    }

protected:
    const NavigationProfile& profile() const override;
    void processStyleButtonEvent(EventContext& context) override;
    bool processStylePointerMotionEvent(EventContext& context) override;
    void zoomByCursor(const SbVec2f& thispos, const SbVec2f& prevpos) override;
};

class GuiExport TinkerCADNavigationStyle: public MappedNavigationStyle
{
    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    TinkerCADNavigationStyle();
    ~TinkerCADNavigationStyle() override;

protected:
    const NavigationProfile& profile() const override;
    void processStyleButtonEvent(EventContext& context) override;
};

}  // namespace Gui
// NOLINTEND(cppcoreguidelines-avoid*, readability-avoid-const-params-in-decls)
