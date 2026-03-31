from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import httpx
import asyncio

app = FastAPI(title="Ratings Service")

# URLs dos microserviços
USERS_SERVICE_URL = "http://host.docker.internal:8001"
ANIME_SERVICE_URL = "http://host.docker.internal:8002"


# ----------- MODELOS -----------

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


# ----------- DB fake -----------

fake_ratings_db: Dict[int, Rating] = {}


# ----------- HELPERS -----------

async def get_user(user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{USERS_SERVICE_URL}/users/{user_id}")
        if response.status_code != 200:
            return None
        return response.json()


async def get_anime(anime_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{ANIME_SERVICE_URL}/anime/{anime_id}")
        if response.status_code != 200:
            return None
        return response.json()


async def user_exists(user_id: int):
    user = await get_user(user_id)
    return user is not None


async def anime_exists(anime_id: int):
    anime = await get_anime(anime_id)
    return anime is not None


# ----------- ENDPOINTS -----------

@app.get("/rating", response_model=List[RatingResponse])
async def get_ratings():
    result = []

    for r in fake_ratings_db.values():
        anime_task = get_anime(r.anime_id)
        user_task = get_user(r.user_id)

        anime, user = await asyncio.gather(anime_task, user_task)

        result.append({
            "rating_id": r.rating_id,
            "user_id": r.user_id,
            "username": user["username"] if user else None,
            "anime_id": r.anime_id,
            "anime_title": anime["title"] if anime else None,
            "score": r.score,
            "comment": r.comment
        })

    return result


@app.post("/rating", response_model=Rating, status_code=201)
async def create_rating(rating: RatingCreate):

    if not await user_exists(rating.user_id):
        raise HTTPException(status_code=404, detail="User not found")

    if not await anime_exists(rating.anime_id):
        raise HTTPException(status_code=404, detail="Anime not found")

    # evitar duplicados
    for r in fake_ratings_db.values():
        if r.user_id == rating.user_id and r.anime_id == rating.anime_id:
            raise HTTPException(status_code=400, detail="Rating already exists")

    new_id = max(fake_ratings_db.keys()) + 1 if fake_ratings_db else 1

    new_rating = Rating(
        rating_id=new_id,
        user_id=rating.user_id,
        anime_id=rating.anime_id,
        score=rating.score,
        comment=rating.comment
    )

    fake_ratings_db[new_id] = new_rating
    return new_rating


@app.get("/rating/user/{user_id}", response_model=List[RatingResponse])
async def get_ratings_by_user(user_id: int):
    result = []

    for r in fake_ratings_db.values():
        if r.user_id == user_id:
            anime_task = get_anime(r.anime_id)
            user_task = get_user(r.user_id)

            anime, user = await asyncio.gather(anime_task, user_task)

            result.append({
                "rating_id": r.rating_id,
                "user_id": r.user_id,
                "username": user["username"] if user else None,
                "anime_id": r.anime_id,
                "anime_title": anime["title"] if anime else None,
                "score": r.score,
                "comment": r.comment
            })

    return result


@app.get("/rating/anime/{anime_id}", response_model=List[RatingResponse])
async def get_ratings_by_anime(anime_id: int):
    result = []

    for r in fake_ratings_db.values():
        if r.anime_id == anime_id:
            anime_task = get_anime(r.anime_id)
            user_task = get_user(r.user_id)

            anime, user = await asyncio.gather(anime_task, user_task)

            result.append({
                "rating_id": r.rating_id,
                "user_id": r.user_id,
                "username": user["username"] if user else None,
                "anime_id": r.anime_id,
                "anime_title": anime["title"] if anime else None,
                "score": r.score,
                "comment": r.comment
            })

    return result


@app.put("/rating/{rating_id}", response_model=Rating)
def update_rating(rating_id: int, rating_update: RatingUpdate):
    rating = fake_ratings_db.get(rating_id)

    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    updated_data = rating.dict()

    if rating_update.score is not None:
        updated_data["score"] = rating_update.score

    if rating_update.comment is not None:
        updated_data["comment"] = rating_update.comment

    updated_rating = Rating(**updated_data)
    fake_ratings_db[rating_id] = updated_rating

    return updated_rating


@app.delete("/rating/{rating_id}", status_code=204)
def delete_rating(rating_id: int):
    if rating_id not in fake_ratings_db:
        raise HTTPException(status_code=404, detail="Rating not found")

    del fake_ratings_db[rating_id]
    return