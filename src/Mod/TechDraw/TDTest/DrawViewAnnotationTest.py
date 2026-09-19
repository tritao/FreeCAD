# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD
import unittest
from .TechDrawTestUtilities import createPageWithSVGTemplate


class DrawViewAnnotationTest(unittest.TestCase):
    def setUp(self):
        """Creates a page"""
        FreeCAD.newDocument("TDAnno")
        FreeCAD.setActiveDocument("TDAnno")
        FreeCAD.ActiveDocument = FreeCAD.getDocument("TDAnno")
        self.page = createPageWithSVGTemplate()

    def tearDown(self):
        FreeCAD.closeDocument("TDAnno")

    def testMakeAnnotation(self):
        """Tests if an annotation can be added to page"""
        anno = FreeCAD.ActiveDocument.addObject(
            "TechDraw::DrawViewAnnotation", "TestAnno"
        )
        s = "Different Text"
        sl = list()
        sl.append(s)
        anno.Text = sl
        anno.TextStyle = "Bold"
        self.page.addView(anno)
        anno.X = 30.0
        anno.Y = 150.0
        FreeCAD.ActiveDocument.recompute()

        self.assertTrue("Up-to-date" in anno.State)

    def testFollowOwnerPositionAfterOwnerMoves(self):
        """A page-owned annotation follows a page-owned view after recompute."""
        owner = FreeCAD.ActiveDocument.addObject(
            "TechDraw::DrawViewAnnotation", "AnnotationOwner"
        )
        follower = FreeCAD.ActiveDocument.addObject(
            "TechDraw::DrawViewAnnotation", "FollowingAnnotation"
        )
        self.page.addView(owner)
        self.page.addView(follower)
        follower.Owner = owner
        follower.FollowOwnerPosition = True
        follower.OwnerOffsetX = 2.0
        follower.OwnerOffsetY = -5.0
        FreeCAD.ActiveDocument.recompute()

        owner.X = 80.0
        owner.Y = 60.0
        FreeCAD.ActiveDocument.recompute()

        self.assertAlmostEqual(82.0, follower.X.Value)
        self.assertAlmostEqual(55.0, follower.Y.Value)


if __name__ == "__main__":
    unittest.main()
