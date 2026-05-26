# This file builds an environment that can run the analytics endpoint

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