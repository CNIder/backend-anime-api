from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from google.cloud import bigquery
from google.oauth2 import service_account
from prometheus_fastapi_instrumentator import Instrumentator

import httpx
import asyncio
import json
import os


# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(title="Ratings Service")

Instrumentator().instrument(app).expose(app)


# --------------------------------------------------
# EXTERNAL SERVICES
# --------------------------------------------------

USERS_SERVICE_URL = "http://user-service:8001"
ANIME_SERVICE_URL = "http://catalog-service:8002"


# --------------------------------------------------
# GLOBAL HTTP CLIENT (REUSED)
# --------------------------------------------------

http_client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100
    )
)


# --------------------------------------------------
# BIGQUERY CONFIG
# --------------------------------------------------

json_string = os.environ.get("API_TOKEN")

if not json_string:
    raise RuntimeError("API_TOKEN environment variable not set")

credentials_info = json.loads(json_string)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info
)

client = bigquery.Client(
    credentials=credentials,
    location="europe-west1"
)

TABLE_ID = "cm-labs-exemplo.projeto.rating"


# --------------------------------------------------
# MODELS
# --------------------------------------------------

class Rating(BaseModel):
    rating_id: int
    user_id: int
    anime_id: int
    score: float = Field(..., ge=0, le=10)
    comment: Optional[str] = None


class RatingCreate(BaseModel):
    user_id: int
    anime_id: int
    score: float = Field(..., ge=0, le=10)
    comment: Optional[str] = Field(None, max_length=500)


class RatingUpdate(BaseModel):
    score: Optional[float] = Field(None, ge=0, le=10)
    comment: Optional[str] = Field(None, max_length=500)


class RatingResponse(BaseModel):
    rating_id: int
    user_id: int
    username: Optional[str]
    anime_id: int
    anime_title: Optional[str]
    score: float
    comment: Optional[str]


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def run_query(query: str, job_config=None):
    query_job = client.query(query, job_config=job_config)
    return list(query_job.result())


async def get_user(user_id: int):

    try:
        response = await http_client.get(
            f"{USERS_SERVICE_URL}/users/{user_id}"
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


async def get_anime(anime_id: int):

    try:
        response = await http_client.get(
            f"{ANIME_SERVICE_URL}/anime/{anime_id}"
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


async def user_exists(user_id: int):
    user = await get_user(user_id)
    return user is not None


async def anime_exists(anime_id: int):
    anime = await get_anime(anime_id)
    return anime is not None


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.get("/")
def root():
    return {"status": "ok"}


# --------------------------------------------------
# GET ALL RATINGS (OPTIMIZED)
# --------------------------------------------------

@app.get("/rating", response_model=List[RatingResponse])
async def get_ratings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):

    query = f"""
        SELECT rating_id, user_id, anime_id, score, comment
        FROM `{TABLE_ID}`
        ORDER BY rating_id ASC
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
            )
        ]
    )

    rows = run_query(query, job_config)

    if not rows:
        return []

    # ----------------------------------------------
    # DEDUPLICATE IDS
    # ----------------------------------------------

    unique_user_ids = list({
        r["user_id"]
        for r in rows
    })

    unique_anime_ids = list({
        r["anime_id"]
        for r in rows
    })

    # ----------------------------------------------
    # FETCH CONCURRENTLY
    # ----------------------------------------------

    user_tasks = [
        get_user(user_id)
        for user_id in unique_user_ids
    ]

    anime_tasks = [
        get_anime(anime_id)
        for anime_id in unique_anime_ids
    ]

    users_result, anime_result = await asyncio.gather(
        asyncio.gather(*user_tasks),
        asyncio.gather(*anime_tasks)
    )

    # ----------------------------------------------
    # CREATE LOOKUP MAPS
    # ----------------------------------------------

    users_map = {
        user_id: user
        for user_id, user in zip(
            unique_user_ids,
            users_result
        )
    }

    anime_map = {
        anime_id: anime
        for anime_id, anime in zip(
            unique_anime_ids,
            anime_result
        )
    }

    # ----------------------------------------------
    # BUILD RESPONSE
    # ----------------------------------------------

    result = []

    for r in rows:

        user = users_map.get(r["user_id"])
        anime = anime_map.get(r["anime_id"])

        result.append({
            "rating_id": r["rating_id"],
            "user_id": r["user_id"],
            "username": (
                user.get("username")
                if user else None
            ),
            "anime_id": r["anime_id"],
            "anime_title": (
                anime.get("Name")
                if anime else None
            ),
            "score": r["score"],
            "comment": r["comment"]
        })

    return result


# --------------------------------------------------
# CREATE RATING
# --------------------------------------------------

@app.post("/rating", response_model=Rating, status_code=201)
async def create_rating(rating: RatingCreate):

    user_task = user_exists(rating.user_id)
    anime_task = anime_exists(rating.anime_id)

    user_ok, anime_ok = await asyncio.gather(
        user_task,
        anime_task
    )

    if not user_ok:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if not anime_ok:
        raise HTTPException(
            status_code=404,
            detail="Anime not found"
        )

    duplicate_query = f"""
        SELECT rating_id
        FROM `{TABLE_ID}`
        WHERE user_id = @user_id
        AND anime_id = @anime_id
        LIMIT 1
    """

    duplicate_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "user_id",
                "INT64",
                rating.user_id
            ),
            bigquery.ScalarQueryParameter(
                "anime_id",
                "INT64",
                rating.anime_id
            ),
        ]
    )

    duplicate_rows = run_query(
        duplicate_query,
        duplicate_config
    )

    if duplicate_rows:
        raise HTTPException(
            status_code=400,
            detail="Rating already exists"
        )

    # WARNING:
    # This ID generation is NOT safe under concurrency
    # Better use UUIDs in production

    id_query = f"""
        SELECT COALESCE(MAX(rating_id), 0) + 1 AS next_id
        FROM `{TABLE_ID}`
    """

    next_id = run_query(id_query)[0]["next_id"]

    insert_query = f"""
        INSERT INTO `{TABLE_ID}`
        (rating_id, user_id, anime_id, score, comment)
        VALUES
        (@rating_id, @user_id, @anime_id, @score, @comment)
    """

    insert_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "rating_id",
                "INT64",
                next_id
            ),
            bigquery.ScalarQueryParameter(
                "user_id",
                "INT64",
                rating.user_id
            ),
            bigquery.ScalarQueryParameter(
                "anime_id",
                "INT64",
                rating.anime_id
            ),
            bigquery.ScalarQueryParameter(
                "score",
                "FLOAT64",
                rating.score
            ),
            bigquery.ScalarQueryParameter(
                "comment",
                "STRING",
                rating.comment
            ),
        ]
    )

    client.query(
        insert_query,
        job_config=insert_config
    ).result()

    return Rating(
        rating_id=next_id,
        user_id=rating.user_id,
        anime_id=rating.anime_id,
        score=rating.score,
        comment=rating.comment
    )


# --------------------------------------------------
# UPDATE RATING
# --------------------------------------------------

@app.put("/rating/{rating_id}", response_model=Rating)
def update_rating(
    rating_id: int,
    rating_update: RatingUpdate
):

    check_query = f"""
        SELECT rating_id, user_id, anime_id, score, comment
        FROM `{TABLE_ID}`
        WHERE rating_id = @rating_id
        LIMIT 1
    """

    check_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "rating_id",
                "INT64",
                rating_id
            )
        ]
    )

    rows = run_query(check_query, check_config)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Rating not found"
        )

    current = rows[0]

    new_score = (
        rating_update.score
        if rating_update.score is not None
        else current["score"]
    )

    new_comment = (
        rating_update.comment
        if rating_update.comment is not None
        else current["comment"]
    )

    update_query = f"""
        UPDATE `{TABLE_ID}`
        SET
            score = @score,
            comment = @comment
        WHERE rating_id = @rating_id
    """

    update_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "score",
                "FLOAT64",
                new_score
            ),
            bigquery.ScalarQueryParameter(
                "comment",
                "STRING",
                new_comment
            ),
            bigquery.ScalarQueryParameter(
                "rating_id",
                "INT64",
                rating_id
            ),
        ]
    )

    client.query(
        update_query,
        job_config=update_config
    ).result()

    return Rating(
        rating_id=current["rating_id"],
        user_id=current["user_id"],
        anime_id=current["anime_id"],
        score=new_score,
        comment=new_comment
    )


# --------------------------------------------------
# DELETE RATING
# --------------------------------------------------

@app.delete("/rating/{rating_id}", status_code=204)
def delete_rating(rating_id: int):

    delete_query = f"""
        DELETE FROM `{TABLE_ID}`
        WHERE rating_id = @rating_id
    """

    delete_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "rating_id",
                "INT64",
                rating_id
            )
        ]
    )

    client.query(
        delete_query,
        job_config=delete_config
    ).result()

    return
