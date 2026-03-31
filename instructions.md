# Instructions

## To Local Development
If you don't have an environment created, execute the following commands:
> python -m venv venv

In Unix/MacOS Systems open a shell in this directory and prompt:
> source venv/bin/activate

In Windows Systems, open prompt and enter:
> venv\Scripts\activate

To run each microserver locally execute the following command:
> uvicorn main:app --reload

## API Gateway NGINX
In the API gateway directory, execute the following commands:
> docker build -t gateway .
> docker run -d --name gateway -p 8000:8000 gateway

## Microservices
We have 3 microservices (plus 1) built on docker images to be executed as containers. Inside each directory, execute the following commands:

> cd user-service/
> docker build -t user-service .
> docker run -d --name users -p 8001:8001 user-service

Available endpoint: localhost:8001/users

> cd catalog-service/
> docker build -t catalog-service .
> docker run -d --name catalogs -p 8002:8002 catalog-service

Available endpoint: localhost:8002/anime

> cd rating-service/
> docker build -t rating-service .
> docker run -d --name ratings -p 8003:8003 rating-service

Available endpoint: localhost:8003/rating

## How to access the API Gateway

Access the API Gateway at localhost:8000.

