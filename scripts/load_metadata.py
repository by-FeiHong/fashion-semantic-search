"""Load and combine DeepFashion In-shop retrieval metadata."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATASET_ROOT = Path(r"D:\Datasets\DeepFashion\In-shop")


class MetadataError(RuntimeError):
    """Raised when DeepFashion metadata is missing or malformed."""


@dataclass(frozen=True)
class ProductDescription:
    """Text metadata shared by all images of one fashion item."""

    color: str
    description: str


@dataclass(frozen=True)
class FashionRecord:
    """Combined metadata for one DeepFashion image."""

    image_path: Path
    item_id: str
    split: str
    color: str
    description: str


def require_file(path: Path) -> None:
    """Raise a clear error when a required metadata file is unavailable."""
    if not path.is_file():
        raise MetadataError(f"Required metadata file was not found: {path}")


def normalize_description(value: Any, *, item_id: str) -> str:
    """Convert a string or list of description fragments into plain text."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return " ".join(part.strip() for part in value if part.strip())
    raise MetadataError(
        f"Invalid description for {item_id}: expected a string or list of strings."
    )


def load_descriptions(path: Path) -> dict[str, ProductDescription]:
    """Load item-level colors and descriptions indexed by item ID."""
    require_file(path)
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise MetadataError(f"Could not parse description metadata: {path}") from exc

    if not isinstance(payload, list):
        raise MetadataError(f"Expected a JSON list in {path}.")

    descriptions: dict[str, ProductDescription] = {}
    for index, entry in enumerate(payload, start=1):
        if not isinstance(entry, dict):
            raise MetadataError(f"Description entry {index} is not an object.")

        item_id = entry.get("item")
        color = entry.get("color", "")
        if not isinstance(item_id, str) or not item_id.strip():
            raise MetadataError(f"Description entry {index} has no valid item ID.")
        if not isinstance(color, str):
            raise MetadataError(f"Invalid color for {item_id}: expected a string.")
        product = ProductDescription(
            color=color.strip(),
            description=normalize_description(entry.get("description"), item_id=item_id),
        )
        existing = descriptions.get(item_id)
        if existing is not None:
            if existing != product:
                raise MetadataError(f"Conflicting description entries for item {item_id}.")
            continue
        descriptions[item_id] = product

    return descriptions


def iter_partition_rows(path: Path) -> Iterable[tuple[int, str, str, str]]:
    """Yield line number, image name, item ID, and split from the partition file."""
    require_file(path)
    try:
        with path.open(encoding="utf-8") as file:
            first_line = file.readline().strip()
            header = file.readline().split()
            if not first_line.isdigit():
                raise MetadataError(f"Invalid record count on the first line of {path}.")
            expected_count = int(first_line)
            if header != ["image_name", "item_id", "evaluation_status"]:
                raise MetadataError(f"Unexpected partition header in {path}: {header}")

            actual_count = 0
            for line_number, line in enumerate(file, start=3):
                if not line.strip():
                    continue
                fields = line.split()
                if len(fields) != 3:
                    raise MetadataError(
                        f"Malformed partition row at {path}:{line_number}; "
                        f"expected 3 fields, found {len(fields)}."
                    )
                actual_count += 1
                yield line_number, fields[0], fields[1], fields[2]

            if actual_count != expected_count:
                raise MetadataError(
                    f"Partition count mismatch: header says {expected_count:,}, "
                    f"but parsed {actual_count:,}."
                )
    except OSError as exc:
        raise MetadataError(f"Could not read partition metadata: {path}") from exc


def load_metadata(dataset_root: Path) -> list[FashionRecord]:
    """Combine image partitions with item descriptions."""
    partition_path = dataset_root / "Eval" / "list_eval_partition.txt"
    description_path = dataset_root / "Anno" / "list_description_inshop.json"
    image_root = dataset_root / "Img"
    descriptions = load_descriptions(description_path)

    records: list[FashionRecord] = []
    for line_number, image_name, item_id, split in iter_partition_rows(partition_path):
        product = descriptions.get(item_id)
        if product is None:
            raise MetadataError(
                f"No description found for {item_id} referenced at "
                f"{partition_path}:{line_number}."
            )
        records.append(
            FashionRecord(
                image_path=image_root / Path(image_name),
                item_id=item_id,
                split=split,
                color=product.color,
                description=product.description,
            )
        )
    return records


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"DeepFashion In-shop root (default: {DEFAULT_DATASET_ROOT})",
    )
    return parser.parse_args()


def main() -> None:
    """Load metadata and print a five-record preview."""
    args = parse_args()
    try:
        records = load_metadata(args.dataset_root)
    except MetadataError as exc:
        raise SystemExit(f"Metadata error: {exc}") from exc

    print(f"Dataset root: {args.dataset_root}")
    print(f"Total records: {len(records):,}\n")
    print("First 5 records:")
    for record in records[:5]:
        print(
            {
                "image_path": str(record.image_path),
                "item_id": record.item_id,
                "split": record.split,
                "color": record.color,
                "description": record.description,
            }
        )


if __name__ == "__main__":
    main()
