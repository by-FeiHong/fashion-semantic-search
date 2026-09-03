"""FastAPI application that loads the semantic-search runtime once."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import faiss
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
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
from ai_service.tools import (
    ToolContext,
    ToolError,
    ToolRegistry,
    ToolValidationError,
    UnknownToolError,
    create_tool_registry,
)
from ai_service.agent import AgentRuntime, Planner
from ai_service.llm import LLMProvider, create_llm_provider


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


class AgentRequest(BaseModel):
    query: str = Field(min_length=1)
    max_steps: int | None = Field(default=None, ge=1, le=20)
    demo_mode: bool = False


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


def create_app(
    runtime_loader: Callable[[], SearchRuntime] = load_runtime,
    registry: ToolRegistry | None = None,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    tool_registry = registry or create_tool_registry()
    agent_runtime = AgentRuntime(tool_registry, Planner(llm_provider or create_llm_provider()))
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

    @app.get("/tools")
    def list_tools() -> dict[str, object]:
        return {
            "success": True,
            "tools": [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": spec.input_schema,
                }
                for spec in tool_registry.list_specs()
            ],
        }

    @app.post("/tools/{name}/invoke", response_model=None)
    def invoke_tool(
        name: str,
        arguments: dict[str, object],
        runtime: SearchRuntime = Depends(get_runtime),
    ) -> JSONResponse | dict[str, object]:
        try:
            return tool_registry.invoke(name, arguments, ToolContext(runtime))
        except UnknownToolError as exc:
            return JSONResponse(status_code=404, content=_tool_error(name, exc))
        except ToolValidationError as exc:
            return JSONResponse(status_code=422, content=_tool_error(name, exc))
        except ToolError as exc:
            return JSONResponse(status_code=500, content=_tool_error(name, exc))

    @app.post("/agent/recommend")
    def recommend(
        agent_request: AgentRequest,
        runtime: SearchRuntime = Depends(get_runtime),
    ) -> dict[str, object]:
        return agent_runtime.recommend(
            agent_request.query,
            ToolContext(runtime),
            agent_request.max_steps,
            agent_request.demo_mode,
        )

    return app


def _tool_error(name: str, error: ToolError) -> dict[str, object]:
    payload: dict[str, object] = {
        "success": False,
        "tool": name,
        "data": None,
        "error": {"type": error.error_type, "message": str(error)},
    }
    if isinstance(error, ToolValidationError) and error.details:
        payload["error"]["details"] = error.details
    return payload


app = create_app()
