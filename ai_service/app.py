"""FastAPI application that loads the semantic-search runtime once."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import faiss
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from scripts.search import (
    DEFAULT_DETAILS_PATH,
    DEFAULT_INDEX_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_MODEL_NAME,
    enrich_metadata,
    load_metadata,
    search_text,
)


@dataclass(frozen=True)
class SearchRuntime:
    index: faiss.Index
    metadata: list[dict[str, str]]
    model: SentenceTransformer

    def search(self, query: str, top_k: int) -> list[dict[str, str | float]]:
        return search_text(query, top_k, self.index, self.metadata, self.model)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    topK: int = Field(gt=0, le=100)


def _path_from_env(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default)))


def load_runtime() -> SearchRuntime:
    index_path = _path_from_env("FASHION_SEARCH_INDEX_PATH", DEFAULT_INDEX_PATH)
    metadata_path = _path_from_env(
        "FASHION_SEARCH_METADATA_PATH", DEFAULT_METADATA_PATH
    )
    details_path = _path_from_env("FASHION_SEARCH_DETAILS_PATH", DEFAULT_DETAILS_PATH)
    model_name = os.getenv("FASHION_SEARCH_MODEL_NAME", DEFAULT_MODEL_NAME)
    allow_download = os.getenv("FASHION_SEARCH_ALLOW_MODEL_DOWNLOAD", "false").lower() in {
        "1", "true", "yes"
    }

    if not index_path.is_file():
        raise FileNotFoundError(f"FAISS index was not found: {index_path}")
    index = faiss.read_index(str(index_path))
    metadata = enrich_metadata(load_metadata(metadata_path), details_path)
    if index.ntotal != len(metadata):
        raise ValueError(
            f"FAISS and metadata counts do not match: {index.ntotal:,} != "
            f"{len(metadata):,}."
        )
    model = SentenceTransformer(model_name, local_files_only=not allow_download)
    return SearchRuntime(index=index, metadata=metadata, model=model)


def create_app(runtime_loader: Callable[[], SearchRuntime] = load_runtime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Iterator[None]:
        app.state.search_runtime = runtime_loader()
        yield

    app = FastAPI(title="Fashion Semantic Search AI Service", lifespan=lifespan)

    def get_runtime(request: Request) -> SearchRuntime:
        return request.app.state.search_runtime

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    @app.post("/search")
    def search(
        search_request: SearchRequest,
        runtime: SearchRuntime = Depends(get_runtime),
    ) -> list[dict[str, str | float]]:
        return runtime.search(search_request.query, search_request.topK)

    return app


app = create_app()
