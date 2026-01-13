// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2009 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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

#include <map>
#include <vector>
#include <string>

#include <Base/Reader.h>
#include <Base/Tools.h>
#include <Base/UniqueNameManager.h>
#include <Base/Writer.h>

#include "DynamicProperty.h"
#include "Application.h"
#include "Property.h"
#include "PropertyContainer.h"


FC_LOG_LEVEL_INIT("Property", true, true)


using namespace App;


DynamicProperty::DynamicProperty() = default;

DynamicProperty::~DynamicProperty()
{
    clear();
}

void DynamicProperty::clear()
{
    for (auto& v : props) {
        delete v.property;
    }
    props.clear();
    propsByName.clear();
    propsByProperty.clear();
}

void DynamicProperty::getPropertyList(std::vector<Property*>& List) const
{
    for (auto& v : props) {
        List.push_back(v.property);
    }
}

void DynamicProperty::getPropertyNamedList(
    std::vector<std::pair<const char*, Property*>>& List) const
{
    for (auto& v : props) {
        List.emplace_back(v.getName(), v.property);
    }
}

void DynamicProperty::visitProperties(const std::function<void(Property*)>& visitor) const {
    for (auto& v : props) {
        visitor(v.property);
    }
}

void DynamicProperty::getPropertyMap(std::map<std::string,Property*>& Map) const
{
    for (auto& v : props) {
        Map[v.name] = v.property;
    }
}

Property* DynamicProperty::getDynamicPropertyByName(const char* name) const
{
    auto it = propsByName.find(name);
    if (it != propsByName.end()) {
        return it->second->property;
    }
    return nullptr;
}

std::vector<std::string> DynamicProperty::getDynamicPropertyNames() const
{
    std::vector<std::string> names;
    names.reserve(props.size());
    for (auto& v : props) {
        names.push_back(v.name);
    }
    return names;
}

short DynamicProperty::getPropertyType(const Property* prop) const
{
    return prop ? prop->getType() : 0;
}

short DynamicProperty::getPropertyType(const char* name) const
{
    auto it = propsByName.find(name);
    if (it != propsByName.end()) {
        const PropData& data = *it->second;
        short attr = data.attr;
        if (data.hidden) {
            attr |= Prop_Hidden;
        }
        if (data.readonly) {
            attr |= Prop_ReadOnly;
        }
        return attr;
    }
    return 0;
}

const char* DynamicProperty::getPropertyGroup(const Property* prop) const
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        return it->second->group.c_str();
    }
    return nullptr;
}

const char* DynamicProperty::getPropertyGroup(const char* name) const
{
    auto it = propsByName.find(name);
    if (it != propsByName.end()) {
        return it->second->group.c_str();
    }
    return nullptr;
}

const char* DynamicProperty::getPropertyDocumentation(const Property* prop) const
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        return it->second->doc.c_str();
    }
    return nullptr;
}

const char* DynamicProperty::getPropertyDocumentation(const char* name) const
{
    auto it = propsByName.find(name);
    if (it != propsByName.end()) {
        return it->second->doc.c_str();
    }
    return nullptr;
}

Property* DynamicProperty::addDynamicProperty(PropertyContainer& pc,
                                              std::string_view type,
                                              const char* cstrName,
                                              const char* group,
                                              const char* doc,
                                              short attr,
                                              bool ro,
                                              bool hidden)
{
    if (type.empty()) {
        type = "<null>";
    }

    std::string name {(cstrName && cstrName[0] != '\0') ? cstrName : ""};

    static ParameterGrp::handle hGrp =
        GetApplication().GetParameterGroupByPath("User parameter:BaseApp/Preferences/Document");
    if (hGrp->GetBool("AutoNameDynamicProperty", false)) {
        if (name.empty()) {
            name = type;
        }
        std::string uniqueName = getUniquePropertyName(pc, name.c_str());
        if (uniqueName != name) {
            FC_WARN(
                pc.getFullName() << " rename dynamic property from '" << name << "' to '"
                                 << uniqueName << "'"
            );
            name = uniqueName;
        }
    }
    else if (name.empty()) {
        name = "<null>";  // setting a bad name to trigger exception
    }

    auto prop = pc.getPropertyByName(name.c_str());
    if (prop && prop->getContainer() == &pc) {
        FC_THROWM(Base::NameError,
                  "Property " << pc.getFullName() << '.' << name << " already exists");
    }

    if (Base::Tools::getIdentifier(name) != name) {
        FC_THROWM(Base::NameError, "Invalid property name '" << name << "'");
    }

    Base::Type propType =
        Base::Type::getTypeIfDerivedFrom(type, App::Property::getClassTypeId(), true);
    if (propType.isBad()) {
        FC_THROWM(Base::TypeError,
                  "Invalid type " << type << " for property " << pc.getFullName() << '.' << name);
    }

    void* propInstance = propType.createInstance();
    if (!propInstance) {
        FC_THROWM(Base::RuntimeError,
                  "Failed to create property " << pc.getFullName() << '.' << name << " of type "
                                               << type);
    }

    Property* pcProperty = static_cast<Property*>(propInstance);

    auto inserted = props.emplace(props.end(), pcProperty, name.c_str(), nullptr, group, doc, attr, ro, hidden);
    propsByProperty.emplace(pcProperty, inserted);
    propsByName.emplace(inserted->getName(), inserted);

    pcProperty->setContainer(&pc);
    pcProperty->myName = inserted->name.c_str();

    if (ro) {
        attr |= Prop_ReadOnly;
    }
    if (hidden) {
        attr |= Prop_Hidden;
    }

    pcProperty->syncType(attr);
    pcProperty->StatusBits.set((size_t)Property::PropDynamic);

    GetApplication().signalAppendDynamicProperty(*pcProperty);

    return pcProperty;
}

bool DynamicProperty::addProperty(Property* prop)
{
    if (!prop || !prop->hasName()) {
        return false;
    }
    if (propsByName.find(prop->getName()) != propsByName.end()) {
        return false;
    }

    auto inserted = props.emplace(
        props.end(),
        prop,
        std::string(),
        prop->getName(),
        prop->getGroup(),
        prop->getDocumentation(),
        prop->getType(),
        false,
        false
    );
    propsByProperty.emplace(prop, inserted);
    propsByName.emplace(inserted->getName(), inserted);
    return true;
}

bool DynamicProperty::removeProperty(const Property* prop)
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        const auto listIt = it->second;
        auto nameIt = propsByName.find(listIt->getName());
        if (nameIt != propsByName.end()) {
            propsByName.erase(nameIt);
        }
        props.erase(listIt);
        propsByProperty.erase(it);
        return true;
    }
    return false;
}

bool DynamicProperty::removeDynamicProperty(const char* name)
{
    auto it = propsByName.find(name);
    if (it != propsByName.end()) {
        Property* prop = it->second->property;
        if (prop->testStatus(Property::LockDynamic)) {
            throw Base::RuntimeError("property is locked");
        }
        else if (!prop->testStatus(Property::PropDynamic)) {
            throw Base::RuntimeError("property is not dynamic");
        }
        GetApplication().signalRemoveDynamicProperty(*prop);

        // Handle possible recursive calls of removeDynamicProperty
        if (prop->myName) {
            Property::destroy(prop);
            auto propIt = propsByProperty.find(prop);
            if (propIt != propsByProperty.end()) {
                const auto listIt = propIt->second;
                auto nameIt = propsByName.find(listIt->getName());
                if (nameIt != propsByName.end()) {
                    propsByName.erase(nameIt);
                }
                props.erase(listIt);
                propsByProperty.erase(propIt);
            }
            // memory of myName has been freed
            prop->myName = nullptr;
        }
        return true;
    }

    return false;
}

std::string DynamicProperty::getUniquePropertyName(const PropertyContainer& pc, const char* Name) const
{
    std::string cleanName = Base::Tools::getIdentifier(Name);

    // We test if the property already exists by finding it, which is not much more expensive than
    // having a separate propertyExists(name) method. This avoids building the UniqueNameManager
    // (which could also tell if the name exists) except in the relatively rare condition of
    // the name already existing.
    if (pc.getPropertyByName(cleanName.c_str()) == nullptr) {
        return cleanName;
    }
    Base::UniqueNameManager names;
    // Build the index of existing names.
    pc.visitProperties([&](Property* prop) {
        names.addExactName(prop->getName());
    });
    return names.makeUniqueName(cleanName);
}

void DynamicProperty::save(const Property* prop, Base::Writer& writer) const
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        auto& data = *it->second;
        writer.Stream() << "\" group=\"" << Base::Persistence::encodeAttribute(data.group)
                        << "\" doc=\"" << Base::Persistence::encodeAttribute(data.doc)
                        << "\" attr=\"" << data.attr << "\" ro=\"" << data.readonly << "\" hide=\""
                        << data.hidden;
    }
}

Property* DynamicProperty::restore(PropertyContainer& pc,
                                   const char* PropName,
                                   const char* TypeName,
                                   const Base::XMLReader& reader)
{
    if (!reader.hasAttribute("group")) {
        return nullptr;
    }

    short attribute = 0;
    bool readonly = false, hidden = false;
    const char *group = nullptr, *doc = nullptr, *attr = nullptr, *ro = nullptr, *hide = nullptr;
    group = reader.getAttribute<const char*>("group");
    if (reader.hasAttribute("doc")) {
        doc = reader.getAttribute<const char*>("doc");
    }
    if (reader.hasAttribute("attr")) {
        attr = reader.getAttribute<const char*>("attr");
        if (attr) {
            std::istringstream str(attr);
            str >> attribute;
        }
    }
    if (reader.hasAttribute("ro")) {
        ro = reader.getAttribute<const char*>("ro");
        if (ro) {
            readonly = (ro[0] - 48) != 0;
        }
    }
    if (reader.hasAttribute("hide")) {
        hide = reader.getAttribute<const char*>("hide");
        if (hide) {
            hidden = (hide[0] - 48) != 0;
        }
    }

    return addDynamicProperty(pc, TypeName, PropName, group, doc, attribute, readonly, hidden);
}

DynamicProperty::PropData DynamicProperty::getDynamicPropertyData(const Property* prop) const
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        return *it->second;
    }
    return {};
}

bool DynamicProperty::changeDynamicProperty(const Property* prop,
                                            const char* group,
                                            const char* doc)
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it == propsByProperty.end()) {
        return false;
    }
    auto& data = *it->second;
    if (group) {
        data.group = group;
    }
    if (doc) {
        data.doc = doc;
    }
    return true;
}

bool DynamicProperty::renameDynamicProperty(Property* prop,
                                            const char* newName)
{
    auto propIt = propsByProperty.find(prop);
    if (propIt == propsByProperty.end()) {
        return false;
    }
    const PropData& data = *propIt->second;

    if (prop->testStatus(Property::LockDynamic)) {
        FC_THROWM(Base::RuntimeError, "Property " << prop->getName() << " is locked");
    }

    PropertyContainer* container = prop->getContainer();
    if (container->getPropertyByName(newName) != nullptr) {
        FC_THROWM(Base::NameError,
                  "Property " << container->getFullName() << '.' << newName << " already exists");
    }

    if (Base::Tools::getIdentifier(newName) != newName) {
        FC_THROWM(Base::NameError, "Invalid property name '" << newName << "'");
    }

    std::string oldName {data.getName()};
    auto& listIt = propIt->second;

    auto nameMapIt = propsByName.find(data.getName());
    if (nameMapIt == propsByName.end()) {
        FC_THROWM(Base::RuntimeError, "Property " << data.getName() << " not found in index");
    }
    propsByName.erase(nameMapIt);

    listIt->name = newName;
    listIt->pName = nullptr;
    // make sure that the property's name points to PropData.name that manages the memory.
    prop->myName = listIt->name.c_str();
    propsByName.emplace(listIt->getName(), listIt);

    GetApplication().signalRenameDynamicProperty(*prop, oldName.c_str());

    return true;
}

const char* DynamicProperty::getPropertyName(const Property* prop) const
{
    auto it = propsByProperty.find(const_cast<Property*>(prop));
    if (it != propsByProperty.end()) {
        return it->second->getName();
    }
    return nullptr;
}
