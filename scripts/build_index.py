"""Build a FAISS cosine-similarity index from normalized embeddings."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import faiss
import numpy as np


DEFAULT_EMBEDDINGS_PATH = Path("data") / "processed" / "embeddings_1000.npy"
DEFAULT_METADATA_PATH = Path("data") / "processed" / "metadata_index.csv"
DEFAULT_OUTPUT_PATH = Path("data") / "processed" / "fashion.index"


def count_metadata_rows(path: Path) -> int:
    """Count data rows in the metadata index."""
    if not path.is_file():
        raise FileNotFoundError(f"Metadata index was not found: {path}")
    with path.open(encoding="utf-8", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    """Validate inputs, build an exact inner-product index, and save it."""
    args = parse_args()
    if not args.embeddings.is_file():
        raise FileNotFoundError(f"Embeddings were not found: {args.embeddings}")

    embeddings = np.load(args.embeddings)
    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        raise ValueError("Embeddings must be a non-empty two-dimensional array.")
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

    metadata_count = count_metadata_rows(args.metadata)
    if embeddings.shape[0] != metadata_count:
        raise ValueError(
            "Embedding and metadata counts do not match: "
            f"{embeddings.shape[0]:,} != {metadata_count:,}."
        )

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(args.output))

    print(f"Vectors indexed: {index.ntotal:,}")
    print(f"Vector dimension: {index.d:,}")
    print(f"Index type: {type(index).__name__}")
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
