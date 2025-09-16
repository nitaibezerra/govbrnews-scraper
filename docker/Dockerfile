# PostgreSQL with HuggingFace GovBR News Dataset
FROM postgres:16

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment for Python dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy initialization scripts
COPY init-db.py /docker-entrypoint-initdb.d/01-init-db.py
COPY init-db.sh /docker-entrypoint-initdb.d/02-init-db.sh

# Make the shell script executable
RUN chmod +x /docker-entrypoint-initdb.d/02-init-db.sh

# Set environment variables for PostgreSQL
ENV POSTGRES_DB=govbrnews
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres

# Expose PostgreSQL port
EXPOSE 5432

# Use the default PostgreSQL entrypoint
CMD ["postgres"]
