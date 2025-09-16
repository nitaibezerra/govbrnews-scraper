#!/bin/bash
set -e

echo "Starting GovBR News database initialization..."

# Activate the virtual environment
source /opt/venv/bin/activate

# Wait a bit for PostgreSQL to fully start
sleep 5

# Run the Python initialization script
echo "Running Python database initialization script..."
python3 /docker-entrypoint-initdb.d/01-init-db.py

echo "Database initialization completed!"
