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
Java 17. It keeps the web API and service layers in Java while reusing the
existing Python embedding and FAISS search through a small CLI adapter.

```text
Client
  -> Spring Boot controller
  -> Search service
  -> Python CLI adapter
  -> Sentence Transformer + FAISS
  -> DeepFashion metadata and images
```

Run the backend after installing Java 17 and Maven:

```powershell
cd java-backend
mvn spring-boot:run
```

If the repository is not in the default location, configure the adapter:

```powershell
$env:FASHION_SEARCH_PROJECT_ROOT = "D:\Projects\fashion-semantic-search"
$env:PYTHON_EXECUTABLE = "D:\Projects\fashion-semantic-search\.venv\Scripts\python.exe"
mvn spring-boot:run
```

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

Both endpoints return a consistent response envelope containing `success`,
`data`, `message`, and `timestamp`. Validation and adapter failures are
converted into structured HTTP error responses.
