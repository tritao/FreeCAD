# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

from ArchRepresentation import RepresentationPurpose, RepresentationRequest


class TestArchRepresentation(unittest.TestCase):
    def test_request_accepts_enum_or_serialized_purpose(self):
        plan = RepresentationRequest(purpose=RepresentationPurpose.PLAN)
        section = RepresentationRequest(purpose="Section")
        self.assertIs(plan.purpose, RepresentationPurpose.PLAN)
        self.assertIs(section.purpose, RepresentationPurpose.SECTION)
        self.assertIsNone(section.reference_frame)

    def test_request_keeps_arbitrary_frame_and_ranges(self):
        frame = object()
        request = RepresentationRequest(
            purpose="Elevation",
            reference_frame=frame,
            cut_range=(0.0, 2.1),
            projection_range=(-1.0, 8.0),
            cut_offset=1.2,
            target_offset=0.0,
        )
        self.assertIs(request.reference_frame, frame)
        self.assertEqual(request.cut_range, (0.0, 2.1))
        self.assertEqual(request.projection_range, (-1.0, 8.0))
        self.assertEqual(request.cut_offset, 1.2)
        self.assertEqual(request.target_offset, 0.0)


if __name__ == "__main__":
    unittest.main()


    def test_request_supports_plan_offsets(self):
        request = RepresentationRequest(
            purpose=RepresentationPurpose.PLAN,
            cut_offset=1.0,
            target_offset=0.0,
        )
        self.assertIs(request.purpose, RepresentationPurpose.PLAN)
        self.assertEqual(request.cut_offset, 1.0)
        self.assertEqual(request.target_offset, 0.0)
