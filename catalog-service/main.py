from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import pandas as pd

class Anime(BaseModel):
    anime_id: int
    title: str
    genres: str
    synopsis: str
    rank: float

app = FastAPI(title="Anime Catalog API")

CSV_FILE = "anime-dataset-2023.csv"

# Carrega o CSV uma vez no startup
def load_csv(file_path):
    df = pd.read_csv(file_path)

    # Seleciona e renomeia colunas
    cols = ['anime_id', 'Name', 'Genres', 'Synopsis', 'Rank']
    df_filtered = df[cols].copy()
    df_filtered.rename(columns={
        'Name': 'title',
        'Genres': 'genres',
        'Synopsis': 'synopsis',
        'Rank' : 'rank'
    }, inplace=True)

    return df_filtered

# Pré-carrega o CSV
df_animes = load_csv(CSV_FILE)
df_animes = df_animes.head(50)

@app.get("/anime/top", response_model=Anime)
def getTopAnime():
    top_anime = df_animes.loc[df_animes['rank'].idxmax()]
    return Anime(**top_anime.to_dict())

# Endpoint paginado
@app.get("/anime", response_model=list[Anime])
def get_animes():
    if df_animes.empty:
        raise HTTPException(status_code=404, detail="No animes found for this range")
    return df_animes.to_dict(orient="records")

# Endpoint por ID
@app.get("/anime/{anime_id}", response_model=Anime)
def get_anime(anime_id: int):
    anime_row = df_animes[df_animes['anime_id'] == anime_id]
    if anime_row.empty:
        raise HTTPException(status_code=404, detail="Anime not found")
    return anime_row.iloc[0].to_dict()