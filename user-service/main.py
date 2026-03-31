from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List
from datetime import datetime

app = FastAPI(title="Users Service")

class User(BaseModel):
    user_id: int
    username: str = Field(..., min_length=1)
    joined_date: datetime
    watchlist_count: int = 0

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1)
    watchlist_count: int = 0

class UserUpdate(BaseModel):
    username: str = None
    watchlist_count: int = None


fake_users_db: Dict[int, User] = {
    1: User(user_id=1, username="Alice", joined_date=datetime(2026, 3, 20), watchlist_count=5),
    2: User(user_id=2, username="Bob", joined_date=datetime(2026, 3, 20), watchlist_count=2)
}

@app.get("/users", response_model=List[User])
def get_users():
    return list(fake_users_db.values())


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    user = fake_users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users", response_model=User, status_code=201)
def create_user(user: UserCreate):
    new_id = max(fake_users_db.keys()) + 1 if fake_users_db else 1
    new_user = User(
        user_id=new_id,
        username=user.username,
        joined_date=datetime.utcnow(),
        watchlist_count=user.watchlist_count
    )
    fake_users_db[new_id] = new_user
    return new_user


@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user_update: UserUpdate):
    user = fake_users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_data = user.dict()
    if user_update.username is not None:
        updated_data["username"] = user_update.username
    if user_update.watchlist_count is not None:
        updated_data["watchlist_count"] = user_update.watchlist_count

    updated_user = User(**updated_data)
    fake_users_db[user_id] = updated_user
    return updated_user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del fake_users_db[user_id]
    return