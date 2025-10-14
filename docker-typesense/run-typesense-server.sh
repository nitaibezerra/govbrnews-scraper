#!/bin/bash

# GovBR News Typesense Server - Build, Run & Test Script
# This script automates the process of building and testing the Typesense container
#
# Features:
#   - Can be run from anywhere (automatically changes to correct directory)
#   - Full container lifecycle management (build, run, cleanup, refresh)
#   - Comprehensive error handling and logging
#
# Usage:
#   ./run-typesense-server.sh [COMMAND]
#   docker-typesense/run-typesense-server.sh [COMMAND]  # From project root
#
# Commands:
#   (no args)  - Build and run Typesense server (default)
#   cleanup    - Remove container, image, and persistent volume (full cleanup)
#   refresh    - Update dataset in running container (keeps existing data structure)
#   help       - Show this help message

set -e  # Exit on any error

# Configuration
CONTAINER_NAME="govbrnews-typesense"
IMAGE_NAME="govbrnews-typesense"
TYPESENSE_PORT="8108"
VOLUME_NAME="govbrnews-typesense-data"
API_KEY="govbrnews_api_key_change_in_production"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}===${NC} $1 ${BLUE}===${NC}"
}

# Function to show help
show_help() {
    echo -e "${BLUE}GovBR News Typesense Server${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run-typesense-server.sh [COMMAND]"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  ${GREEN}(no args)${NC}  Build and run Typesense server with dataset (default)"
    echo "  ${GREEN}cleanup${NC}    Remove container, image, and persistent volume (full reset)"
    echo "  ${GREEN}refresh${NC}    Update dataset in running container (recreates collection)"
    echo "  ${GREEN}help${NC}       Show this help message"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./run-typesense-server.sh           # Start the server"
    echo "  ./run-typesense-server.sh cleanup   # Clean everything for fresh start"
    echo "  ./run-typesense-server.sh refresh   # Update dataset in running container"
    echo ""
    echo -e "${YELLOW}Note:${NC}"
    echo "  This script can be run from anywhere - it will automatically"
    echo "  change to the correct directory (docker-typesense/) before executing."
    echo ""
}

# Function to cleanup existing container and image
cleanup_existing() {
    log_step "Cleaning up existing container and image"

    # Stop and remove existing container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Stopping existing container: ${CONTAINER_NAME}"
        docker stop ${CONTAINER_NAME} >/dev/null 2>&1 || true
        log_info "Removing existing container: ${CONTAINER_NAME}"
        docker rm ${CONTAINER_NAME} >/dev/null 2>&1 || true
        log_success "Existing container removed"
    else
        log_info "No existing container found"
    fi

    # Remove existing image if it exists
    if docker images --format '{{.Repository}}' | grep -q "^${IMAGE_NAME}$"; then
        log_info "Removing existing image: ${IMAGE_NAME}"
        docker rmi ${IMAGE_NAME} >/dev/null 2>&1 || true
        log_success "Existing image removed"
    else
        log_info "No existing image found"
    fi
}

# Function for full cleanup (container, image, and volume)
full_cleanup() {
    log_step "Performing full cleanup (container, image, and volume)"

    # Ensure we're in the correct directory for any Docker operations
    ensure_correct_directory

    # Stop and remove container
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Stopping container: ${CONTAINER_NAME}"
        docker stop ${CONTAINER_NAME} >/dev/null 2>&1 || true
        log_info "Removing container: ${CONTAINER_NAME}"
        docker rm ${CONTAINER_NAME} >/dev/null 2>&1 || true
        log_success "Container removed"
    else
        log_info "No container found to remove"
    fi

    # Remove image
    if docker images --format '{{.Repository}}' | grep -q "^${IMAGE_NAME}$"; then
        log_info "Removing image: ${IMAGE_NAME}"
        docker rmi ${IMAGE_NAME} >/dev/null 2>&1 || true
        log_success "Image removed"
    else
        log_info "No image found to remove"
    fi

    # Remove volume
    if docker volume ls --format '{{.Name}}' | grep -q "^${VOLUME_NAME}$"; then
        log_info "Removing persistent volume: ${VOLUME_NAME}"
        docker volume rm ${VOLUME_NAME} >/dev/null 2>&1 || true
        log_success "Volume removed"
    else
        log_info "No volume found to remove"
    fi

    log_success "🧹 Full cleanup completed! Run './run-typesense-server.sh' to start fresh."
}

# Function to refresh dataset in running container
refresh_dataset() {
    log_step "Refreshing dataset in running container"

    # Ensure we're in the correct directory (though not strictly needed for refresh)
    ensure_correct_directory

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_error "Container '${CONTAINER_NAME}' is not running!"
        log_info "To start the server, run: ./run-typesense-server.sh"
        exit 1
    fi

    log_info "Container is running, proceeding with dataset refresh..."

    # First, delete the existing collection
    log_info "Deleting existing collection..."
    if docker exec ${CONTAINER_NAME} curl -s -X DELETE \
        "http://localhost:8108/collections/news" \
        -H "X-TYPESENSE-API-KEY: ${API_KEY}" >/dev/null 2>&1; then
        log_success "Existing collection deleted"
    else
        log_warning "Collection may not exist or could not be deleted (this is okay for first run)"
    fi

    log_info "Starting dataset refresh process..."
    log_info "This will download the latest dataset and reindex the collection..."

    log_info "📥 Downloading latest dataset from HuggingFace..."
    start_time=$(date +%s)

    # Run the refresh process and capture output
    if docker exec ${CONTAINER_NAME} bash -c "
        source /opt/venv/bin/activate &&
        python3 /opt/init-typesense.py
    "; then
        end_time=$(date +%s)
        refresh_duration=$((end_time - start_time))

        # Verify the refresh
        log_info "Verifying dataset refresh..."
        doc_count=$(docker exec ${CONTAINER_NAME} curl -s \
            "http://localhost:8108/collections/news" \
            -H "X-TYPESENSE-API-KEY: ${API_KEY}" | grep -o '"num_documents":[0-9]*' | cut -d: -f2)

        if [ -n "$doc_count" ]; then
            log_success "✅ Collection now contains ${doc_count} documents"
        else
            log_success "✅ Collection refreshed (document count unavailable)"
        fi
        log_success "🔄 Dataset refresh completed successfully in ${refresh_duration} seconds!"
    else
        log_error "Dataset refresh failed! Check container logs for details."
        log_info "Container logs:"
        docker logs ${CONTAINER_NAME} --tail 20
        exit 1
    fi
}

# Function to check if port is available
check_port() {
    log_step "Checking port availability"

    if lsof -i :${TYPESENSE_PORT} >/dev/null 2>&1; then
        log_warning "Port ${TYPESENSE_PORT} is already in use!"
        log_info "Services using port ${TYPESENSE_PORT}:"
        lsof -i :${TYPESENSE_PORT}
        log_error "Please stop the service using port ${TYPESENSE_PORT} or modify the script to use a different port"
        exit 1
    else
        log_success "Port ${TYPESENSE_PORT} is available"
    fi
}

# Function to create Docker volume
create_volume() {
    log_step "Creating Docker volume for persistent storage"

    if docker volume ls --format '{{.Name}}' | grep -q "^${VOLUME_NAME}$"; then
        log_info "Volume ${VOLUME_NAME} already exists"
    else
        log_info "Creating new volume: ${VOLUME_NAME}"
        docker volume create ${VOLUME_NAME}
        log_success "Volume ${VOLUME_NAME} created"
    fi
}

# Function to build Docker image
build_image() {
    log_step "Building Docker image"

    log_info "Building image: ${IMAGE_NAME}"
    log_info "This may take a few minutes on first build..."

    start_time=$(date +%s)

    if docker build -t ${IMAGE_NAME} . ; then
        end_time=$(date +%s)
        build_duration=$((end_time - start_time))
        log_success "Image built successfully in ${build_duration} seconds"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

# Function to run container
run_container() {
    log_step "Starting Typesense container"

    log_info "Starting container: ${CONTAINER_NAME}"
    log_info "Port mapping: localhost:${TYPESENSE_PORT} -> container:8108"
    log_info "Using persistent volume: ${VOLUME_NAME}"

    container_id=$(docker run -d \
        --name ${CONTAINER_NAME} \
        -p ${TYPESENSE_PORT}:8108 \
        -e TYPESENSE_API_KEY=${API_KEY} \
        -e TYPESENSE_DATA_DIR=/data \
        -v ${VOLUME_NAME}:/data \
        ${IMAGE_NAME})

    log_success "Container started with ID: ${container_id:0:12}"
}

# Function to wait for Typesense to be ready
wait_for_typesense() {
    log_step "Waiting for Typesense to be ready"

    max_attempts=30
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:${TYPESENSE_PORT}/health >/dev/null 2>&1; then
            log_success "Typesense is ready after ${attempt} attempts"
            return 0
        else
            log_info "Attempt ${attempt}/${max_attempts}: Typesense not ready yet..."
            sleep 2
            attempt=$((attempt + 1))
        fi
    done

    log_error "Typesense failed to start within expected time"
    log_info "Container logs:"
    docker logs ${CONTAINER_NAME} --tail 20
    exit 1
}

# Function to wait for initialization
wait_for_initialization() {
    log_step "Waiting for dataset initialization to complete"

    log_info "Monitoring initialization progress..."
    log_info "This process downloads ~290k news records from HuggingFace and may take 2-5 minutes"

    start_time=$(date +%s)

    # Monitor logs for completion
    timeout=600  # 10 minutes timeout
    elapsed=0

    while [ $elapsed -lt $timeout ]; do
        # Check if initialization completed successfully
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Typesense initialization completed successfully"; then
            end_time=$(date +%s)
            init_duration=$((end_time - start_time))
            log_success "Typesense initialization completed in ${init_duration} seconds"
            return 0
        fi

        # Check if data already exists (skipped initialization)
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Data directory contains existing data"; then
            log_success "Using existing data from persistent volume"
            return 0
        fi

        # Check for initialization failure
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Typesense initialization failed"; then
            log_error "Typesense initialization failed!"
            log_info "Recent container logs:"
            docker logs ${CONTAINER_NAME} --tail 20
            exit 1
        fi

        # Show progress indicators
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Downloading govbrnews dataset"; then
            log_info "📥 Downloading dataset from HuggingFace..."
        elif docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Dataset downloaded successfully"; then
            log_info "✅ Dataset downloaded, processing data..."
        elif docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Indexing documents into Typesense"; then
            log_info "💾 Indexing documents into Typesense..."
        fi

        sleep 5
        elapsed=$((elapsed + 5))
    done

    log_error "Initialization timeout after ${timeout} seconds"
    log_info "Container logs:"
    docker logs ${CONTAINER_NAME} --tail 30
    exit 1
}

# Function to run test queries
run_test_queries() {
    log_step "Running test queries to verify functionality"

    # Test 1: Get collection info
    log_info "Test 1: Checking collection info"
    collection_info=$(curl -s "http://localhost:${TYPESENSE_PORT}/collections/news" \
        -H "X-TYPESENSE-API-KEY: ${API_KEY}")

    doc_count=$(echo "$collection_info" | grep -o '"num_documents":[0-9]*' | cut -d: -f2)
    if [ -n "$doc_count" ]; then
        log_success "✅ Collection contains ${doc_count} documents"
    else
        log_warning "Could not retrieve document count"
    fi

    # Test 2: Simple search
    log_info "Test 2: Testing search functionality"
    search_result=$(curl -s "http://localhost:${TYPESENSE_PORT}/collections/news/documents/search?q=saúde&query_by=title,content&limit=3" \
        -H "X-TYPESENSE-API-KEY: ${API_KEY}")

    found=$(echo "$search_result" | grep -o '"found":[0-9]*' | cut -d: -f2)
    if [ -n "$found" ]; then
        log_success "✅ Search query returned ${found} results for 'saúde'"
    else
        log_warning "Search test inconclusive"
    fi

    # Test 3: Faceted search
    log_info "Test 3: Testing faceted search by agency"
    facet_result=$(curl -s "http://localhost:${TYPESENSE_PORT}/collections/news/documents/search?q=*&query_by=title&facet_by=agency&max_facet_values=5&limit=0" \
        -H "X-TYPESENSE-API-KEY: ${API_KEY}")

    if echo "$facet_result" | grep -q "facet_counts"; then
        log_success "✅ Faceted search is working"
        echo -e "\n${YELLOW}Top agencies by document count:${NC}"
        echo "$facet_result" | grep -o '"value":"[^"]*","count":[0-9]*' | head -5 | while read -r line; do
            agency=$(echo "$line" | grep -o '"value":"[^"]*"' | cut -d'"' -f4)
            count=$(echo "$line" | grep -o '"count":[0-9]*' | cut -d: -f2)
            echo "   $agency: $count documents"
        done
    else
        log_warning "Faceted search test inconclusive"
    fi
}

# Function to show connection info
show_connection_info() {
    log_step "Connection Information"

    echo -e "${GREEN}🎉 Typesense server is ready!${NC}\n"

    echo -e "${YELLOW}Connection Details:${NC}"
    echo -e "  Host: localhost"
    echo -e "  Port: ${TYPESENSE_PORT}"
    echo -e "  API Key: ${API_KEY}"
    echo -e "  Collection: news"

    echo -e "\n${YELLOW}Quick Test Commands:${NC}"
    echo -e "  # Health check:"
    echo -e "  curl http://localhost:${TYPESENSE_PORT}/health"

    echo -e "\n  # Get collection info:"
    echo -e "  curl \"http://localhost:${TYPESENSE_PORT}/collections/news\" \\"
    echo -e "    -H \"X-TYPESENSE-API-KEY: ${API_KEY}\""

    echo -e "\n  # Search for 'saúde':"
    echo -e "  curl \"http://localhost:${TYPESENSE_PORT}/collections/news/documents/search?q=saúde&query_by=title,content\" \\"
    echo -e "    -H \"X-TYPESENSE-API-KEY: ${API_KEY}\""

    echo -e "\n${YELLOW}Management Commands:${NC}"
    echo -e "  # View logs:"
    echo -e "  docker logs -f ${CONTAINER_NAME}"

    echo -e "\n  # Stop container:"
    echo -e "  docker stop ${CONTAINER_NAME}"

    echo -e "\n  # Remove container:"
    echo -e "  docker stop ${CONTAINER_NAME} && docker rm ${CONTAINER_NAME}"

    echo -e "\n${YELLOW}Script Commands:${NC}"
    echo -e "  # Update dataset with latest data (container must be running):"
    echo -e "  ./run-typesense-server.sh refresh"

    echo -e "\n  # Full cleanup (remove container, image, and volume for fresh start):"
    echo -e "  ./run-typesense-server.sh cleanup"

    echo -e "\n  # Show help and available commands:"
    echo -e "  ./run-typesense-server.sh help"
}

# Function to ensure we're in the correct directory
ensure_correct_directory() {
    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Change to the script directory (docker-typesense/)
    cd "$SCRIPT_DIR"

    log_info "Working directory: $SCRIPT_DIR"

    # Verify we have the required files
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile not found in $SCRIPT_DIR"
        log_error "This script must be located in the docker-typesense/ directory with the Dockerfile"
        exit 1
    fi

    if [ ! -f "init-typesense.py" ]; then
        log_error "init-typesense.py not found in $SCRIPT_DIR"
        log_error "Required files are missing from the docker-typesense/ directory"
        exit 1
    fi

    log_success "✅ All required files found in $SCRIPT_DIR"
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                GovBR News Typesense Server                     ║"
    echo "║                   Build, Run & Test Script                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"

    # Ensure we're in the correct directory
    ensure_correct_directory

    # Execute main steps
    cleanup_existing
    check_port
    create_volume
    build_image
    run_container
    wait_for_typesense
    wait_for_initialization
    run_test_queries
    show_connection_info

    log_success "🚀 Setup completed successfully!"
}

# Script execution with argument handling
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        "cleanup")
            echo -e "${BLUE}"
            echo "╔════════════════════════════════════════════════════════════════╗"
            echo "║                     Full Cleanup Mode                          ║"
            echo "╚════════════════════════════════════════════════════════════════╝"
            echo -e "${NC}\n"
            full_cleanup
            ;;
        "refresh")
            echo -e "${BLUE}"
            echo "╔════════════════════════════════════════════════════════════════╗"
            echo "║                   Dataset Refresh Mode                         ║"
            echo "╚════════════════════════════════════════════════════════════════╝"
            echo -e "${NC}\n"
            refresh_dataset
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        "")
            main "$@"
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
fi
