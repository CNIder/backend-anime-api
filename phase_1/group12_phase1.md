# Cloud Computing: Group 12's Phase 1

## Dataset: MyAnimeList Dataset (Anime Database)

- **URL:** https://www.kaggle.com/datasets/dbdmobile/myanimelist-dataset?select=anime-dataset-2023.csv  
- **Topic:** Anime / Entertainment  
- **Size:** 7.35 GB  
- **Publication / Last Update:** Updated 3 years ago (according to Kaggle metadata)

---

# Business Capabilities

We propose the following business capabilities:

- Catalogue infrastructure for anime series featuring attribute filtering, keyword search, and detailed show pages.
- A recommendation system that suggests new anime series to users based on their activity and profile.
- User profile support including username, location, and personal watchlist.
- Media interaction functionality, including reviews, ratings, and forum-like discussion threads.
- Analytics and insights derived from dataset statistics and user interaction.

---

# Use Cases (Our Contributions)

We propose the following use cases:

- Search for a specific anime's details.
- Get the highest-rated anime of the season.
- Get show recommendations based on user interests.
- Retrieve profile information.
- View a user's watchlist.
- Add, remove, or update entries in a user watchlist.
- Write or read a review of the currently most popular anime.
- Rate a show based on a fixed scale.
- Post a question in the forum regarding a plot twist or service issue.
- Get a studio's most popular anime shows of all time.


## Anime Application Architecture
```mermaid
graph TD
    UI([Web UI]):::client

    UI -->|HTTP/REST| GW

    subgraph Gateway
        GW[API Gateway]:::gateway
        AUTH[Auth Service]:::infra
    end

    subgraph Data Domain
        ANIME[Anime Catalogue]:::data
        STATS[Statistics]:::data
    end

    subgraph User Domain
        USER[User Management]:::user
        WATCH[Watchlist]:::user
        RATE[Rating]:::user
        REV[Review]:::user
        FORUM[Forum]:::user
    end

    subgraph Curation Domain
        REC[Recommendation]:::curation
    end

    GW -->|REST| AUTH
    GW -->|REST| ANIME
    GW -->|REST| USER
    GW -->|REST| WATCH
    GW -->|REST| RATE
    GW -->|REST| REV
    GW -->|REST| FORUM
    GW -->|REST| REC
    GW -->|REST| STATS

    REC -->|REST| ANIME
    REC -->|REST| WATCH
    REC -->|REST| USER

    STATS -->|REST| ANIME
    STATS -->|REST| USER
    STATS -->|REST| WATCH
    STATS -->|REST| RATE
    STATS -->|REST| REV
    STATS -->|REST| FORUM

    ANIME -->|SQL| DB1[(Anime DB)]:::db
    USER -->|SQL| DB2[(User DB)]:::db
    WATCH -->|SQL| DB3[(Watchlist DB)]:::db
    RATE -->|SQL| DB4[(Rating DB)]:::db
    REV -->|SQL| DB5[(Review DB)]:::db
    FORUM -->|SQL| DB6[(Forum DB)]:::db
    REC -->|SQL| DB7[(Rec DB)]:::db

    classDef client fill:#ff6a8a,stroke:#ff6a8a,color:#000
    classDef gateway fill:#f5a623,stroke:#f5a623,color:#000
    classDef infra fill:#e74c3c,stroke:#e74c3c,color:#fff
    classDef data fill:#3498db,stroke:#3498db,color:#fff
    classDef user fill:#2ecc71,stroke:#2ecc71,color:#000
    classDef curation fill:#7c6aff,stroke:#7c6aff,color:#fff
    classDef db fill:#1e1e2e,stroke:#6b6b8a,color:#e2e2f0
```