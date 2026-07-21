"""Editorial Streamlit interface for DeepFashion semantic search."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer

from scripts.fusion import fuse_ranked_results
from scripts.search import (
    DEFAULT_MODEL_NAME,
    load_metadata,
    search_text,
    search_unique_items,
)


PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_PATH = PROJECT_ROOT / "data/processed/fashion.index"
METADATA_INDEX_PATH = PROJECT_ROOT / "data/processed/metadata_index.csv"
CATALOG_PATH = PROJECT_ROOT / "data/processed/metadata.csv"
CLIP_INDEX_PATH = PROJECT_ROOT / "data/processed/fashion_clip.index"
CLIP_METADATA_PATH = PROJECT_ROOT / "data/processed/clip_metadata.csv"
DEFAULT_DATASET_ROOT = Path(r"D:\Datasets\DeepFashion\In-shop")
CLIP_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
SEARCH_EXAMPLES = (
    "washed black oversized jacket",
    "boxy neutral knit",
    "distressed dark denim",
    "minimal charcoal shirt",
)


def dataset_root() -> Path:
    """Return the configured DeepFashion In-shop root."""
    return Path(os.environ.get("DEEPFASHION_ROOT", DEFAULT_DATASET_ROOT))


def resolve_image_path(raw_path: str, root: Path) -> Path:
    """Resolve stored absolute paths or paths relative to the dataset root."""
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
    """Load display fields keyed by image path."""
    catalog_path = Path(path)
    if not catalog_path.is_file():
        return {}
    with catalog_path.open(encoding="utf-8", newline="") as file:
        return {row["image_path"]: row for row in csv.DictReader(file)}


@st.cache_resource(show_spinner="OPENING THE ARCHIVE")
def load_search_resources(
    index_version: int,
    metadata_version: int,
) -> tuple[faiss.Index, list[dict[str, str]], SentenceTransformer]:
    """Load and cache the FAISS index, aligned metadata, and encoder."""
    if not INDEX_PATH.is_file():
        raise FileNotFoundError(f"FAISS index not found: {INDEX_PATH}")
    index = faiss.read_index(str(INDEX_PATH))
    metadata = load_metadata(METADATA_INDEX_PATH)
    try:
        model = SentenceTransformer(DEFAULT_MODEL_NAME, local_files_only=True)
    except Exception as error:
        raise RuntimeError(
            "The embedding model is not available locally. Run "
            "scripts/build_embeddings.py once while online, then restart."
        ) from error
    return index, metadata, model


@st.cache_resource(show_spinner="OPENING THE VISUAL ARCHIVE")
def load_clip_resources(
    index_version: int,
    metadata_version: int,
) -> tuple[faiss.Index, list[dict[str, str]], SentenceTransformer]:
    """Load the CLIP image index, item metadata, and multimodal encoder."""
    if not CLIP_INDEX_PATH.is_file() or not CLIP_METADATA_PATH.is_file():
        raise FileNotFoundError("The CLIP visual index has not been built.")
    index = faiss.read_index(str(CLIP_INDEX_PATH))
    metadata = load_metadata(CLIP_METADATA_PATH)
    if index.ntotal != len(metadata):
        raise ValueError(
            f"CLIP index and metadata counts differ: {index.ntotal:,} != "
            f"{len(metadata):,}."
        )
    model = SentenceTransformer(CLIP_MODEL_NAME, local_files_only=True)
    return index, metadata, model


def use_example() -> None:
    """Move the selected reference query into the search field."""
    selected = st.session_state.get("reference_query")
    if selected:
        st.session_state.search_query = selected


def run_search(query: str, top_k: int, search_lens: str) -> None:
    """Execute a search and preserve it across subsequent reruns."""
    if not query.strip():
        st.warning("Describe a garment before searching.", icon=":material/warning:")
        return
    try:
        if search_lens in {"Visual", "Hybrid"}:
            index, metadata, model = load_clip_resources(
                CLIP_INDEX_PATH.stat().st_mtime_ns,
                CLIP_METADATA_PATH.stat().st_mtime_ns,
            )
            query_vector = model.encode(
                [query.strip()], convert_to_numpy=True, normalize_embeddings=True
            )
            candidate_count = max(top_k, 40) if search_lens == "Hybrid" else top_k
            ranked_vectors = search_unique_items(
                index,
                np.ascontiguousarray(query_vector, dtype=np.float32),
                metadata,
                candidate_count,
            )
            visual_results = [
                {**metadata[vector_id], "score": score}
                for score, vector_id in ranked_vectors
            ]
        if search_lens in {"Description", "Hybrid"}:
            index, metadata, model = load_search_resources(
                INDEX_PATH.stat().st_mtime_ns,
                METADATA_INDEX_PATH.stat().st_mtime_ns,
            )
            details = load_catalog_details(str(CATALOG_PATH))
            candidate_count = max(top_k, 40) if search_lens == "Hybrid" else top_k
            raw_results = search_text(query, candidate_count, index, metadata, model)
            description_results = [
                {**details.get(str(result["image_path"]), {}), **result}
                for result in raw_results
            ]
        if search_lens == "Hybrid":
            st.session_state.results = fuse_ranked_results(
                [(0.7, visual_results), (0.3, description_results)], top_k
            )
        elif search_lens == "Visual":
            st.session_state.results = visual_results
        else:
            st.session_state.results = description_results
        st.session_state.last_query = query.strip()
        st.session_state.last_lens = search_lens
    except FileNotFoundError as error:
        st.error(f"A required archive file is missing. {error}", icon=":material/error:")
    except Exception as error:
        st.error(f"The archive could not be searched: {error}", icon=":material/error:")


def display_description(record: dict[str, Any]) -> str:
    """Return a compact editorial description."""
    description = str(record.get("description") or "Description unavailable.").strip()
    return description if len(description) <= 210 else f"{description[:207].rstrip()}…"


def render_result(record: dict[str, Any], rank: int, root: Path) -> None:
    """Render one product as a restrained archive entry."""
    image_path = resolve_image_path(str(record["image_path"]), root)
    score_label = str(record.get("score_label", "MATCH"))
    st.caption(
        f"NO. {rank:02d}  /  {score_label} {float(record['score']) * 100:05.1f}"
    )
    if image_path.is_file():
        st.image(str(image_path), width="stretch")
    else:
        st.warning(f"IMAGE UNAVAILABLE — {image_path.name}")

    st.subheader(str(record.get("item_id", "UNTITLED")).upper())
    tags = [record.get("color"), record.get("split")]
    st.caption("  ·  ".join(str(tag).upper() for tag in tags if tag))
    st.write(display_description(record))


st.set_page_config(
    page_title="Archive / Semantic Search",
    page_icon=":material/search:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.session_state.setdefault("results", [])
st.session_state.setdefault("last_query", "")
st.session_state.setdefault("last_lens", "Visual")
st.session_state.setdefault("search_query", "")

with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
    st.caption("FSS / 001")
    st.caption("DEEPFASHION ARCHIVE — LONDON 2026")

st.space("large")
st.title("SEARCH THE ARCHIVE")
st.caption(
    "A semantic index of garments, silhouettes and material references. "
    "Describe what you are looking for rather than naming a product."
)

st.space("medium")
st.pills(
    "Reference searches",
    SEARCH_EXAMPLES,
    key="reference_query",
    on_change=use_example,
    label_visibility="collapsed",
)

with st.form("archive_search", border=False):
    query_col, lens_col, count_col = st.columns([5, 1.4, 1], vertical_alignment="bottom")
    with query_col:
        query = st.text_input(
            "Archive query",
            key="search_query",
            placeholder="WASHED BLACK / BOXY / DISTRESSED / MINIMAL",
        )
    with lens_col:
        search_lens = st.selectbox(
            "Search lens",
            ["Visual", "Hybrid", "Description"],
            help="Hybrid combines CLIP garment imagery with catalog descriptions.",
        )
    with count_col:
        top_k = st.selectbox("Edit size", [4, 6, 8, 10], index=1)
    submitted = st.form_submit_button(
        "SEARCH",
        type="primary",
        icon=":material/arrow_forward:",
        width="stretch",
    )

if submitted:
    run_search(query, top_k, search_lens)

try:
    archive_size = faiss.read_index(str(INDEX_PATH)).ntotal if INDEX_PATH.is_file() else 0
except RuntimeError:
    archive_size = 0
try:
    visual_size = (
        faiss.read_index(str(CLIP_INDEX_PATH)).ntotal if CLIP_INDEX_PATH.is_file() else 0
    )
except RuntimeError:
    visual_size = 0

with st.sidebar:
    st.caption("ARCHIVE STATUS")
    st.metric("Visual products", f"{visual_size:,}", border=True)
    st.metric("Text images", f"{archive_size:,}", border=True)
    st.caption(f"VISUAL MODEL\n\n{CLIP_MODEL_NAME}")
    st.caption(f"TEXT MODEL\n\n{DEFAULT_MODEL_NAME}")
    st.caption(f"SOURCE\n\n{dataset_root()}")
    st.caption(
        "Hybrid search fuses visual and description rankings at 70/30. "
        "The individual lenses remain available for comparison."
    )

results = st.session_state.results
if results:
    st.space("large")
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="bottom"):
        st.subheader(f"SELECTED OBJECTS / {len(results):02d}")
        st.caption(
            f'{st.session_state.last_lens.upper()} LENS — '
            f'“{st.session_state.last_query.upper()}”'
        )

    left, right = st.columns(2, gap="large")
    root = dataset_root()
    for position, record in enumerate(results):
        target = left if position % 2 == 0 else right
        with target:
            if position % 4 in (1, 2):
                st.space("medium")
            render_result(record, position + 1, root)
            st.space("large")
elif st.session_state.last_query:
    st.info("No objects matched this reference.", icon=":material/info:")
else:
    st.space("large")
    st.caption("THE CURRENT DEVELOPMENT ARCHIVE CONTAINS A LIMITED INDEX. OPEN THE SIDEBAR FOR DETAILS.")
