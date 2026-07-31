// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <Gui/Navigation/NavigationStyleBase.h>
#include <Gui/Navigation/MappedNavigationStyle.h>

// NOLINTBEGIN(cppcoreguidelines-avoid*, readability-avoid-const-params-in-decls)
namespace Gui
{

class GuiExport InventorNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    InventorNavigationStyle();
    ~InventorNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;
    std::string userFriendlyName() const override;
    ClarifySelectionMode clarifySelectionMode() const override
    {
        return ClarifySelectionMode::Ctrl;
    }

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
};

class GuiExport CADNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    CADNavigationStyle();
    ~CADNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;

private:
    SbBool lockButton1 {false};
};

class GuiExport RevitNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    RevitNavigationStyle();
    ~RevitNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;

private:
    SbBool lockButton1 {false};
};

class GuiExport BlenderNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    BlenderNavigationStyle();
    ~BlenderNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;

private:
    SbBool lockButton1 {false};
};

class GuiExport SolidWorksNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    SolidWorksNavigationStyle();
    ~SolidWorksNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;

private:
    SbBool lockButton1 {false};
};

class GuiExport MayaGestureNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    MayaGestureNavigationStyle();
    ~MayaGestureNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    void zoomByCursor(const SbVec2f& thispos, const SbVec2f& prevpos) override;
    int selectionMoveThreshold() const override;

    SbBool processSoEvent(const SoEvent* const ev) override;

    SbVec2s mousedownPos;  // the position where some mouse button was pressed (local pixel coordinates).
    short mouseMoveThreshold;  // setting. Minimum move required to consider it a move (in pixels).
    bool mouseMoveThresholdBroken;  // a flag that the move threshold was surpassed since last mousedown.
    int mousedownConsumedCount;  // a flag for remembering that a mousedown of button1/button2 was
                                 // consumed.
    SoMouseButtonEvent mousedownConsumedEvents[5];  // the event that was consumed and is to be
                                                    // refired. 2 should be enough, but just for a
                                                    // case of the maximum 5 buttons...
    bool testMoveThreshold(const SbVec2s currentPos) const;

    bool thisClickIsComplex;  // a flag that becomes set when a complex clicking pattern is detected
                              // (i.e., two or more mouse buttons were down at the same time).
    bool inGesture;           // a flag that is used to filter out mouse events during gestures.
};

class GuiExport TouchpadNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    TouchpadNavigationStyle();
    ~TouchpadNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;

private:
    SbBool blockPan {false};  // Used to block the first pan in a mouse movement to prevent big jumps
};

class GuiExport OpenCascadeNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    OpenCascadeNavigationStyle();
    ~OpenCascadeNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
};

class GuiExport OpenSCADNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    OpenSCADNavigationStyle();
    ~OpenSCADNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;
    ClarifySelectionMode clarifySelectionMode() const override
    {
        return ClarifySelectionMode::Ctrl;
    }

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
};

class GuiExport TinkerCADNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    TinkerCADNavigationStyle();
    ~TinkerCADNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
};

}  // namespace Gui
// NOLINTEND(cppcoreguidelines-avoid*, readability-avoid-const-params-in-decls)
