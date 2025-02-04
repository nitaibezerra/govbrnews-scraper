# Use a Python base image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for Poetry & Python dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libbz2-dev \
    liblzma-dev \
    libsqlite3-dev \
    libreadline-dev \
    zlib1g-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Poetry configuration first for dependency caching
COPY pyproject.toml poetry.lock ./

# Install Poetry
RUN pip install --no-cache-dir poetry

# Install dependencies using Poetry
RUN poetry install --no-root --no-interaction --no-ansi

# Copy the rest of the application files
COPY . /app

# Default working directory should be /app
WORKDIR /app

# Default command
CMD [ "poetry", "run", "python", "src/main.py", "--help" ]