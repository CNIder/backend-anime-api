from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2

app = FastAPI()

class StudioRequest(BaseModel):
    studio_name: str

class GenreRequest(BaseModel):
    genre_name: str

def get_db_connection():
    return psycopg2.connect(
        host="db",
        database="anime",
        user="anime_user",
        password="anime_pass"
    )

@app.get("/analytics/anime")
def anime_analytics():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Total anime
        cur.execute("SELECT COUNT(*) FROM anime;")
        total_anime = cur.fetchone()[0]

        # Average score
        cur.execute("""
            SELECT ROUND(AVG(score::numeric), 2)
            FROM anime
            WHERE score ~ '^[0-9]+(\\.[0-9]+)?$';
        """)
        avg_score = cur.fetchone()[0]

        # Median score (middle score)
        cur.execute("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score::numeric)
            FROM anime
            WHERE score ~ '^[0-9]+(\\.[0-9]+)?$';
        """)
        median_score = cur.fetchone()[0]

        # Mode score (most frequently occurring score)
        cur.execute("""
            SELECT score::numeric, COUNT(*) AS frequency
            FROM anime
            WHERE score ~ '^[0-9]+(\\.[0-9]+)?$'
            GROUP BY score::numeric
            ORDER BY frequency DESC, score::numeric DESC
            LIMIT 1;""")
        mode_result = cur.fetchone()

        # Score standard deviation
        cur.execute("""
            SELECT ROUND(STDDEV(score::numeric), 2)
            FROM anime
            WHERE score ~ '^[0-9]+(\\.[0-9]+)?$';
        """)
        stddev_score = cur.fetchone()[0]

        # Most popular anime by popularity rank
        # Usually smaller rank = more popular
        cur.execute("""
            SELECT english_name, popularity
            FROM anime
            WHERE popularity IS NOT NULL
            ORDER BY popularity ASC
            LIMIT 1;
        """)
        popular_anime = cur.fetchone()

        # Anime with most members
        cur.execute("""
            SELECT english_name, members
            FROM anime
            WHERE members IS NOT NULL
            ORDER BY members DESC
            LIMIT 1;
        """)
        member_anime = cur.fetchone()

        return {
            "total_anime": total_anime,
            "average_score": float(avg_score) if avg_score is not None else None,
            "median_score": float(median_score) if median_score is not None else None,
            "mode_score": float(mode_result[0]) if mode_result is not None else None,
            "mode_score_frequency": mode_result[1] if mode_result is not None else None,
            "score_standard_deviation": float(stddev_score) if stddev_score is not None else None,
            "most_popular_anime": {
                "english_name": popular_anime[0],
                "popularity": popular_anime[1]
            } if popular_anime else None,
            "anime_in_most_watchlists": {
                "english_name": member_anime[0],
                "members": member_anime[1]
            } if member_anime else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.get("/analytics/studio")
def studio_analytics():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Total studios
        cur.execute("""
            SELECT COUNT(DISTINCT TRIM(studio))
            FROM (
                SELECT unnest(string_to_array(studios, ',')) AS studio
                FROM anime
            ) AS s
            WHERE studio IS NOT NULL
              AND TRIM(studio) <> ''
              AND TRIM(studio) <> 'UNKNOWN';
        """)
        total_studios = cur.fetchone()[0]

        # Most prolific studio
        cur.execute("""
            SELECT studio, COUNT(*) AS total_anime
            FROM (
                SELECT TRIM(unnest(string_to_array(studios, ','))) AS studio
                FROM anime
            ) AS s
            WHERE studio IS NOT NULL
              AND studio <> ''
              AND studio <> 'UNKNOWN'
            GROUP BY studio
            ORDER BY total_anime DESC
            LIMIT 1;
        """)
        diligent_studio = cur.fetchone()

        # Highest-rated studio
        cur.execute("""
            SELECT studio, ROUND(AVG(score::numeric), 2) AS avg_score, COUNT(*) AS total_anime
            FROM (
                SELECT TRIM(unnest(string_to_array(studios, ','))) AS studio, score
                FROM anime
                WHERE score ~ '^[0-9]+(\\.[0-9]+)?$'
            ) AS s
            WHERE studio IS NOT NULL
              AND studio <> ''
              AND studio <> 'UNKNOWN'
            GROUP BY studio
            HAVING COUNT(*) > 1
            ORDER BY avg_score DESC
            LIMIT 1;
        """)
        studio_rank = cur.fetchone()

        return {
            "total_studios": total_studios,
            "most_prolific_studio": {
                "studio": diligent_studio[0],
                "total_anime": diligent_studio[1]
            } if diligent_studio else None,
            "highest_rated_studio": {
                "studio": studio_rank[0],
                "average_score": float(studio_rank[1]),
                "total_anime": studio_rank[2]
            } if studio_rank else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.post("/analytics/studio/search")
def studio_search(req: StudioRequest):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check studio exists
        cur.execute("""
            SELECT 1
            FROM (
                SELECT TRIM(unnest(string_to_array(studios, ','))) AS studio
                FROM anime
            ) s
            WHERE studio IS NOT NULL
              AND studio <> ''
              AND studio <> 'UNKNOWN'
              AND LOWER(studio) = LOWER(%s)
            LIMIT 1;
        """, (req.studio_name,))
        exists = cur.fetchone()

        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Studio '{req.studio_name}' not found."
            )

        # Top 5 highest-scored anime by studio
        cur.execute("""
            SELECT english_name, ROUND(score::numeric, 2) AS score
            FROM anime
            WHERE english_name IS NOT NULL
              AND TRIM(english_name) <> ''
              AND english_name <> 'UNKNOWN'
              AND score ~ '^[0-9]+(\\.[0-9]+)?$'
              AND EXISTS (
                  SELECT 1
                  FROM unnest(string_to_array(studios, ',')) AS s(studio)
                  WHERE TRIM(s.studio) IS NOT NULL
                    AND TRIM(s.studio) <> ''
                    AND TRIM(s.studio) <> 'UNKNOWN'
                    AND LOWER(TRIM(s.studio)) = LOWER(%s)
              )
            ORDER BY score::numeric DESC, english_name ASC
            LIMIT 5;
        """, (req.studio_name,))
        top_anime = cur.fetchall()

        # All genres of anime made by that studio
        cur.execute("""
            SELECT DISTINCT TRIM(g.genre) AS genre
            FROM anime
            CROSS JOIN unnest(string_to_array(genres, ',')) AS g(genre)
            WHERE genres IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM unnest(string_to_array(studios, ',')) AS s(studio)
                  WHERE TRIM(s.studio) IS NOT NULL
                    AND TRIM(s.studio) <> ''
                    AND TRIM(s.studio) <> 'UNKNOWN'
                    AND LOWER(TRIM(s.studio)) = LOWER(%s)
              )
              AND TRIM(g.genre) IS NOT NULL
              AND TRIM(g.genre) <> ''
              AND TRIM(g.genre) <> 'UNKNOWN'
            ORDER BY genre ASC;
        """, (req.studio_name,))
        genres = [row[0] for row in cur.fetchall()]

        return {
            "studio": req.studio_name,
            "top_5_highest_scored_anime": [
                {
                    "english_name": row[0],
                    "score": float(row[1])
                }
                for row in top_anime
            ],
            "all_genres_of_anime_by_this_studio": genres
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/analytics/genre")
def genre_analytics():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Total genres
        cur.execute("""
            SELECT COUNT(DISTINCT TRIM(genre))
            FROM (
                SELECT unnest(string_to_array(genres, ',')) AS genre
                FROM anime
            ) AS g
            WHERE genre IS NOT NULL
              AND TRIM(genre) <> ''
              AND TRIM(genre) <> 'UNKNOWN';
        """)
        total_genres = cur.fetchone()[0]

        # Most prolific genre
        cur.execute("""
            SELECT genre, COUNT(*) AS total_anime
            FROM (
                SELECT TRIM(unnest(string_to_array(genres, ','))) AS genre
                FROM anime
            ) AS g
            WHERE genre IS NOT NULL
              AND genre <> ''
              AND genre <> 'UNKNOWN'
            GROUP BY genre
            ORDER BY total_anime DESC
            LIMIT 1;
        """)
        ubiquitous_genre = cur.fetchone()

        # Highest-rated genre
        cur.execute("""
            SELECT genre, ROUND(AVG(score::numeric), 2) AS avg_score, COUNT(*) AS total_anime
            FROM (
                SELECT TRIM(unnest(string_to_array(genres, ','))) AS genre, score
                FROM anime
                WHERE score ~ '^[0-9]+(\\.[0-9]+)?$'
            ) AS g
            WHERE genre IS NOT NULL
              AND genre <> ''
              AND genre <> 'UNKNOWN'
            GROUP BY genre
            HAVING COUNT(*) > 1
            ORDER BY avg_score DESC
            LIMIT 1;
        """)
        genre_rank = cur.fetchone()

        return {
            "total_genres": total_genres,
            "most_prolific_genre": {
                "genre": ubiquitous_genre[0],
                "total_anime": ubiquitous_genre[1]
            } if ubiquitous_genre else None,
            "highest_rated_genre": {
                "genre": genre_rank[0],
                "average_score": float(genre_rank[1]),
                "total_anime": genre_rank[2]
            } if genre_rank else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.post("/analytics/genre/search")
def genre_search(req: GenreRequest):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check genre exists
        cur.execute("""
            SELECT 1
            FROM (
                SELECT TRIM(unnest(string_to_array(genres, ','))) AS genre
                FROM anime
            ) g
            WHERE genre IS NOT NULL
              AND genre <> ''
              AND genre <> 'UNKNOWN'
              AND LOWER(genre) = LOWER(%s)
            LIMIT 1;
        """, (req.genre_name,))
        exists = cur.fetchone()

        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Genre '{req.genre_name}' not found."
            )

        # Top 5 highest-scored anime of that genre
        cur.execute("""
            SELECT english_name, ROUND(score::numeric, 2) AS score
            FROM anime
            WHERE english_name IS NOT NULL
              AND TRIM(english_name) <> ''
              AND english_name <> 'UNKNOWN'
              AND score ~ '^[0-9]+(\\.[0-9]+)?$'
              AND EXISTS (
                  SELECT 1
                  FROM unnest(string_to_array(genres, ',')) AS g(genre)
                  WHERE TRIM(g.genre) IS NOT NULL
                    AND TRIM(g.genre) <> ''
                    AND TRIM(g.genre) <> 'UNKNOWN'
                    AND LOWER(TRIM(g.genre)) = LOWER(%s)
              )
            ORDER BY score::numeric DESC, english_name ASC
            LIMIT 5;
        """, (req.genre_name,))
        top_anime = cur.fetchall()

        # All studios that made anime of that genre
        cur.execute("""
            SELECT DISTINCT TRIM(s.studio) AS studio
            FROM anime
            CROSS JOIN unnest(string_to_array(studios, ',')) AS s(studio)
            WHERE studios IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM unnest(string_to_array(genres, ',')) AS g(genre)
                  WHERE TRIM(g.genre) IS NOT NULL
                    AND TRIM(g.genre) <> ''
                    AND TRIM(g.genre) <> 'UNKNOWN'
                    AND LOWER(TRIM(g.genre)) = LOWER(%s)
              )
              AND TRIM(s.studio) IS NOT NULL
              AND TRIM(s.studio) <> ''
              AND TRIM(s.studio) <> 'UNKNOWN'
            ORDER BY studio ASC;
        """, (req.genre_name,))
        studios = [row[0] for row in cur.fetchall()]

        return {
            "genre": req.genre_name,
            "top_5_highest_scored_anime": [
                {
                    "english_name": row[0],
                    "score": float(row[1])
                }
                for row in top_anime
            ],
            "all_studios_of_anime_with_this_genre": studios
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()