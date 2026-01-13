// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2025 Werner Mayer <wmayer[at]users.sourceforge.net>     *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 **************************************************************************/

#include <QApplication>

#include <memory>

#include "Camera.h"
#include "SiemensNXNavigationStyle.h"
#include "View3DInventorViewer.h"

// NOLINTBEGIN(cppcoreguidelines-pro-type-static-cast-downcast,
//             cppcoreguidelines-avoid*,
//             readability-avoid-const-params-in-decls)
using namespace Gui;
using SC = NavigationStateChart;
using NS = SiemensNXNavigationStyle;

struct NS::NaviMachine: public NaviStateMachine
{
    explicit NaviMachine(NS& ns)
        : ns(ns)
    {
        state = std::make_unique<IdleState>(*this);
        state->onEnter(nullptr);
    }

    NS& ns;

	    void process_event(const SC::Event& ev) override
	    {
        if (!state) {
            state = std::make_unique<IdleState>(*this);
            state->onEnter(nullptr);
        }
        pending.reset();
        pendingEnterEvent = nullptr;
        state->react(ev);
        if (pending) {
            state = std::move(pending);
            state->onEnter(pendingEnterEvent);
        }
	    }

	public:
	    struct State
	    {
        explicit State(NaviMachine& machine)
            : machine(machine)
        {}
        virtual ~State() = default;

        virtual void onEnter(const SC::Event* /*ev*/) {}
        virtual void react(const SC::Event& ev) = 0;

	    protected:
	        NaviMachine& machine;
	    };

	private:
	    template<typename TState>
	    void requestTransit(const SC::Event* ev)
	    {
	        pending = std::make_unique<TState>(*this);
	        pendingEnterEvent = ev;
    }

    std::unique_ptr<State> state;
    std::unique_ptr<State> pending;
    const SC::Event* pendingEnterEvent {nullptr};

	    struct IdleState final : State
	    {
        using State::State;

        void onEnter(const SC::Event* /*ev*/) override
        {
            machine.ns.setViewingMode(NavigationStyle::IDLE);
        }

        void react(const SC::Event& ev) override
        {
            auto& ns = machine.ns;
            switch (ns.getViewingMode()) {
                case NavigationStyle::SEEK_WAIT_MODE: {
                    if (ev.isPress(SoMouseButtonEvent::BUTTON1)) {
                        ns.seekToPoint(ev.inventor_event->getPosition());
                        ns.setViewingMode(NavigationStyle::SEEK_MODE);
                        ev.flags->processed = true;
                        machine.requestTransit<AwaitingReleaseState>(&ev);
                        return;
                    }
                    break;
                }
                case NavigationStyle::SPINNING:
                case NavigationStyle::SEEK_MODE: {
                    if (!ev.flags->processed) {
                        if (ev.isMouseButtonEvent()) {
                            ev.flags->processed = true;
                            machine.requestTransit<AwaitingReleaseState>(&ev);
                            return;
                        }
                        else if (ev.isKeyboardEvent() || ev.isMotion3Event()) {
                            ns.setViewingMode(NavigationStyle::IDLE);
                        }
                    }

                    break;
                }
                case NavigationStyle::BOXZOOM:
                    return;
            }

            // right-click
            if (ev.isRelease(SoMouseButtonEvent::BUTTON2) && ev.mbstate() == 0 && !ns.viewer->isEditing()
                && ns.isPopupMenuEnabled()) {
                ns.openPopupMenu(ev.inventor_event->getPosition());
            }

            if (ev.isPress(SoMouseButtonEvent::BUTTON3)) {
                if (ev.isDownShift()) {
                    ev.flags->processed = true;
                    machine.requestTransit<PanState>(&ev);
                    return;
                }

                if (ev.isDownButton(SC::Event::BUTTON3DOWN)) {
                    ev.flags->processed = true;
                    machine.requestTransit<AwaitingMoveState>(&ev);
                    return;
                }
            }

            // Use processClickEvent()

            // Implement selection callback
            // if (ev.isLocation2Event() && ev.isDownButton1()) {
            //    ev.flags->processed = true;
            //    machine.transit<SelectionState>(&ev);
            // }
        }
    };

    struct AwaitingReleaseState final : State
    {
        using State::State;

        void react(const SC::Event& /*ev*/) override {}
    };

    struct InteractState final : State
    {
        using State::State;

        void onEnter(const SC::Event* /*ev*/) override
        {
            machine.ns.setViewingMode(NavigationStyle::INTERACT);
        }

        void react(const SC::Event& /*ev*/) override {}
    };

    struct AwaitingMoveState final : State
    {
        using State::State;

        void onEnter(const SC::Event* ev) override
        {
            auto& ns = machine.ns;
            ns.setViewingMode(NavigationStyle::DRAGGING);

            if (ev) {
                this->base_pos = ev->inventor_event->getPosition();
                this->since = ev->inventor_event->getTime();
            }
        }

        void react(const SC::Event& ev) override
        {
            // this state consumes all mouse events.
            ev.flags->processed = ev.isMouseButtonEvent() || ev.isLocation2Event();

            if (ev.isLocation2Event()) {
                machine.requestTransit<RotateState>(&ev);
                return;
            }

            // right-click
            if (ev.isPress(SoMouseButtonEvent::BUTTON2) && ev.isDownButton3()) {
                machine.requestTransit<PanState>(&ev);
                return;
            }

            if (ev.isKeyPress(SoKeyboardEvent::LEFT_SHIFT)) {
                ev.flags->processed = true;
                machine.requestTransit<PanState>(&ev);
                return;
            }

            // left-click
            if (ev.isPress(SoMouseButtonEvent::BUTTON1) && ev.isDownButton3()) {
                machine.requestTransit<ZoomState>(&ev);
                return;
            }

            if (ev.isKeyPress(SoKeyboardEvent::LEFT_CONTROL)) {
                ev.flags->processed = true;
                machine.requestTransit<ZoomState>(&ev);
                return;
            }

            // middle-click
            if (ev.isRelease(SoMouseButtonEvent::BUTTON3) && ev.isDownNoButton()) {
                auto& ns = machine.ns;
                SbTime tmp = (ev.inventor_event->getTime() - this->since);
                double dci = QApplication::doubleClickInterval() / 1000.0;

                // is this a simple middle click?
                if (tmp.getValue() < dci) {
                    ev.flags->processed = true;
                    SbVec2s pos = ev.inventor_event->getPosition();
                    ns.lookAtPoint(pos);
                }
                machine.requestTransit<IdleState>(&ev);
            }
        }

    private:
        SbVec2s base_pos;
        SbTime since;
    };

    struct RotateState final : State
    {
        using State::State;

        void onEnter(const SC::Event* ev) override
        {
            auto& ns = machine.ns;
            if (!ev) {
                return;
            }
            const auto inventorEvent = ev->inventor_event;
            ns.saveCursorPosition(inventorEvent);
            ns.setViewingMode(NavigationStyle::DRAGGING);
            this->base_pos = inventorEvent->getPosition();
        }

        void react(const SC::Event& ev) override
        {
            auto& ns = machine.ns;

            if (ev.isLocation2Event()) {
                ns.addToLog(ev.inventor_event->getPosition(), ev.inventor_event->getTime());
                const SbVec2s pos = ev.inventor_event->getPosition();
                const SbVec2f posn = ns.normalizePixelPos(pos);
                ns.spin(posn);
                ns.moveCursorPosition();
                ev.flags->processed = true;
            }

            // right-click
            if (ev.isPress(SoMouseButtonEvent::BUTTON2) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<PanState>(&ev);
                return;
            }

            if (ev.isKeyPress(SoKeyboardEvent::LEFT_SHIFT)) {
                ev.flags->processed = true;
                machine.requestTransit<PanState>(&ev);
                return;
            }

            // left-click
            if (ev.isPress(SoMouseButtonEvent::BUTTON1) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<ZoomState>(&ev);
                return;
            }

            if (ev.isKeyPress(SoKeyboardEvent::LEFT_CONTROL)) {
                ev.flags->processed = true;
                machine.requestTransit<ZoomState>(&ev);
                return;
            }

            if (ev.isRelease(SoMouseButtonEvent::BUTTON3) && ev.isDownNoButton()) {
                ev.flags->processed = true;
                machine.requestTransit<IdleState>(&ev);
            }
        }

    private:
        SbVec2s base_pos;
    };

    struct PanState final : State
    {
        using State::State;

        void onEnter(const SC::Event* ev) override
        {
            auto& ns = machine.ns;
            ns.setViewingMode(NavigationStyle::PANNING);
            if (ev) {
                this->base_pos = ev->inventor_event->getPosition();
                ns.centerTime = ev->inventor_event->getTime();
            }
            this->ratio = ns.viewer->getSoRenderManager()->getViewportRegion().getViewportAspectRatio();
            ns.setupPanningPlane(ns.getCamera());
        }

        void react(const SC::Event& ev) override
        {
            auto& ns = machine.ns;

            if (ev.isLocation2Event()) {
                ev.flags->processed = true;
                SbVec2s pos = ev.inventor_event->getPosition();
                ns.panCamera(
                    ns.viewer->getSoRenderManager()->getCamera(),
                    this->ratio,
                    ns.panningplane,
                    ns.normalizePixelPos(pos),
                    ns.normalizePixelPos(this->base_pos)
                );
                this->base_pos = pos;
            }

            if (ev.isRelease(SoMouseButtonEvent::BUTTON2) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<RotateState>(&ev);
                return;
            }

            if (ev.isKeyRelease(SoKeyboardEvent::LEFT_SHIFT) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<RotateState>(&ev);
                return;
            }

            if (ev.isRelease(SoMouseButtonEvent::BUTTON3)) {
                ev.flags->processed = true;
                machine.requestTransit<IdleState>(&ev);
            }
        }

    private:
        SbVec2s base_pos;
        float ratio {1.0F};
    };

    struct ZoomState final : State
    {
        using State::State;

        void onEnter(const SC::Event* ev) override
        {
            auto& ns = machine.ns;
            ns.setViewingMode(NavigationStyle::ZOOMING);
            if (ev) {
                this->base_pos = ev->inventor_event->getPosition();
            }
        }

        void react(const SC::Event& ev) override
        {
            auto& ns = machine.ns;

            if (ev.isLocation2Event()) {
                ev.flags->processed = true;
                SbVec2s pos = ev.inventor_event->getPosition();
                ns.zoomByCursor(ns.normalizePixelPos(pos), ns.normalizePixelPos(this->base_pos));
                this->base_pos = pos;
            }

            if (ev.isRelease(SoMouseButtonEvent::BUTTON1) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<RotateState>(&ev);
                return;
            }

            if (ev.isKeyRelease(SoKeyboardEvent::LEFT_CONTROL) && ev.isDownButton3()) {
                ev.flags->processed = true;
                machine.requestTransit<RotateState>(&ev);
                return;
            }

            if (ev.isRelease(SoMouseButtonEvent::BUTTON3)) {
                ev.flags->processed = true;
                machine.requestTransit<IdleState>(&ev);
            }
        }

    private:
        SbVec2s base_pos;
    };

    struct SelectionState final : State
    {
        using State::State;

        void onEnter(const SC::Event* ev) override
        {
            auto& ns = machine.ns;
            if (!ev) {
                return;
            }

            ns.setViewingMode(NavigationStyle::BOXZOOM);
            ns.startSelection(NavigationStyle::Rubberband);
            fakeLeftButtonDown(ev->inventor_event->getPosition());
        }

        void react(const SC::Event& ev) override
        {
            // This isn't called while selection mode is active
            machine.requestTransit<IdleState>(&ev);
        }

        void fakeLeftButtonDown(const SbVec2s& pos)
        {
            SoMouseButtonEvent mbe;
            mbe.setButton(SoMouseButtonEvent::BUTTON1);
            mbe.setState(SoMouseButtonEvent::DOWN);
            mbe.setPosition(pos);

            machine.ns.processEvent(&mbe);
        }
    };
};

// ----------------------------------------------------------------------------------

/* TRANSLATOR Gui::SiemensNXNavigationStyle */

TYPESYSTEM_SOURCE(Gui::SiemensNXNavigationStyle, Gui::UserNavigationStyle)

SiemensNXNavigationStyle::SiemensNXNavigationStyle()
{
    naviMachine.reset(new NaviMachine(*this));
}

SiemensNXNavigationStyle::~SiemensNXNavigationStyle()
{}

const char* SiemensNXNavigationStyle::mouseButtons(ViewerMode mode)
{
    switch (mode) {
        case NavigationStyle::SELECTION:
            return QT_TR_NOOP("Press left mouse button");
        case NavigationStyle::PANNING:
            return QT_TR_NOOP("Press middle+right click");
        case NavigationStyle::DRAGGING:
            return QT_TR_NOOP("Press middle mouse button");
        case NavigationStyle::ZOOMING:
            return QT_TR_NOOP("Scroll mouse wheel");
        default:
            return "No description";
    }
}

std::string SiemensNXNavigationStyle::userFriendlyName() const
{
    return {"Siemens NX"};
}

SbBool SiemensNXNavigationStyle::processKeyboardEvent(const SoKeyboardEvent* const event)
{
    // See https://forum.freecad.org/viewtopic.php?t=96459
    // Isometric view: Home key button
    // Trimetric view: End key button
    // Fit all: CTRL+F
    // Normal view: F8
    switch (event->getKey()) {
        case SoKeyboardEvent::F:
            if (event->wasCtrlDown()) {
                viewer->viewAll();
                return true;
            }
            break;
        case SoKeyboardEvent::HOME: {
            viewer->setCameraOrientation(Camera::rotation(Camera::Isometric));
            return true;
        }
        case SoKeyboardEvent::END: {
            viewer->setCameraOrientation(Camera::rotation(Camera::Trimetric));
            return true;
        }
        case SoKeyboardEvent::F8: {
            viewer->setCameraOrientation(Camera::rotation(Camera::Top));
            return true;
        }
        default:
            break;
    }

    return inherited::processKeyboardEvent(event);
}

// NOLINTEND(cppcoreguidelines-pro-type-static-cast-downcast,
//           cppcoreguidelines-avoid*,
//           readability-avoid-const-params-in-decls)
