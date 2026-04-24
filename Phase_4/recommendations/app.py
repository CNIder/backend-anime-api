'''
THIS SCRIPT CREATES RECOMMENDATIONS BASED ON GENRE SIMILARITY -> NO LLM!!!!


from fastapi import FastAPI, HTTPException
import psycopg2
from pydantic import BaseModel

app = FastAPI()


class RecommendationRequest(BaseModel):
    anime_name: str


def get_db_connection():
    return psycopg2.connect(
        host="db",
        database="anime",
        user="anime_user",
        password="anime_pass"
    )


@app.post("/recommendations")
def recommend(req: RecommendationRequest):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check that the anime exists first
        cur.execute(
            "SELECT 1 FROM anime WHERE english_name ILIKE %s LIMIT 1;",
            (req.anime_name,)
        )
        exists = cur.fetchone()

        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Anime '{req.anime_name}' not found."
            )

        query = """
        SELECT
            a.english_name,
            COUNT(*) AS similarity_score,
            ROUND(AVG(a.score::numeric), 2) AS avg_score
        FROM (
            SELECT
                english_name,
                TRIM(unnest(string_to_array(genres, ','))) AS genre,
                score
            FROM anime
            WHERE score ~ '^[0-9]+(\\.[0-9]+)?$'
        ) a
        JOIN (
            SELECT DISTINCT TRIM(unnest(string_to_array(genres, ','))) AS genre
            FROM anime
            WHERE english_name ILIKE %s
        ) t
        ON a.genre = t.genre
        WHERE a.english_name NOT ILIKE %s
          AND a.english_name <> 'UNKNOWN'
          AND a.genre IS NOT NULL
          AND a.genre <> ''
          AND a.genre <> 'UNKNOWN'
        GROUP BY a.english_name
        ORDER BY similarity_score DESC, avg_score DESC
        LIMIT 10;
        """

        cur.execute(query, (req.anime_name, req.anime_name))
        results = cur.fetchall()

        return [
            {
                "anime": row[0],
                "similarity_score": row[1],
                "avg_score": float(row[2]) if row[2] is not None else None
            }
            for row in results
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
'''

"""
THIS SCRIPT USES LIGHTWEIGHT LLM for recommendation system; NO TRAINING, JUST INFERENCE!!!
"""
from contextlib import asynccontextmanager
from typing import Any
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util


class RecommendationRequest(BaseModel):
    anime_name: str


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_db_connection():
    return psycopg2.connect(
        host="db",
        database="anime",
        user="anime_user",
        password="anime_pass"
    )


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper() == "UNKNOWN":
        return ""
    return text


def anime_to_text(row: tuple) -> str:
    """
    Convert one anime row into a single text string for embedding.
    Tune this template as needed.
    """
    english_name, genres, synopsis, studios = row

    parts = [
        f"Title: {safe_text(english_name)}",
        f"Genres: {safe_text(genres)}",
        f"Synopsis: {safe_text(synopsis)}",
        f"Studios: {safe_text(studios)}",
    ]

    # Remove empty fields so embeddings are cleaner
    return ". ".join(part for part in parts if not part.endswith(": "))


def load_anime_catalog():
    """
    Read anime metadata from PostgreSQL and prepare:
    - app.state.anime_rows
    - app.state.anime_texts
    - app.state.anime_embeddings
    - app.state.name_to_index
    """
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                english_name,
                genres,
                synopsis,
                studios
            FROM anime
            WHERE english_name IS NOT NULL
              AND TRIM(english_name) <> ''
              AND english_name <> 'UNKNOWN';
        """)

        rows = cur.fetchall()

        if not rows:
            raise RuntimeError("No anime rows found in database.")

        anime_texts = [anime_to_text(row) for row in rows]

        # normalize_embeddings=True makes cosine-style similarity efficient/stable
        anime_embeddings = app.state.model.encode(
            anime_texts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        name_to_index = {}
        for idx, row in enumerate(rows):
            # case-insensitive lookup
            name_to_index[row[0].strip().lower()] = idx

        app.state.anime_rows = rows
        app.state.anime_texts = anime_texts
        app.state.anime_embeddings = anime_embeddings
        app.state.name_to_index = name_to_index

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load embedding model once at app startup
    app.state.model = SentenceTransformer(MODEL_NAME)

    # Build in-memory recommendation index once at startup
    load_anime_catalog()

    yield

    # Optional cleanup
    app.state.model = None
    app.state.anime_rows = None
    app.state.anime_texts = None
    app.state.anime_embeddings = None
    app.state.name_to_index = None


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "catalog_size": len(app.state.anime_rows) if app.state.anime_rows else 0
    }


@app.post("/recommendations")
def recommend(req: RecommendationRequest):
    try:
        query_name = req.anime_name.strip().lower()
        query_idx = app.state.name_to_index.get(query_name)

        if query_idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"Anime '{req.anime_name}' not found."
            )

        query_embedding = app.state.anime_embeddings[query_idx]

        # Cosine similarity against the full catalog
        scores = util.cos_sim(query_embedding, app.state.anime_embeddings)[0]

        # Get more than needed because the first result is usually the same anime
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

            # Skip the exact same anime
            if anime_name.strip().lower() == query_name_original:
                continue

            recommendations.append({
                "anime": anime_name,
                "similarity_score": round(score, 4),
                "genres": app.state.anime_rows[idx][1],
                "studios": app.state.anime_rows[idx][3],
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


@app.post("/reload-index") # Calculate new embeddings for db updates
def reload_index():
    """
    Rebuild the in-memory embedding index after DB updates.
    """
    try:
        load_anime_catalog()
        return {
            "status": "reloaded",
            "catalog_size": len(app.state.anime_rows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload error: {str(e)}")