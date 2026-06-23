// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2002 Jürgen Riegel <juergen.riegel@web.de>              *
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


#include <algorithm>
#include <cassert>
#include <iomanip>
#include <map>
#include <memory>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <App/Application.h>

#include "Application.h"
#include "DirectedGraph.h"
#include "Document.h"
#include "private/DocumentP.h"
#include "DocumentObject.h"
#include "ExpressionParser.h"
#include "GeoFeatureGroupExtension.h"
#include "Origin.h"
#include "OriginGroupExtension.h"
#include "ObjectIdentifier.h"

using namespace App;

namespace
{

using GraphvizAttributes = std::map<std::string, std::string>;

std::string dotQuote(const std::string& text)
{
    std::string result;
    result.reserve(text.size() + 2);
    result += '"';
    for (char ch : text) {
        if (ch == '"' || ch == '\\') {
            result += '\\';
        }
        result += ch;
    }
    result += '"';
    return result;
}

void writeAttributes(std::ostream& out, const GraphvizAttributes& attributes)
{
    if (attributes.empty()) {
        return;
    }

    out << " [";
    const char* separator = "";
    for (const auto& [key, value] : attributes) {
        out << separator << key << "=" << dotQuote(value);
        separator = ", ";
    }
    out << "]";
}

class DotGraph
{
public:
    using Vertex = App::DirectedGraph::Vertex;
    using Edge = std::size_t;

    struct Cluster
    {
        std::string name;
        GraphvizAttributes attributes;
        std::vector<Vertex> vertices;
        std::vector<std::unique_ptr<Cluster>> children;
        Cluster* parent {};
    };

    DotGraph()
    {
        _root.name = "G";
    }

    Cluster* root()
    {
        return &_root;
    }

    const Cluster* root() const
    {
        return &_root;
    }

    Cluster* createSubgraph(Cluster& parent)
    {
        auto subgraph = std::make_unique<Cluster>();
        subgraph->parent = &parent;
        auto* result = subgraph.get();
        parent.children.push_back(std::move(subgraph));
        return result;
    }

    Vertex addVertex(Cluster& graph)
    {
        const auto vertex = _graph.addVertex();
        _vertices.emplace_back();
        graph.vertices.push_back(vertex);
        return vertex;
    }

    Edge addEdge(Vertex source, Vertex target)
    {
        const auto index = _graph.addEdge(source, target);
        _edges.push_back({source, target, {}});
        return index;
    }

    bool hasEdge(Vertex source, Vertex target) const
    {
        return _graph.hasEdge(source, target);
    }

    Edge findEdge(Vertex source, Vertex target) const
    {
        return _graph.edgeIndex(source, target);
    }

    GraphvizAttributes& graphAttributes(Cluster& graph)
    {
        return graph.attributes;
    }

    std::string& graphName(Cluster& graph)
    {
        return graph.name;
    }

    GraphvizAttributes& vertexAttributes(Vertex vertex)
    {
        return _vertices.at(vertex).attributes;
    }

    GraphvizAttributes& edgeAttributes(Edge edge)
    {
        return _edges.at(edge).attributes;
    }

    void markCycleEdges()
    {
        for (auto edge : _graph.cyclicEdgeIndices()) {
            edgeAttributes(edge)["color"] = "red";
        }
    }

    void write(std::ostream& out) const
    {
        out << "digraph " << _root.name << " {\n";
        writeGraphBody(out, _root, 1);
        out << "}\n";
    }

private:
    struct VertexInfo
    {
        GraphvizAttributes attributes;
    };

    struct EdgeInfo
    {
        Vertex source {};
        Vertex target {};
        GraphvizAttributes attributes;
    };

    static void indent(std::ostream& out, int level)
    {
        for (int i = 0; i < level; ++i) {
            out << "  ";
        }
    }

    void writeGraphBody(std::ostream& out, const Cluster& graph, int level) const
    {
        for (const auto& [key, value] : graph.attributes) {
            indent(out, level);
            out << key << "=" << dotQuote(value) << ";\n";
        }

        for (const auto& child : graph.children) {
            indent(out, level);
            out << "subgraph " << child->name << " {\n";
            writeGraphBody(out, *child, level + 1);
            indent(out, level);
            out << "}\n";
        }

        for (auto vertex : graph.vertices) {
            indent(out, level);
            out << vertex;
            writeAttributes(out, _vertices.at(vertex).attributes);
            out << ";\n";
        }

        if (graph.parent) {
            return;
        }

        for (const auto& edge : _edges) {
            indent(out, level);
            out << edge.source << " -> " << edge.target;
            writeAttributes(out, edge.attributes);
            out << ";\n";
        }
    }

    Cluster _root;
    App::DirectedGraph _graph;
    std::vector<VertexInfo> _vertices;
    std::vector<EdgeInfo> _edges;
};

}  // namespace

void Document::writeDependencyGraphViz(std::ostream& out)
{
    out << "digraph G {" << std::endl;
    out << "\tordering=out;" << std::endl;
    out << "\tnode [shape = box];" << std::endl;

    for (const auto& It : d->objectMap) {
        out << "\t" << It.first << ";" << std::endl;
        std::vector<DocumentObject*> OutList = It.second->getOutList();
        for (const auto& It2 : OutList) {
            if (It2) {
                out << "\t" << It.first << "->" << It2->getNameInDocument() << ";" << std::endl;
            }
        }
    }
    out << "}" << std::endl;
}

enum class PropType
{
    PROP_REGULAR,
    PROP_INPUT,
    PROP_OUTPUT
};

static PropType getPropType(DocumentObject* obj, const std::string& propName)
{
    if (obj->isInputProperty(propName)) {
        return PropType::PROP_INPUT;
    }
    else if (obj->isOutputProperty(propName)) {
        return PropType::PROP_OUTPUT;
    }
    return PropType::PROP_REGULAR;
}

static void exportProp(const char* objName, const char* propName, PropType propType, std::ostream& out)
{
    const char* color = propType == PropType::PROP_INPUT ? ", color=blue, fontcolor=blue" : "";
    out << "    " << objName << "_" << propName <<
        " [label=\"" << propName << "\"" << color << "];\n";
}

static std::map<std::string, PropType> getSubGraphNodes(DocumentObject* obj)
{
    std::map<std::string, PropType> nodes;
    nodes["HEAD"] = PropType::PROP_REGULAR;

    for (const auto& [objFrom, propFrom, objTo, propTo] : obj->getOutListProp()) {
        if (!nodes.contains(propFrom)) {
            nodes[propFrom] = getPropType(objFrom, propFrom);
        }
    }

    for (const auto& [objFrom, propFrom, objTo, propTo] : obj->getInListProp()) {
        if (!propTo.empty() && !nodes.contains(propTo)) {
            nodes[propTo] = getPropType(objTo, propTo);
        }
    }

    return nodes;
}

static void exportSubGraphNodes(DocumentObject* obj, std::ostream& out)
{
    const char* name = obj->getNameInDocument();
    std::map<std::string, PropType> nodes = getSubGraphNodes(obj);
    for (const auto& [propName, propType] : nodes) {
        exportProp(name, propName.c_str(), propType, out);
    }
}

static void exportSubGraph(DocumentObject* obj, std::ostream& out)
{
    const char* name = obj->getNameInDocument();
    out << "  subgraph cluster_" << name << " {\n";
    out << "    label = \"" << name << " (" << obj->Label.getValue() << ")\";\n";
    out << "    style=dashed;\n\n";

    exportSubGraphNodes(obj, out);
    out << "  }\n\n";
}

static void exportEdge(std::string& from, std::string& to, std::ostream& out)
{
    out << "  " << from << " -> " << to << ";\n";
}

static void exportEdges(DocumentObject* objTo, std::ostream& out)
{
    const char* nameObjTo = objTo->getNameInDocument();

    std::map<std::string, PropType> subgraphNodes = getSubGraphNodes(objTo);
    // create edges from the first node (HEAD) to all other nodes in the subgraph
    std::string from = nameObjTo + std::string("_HEAD");
    for (const auto& [propName, propType] : subgraphNodes) {
        if (propName != "HEAD") {
            std::string to = nameObjTo + ("_" + propName);
            if (propType == PropType::PROP_OUTPUT) {
                exportEdge(to, from, out);
            }
            else {
                exportEdge(from, to, out);
            }
        }
    }

    for (const auto& [objFrom, propFrom, objTo, propTo] : objTo->getInListProp()) {
        const char* nameObjFrom = objFrom->getNameInDocument();
        std::string from = nameObjFrom + ("_" + propFrom);
        std::string to = nameObjTo + ("_" + (propTo == "" ? "HEAD" : propTo));
        exportEdge(from,to, out);
    }
    out << "\n";
}

void Document::exportGraphvizProp(std::ostream& out) const
{
    out << "digraph G {\n";
    out << "  rankdir=TB;\n";
    out << "  node [shape=ellipse, color=black];\n\n";

    for (auto* obj : getDependingObjects()) {
        exportSubGraph(obj, out);
    }

    for (auto* obj : getDependingObjects()) {
        exportEdges(obj, out);
    }

    out << "}\n";
}

void Document::exportGraphviz(std::ostream& out) const
{
    if (GetApplication().isFineGrainedRecomputeEnabled()) {
        exportGraphvizProp(out);
        return;
    }

    using Graph = DotGraph::Cluster;
    using Vertex = DotGraph::Vertex;
    using Edge = DotGraph::Edge;

    /**
     * @brief The GraphCreator class
     *
     * This class creates the dependency graph for a document.
     *
     */
    class GraphCreator
    {
    public:
        explicit GraphCreator(struct DocumentP* _d)
            : d(_d)
            , seed(std::random_device()())
            , distribution(0, 255)
        {
            build();
        }

        const DotGraph& getGraph() const
        {
            return DepList;
        }

    private:
        void build()
        {
            // Set attribute(s) for main graph
            DepList.graphAttributes(*DepList.root())["compound"] = "true";

            addSubgraphs();
            buildAdjacencyList();
            addEdges();
            markCycles();
            markOutOfScopeLinks();
        }

        /**
         * @brief getId returns a canonical string for a DocumentObject.
         * @param docObj Document object to get an ID from
         * @return A string
         */
        std::string getId(const DocumentObject* docObj)
        {
            std::string id;
            if (docObj->isAttachedToDocument()) {
                auto doc = docObj->getDocument();
                id.append(doc->getName());
                id.append("#");
                id.append(docObj->getNameInDocument());
            }
            return id;
        }

        /**
         * @brief getId returns a canonical string for an ObjectIdentifier;
         * @param path
         * @return A string
         */
        std::string getId(const ObjectIdentifier& path)
        {
            DocumentObject* docObj = path.getDocumentObject();
            if (!docObj) {
                return {};
            }

            return std::string((docObj)->getDocument()->getName()) + "#"
                + docObj->getNameInDocument() + "." + path.getPropertyName() + path.getSubPathStr();
        }

        std::string getClusterName(const DocumentObject* docObj) const
        {
            return std::string("cluster") + docObj->getNameInDocument();
        }

        void setGraphLabel(Graph& g, const DocumentObject* obj)
        {
            std::string name(obj->getNameInDocument());
            std::string label(obj->Label.getValue());
            if (name == label) {
                DepList.graphAttributes(g)["label"] = name;
            }
            else {
                DepList.graphAttributes(g)["label"] = name + "&#92;n(" + label + ")";
            }
        }

        /**
         * @brief setGraphAttributes Set graph attributes on a subgraph for a DocumentObject node.
         * @param obj DocumentObject
         */
        void setGraphAttributes(const DocumentObject* obj)
        {
            assert(GraphList.find(obj) != GraphList.end());
            DepList.graphName(*GraphList[obj]) = getClusterName(obj);

            DepList.graphAttributes(*GraphList[obj])["bgcolor"] = "#e0e0e0";

            DepList.graphAttributes(*GraphList[obj])["style"] = "rounded,filled";
            setGraphLabel(*GraphList[obj], obj);
        }

        /**
         * @brief setPropertyVertexAttributes Set vertex attributes for a Property node in a graph.
         * @param g Graph
         * @param vertex Property node
         * @param name Name of node
         */
        void setPropertyVertexAttributes(Vertex vertex, const std::string& name)
        {
            auto& attributes = DepList.vertexAttributes(vertex);
            attributes["label"] = name;
            attributes["shape"] = "box";
            attributes["style"] = "dashed";
            attributes["fontsize"] = "8pt";
        }

        /**
         * @brief addExpressionSubgraphIfNeeded Add a subgraph to the main graph if it is needed,
         * i.e. there are defined at least one expression in the document object, or other objects
         * are referencing properties in it.
         * @param obj DocumentObject to assess.
         * @param CSSubgraphs Boolean if the GeoFeatureGroups are created as subgraphs
         */
        void addExpressionSubgraphIfNeeded(DocumentObject* obj, bool CSsubgraphs)
        {

            auto expressions = obj->ExpressionEngine.getExpressions();

            if (!expressions.empty()) {

                Graph* graph = DepList.root();
                if (CSsubgraphs) {
                    auto group = GeoFeatureGroupExtension::getGroupOfObject(obj);
                    if (group) {
                        auto it = GraphList.find(group);
                        if (it != GraphList.end()) {
                            graph = it->second;
                        }
                    }
                }

                // If documentObject has an expression, create a subgraph for it
                if (graph && !GraphList[obj]) {
                    GraphList[obj] = DepList.createSubgraph(*graph);
                    setGraphAttributes(obj);
                }

                // Create subgraphs for all document objects that it depends on; it will depend on
                // some property there
                for (const auto& expr : expressions) {
                    std::map<ObjectIdentifier, bool> deps;

                    expr.second->getIdentifiers(deps);

                    for (const auto& dep : deps) {
                        if (dep.second) {
                            continue;
                        }
                        DocumentObject* o = dep.first.getDocumentObject();

                        // Doesn't exist already?
                        if (o && !GraphList[o]) {

                            if (CSsubgraphs) {
                                auto group = GeoFeatureGroupExtension::getGroupOfObject(o);
                                auto graph2 = group ? GraphList[group] : DepList.root();
                                if (graph2) {
                                    GraphList[o] = DepList.createSubgraph(*graph2);
                                    setGraphAttributes(o);
                                }
                            }
                            else if (graph) {
                                GraphList[o] = DepList.createSubgraph(*graph);
                                setGraphAttributes(o);
                            }
                        }
                    }
                }
            }
        }

        /**
         * @brief add Add @docObj to the graph, including all expressions (and dependencies) it
         * includes.
         * @param docObj The document object to add.
         * @param name Name of node.
         */
        void add(DocumentObject* docObj,
                 const std::string& name,
                 const std::string& label,
                 bool CSSubgraphs)
        {

            // don't add objects twice
            if (objects.contains(docObj)) {
                return;
            }

            // find the correct graph to add the vertex to. Check first expression graphs,
            // afterwards the parent CS and origin graphs
            Graph* sgraph = GraphList[docObj];
            if (CSSubgraphs) {
                if (!sgraph) {
                    auto group = GeoFeatureGroupExtension::getGroupOfObject(docObj);
                    if (group) {
                        if (docObj->isDerivedFrom<App::DatumElement>()) {
                            sgraph = GraphList[group->getExtensionByType<OriginGroupExtension>()
                                                   ->Origin.getValue()];
                        }
                        else {
                            sgraph = GraphList[group];
                        }
                    }
                }
                if (!sgraph) {
                    if (docObj->isDerivedFrom<DatumElement>()) {
                        auto* lcs = static_cast<DatumElement*>(docObj)->getLCS();
                        if (lcs) {
                            sgraph = GraphList[lcs];
                        }
                    }
                }
            }
            if (!sgraph) {
                sgraph = DepList.root();
            }

            // Keep a list of all added document objects.
            objects.insert(docObj);

            // Add vertex to graph. Track global and local index
            LocalVertexList[getId(docObj)] = DepList.addVertex(*sgraph);
            GlobalVertexList[getId(docObj)] = LocalVertexList[getId(docObj)];

            // If node is in main graph, style it with rounded corners. If not, make it invisible.
            if (!GraphList[docObj]) {
                auto& attributes = DepList.vertexAttributes(LocalVertexList[getId(docObj)]);
                attributes["style"] = "filled";
                attributes["shape"] = "Mrecord";
                // Set node label
                if (name == label) {
                    attributes["label"] = name;
                }
                else {
                    attributes["label"] = name + "&#92;n(" + label + ")";
                }
            }
            else {
                auto& attributes = DepList.vertexAttributes(LocalVertexList[getId(docObj)]);
                attributes["style"] = "invis";
                attributes["fixedsize"] = "true";
                attributes["width"] = "0";
                attributes["height"] = "0";
            }

            // Add expressions and its dependencies
            auto expressions {docObj->ExpressionEngine.getExpressions()};
            for (const auto& expr : expressions) {
                auto found = std::as_const(GlobalVertexList).find(getId(expr.first));
                if (found == GlobalVertexList.end()) {
                    Vertex vid = LocalVertexList[getId(expr.first)] = DepList.addVertex(*sgraph);
                    GlobalVertexList[getId(expr.first)] = vid;
                    setPropertyVertexAttributes(vid, expr.first.toString());
                }
            }

            // Add all dependencies
            for (const auto& expression : expressions) {
                // Get dependencies
                std::map<ObjectIdentifier, bool> deps;
                expression.second->getIdentifiers(deps);

                // Create subgraphs for all documentobjects that it depends on; it will depend on
                // some property there
                for (const auto& dep : deps) {
                    if (dep.second) {
                        continue;
                    }
                    DocumentObject* depObjDoc = dep.first.getDocumentObject();
                    auto found = GlobalVertexList.find(getId(dep.first));

                    if (found == GlobalVertexList.end()) {
                        Graph* depSgraph =
                            GraphList[depObjDoc] ? GraphList[depObjDoc] : DepList.root();

                        LocalVertexList[getId(dep.first)] = DepList.addVertex(*depSgraph);
                        GlobalVertexList[getId(dep.first)] = LocalVertexList[getId(dep.first)];
                        setPropertyVertexAttributes(LocalVertexList[getId(dep.first)],
                                                    dep.first.getPropertyName()
                                                        + dep.first.getSubPathStr());
                    }
                }
            }
        }

        void recursiveCSSubgraphs(DocumentObject* cs, DocumentObject* parent)
        {

            auto graph = parent ? GraphList[parent] : DepList.root();
            // check if the value for the key 'parent' is null
            if (!graph) {
                return;
            }
            auto* sub = DepList.createSubgraph(*graph);
            GraphList[cs] = sub;
            DepList.graphName(*sub) = getClusterName(cs);

            // build random color string
            std::stringstream stream;
            stream << "#" << std::setfill('0') << std::setw(2) << std::hex << distribution(seed)
                   << std::setfill('0') << std::setw(2) << std::hex << distribution(seed)
                   << std::setfill('0') << std::setw(2) << std::hex << distribution(seed) << 80;
            std::string result(stream.str());

            DepList.graphAttributes(*sub)["bgcolor"] = result;
            DepList.graphAttributes(*sub)["style"] = "rounded,filled";
            setGraphLabel(*sub, cs);

            for (auto obj : cs->getOutList()) {
                if (obj->hasExtension(GeoFeatureGroupExtension::getExtensionClassTypeId())) {
                    // in case of dependencies loops check if obj is already part of the
                    // map to avoid infinite recursions
                    auto it = GraphList.find(obj);
                    if (it == GraphList.end()) {
                        recursiveCSSubgraphs(obj, cs);
                    }
                }
            }

            // setup the origin if available
            if (cs->hasExtension(App::OriginGroupExtension::getExtensionClassTypeId())) {
                auto origin = cs->getExtensionByType<OriginGroupExtension>()->Origin.getValue();
                if (!origin) {
                    std::cerr << "Origin feature not found" << std::endl;
                    return;
                }
                auto* osub = DepList.createSubgraph(*sub);
                GraphList[origin] = osub;
                DepList.graphName(*osub) = getClusterName(origin);
                DepList.graphAttributes(*osub)["bgcolor"] = "none";
                setGraphLabel(*osub, origin);
            }
        }

        void addSubgraphs()
        {

            ParameterGrp::handle depGrp = App::GetApplication().GetParameterGroupByPath(
                "User parameter:BaseApp/Preferences/DependencyGraph");
            bool CSSubgraphs = depGrp->GetBool("GeoFeatureSubgraphs", true);

            if (CSSubgraphs) {
                // first build up the coordinate system subgraphs
                for (auto objectIt : d->objectArray) {
                    // ignore groups inside other groups, these will be processed in one of the next
                    // recursive calls. App::Origin now has the GeoFeatureGroupExtension but it
                    // should not move its group symbol outside its parent
                    if (!objectIt->isDerivedFrom<Origin>()
                        && objectIt->hasExtension(
                            GeoFeatureGroupExtension::getExtensionClassTypeId())
                        && GeoFeatureGroupExtension::getGroupOfObject(objectIt) == nullptr) {
                        recursiveCSSubgraphs(objectIt, nullptr);
                    }
                }
            }

            // Internal document objects
            for (const auto& It : d->objectMap) {
                addExpressionSubgraphIfNeeded(It.second, CSSubgraphs);
            }

            // Add external document objects
            for (const auto& it : d->objectMap) {
                std::vector<DocumentObject*> OutList = it.second->getOutList();
                for (auto obj : OutList) {
                    if (obj) {
                        std::map<std::string, Vertex>::const_iterator item =
                            GlobalVertexList.find(getId(obj));

                        if (item == GlobalVertexList.end()) {
                            addExpressionSubgraphIfNeeded(obj, CSSubgraphs);
                        }
                    }
                }
            }
        }

        // Filling up the adjacency List
        void buildAdjacencyList()
        {

            ParameterGrp::handle depGrp = App::GetApplication().GetParameterGroupByPath(
                "User parameter:BaseApp/Preferences/DependencyGraph");
            bool CSSubgraphs = depGrp->GetBool("GeoFeatureSubgraphs", true);

            // Add internal document objects
            for (const auto& It : d->objectMap) {
                add(It.second,
                    It.second->getNameInDocument(),
                    It.second->Label.getValue(),
                    CSSubgraphs);
            }

            // Add external document objects
            for (const auto& It : d->objectMap) {
                std::vector<DocumentObject*> OutList = It.second->getOutList();
                for (auto obj : OutList) {
                    if (obj) {
                        std::map<std::string, Vertex>::const_iterator item =
                            GlobalVertexList.find(getId(obj));

                        if (item == GlobalVertexList.end()) {
                            if (obj->isAttachedToDocument()) {
                                add(obj,
                                    std::string(obj->getDocument()->getName()) + "#"
                                        + obj->getNameInDocument(),
                                    std::string(obj->getDocument()->getName()) + "#"
                                        + obj->Label.getValue(),
                                    CSSubgraphs);
                            }
                        }
                    }
                }
            }
        }

        void addEdges()
        {
            // Track edges between document objects connected by expression dependencies
            std::set<std::pair<const DocumentObject*, const DocumentObject*>> existingEdges;

            // Add edges between properties
            for (const auto& docObj : objects) {

                // Add expressions and its dependencies
                auto expressions = docObj->ExpressionEngine.getExpressions();
                for (const auto& expr : expressions) {
                    std::map<ObjectIdentifier, bool> deps;
                    expr.second->getIdentifiers(deps);

                    // Create subgraphs for all documentobjects that it depends on; it will depend
                    // on some property there
                    for (const auto& dep : deps) {
                        if (dep.second) {
                            continue;
                        }
                        DocumentObject* depObjDoc = dep.first.getDocumentObject();
                        auto exprVertex = GlobalVertexList.find(getId(expr.first));
                        auto depVertex = GlobalVertexList.find(getId(dep.first));
                        if (exprVertex == GlobalVertexList.end()
                            || depVertex == GlobalVertexList.end()) {
                            continue;
                        }

                        Edge edge = DepList.addEdge(exprVertex->second, depVertex->second);

                        // Add this edge to the set of all expression generated edges
                        existingEdges.insert(std::make_pair(docObj, depObjDoc));

                        // Edges between properties should be a bit smaller, and dashed
                        auto& attributes = DepList.edgeAttributes(edge);
                        attributes["arrowsize"] = "0.5";
                        attributes["style"] = "dashed";
                    }
                }
            }

            ParameterGrp::handle depGrp = App::GetApplication().GetParameterGroupByPath(
                "User parameter:BaseApp/Preferences/DependencyGraph");
            bool omitGeoFeatureGroups = depGrp->GetBool("GeoFeatureSubgraphs", true);

            // Add edges between document objects
            for (const auto& It : d->objectMap) {

                if (omitGeoFeatureGroups && It.second->isDerivedFrom<Origin>()) {
                    continue;
                }

                std::map<DocumentObject*, int> dups;
                std::vector<DocumentObject*> OutList = It.second->getOutList();
                const DocumentObject* docObj = It.second;
                const bool docObj_is_group =
                    docObj->hasExtension(GeoFeatureGroupExtension::getExtensionClassTypeId());

                for (auto obj : OutList) {
                    if (obj) {
                        if (omitGeoFeatureGroups && docObj_is_group
                            && GeoFeatureGroupExtension::getGroupOfObject(obj) == docObj) {
                            continue;
                        }
                        auto docVertex = GlobalVertexList.find(getId(docObj));
                        auto objVertex = GlobalVertexList.find(getId(obj));
                        if (docVertex == GlobalVertexList.end()
                            || objVertex == GlobalVertexList.end()) {
                            continue;
                        }

                        // Count duplicate edges
                        if (DepList.hasEdge(docVertex->second, objVertex->second)) {
                            dups[obj]++;
                            continue;
                        }

                        // Skip edge if an expression edge already exists
                        if (existingEdges.find(std::make_pair(docObj, obj))
                            != existingEdges.end()) {
                            continue;
                        }

                        // Add edge

                        Edge edge = DepList.addEdge(docVertex->second, objVertex->second);

                        // Set properties to make arrows go between subgraphs if needed
                        auto& attributes = DepList.edgeAttributes(edge);
                        if (GraphList[docObj]) {
                            attributes["ltail"] = getClusterName(docObj);
                        }
                        if (GraphList[obj]) {
                            attributes["lhead"] = getClusterName(obj);
                        }
                    }
                }

                // Set labels for duplicate edges
                for (const auto& dup : dups) {
                    auto source = GlobalVertexList.find(getId(It.second));
                    auto target = GlobalVertexList.find(getId(dup.first));
                    if (source == GlobalVertexList.end() || target == GlobalVertexList.end()) {
                        continue;
                    }
                    Edge e = DepList.findEdge(source->second, target->second);
                    if (e == App::DirectedGraph::npos) {
                        continue;
                    }
                    std::stringstream s;
                    s << " " << (dup.second + 1) << "x";
                    DepList.edgeAttributes(e)["label"] = s.str();
                }
            }
        }

        void markCycles()
        {
            DepList.markCycleEdges();
        }

        void markOutOfScopeLinks()
        {
            for (auto obj : objects) {

                std::vector<App::DocumentObject*> invalids;
                GeoFeatureGroupExtension::getInvalidLinkObjects(obj, invalids);
                // isLinkValid returns true for non-link properties
                for (auto linkedObj : invalids) {

                    auto source = GlobalVertexList.find(getId(obj));
                    auto target = GlobalVertexList.find(getId(linkedObj));
                    if (source == GlobalVertexList.end() || target == GlobalVertexList.end()) {
                        continue;
                    }
                    auto edge = DepList.findEdge(source->second, target->second);
                    if (edge != App::DirectedGraph::npos) {
                        DepList.edgeAttributes(edge)["color"] = "orange";
                    }
                }
            }
        }

        const struct DocumentP* d;
        DotGraph DepList;
        std::map<std::string, Vertex> LocalVertexList;
        std::map<std::string, Vertex> GlobalVertexList;
        std::set<const DocumentObject*> objects;
        std::map<const DocumentObject*, Graph*> GraphList;
        // random color generation
        std::mt19937 seed;
        std::uniform_int_distribution<int> distribution;
    };

    GraphCreator g(d);

    g.getGraph().write(out);
}
