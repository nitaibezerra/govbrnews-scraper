#!/bin/bash
set -e

echo "Starting GovBR News Typesense server..."

# Start Typesense server in the background
echo "Launching Typesense server..."
/opt/typesense-server \
    --data-dir=${TYPESENSE_DATA_DIR} \
    --api-key=${TYPESENSE_API_KEY} \
    --enable-cors \
    --log-dir=/tmp &

TYPESENSE_PID=$!

# Wait for Typesense to be ready
echo "Waiting for Typesense to be ready..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8108/health > /dev/null 2>&1; then
        echo "Typesense is ready!"
        break
    fi
    echo "Attempt ${attempt}/${max_attempts}: Typesense not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "ERROR: Typesense failed to start within expected time"
    exit 1
fi

# Check if data already exists (skip initialization if data directory has collections)
if [ -f "${TYPESENSE_DATA_DIR}/state/db/CURRENT" ]; then
    echo "Data directory contains existing data - skipping initialization"
else
    echo "Fresh data directory detected - running initialization..."

    # Activate the virtual environment
    source /opt/venv/bin/activate

    # Run Python initialization script
    echo "Running Typesense database initialization script..."
    python3 /opt/init-typesense.py

    echo "Initialization completed!"
fi

# Keep the container running by waiting on the Typesense process
echo "Typesense server is running and ready to accept connections!"
echo "API Key: ${TYPESENSE_API_KEY}"
echo "Port: 8108"

wait $TYPESENSE_PID
