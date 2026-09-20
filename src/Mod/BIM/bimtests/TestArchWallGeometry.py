# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association
# SPDX-FileNotice: Part of the FreeCAD project.
################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public                       #
#   License as published by the FreeCAD Project Association, either version 2 #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Lesser General Public License for more details.                        #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""Direct tests for the wall path and section value objects."""

import ArchWallGeometry
import ArchWallExact
import FreeCAD as App
import Part

from bimtests import TestArchBase


class TestArchWallGeometry(TestArchBase.TestArchBase):
    """Exercise the standalone wall path and section geometry contracts."""

    def test_wall_path_operations_use_finite_segments(self):
        """Path queries use ordered finite endpoints and global geometry."""
        path = ArchWallGeometry.WallPath(
            Part.makeLine(App.Vector(0, 0, 0), App.Vector(1000, 0, 0)),
            App.Vector(0, 0, 1),
        )
        self.assertTrue(path.contains_point(App.Vector(1000.00005, 0, 0)))
        self.assertFalse(path.contains_point(App.Vector(1000.2, 0, 0)))
        self.assertFalse(path.contains_point(App.Vector(500, 0.2, 0)))
        self.assertEqual(path.nearest_end_name(App.Vector(500, 0, 0)), "End")
        self.assertTrue(path.lateral_direction().isEqual(App.Vector(0, -1, 0), 1e-6))

        crossing = ArchWallGeometry.WallPath(
            Part.makeLine(App.Vector(500, -500, 0), App.Vector(500, 500, 0)),
            App.Vector(0, 0, 1),
        )
        point, end_a, end_b = ArchWallGeometry.find_path_intersection(path, crossing)
        self.assertTrue(point.isEqual(App.Vector(500, 0, 0), 1e-6))
        self.assertEqual((end_a, end_b), ("End", "End"))

    def test_wall_path_consumes_immutable_oriented_baseline(self):
        """WallPath uses explicit endpoint orientation from WallBaseline."""
        baseline = ArchWallGeometry.WallBaseline(
            Part.makeLine(App.Vector(1000, 0, 0), App.Vector(0, 0, 0)),
            App.Vector(0, 0, 1),
            App.Vector(1000, 0, 0),
            App.Vector(0, 0, 0),
        )
        path = ArchWallGeometry.WallPath.from_baseline(baseline)
        self.assertTrue(path.start_point.isEqual(baseline.start_point, 1e-6))
        self.assertTrue(path.end_point.isEqual(baseline.end_point, 1e-6))
        with self.assertRaises(AttributeError):
            baseline.start_point = App.Vector()

    def test_wall_path_rejects_invalid_values(self):
        """WallPath rejects non-geometry, degenerate, and parallel inputs."""
        with self.assertRaises(TypeError):
            ArchWallGeometry.WallPath(None, App.Vector(0, 0, 1))
        with self.assertRaises((ValueError, Part.OCCError)):
            ArchWallGeometry.WallPath(
                Part.makeLine(App.Vector(0, 0, 0), App.Vector(0, 0, 0)),
                App.Vector(0, 0, 1),
            )
        with self.assertRaises(ValueError):
            ArchWallGeometry.WallPath(
                Part.makeLine(App.Vector(0, 0, 0), App.Vector(1000, 0, 0)),
                App.Vector(1, 0, 0),
            )

    def test_wall_section_is_immutable_resolved_data(self):
        """WallSection exposes resolved extents without mutable state."""
        section = ArchWallGeometry.WallSection(
            (
                ArchWallGeometry.WallSectionLayer(100, -150, -50),
                ArchWallGeometry.WallSectionLayer(-50, -50, 0),
                ArchWallGeometry.WallSectionLayer(200, 0, 200),
            )
        )

        self.assertEqual(section.y_min, -150)
        self.assertEqual(section.y_max, 200)
        self.assertEqual(len(section.visible_layers), 2)
        self.assertEqual(section.offset_towards(App.Vector(1, 0, 0), App.Vector(1, 0, 0)), 150)
        self.assertEqual(section.offset_towards(App.Vector(1, 0, 0), App.Vector(-1, 0, 0)), -200)
        with self.assertRaises(AttributeError):
            section.layers = ()

    def test_wall_geometry_recipe_derives_trimmed_open_plan_regions(self):
        """One shared wall recipe derives Plan regions without OCCT booleans."""

        section = ArchWallGeometry.WallSection(
            (ArchWallGeometry.WallSectionLayer(200, -100, 100),)
        )
        recipe = ArchWallGeometry.WallGeometryRecipe(
            axis_start=App.Vector(0, 0, 0),
            axis_end=App.Vector(1000, 0, 0),
            lateral=App.Vector(0, 1, 0),
            section=section,
            z_min=0,
            z_max=3000,
            trim_planes=(
                ArchWallGeometry.WallTrimPlane(
                    "End", App.Vector(900, 0, 0), App.Vector(1, 0, 0)
                ),
            ),
            openings=(
                ArchWallGeometry.WallOpeningRecipe(
                    source=None,
                    u_min=300,
                    u_max=500,
                    v_min=-100,
                    v_max=100,
                    z_min=0,
                    z_max=2000,
                ),
            ),
        )

        boundaries = recipe.plan_boundaries(25, recipe.opening_intervals_at(25))
        self.assertEqual(2, len(boundaries))
        self.assertEqual(
            [(0, 300), (500, 900)],
            [
                (min(point.x for point in boundary), max(point.x for point in boundary))
                for boundary in boundaries
            ],
        )
        self.assertTrue(all(point.z == 25 for boundary in boundaries for point in boundary))
        self.assertEqual((), recipe.opening_intervals_at(2500))

    def test_wall_geometry_recipe_derives_closed_viewport_mesh(self):
        """A trimmed straight-wall recipe produces a closed semantic prism mesh."""

        section = ArchWallGeometry.WallSection(
            (ArchWallGeometry.WallSectionLayer(200, -100, 100),)
        )
        recipe = ArchWallGeometry.WallGeometryRecipe(
            axis_start=App.Vector(0, 0, 0),
            axis_end=App.Vector(1000, 0, 0),
            lateral=App.Vector(0, 1, 0),
            section=section,
            z_min=0,
            z_max=3000,
            trim_planes=(
                ArchWallGeometry.WallTrimPlane(
                    "End", App.Vector(900, 0, 0), App.Vector(1, 0, 0)
                ),
            ),
        )

        mesh = recipe.viewport_mesh()
        self.assertIsNotNone(mesh)
        self.assertTrue(mesh.is_closed)
        self.assertEqual((0, -100, 0, 900, 100, 3000), mesh.bounds)
        self.assertAlmostEqual(540000000, mesh.volume)
        self.assertEqual(len(mesh.triangles), len(mesh.triangle_roles))
        self.assertEqual({"Bottom", "Top", "SideMin", "SideMax", "End"}, set(mesh.triangle_roles))

        self.assertIsNone(
            ArchWallGeometry.WallGeometryRecipe(
                axis_start=recipe.axis_start,
                axis_end=recipe.axis_end,
                lateral=recipe.lateral,
                section=recipe.section,
                z_min=recipe.z_min,
                z_max=recipe.z_max,
                openings=(
                    ArchWallGeometry.WallOpeningRecipe(
                        None, 200, 400, -100, 100, 0, 2000
                    ),
                ),
            ).viewport_mesh()
        )

    def test_exact_compiler_extrudes_perforated_wall_profile(self):
        """The exact compiler creates and classifies one perforated extrusion."""

        section = ArchWallGeometry.WallSection(
            (ArchWallGeometry.WallSectionLayer(200, -100, 100),)
        )
        opening_source = object()
        recipe = ArchWallGeometry.WallGeometryRecipe(
            axis_start=App.Vector(0, 0, 0),
            axis_end=App.Vector(3000, 0, 0),
            lateral=App.Vector(0, 1, 0),
            section=section,
            z_min=0,
            z_max=2500,
            openings=(
                ArchWallGeometry.WallOpeningRecipe(
                    opening_source, 900, 1700, -100, 100, 700, 1900
                ),
            ),
        )

        compilation = ArchWallExact.compile_wall_recipe(recipe)
        self.assertIsNotNone(compilation)
        self.assertTrue(compilation.shape.isValid())
        self.assertEqual(1, len(compilation.shape.Solids))
        self.assertAlmostEqual(
            (3000 * 2500 - 800 * 1200) * 200,
            compilation.shape.Volume,
            delta=1e-3,
        )
        roles = [item.role for item in compilation.face_roles]
        self.assertEqual(2, roles.count("SideMin") + roles.count("SideMax"))
        self.assertIn("OpeningSill", roles)
        self.assertIn("OpeningHead", roles)
        self.assertEqual(2, roles.count("OpeningJamb"))
        self.assertAlmostEqual(14560000.0, compilation.vertical_area)
        self.assertAlmostEqual(600000.0, compilation.horizontal_area)
        self.assertAlmostEqual(6400.0, compilation.perimeter_length)
        self.assertTrue(
            all(
                item.source is opening_source
                for item in compilation.face_roles
                if item.role.startswith("Opening")
            )
        )

        trimmed = ArchWallGeometry.WallGeometryRecipe(
            axis_start=recipe.axis_start,
            axis_end=recipe.axis_end,
            lateral=recipe.lateral,
            section=recipe.section,
            z_min=recipe.z_min,
            z_max=recipe.z_max,
            trim_planes=(
                ArchWallGeometry.WallTrimPlane(
                    "End", App.Vector(2900, 0, 0), App.Vector(1, 0, 0)
                ),
            ),
        )
        trimmed_compilation = ArchWallExact.compile_wall_recipe(trimmed)
        self.assertIsNotNone(trimmed_compilation)
        self.assertTrue(trimmed_compilation.shape.isValid())
        self.assertAlmostEqual(2900 * 200 * 2500, trimmed_compilation.shape.Volume)
        self.assertIn(
            "EndEnd", [item.role for item in trimmed_compilation.face_roles]
        )

        nonvertical = ArchWallGeometry.WallGeometryRecipe(
            axis_start=recipe.axis_start,
            axis_end=recipe.axis_end,
            lateral=recipe.lateral,
            section=recipe.section,
            z_min=recipe.z_min,
            z_max=recipe.z_max,
            trim_planes=(
                ArchWallGeometry.WallTrimPlane(
                    "End", App.Vector(2900, 0, 0), App.Vector(1, 0, 1)
                ),
            ),
        )
        self.assertIsNone(ArchWallExact.compile_wall_recipe(nonvertical))
