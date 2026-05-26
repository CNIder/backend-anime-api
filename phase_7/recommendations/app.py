"""
THIS SCRIPT ALLOWS INDEX TO BUILD IN THE BACKGROUND. AFTER LOADING RECOMMENDATIONS WILL BE READY
"""
from contextlib import asynccontextmanager
from typing import Any
from urllib import error, request
import json
import os
import threading
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    anime_name: str


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RECOMMENDATIONS_MODE = os.getenv("RECOMMENDATIONS_MODE", "full").strip().lower()
SMOKE_MODES = {"smoke", "disabled", "mock"}
IS_SMOKE_MODE = RECOMMENDATIONS_MODE in SMOKE_MODES

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET = os.getenv("BQ_DATASET")
BQ_TABLE = os.getenv("BQ_TABLE")
ANALYTICS_SERVICE_URL = os.getenv(
    "ANALYTICS_SERVICE_URL",
    "http://analytics.anime-api.svc.cluster.local"
).rstrip("/")
ANALYTICS_TIMEOUT_SECONDS = float(os.getenv("ANALYTICS_TIMEOUT_SECONDS", "3"))
INDEX_BATCH_SIZE = int(os.getenv("INDEX_BATCH_SIZE", "256"))

if not IS_SMOKE_MODE and (not PROJECT_ID or not BQ_DATASET or not BQ_TABLE):
    raise RuntimeError("Missing BigQuery environment variables.")

TABLE_REF = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}" if not IS_SMOKE_MODE else None
client = None

if not IS_SMOKE_MODE:
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper() == "UNKNOWN":
        return ""
    return text


def anime_to_text(row: tuple) -> str:
    name, genres, studios = row

    parts = [
        f"Title: {safe_text(name)}",
        f"Genres: {safe_text(genres)}",
        f"Studios: {safe_text(studios)}",
    ]

    return ". ".join(part for part in parts if not part.endswith(": "))


def reset_index_progress(phase: str = "idle", total: int = 0):
    app.state.index_progress = {
        "phase": phase,
        "processed": 0,
        "total": total,
        "percent": 0.0,
        "started_at": None,
        "elapsed_seconds": 0.0,
        "eta_seconds": None,
    }


def update_index_progress(phase: str, processed: int, total: int, started_at: float | None):
    elapsed_seconds = round(time.time() - started_at, 2) if started_at else 0.0
    percent = round((processed / total) * 100, 2) if total else 0.0
    eta_seconds = None

    if started_at and processed > 0 and processed < total:
        rate = processed / elapsed_seconds if elapsed_seconds > 0 else 0
        eta_seconds = round((total - processed) / rate, 2) if rate > 0 else None

    # This state is read by /health and /recommendations/index-status while the background
    # thread builds embeddings, giving clients enough data for a progress bar and ETA.
    app.state.index_progress = {
        "phase": phase,
        "processed": processed,
        "total": total,
        "percent": percent,
        "started_at": started_at,
        "elapsed_seconds": elapsed_seconds,
        "eta_seconds": eta_seconds,
    }


def get_user_choice(anime_name: str) -> dict:
    payload = json.dumps({"anime_name": anime_name}).encode("utf-8")
    user_choice_url = f"{ANALYTICS_SERVICE_URL}/analytics/anime/user-choice-score"
    http_request = request.Request(
        user_choice_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=ANALYTICS_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Analytics user_choice request failed with HTTP {e.code}: {error_body}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Analytics user_choice service call failed: {str(e)}"
        )


def compact_user_choice(user_choice: dict) -> dict:
    return {
        "user_choice_score": user_choice.get("user_choice_score"),
    }


def user_choice_response_item(row: tuple, user_choice: dict, rank: int | None = None) -> dict:
    name, genres, studios = row
    item = {
        "anime": name,
        "user_choice_score": user_choice["user_choice_score"],
        "genres": genres,
        "studios": studios,
    }

    # Recommendation entries are numbered after sorting by user_choice_score.
    if rank is not None:
        item = {"rank": rank, **item}

    return item


def load_anime_catalog_background():
    """
    Build the in-memory recommendation index in the background.
    This should never crash the whole app process.
    """
    app.state.index_loading = True
    app.state.index_ready = False
    app.state.index_error = None
    reset_index_progress("querying_bigquery")
    started_at = time.time()

    try:
        query = f"""
        SELECT
            name,
            genres,
            studios
        FROM `{TABLE_REF}`
        WHERE name IS NOT NULL
          AND TRIM(name) != ''
        """
        rows_iter = client.query(query).result()
        rows = [(row.name, row.genres, row.studios) for row in rows_iter]

        if not rows:
            raise RuntimeError("No anime rows found in BigQuery.")

        anime_texts = [anime_to_text(row) for row in rows]
        total = len(anime_texts)
        update_index_progress("building_embeddings", 0, total, started_at)

        embedding_batches = []
        for start in range(0, total, INDEX_BATCH_SIZE):
            end = min(start + INDEX_BATCH_SIZE, total)
            batch_embeddings = app.state.model.encode(
                anime_texts[start:end],
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            embedding_batches.append(batch_embeddings)
            update_index_progress("building_embeddings", end, total, started_at)

        anime_embeddings = app.state.torch.cat(embedding_batches, dim=0)
        update_index_progress("finalizing_index", total, total, started_at)

        name_to_index = {}
        for idx, row in enumerate(rows):
            name_to_index[row[0].strip().lower()] = idx

        app.state.anime_rows = rows
        app.state.anime_texts = anime_texts
        app.state.anime_embeddings = anime_embeddings
        app.state.name_to_index = name_to_index
        app.state.index_ready = True
        update_index_progress("ready", total, total, started_at)

    except Exception as e:
        app.state.index_error = str(e)
        app.state.index_ready = False
        total = app.state.index_progress.get("total", 0)
        processed = app.state.index_progress.get("processed", 0)
        update_index_progress("error", processed, total, started_at)

    finally:
        app.state.index_loading = False


def start_background_index_build():
    thread = threading.Thread(target=load_anime_catalog_background, daemon=True)
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state
    app.state.model = None
    app.state.semantic_util = None
    app.state.torch = None
    app.state.anime_rows = []
    app.state.anime_texts = []
    app.state.anime_embeddings = None
    app.state.name_to_index = {}
    app.state.index_ready = False
    app.state.index_loading = False
    app.state.index_error = None
    reset_index_progress()

    if not IS_SMOKE_MODE:
        # Import and load the ML stack only when the real recommendation engine is enabled.
        from sentence_transformers import SentenceTransformer, util
        import torch

        app.state.semantic_util = util
        app.state.torch = torch
        app.state.model = SentenceTransformer(MODEL_NAME)

        # Start index build in background
        start_background_index_build()

    yield

    # Optional cleanup
    app.state.model = None
    app.state.anime_rows = []
    app.state.anime_texts = []
    app.state.anime_embeddings = None
    app.state.name_to_index = {}
    app.state.index_ready = False
    app.state.index_loading = False
    app.state.index_error = None
    reset_index_progress()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": RECOMMENDATIONS_MODE,
        "model": MODEL_NAME,
        "table": TABLE_REF,
        "analytics_service_url": ANALYTICS_SERVICE_URL,
        "catalog_size": len(getattr(app.state, "anime_rows", [])),
        "index_ready": getattr(app.state, "index_ready", False),
        "index_loading": getattr(app.state, "index_loading", False),
        "index_error": getattr(app.state, "index_error", None),
        "index_progress": getattr(app.state, "index_progress", {}),
    }


@app.get("/recommendations/health")
def recommendations_health():
    return health()


@app.get("/recommendations/index-status")
def recommendations_index_status():
    return {
        "index_ready": getattr(app.state, "index_ready", False),
        "index_loading": getattr(app.state, "index_loading", False),
        "index_error": getattr(app.state, "index_error", None),
        "index_progress": getattr(app.state, "index_progress", {}),
    }


@app.get("/recommendations/index-progress-page", response_class=HTMLResponse)
def recommendations_index_progress_page():
    # This small self-refreshing page is useful during demos because it turns the JSON
    # index-status endpoint into a visible progress bar with ETA.
    return """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Recommendation Index Progress</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 32px; color: #17202a; }
        main { max-width: 720px; }
        .bar { width: 100%; height: 24px; border: 1px solid #ccd6e0; border-radius: 8px; overflow: hidden; }
        .fill { height: 100%; width: 0%; background: #0f766e; transition: width 300ms ease; }
        dl { display: grid; grid-template-columns: 180px 1fr; gap: 8px 12px; }
        dt { font-weight: 700; }
        dd { margin: 0; }
        code { background: #eef3f8; padding: 2px 5px; border-radius: 4px; }
      </style>
    </head>
    <body>
      <main>
        <h1>Recommendation Index Progress</h1>
        <div class="bar"><div id="fill" class="fill"></div></div>
        <p id="summary">Loading status...</p>
        <dl>
          <dt>Phase</dt><dd id="phase"></dd>
          <dt>Processed</dt><dd id="processed"></dd>
          <dt>Elapsed</dt><dd id="elapsed"></dd>
          <dt>ETA</dt><dd id="eta"></dd>
          <dt>Ready</dt><dd id="ready"></dd>
          <dt>Error</dt><dd id="error"></dd>
        </dl>
      </main>
      <script>
        function fmt(seconds) {
          if (seconds === null || seconds === undefined) return "--";
          const rounded = Math.max(0, Math.round(seconds));
          const minutes = Math.floor(rounded / 60);
          const rest = rounded % 60;
          return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
        }

        async function refresh() {
          const response = await fetch("/recommendations/index-status", { cache: "no-store" });
          const status = await response.json();
          const progress = status.index_progress || {};
          const percent = progress.percent || 0;
          document.getElementById("fill").style.width = `${percent}%`;
          document.getElementById("summary").textContent = `${percent}% complete`;
          document.getElementById("phase").textContent = progress.phase || "unknown";
          document.getElementById("processed").textContent = `${progress.processed || 0} / ${progress.total || 0}`;
          document.getElementById("elapsed").textContent = fmt(progress.elapsed_seconds);
          document.getElementById("eta").textContent = fmt(progress.eta_seconds);
          document.getElementById("ready").textContent = String(status.index_ready);
          document.getElementById("error").textContent = status.index_error || "";
        }

        refresh();
        setInterval(refresh, 2000);
      </script>
    </body>
    </html>
    """


@app.post("/recommendations")
def recommend(req: RecommendationRequest):
    if IS_SMOKE_MODE:
        query_user_choice = compact_user_choice(get_user_choice(req.anime_name))
        return {
            "input_anime": {
                "anime": req.anime_name,
                "user_choice_score": query_user_choice["user_choice_score"],
                "genres": None,
                "studios": None,
            },
            "mode": RECOMMENDATIONS_MODE,
            "recommendations": [],
            "detail": "Recommendation model disabled for low-memory full-application smoke testing."
        }

    if not app.state.index_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Recommendation index is still building.",
                "index_status": recommendations_index_status(),
            }
        )

    try:
        query_name = req.anime_name.strip().lower()
        query_idx = app.state.name_to_index.get(query_name)

        if query_idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"Anime '{req.anime_name}' not found."
            )

        query_embedding = app.state.anime_embeddings[query_idx]
        query_row = app.state.anime_rows[query_idx]
        query_display_name = query_row[0]
        query_user_choice = compact_user_choice(get_user_choice(query_display_name))

        top_k = min(11, len(app.state.anime_rows))
        top_results = app.state.semantic_util.semantic_search(
            query_embedding.unsqueeze(0),
            app.state.anime_embeddings,
            top_k=top_k
        )[0]

        recommendations = []
        query_name_original = app.state.anime_rows[query_idx][0].strip().lower()

        for hit in top_results:
            idx = hit["corpus_id"]
            anime_name = app.state.anime_rows[idx][0]

            if anime_name.strip().lower() == query_name_original:
                continue

            user_choice = compact_user_choice(get_user_choice(anime_name))
            recommendations.append(user_choice_response_item(app.state.anime_rows[idx], user_choice))

            if len(recommendations) == 10:
                break

        # The model chooses the candidate set; user_choice_score controls the final display order.
        recommendations.sort(
            key=lambda item: item["user_choice_score"] if item["user_choice_score"] is not None else -1,
            reverse=True
        )

        ranked_recommendations = [
            {"rank": rank, **item}
            for rank, item in enumerate(recommendations, start=1)
        ]

        return {
            "input_anime": user_choice_response_item(query_row, query_user_choice),
            "recommendations": ranked_recommendations
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


@app.post("/reload-index")
def reload_index():
    if app.state.index_loading:
        return {"status": "already_loading"}

    print("Starting recommendation index in background...")
    start_background_index_build()
    return {"status": "reload_started"}
