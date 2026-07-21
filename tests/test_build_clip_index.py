"""Tests for CLIP representative-image selection."""

import unittest

from scripts.build_clip_index import select_item_views, view_priority


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

    def test_selects_distinct_views_before_duplicate_views(self) -> None:
        import csv
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=("image_path", "item_id", "split", "color", "description"),
                )
                writer.writeheader()
                for image_path in ("02_1_front.jpg", "01_1_front.jpg", "01_2_side.jpg"):
                    writer.writerow({"image_path": image_path, "item_id": "A"})

            selections = select_item_views(path, views_per_item=2)

        self.assertEqual(selections[0][1], ["01_1_front.jpg", "01_2_side.jpg"])


if __name__ == "__main__":
    unittest.main()
