# Use any Python base image you prefer
FROM python:3.13-slim

# Create app directory
WORKDIR /app

# Copy only pyproject and poetry.lock first for dependency installation caching
COPY pyproject.toml poetry.lock ./

# Install Poetry and dependencies
RUN pip install --no-cache-dir poetry \
 && poetry install --no-root --no-interaction --no-ansi

# Now copy the rest of your code
COPY . /app

# Default command (this can be overridden in your workflow)
CMD [ "poetry", "run", "python", "src/main.py", "--help" ]