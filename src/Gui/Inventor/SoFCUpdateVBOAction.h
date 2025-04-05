/***************************************************************************
 *   Copyright (c) 2005 Jürgen Riegel <juergen.riegel@web.de>              *
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
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#ifndef _SoFCUpdateVBOAction_h
#define _SoFCUpdateVBOAction_h

#include <Inventor/actions/SoAction.h>
#include <FCGlobal.h>

namespace Gui {

/**
 * Helper class no notify nodes to update VBO.
 * @author Werner Mayer
 */
class GuiExport SoUpdateVBOAction : public SoAction
{
    SO_ACTION_HEADER(SoUpdateVBOAction);

public:
    SoUpdateVBOAction ();
    ~SoUpdateVBOAction() override;

    static void initClass();
    static void finish();

protected:
    void beginTraversal(SoNode *node) override;

private:
    static void callDoAction(SoAction *action,SoNode *node);
};

} // namespace Gui

#endif // _SoFCUpdateVBOAction_h
