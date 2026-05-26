from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import bigquery
from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
import os

app = FastAPI()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET = os.getenv("BQ_DATASET")
BQ_TABLE = os.getenv("BQ_TABLE")

if not PROJECT_ID or not BQ_DATASET or not BQ_TABLE:
    raise RuntimeError("Missing BigQuery environment variables.")

TABLE_REF = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
_client = None

def get_bigquery_client():
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT_ID)
    return _client

class StudioRequest(BaseModel):
    studio_name: str

class GenreRequest(BaseModel):
    genre_name: str

class AnimeUserChoiceRequest(BaseModel):
    anime_name: str

@app.get("/health")
def health():
    return {"status": "ok", "table": TABLE_REF}


@app.get("/analytics/health")
def analytics_health():
    return health()


@app.get("/analytics/anime")
def anime_analytics():
    try:
        query = f"""
        WITH mode_cte AS (
          SELECT score, COUNT(*) AS frequency
          FROM `{TABLE_REF}`
          WHERE score IS NOT NULL
          GROUP BY score
          ORDER BY frequency DESC, score DESC
          LIMIT 1
        ),
        popular_cte AS (
          SELECT name, popularity
          FROM `{TABLE_REF}`
          WHERE popularity IS NOT NULL
          ORDER BY popularity ASC
          LIMIT 1
        ),
        members_cte AS (
          SELECT name, members
          FROM `{TABLE_REF}`
          WHERE members IS NOT NULL
          ORDER BY members DESC
          LIMIT 1
        )
        SELECT
          (SELECT COUNT(*) FROM `{TABLE_REF}`) AS total_anime,
          (SELECT ROUND(AVG(score), 2) FROM `{TABLE_REF}` WHERE score IS NOT NULL) AS average_score,
          (SELECT ROUND(APPROX_QUANTILES(score, 2)[OFFSET(1)], 2) FROM `{TABLE_REF}` WHERE score IS NOT NULL) AS median_score,
          (SELECT score FROM mode_cte) AS mode_score,
          (SELECT frequency FROM mode_cte) AS mode_score_frequency,
          (SELECT ROUND(STDDEV(score), 2) FROM `{TABLE_REF}` WHERE score IS NOT NULL) AS score_standard_deviation,
          (SELECT name FROM popular_cte) AS most_popular_name,
          (SELECT popularity FROM popular_cte) AS most_popular_rank,
          (SELECT name FROM members_cte) AS most_watchlisted_name,
          (SELECT members FROM members_cte) AS most_watchlisted_members
        """
        row = next(get_bigquery_client().query(query).result())

        return {
            "total_anime": row.total_anime,
            "average_score": float(row.average_score) if row.average_score is not None else None,
            "median_score": float(row.median_score) if row.median_score is not None else None,
            "mode_score": float(row.mode_score) if row.mode_score is not None else None,
            "mode_score_frequency": row.mode_score_frequency,
            "score_standard_deviation": float(row.score_standard_deviation) if row.score_standard_deviation is not None else None,
            "most_popular_anime": {
                "name": row.most_popular_name,
                "popularity": row.most_popular_rank
            } if row.most_popular_name is not None else None,
            "anime_in_most_watchlists": {
                "name": row.most_watchlisted_name,
                "members": row.most_watchlisted_members
            } if row.most_watchlisted_name is not None else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")


@app.get("/analytics/studio")
def studio_analytics():
    try:
        query = f"""
        WITH exploded AS (
          SELECT TRIM(studio) AS studio, score
          FROM `{TABLE_REF}`,
          UNNEST(SPLIT(studios, ',')) AS studio
          WHERE studios IS NOT NULL
        ),
        cleaned AS (
          SELECT studio, score
          FROM exploded
          WHERE studio IS NOT NULL
            AND studio != ''
            AND UPPER(studio) != 'UNKNOWN'
        ),
        prolific AS (
          SELECT studio, COUNT(*) AS total_anime
          FROM cleaned
          GROUP BY studio
          ORDER BY total_anime DESC
          LIMIT 1
        ),
        rated AS (
          SELECT studio, ROUND(AVG(score), 2) AS avg_score, COUNT(*) AS total_anime
          FROM cleaned
          WHERE score IS NOT NULL
          GROUP BY studio
          HAVING COUNT(*) > 1
          ORDER BY avg_score DESC
          LIMIT 1
        )
        SELECT
          (SELECT COUNT(DISTINCT studio) FROM cleaned) AS total_studios,
          (SELECT studio FROM prolific) AS prolific_studio,
          (SELECT total_anime FROM prolific) AS prolific_total,
          (SELECT studio FROM rated) AS rated_studio,
          (SELECT avg_score FROM rated) AS rated_avg,
          (SELECT total_anime FROM rated) AS rated_total
        """
        row = next(get_bigquery_client().query(query).result())

        return {
            "total_studios": row.total_studios,
            "most_prolific_studio": {
                "studio": row.prolific_studio,
                "total_anime": row.prolific_total
            } if row.prolific_studio is not None else None,
            "highest_rated_studio": {
                "studio": row.rated_studio,
                "average_score": float(row.rated_avg),
                "total_anime": row.rated_total
            } if row.rated_studio is not None else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")


@app.post("/analytics/studio/search")
def studio_search(req: StudioRequest):
    try:
        exists_query = f"""
        SELECT 1
        FROM `{TABLE_REF}`, UNNEST(SPLIT(studios, ',')) AS studio
        WHERE studios IS NOT NULL
          AND TRIM(studio) != ''
          AND UPPER(TRIM(studio)) != 'UNKNOWN'
          AND LOWER(TRIM(studio)) = LOWER(@studio_name)
        LIMIT 1
        """
        exists_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("studio_name", "STRING", req.studio_name)
            ]
        )
        exists_rows = list(get_bigquery_client().query(exists_query, job_config=exists_config).result())

        if not exists_rows:
            raise HTTPException(status_code=404, detail=f"Studio '{req.studio_name}' not found.")

        top_query = f"""
        SELECT name, ROUND(score, 2) AS score
        FROM `{TABLE_REF}`
        WHERE name IS NOT NULL
          AND TRIM(name) != ''
          AND score IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM UNNEST(SPLIT(studios, ',')) AS studio
            WHERE TRIM(studio) != ''
              AND UPPER(TRIM(studio)) != 'UNKNOWN'
              AND LOWER(TRIM(studio)) = LOWER(@studio_name)
          )
        ORDER BY score DESC, name ASC
        LIMIT 5
        """
        top_rows = get_bigquery_client().query(top_query, job_config=exists_config).result()

        genres_query = f"""
        SELECT DISTINCT TRIM(genre) AS genre
        FROM `{TABLE_REF}`,
        UNNEST(SPLIT(genres, ',')) AS genre
        WHERE genres IS NOT NULL
          AND TRIM(genre) != ''
          AND UPPER(TRIM(genre)) != 'UNKNOWN'
          AND EXISTS (
            SELECT 1
            FROM UNNEST(SPLIT(studios, ',')) AS studio
            WHERE TRIM(studio) != ''
              AND UPPER(TRIM(studio)) != 'UNKNOWN'
              AND LOWER(TRIM(studio)) = LOWER(@studio_name)
          )
        ORDER BY genre ASC
        """
        genre_rows = get_bigquery_client().query(genres_query, job_config=exists_config).result()

        return {
            "studio": req.studio_name,
            "top_5_highest_scored_anime": [
                {"name": row.name, "score": float(row.score)}
                for row in top_rows
            ],
            "all_genres_of_anime_by_this_studio": [row.genre for row in genre_rows]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")


@app.get("/analytics/genre")
def genre_analytics():
    try:
        query = f"""
        WITH exploded AS (
          SELECT TRIM(genre) AS genre, score
          FROM `{TABLE_REF}`,
          UNNEST(SPLIT(genres, ',')) AS genre
          WHERE genres IS NOT NULL
        ),
        cleaned AS (
          SELECT genre, score
          FROM exploded
          WHERE genre IS NOT NULL
            AND genre != ''
            AND UPPER(genre) != 'UNKNOWN'
        ),
        prolific AS (
          SELECT genre, COUNT(*) AS total_anime
          FROM cleaned
          GROUP BY genre
          ORDER BY total_anime DESC
          LIMIT 1
        ),
        rated AS (
          SELECT genre, ROUND(AVG(score), 2) AS avg_score, COUNT(*) AS total_anime
          FROM cleaned
          WHERE score IS NOT NULL
          GROUP BY genre
          HAVING COUNT(*) > 1
          ORDER BY avg_score DESC
          LIMIT 1
        )
        SELECT
          (SELECT COUNT(DISTINCT genre) FROM cleaned) AS total_genres,
          (SELECT genre FROM prolific) AS prolific_genre,
          (SELECT total_anime FROM prolific) AS prolific_total,
          (SELECT genre FROM rated) AS rated_genre,
          (SELECT avg_score FROM rated) AS rated_avg,
          (SELECT total_anime FROM rated) AS rated_total
        """
        row = next(get_bigquery_client().query(query).result())

        return {
            "total_genres": row.total_genres,
            "most_prolific_genre": {
                "genre": row.prolific_genre,
                "total_anime": row.prolific_total
            } if row.prolific_genre is not None else None,
            "highest_rated_genre": {
                "genre": row.rated_genre,
                "average_score": float(row.rated_avg),
                "total_anime": row.rated_total
            } if row.rated_genre is not None else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")


@app.post("/analytics/genre/search")
def genre_search(req: GenreRequest):
    try:
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("genre_name", "STRING", req.genre_name)
            ]
        )

        exists_query = f"""
        SELECT 1
        FROM `{TABLE_REF}`, UNNEST(SPLIT(genres, ',')) AS genre
        WHERE genres IS NOT NULL
          AND TRIM(genre) != ''
          AND UPPER(TRIM(genre)) != 'UNKNOWN'
          AND LOWER(TRIM(genre)) = LOWER(@genre_name)
        LIMIT 1
        """
        exists_rows = list(get_bigquery_client().query(exists_query, job_config=job_config).result())
        if not exists_rows:
            raise HTTPException(status_code=404, detail=f"Genre '{req.genre_name}' not found.")

        top_query = f"""
        SELECT name, ROUND(score, 2) AS score
        FROM `{TABLE_REF}`
        WHERE name IS NOT NULL
          AND TRIM(name) != ''
          AND score IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM UNNEST(SPLIT(genres, ',')) AS genre
            WHERE TRIM(genre) != ''
              AND UPPER(TRIM(genre)) != 'UNKNOWN'
              AND LOWER(TRIM(genre)) = LOWER(@genre_name)
          )
        ORDER BY score DESC, name ASC
        LIMIT 5
        """
        top_rows = get_bigquery_client().query(top_query, job_config=job_config).result()

        studios_query = f"""
        SELECT DISTINCT TRIM(studio) AS studio
        FROM `{TABLE_REF}`,
        UNNEST(SPLIT(studios, ',')) AS studio
        WHERE studios IS NOT NULL
          AND TRIM(studio) != ''
          AND UPPER(TRIM(studio)) != 'UNKNOWN'
          AND EXISTS (
            SELECT 1
            FROM UNNEST(SPLIT(genres, ',')) AS genre
            WHERE TRIM(genre) != ''
              AND UPPER(TRIM(genre)) != 'UNKNOWN'
              AND LOWER(TRIM(genre)) = LOWER(@genre_name)
          )
        ORDER BY studio ASC
        """
        studio_rows = get_bigquery_client().query(studios_query, job_config=job_config).result()

        return {
            "genre": req.genre_name,
            "top_5_highest_scored_anime": [
                {"name": row.name, "score": float(row.score)}
                for row in top_rows
            ],
            "all_studios_of_anime_with_this_genre": [row.studio for row in studio_rows]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")
    

@app.post("/analytics/anime/user-choice-score")
def anime_user_choice_score(req: AnimeUserChoiceRequest):
    try:
        job_config = QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("anime_name", "STRING", req.anime_name)
            ]
        )

        query = f"""
        WITH target AS (
          SELECT
            name,
            score,
            popularity,
            members
          FROM `{TABLE_REF}`
          WHERE name IS NOT NULL
            AND LOWER(TRIM(name)) = LOWER(TRIM(@anime_name))
          LIMIT 1
        ),
        global_stats AS (
          SELECT
            MIN(score) AS min_score,
            MAX(score) AS max_score,
            MIN(popularity) AS min_popularity,
            MAX(popularity) AS max_popularity,
            MIN(members) AS min_members,
            MAX(members) AS max_members
          FROM `{TABLE_REF}`
          WHERE score IS NOT NULL
            AND popularity IS NOT NULL
            AND members IS NOT NULL
        )
        SELECT
          t.name,
          t.score,
          t.popularity,
          t.members,

          SAFE_DIVIDE(
            t.score - g.min_score,
            g.max_score - g.min_score
          ) AS score_normalized,

          1 - SAFE_DIVIDE(
            t.popularity - g.min_popularity,
            g.max_popularity - g.min_popularity
          ) AS popularity_normalized,

          SAFE_DIVIDE(
            t.members - g.min_members,
            g.max_members - g.min_members
          ) AS members_normalized

        FROM target t
        CROSS JOIN global_stats g
        """

        rows = list(get_bigquery_client().query(query, job_config=job_config).result())

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Anime '{req.anime_name}' not found."
            )

        row = rows[0]

        score_norm = float(row.score_normalized) if row.score_normalized is not None else 0.0
        popularity_norm = float(row.popularity_normalized) if row.popularity_normalized is not None else 0.0
        members_norm = float(row.members_normalized) if row.members_normalized is not None else 0.0

        user_choice_score = (
            0.20 * score_norm
            + 0.45 * popularity_norm
            + 0.35 * members_norm
        )

        if user_choice_score >= 0.85:
            user_choice_label = "very_high"
        elif user_choice_score >= 0.65:
            user_choice_label = "high"
        elif user_choice_score >= 0.40:
            user_choice_label = "medium"
        elif user_choice_score >= 0.20:
            user_choice_label = "low"
        else:
            user_choice_label = "very_low"

        return {
            "anime_name": row.name,
            "raw_metrics": {
                "score": float(row.score) if row.score is not None else None,
                "popularity_rank": row.popularity,
                "members": row.members
            },
            "normalized_metrics": {
                "score_normalized": round(score_norm, 4),
                "popularity_normalized": round(popularity_norm, 4),
                "members_normalized": round(members_norm, 4)
            },
            "weights": {
                "score_normalized": 0.20,
                "popularity_normalized": 0.45,
                "members_normalized": 0.35
            },
            "user_choice_score": round(user_choice_score, 4),
            "user_choice_label": user_choice_label,
            "strategy": "weighted_normalized_user_choice_score"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")