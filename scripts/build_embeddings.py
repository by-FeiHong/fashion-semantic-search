"""Build normalized text embeddings for a small metadata smoke test."""

from __future__ import annotations

import argparse
import csv
from itertools import islice
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_INPUT_PATH = Path("data") / "processed" / "metadata.csv"
DEFAULT_OUTPUT_PATH = Path("data") / "processed" / "embeddings_sample.npy"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LIMIT = 100
REQUIRED_COLUMNS = {"color", "description"}


def combine_text(color: str | None, description: str | None) -> str:
    """Combine available color and description values into embedding text."""
    parts = [value.strip() for value in (color, description) if value and value.strip()]
    return " ".join(parts)


def load_texts(metadata_path: Path, limit: int) -> list[str]:
    """Load up to ``limit`` combined texts from the processed metadata CSV."""
    if limit <= 0:
        raise ValueError("The record limit must be greater than zero.")
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Metadata CSV was not found: {metadata_path}. "
            "Run scripts/export_metadata.py first."
        )

    with metadata_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                f"Metadata CSV is missing required columns: {', '.join(sorted(missing))}"
            )
        texts = [
            combine_text(row.get("color"), row.get("description"))
            for row in islice(reader, limit)
        ]

    if not texts:
        raise ValueError(f"Metadata CSV contains no records: {metadata_path}")
    return texts


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    return parser.parse_args()


def main() -> None:
    """Generate and save normalized sample embeddings."""
    args = parse_args()
    texts = load_texts(args.input, args.limit)
    model = SentenceTransformer(args.model)
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    embeddings = np.asarray(embeddings, dtype=np.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, embeddings)

    print(f"Records embedded: {embeddings.shape[0]:,}")
    print(f"Embedding dimension: {embeddings.shape[1]:,}")
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
