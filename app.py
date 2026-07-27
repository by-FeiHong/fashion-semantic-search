"""Streamlit MVP for DeepFashion semantic text search."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import faiss
import streamlit as st
from sentence_transformers import SentenceTransformer

from scripts.search import DEFAULT_MODEL_NAME, load_metadata, search_text


PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_PATH = PROJECT_ROOT / "data/processed/fashion.index"
METADATA_INDEX_PATH = PROJECT_ROOT / "data/processed/metadata_index.csv"
CATALOG_PATH = PROJECT_ROOT / "data/processed/metadata.csv"
DEFAULT_DATASET_ROOT = Path(r"D:\Datasets\DeepFashion\In-shop")


def dataset_root() -> Path:
    """Return the configured DeepFashion In-shop root."""
    return Path(os.environ.get("DEEPFASHION_ROOT", str(DEFAULT_DATASET_ROOT)))


def resolve_image_path(raw_path: str, root: Path) -> Path:
    """Resolve an indexed image path against the configured dataset root."""
    path = Path(raw_path)
    if path.is_absolute() and path.is_file():
        return path

    normalized = raw_path.replace("\\", "/")
    for marker in ("Img/img/", "img/"):
        if marker in normalized:
            relative = normalized.split(marker, 1)[1]
            return root / "Img" / "img" / Path(relative)
    return root / path


@st.cache_data(show_spinner=False)
def load_catalog_details(path: str) -> dict[str, dict[str, str]]:
    """Load display metadata keyed by image path."""
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise FileNotFoundError(
            f"Processed catalog not found: {catalog_path}. "
            "Run scripts/export_metadata.py first."
        )
    with catalog_path.open(encoding="utf-8", newline="") as file:
        return {row["image_path"]: row for row in csv.DictReader(file)}


@st.cache_resource(show_spinner="Loading search index and model...")
def load_search_resources(
    index_version: int,
    metadata_version: int,
) -> tuple[faiss.Index, list[dict[str, str]], SentenceTransformer]:
    """Load and cache the FAISS index, aligned metadata, and text encoder."""
    if not INDEX_PATH.is_file():
        raise FileNotFoundError(
            f"FAISS index not found: {INDEX_PATH}. Run scripts/build_index.py first."
        )
    if not METADATA_INDEX_PATH.is_file():
        raise FileNotFoundError(
            f"Metadata index not found: {METADATA_INDEX_PATH}. "
            "Run scripts/build_embeddings.py first."
        )

    index = faiss.read_index(str(INDEX_PATH))
    metadata = load_metadata(METADATA_INDEX_PATH)
    if index.ntotal != len(metadata):
        raise ValueError(
            f"Index and metadata counts differ: {index.ntotal:,} != "
            f"{len(metadata):,}."
        )
    try:
        model = SentenceTransformer(DEFAULT_MODEL_NAME, local_files_only=True)
    except Exception as error:
        raise RuntimeError(
            "The embedding model is not available locally. Run "
            "scripts/build_embeddings.py once while online, then restart the app."
        ) from error
    return index, metadata, model


def run_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """Search for distinct products and enrich them with display metadata."""
    index, metadata, model = load_search_resources(
        INDEX_PATH.stat().st_mtime_ns,
        METADATA_INDEX_PATH.stat().st_mtime_ns,
    )
    details = load_catalog_details(str(CATALOG_PATH))
    results = search_text(query, top_k, index, metadata, model)
    return [
        {**details.get(str(result["image_path"]), {}), **result}
        for result in results
    ]


def render_result(record: dict[str, Any], rank: int, root: Path) -> None:
    """Render one search result."""
    image_path = resolve_image_path(str(record["image_path"]), root)
    with st.container(border=True):
        if image_path.is_file():
            st.image(str(image_path), width="stretch")
        else:
            st.warning(f"Image unavailable: {image_path}")
        st.subheader(f"{rank}. {record.get('item_id', 'Unknown item')}")
        st.metric("Similarity", f"{float(record['score']):.4f}")
        st.write(f"**Color:** {record.get('color') or 'Unknown'}")
        st.write(record.get("description") or "Description unavailable.")


st.set_page_config(
    page_title="Fashion semantic search",
    page_icon=":material/search:",
    layout="wide",
)

st.title("Fashion semantic search")
st.caption(
    "Describe a garment in natural language to find semantically similar "
    "DeepFashion products."
)

with st.form("search_form"):
    query = st.text_input(
        "Fashion description",
        placeholder="minimal black oversized blazer",
        key="search_query",
    )
    top_k = st.selectbox("Number of results", [3, 5, 8, 10], index=1)
    submitted = st.form_submit_button(
        "Search",
        type="primary",
        icon=":material/search:",
        width="stretch",
    )

if submitted:
    if not query.strip():
        st.warning("Enter a fashion description before searching.")
    else:
        try:
            with st.spinner("Searching the catalog..."):
                results = run_search(query, top_k)
        except (FileNotFoundError, ValueError, RuntimeError) as error:
            st.error(str(error), icon=":material/error:")
        except Exception as error:
            st.error(
                f"Search failed unexpectedly: {error}",
                icon=":material/error:",
            )
        else:
            if not results:
                st.info("No matching products were found.")
            else:
                st.success(f"Found {len(results)} distinct products.")
                root = dataset_root()
                columns = st.columns(2, gap="large")
                for position, record in enumerate(results):
                    with columns[position % 2]:
                        render_result(record, position + 1, root)
