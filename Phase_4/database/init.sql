CREATE TABLE IF NOT EXISTS anime (
    anime_id     INTEGER,
    english_name TEXT,
    score        TEXT,
    genres       TEXT,
    synopsis     TEXT,
    episodes     TEXT,
    studios      TEXT,
    rank         TEXT,
    popularity   INTEGER,
    members      INTEGER
);

COPY anime(anime_id, english_name, score, genres, synopsis, episodes, studios, rank, popularity, members)
FROM '/data/anime_trimmed.csv'
DELIMITER ','
CSV HEADER
QUOTE '"'
ESCAPE '\';