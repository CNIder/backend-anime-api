from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from google.cloud import bigquery
from google.oauth2 import service_account 
import json, os
from prometheus_fastapi_instrumentator import Instrumentator

class Anime(BaseModel):
    anime_id: int
    Name: str
    Ranked: float | None = None

app = FastAPI(title="Anime Catalog API")

# prometheus
Instrumentator().instrument(app).expose(app)

# Load credentials
json_string = os.environ.get('API_TOKEN') 
json_file = json.loads(json_string) 
credentials = service_account.Credentials.from_service_account_info(json_file) 
client = bigquery.Client(credentials=credentials, location="europe-west1")

TABLE_ID = "cm-labs-exemplo.projeto.anime"

# Helper function to run queries
def run_query(query: str):
    query_job = client.query(query)
    return query_job.to_dataframe()

@app.get("/")
def root():
    return {"status": "ok"}

# Endpoint paginado
@app.get("/anime", response_model=list[Anime])
def get_animes(
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0)
):
    query = f"""
        SELECT anime_id, Name, Ranked
        FROM `{TABLE_ID}`
        ORDER BY Ranked ASC
        LIMIT {limit}
        OFFSET {offset}
    """
    
    df_animes = run_query(query)

    if df_animes.empty:
        raise HTTPException(status_code=404, detail="No animes found for this range")
    
    return df_animes.to_dict(orient="records")

# Endpoint por ID
@app.get("/anime/{anime_id}", response_model=Anime)
def get_anime(anime_id: int):
    query = f"""
        SELECT anime_id, Name, Ranked
        FROM `{TABLE_ID}`
        WHERE anime_id = {anime_id}
        LIMIT 1
    """
    
    df_animes = run_query(query)

    if df_animes.empty:
        raise HTTPException(status_code=404, detail="Anime not found")
    
    return df_animes.iloc[0].to_dict()