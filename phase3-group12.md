#  Phase 3 – Functional requirements & Architecture
## Authors: Antonio, Artur & Claudio (Group 12)

### Functional Requirements
The Use Cases defined in phase 1 focus on the user's goals and needs and cover only a subset of the system and its functions.Functional requirements - the focus of this phase - focus on the system's functionality and behavior; functional requirements cover the entire system and all its features and below we listed some functional requirements derived from our listed use cases (from phase 1) for our project:
- The system allows users to search for anime by title and show all the relevant details.
- The system allows users to filter anime using diferent criteria and show all the relevant details.
- The system provides a list of the highest-rated anime of the current season.
- The system displays ranking information (e.g., Top 10 or Top N) for seasonal anime.
- The system generates anime recommendations based on user watch history.
- The system generates recommendations based on user ratings.
- The system allows users to create and manage a personal profile.
- The system displays profile information
- The system allows users to view other users' public profiles.
- The system allows users to create and maintain a watchlist.
- The system allows users to add/remove anime to their watchlist.
- The system allows users to update watchlist entries
- The system allows users to write/read reviews for anime.
- The system allows users to rate anime using a fixed rating scale (e.g., 1–10).
- The system calculates and displays the average rating of each anime.
- The system allows users to post questions or discussions in a forum.
- The system allows users to comment on forum posts.
- The system allows users to search forum threads.
- The system provides top-watched anime lists.
- The system allows users to filter top anime by criteria

### Microservices Architecture
From the functional requirements listed, the system can be decomposed into multiple microservices, each responsible for a single bounded context. Listed below are some key services to be implemented in our architecture based on microservices:
1. User Service
2. Anime Catalog Service
3. Watchlist Service
4. Rating Service
5. Review Service
6. Recommendation Service
7. Forum / Discussion Service
8. Analytics / Statistics Service

Claudio will do:
- User, Anime and Rating Service

Antonio will do:
- Watchlist, Recommendation and Analytics Service

Artur will do:
- Review and Forum Service

### Architecture Diagram
![Architecture](diagrama-projeto-cn.png)
### Diagram Description
This diagram illustrates the high‑level architecture of an anime‑focused api backend cloud native app. It shows how the browser, API gateway, backend services, and databases interact to deliver features like recommendations, reviews, ratings, and user management.Each feature of the application is implemented as an independent microservice, each with its own dedicated database. This supports scalability and modular development.