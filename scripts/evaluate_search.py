"""Compare visual, description, and hybrid retrieval on fixed fashion queries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from fusion import fuse_ranked_results
from search import (
    DEFAULT_MODEL_NAME,
    load_metadata,
    search_text,
    search_unique_items,
)


CLIP_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
CASES = (
    ("washed black oversized jacket", {"Jackets_Vests", "Jackets_Coats"}),
    ("boxy neutral knit", {"Sweaters"}),
    ("distressed dark denim", {"Denim"}),
    ("floral summer dress", {"Dresses"}),
    ("white graphic t-shirt", {"Tees_Tanks"}),
    ("blue skinny jeans", {"Denim", "Pants"}),
)
TOP_K = 5
CANDIDATES = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clip-index",
        type=Path,
        default=Path("data/processed/fashion_clip.index"),
    )
    parser.add_argument(
        "--clip-metadata",
        type=Path,
        default=Path("data/processed/clip_metadata.csv"),
    )
    return parser.parse_args()


def category(image_path: str) -> str:
    """Extract the DeepFashion garment category from an image path."""
    parts = Path(image_path).parts
    return parts[-3] if len(parts) >= 3 else ""


def precision(results: list[dict[str, str | float]], expected: set[str]) -> float:
    """Return category precision for one ranked result list."""
    if not results:
        return 0.0
    return sum(category(str(row["image_path"])) in expected for row in results) / len(
        results
    )


def main() -> None:
    args = parse_args()
    root = Path("data/processed")
    clip_index = faiss.read_index(str(args.clip_index))
    clip_metadata = load_metadata(args.clip_metadata)
    text_index = faiss.read_index(str(root / "fashion.index"))
    text_metadata = load_metadata(root / "metadata_index.csv")
    with (root / "metadata.csv").open(encoding="utf-8", newline="") as file:
        details = {row["image_path"]: row for row in csv.DictReader(file)}

    clip_model = SentenceTransformer(CLIP_MODEL_NAME, local_files_only=True)
    text_model = SentenceTransformer(DEFAULT_MODEL_NAME, local_files_only=True)
    totals = {"Visual": 0.0, "Description": 0.0, "Hybrid": 0.0}

    print(f"{'Query':34} {'Visual':>8} {'Text':>8} {'Hybrid':>8}")
    print("-" * 62)
    for query, expected in CASES:
        vector = clip_model.encode([query], normalize_embeddings=True)
        ranked_vectors = search_unique_items(
            clip_index,
            np.ascontiguousarray(vector, dtype=np.float32),
            clip_metadata,
            CANDIDATES,
        )
        visual = [
            {**clip_metadata[vector_id], "score": score}
            for score, vector_id in ranked_vectors
        ]
        raw_text = search_text(
            query, CANDIDATES, text_index, text_metadata, text_model
        )
        description = [
            {**details.get(str(row["image_path"]), {}), **row} for row in raw_text
        ]
        hybrid = fuse_ranked_results([(0.7, visual), (0.3, description)], TOP_K)
        values = {
            "Visual": precision(visual[:TOP_K], expected),
            "Description": precision(description[:TOP_K], expected),
            "Hybrid": precision(hybrid, expected),
        }
        for name, value in values.items():
            totals[name] += value
        print(
            f"{query:34} {values['Visual']:8.0%} "
            f"{values['Description']:8.0%} {values['Hybrid']:8.0%}"
        )

    count = len(CASES)
    print("-" * 62)
    print(
        f"{'Mean precision@5':34} {totals['Visual'] / count:8.0%} "
        f"{totals['Description'] / count:8.0%} {totals['Hybrid'] / count:8.0%}"
    )


if __name__ == "__main__":
    main()
