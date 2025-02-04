# Use a slim Python image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for Poetry and Python packages
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

# Copy only Poetry files first to leverage caching
COPY pyproject.toml poetry.lock ./

# Install Poetry globally
RUN pip install --no-cache-dir poetry

# Make sure Poetry installs dependencies inside the system (not in a virtual environment)
RUN poetry config virtualenvs.create false

# Install dependencies system-wide
RUN poetry install --no-root --no-interaction --no-ansi

# Now copy the rest of the app
COPY . /app

# Default working directory should be /app
WORKDIR /app

# Default command
CMD [ "poetry", "run", "python", "src/main.py", "--help" ]