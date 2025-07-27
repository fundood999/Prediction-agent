# Use a slim Python base image.
FROM python:3.12-slim

# Install system dependencies, build tools, and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    --no-install-recommends && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt file first to leverage Docker cache
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Set environment variable for GCP credentials
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/tools/key.json

# Expose the port FastAPI listens on
EXPOSE 8080

# Default command to run the FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
