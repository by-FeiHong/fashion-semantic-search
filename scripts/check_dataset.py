from pathlib import Path


DATASET_ROOT = Path(r"D:\Datasets\DeepFashion\In-shop")


def main() -> None:
    required_paths = {
        "annotations": DATASET_ROOT / "Anno",
        "evaluation": DATASET_ROOT / "Eval" / "list_eval_partition.txt",
        "images": DATASET_ROOT / "Img" / "img",
    }

    print(f"Dataset root: {DATASET_ROOT}\n")

    all_valid = True

    for name, path in required_paths.items():
        exists = path.exists()
        status = "OK" if exists else "MISSING"
        print(f"[{status}] {name}: {path}")

        if not exists:
            all_valid = False

    if not all_valid:
        raise FileNotFoundError("Dataset structure is incomplete.")

    image_extensions = {".jpg", ".jpeg", ".png"}
    image_count = sum(
        1
        for path in required_paths["images"].rglob("*")
        if path.is_file() and path.suffix.lower() in image_extensions
    )

    print(f"\nImage count: {image_count:,}")
    print("Dataset structure looks valid.")


if __name__ == "__main__":
    main()