"""Search a FAISS fashion index with a natural-language query."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_INDEX_PATH = Path("data") / "processed" / "fashion.index"
DEFAULT_METADATA_PATH = Path("data") / "processed" / "metadata_index.csv"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_metadata(path: Path) -> list[dict[str, str]]:
    """Load metadata whose row order matches the FAISS vector IDs."""
    if not path.is_file():
        raise FileNotFoundError(f"Metadata index was not found: {path}")
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Natural-language fashion search query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    return parser.parse_args()


def main() -> None:
    """Encode the query and print the closest indexed products."""
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("--top-k must be greater than zero.")
    if not args.index.is_file():
        raise FileNotFoundError(f"FAISS index was not found: {args.index}")

    index = faiss.read_index(str(args.index))
    metadata = load_metadata(args.metadata)
    if index.ntotal != len(metadata):
        raise ValueError(
            f"FAISS and metadata counts do not match: {index.ntotal:,} != "
            f"{len(metadata):,}."
        )

    model = SentenceTransformer(args.model)
    query_vector = model.encode(
        [args.query], convert_to_numpy=True, normalize_embeddings=True
    )
    query_vector = np.ascontiguousarray(query_vector, dtype=np.float32)
    result_count = min(args.top_k, index.ntotal)
    scores, vector_ids = index.search(query_vector, result_count)

    print(f'Query: "{args.query}"')
    print(f"Top {result_count} results:\n")
    for rank, (score, vector_id) in enumerate(
        zip(scores[0], vector_ids[0]), start=1
    ):
        record = metadata[int(vector_id)]
        print(
            f"{rank}. score={score:.4f} item_id={record['item_id']} "
            f"split={record['split']}\n   {record['image_path']}"
        )


if __name__ == "__main__":
    main()
