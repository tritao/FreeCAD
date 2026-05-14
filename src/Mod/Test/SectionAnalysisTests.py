# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the FreeCAD project.
################################################################################
#                                                                              #
#   © 2026 FreeCAD contributors                                                #
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public License as             #
#   published by the Free Software Foundation, either version 2.1              #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty                #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                    #
#   See the GNU Lesser General Public License for more details.                #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

import os
import tempfile
import unittest

import FreeCAD


class SectionAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("SectionAnalysisTests")
        self.file_name = os.path.join(tempfile.gettempdir(), "SectionAnalysisTests.FCStd")

    def tearDown(self):
        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None
        if os.path.exists(self.file_name):
            os.remove(self.file_name)

    def make_box(self, name="Box"):
        box = self.doc.addObject("Part::Box", name)
        box.Length = 10
        box.Width = 10
        box.Height = 10
        return box

    def make_clipping_plane(self, name="Clip", z=5):
        plane = self.doc.addObject("App::ClippingPlane", name)
        plane.Placement.Base = FreeCAD.Vector(0, 0, z)
        return plane

    def testCreateSectionAnalysis(self):
        obj = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        self.assertEqual(obj.TypeId, "Part::SectionAnalysis")
        self.assertEqual(list(obj.Sources), [])
        self.assertIsNone(obj.ClippingPlane)
        self.assertEqual(obj.ResultMode, "Both")
        self.assertTrue(obj.ShowHatching)
        self.assertEqual(obj.HatchSpacing, 2)
        self.assertEqual(obj.HatchAngle, 45)
        self.assertTrue(obj.HatchShape.isNull())

    def testSectionAnalysisRecomputeProducesEdges(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane
        analysis.ResultMode = "Edges"

        self.doc.recompute()

        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Edges), 0)

    def testSectionAnalysisRecomputeProducesFaces(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane
        analysis.ResultMode = "Faces"

        self.doc.recompute()

        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Faces), 0)

    def testSectionAnalysisRecomputeProducesFacesAndEdges(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane
        analysis.ResultMode = "Both"

        self.doc.recompute()

        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Faces), 0)
        self.assertGreater(len(analysis.Shape.Edges), 0)

    def testSaveRestoreSectionAnalysis(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane
        analysis.ResultMode = "Faces"
        self.doc.recompute()

        self.doc.saveAs(self.file_name)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.open(self.file_name)

        restored = self.doc.getObject("Analysis")
        self.assertIsNotNone(restored)
        self.assertEqual([obj.Name for obj in restored.Sources], ["Box"])
        self.assertEqual(restored.ClippingPlane.Name, "Clip")
        self.assertEqual(restored.ResultMode, "Faces")
        self.assertFalse(restored.Shape.isNull())
        self.assertGreater(len(restored.Shape.Faces), 0)

    def testDefaultModeProducesFacesAndEdges(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane

        self.doc.recompute()

        self.assertEqual(analysis.ResultMode, "Both")
        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Faces), 0)
        self.assertGreater(len(analysis.Shape.Edges), 0)
        self.assertFalse(analysis.HatchShape.isNull())
        self.assertGreater(len(analysis.HatchShape.Edges), 0)

    def testHatchingGeneratesSeparateHatchShape(self):
        box = self.make_box()
        plane = self.make_clipping_plane()
        analysis = self.doc.addObject("Part::SectionAnalysis", "Analysis")
        analysis.Sources = [box]
        analysis.ClippingPlane = plane
        analysis.ResultMode = "Faces"
        analysis.ShowHatching = True
        analysis.HatchSpacing = 2
        analysis.HatchAngle = 45

        self.doc.recompute()

        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Faces), 0)
        self.assertGreater(len(analysis.Shape.Edges), 0)
        self.assertFalse(analysis.HatchShape.isNull())
        self.assertEqual(len(analysis.HatchShape.Faces), 0)
        self.assertGreater(len(analysis.HatchShape.Edges), 0)
