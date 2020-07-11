/***************************************************************************
 *   (c) Jürgen Riegel (juergen.riegel@web.de) 2002                        *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Library General Public License (LGPL)   *
 *   as published by the Free Software Foundation; either version 2 of     *
 *   the License, or (at your option) any later version.                   *
 *   for detail see the LICENCE text file.                                 *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful,            *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with FreeCAD; if not, write to the Free Software        *
 *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
 *   USA                                                                   *
 *                                                                         *
 *   Juergen Riegel 2002                                                   *
 ***************************************************************************/


#include "PreCompiled.h"

#ifndef _PreComp_
# include <iostream>
# include <assert.h>
#endif

#ifdef BUILD_QT
#include <QAtomicInt>
#endif

#include "Handle.h"
#include "Exception.h"

using namespace Base;

//**************************************************************************
// Construction/Destruction

Handled::Handled()
#ifdef BUILD_QT
  : _lRefCount(new QAtomicInt(0))
#else
  : _lRefCount(0)
#endif
{
}

Handled::~Handled()
{
#ifdef BUILD_QT
    if ((int)(*_lRefCount) != 0)
        std::cerr << "Reference counter of deleted object is not zero!!!!!" << std::endl;
    delete _lRefCount;
#else
    if (_lRefCount.load() != 0)
        std::cerr << "Reference counter of deleted object is not zero!!!!!" << std::endl;
#endif
}

void Handled::ref() const
{
#ifdef BUILD_QT
    _lRefCount->ref();
#else
    _lRefCount++;
#endif
}

void Handled::unref() const
{
#ifdef BUILD_QT
    assert(*_lRefCount > 0);
    if (!_lRefCount->deref()) {
        delete this;
    }
#else
    assert(_lRefCount.load() > 0);
    _lRefCount--;
    if (!_lRefCount.load()) {
        delete this;
    }
#endif
}

int Handled::getRefCount(void) const
{
#ifdef BUILD_QT
    return (int)(*_lRefCount);
#else
    return _lRefCount.load();
#endif
}

const Handled& Handled::operator = (const Handled&)
{
    // we must not assign _lRefCount
    return *this;
}
