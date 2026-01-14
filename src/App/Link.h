// SPDX-License-Identifier: LGPL-2.1-or-later

/****************************************************************************
 *   Copyright (c) 2017 Zheng Lei (realthunder) <realthunder.dev@gmail.com> *
 *                                                                          *
 *   This file is part of the FreeCAD CAx development system.               *
 *                                                                          *
 *   This library is free software; you can redistribute it and/or          *
 *   modify it under the terms of the GNU Library General Public            *
 *   License as published by the Free Software Foundation; either           *
 *   version 2 of the License, or (at your option) any later version.       *
 *                                                                          *
 *   This library  is distributed in the hope that it will be useful,       *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of         *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          *
 *   GNU Library General Public License for more details.                   *
 *                                                                          *
 *   You should have received a copy of the GNU Library General Public      *
 *   License along with this library; see the file COPYING.LIB. If not,     *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,          *
 *   Suite 330, Boston, MA  02111-1307, USA                                 *
 *                                                                          *
 ****************************************************************************/

#ifndef APP_LINK_H
#define APP_LINK_H

#include <vector>
#include <unordered_set>

#include <Base/Parameter.h>
#include <Base/Bitmask.h>
#include "DocumentObject.h"
#include "DocumentObjectExtension.h"
#include "FeaturePython.h"
#include "GroupExtension.h"
#include "PropertyLinks.h"

#define LINK_THROW(_type, _msg)                                                                    \
    do {                                                                                           \
        if (FC_LOG_INSTANCE.isEnabled(FC_LOGLEVEL_LOG))                                            \
            FC_ERR(_msg);                                                                          \
        throw _type(_msg);                                                                         \
    } while (0)

namespace App
{

class AppExport LinkBaseExtension: public App::DocumentObjectExtension
{
    EXTENSION_PROPERTY_HEADER_WITH_OVERRIDE(App::LinkExtension);
    using inherited = App::DocumentObjectExtension;

public:
    LinkBaseExtension();
    ~LinkBaseExtension() override = default;

    PropertyBool _LinkTouched;
    PropertyInteger _LinkOwner;
    PropertyLinkList _ChildCache;  // cache for plain group expansion

    enum
    {
        LinkModeNone,
        LinkModeAutoDelete,
        LinkModeAutoLink,
        LinkModeAutoUnlink,
    };

    /** \name Parameter definition
     *
     * Parameter definition (Name, Type, Property Type, Default, Document,
     * Derived Property Type, App::PropertyType).
     */
    //@{

#define LINK_PARAM_LINK_PLACEMENT(_apply, _data)                                                   \
    _apply(_data,                                                                                  \
           LinkPlacement,                                                                          \
           Base::Placement,                                                                        \
           App::PropertyPlacement,                                                                 \
           (Base::Placement()),                                                                    \
           "Link placement",                                                                       \
           App::PropertyPlacement,                                                                 \
           App::Prop_None)

#define LINK_PARAM_PLACEMENT(_apply, _data)                                                        \
    _apply(_data,                                                                                  \
           Placement,                                                                              \
           Base::Placement,                                                                        \
           App::PropertyPlacement,                                                                 \
           (Base::Placement()),                                                                    \
           "Alias to LinkPlacement to make the link object compatibale with other objects",        \
           App::PropertyPlacement,                                                                 \
           App::Prop_None)

#define LINK_PARAM_OBJECT(_apply, _data)                                                           \
    _apply(_data,                                                                                  \
           LinkedObject,                                                                           \
           App::DocumentObject*,                                                                   \
           App::PropertyLink,                                                                      \
           (0),                                                                                    \
           "Linked object",                                                                        \
           App::PropertyXLink,                                                                     \
           App::Prop_None)

#define LINK_PARAM_TRANSFORM(_apply, _data)                                                        \
    _apply(_data,                                                                                  \
           LinkTransform,                                                                          \
           bool,                                                                                   \
           App::PropertyBool,                                                                      \
           (false),                                                                                \
           "Set to false to override linked object's placement",                                   \
           App::PropertyBool,                                                                      \
           App::Prop_None)

#define LINK_PARAM_CLAIM_CHILD(_apply, _data)                                                      \
    _apply(_data,                                                                                  \
           LinkClaimChild,                                                                         \
           bool,                                                                                   \
           App::PropertyBool,                                                                      \
           (false),                                                                                \
           "Claim the linked object as a child",                                                   \
           App::PropertyBool,                                                                      \
           App::Prop_None)

#define LINK_PARAM_COPY_ON_CHANGE(_apply, _data)                                                   \
    _apply(_data,                                                                                  \
           LinkCopyOnChange,                                                                       \
           long,                                                                                   \
           App::PropertyEnumeration,                                                               \
           ((long)0),                                                                              \
           "Disabled: disable copy on change\n"                                                    \
           "Enabled: enable copy linked object on change of any of its properties marked as "      \
           "CopyOnChange\n"                                                                        \
           "Owned: indicate the linked object has been copied and is own owned by the link. And " \
           "the\n"                                                                                 \
           "       the link will try to sync any change of the original linked object back to "    \
           "the copy.",                                                                            \
           App::PropertyEnumeration,                                                               \
           App::Prop_None)

#define LINK_PARAM_COPY_ON_CHANGE_SOURCE(_apply, _data)                                            \
    _apply(_data,                                                                                  \
           LinkCopyOnChangeSource,                                                                 \
           App::DocumentObject*,                                                                   \
           App::PropertyLink,                                                                      \
           (0),                                                                                    \
           "The copy on change source object",                                                     \
           App::PropertyXLink,                                                                     \
           App::Prop_None)

#define LINK_PARAM_COPY_ON_CHANGE_GROUP(_apply, _data)                                             \
    _apply(_data,                                                                                  \
           LinkCopyOnChangeGroup,                                                                  \
           App::DocumentObject*,                                                                   \
           App::PropertyLink,                                                                      \
           (0),                                                                                    \
           "Linked to a internal group object for holding on change copies",                       \
           App::PropertyLink,                                                                      \
           App::Prop_None)

#define LINK_PARAM_COPY_ON_CHANGE_TOUCHED(_apply, _data)                                           \
    _apply(_data,                                                                                  \
           LinkCopyOnChangeTouched,                                                                \
           bool,                                                                                   \
           App::PropertyBool,                                                                      \
           (0),                                                                                    \
           "Indicating the copy on change source object has been changed",                         \
           App::PropertyBool,                                                                      \
           App::Prop_None)

#define LINK_PARAM_SCALE(_apply, _data)                                                            \
    _apply(_data, Scale, double, App::PropertyFloat, (1.0), "Scale factor", App::PropertyFloat, App::Prop_None)

#define LINK_PARAM_SCALE_VECTOR(_apply, _data)                                                     \
    _apply(_data,                                                                                  \
           ScaleVector,                                                                            \
           Base::Vector3d,                                                                         \
           App::PropertyVector,                                                                    \
           (Base::Vector3d(1, 1, 1)),                                                              \
           "Scale factors",                                                                        \
           App::PropertyVector,                                                                    \
           App::Prop_Hidden)

#define LINK_PARAM_PLACEMENTS(_apply, _data)                                                       \
    _apply(_data,                                                                                  \
           PlacementList,                                                                          \
           std::vector<Base::Placement>,                                                           \
           App::PropertyPlacementList,                                                             \
           (std::vector<Base::Placement>()),                                                       \
           "The placement for each link element",                                                  \
           App::PropertyPlacementList,                                                             \
           App::Prop_None)

#define LINK_PARAM_SCALES(_apply, _data)                                                           \
    _apply(_data,                                                                                  \
           ScaleList,                                                                              \
           std::vector<Base::Vector3d>,                                                            \
           App::PropertyVectorList,                                                                \
           (std::vector<Base::Vector3d>()),                                                        \
           "The scale factors for each link element",                                              \
           App::PropertyVectorList,                                                                \
           App::Prop_None)

#define LINK_PARAM_VISIBILITIES(_apply, _data)                                                     \
    _apply(_data,                                                                                  \
           VisibilityList,                                                                         \
           std::vector<bool>,                                                                      \
           App::PropertyBoolList,                                                                  \
           (std::vector<bool>()),                                                                  \
           "The visibility state of each link element",                                            \
           App::PropertyBoolList,                                                                  \
           App::Prop_None)

#define LINK_PARAM_COUNT(_apply, _data)                                                            \
    _apply(_data,                                                                                  \
           ElementCount,                                                                           \
           int,                                                                                    \
           App::PropertyInteger,                                                                   \
           (0),                                                                                    \
           "Link element count",                                                                   \
           App::PropertyIntegerConstraint,                                                         \
           App::Prop_None)

#define LINK_PARAM_ELEMENTS(_apply, _data)                                                         \
    _apply(_data,                                                                                  \
           ElementList,                                                                            \
           std::vector<App::DocumentObject*>,                                                      \
           App::PropertyLinkList,                                                                  \
           (std::vector<App::DocumentObject*>()),                                                  \
           "The link element object list",                                                         \
           App::PropertyLinkList,                                                                  \
           App::Prop_None)

#define LINK_PARAM_SHOW_ELEMENT(_apply, _data)                                                     \
    _apply(_data, ShowElement, bool, App::PropertyBool, (true), "Enable link element list", App::PropertyBool, App::Prop_None)

#define LINK_PARAM_MODE(_apply, _data)                                                             \
    _apply(_data,                                                                                  \
           LinkMode,                                                                               \
           long,                                                                                   \
           App::PropertyEnumeration,                                                               \
           ((long)0),                                                                              \
           "Link group mode",                                                                      \
           App::PropertyEnumeration,                                                               \
           App::Prop_None)

#define LINK_PARAM_LINK_EXECUTE(_apply, _data)                                                     \
    _apply(_data,                                                                                  \
           LinkExecute,                                                                            \
           const char*,                                                                            \
           App::PropertyString,                                                                    \
           (""),                                                                                   \
           "Link execute function. Default to 'appLinkExecute'. 'None' to disable.",               \
           App::PropertyString,                                                                    \
           App::Prop_None)

#define LINK_PARAM_COLORED_ELEMENTS(_apply, _data)                                                 \
    _apply(_data,                                                                                  \
           ColoredElements,                                                                        \
           App::DocumentObject*,                                                                   \
           App::PropertyLinkSubHidden,                                                             \
           (0),                                                                                    \
           "Link colored elements",                                                                \
           App::PropertyLinkSubHidden,                                                             \
           App::Prop_Hidden)
    //@}

#define LINK_PARAMS(_apply, _data)                                                                 \
    LINK_PARAM_PLACEMENT(_apply, _data)                                                            \
    LINK_PARAM_LINK_PLACEMENT(_apply, _data)                                                       \
    LINK_PARAM_OBJECT(_apply, _data)                                                               \
    LINK_PARAM_CLAIM_CHILD(_apply, _data)                                                          \
    LINK_PARAM_TRANSFORM(_apply, _data)                                                            \
    LINK_PARAM_SCALE(_apply, _data)                                                                \
    LINK_PARAM_SCALE_VECTOR(_apply, _data)                                                         \
    LINK_PARAM_PLACEMENTS(_apply, _data)                                                           \
    LINK_PARAM_SCALES(_apply, _data)                                                               \
    LINK_PARAM_VISIBILITIES(_apply, _data)                                                         \
    LINK_PARAM_COUNT(_apply, _data)                                                                \
    LINK_PARAM_ELEMENTS(_apply, _data)                                                             \
    LINK_PARAM_SHOW_ELEMENT(_apply, _data)                                                         \
    LINK_PARAM_MODE(_apply, _data)                                                                 \
    LINK_PARAM_LINK_EXECUTE(_apply, _data)                                                         \
    LINK_PARAM_COLORED_ELEMENTS(_apply, _data)                                                     \
    LINK_PARAM_COPY_ON_CHANGE(_apply, _data)                                                       \
    LINK_PARAM_COPY_ON_CHANGE_SOURCE(_apply, _data)                                                \
    LINK_PARAM_COPY_ON_CHANGE_GROUP(_apply, _data)                                                 \
    LINK_PARAM_COPY_ON_CHANGE_TOUCHED(_apply, _data)

    enum PropIndex
    {
#define LINK_PINDEX_DEFINE(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype) Prop##_name,

        // defines Prop##Name enumeration value
        LINK_PARAMS(LINK_PINDEX_DEFINE, _) PropMax
    };

    virtual void setProperty(int idx, Property* prop);
    Property* getProperty(int idx);
    Property* getProperty(const char*);

    struct PropInfo
    {
        int index;
        const char* name;
        Base::Type type;
        const char* doc;

        PropInfo(int index, const char* name, Base::Type type, const char* doc)
            : index(index)
            , name(name)
            , type(type)
            , doc(doc)
        {}

        PropInfo()
            : index(0)
            , name(nullptr)
            , doc(nullptr)
        {}
    };

#define LINK_PROP_INFO(_var, _name, _type, _ptype, _def, _doc, _dtype, _atype)                     \
    _var.push_back(PropInfo(Prop##_name, #_name, _ptype::getClassTypeId(), _doc));

    virtual const std::vector<PropInfo>& getPropertyInfo() const;

    using PropInfoMap = std::map<std::string, PropInfo>;
    virtual const PropInfoMap& getPropertyInfoMap() const;

    enum LinkCopyOnChangeType
    {
        CopyOnChangeDisabled = 0,
        CopyOnChangeEnabled = 1,
        CopyOnChangeOwned = 2,
        CopyOnChangeTracking = 3
    };

#define LINK_PROP_GET(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype)                     \
    _type get##_name##Value() const                                                                \
    {                                                                                              \
        auto prop = props[Prop##_name];                                                            \
        if (!prop)                                                                                 \
            return _def;                                                                           \
        return static_cast<const _ptype*>(prop)->getValue();                                       \
    }                                                                                              \
    const _ptype* get##_name##Property() const                                                     \
    {                                                                                              \
        auto prop = props[Prop##_name];                                                            \
        return static_cast<const _ptype*>(prop);                                                   \
    }                                                                                              \
    _ptype* get##_name##Property()                                                                 \
    {                                                                                              \
        auto prop = props[Prop##_name];                                                            \
        return static_cast<_ptype*>(prop);                                                         \
    }

    // defines get##Name##Property() and get##Name##Value() accessor
    LINK_PARAMS(LINK_PROP_GET, _)

    PropertyLinkList* _getElementListProperty() const;
    const std::vector<App::DocumentObject*>& _getElementListValue() const;

    PropertyBool* _getShowElementProperty() const;
    bool _getShowElementValue() const;

    PropertyInteger* _getElementCountProperty() const;
    int _getElementCountValue() const;

    std::vector<DocumentObject*> getLinkedChildren(bool filter = true) const;

    const char* flattenSubname(const char* subname) const;
    void expandSubname(std::string& subname) const;

    DocumentObject* getLink(int depth = 0) const;

    Base::Matrix4D getTransform(bool transform) const;
    Base::Vector3d getScaleVector() const;

    App::GroupExtension* linkedPlainGroup() const;

    bool linkTransform() const;

    const char* getSubName() const
    {
        parseSubName();
        return !mySubName.empty() ? mySubName.c_str() : nullptr;
    }

    const std::vector<std::string>& getSubElements() const
    {
        parseSubName();
        return mySubElements;
    }

    bool extensionGetSubObject(DocumentObject*& ret,
                               const char* subname,
                               PyObject** pyObj = nullptr,
                               Base::Matrix4D* mat = nullptr,
                               bool transform = false,
                               int depth = 0) const override;

    bool extensionGetSubObjects(std::vector<std::string>& ret, int reason) const override;

    bool extensionGetLinkedObject(DocumentObject*& ret,
                                  bool recurse,
                                  Base::Matrix4D* mat,
                                  bool transform,
                                  int depth) const override;

    App::DocumentObjectExecReturn* extensionExecute() override;
    short extensionMustExecute() override;
    void extensionOnChanged(const Property* p) override;
    void onExtendedUnsetupObject() override;
    void onExtendedDocumentRestored() override;

    int extensionSetElementVisible(const char*, bool) override;
    int extensionIsElementVisible(const char*) override;
    bool extensionHasChildElement() const override;

    PyObject* getExtensionPyObject() override;

    Property* extensionGetPropertyByName(const char* name) const override;

    static int getArrayIndex(const char* subname, const char** psubname = nullptr);
    int getElementIndex(const char* subname, const char** psubname = nullptr) const;
    void elementNameFromIndex(int idx, std::ostream& ss) const;

    DocumentObject* getContainer();
    const DocumentObject* getContainer() const;

    void setLink(int index,
                 DocumentObject* obj,
                 const char* subname = nullptr,
                 const std::vector<std::string>& subs = std::vector<std::string>());

    DocumentObject* getTrueLinkedObject(bool recurse,
                                        Base::Matrix4D* mat = nullptr,
                                        int depth = 0,
                                        bool noElement = false) const;

    using LinkPropMap = std::map<const Property*, std::pair<LinkBaseExtension*, int>>;

    bool hasPlacement() const
    {
        return getLinkPlacementProperty() || getPlacementProperty();
    }

    void cacheChildLabel(int enable = -1) const;

    static bool
    setupCopyOnChange(App::DocumentObject* obj,
                      App::DocumentObject* linked,
                      std::vector<fastsignals::scoped_connection>* copyOnChangeConns,
                      bool checkExisting);

    static bool isCopyOnChangeProperty(App::DocumentObject* obj, const Property& prop);

    void syncCopyOnChange();

    /** Options used in setOnChangeCopyObject()
     * Multiple options can be combined by bitwise or operator
     */
    enum class OnChangeCopyOptions
    {
        /// No options set
        None = 0,
        /// If set, then exclude the input from object list to copy on change, or else, include the
        /// input object.
        Exclude = 1,
        /// If set , then apply the setting to all links to the input object, or else, apply only to
        /// this link.
        ApplyAll = 2,
    };

    /** Include or exclude object from list of objects to copy on change
     * @param obj: input object
     * @param options: control options. @sa OnChangeCopyOptions.
     */
    void setOnChangeCopyObject(App::DocumentObject* obj, OnChangeCopyOptions options);

    std::vector<App::DocumentObject*>
    getOnChangeCopyObjects(std::vector<App::DocumentObject*>* excludes = nullptr,
                           App::DocumentObject* src = nullptr);

    bool isLinkedToConfigurableObject() const;

    void monitorOnChangeCopyObjects(const std::vector<App::DocumentObject*>& objs);

    /// Check if the linked object is a copy on change
    bool isLinkMutated() const;

protected:
    void
    _handleChangedPropertyName(Base::XMLReader& reader, const char* TypeName, const char* PropName);
    void parseSubName() const;
    void update(App::DocumentObject* parent, const Property* prop);
    void checkCopyOnChange(App::DocumentObject* parent, const App::Property& prop);
    void setupCopyOnChange(App::DocumentObject* parent, bool checkSource = false);
    App::DocumentObject* makeCopyOnChange();
    void syncElementList();
    void detachElement(App::DocumentObject* obj);
    void detachElements();
    void checkGeoElementMap(const App::DocumentObject* obj,
                            const App::DocumentObject* linked,
                            PyObject** pyObj,
                            const char* postfix) const;
    void updateGroup();
    void slotChangedPlainGroup(const App::DocumentObject&, const App::Property&);

protected:
    std::vector<Property*> props;
    std::unordered_set<const App::DocumentObject*> myHiddenElements;
    mutable std::vector<std::string> mySubElements;
    mutable std::string mySubName;

    std::unordered_map<const App::DocumentObject*, fastsignals::scoped_connection>
        plainGroupConns;

    long prevLinkedObjectID = 0;

    mutable std::unordered_map<std::string, int> myLabelCache;  // for label based subname lookup
    mutable bool enableLabelCache {false};
    bool hasOldSubElement {false};

    std::vector<fastsignals::scoped_connection> copyOnChangeConns;
    std::vector<fastsignals::scoped_connection> copyOnChangeSrcConns;
    bool hasCopyOnChange {true};

    mutable bool checkingProperty = false;
    bool pauseCopyOnChange = false;

    fastsignals::scoped_connection connCopyOnChangeSource;
};

///////////////////////////////////////////////////////////////////////////

using LinkBaseExtensionPython = ExtensionPythonT<LinkBaseExtension>;

///////////////////////////////////////////////////////////////////////////

class AppExport LinkExtension: public LinkBaseExtension
{
    EXTENSION_PROPERTY_HEADER_WITH_OVERRIDE(App::LinkExtension);
    using inherited = LinkBaseExtension;

public:
    LinkExtension();
    ~LinkExtension() override = default;

    /** \name Helpers for defining Link properties
     *
     * Reuse LINK_PARAM_* definitions above and keep all link-related properties under the " Link"
     * group (leading space for sorting).
     */
    //@{

#define _LINK_PROP_ADD(_add_property, _name, _def, _atype, _doc)                                   \
    _add_property(#_name, _name, _def, " Link", _atype, _doc);                                     \
    setProperty(Prop##_name, &_name);

#define LINK_PROP_ADD(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype)                     \
    _LINK_PROP_ADD(_ADD_PROPERTY_TYPE, _name, _def, _atype, _doc);

#define LINK_PROP_ADD_EXTENSION(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype)           \
    _LINK_PROP_ADD(_EXTENSION_ADD_PROPERTY_TYPE, _name, _def, _atype, _doc);

#define LINK_PROPS_ADD(_seq) _seq(LINK_PROP_ADD, _)
#define LINK_PROPS_ADD_EXTENSION(_seq) _seq(LINK_PROP_ADD_EXTENSION, _)

#define _LINK_PROP_SET(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype)                    \
    setProperty(Prop##_name, &_name);

#define LINK_PROPS_SET(_seq) _seq(_LINK_PROP_SET, _)
    //@}

#define LINK_PARAMS_EXT(_apply, _data)                                                             \
    LINK_PARAM_SCALE(_apply, _data)                                                                \
    LINK_PARAM_SCALE_VECTOR(_apply, _data)                                                         \
    LINK_PARAM_SCALES(_apply, _data)                                                               \
    LINK_PARAM_VISIBILITIES(_apply, _data)                                                         \
    LINK_PARAM_PLACEMENTS(_apply, _data)                                                           \
    LINK_PARAM_ELEMENTS(_apply, _data)

#define LINK_PROP_DEFINE(_data, _name, _type, _ptype, _def, _doc, _dtype, _atype) _dtype _name;
#define LINK_PROPS_DEFINE(_seq) _seq(LINK_PROP_DEFINE, _)

    // defines the actual properties
    LINK_PROPS_DEFINE(LINK_PARAMS_EXT)

    void onExtendedDocumentRestored() override
    {
        LINK_PROPS_SET(LINK_PARAMS_EXT);
        inherited::onExtendedDocumentRestored();
    }
};

///////////////////////////////////////////////////////////////////////////

using LinkExtensionPython = ExtensionPythonT<LinkExtension>;

///////////////////////////////////////////////////////////////////////////

class AppExport Link: public App::DocumentObject, public App::LinkExtension
{
    PROPERTY_HEADER_WITH_EXTENSIONS(App::Link);
    using inherited = App::DocumentObject;

public:
#define LINK_PARAMS_LINK(_apply, _data)                                                            \
    LINK_PARAM_OBJECT(_apply, _data)                                                               \
    LINK_PARAM_CLAIM_CHILD(_apply, _data)                                                          \
    LINK_PARAM_TRANSFORM(_apply, _data)                                                            \
    LINK_PARAM_LINK_PLACEMENT(_apply, _data)                                                       \
    LINK_PARAM_PLACEMENT(_apply, _data)                                                            \
    LINK_PARAM_SHOW_ELEMENT(_apply, _data)                                                         \
    LINK_PARAM_COUNT(_apply, _data)                                                                \
    LINK_PARAM_LINK_EXECUTE(_apply, _data)                                                         \
    LINK_PARAM_COLORED_ELEMENTS(_apply, _data)                                                     \
    LINK_PARAM_COPY_ON_CHANGE(_apply, _data)                                                       \
    LINK_PARAM_COPY_ON_CHANGE_SOURCE(_apply, _data)                                                \
    LINK_PARAM_COPY_ON_CHANGE_GROUP(_apply, _data)                                                 \
    LINK_PARAM_COPY_ON_CHANGE_TOUCHED(_apply, _data)

    LINK_PROPS_DEFINE(LINK_PARAMS_LINK)

    Link();

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderLink";
    }

    void onDocumentRestored() override
    {
        LINK_PROPS_SET(LINK_PARAMS_LINK);
        inherited::onDocumentRestored();
    }

    void handleChangedPropertyName(Base::XMLReader& reader,
                                   const char* TypeName,
                                   const char* PropName) override
    {
        _handleChangedPropertyName(reader, TypeName, PropName);
    }

    bool canLinkProperties() const override;

    Base::Placement getPlacementOf(const std::string& sub, DocumentObject* targetObj = nullptr) override;

    bool isLink() const override;

    bool isLinkGroup() const override;
};

using LinkPython = App::FeaturePythonT<Link>;

///////////////////////////////////////////////////////////////////////////

class AppExport LinkElement: public App::DocumentObject, public App::LinkBaseExtension
{
    PROPERTY_HEADER_WITH_EXTENSIONS(App::LinkElement);
    using inherited = App::DocumentObject;

public:
#define LINK_PARAMS_ELEMENT(_apply, _data)                                                         \
    LINK_PARAM_SCALE(_apply, _data)                                                                \
    LINK_PARAM_SCALE_VECTOR(_apply, _data)                                                         \
    LINK_PARAM_OBJECT(_apply, _data)                                                               \
    LINK_PARAM_TRANSFORM(_apply, _data)                                                            \
    LINK_PARAM_LINK_PLACEMENT(_apply, _data)                                                       \
    LINK_PARAM_PLACEMENT(_apply, _data)                                                            \
    LINK_PARAM_COPY_ON_CHANGE(_apply, _data)                                                       \
    LINK_PARAM_COPY_ON_CHANGE_SOURCE(_apply, _data)                                                \
    LINK_PARAM_COPY_ON_CHANGE_GROUP(_apply, _data)                                                 \
    LINK_PARAM_COPY_ON_CHANGE_TOUCHED(_apply, _data)

    // defines the actual properties
    LINK_PROPS_DEFINE(LINK_PARAMS_ELEMENT)

    LinkElement();
    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderLink";
    }

    void onDocumentRestored() override
    {
        LINK_PROPS_SET(LINK_PARAMS_ELEMENT);
        inherited::onDocumentRestored();
    }

    bool canDelete() const;

    void handleChangedPropertyName(Base::XMLReader& reader,
                                   const char* TypeName,
                                   const char* PropName) override
    {
        _handleChangedPropertyName(reader, TypeName, PropName);
    }

    bool isLink() const override;

    App::Link* getLinkGroup() const;

    Base::Placement getPlacementOf(const std::string& sub, DocumentObject* targetObj = nullptr) override;
};

using LinkElementPython = App::FeaturePythonT<LinkElement>;

///////////////////////////////////////////////////////////////////////////

class AppExport LinkGroup: public App::DocumentObject, public App::LinkBaseExtension
{
    PROPERTY_HEADER_WITH_EXTENSIONS(App::LinkGroup);
    using inherited = App::DocumentObject;

public:
#define LINK_PARAMS_GROUP(_apply, _data)                                                           \
    LINK_PARAM_ELEMENTS(_apply, _data)                                                             \
    LINK_PARAM_PLACEMENT(_apply, _data)                                                            \
    LINK_PARAM_VISIBILITIES(_apply, _data)                                                         \
    LINK_PARAM_MODE(_apply, _data)                                                                 \
    LINK_PARAM_COLORED_ELEMENTS(_apply, _data)

    // defines the actual properties
    LINK_PROPS_DEFINE(LINK_PARAMS_GROUP)

    LinkGroup();

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderLink";
    }

    void onDocumentRestored() override
    {
        LINK_PROPS_SET(LINK_PARAMS_GROUP);
        inherited::onDocumentRestored();
    }
};

using LinkGroupPython = App::FeaturePythonT<LinkGroup>;

}  // namespace App

ENABLE_BITMASK_OPERATORS(App::Link::OnChangeCopyOptions)

/*[[[cog
import LinkParams
LinkParams.declare()
]]]*/

namespace App
{
/** Convenient class to obtain App::Link related parameters

 * The parameters are under group "User parameter:BaseApp/Preferences/Link"
 *
 * This class is auto generated by LinkParams.py. Modify that file
 * instead of this one, if you want to add any parameter. You need
 * to install Cog Python package for code generation:
 * @code
 *     pip install cogapp
 * @endcode
 *
 * Once modified, you can regenerate the header and the source file,
 * @code
 *     python3 -m cogapp -r Link.h Link.cpp
 * @endcode
 *
 * You can add a new parameter by adding lines in LinkParams.py. Available
 * parameter types are 'Int, UInt, String, Bool, Float'. For example, to add
 * a new Int type parameter,
 * @code
 *     ParamInt(parameter_name, default_value, documentation, on_change=False)
 * @endcode
 *
 * If there is special handling on parameter change, pass in on_change=True.
 * And you need to provide a function implementation in Link.cpp with
 * the following signature.
 * @code
 *     void LinkParams:on<parameter_name>Changed()
 * @endcode
 */
class AppExport LinkParams
{
public:
    static ParameterGrp::handle getHandle();

    //@{
    /// Accessor for parameter CopyOnChangeApplyToAll
    ///
    /// Stores the last user choice of whether to apply CopyOnChange setup to all link
    /// that links to the same configurable object
    static const bool& getCopyOnChangeApplyToAll();
    static const bool& defaultCopyOnChangeApplyToAll();
    static void removeCopyOnChangeApplyToAll();
    static void setCopyOnChangeApplyToAll(const bool& v);
    static const char* docCopyOnChangeApplyToAll();
    //@}

    // Auto generated code. See class document of LinkParams.
};
}  // namespace App
//[[[end]]]


#endif  // APP_LINK_H
