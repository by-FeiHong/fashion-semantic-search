"""Export normalized DeepFashion metadata to tabular files."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from load_metadata import DEFAULT_DATASET_ROOT, FashionRecord, MetadataError, load_metadata


DEFAULT_OUTPUT_DIR = Path("data") / "processed"
COLUMNS = ["image_path", "item_id", "split", "color", "description"]


def record_to_dict(record: FashionRecord) -> dict[str, str]:
    """Convert a metadata record into a serializable row."""
    return {
        "image_path": str(record.image_path),
        "item_id": record.item_id,
        "split": record.split,
        "color": record.color,
        "description": record.description,
    }


def export_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write metadata rows as a UTF-8 CSV file."""
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def export_parquet(rows: list[dict[str, str]], output_path: Path) -> str | None:
    """Write Parquet when pandas and a supported Parquet engine are available."""
    try:
        import pandas as pd
    except ImportError:
        return "pandas is not installed"

    try:
        pd.DataFrame(rows, columns=COLUMNS).to_parquet(output_path, index=False)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        return f"a Parquet engine is unavailable ({exc})"
    return None


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"DeepFashion In-shop root (default: {DEFAULT_DATASET_ROOT})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Export directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    """Load metadata and export it as CSV and, when supported, Parquet."""
    args = parse_args()
    try:
        records = load_metadata(args.dataset_root)
    except MetadataError as exc:
        raise SystemExit(f"Metadata error: {exc}") from exc

    rows = [record_to_dict(record) for record in records]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "metadata.csv"
    export_csv(rows, csv_path)

    parquet_path = args.output_dir / "metadata.parquet"
    parquet_skip_reason = export_parquet(rows, parquet_path)

    print(f"Records exported: {len(rows):,}")
    print(f"Columns: {', '.join(COLUMNS)}")
    print(f"CSV: {csv_path.resolve()}")
    if parquet_skip_reason is None:
        print(f"Parquet: {parquet_path.resolve()}")
    else:
        print(f"Parquet skipped: {parquet_skip_reason}")


if __name__ == "__main__":
    main()
