from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from google.cloud import bigquery
from google.oauth2 import service_account 
import json, os
import random

app = FastAPI(title="Users Service")

# Load credentials
json_string = os.environ.get('API_TOKEN') 
json_file = json.loads(json_string) 
credentials = service_account.Credentials.from_service_account_info(json_file) 
client = bigquery.Client(credentials=credentials, location="europe-west1")

TABLE_ID = "cm-labs-exemplo.projeto.user"

# Models
class User(BaseModel):
    id: int
    username: str

class UserCreate(BaseModel):
    username: str

class UserUpdate(BaseModel):
    username: Optional[str] = None


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/users", response_model=List[User])
def get_users():
    query = f"SELECT id, username FROM `{TABLE_ID}`"
    results = client.query(query).result()
    
    return [User(id=row.id, username=row.username) for row in results]


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    query = f"""
        SELECT id, username 
        FROM `{TABLE_ID}` 
        WHERE id = @user_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "INT64", user_id)
        ]
    )
    
    results = list(client.query(query, job_config=job_config).result())
    
    if not results:
        raise HTTPException(status_code=404, detail="User not found")
    
    row = results[0]
    return User(id=row.id, username=row.username)


@app.post("/users", response_model=User, status_code=201)
def create_user(user: UserCreate):
    # gerar id random
    user_id = random.randint(1, 10**9)

    rows_to_insert = [
        {"id": user_id, "username": user.username}
    ]
    
    errors = client.insert_rows_json(TABLE_ID, rows_to_insert)
    
    if errors:
        raise HTTPException(status_code=500, detail=str(errors))
    
    return User(id=user_id, username=user.username)


@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user_update: UserUpdate):
    if not user_update.username:
        raise HTTPException(status_code=400, detail="Nothing to update")

    query = f"""
        UPDATE `{TABLE_ID}`
        SET username = @username
        WHERE id = @user_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("username", "STRING", user_update.username),
            bigquery.ScalarQueryParameter("user_id", "INT64", user_id),
        ]
    )

    query_job = client.query(query, job_config=job_config)
    query_job.result()

    # verificar se existe
    return get_user(user_id)


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    query = f"""
        DELETE FROM `{TABLE_ID}`
        WHERE id = @user_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "INT64", user_id)
        ]
    )

    query_job = client.query(query, job_config=job_config)
    query_job.result()

    return