# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2025 Furgo                                              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

import Arch
import ArchRepresentation
import ArchSectionProjection
import ArchSectionPlane
import TechDrawBIM
import Draft
import os
import FreeCAD as App
import Part
from bimtests import TestArchBase


class TestArchSectionPlane(TestArchBase.TestArchBase):

    def _makeBox(self, length=1000, width=2000, height=3000):
        box = self.document.addObject("Part::Box", "SectionPlaneFitBox")
        box.Length = length
        box.Width = width
        box.Height = height
        self.document.recompute()
        return box

    def test_makeSectionPlane(self):
        """Test the makeSectionPlane function."""
        operation = "Testing makeSectionPlane function"
        self.printTestMessage(operation)

        section_plane = Arch.makeSectionPlane(name="TestSectionPlane")
        self.assertIsNotNone(
            section_plane, "makeSectionPlane failed to create a section plane object."
        )
        self.assertEqual(
            section_plane.Label, "TestSectionPlane", "Section plane label is incorrect."
        )

    def testRepresentationRequestUsesArbitrarySectionFrame(self):
        """Section planes expose the canonical renderer-neutral request."""

        section_plane = Arch.makeSectionPlane(name="RepresentationSection")
        section_plane.Placement = App.Placement(
            App.Vector(100, 200, 300), App.Rotation(App.Vector(0, 1, 0), 35)
        )
        section_plane.Depth = 2500
        self.document.recompute()

        request = section_plane.Proxy.getRepresentationRequest(section_plane)

        self.assertIsInstance(request, ArchRepresentation.RepresentationRequest)
        self.assertIs(request.purpose, ArchRepresentation.RepresentationPurpose.SECTION)
        self.assertEqual(request.reference_frame, section_plane.Placement)
        self.assertEqual(request.projection_range, (0.0, 2500.0))

        section_plane.Purpose = "Elevation"
        elevation = section_plane.Proxy.getRepresentationRequest(section_plane)
        self.assertIs(
            elevation.purpose,
            ArchRepresentation.RepresentationPurpose.ELEVATION,
        )
        self.assertEqual(elevation.projection_range, (-2500.0, 0.0))

    def testProjectionGeometryCharacterizesCutAndForwardShapes(self):
        """Neutral projection preserves the established section split."""

        box = self._makeBox(length=1000, width=1000, height=1000)
        cutplane = Part.makePlane(
            2000,
            2000,
            App.Vector(500, -500, -500),
            App.Vector(1, 0, 0),
        )

        result = ArchSectionPlane.getCutShapes(
            (box,),
            cutplane,
            True,
            clip=False,
            joinArch=False,
            showHidden=True,
        )

        visible, hidden, cut, _face, _front, _behind = result
        self.assertTrue(visible)
        self.assertTrue(hidden)
        self.assertEqual(1, len(cut))
        self.assertAlmostEqual(1000000.0, cut[0].Area)

    def testProjectionGeometryRetainsPerObjectCutSources(self):
        """Grouped section faces retain their originating document object."""

        box = self._makeBox(length=1000, width=1000, height=1000)
        cutplane = Part.makePlane(
            2000,
            2000,
            App.Vector(500, -500, -500),
            App.Vector(1, 0, 0),
        )

        result = ArchSectionPlane.getCutShapes(
            (box,),
            cutplane,
            True,
            clip=False,
            joinArch=False,
            showHidden=False,
            groupSshapesByObject=True,
        )

        object_cut_shapes = result[-1]
        self.assertEqual(1, len(object_cut_shapes))
        self.assertIs(box, object_cut_shapes[0][0])
        self.assertEqual(1, len(object_cut_shapes[0][1]))

    def testElevationProjectionProducesMappedPlanarLines(self):
        """Elevation projection is 2D while retaining the BIM source."""

        box = self._makeBox(length=1000, width=200, height=1200)
        rotation = App.Rotation(
            App.Vector(1, 0, 0),
            App.Vector(0, 0, 1),
            App.Vector(0, -1, 0),
            "ZXY",
        )
        frame = App.Placement(App.Vector(500, -100, 600), rotation)
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
            reference_frame=frame,
            projection_range=(-400.0, 0.0),
            target_offset=0.0,
        )

        representation = ArchSectionProjection.project_elevation_object(box, request)

        self.assertTrue(representation.projected_geometry)
        self.assertTrue(representation.source_mappings)
        self.assertTrue(
            all(mapping.source is box for mapping in representation.source_mappings)
        )
        for polyline in representation.projected_geometry:
            for point in polyline:
                self.assertAlmostEqual(0.0, frame.inverse().multVec(point).z)

    def testElevationProjectionHonorsDepthRange(self):
        box = self._makeBox(length=1000, width=200, height=1200)
        frame = App.Placement(App.Vector(0, 0, -1000), App.Rotation())
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
            reference_frame=frame,
            projection_range=(-100.0, 0.0),
        )

        representation = ArchSectionProjection.project_elevation_object(box, request)

        self.assertFalse(representation.projected_geometry)

    def testElevationScopeRemovesEdgesHiddenBehindNearerObjects(self):
        front = self._makeBox(length=1000, width=1200, height=50)
        front.Placement.Base.z = -100
        back = self._makeBox(length=1000, width=1200, height=50)
        back.Placement.Base.z = -300
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
            reference_frame=App.Placement(),
            projection_range=(-500.0, 0.0),
        )
        self.document.recompute()

        representations = ArchSectionProjection.project_elevation_scope(
            (front, back), request
        )

        self.assertTrue(representations[front].projected_geometry)
        self.assertFalse(representations[back].projected_geometry)
        self.assertTrue(
            all(
                mapping.source is front
                for mapping in representations[front].source_mappings
            )
        )

    def testElevationScopeProjectionIsReusedUntilDocumentInvalidation(self):
        from bimviews import representation_cache

        box = self._makeBox(length=1000, width=1200, height=50)
        box.Placement.Base.z = -100
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
            reference_frame=App.Placement(),
            projection_range=(-500.0, 0.0),
        )
        self.document.recompute()
        representation_cache.invalidate_document(self.document)
        original_project = ArchSectionProjection._project_visible_edges
        calls = []

        def capture_project(shape):
            calls.append(shape)
            return original_project(shape)

        ArchSectionProjection._project_visible_edges = capture_project
        try:
            ArchSectionProjection.project_elevation_scope((box,), request)
            first_count = len(calls)
            ArchSectionProjection.project_elevation_scope((box,), request)
            self.assertEqual(first_count, len(calls))
            representation_cache.invalidate_document(self.document)
            ArchSectionProjection.project_elevation_scope((box,), request)
        finally:
            ArchSectionProjection._project_visible_edges = original_project

        self.assertGreater(first_count, 0)
        self.assertGreater(len(calls), first_count)

    def testTechDrawUsesSemanticRepresentationWithoutLegacyCutShapes(self):
        """The production section path consumes provider geometry directly."""

        wall = Arch.makeWall(length=3000, width=200, height=3000)
        section_plane = Arch.makeSectionPlane([wall])
        section_plane.Placement = App.Placement(
            App.Vector(1500, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90)
        )
        self.document.recompute()
        calls = []
        original_project = TechDrawBIM.project_representation_to_svg
        original_cut_shapes = ArchSectionPlane.getCutShapes

        def capture_project(
            representation, direction, collection="projected_geometry", **styles
        ):
            calls.append(collection)
            return original_project(
                representation, direction, collection=collection, **styles
            )

        def fail_legacy_cut_shapes(*args, **kwargs):
            raise AssertionError("semantic TechDraw must not build legacy cut shapes")

        TechDrawBIM.project_representation_to_svg = capture_project
        ArchSectionPlane.getCutShapes = fail_legacy_cut_shapes
        try:
            svg = ArchSectionPlane.getSVG(
                section_plane, techdraw=True, renderMode="Wireframe"
            )
        finally:
            TechDrawBIM.project_representation_to_svg = original_project
            ArchSectionPlane.getCutShapes = original_cut_shapes

        self.assertTrue(svg)
        self.assertIn("cut_geometry", calls)

    def testTechDrawElevationUsesSharedScopeProjection(self):
        front = self._makeBox(length=1000, width=1200, height=50)
        front.Placement.Base.z = -100
        back = self._makeBox(length=1000, width=1200, height=50)
        back.Placement.Base.z = -300
        section_plane = Arch.makeSectionPlane([front, back])
        section_plane.Purpose = "Elevation"
        section_plane.Depth = 500
        self.document.recompute()
        original_cut_shapes = ArchSectionPlane.getCutShapes

        def fail_legacy_cut_shapes(*args, **kwargs):
            raise AssertionError("elevation TechDraw must use the shared projection")

        ArchSectionPlane.getCutShapes = fail_legacy_cut_shapes
        try:
            svg = ArchSectionPlane.getSVG(
                section_plane, techdraw=True, renderMode="Wireframe"
            )
        finally:
            ArchSectionPlane.getCutShapes = original_cut_shapes

        self.assertTrue(svg)

    def testTechDrawConvertsSemanticPolylinesToProjectionGeometry(self):
        """Semantic cut lines remain directly consumable by TechDraw."""

        representation = ArchRepresentation.BIMRepresentation()
        cut_line = (
            App.Vector(0, 0, 0),
            App.Vector(100, 75, 0),
        )
        representation.add_geometry(
            "projected_geometry", cut_line, "WallJointCutLine"
        )

        geometry = TechDrawBIM._geometry(representation, "projected_geometry")

        self.assertFalse(geometry.isNull())
        self.assertEqual(1, len(geometry.Edges))
        self.assertEqual(2, len(geometry.Vertexes))

    def testSectionPlaneFitUsesLocalAxesAfterRotateY(self):
        """Resize-to-fit dimensions follow the rotated section plane axes."""

        box = self._makeBox()
        placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))

        length, height = ArchSectionPlane.getSectionPlaneFit([box], placement)

        self.assertAlmostEqual(length, 3300)
        self.assertAlmostEqual(height, 2300)

    def testSectionPlaneFitCombinesMultipleObjects(self):
        """Resize-to-fit covers the combined bounds of all objects."""

        box = self._makeBox()
        second_box = self._makeBox()
        second_box.Placement.Base = App.Vector(2000, 500, -100)
        self.document.recompute()

        length, height = ArchSectionPlane.getSectionPlaneFit([box, second_box], App.Placement())

        self.assertAlmostEqual(length, 3300)
        self.assertAlmostEqual(height, 2800)

    def testSectionPlaneFitUsesLocalAxesAfterRotateZ(self):
        """Resize-to-fit handles in-plane rotations without swapping axes."""

        box = self._makeBox()
        placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))

        length, height = ArchSectionPlane.getSectionPlaneFit([box], placement)

        self.assertAlmostEqual(length, 2200)
        self.assertAlmostEqual(height, 1200)

    def testSectionPlaneCenterRecentersLocalBounds(self):
        """Recenter moves the placement base to the local bound-box center."""

        box = self._makeBox()
        placement = App.Placement(App.Vector(500, -250, 125), App.Rotation(App.Vector(0, 1, 0), 90))
        center = ArchSectionPlane.getSectionPlaneCenter([box], placement)
        recentered = App.Placement(center, placement.Rotation)

        local_boundbox = ArchSectionPlane.getSectionPlaneLocalBoundBox([box], recentered)

        self.assertAlmostEqual(local_boundbox.Center.x, 0)
        self.assertAlmostEqual(local_boundbox.Center.y, 0)
        self.assertAlmostEqual(local_boundbox.Center.z, 0)

    def testTechDrawViewGeneration(self):
        """Tests the whole TD view generation workflow"""

        # Create a few objects
        points = [App.Vector(0.0, 0.0, 0.0), App.Vector(2000.0, 0.0, 0.0)]
        line = Draft.make_wire(points)
        wall = Arch.makeWall(line, height=2000)
        wpl = App.Placement(App.Vector(500, 0, 1500), App.Vector(1, 0, 0), -90)
        win = Arch.makeWindowPreset(
            "Fixed",
            width=1000.0,
            height=1000.0,
            h1=50.0,
            h2=50.0,
            h3=50.0,
            w1=100.0,
            w2=50.0,
            o1=0.0,
            o2=50.0,
            placement=wpl,
        )
        win.Hosts = [wall]
        profile = Arch.makeProfile([169, "HEA", "HEA100", "H", 100.0, 96.0, 5.0, 8.0])
        column = Arch.makeStructure(profile, height=2000.0)
        column.Profile = "HEA100"
        column.Placement.Base = App.Vector(500.0, 600.0, 0.0)
        level = Arch.makeFloor()
        level.addObjects([wall, column])
        App.ActiveDocument.recompute()

        # Create a drawing view
        section = Arch.makeSectionPlane(level)
        drawing = Arch.make2DDrawing()
        view = Draft.make_shape2dview(section)
        cut = Draft.make_shape2dview(section)
        cut.InPlace = False
        cut.ProjectionMode = "Cutfaces"
        drawing.addObjects([view, cut])
        App.ActiveDocument.recompute()

        # Create a TD page
        tpath = os.path.join(
            App.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO", "A3_Landscape_blank.svg"
        )
        page = App.ActiveDocument.addObject("TechDraw::DrawPage", "Page")
        template = App.ActiveDocument.addObject("TechDraw::DrawSVGTemplate", "Template")
        template.Template = tpath
        page.Template = template
        view = App.ActiveDocument.addObject("TechDraw::DrawViewDraft", "DraftView")
        view.Source = drawing
        page.addView(view)
        view.Scale = 1.0
        view.X = "20cm"
        view.Y = "15cm"
        App.ActiveDocument.recompute()
        assert True

    def testShape2DViewGeneration(self):
        """Tests Draft_Shape2DView face with hole creation"""

        # Create a wall based on a clock-wise wire starting at the lower left corner.
        # Such a wire would previously result in an invalid face in the Shape2DView.
        wire = Draft.make_wire(
            [
                App.Vector(0, 0, 0),
                App.Vector(0, 1000, 0),
                App.Vector(2000, 1000, 0),
                App.Vector(2000, 0, 0),
            ],
            closed=True,
        )
        wire.MakeFace = False
        wall = Arch.makeWall(wire, height=3000, width=200)
        App.ActiveDocument.recompute()

        section = Arch.makeSectionPlane(wall)
        shp_view = Draft.make_shape2dview(section)
        shp_view.InPlace = False
        shp_view.ProjectionMode = "Cutfaces"
        App.ActiveDocument.recompute()

        face = shp_view.Shape.Faces[0]
        self.assertTrue(face.isValid())

        area_expected = 1200 * 2200 - 800 * 1800
        self.assertAlmostEqual(face.Area, area_expected)
