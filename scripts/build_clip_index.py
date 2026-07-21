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
VIEW_NAMES = ("front", "full", "side", "back", "additional")


def view_priority(image_path: str) -> tuple[int, str]:
    """Rank product views from most useful for retrieval to least useful."""
    name = Path(image_path).stem.lower()
    return next((rank for rank, view in enumerate(VIEW_NAMES) if view in name), 99), name


def view_name(image_path: str) -> str:
    """Return the normalized DeepFashion view name."""
    name = Path(image_path).stem.lower()
    return next((view for view in VIEW_NAMES if view in name), "unknown")


def select_item_views(
    metadata_path: Path, views_per_item: int, limit: int = 0
) -> list[tuple[dict[str, str], list[str]]]:
    """Select diverse, prioritized views and a display row for every item."""
    if views_per_item <= 0:
        raise ValueError("Views per item must be greater than zero.")
    if limit < 0:
        raise ValueError("The item limit must be zero or greater.")
    with metadata_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["item_id"], []).append(row)

    selections: list[tuple[dict[str, str], list[str]]] = []
    for item_id in sorted(grouped):
        item_rows = sorted(grouped[item_id], key=lambda row: view_priority(row["image_path"]))
        chosen: list[dict[str, str]] = []
        chosen_paths: set[str] = set()
        seen_views: set[str] = set()
        for row in item_rows:
            kind = view_name(row["image_path"])
            if kind in seen_views:
                continue
            chosen.append(row)
            chosen_paths.add(row["image_path"])
            seen_views.add(kind)
            if len(chosen) == views_per_item:
                break
        for row in item_rows:
            if len(chosen) == views_per_item:
                break
            if row["image_path"] not in chosen_paths:
                chosen.append(row)
                chosen_paths.add(row["image_path"])
        selections.append((item_rows[0], [row["image_path"] for row in chosen]))
        if limit and len(selections) == limit:
            break
    return selections


def select_representatives(
    metadata_path: Path, limit: int = 0
) -> list[dict[str, str]]:
    """Select the best available image row for each unique item."""
    if limit < 0:
        raise ValueError("The item limit must be zero or greater.")
    return [
        representative
        for representative, _ in select_item_views(metadata_path, 1, limit)
    ]


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
    parser.add_argument("--views-per-item", type=int, default=1)
    parser.add_argument(
        "--index-mode",
        choices=("item-average", "view-max"),
        default="item-average",
        help="Average views per item or index each view for max-score item retrieval",
    )
    parser.add_argument("--allow-download", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("The batch size must be greater than zero.")
    selections = select_item_views(args.input, args.views_per_item, args.limit)
    if not selections:
        raise ValueError("No representative product images were found.")
    item_rows = [representative for representative, _ in selections]
    image_tasks = [
        (item_index, image_path)
        for item_index, (_, image_paths) in enumerate(selections)
        for image_path in image_paths
    ]

    model = SentenceTransformer(args.model, local_files_only=not args.allow_download)
    dimension = model.get_embedding_dimension()
    args.embeddings.parent.mkdir(parents=True, exist_ok=True)
    partial_path = args.embeddings.with_suffix(args.embeddings.suffix + ".partial")
    if args.index_mode == "view-max":
        embeddings = np.empty((len(image_tasks), dimension), dtype=np.float32)
    else:
        sums = np.zeros((len(item_rows), dimension), dtype=np.float32)
        counts = np.zeros(len(item_rows), dtype=np.int32)

    started = time.perf_counter()
    for start in range(0, len(image_tasks), args.batch_size):
        batch_tasks = image_tasks[start : start + args.batch_size]
        images: list[Image.Image] = []
        try:
            for _, image_path in batch_tasks:
                with Image.open(image_path) as image:
                    images.append(image.convert("RGB"))
            vectors = model.encode(
                images,
                batch_size=args.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if args.index_mode == "view-max":
                embeddings[start : start + len(batch_tasks)] = vectors
            else:
                item_indices = np.asarray([item_index for item_index, _ in batch_tasks])
                np.add.at(sums, item_indices, vectors)
                np.add.at(counts, item_indices, 1)
        finally:
            for image in images:
                image.close()
        completed = start + len(batch_tasks)
        elapsed = time.perf_counter() - started
        print(
            f"Encoded {completed:,}/{len(image_tasks):,} views "
            f"({completed / elapsed:.2f} images/s)",
            flush=True,
        )

    if args.index_mode == "view-max":
        rows = [
            {**item_rows[item_index], "image_path": image_path}
            for item_index, image_path in image_tasks
        ]
    else:
        embeddings = sums / counts[:, None]
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = np.ascontiguousarray(
            embeddings / np.maximum(norms, 1e-12), dtype=np.float32
        )
        rows = item_rows
    np.save(partial_path, embeddings)
    generated_partial_path = partial_path.with_suffix(partial_path.suffix + ".npy")
    if generated_partial_path.is_file():
        partial_path = generated_partial_path
    os.replace(partial_path, args.embeddings)
    write_metadata(args.metadata, rows)

    vectors = np.ascontiguousarray(np.load(args.embeddings), dtype=np.float32)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(args.index))
    print(f"Vectors indexed: {index.ntotal:,}")
    print(f"Distinct items: {len(item_rows):,}")
    print(f"Views encoded: {len(image_tasks):,}")
    print(f"Embedding dimension: {index.d:,}")
    print(f"Index: {args.index.resolve()}")


if __name__ == "__main__":
    main()
