/***************************************************************************
 *   Copyright (c) 2025 WandererFan <wandererfan@gmail.com>                *
 *   Copyright (c) 2025 Benjamin Bræstrup Sayoc <benj5378@outlook.com>     *
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

#include <Base/Reader.h>
#include <Base/UuidTag.h>
#include <Base/Writer.h>

#include "Tag.h"

using namespace TechDraw;

// lint complains if tag is not initialized here.
Tag::Tag() :
    tag()
{
    createNewTag();
}

Base::UuidTag Tag::getTag() const
{
    return tag;
}

std::string Tag::getTagAsString() const
{
    return getTag().toString();
}

Base::UuidTag Tag::fromString(const std::string& tagString)
{
    return Base::UuidTag::fromString(tagString);
}

void Tag::setTag(const Base::UuidTag& newTag)
{
    tag = newTag;
}

void Tag::createNewTag()
{
    tag = Base::UuidTag::randomV4();
}

void Tag::Save(Base::Writer& writer) const
{
    writer.Stream() << writer.ind() << "<Tag value=\"" <<  getTagAsString() << "\"/>" << std::endl;
}

void Tag::Restore(Base::XMLReader& reader, std::string_view elementName)
{
    // Setting elementName is only for backwards compatibility!
    reader.readElement(elementName.data());
    std::string temp = reader.getAttribute<const char*>("value");
    tag = fromString(temp);
}
