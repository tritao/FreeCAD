// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

/******************************************************************************
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   License, or (at your option) any later version.                          *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#pragma once

#include <Gui/Navigation/NavigationEventView.h>
#include <Gui/Navigation/NavigationStyleBase.h>

#include <variant>
#include <vector>

namespace Gui
{

class GuiExport MayaGestureNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;

    TYPESYSTEM_HEADER_WITH_OVERRIDE();

public:
    MayaGestureNavigationStyle();
    ~MayaGestureNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;

protected:
    SbBool processSoEvent(const SoEvent* const event) override;
    int selectionMoveThreshold() const override;
    void zoomByCursor(const SbVec2f& position, const SbVec2f& previousPosition) override;

private:
    enum class State
    {
        Idle,
        AwaitingMove,
        Rotate,
        Pan,
        Zoom,
        Gesture,
    };

    enum class GestureKind
    {
        Pan,
        Pinch,
    };

    struct AwaitingMoveData
    {
        SbVec2s pressPosition;
        bool moveThresholdBroken = false;
        bool complexClick = false;
        std::vector<SoMouseButtonEvent> deferredEvents;
    };

    struct MotionData
    {
        SbVec2s previousPosition;
        float viewportAspect = 1.0F;
    };

    struct GestureData
    {
        GestureKind kind;
    };

    using StateData = std::variant<std::monostate, AwaitingMoveData, MotionData, GestureData>;

    struct EventContext
    {
        const NavigationEventView& event;
        const NavigationInputState& before;
        SbVec2f normalizedPosition;
        SbVec2f previousNormalizedPosition;
        float viewportAspect;
        bool editing;
    };

    struct EventOutcome
    {
        bool processed = false;
        bool propagated = false;
    };

    EventOutcome dispatchEvent(const EventContext& context);
    EventOutcome handleIdle(const EventContext& context);
    EventOutcome handleAwaitingMove(const EventContext& context);
    EventOutcome handleMotion(const EventContext& context);
    EventOutcome handleGesture(const EventContext& context);

    void enterAwaitingMove(const EventContext& context);
    void enterMotion(State state, const SoEvent* event);
    void enterGesture(GestureKind kind, const SoEvent* event);
    void leaveState();

    EventOutcome handleAwaitingMoveButton(const EventContext& context);
    EventOutcome handleAwaitingMoveMotion(const EventContext& context);
    EventOutcome handleAwaitingMoveGesture(const EventContext& context);
    EventOutcome handleMotionButton(const EventContext& context);
    EventOutcome handleMotionPointer(const EventContext& context);
    EventOutcome handleMotionGesture(const EventContext& context);

    void replayDeferredEvents();
    void clearDeferredEvents();
    bool hasDeferredEvents() const;
    void updateClickState(const NavigationInputState& before, const NavigationInputState& after);
    bool isContinuousMotionEvent(const NavigationEventView& event) const;
    static bool hasPrimaryButton(const NavigationInputState& input);
    static bool hasSecondaryButton(const NavigationInputState& input);

    int mouseMoveThreshold = 0;
    State state = State::Idle;
    StateData stateData;
};

}  // namespace Gui
