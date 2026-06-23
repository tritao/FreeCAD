// SPDX-License-Identifier: LGPL-2.1-or-later

#include <algorithm>

#include <gmock/gmock.h>
#include <gtest/gtest.h>

#include <App/DirectedGraph.h>

using namespace testing;

TEST(DirectedGraph, topologicalSortReturnsDependenciesFirst)
{
    App::DirectedGraph graph;
    const auto object = graph.addVertex();
    const auto dependency = graph.addVertex();
    const auto nestedDependency = graph.addVertex();

    graph.addEdge(object, dependency);
    graph.addEdge(dependency, nestedDependency);

    EXPECT_THAT(graph.topologicalSort(), ElementsAre(nestedDependency, dependency, object));
}

TEST(DirectedGraph, topologicalSortThrowsOnCycle)
{
    App::DirectedGraph graph;
    const auto first = graph.addVertex();
    const auto second = graph.addVertex();

    graph.addEdge(first, second);
    graph.addEdge(second, first);

    EXPECT_THROW(graph.topologicalSort(), App::DirectedGraph::CycleError);
    EXPECT_NE(graph.findCycleSource(), App::DirectedGraph::npos);
}

TEST(DirectedGraph, stronglyConnectedComponentsGroupsCycles)
{
    App::DirectedGraph graph;
    const auto first = graph.addVertex();
    const auto second = graph.addVertex();
    const auto acyclic = graph.addVertex();

    graph.addEdge(first, second);
    graph.addEdge(second, first);
    graph.addEdge(first, acyclic);

    auto components = graph.stronglyConnectedComponents();
    for (auto& component : components) {
        std::ranges::sort(component);
    }

    EXPECT_THAT(components,
                UnorderedElementsAre(ElementsAre(first, second), ElementsAre(acyclic)));
}

TEST(DirectedGraph, cyclicEdgeIndicesReturnsOnlyEdgesInCycles)
{
    App::DirectedGraph graph;
    const auto first = graph.addVertex();
    const auto second = graph.addVertex();
    const auto acyclic = graph.addVertex();
    const auto selfCycle = graph.addVertex();

    graph.addEdge(first, second);
    graph.addEdge(second, first);
    graph.addEdge(first, acyclic);
    graph.addEdge(selfCycle, selfCycle);

    EXPECT_THAT(graph.cyclicEdgeIndices(), ElementsAre(0, 1, 3));
}
