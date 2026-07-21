"""Build normalized text embeddings and their aligned metadata index."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_INPUT_PATH = Path("data") / "processed" / "metadata.csv"
DEFAULT_OUTPUT_PATH = Path("data") / "processed" / "embeddings_sample.npy"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LIMIT = 100
DEFAULT_BATCH_SIZE = 32
INDEX_COLUMNS = ("row_id", "image_path", "item_id", "split")
REQUIRED_COLUMNS = {"image_path", "item_id", "split", "color", "description"}


def combine_text(color: str | None, description: str | None) -> str:
    """Combine available color and description values into embedding text."""
    parts = [value.strip() for value in (color, description) if value and value.strip()]
    return " ".join(parts)


def metadata_index_path(output_path: Path) -> Path:
    """Return the metadata index path stored beside the embedding output."""
    return output_path.with_name("metadata_index.csv")


def load_records(
    metadata_path: Path, limit: int
) -> tuple[list[str], list[dict[str, str | int]]]:
    """Load embedding texts and aligned index rows from the metadata CSV.

    A limit of zero reads the entire metadata file.
    """
    if limit < 0:
        raise ValueError("The record limit must be zero or greater.")
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
        texts: list[str] = []
        index_rows: list[dict[str, str | int]] = []
        for row_id, row in enumerate(reader):
            if limit and row_id >= limit:
                break
            texts.append(combine_text(row.get("color"), row.get("description")))
            index_rows.append(
                {
                    "row_id": row_id,
                    "image_path": row["image_path"],
                    "item_id": row["item_id"],
                    "split": row["split"],
                }
            )

    if not texts:
        raise ValueError(f"Metadata CSV contains no records: {metadata_path}")
    return texts, index_rows


def write_metadata_index(
    index_path: Path, index_rows: list[dict[str, str | int]]
) -> None:
    """Write metadata rows in exactly the same order as the embeddings."""
    with index_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(index_rows)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--metadata-output",
        type=Path,
        help="Aligned metadata CSV (defaults to metadata_index.csv beside embeddings)",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow downloading model files instead of requiring the local cache",
    )
    return parser.parse_args()


def main() -> None:
    """Generate and save normalized sample embeddings."""
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("The batch size must be greater than zero.")

    texts, index_rows = load_records(args.input, args.limit)
    model = SentenceTransformer(
        args.model,
        local_files_only=not args.allow_download,
    )
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    embeddings = np.asarray(embeddings, dtype=np.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, embeddings)
    index_path = args.metadata_output or metadata_index_path(args.output)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    write_metadata_index(index_path, index_rows)

    if embeddings.shape[0] != len(index_rows):
        raise RuntimeError("Embedding and metadata index row counts do not match.")

    print(f"Records embedded: {embeddings.shape[0]:,}")
    print(f"Embedding dimension: {embeddings.shape[1]:,}")
    print(f"Output: {args.output.resolve()}")
    print(f"Metadata index: {index_path.resolve()}")


if __name__ == "__main__":
    main()
