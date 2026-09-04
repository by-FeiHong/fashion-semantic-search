# Fashion Semantic Search

An AI-powered fashion search engine using semantic embeddings and vector search.

## Docker Compose one-command stack

The Compose stack starts MySQL, Redis, the FastAPI AI service, and Spring Boot on
one private network. Spring Boot uses the service names `mysql`, `redis`, and
`fastapi`; its existing non-Docker defaults still use `localhost`. MySQL and
Redis are not published to the host, while the two HTTP APIs remain available
on ports 8080 and 8000 by default.

Large FAISS, metadata, and model files are not copied into either image. The
`data` directory and Hugging Face cache are mounted read-only from the host.
Before the first start, copy the example environment file and set real passwords
and the path to the existing model cache:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose config
docker compose up --build -d
docker compose ps
```

If port 8080 or 8000 is already in use, set an override in `.env` (for example,
`SPRING_BOOT_PORT_HOST=18080`) or for the current PowerShell session:

```powershell
$env:SPRING_BOOT_PORT_HOST = "18080"
docker compose up -d
Invoke-RestMethod http://localhost:18080/api/health
```

On Windows, use forward slashes for an absolute cache path in `.env`, for example
`C:/Users/alice/.cache/huggingface`. The mounted cache must contain
`sentence-transformers/all-MiniLM-L6-v2`; otherwise set
`FASHION_SEARCH_ALLOW_MODEL_DOWNLOAD=true` and use a writable model mount, or
download the model before starting. The default data mount expects:

```text
data/processed/fashion.index
data/processed/metadata_index.csv
data/processed/metadata.csv
```

Compose waits for MySQL, Redis, and FastAPI health checks before starting Spring
Boot. Once all four services are healthy, verify the public API from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
Invoke-RestMethod http://localhost:8080/api/search -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"minimal black dress","topK":5}'
```

Useful lifecycle commands:

```powershell
# Follow every service, or only one service
docker compose logs -f
docker compose logs -f fastapi

# Stop containers while preserving the MySQL named volume
docker compose down

# Rebuild images and recreate containers after code changes
docker compose up --build --force-recreate -d

# Remove containers and the persistent MySQL data (destructive)
docker compose down --volumes
```

The named volume is `fashion-semantic-search_mysql_data` by default. `docker
compose down` preserves it; `docker compose down --volumes` permanently removes
the database data. Do not commit `.env`; only `.env.example` is intended for
version control.

## Features

- Natural language search
- Semantic similarity retrieval
- Fashion product discovery

## Roadmap

- [ ] Dataset integration
- [ ] Semantic embedding
- [ ] Vector search
- [ ] Streamlit UI
- [ ] Image search
- [ ] AI stylist

## Tech Stack

- Python
- FastAPI
- Streamlit
- Sentence Transformers
- FAISS

## Dataset Preparation

Place the DeepFashion In-shop Clothes Retrieval Benchmark outside the repository,
then run the preparation scripts in order from the project root:

```powershell
python scripts/check_dataset.py
python scripts/load_metadata.py
python scripts/export_metadata.py
```

The export step creates `data/processed/metadata.csv` in UTF-8 format. It also
creates `metadata.parquet` when pandas and a compatible Parquet engine are
available.

## Embeddings

Install the project dependencies, then run the 100-record embedding smoke test
from the project root:

```powershell
python -m pip install -r requirements.txt
python scripts/build_embeddings.py
```

The script combines each product's color and description, generates normalized
text embeddings with `sentence-transformers/all-MiniLM-L6-v2`, and writes the
array plus its aligned `metadata_index.csv` file to `data/processed/`.

For example, generate a 1,000-record development embedding file:

```powershell
python scripts/build_embeddings.py --limit 1000 --output data/processed/embeddings_1000.npy
```

Use `--limit 0` to process the complete metadata file.

To build the complete application archive without overwriting the active metadata
during encoding:

```powershell
python scripts/build_embeddings.py --limit 0 --batch-size 64 `
  --output data/processed/embeddings_full.npy `
  --metadata-output data/processed/metadata_index_full.csv
python scripts/build_index.py `
  --embeddings data/processed/embeddings_full.npy `
  --metadata data/processed/metadata_index_full.csv `
  --output data/processed/fashion_full.index
```

## Vector Search

The active app files are `fashion.index` and `metadata_index.csv`. Build an exact
cosine-similarity FAISS index and run a natural-language query:

```powershell
python scripts/build_index.py
python scripts/search.py "minimal black dress" --top-k 5
```

## Streamlit MVP

The app uses `D:\Datasets\DeepFashion\In-shop` by default. To use another
location, set `DEEPFASHION_ROOT` before launching it:

```powershell
$env:DEEPFASHION_ROOT = "D:\Datasets\DeepFashion\In-shop"
streamlit run app.py
```

Enter a natural-language description, choose the number of distinct products,
and select **Search**. The app displays each item's similarity score, metadata,
and DeepFashion image.

## CLIP visual search

Build a visual index with one representative image for each distinct product:

```powershell
python scripts/build_clip_index.py --batch-size 32
```

The builder can also create an experimental per-item average of up to four
distinct views with `--views-per-item 4`. This is not the app default: on the
current benchmark, equal-weight view averaging performs worse than using the
best representative image.

For max-score multi-view retrieval, keep each view as an independent vector and
deduplicate by item at query time:

```powershell
python scripts/build_clip_index.py --views-per-item 4 --index-mode view-max `
  --batch-size 32 `
  --embeddings data/processed/clip_viewmax_embeddings.npy `
  --metadata data/processed/clip_viewmax_metadata.csv `
  --index data/processed/fashion_clip_viewmax.index
```

On the current fixed benchmark, view-max ties the representative-image Visual
score but uses roughly four times as many vectors, so it remains an experimental
candidate rather than the app default.

The CLIP and hybrid-search scripts are experimental. The current Streamlit MVP
intentionally uses the stable MiniLM text-search path only.

Run the fixed category-level retrieval benchmark after changing models, query
encoding, or fusion weights:

```powershell
python scripts/evaluate_search.py
```

To evaluate a candidate visual index before switching the app:

```powershell
python scripts/evaluate_search.py `
  --clip-index data/processed/fashion_clip_multiview.index `
  --clip-metadata data/processed/clip_multiview_metadata.csv
```

## Java backend

The `java-backend/` module is a Spring Boot 3 application using Maven and
Java 17. Semantic search runs in a persistent FastAPI service, so the model,
FAISS index, and metadata are loaded once at service startup instead of once
per request. `scripts/search.py` remains available for offline debugging and
regression checks.

```text
Client
  -> Spring Boot controller
  -> Search service
  -> SearchEnginePort
  -> HTTP adapter
  -> persistent FastAPI service
  -> Sentence Transformer + FAISS (loaded once)
  -> DeepFashion metadata and images
```

The Java backend follows a ports-and-adapters boundary: business logic depends
on `SearchEnginePort`, while `HttpSearchEngineAdapter` owns HTTP and JSON
translation. The service layer does not depend on FastAPI or HTTP details.

### Complete local startup order

From the project root, install dependencies and start the AI service first:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn ai_service.app:app --host 127.0.0.1 --port 8000
```

The FastAPI process must be started from the project root so its default paths
resolve to `data/processed/fashion.index`, `metadata_index.csv`, and
`metadata.csv`. Verify that the initialized service is ready:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

In separate terminals, start Redis and MySQL as documented below, then start
the Java API:

Run the backend after installing Java 17 and Maven:

```powershell
cd java-backend
mvn spring-boot:run
```

The HTTP adapter is configured in
`java-backend/src/main/resources/application.yml`:

```yaml
fashion-search:
  ai-service:
    base-url: ${FASHION_SEARCH_AI_BASE_URL:http://localhost:8000}
    connect-timeout: ${FASHION_SEARCH_AI_CONNECT_TIMEOUT:2s}
    read-timeout: ${FASHION_SEARCH_AI_READ_TIMEOUT:10s}
```

Environment variables can override every deployment-specific value:

```powershell
$env:FASHION_SEARCH_AI_BASE_URL = "http://localhost:8000"
$env:FASHION_SEARCH_AI_CONNECT_TIMEOUT = "2s"
$env:FASHION_SEARCH_AI_READ_TIMEOUT = "10s"
mvn spring-boot:run
```

The Python service also supports `FASHION_SEARCH_INDEX_PATH`,
`FASHION_SEARCH_METADATA_PATH`, `FASHION_SEARCH_DETAILS_PATH`,
`FASHION_SEARCH_MODEL_NAME`, and `FASHION_SEARCH_ALLOW_MODEL_DOWNLOAD`.

### Lightweight Tool Framework

The AI service now exposes a small framework for later Agent/LLM orchestration,
without LangChain, LangGraph, CrewAI, or an Agents SDK. A `@tool` decorator builds
JSON-compatible input schemas from Pydantic models, while `ToolRegistry` provides
registration, lookup, schema listing, validation, and a single invocation boundary.
All tools share the already-loaded semantic-search runtime.

```text
FastAPI -> ToolRegistry -> semantic_search / filters / build_outfit
                         -> persistent SearchRuntime -> FAISS + model
```

Available tools:

- `semantic_search`: reuses the persistent semantic index.
- `filter_by_category`: filters an explicit candidate list.
- `filter_by_price`: uses real `price` fields by default. If none exist, it returns
  `unsupported`; deterministic synthetic values are used only with `demo_mode=true`
  and are marked `price_source=synthetic_demo`.
- `build_outfit`: deterministically picks the first matching unused candidate for
  each requested category and reports missing categories.

List tool definitions and generated input schemas:

```powershell
Invoke-RestMethod http://localhost:8000/tools
```

Invoke semantic search through the tool boundary:

```powershell
Invoke-RestMethod http://localhost:8000/tools/semantic_search/invoke `
  -Method Post -ContentType "application/json" `
  -Body '{"query":"minimal black dress","top_k":5}'
```

Responses use `{success, tool, data, error}`. Unknown tools return HTTP 404,
argument validation errors return 422, and unexpected execution failures return
500. Structured logs include only the tool name, elapsed time, result count, or
error type; full query text is not logged.

Structured logs cover controller, service, and adapter boundaries with the
query, `topK`, elapsed time, outcome, and safe error category. Python stderr and
exception stack traces are deliberately excluded from request-failure logs.
Adapter failures use the same response envelope as validation failures:
timeouts return HTTP 504, upstream 5xx and invalid JSON return HTTP 502, and
connection failures return HTTP 503.

Health check:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
```

Text search:

```powershell
Invoke-RestMethod http://localhost:8080/api/search `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"minimal black dress","topK":5}'
```

Equivalent `curl` examples:

```powershell
curl.exe http://localhost:8080/api/health
curl.exe -X POST http://localhost:8080/api/search `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"minimal black dress\",\"topK\":5}'
```

Search statistics (the default returns the top 10 queries):

```powershell
Invoke-RestMethod http://localhost:8080/api/stats
Invoke-RestMethod "http://localhost:8080/api/stats?limit=5"
```

Equivalent `curl` examples:

```powershell
curl.exe http://localhost:8080/api/stats
curl.exe "http://localhost:8080/api/stats?limit=5"
```

The optional `limit` query parameter accepts values from 1 through 50. A
successful response uses the standard envelope and contains aggregate search
history data:

```json
{
  "success": true,
  "data": {
    "totalSearches": 120,
    "cacheHitRate": 0.75,
    "averageDurationMs": 214.5,
    "topQueries": [
      {
        "query": "minimal black dress",
        "count": 24
      }
    ]
  },
  "message": "OK",
  "timestamp": "2026-08-06T00:00:00Z"
}
```

When no searches have been recorded, counts, cache-hit rate, and average
duration are zero and `topQueries` is empty. Top queries are ordered by count
descending, then query ascending for deterministic results.

All endpoints return a consistent response envelope containing `success`,
`data`, `message`, and `timestamp`. Validation and adapter failures are
converted into structured HTTP error responses.

### Redis search cache

The Spring Boot service uses a Cache-Aside flow through a technology-neutral
`CachePort`. Search keys use the prefix `fashion-search:search:v1`, a SHA-256
digest of the normalized query, and `topK`. Query text is not stored in keys or
logs. A cache hit skips the AI service; a miss calls the search engine
and stores the result for 10 minutes by default.

Redis is an optional performance dependency. Read or write failures are logged
with a safe query digest and automatically fall back to the normal
`SearchEnginePort`, so `/api/search` remains available when Redis is offline.

Configuration:

```yaml
spring:
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
      connect-timeout: ${REDIS_CONNECT_TIMEOUT:1s}
      timeout: ${REDIS_COMMAND_TIMEOUT:1s}

fashion-search:
  cache:
    key-prefix: ${FASHION_SEARCH_CACHE_PREFIX:fashion-search:search:v1}
    ttl: ${FASHION_SEARCH_CACHE_TTL:10m}
```

Start only Redis with Docker:

```powershell
docker run --name fashion-search-redis --rm -p 6379:6379 redis:7-alpine
```

The backend can also run without Redis; searches then use the FastAPI search
service directly.

### MySQL search history

After a successful search, the service writes the normalized query, resolved
`topK`, total duration, and cache-hit status to `search_history`. Cache hits are
recorded with `cacheHit=true`; cache misses that call the FastAPI search service
are recorded with `cacheHit=false`. Persistence is reached through a
`SearchHistoryPort`, keeping JPA out of the controller and search-domain
boundary. A database write failure is logged as `search_history_save_failed`
and never changes the search response or HTTP status.

Start a local MySQL 8 instance with Docker:

```powershell
docker run --name fashion-search-mysql --rm `
  -e MYSQL_DATABASE=fashion_search `
  -e MYSQL_USER=fashion_search `
  -e MYSQL_PASSWORD=fashion_search `
  -e MYSQL_ROOT_PASSWORD=change-me `
  -p 3306:3306 `
  mysql:8.4
```

The connection settings support environment variables (the values below are
also the development defaults):

```powershell
$env:MYSQL_HOST = "localhost"
$env:MYSQL_PORT = "3306"
$env:MYSQL_DATABASE = "fashion_search"
$env:MYSQL_USERNAME = "fashion_search"
$env:MYSQL_PASSWORD = "fashion_search"
cd java-backend
mvn spring-boot:run
```

Hibernate creates or updates `search_history` at application startup and keeps
indexes on the search query and creation time. For production deployments, set
a strong password and manage schema changes with a migration tool.

Java tests use an in-memory H2 database and MockWebServer; they do not require
MySQL, Redis, or a running Python service. Run the complete verification suite:

```powershell
cd java-backend
mvn test
cd ..
python -m pytest
python -m compileall ai_service scripts tests
git diff --check
```
# Single-Agent Planner and Tool Calling

The Python AI service includes a provider-neutral `LLMProvider`, a Pydantic-validated
`Planner`, and a bounded `AgentRuntime`. The runtime executes a plan through the existing
`ToolRegistry`, accumulates tool outputs, skips duplicate calls, and stops at six steps by
default. It returns a compact plan summary and tool timing/status trace, never hidden
reasoning or chain-of-thought.

Configuration is injected exclusively through environment variables:

```text
FASHION_LLM_PROVIDER=disabled|openai_compatible
FASHION_LLM_MODEL=<model name>
FASHION_LLM_BASE_URL=<provider API base URL>
FASHION_LLM_API_KEY=<secret>
FASHION_LLM_TIMEOUT_SECONDS=20
```

`disabled` is the safe default. The `openai_compatible` implementation calls a configurable
JSON chat-completions endpoint; tests inject an in-memory stub and never use the network.

Request example:

```powershell
Invoke-RestMethod http://localhost:8000/agent/recommend `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"black and grey minimalist autumn commute outfit","max_steps":6}'
```

If the LLM is unavailable or returns an invalid plan, the service marks the response as
`degraded` and uses a deterministic `semantic_search` plus `build_outfit` plan. A failed
tool is recorded in the trace; later recoverable calls continue with the last good context,
and partial results are returned when available. Price filtering still uses real prices only
unless explicit `demo_mode=true` is supplied.

## Constraint-aware outfit recommendations

`POST /agent/recommend` now always normalizes successful search candidates into a
structured outfit recommendation. The typed plan accepts optional `season`, `occasion`,
`colors`, `style`, `budget`, and `categories` constraints while remaining compatible with
plans that omit them. The LLM is asked for these fields first; the deterministic fallback
recognizes simple English and Chinese season, occasion, color, style, category, and budget
terms.

`build_outfit` groups candidates by canonical category, applies documented substitutions
(for example, a dress may cover a missing top or bottom), and ranks deterministically using
semantic relevance, category fit, and only the color/style/season/occasion metadata that is
actually present. Its response includes `selected_items`, `missing_categories`,
`substitutions`, `constraint_summary`, `score_summary`, and `recommendation_reason`; the
legacy `items` field remains available. A provider-neutral LLM may generate the short reason,
with a deterministic factual explanation as fallback. Hidden reasoning is never returned.

Example response (abbreviated):

```json
{
  "recommendation": {
    "selected_items": [{"requested_category":"top","matched_category":"top","item":{"item_id":"42"},"score":0.71}],
    "missing_categories": ["shoes"],
    "constraint_summary": {"requested":{"season":"autumn","colors":["black","gray"]},"supported":["colors"],"unsupported":["season"]},
    "score_summary": {"overall":0.71,"method":"deterministic_weighted_v1"},
    "recommendation_reason": "Selected 1 item using deterministic category and available attribute matching; no suitable candidate was available for shoes."
  },
  "trace": [], "degraded": false
}
```

DeepFashion metadata does not consistently contain real prices, colors, styles, seasons, or
occasions. Missing attributes are reported as `unsupported` and never invented. Budget is a
hard cumulative constraint only when real prices are available for the candidate set, or
when the request explicitly sends `"demo_mode": true`; synthetic demo prices are clearly
marked `price_source=synthetic_demo`.

## Weather-aware recommendations

The single-agent runtime can enrich requests such as `What should I wear in Lund tomorrow?`
or `哥本哈根后天通勤穿搭` through a provider-neutral `WeatherProvider`. The orchestration is:

```text
query -> Planner + deterministic location/date extraction
      -> weather_lookup -> normalized weather context
      -> deterministic weather-derived suggestions
      -> semantic_search -> build_outfit -> factual recommendation_reason
```

No agent framework or multi-agent system is used. `weather_lookup` is also listed by
`GET /tools` and may be invoked directly. Its input requires `location` and accepts either a
`date` in `YYYY-MM-DD` form or a `date_offset` from 0 through 14. Its normalized response
includes the usable `temperature`, `feels_like`, `precipitation`, `rain`, `wind`, and
`condition` fields, plus `source` and `provider` metadata.

Weather is disabled by default. A generic JSON HTTP adapter can be configured without
changing planner, tool, or recommendation code:

```powershell
$env:FASHION_WEATHER_PROVIDER = "http"
$env:FASHION_WEATHER_BASE_URL = "https://weather.example/v1/forecast"
$env:FASHION_WEATHER_API_KEY = "replace-with-secret"
$env:FASHION_WEATHER_TIMEOUT_SECONDS = "5"
```

The adapter sends `location`, `date`, and, when configured, `api_key` query parameters. It
accepts a top-level record or a `weather`, `current`, or `forecast` record and normalizes
common JSON names such as `temp_c`, `feelslike_c`, `rain_mm`, and `wind_mps`. This deliberately
small contract also makes it straightforward to place a vendor-specific gateway in front of
the service. API keys are read from configuration only and are never included in tool output.

Example request:

```powershell
Invoke-RestMethod http://localhost:8000/agent/recommend `
  -Method Post -ContentType "application/json" `
  -Body '{"query":"明天 Lund 穿什么","max_steps":6}'
```

Example weather portion of the response:

```json
{
  "recommendation": {
    "weather_context": {
      "location": "lund",
      "date": "2026-09-05",
      "temperature": 7,
      "feels_like": 5,
      "precipitation": 1.2,
      "wind": 8,
      "condition": "light rain",
      "source": "weather_provider",
      "provider": "http"
    },
    "constraint_summary": {
      "derived_from_weather": [
        {"constraint": "outerwear", "rule": "temperature_lte_10c", "value": 7},
        {"constraint": "rain_protection", "rule": "precipitation_gt_0", "value": 1.2}
      ]
    },
    "recommendation_reason": "Weather used: lund on 2026-09-05: 7°C, feels like 5°C, precipitation 1.2 mm, wind 8 m/s, light rain. Selected 4 item(s). Derived suggestions: outerwear, rain_protection."
  }
}
```

Weather-derived behavior is deterministic and advisory:

- temperature at or below 10°C adds an `outerwear` category request;
- temperature at or below 5°C adds a `layering` suggestion;
- precipitation above 0 mm (or an explicit rain flag) adds `rain_protection`;
- wind at or above 10 m/s adds `wind_protection`.

Only the `outerwear` rule changes category composition. Layering, rain, and wind suggestions
are reported under `derived_from_weather`; they do not award fictitious item scores because
DeepFashion does not provide reliable weather-protection attributes. The weather explanation
is built from the normalized provider values rather than generated freely by an LLM.

If weather is disabled, times out, fails, or returns no usable temperature, the response is
marked `degraded`, `fallback_reason` records `weather_lookup_failed`, and recommendation
continues without weather. Existing `/health`, `/search`, `/tools`, and `/agent/recommend`
contracts remain compatible apart from the additive tool and response fields.

Location and requested date are sent to the configured weather endpoint. Treat them as
potentially sensitive, choose a provider with suitable retention terms, avoid embedding
personal addresses in queries, and use TLS. Forecast accuracy, units, location resolution,
and supported forecast range depend on the configured provider; the generic adapter assumes
temperature in °C, precipitation in mm, and wind in m/s after any vendor-side normalization.

### Structured user preference memory

The optional memory path is explicit and provider-neutral:

```text
Preferences API -> UserPreferenceStore -> InMemoryUserPreferenceStore
                                         (future MySQL/Redis adapter)
Agent request + optional user_id -> read preferences -> deterministic merge -> search/build_outfit
```

Preferences are never learned implicitly from conversation. Clients write them deliberately:

```powershell
Invoke-RestMethod http://localhost:8000/memory/preferences/user-123 -Method Put `
  -ContentType "application/json" `
  -Body '{"preferred_colors":["black","gray"],"disliked_colors":["white"],"preferred_styles":["minimal"],"preferred_categories":["top","bottom","shoes"],"budget_min":40,"budget_max":300,"notes":"workwear"}'

Invoke-RestMethod http://localhost:8000/memory/preferences/user-123

Invoke-RestMethod http://localhost:8000/memory/preferences/user-123 -Method Patch `
  -ContentType "application/json" -Body '{"budget_max":250}'

Invoke-RestMethod http://localhost:8000/agent/recommend -Method Post `
  -ContentType "application/json" -Body '{"query":"white office outfit under 200","user_id":"user-123"}'
```

The merge priority is current query, then stored preferences, then defaults. Explicit query
colors/styles/categories and budget replace the corresponding memory values. A query value
that conflicts with a disliked value is retained and recorded as `overridden_by_query` in
`applied_preferences`. Otherwise preferred values fill missing constraints, disliked colors
and styles receive a deterministic ranking penalty, and stored budget bounds constrain items
when real (or explicitly enabled demo) prices exist. Responses expose only
`memory_summary` and `applied_preferences`, never hidden reasoning.

The default store is process-local and is lost on restart. `UserPreferenceStore` is the
persistence boundary for future MySQL/Redis adapters. Preference data can be personal data:
use opaque user IDs, authenticate and authorize these endpoints before production use,
encrypt persistent stores and transport, apply retention/deletion policies, and avoid storing
sensitive free text in `notes`.
