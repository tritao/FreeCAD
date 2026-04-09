# --- src/Mod/BIM/bimcommands/BimJoin.py ---

# ***************************************************************************
# * (License Header as in other BIM files)                                  *
# ***************************************************************************

"""
BIM join command
This command joins different objects that can be joined, currently only Walls
"""

import math
import FreeCAD
import FreeCADGui
import Part
import Draft
import DraftGeomUtils

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate


class BIM_Join:
    """
    Base class for the different BIM Join commands. It contains the common
    logic to select objects, find their baselines, and determine the
    intersection point.
    """

    Supported = translate("BIM", "Supported objects: Walls")
    SupportedBaselines = translate(
        "BIM", "The Join command only supports walls with a single straight baseline"
    )

    def IsActive(self):
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v

    def Activated(self):
        """Executes the command's main logic."""
        sel = FreeCADGui.Selection.getSelection()

        if len(sel) != 2:
            FreeCAD.Console.PrintError(
                translate("BIM", "The BIM Join command needs exactly 2 objects selected.") + "\n"
            )
            return

        baselines = []
        for obj in sel:
            baseline = self._get_join_baseline(obj)
            if baseline:
                baselines.append(baseline)
            else:
                return

        # Find the best intersection point and which ends of the walls are involved.
        intersection, end_name1, end_name2 = self.find_best_intersection(baselines[0], baselines[1])

        if not intersection:
            FreeCAD.Console.PrintError(
                translate("BIM", "The baselines of the selected walls do not intersect.") + "\n"
            )
            return

        # Let the specific join command calculate the cutting planes.
        # This method is overridden by the subclasses.
        plane1_placement, plane2_placement = self.calculate_cutting_planes(
            baselines[0], baselines[1], intersection, sel[0].Width.Value, sel[1].Width.Value
        )

        # Apply the calculated placements to the wall objects.
        doc = sel[0].Document
        doc.openTransaction(translate("BIM", "Join objects"))

        if plane1_placement and end_name1:
            # The placement is calculated in global coordinates. We need to store it
            # relative to the wall's own placement.
            relative_placement1 = sel[0].Placement.inverse().multiply(plane1_placement)
            setattr(sel[0], "Ending" + end_name1, relative_placement1)

        if plane2_placement and end_name2:
            relative_placement2 = sel[1].Placement.inverse().multiply(plane2_placement)
            setattr(sel[1], "Ending" + end_name2, relative_placement2)

        doc.commitTransaction()
        doc.recompute()

    def find_best_intersection(self, line1, line2):
        """
        Finds the intersection point of two lines and determines which
        end of each line is closest to that intersection.
        """
        edge1 = self._get_single_straight_edge(line1)
        edge2 = self._get_single_straight_edge(line2)
        if not edge1 or not edge2:
            return None, None, None

        intersections = DraftGeomUtils.findIntersection(
            edge1, edge2, infinite1=True, infinite2=True
        )
        if not intersections:
            return None, None, None

        intersection_point = intersections[0]

        # Determine which end of line1 is closer to the intersection
        dist_start1 = intersection_point.distanceToPoint(line1.Vertexes[0].Point)
        dist_end1 = intersection_point.distanceToPoint(line1.Vertexes[-1].Point)
        end_name1 = "Start" if dist_start1 < dist_end1 else "End"

        # Determine which end of line2 is closer to the intersection
        dist_start2 = intersection_point.distanceToPoint(line2.Vertexes[0].Point)
        dist_end2 = intersection_point.distanceToPoint(line2.Vertexes[-1].Point)
        end_name2 = "Start" if dist_start2 < dist_end2 else "End"

        return intersection_point, end_name1, end_name2

    def _get_single_straight_edge(self, baseline):
        """Returns the unique straight edge for a joinable baseline."""
        if not baseline:
            return None

        edges = getattr(baseline, "Edges", None)
        if not edges or len(edges) != 1:
            return None

        edge = edges[0]
        curve = getattr(edge, "Curve", None)
        if getattr(curve, "TypeId", "") != "Part::GeomLine":
            return None

        return edge

    def _report_unsupported_baseline(self, obj):
        FreeCAD.Console.PrintError(self.SupportedBaselines + f": {obj.Label}\n")

    def _get_join_baseline(self, obj):
        """Returns the baseline edge for a supported wall join."""
        if not (hasattr(obj, "Proxy") and hasattr(obj.Proxy, "get_baseline")):
            FreeCAD.Console.PrintError(
                translate("BIM", "This object is not supported by the Join command")
                + f": {obj.Label}\n"
            )
            return None

        baseline = obj.Proxy.get_baseline(obj)
        edge = self._get_single_straight_edge(baseline)
        if not edge:
            self._report_unsupported_baseline(obj)
            return None

        return edge

    def calculate_cutting_planes(self, _baseline1, _baseline2, _intersection, _width1, _width2):
        """
        Abstract placeholder method to be overridden by subclasses.

        This method defines the interface for calculating join geometry but
        should never be called directly on the base class.
        """
        raise NotImplementedError("This join type is not implemented.")


class BIM_Join_Miter(BIM_Join):
    """The BIM_Join_Miter command creates a miter joint between two objects."""

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Miter",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Miter", "Miter joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Miter", "Creates a miter joint between two supported objects."
            ),
        }

    def calculate_cutting_planes(self, baseline1, baseline2, intersection, width1, width2):
        # Determine the direction vectors of the walls, pointing AWAY from the intersection.

        dir1 = baseline1.Vertexes[-1].Point.sub(baseline1.Vertexes[0].Point)
        if intersection.distanceToPoint(baseline1.Vertexes[0].Point) > intersection.distanceToPoint(
            baseline1.Vertexes[-1].Point
        ):
            dir1.multiply(-1)

        dir2 = baseline2.Vertexes[-1].Point.sub(baseline2.Vertexes[0].Point)
        if intersection.distanceToPoint(baseline2.Vertexes[0].Point) > intersection.distanceToPoint(
            baseline2.Vertexes[-1].Point
        ):
            dir2.multiply(-1)

        # The bisector of the angle between the two direction vectors is the normal of our cutting plane.
        bisector_normal = (dir1.normalize() + dir2.normalize()).normalize()

        # The cutting plane's local X-axis can be aligned with one of the walls.
        # The local Y-axis is the global Z direction (assuming walls are upright).
        axis_x = dir1.normalize()
        axis_y = FreeCAD.Vector(0, 0, 1)
        # The local Z-axis (the plane's normal) is perpendicular to the bisector.
        axis_z = bisector_normal.cross(axis_y).normalize()

        # Create the placement for the cutting plane.
        rot = FreeCAD.Rotation(axis_x, axis_y, axis_z, "ZXY")
        plane1 = FreeCAD.Placement(intersection, rot)

        # The second plane is the same, but rotated 180 degrees around its Y-axis (the world Z).
        plane2 = plane1.copy()
        plane2.rotate(intersection, FreeCAD.Vector(0, 0, 1), 180)

        return plane1, plane2


class BIM_Join_Tee(BIM_Join):
    """The BIM_Join_Tee command creates a tee joint between two objects."""

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Tee",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Tee", "Tee joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Tee", "Creates a tee joint between two supported objects."
            ),
        }

    def Activated(self):
        """Overridden Activated method for Tee joins that performs role detection."""
        sel = FreeCADGui.Selection.getSelection()
        if len(sel) != 2:
            FreeCAD.Console.PrintError(
                translate("BIM", "The BIM Join command needs exactly 2 objects selected.") + "\n"
            )
            return

        baseline1 = self._get_join_baseline(sel[0])
        baseline2 = self._get_join_baseline(sel[1])
        if not baseline1 or not baseline2:
            return

        intersection, _, _ = self.find_best_intersection(baseline1, baseline2)
        if not intersection:
            FreeCAD.Console.PrintError(
                translate("BIM", "The baselines of the selected walls do not intersect.") + "\n"
            )
            return

        # Role Detection Logic
        dist_to_end1 = min(
            intersection.distanceToPoint(baseline1.Vertexes[0].Point),
            intersection.distanceToPoint(baseline1.Vertexes[-1].Point),
        )
        dist_to_end2 = min(
            intersection.distanceToPoint(baseline2.Vertexes[0].Point),
            intersection.distanceToPoint(baseline2.Vertexes[-1].Point),
        )

        if dist_to_end1 < dist_to_end2:
            stem_wall, top_wall = sel[0], sel[1]
            stem_line, top_line = baseline1, baseline2
        else:
            stem_wall, top_wall = sel[1], sel[0]
            stem_line, top_line = baseline2, baseline1

        if intersection.distanceToPoint(stem_line.Vertexes[0].Point) < intersection.distanceToPoint(
            stem_line.Vertexes[-1].Point
        ):
            end_name_to_trim = "Start"
        else:
            end_name_to_trim = "End"

        plane_placement = self.calculate_cutting_plane_for_tee(
            stem_wall, top_wall, stem_line, top_line, intersection
        )

        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Tee Join")

        if plane_placement:
            relative_placement = stem_wall.Placement.inverse().multiply(plane_placement)
            setattr(stem_wall, "Ending" + end_name_to_trim, relative_placement)

        doc.commitTransaction()
        doc.recompute()

    def calculate_cutting_plane_for_tee(
        self, stem_wall, top_wall, stem_line, top_line, intersection
    ):
        """
        Calculates the correctly positioned and oriented cutting plane for the stem wall in a Tee join.
        """
        plane_normal = DraftGeomUtils.vec(stem_line).normalize()
        rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), plane_normal)

        top_dir = DraftGeomUtils.vec(top_line).normalize()
        offset_dir = top_dir.cross(FreeCAD.Vector(0, 0, 1))

        center_stem = (stem_line.Vertexes[0].Point + stem_line.Vertexes[-1].Point) / 2
        vec_to_stem = center_stem - intersection

        if offset_dir.dot(vec_to_stem) < 0:
            offset_dir.multiply(-1)

        offset_distance = top_wall.Width.Value / 2.0
        offset_vector = offset_dir * offset_distance

        plane_position = intersection.add(offset_vector)

        # Add a small overlap to avoid co-planar boolean failure by moving
        # the plane slightly into the volume that will be kept.
        overlap_vector = vec_to_stem.normalize() * 1e-6
        plane_position = plane_position.add(overlap_vector)

        return FreeCAD.Placement(plane_position, rot)


class BIM_Join_Butt(BIM_Join):
    """The BIM_Join_Butt command creates a butt joint between two objects."""

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Butt",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Butt", "Butt joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Butt", "Creates a butt joint between two supported objects."
            ),
        }

    def calculate_cutting_planes(self, baseline1, baseline2, intersection, width1, width2):
        # Wall 2 is trimmed flush with the face of Wall 1.
        # Wall 1 is trimmed to extend and cap the end of Wall 2.

        # --- Calculate plane for Wall 2 ---
        # The plane is aligned with the baseline of Wall 1.
        axis_x_2 = DraftGeomUtils.vec(baseline1)
        axis_y_2 = FreeCAD.Vector(0, 0, 1)
        axis_z_2 = axis_x_2.cross(axis_y_2).normalize()
        rot2 = FreeCAD.Rotation(axis_x_2, axis_y_2, axis_z_2, "ZXY")
        plane2 = FreeCAD.Placement(intersection, rot2)

        # --- Calculate plane for Wall 1 ---
        # This plane is aligned with baseline2, but offset by half of wall2's width.
        dir1 = DraftGeomUtils.vec(baseline1).normalize()
        dir2 = DraftGeomUtils.vec(baseline2).normalize()

        # The offset direction is perpendicular to baseline1.
        offset_dir = dir1.cross(FreeCAD.Vector(0, 0, 1))

        # Check if the offset direction is correct.
        if offset_dir.dot(dir2) < 0:
            offset_dir.multiply(-1)

        offset_vector = offset_dir * (width2 / 2.0)
        offset_intersection = intersection.add(offset_vector)

        axis_x_1 = dir2
        axis_y_1 = FreeCAD.Vector(0, 0, 1)
        axis_z_1 = axis_x_1.cross(axis_y_1).normalize()
        rot1 = FreeCAD.Rotation(axis_x_1, axis_y_1, axis_z_1, "ZXY")
        plane1 = FreeCAD.Placement(offset_intersection, rot1)

        return plane1, plane2


# Register the commands with FreeCAD's GUI
FreeCADGui.addCommand("BIM_Join_Miter", BIM_Join_Miter())
FreeCADGui.addCommand("BIM_Join_Tee", BIM_Join_Tee())
FreeCADGui.addCommand("BIM_Join_Butt", BIM_Join_Butt())
