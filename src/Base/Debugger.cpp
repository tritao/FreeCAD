/***************************************************************************
 *   Copyright (c) 2012 Werner Mayer <wmayer[at]users.sourceforge.net>     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 51 Franklin Street,      *
 *   Fifth Floor, Boston, MA  02110-1301, USA                              *
 *                                                                         *
 ***************************************************************************/


#include "PreCompiled.h"
#ifndef _PreComp_
#ifdef BUILD_QT
# include <QCoreApplication>
# include <QEvent>
#endif
#endif

#include "Debugger.h"
#include "Console.h"

using namespace Base;

#ifdef BUILD_QT
Debugger::Debugger(QObject* parent)
  : QObject(parent), isAttached(false)
#else
Debugger::Debugger(void* parent)
    : isAttached(false)
#endif
{
}

Debugger::~Debugger()
{
}

void Debugger::attach()
{
#ifdef BUILD_QT
    QCoreApplication::instance()->installEventFilter(this);
#endif
    isAttached = true;
}

void Debugger::detach()
{
#ifdef BUILD_QT
    QCoreApplication::instance()->removeEventFilter(this);
#endif
    isAttached = false;
}

#ifdef BUILD_QT
bool Debugger::eventFilter(QObject*, QEvent* event)
{
    if (event->type() == QEvent::KeyPress) {
        if (loop.isRunning()) {
            loop.quit();
            return true;
        }
    }

    return false;
}
#else
bool Debugger::eventFilter(void*, void* event)
{
    return false;
}
#endif

int Debugger::exec()
{
    if (isAttached)
        Base::Console().Message("TO CONTINUE PRESS ANY KEY...\n");
#ifdef BUILD_QT
    return loop.exec();
#else
    assert(0 && "Debugger::exec() not implemented for this platform!");
    return 0;
#endif
}

void Debugger::quit()
{
#ifdef BUILD_QT
    loop.quit();
#endif
}

#ifdef BUILD_QT
#include "moc_Debugger.cpp"
#endif
