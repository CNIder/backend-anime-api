# Phase 4 – Backend Anime API

## Overview

This project implements the Phase 4 cloud-native application as a set of containerized microservices running locally with Docker Compose. This specific part covers the use cases and functionality implemented by António Caldeira.

The system uses a PostgreSQL database and provides:

* anime recommendation functionality
* anime analytics functionality

The application is designed to run locally in containers, one per service.

## Project structure

```
Phase_4/
├── analytics/
│   ├── app.py
│   ├── dockerfile
│   └── requirements.txt
├── data/
├── database/
│   └── init.sql
├── recommendations/
│   ├── app.py
│   ├── dockerfile
│   └── requirements.txt
├── scripts/
│   └── prepare_data.py
└── docker-compose.yaml
```

## Microservices

### Analytics service

Provides endpoints for:

* overall anime analytics
* studio analytics
* genre analytics
* search by studio
* search by genre

### Recommendation service

Provides anime recommendations based on the implemented recommendation logic.

### Database service

A PostgreSQL container stores the anime dataset and is initialized with the provided SQL script.

## Requirements

To run this project locally, the following software is required:

* Docker
* Docker Compose

## How to run

From the `Phase_4` folder, run:

```
docker compose up --build
```

This command builds and starts all containers locally.

## How to stop

To stop the application, run:

```
docker compose down
```

## Services

The main services are available locally on the ports defined in `docker-compose.yaml`.

Example:

* analytics service: `http://localhost:<port>`
* recommendations service: `http://localhost:<port>`

Replace `<port>` with the ports configured in your compose file.

## API endpoints

### Analytics service

#### Anime analytics

`GET /analytics/anime`

Returns:

* total anime
* average score
* median score
* mode score
* score standard deviation
* most popular anime
* anime in the most watchlists

#### Studio analytics

`GET /analytics/studio`

Returns:

* total studios
* most prolific studio
* highest-rated studio

#### Genre analytics

`GET /analytics/genre`

Returns:

* total genres
* most prolific genre
* highest-rated genre

#### Search by studio

`POST /analytics/studio/search`

Example request body:

```
{
  "studio_name": "Madhouse"
}
```

Returns:

* top 5 highest-scored anime by that studio
* all genres associated with that studio

#### Search by genre

`POST /analytics/genre/search`

Example request body:

```
{
  "genre_name": "Action"
}
```

Returns:

* top 5 highest-scored anime of that genre
* all studios associated with that genre

### Recommendation service

#### Anime recommendations

`POST /recommendations`

Example request body:

```
{
  "anime_name": "Naruto"
}
```

Returns a list of recommended anime related to the given input anime.

## Data preparation

The script `scripts/prepare_data.py` is used to prepare the dataset before loading it into the database.

## Database

The database initialization script is located at:

```
database/init.sql
```

This script is used to initialize the PostgreSQL database.

## Notes

* Unknown or invalid values such as `UNKNOWN` are filtered where appropriate (they are quite frequent in the dataset).
* Each service has its own dependencies listed in its respective `requirements.txt` file.