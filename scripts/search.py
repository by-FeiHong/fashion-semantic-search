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


def search_unique_items(
    index: faiss.Index,
    query_vector: np.ndarray,
    metadata: list[dict[str, str]],
    top_k: int,
) -> list[tuple[float, int]]:
    """Return the best-scoring vector for each item, in similarity order."""
    if top_k <= 0:
        return []

    candidate_count = min(top_k, index.ntotal)
    while candidate_count:
        scores, vector_ids = index.search(query_vector, candidate_count)
        results: list[tuple[float, int]] = []
        seen_item_ids: set[str] = set()
        for score, vector_id in zip(scores[0], vector_ids[0]):
            vector_id = int(vector_id)
            if vector_id < 0:
                continue
            item_id = metadata[vector_id]["item_id"]
            if item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)
            results.append((float(score), vector_id))
            if len(results) == top_k:
                return results

        if candidate_count == index.ntotal:
            return results
        candidate_count = min(candidate_count * 2, index.ntotal)

    return []


def search_text(
    query: str,
    top_k: int,
    index: faiss.Index,
    metadata: list[dict[str, str]],
    model: SentenceTransformer,
) -> list[dict[str, str | float]]:
    """Encode a text query and return distinct, ranked fashion items."""
    query = query.strip()
    if not query:
        raise ValueError("Enter a fashion description before searching.")
    if index.ntotal != len(metadata):
        raise ValueError(
            f"FAISS and metadata counts do not match: {index.ntotal:,} != "
            f"{len(metadata):,}."
        )

    query_vector = model.encode(
        [query], convert_to_numpy=True, normalize_embeddings=True
    )
    query_vector = np.ascontiguousarray(query_vector, dtype=np.float32)
    return [
        {**metadata[vector_id], "score": score}
        for score, vector_id in search_unique_items(
            index, query_vector, metadata, top_k
        )
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Natural-language fashion search query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow downloading model files instead of requiring the local cache",
    )
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

    model = SentenceTransformer(
        args.model,
        local_files_only=not args.allow_download,
    )
    results = search_text(args.query, args.top_k, index, metadata, model)

    print(f'Query: "{args.query}"')
    print(f"Top {len(results)} unique items:\n")
    for rank, record in enumerate(results, start=1):
        print(
            f"{rank}. score={record['score']:.4f} item_id={record['item_id']} "
            f"split={record['split']}\n   {record['image_path']}"
        )


if __name__ == "__main__":
    main()
