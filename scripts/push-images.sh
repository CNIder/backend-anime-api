#!/usr/bin/env bash

echo "Logging into Docker Hub..."
docker login

cd ../user-service/
docker build -t user-service .
docker tag user-service cncc62/user-service
echo "Pushing user service image to Docker Hub..."
docker push cncc62/user-service

cd ../catalog-service/
docker build -t anime-service .
docker tag anime-service cncc62/anime-service
echo "Pushing anime service image to Docker Hub..."
docker push cncc62/anime-service

cd ../rating-service/
docker build -t rating-service .
docker tag rating-service cncc62/rating-service
echo "Pushing rating service image to Docker Hub..."
docker push cncc62/rating-service

echo "Done!"
echo "All Images Pushed"