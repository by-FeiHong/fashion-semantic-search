"""Tests for CLIP representative-image selection."""

import unittest

from scripts.build_clip_index import view_priority


class ViewPriorityTest(unittest.TestCase):
    def test_prefers_front_then_full_then_other_views(self) -> None:
        paths = [
            "01_7_additional.jpg",
            "01_2_side.jpg",
            "01_4_full.jpg",
            "01_1_front.jpg",
        ]
        self.assertEqual(sorted(paths, key=view_priority)[0], "01_1_front.jpg")
        self.assertEqual(sorted(paths, key=view_priority)[1], "01_4_full.jpg")


if __name__ == "__main__":
    unittest.main()
