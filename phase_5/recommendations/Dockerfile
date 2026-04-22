# This file builds an environment that can run the recommendation system endpoint

# Use a smaller prebuilt Python image for a lighter container
FROM python:3.10-slim

# Set working directory inside the container (equivalent to cd /app)
WORKDIR /app

# Copy requirements file from host to container
COPY requirements.txt .

# Install Python dependencies during build time
# --no-cache-dir reduces image size by not keeping pip cache
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformer model during Docker build
# This makes the container less dependent on internet access at startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy all project files from host to container (/app)
COPY . .

# Document the port used by the FastAPI application inside the container
EXPOSE 8080

# Start the API server when the container runs
#   Run FastAPI using Uvicorn:
#   app:app  -> app.py file, FastAPI instance named "app"
#   0.0.0.0  -> listen on all network interfaces (allows external/container access)
#   8080     -> internal container port
#
# Note:
#   --reload is improper for deployment in Docker/GKE
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]