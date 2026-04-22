"""
THIS SCRIPT ALLOWS INDEX TO BUILD IN THE BACKGROUND. AFTER LOADING RECOMMENDATIONS WILL BE READY
"""
from contextlib import asynccontextmanager
from typing import Any
import os
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
from google.cloud import bigquery


class RecommendationRequest(BaseModel):
    anime_name: str


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET = os.getenv("BQ_DATASET")
BQ_TABLE = os.getenv("BQ_TABLE")

if not PROJECT_ID or not BQ_DATASET or not BQ_TABLE:
    raise RuntimeError("Missing BigQuery environment variables.")

TABLE_REF = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
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


def load_anime_catalog_background():
    """
    Build the in-memory recommendation index in the background.
    This should never crash the whole app process.
    """
    app.state.index_loading = True
    app.state.index_ready = False
    app.state.index_error = None

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

        anime_embeddings = app.state.model.encode(
            anime_texts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        name_to_index = {}
        for idx, row in enumerate(rows):
            name_to_index[row[0].strip().lower()] = idx

        app.state.anime_rows = rows
        app.state.anime_texts = anime_texts
        app.state.anime_embeddings = anime_embeddings
        app.state.name_to_index = name_to_index
        app.state.index_ready = True

    except Exception as e:
        app.state.index_error = str(e)
        app.state.index_ready = False

    finally:
        app.state.index_loading = False


def start_background_index_build():
    thread = threading.Thread(target=load_anime_catalog_background, daemon=True)
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model once
    app.state.model = SentenceTransformer(MODEL_NAME)

    # Initialize state
    app.state.anime_rows = []
    app.state.anime_texts = []
    app.state.anime_embeddings = None
    app.state.name_to_index = {}
    app.state.index_ready = False
    app.state.index_loading = False
    app.state.index_error = None

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


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "table": TABLE_REF,
        "catalog_size": len(app.state.anime_rows),
        "index_ready": app.state.index_ready,
        "index_loading": app.state.index_loading,
        "index_error": app.state.index_error,
    }


@app.post("/recommendations")
def recommend(req: RecommendationRequest):
    if not app.state.index_ready:
        raise HTTPException(
            status_code=503,
            detail="Recommendation index is still building. Please try again shortly."
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

        top_k = min(11, len(app.state.anime_rows))
        top_results = util.semantic_search(
            query_embedding.unsqueeze(0),
            app.state.anime_embeddings,
            top_k=top_k
        )[0]

        recommendations = []
        query_name_original = app.state.anime_rows[query_idx][0].strip().lower()

        for hit in top_results:
            idx = hit["corpus_id"]
            score = float(hit["score"])
            anime_name = app.state.anime_rows[idx][0]

            if anime_name.strip().lower() == query_name_original:
                continue

            recommendations.append({
                "anime": anime_name,
                "similarity_score": round(score, 4),
                "genres": app.state.anime_rows[idx][1],
                "studios": app.state.anime_rows[idx][2],
            })

            if len(recommendations) == 10:
                break

        return {
            "query": app.state.anime_rows[query_idx][0],
            "model": MODEL_NAME,
            "recommendations": recommendations
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
