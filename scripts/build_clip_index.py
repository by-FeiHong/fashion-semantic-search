"""Build a CLIP image index with one representative image per fashion item."""

from __future__ import annotations

import argparse
import csv
import os
import time
from pathlib import Path

import faiss
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer


DEFAULT_INPUT_PATH = Path("data/processed/metadata.csv")
DEFAULT_EMBEDDINGS_PATH = Path("data/processed/clip_embeddings.npy")
DEFAULT_METADATA_PATH = Path("data/processed/clip_metadata.csv")
DEFAULT_INDEX_PATH = Path("data/processed/fashion_clip.index")
DEFAULT_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
METADATA_COLUMNS = ("image_path", "item_id", "split", "color", "description")


def view_priority(image_path: str) -> tuple[int, str]:
    """Rank product views from most useful for retrieval to least useful."""
    name = Path(image_path).stem.lower()
    priorities = ("front", "full", "side", "back", "additional")
    return next((rank for rank, view in enumerate(priorities) if view in name), 99), name


def select_representatives(
    metadata_path: Path, limit: int = 0
) -> list[dict[str, str]]:
    """Select the best available image row for each unique item."""
    if limit < 0:
        raise ValueError("The item limit must be zero or greater.")
    with metadata_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row["item_id"]
        current = selected.get(item_id)
        if current is None or view_priority(row["image_path"]) < view_priority(
            current["image_path"]
        ):
            selected[item_id] = row

    representatives = list(selected.values())
    representatives.sort(key=lambda row: row["item_id"])
    return representatives[:limit] if limit else representatives


def write_metadata(path: Path, rows: list[dict[str, str]]) -> None:
    """Write CLIP metadata in exact vector order."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=METADATA_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in METADATA_COLUMNS} for row in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--allow-download", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("The batch size must be greater than zero.")
    rows = select_representatives(args.input, args.limit)
    if not rows:
        raise ValueError("No representative product images were found.")

    model = SentenceTransformer(args.model, local_files_only=not args.allow_download)
    dimension = model.get_embedding_dimension()
    args.embeddings.parent.mkdir(parents=True, exist_ok=True)
    partial_path = args.embeddings.with_suffix(args.embeddings.suffix + ".partial")
    embeddings = np.lib.format.open_memmap(
        partial_path, mode="w+", dtype=np.float32, shape=(len(rows), dimension)
    )

    started = time.perf_counter()
    for start in range(0, len(rows), args.batch_size):
        batch_rows = rows[start : start + args.batch_size]
        images: list[Image.Image] = []
        try:
            for row in batch_rows:
                with Image.open(row["image_path"]) as image:
                    images.append(image.convert("RGB"))
            vectors = model.encode(
                images,
                batch_size=args.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embeddings[start : start + len(batch_rows)] = vectors
        finally:
            for image in images:
                image.close()
        completed = start + len(batch_rows)
        elapsed = time.perf_counter() - started
        print(
            f"Encoded {completed:,}/{len(rows):,} images "
            f"({completed / elapsed:.2f} images/s)",
            flush=True,
        )

    embeddings.flush()
    del embeddings
    os.replace(partial_path, args.embeddings)
    write_metadata(args.metadata, rows)

    vectors = np.ascontiguousarray(np.load(args.embeddings), dtype=np.float32)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(args.index))
    print(f"Items indexed: {index.ntotal:,}")
    print(f"Embedding dimension: {index.d:,}")
    print(f"Index: {args.index.resolve()}")


if __name__ == "__main__":
    main()
