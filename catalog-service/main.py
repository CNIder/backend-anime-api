from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from google.cloud import bigquery
from google.oauth2 import service_account
from prometheus_fastapi_instrumentator import Instrumentator

import json
import os


# -----------------------------
# Models
# -----------------------------
class Anime(BaseModel):
    anime_id: int
    Name: str
    Ranked: float | None = None


# -----------------------------
# App
# -----------------------------
app = FastAPI(title="Anime Catalog API")

# Prometheus
Instrumentator().instrument(app).expose(app)


# -----------------------------
# Credentials
# -----------------------------
json_string = os.environ.get("API_TOKEN")

if not json_string:
    raise RuntimeError("API_TOKEN environment variable not set")

json_file = json.loads(json_string)

credentials = service_account.Credentials.from_service_account_info(
    json_file
)

client = bigquery.Client(
    credentials=credentials,
    location="europe-west1"
)

TABLE_ID = "cm-labs-exemplo.projeto.anime"


# -----------------------------
# Helper
# -----------------------------
def run_query(query: str, job_config=None):
    query_job = client.query(query, job_config=job_config)
    return list(query_job.result())


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {"status": "ok"}


# Search endpoint MUST come before /anime/{anime_id}
@app.get("/anime/search", response_model=list[Anime])
def search_anime(
    title: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=50),
):
    query = f"""
        SELECT anime_id, Name, Ranked
        FROM `{TABLE_ID}`
        WHERE LOWER(Name) LIKE CONCAT('%', LOWER(@title), '%')
        ORDER BY Ranked ASC
        LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "title",
                "STRING",
                title
            ),
            bigquery.ScalarQueryParameter(
                "limit",
                "INT64",
                limit
            ),
        ]
    )

    rows = run_query(query, job_config)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No anime found matching this title"
        )

    return [dict(row.items()) for row in rows]


# Paginated endpoint
@app.get("/anime", response_model=list[Anime])
def get_animes(
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0)
):
    query = f"""
        SELECT anime_id, Name, Ranked
        FROM `{TABLE_ID}`
        ORDER BY Ranked ASC
        LIMIT @limit
        OFFSET @offset
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "limit",
                "INT64",
                limit
            ),
            bigquery.ScalarQueryParameter(
                "offset",
                "INT64",
                offset
            ),
        ]
    )

    rows = run_query(query, job_config)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No animes found for this range"
        )

    return [dict(row.items()) for row in rows]


# Endpoint by ID
@app.get("/anime/{anime_id}", response_model=Anime)
def get_anime(anime_id: int):

    query = f"""
        SELECT anime_id, Name, Ranked
        FROM `{TABLE_ID}`
        WHERE anime_id = @anime_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "anime_id",
                "INT64",
                anime_id
            )
        ]
    )

    rows = run_query(query, job_config)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Anime not found"
        )

    return dict(rows[0].items())