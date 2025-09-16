#!/bin/bash
set -e

echo "Starting GovBR News database initialization..."

# Activate the virtual environment
source /opt/venv/bin/activate

# During Docker init, PostgreSQL is already running and accessible
# We can connect directly since init scripts run after DB is ready

echo "Running Python database initialization script..."
python3 /docker-entrypoint-initdb.d/01-init-db.py

echo "Database initialization completed!"
