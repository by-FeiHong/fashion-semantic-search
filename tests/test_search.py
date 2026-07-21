"""Tests for unique-item vector search."""

import unittest

import faiss
import numpy as np

from scripts.fusion import fuse_ranked_results
from scripts.search import search_unique_items


class SearchUniqueItemsTest(unittest.TestCase):
    def test_overfetches_until_top_k_items_are_distinct(self) -> None:
        embeddings = np.array(
            [[1.00, 0.00], [0.99, 0.01], [0.98, 0.02], [0.90, 0.10],
             [0.80, 0.20], [0.70, 0.30]],
            dtype=np.float32,
        )
        index = faiss.IndexFlatIP(2)
        index.add(embeddings)
        metadata = [
            {"item_id": item_id}
            for item_id in ["A", "A", "A", "B", "C", "D"]
        ]

        results = search_unique_items(
            index, np.array([[1.0, 0.0]], dtype=np.float32), metadata, 3
        )

        self.assertEqual(
            [metadata[vector_id]["item_id"] for _, vector_id in results],
            ["A", "B", "C"],
        )

    def test_returns_all_available_unique_items_when_fewer_than_top_k(self) -> None:
        embeddings = np.array([[1.0], [0.9], [0.8]], dtype=np.float32)
        index = faiss.IndexFlatIP(1)
        index.add(embeddings)
        metadata = [{"item_id": item_id} for item_id in ["A", "A", "B"]]

        results = search_unique_items(
            index, np.array([[1.0]], dtype=np.float32), metadata, 5
        )

        self.assertEqual(len(results), 2)


class FuseRankedResultsTest(unittest.TestCase):
    def test_rewards_items_found_by_both_search_engines(self) -> None:
        visual = [{"item_id": "A"}, {"item_id": "B"}, {"item_id": "C"}]
        text = [{"item_id": "C"}, {"item_id": "D"}, {"item_id": "A"}]

        results = fuse_ranked_results([(0.7, visual), (0.3, text)], top_k=3)

        self.assertEqual([result["item_id"] for result in results], ["A", "C", "B"])
        self.assertEqual(results[0]["score_label"], "FUSION")

    def test_ignores_non_positive_weights(self) -> None:
        results = fuse_ranked_results(
            [(0.0, [{"item_id": "A"}]), (1.0, [{"item_id": "B"}])],
            top_k=2,
        )
        self.assertEqual([result["item_id"] for result in results], ["B"])


if __name__ == "__main__":
    unittest.main()
