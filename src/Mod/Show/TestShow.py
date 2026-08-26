# SPDX-License-Identifier: LGPL-2.1-or-later

"""Focused regression tests for the Show visibility helpers.

Run with::

    FreeCAD -t TestShow
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Show import TempoVis
from Show.SceneDetails.ObjectClipPlane import ObjectClipPlane, clipPlane


class TestShow(unittest.TestCase):
    def test_restore_detail_uses_internal_restore_method(self):
        tempovis = TempoVis.__new__(TempoVis)
        detail = object()
        tempovis.has = Mock(return_value=True)
        tempovis._restoreDetail = Mock()
        tempovis.forgetDetail = Mock()

        tempovis.restoreDetail(detail, ultimate=True)

        tempovis._restoreDetail.assert_called_once_with(detail)
        tempovis.forgetDetail.assert_called_once_with(detail)

    def test_object_clip_plane_reads_plane_field_value(self):
        document = Mock()
        document.getObject.return_value = SimpleNamespace(ViewObject=object())
        obj = SimpleNamespace(Name="Box", Document=document)

        plane = Mock()
        plane_value = Mock()
        plane_value.getDistanceFromOrigin.return_value = 3.5
        plane_value.getNormal.return_value = (0.0, 0.0, 1.0)
        plane.getValue.return_value = plane_value
        clip_node = SimpleNamespace(on=SimpleNamespace(getValue=lambda: True), plane=plane)

        with patch("Show.SceneDetails.ObjectClipPlane.getClipPlaneNode", return_value=clip_node):
            detail = ObjectClipPlane(obj)

            self.assertEqual(detail.scene_value(), (True, ((0.0, 0.0, 1.0), 3.5)))
        plane.getValue.assert_called_once_with()

    def test_module_clip_plane_uses_object_clip_plane_detail(self):
        obj = SimpleNamespace(Name="Box", Document=object())
        tempovis = Mock()
        detail = object()

        with patch(
            "Show.SceneDetails.ObjectClipPlane.ObjectClipPlane", return_value=detail
        ) as detail_type:
            result = clipPlane(obj, True, tv=tempovis)

        self.assertIs(result, tempovis)
        detail_type.assert_called_once_with(obj, True, None, 0)
        tempovis.modify.assert_called_once_with(detail)

    def test_tempovis_clip_plane_uses_object_clip_plane_detail(self):
        tempovis = TempoVis.__new__(TempoVis)
        tempovis.modify = Mock()
        obj = object()
        detail = object()

        with (
            patch("Show.ShowUtils.is3DObject", return_value=True),
            patch(
                "Show.SceneDetails.ObjectClipPlane.ObjectClipPlane", return_value=detail
            ) as detail_type,
        ):
            tempovis.clipPlane(obj, True, None)

        detail_type.assert_called_once_with(obj, True, None, 0.02)
        tempovis.modify.assert_called_once_with(detail)


if __name__ == "__main__":
    unittest.main()
