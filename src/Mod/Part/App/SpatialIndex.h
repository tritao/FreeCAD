// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL
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
#include <cmath>
#include <cstddef>
#include <functional>
#include <limits>
#include <optional>
#include <queue>
#include <utility>
#include <vector>

#include <gp_Pnt.hxx>

namespace Part
{
namespace Spatial
{

struct Aabb3d
{
    double xMin {};
    double yMin {};
    double zMin {};
    double xMax {};
    double yMax {};
    double zMax {};

    static Aabb3d fromPoint(const gp_Pnt& p)
    {
        return {p.X(), p.Y(), p.Z(), p.X(), p.Y(), p.Z()};
    }

    static Aabb3d fromMinMax(double xMin, double yMin, double zMin, double xMax, double yMax, double zMax)
    {
        return {xMin, yMin, zMin, xMax, yMax, zMax};
    }

    bool overlaps(const Aabb3d& other) const
    {
        return xMin <= other.xMax && xMax >= other.xMin && yMin <= other.yMax && yMax >= other.yMin
            && zMin <= other.zMax && zMax >= other.zMin;
    }

    Aabb3d combined(const Aabb3d& other) const
    {
        return {
            std::min(xMin, other.xMin),
            std::min(yMin, other.yMin),
            std::min(zMin, other.zMin),
            std::max(xMax, other.xMax),
            std::max(yMax, other.yMax),
            std::max(zMax, other.zMax)
        };
    }

    double surfaceArea() const
    {
        double dx = xMax - xMin;
        double dy = yMax - yMin;
        double dz = zMax - zMin;
        return 2.0 * (dx * dy + dx * dz + dy * dz);
    }

    double distance2ToPoint(const gp_Pnt& p) const
    {
        double dx = 0.0;
        if (p.X() < xMin) {
            dx = xMin - p.X();
        }
        else if (p.X() > xMax) {
            dx = p.X() - xMax;
        }

        double dy = 0.0;
        if (p.Y() < yMin) {
            dy = yMin - p.Y();
        }
        else if (p.Y() > yMax) {
            dy = p.Y() - yMax;
        }

        double dz = 0.0;
        if (p.Z() < zMin) {
            dz = zMin - p.Z();
        }
        else if (p.Z() > zMax) {
            dz = p.Z() - zMax;
        }

        return dx * dx + dy * dy + dz * dz;
    }
};

template<typename Payload>
class AabbTree3d
{
public:
    int insert(const Aabb3d& box, Payload payload)
    {
        int leaf = allocateNode();
        nodes[leaf].box = box;
        nodes[leaf].payload = std::move(payload);
        nodes[leaf].height = 0;
        nodes[leaf].parent = -1;
        nodes[leaf].left = -1;
        nodes[leaf].right = -1;

        insertLeaf(leaf);
        ++leafCount;
        return leaf;
    }

    void remove(int leaf)
    {
        if (leaf < 0) {
            return;
        }
        removeLeaf(leaf);
        freeNode(leaf);
        --leafCount;
    }

    void clear()
    {
        nodes.clear();
        root = -1;
        freeList = -1;
        leafCount = 0;
    }

    bool empty() const
    {
        return leafCount == 0;
    }

    std::size_t size() const
    {
        return leafCount;
    }

    template<typename Visitor>
    void queryOverlap(const Aabb3d& box, Visitor&& visitor) const
    {
        if (root < 0) {
            return;
        }

        std::vector<int> stack;
        stack.reserve(64);
        stack.push_back(root);

        while (!stack.empty()) {
            int nodeId = stack.back();
            stack.pop_back();

            const Node& node = nodes[nodeId];
            if (!node.box.overlaps(box)) {
                continue;
            }

            if (node.isLeaf()) {
                visitor(*node.payload, nodeId);
            }
            else {
                stack.push_back(node.left);
                stack.push_back(node.right);
            }
        }
    }

    std::optional<std::pair<Payload, double>> nearest(const gp_Pnt& point) const
    {
        if (root < 0) {
            return std::nullopt;
        }

        struct QueueEntry
        {
            double dist2;
            int nodeId;
            bool operator>(const QueueEntry& other) const
            {
                return dist2 > other.dist2;
            }
        };

        std::priority_queue<QueueEntry, std::vector<QueueEntry>, std::greater<QueueEntry>> queue;
        queue.push({nodes[root].box.distance2ToPoint(point), root});

        double bestDist2 = std::numeric_limits<double>::infinity();
        int bestLeaf = -1;

        while (!queue.empty()) {
            QueueEntry entry = queue.top();
            queue.pop();

            if (entry.dist2 >= bestDist2) {
                break;
            }

            const Node& node = nodes[entry.nodeId];
            if (node.isLeaf()) {
                bestDist2 = entry.dist2;
                bestLeaf = entry.nodeId;
                continue;
            }

            const Node& left = nodes[node.left];
            const Node& right = nodes[node.right];

            queue.push({left.box.distance2ToPoint(point), node.left});
            queue.push({right.box.distance2ToPoint(point), node.right});
        }

        if (bestLeaf < 0) {
            return std::nullopt;
        }

        return std::make_optional(std::make_pair(*nodes[bestLeaf].payload, bestDist2));
    }

    std::vector<std::pair<Payload, double>> kNearest(const gp_Pnt& point, std::size_t k) const
    {
        std::vector<std::pair<Payload, double>> results;
        if (root < 0 || k == 0) {
            return results;
        }

        struct QueueEntry
        {
            double dist2;
            int nodeId;
            bool operator>(const QueueEntry& other) const
            {
                return dist2 > other.dist2;
            }
        };

        std::priority_queue<QueueEntry, std::vector<QueueEntry>, std::greater<QueueEntry>> queue;
        queue.push({nodes[root].box.distance2ToPoint(point), root});

        struct BestEntry
        {
            double dist2;
            int nodeId;
            bool operator<(const BestEntry& other) const
            {
                return dist2 < other.dist2;
            }
        };

        std::priority_queue<BestEntry> best;
        double worstDist2 = std::numeric_limits<double>::infinity();

        while (!queue.empty()) {
            QueueEntry entry = queue.top();
            queue.pop();

            if (best.size() == k && entry.dist2 > worstDist2) {
                break;
            }

            const Node& node = nodes[entry.nodeId];
            if (node.isLeaf()) {
                if (best.size() < k) {
                    best.push({entry.dist2, entry.nodeId});
                    if (best.size() == k) {
                        worstDist2 = best.top().dist2;
                    }
                }
                else if (entry.dist2 < best.top().dist2) {
                    best.pop();
                    best.push({entry.dist2, entry.nodeId});
                    worstDist2 = best.top().dist2;
                }
                continue;
            }

            const Node& left = nodes[node.left];
            const Node& right = nodes[node.right];
            queue.push({left.box.distance2ToPoint(point), node.left});
            queue.push({right.box.distance2ToPoint(point), node.right});
        }

        results.reserve(best.size());
        while (!best.empty()) {
            BestEntry entry = best.top();
            best.pop();
            results.emplace_back(*nodes[entry.nodeId].payload, entry.dist2);
        }
        std::ranges::sort(results, [](const auto& a, const auto& b) { return a.second < b.second; });
        return results;
    }

private:
    struct Node
    {
        Aabb3d box {};
        int parent {-1};
        int left {-1};
        int right {-1};
        int height {-1};
        std::optional<Payload> payload;

        bool isLeaf() const
        {
            return left < 0;
        }
    };

    std::vector<Node> nodes;
    int root {-1};
    int freeList {-1};
    std::size_t leafCount {0};

    int allocateNode()
    {
        if (freeList >= 0) {
            int nodeId = freeList;
            freeList = nodes[nodeId].parent;
            nodes[nodeId] = Node {};
            return nodeId;
        }
        nodes.push_back(Node {});
        return static_cast<int>(nodes.size() - 1);
    }

    void freeNode(int nodeId)
    {
        nodes[nodeId].payload.reset();
        nodes[nodeId].parent = freeList;
        nodes[nodeId].height = -1;
        nodes[nodeId].left = -1;
        nodes[nodeId].right = -1;
        freeList = nodeId;
    }

    void insertLeaf(int leaf)
    {
        if (root < 0) {
            root = leaf;
            nodes[root].parent = -1;
            return;
        }

        Aabb3d leafBox = nodes[leaf].box;
        int index = root;
        while (!nodes[index].isLeaf()) {
            int left = nodes[index].left;
            int right = nodes[index].right;

            double area = nodes[index].box.surfaceArea();
            Aabb3d combined = nodes[index].box.combined(leafBox);
            double combinedArea = combined.surfaceArea();
            double cost = 2.0 * combinedArea;
            double inheritanceCost = 2.0 * (combinedArea - area);

            double costLeft;
            if (nodes[left].isLeaf()) {
                costLeft = nodes[left].box.combined(leafBox).surfaceArea() + inheritanceCost;
            }
            else {
                double oldArea = nodes[left].box.surfaceArea();
                double newArea = nodes[left].box.combined(leafBox).surfaceArea();
                costLeft = (newArea - oldArea) + inheritanceCost;
            }

            double costRight;
            if (nodes[right].isLeaf()) {
                costRight = nodes[right].box.combined(leafBox).surfaceArea() + inheritanceCost;
            }
            else {
                double oldArea = nodes[right].box.surfaceArea();
                double newArea = nodes[right].box.combined(leafBox).surfaceArea();
                costRight = (newArea - oldArea) + inheritanceCost;
            }

            if (cost < costLeft && cost < costRight) {
                break;
            }

            index = costLeft < costRight ? left : right;
        }

        int sibling = index;
        int oldParent = nodes[sibling].parent;

        int newParent = allocateNode();
        nodes[newParent].parent = oldParent;
        nodes[newParent].box = leafBox.combined(nodes[sibling].box);
        nodes[newParent].height = nodes[sibling].height + 1;
        nodes[newParent].left = sibling;
        nodes[newParent].right = leaf;

        nodes[sibling].parent = newParent;
        nodes[leaf].parent = newParent;

        if (oldParent < 0) {
            root = newParent;
        }
        else if (nodes[oldParent].left == sibling) {
            nodes[oldParent].left = newParent;
        }
        else {
            nodes[oldParent].right = newParent;
        }

        index = nodes[leaf].parent;
        while (index >= 0) {
            index = balance(index);

            int left = nodes[index].left;
            int right = nodes[index].right;
            nodes[index].height = 1 + std::max(nodes[left].height, nodes[right].height);
            nodes[index].box = nodes[left].box.combined(nodes[right].box);

            index = nodes[index].parent;
        }
    }

    void removeLeaf(int leaf)
    {
        if (leaf == root) {
            root = -1;
            return;
        }

        int parent = nodes[leaf].parent;
        int grandParent = nodes[parent].parent;
        int sibling = nodes[parent].left == leaf ? nodes[parent].right : nodes[parent].left;

        if (grandParent < 0) {
            root = sibling;
            nodes[sibling].parent = -1;
            freeNode(parent);
            return;
        }

        if (nodes[grandParent].left == parent) {
            nodes[grandParent].left = sibling;
        }
        else {
            nodes[grandParent].right = sibling;
        }
        nodes[sibling].parent = grandParent;
        freeNode(parent);

        int index = grandParent;
        while (index >= 0) {
            index = balance(index);

            int left = nodes[index].left;
            int right = nodes[index].right;
            nodes[index].box = nodes[left].box.combined(nodes[right].box);
            nodes[index].height = 1 + std::max(nodes[left].height, nodes[right].height);

            index = nodes[index].parent;
        }
    }

    int balance(int iA)
    {
        Node& A = nodes[iA];
        if (A.isLeaf() || A.height < 2) {
            return iA;
        }

        int iB = A.left;
        int iC = A.right;
        Node& B = nodes[iB];
        Node& C = nodes[iC];

        int balance = C.height - B.height;
        if (balance > 1) {
            int iF = C.left;
            int iG = C.right;
            Node& F = nodes[iF];
            Node& G = nodes[iG];

            C.left = iA;
            C.parent = A.parent;
            A.parent = iC;

            if (C.parent < 0) {
                root = iC;
            }
            else if (nodes[C.parent].left == iA) {
                nodes[C.parent].left = iC;
            }
            else {
                nodes[C.parent].right = iC;
            }

            if (F.height > G.height) {
                C.right = iF;
                A.right = iG;
                G.parent = iA;
                A.box = B.box.combined(G.box);
                C.box = A.box.combined(F.box);

                A.height = 1 + std::max(B.height, G.height);
                C.height = 1 + std::max(A.height, F.height);
            }
            else {
                C.right = iG;
                A.right = iF;
                F.parent = iA;
                A.box = B.box.combined(F.box);
                C.box = A.box.combined(G.box);

                A.height = 1 + std::max(B.height, F.height);
                C.height = 1 + std::max(A.height, G.height);
            }
            return iC;
        }

        if (balance < -1) {
            int iD = B.left;
            int iE = B.right;
            Node& D = nodes[iD];
            Node& E = nodes[iE];

            B.left = iA;
            B.parent = A.parent;
            A.parent = iB;

            if (B.parent < 0) {
                root = iB;
            }
            else if (nodes[B.parent].left == iA) {
                nodes[B.parent].left = iB;
            }
            else {
                nodes[B.parent].right = iB;
            }

            if (D.height > E.height) {
                B.right = iD;
                A.left = iE;
                E.parent = iA;
                A.box = C.box.combined(E.box);
                B.box = A.box.combined(D.box);

                A.height = 1 + std::max(C.height, E.height);
                B.height = 1 + std::max(A.height, D.height);
            }
            else {
                B.right = iE;
                A.left = iD;
                D.parent = iA;
                A.box = C.box.combined(D.box);
                B.box = A.box.combined(E.box);

                A.height = 1 + std::max(C.height, D.height);
                B.height = 1 + std::max(A.height, E.height);
            }
            return iB;
        }

        return iA;
    }
};

}  // namespace Spatial
}  // namespace Part
