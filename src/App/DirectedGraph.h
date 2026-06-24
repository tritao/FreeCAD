// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

/******************************************************************************
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
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

#include <algorithm>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace App
{

class DirectedGraph
{
public:
    using Vertex = std::size_t;

    class CycleError: public std::runtime_error
    {
    public:
        CycleError()
            : std::runtime_error("The graph contains a cycle.")
        {}
    };

    DirectedGraph() = default;

    explicit DirectedGraph(std::size_t vertexCount)
        : _adjacency(vertexCount)
    {}

    void clear()
    {
        _adjacency.clear();
        _edges.clear();
    }

    Vertex addVertex()
    {
        _adjacency.emplace_back();
        return _adjacency.size() - 1;
    }

    [[nodiscard]] std::size_t vertexCount() const
    {
        return _adjacency.size();
    }

    std::size_t addEdge(Vertex source, Vertex target)
    {
        checkVertex(source);
        checkVertex(target);
        _adjacency[source].push_back(target);
        _edges.push_back({source, target});
        return _edges.size() - 1;
    }

    [[nodiscard]] bool hasEdge(Vertex source, Vertex target) const
    {
        checkVertex(source);
        checkVertex(target);
        const auto& targets = _adjacency[source];
        return std::find(targets.begin(), targets.end(), target) != targets.end();
    }

    [[nodiscard]] std::size_t edgeIndex(Vertex source, Vertex target) const
    {
        for (std::size_t index = 0; index < _edges.size(); ++index) {
            if (_edges[index].source == source && _edges[index].target == target) {
                return index;
            }
        }
        return npos;
    }

    [[nodiscard]] std::vector<Vertex> topologicalSort() const
    {
        enum class Visit
        {
            Unvisited,
            Active,
            Done
        };

        std::vector<Visit> visits(vertexCount(), Visit::Unvisited);
        std::vector<Vertex> order;
        order.reserve(vertexCount());

        auto visit = [&](auto&& self, Vertex vertex) -> void {
            visits[vertex] = Visit::Active;
            for (auto target : _adjacency[vertex]) {
                if (visits[target] == Visit::Active) {
                    throw CycleError();
                }
                if (visits[target] == Visit::Unvisited) {
                    self(self, target);
                }
            }
            visits[vertex] = Visit::Done;
            order.push_back(vertex);
        };

        for (Vertex vertex = 0; vertex < vertexCount(); ++vertex) {
            if (visits[vertex] == Visit::Unvisited) {
                visit(visit, vertex);
            }
        }

        return order;
    }

    [[nodiscard]] Vertex findCycleSource() const
    {
        enum class Visit
        {
            Unvisited,
            Active,
            Done
        };

        std::vector<Visit> visits(vertexCount(), Visit::Unvisited);

        auto visit = [&](auto&& self, Vertex vertex) -> Vertex {
            visits[vertex] = Visit::Active;
            for (auto target : _adjacency[vertex]) {
                if (visits[target] == Visit::Active) {
                    return vertex;
                }
                if (visits[target] == Visit::Unvisited) {
                    auto source = self(self, target);
                    if (source != npos) {
                        return source;
                    }
                }
            }
            visits[vertex] = Visit::Done;
            return npos;
        };

        for (Vertex vertex = 0; vertex < vertexCount(); ++vertex) {
            if (visits[vertex] == Visit::Unvisited) {
                auto source = visit(visit, vertex);
                if (source != npos) {
                    return source;
                }
            }
        }

        return npos;
    }

    [[nodiscard]] std::vector<std::vector<Vertex>> stronglyConnectedComponents() const
    {
        std::vector<std::vector<Vertex>> components;
        std::vector<Vertex> stack;
        std::vector<bool> onStack(vertexCount(), false);
        std::vector<int> indexes(vertexCount(), -1);
        std::vector<int> lowLinks(vertexCount(), -1);
        int nextIndex = 0;

        auto connect = [&](auto&& self, Vertex vertex) -> void {
            indexes[vertex] = nextIndex;
            lowLinks[vertex] = nextIndex;
            ++nextIndex;
            stack.push_back(vertex);
            onStack[vertex] = true;

            for (auto target : _adjacency[vertex]) {
                if (indexes[target] == -1) {
                    self(self, target);
                    lowLinks[vertex] = std::min(lowLinks[vertex], lowLinks[target]);
                }
                else if (onStack[target]) {
                    lowLinks[vertex] = std::min(lowLinks[vertex], indexes[target]);
                }
            }

            if (lowLinks[vertex] != indexes[vertex]) {
                return;
            }

            auto& component = components.emplace_back();
            while (!stack.empty()) {
                auto item = stack.back();
                stack.pop_back();
                onStack[item] = false;
                component.push_back(item);
                if (item == vertex) {
                    break;
                }
            }
        };

        for (Vertex vertex = 0; vertex < vertexCount(); ++vertex) {
            if (indexes[vertex] == -1) {
                connect(connect, vertex);
            }
        }

        return components;
    }

    [[nodiscard]] std::vector<std::size_t> cyclicEdgeIndices() const
    {
        const auto components = stronglyConnectedComponents();
        std::vector<std::size_t> componentForVertex(vertexCount(), npos);
        std::vector<bool> cyclicComponent(components.size(), false);

        for (std::size_t index = 0; index < components.size(); ++index) {
            const auto& component = components[index];
            cyclicComponent[index] = component.size() > 1;
            for (auto vertex : component) {
                componentForVertex[vertex] = index;
            }
        }

        for (std::size_t index = 0; index < _edges.size(); ++index) {
            const auto& edge = _edges[index];
            if (edge.source == edge.target) {
                cyclicComponent[componentForVertex[edge.source]] = true;
            }
        }

        std::vector<std::size_t> indices;
        for (std::size_t index = 0; index < _edges.size(); ++index) {
            const auto& edge = _edges[index];
            const auto component = componentForVertex[edge.source];
            if (component == componentForVertex[edge.target] && cyclicComponent[component]) {
                indices.push_back(index);
            }
        }
        return indices;
    }

    static constexpr auto npos = std::numeric_limits<Vertex>::max();

private:
    struct Edge
    {
        Vertex source {};
        Vertex target {};
    };

    void checkVertex(Vertex vertex) const
    {
        if (vertex >= vertexCount()) {
            throw std::out_of_range("DirectedGraph vertex out of range");
        }
    }

    std::vector<std::vector<Vertex>> _adjacency;
    std::vector<Edge> _edges;
};

}  // namespace App
