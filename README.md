# Fashion Semantic Search

An AI-powered fashion search engine using semantic embeddings and vector search.

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
