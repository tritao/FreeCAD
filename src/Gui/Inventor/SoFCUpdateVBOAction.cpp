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

#include "PreCompiled.h"

#ifndef _PreComp_
# include <Inventor/actions/SoSearchAction.h>
# include <Inventor/actions/SoGetBoundingBoxAction.h>
# include <Inventor/elements/SoComplexityElement.h>
# include <Inventor/elements/SoComplexityTypeElement.h>
# include <Inventor/elements/SoCoordinateElement.h>
# include <Inventor/elements/SoFontNameElement.h>
# include <Inventor/elements/SoFontSizeElement.h>
# include <Inventor/elements/SoModelMatrixElement.h>
# include <Inventor/elements/SoProfileCoordinateElement.h>
# include <Inventor/elements/SoProfileElement.h>
# include <Inventor/elements/SoProjectionMatrixElement.h>
# include <Inventor/elements/SoShapeStyleElement.h>
# include <Inventor/elements/SoSwitchElement.h>
# include <Inventor/elements/SoUnitsElement.h>
# include <Inventor/elements/SoViewingMatrixElement.h>
# include <Inventor/elements/SoViewportRegionElement.h>
# include <Inventor/elements/SoViewVolumeElement.h>
# include <Inventor/nodes/SoBaseColor.h>
# include <Inventor/nodes/SoCallback.h>
# include <Inventor/nodes/SoCamera.h>
# include <Inventor/nodes/SoComplexity.h>
# include <Inventor/nodes/SoCoordinate3.h>
# include <Inventor/nodes/SoCoordinate4.h>
# include <Inventor/nodes/SoCube.h>
# include <Inventor/nodes/SoDrawStyle.h>
# include <Inventor/nodes/SoFont.h>
# include <Inventor/nodes/SoIndexedLineSet.h>
# include <Inventor/nodes/SoIndexedFaceSet.h>
# include <Inventor/nodes/SoLightModel.h>
# include <Inventor/nodes/SoMatrixTransform.h>
# include <Inventor/nodes/SoPointSet.h>
# include <Inventor/nodes/SoProfile.h>
# include <Inventor/nodes/SoProfileCoordinate2.h>
# include <Inventor/nodes/SoProfileCoordinate3.h>
# include <Inventor/nodes/SoSeparator.h>
# include <Inventor/nodes/SoSwitch.h>
# include <Inventor/nodes/SoTransformation.h>
#endif

#include <Base/Profiler.h>

#include "SoFCUpdateVBOAction.h"
#include "SoFCSelection.h"


using namespace Gui;


SO_ACTION_SOURCE(SoUpdateVBOAction)

/**
 * The order of the defined SO_ACTION_ADD_METHOD statements is very important. First the base
 * classes and afterwards subclasses of them must be listed, otherwise the registered methods
 * of subclasses will be overridden. For more details see the thread in the Coin3d forum
 * https://www.coin3d.org/pipermail/coin-discuss/2004-May/004346.html.
 * This means that \c SoSwitch must be listed after \c SoGroup and \c SoFCSelection after
 * \c SoSeparator because both classes inherits the others.
 */
void SoUpdateVBOAction::initClass()
{
  SO_ACTION_INIT_CLASS(SoUpdateVBOAction,SoAction);

  SO_ENABLE(SoUpdateVBOAction, SoSwitchElement);

  SO_ACTION_ADD_METHOD(SoNode,nullAction);

  SO_ENABLE(SoUpdateVBOAction, SoModelMatrixElement);
  SO_ENABLE(SoUpdateVBOAction, SoProjectionMatrixElement);
  SO_ENABLE(SoUpdateVBOAction, SoCoordinateElement);
  SO_ENABLE(SoUpdateVBOAction, SoViewVolumeElement);
  SO_ENABLE(SoUpdateVBOAction, SoViewingMatrixElement);
  SO_ENABLE(SoUpdateVBOAction, SoViewportRegionElement);


  SO_ACTION_ADD_METHOD(SoCamera,callDoAction);
  SO_ACTION_ADD_METHOD(SoCoordinate3,callDoAction);
  SO_ACTION_ADD_METHOD(SoCoordinate4,callDoAction);
  SO_ACTION_ADD_METHOD(SoGroup,callDoAction);
  SO_ACTION_ADD_METHOD(SoSwitch,callDoAction);
  SO_ACTION_ADD_METHOD(SoShape,callDoAction);
  SO_ACTION_ADD_METHOD(SoIndexedFaceSet,callDoAction);

  SO_ACTION_ADD_METHOD(SoSeparator,callDoAction);
  SO_ACTION_ADD_METHOD(SoFCSelection,callDoAction);
}

SoUpdateVBOAction::SoUpdateVBOAction ()
{
  SO_ACTION_CONSTRUCTOR(SoUpdateVBOAction);
}

SoUpdateVBOAction::~SoUpdateVBOAction() = default;

void SoUpdateVBOAction::finish()
{
  atexit_cleanup();
}

void SoUpdateVBOAction::beginTraversal(SoNode *node)
{
  traverse(node);
}

void SoUpdateVBOAction::callDoAction(SoAction *action,SoNode *node)
{
  node->doAction(action);
}
