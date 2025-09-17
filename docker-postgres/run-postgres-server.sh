#!/bin/bash

# GovBR News PostgreSQL Server - Build, Run & Test Script
# This script automates the process of building and testing the PostgreSQL container
#
# Usage:
#   ./run-postgres-server.sh [COMMAND]
#
# Commands:
#   (no args)  - Build and run PostgreSQL server (default)
#   cleanup    - Remove container, image, and persistent volume (full cleanup)
#   refresh    - Update dataset in running container (keeps existing data structure)
#   help       - Show this help message

set -e  # Exit on any error

# Configuration
CONTAINER_NAME="govbrnews-db"
IMAGE_NAME="govbrnews-postgres"
POSTGRES_PORT="5433"
VOLUME_NAME="govbrnews-data"

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
    echo -e "${BLUE}GovBR News PostgreSQL Server${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run-postgres-server.sh [COMMAND]"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  ${GREEN}(no args)${NC}  Build and run PostgreSQL server with dataset (default)"
    echo "  ${GREEN}cleanup${NC}    Remove container, image, and persistent volume (full reset)"
    echo "  ${GREEN}refresh${NC}    Update dataset in running container (preserves structure)"
    echo "  ${GREEN}help${NC}       Show this help message"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./run-postgres-server.sh           # Start the server"
    echo "  ./run-postgres-server.sh cleanup   # Clean everything for fresh start"
    echo "  ./run-postgres-server.sh refresh   # Update dataset in running container"
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

    log_success "🧹 Full cleanup completed! Run './run-postgres-server.sh' to start fresh."
}

# Function to refresh dataset in running container
refresh_dataset() {
    log_step "Refreshing dataset in running container"

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_error "Container '${CONTAINER_NAME}' is not running!"
        log_info "To start the server, run: ./run-postgres-server.sh"
        exit 1
    fi

    log_info "Container is running, proceeding with dataset refresh..."

    # Check if container has our initialization script
    if ! docker exec ${CONTAINER_NAME} test -f /docker-entrypoint-initdb.d/01-init-db.py; then
        log_error "Initialization script not found in container. Please rebuild the container."
        log_info "Run: ./run-postgres-server.sh cleanup && ./run-postgres-server.sh"
        exit 1
    fi

    log_info "Starting dataset refresh process..."
    log_info "This will download the latest dataset and update the database..."

    log_info "📥 Downloading latest dataset from HuggingFace..."
    start_time=$(date +%s)

    # Run the refresh process and capture output
    if docker exec ${CONTAINER_NAME} bash -c "
        source /opt/venv/bin/activate &&
        python3 /docker-entrypoint-initdb.d/01-init-db.py
    "; then
        end_time=$(date +%s)
        refresh_duration=$((end_time - start_time))

        # Verify the refresh
        log_info "Verifying dataset refresh..."
        record_count=$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" | xargs)
        log_success "✅ Database now contains ${record_count} records"
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

    if lsof -i :${POSTGRES_PORT} >/dev/null 2>&1; then
        log_warning "Port ${POSTGRES_PORT} is already in use!"
        log_info "Services using port ${POSTGRES_PORT}:"
        lsof -i :${POSTGRES_PORT}
        log_error "Please stop the service using port ${POSTGRES_PORT} or modify the script to use a different port"
        exit 1
    else
        log_success "Port ${POSTGRES_PORT} is available"
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
    log_step "Starting PostgreSQL container"

    log_info "Starting container: ${CONTAINER_NAME}"
    log_info "Port mapping: localhost:${POSTGRES_PORT} -> container:5432"
    log_info "Using persistent volume: ${VOLUME_NAME}"

    container_id=$(docker run -d \
        --name ${CONTAINER_NAME} \
        -p ${POSTGRES_PORT}:5432 \
        -e POSTGRES_DB=govbrnews \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -v ${VOLUME_NAME}:/var/lib/postgresql/data \
        ${IMAGE_NAME})

    log_success "Container started with ID: ${container_id:0:12}"
}

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    log_step "Waiting for PostgreSQL to be ready"

    max_attempts=60
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker exec ${CONTAINER_NAME} pg_isready -U postgres >/dev/null 2>&1; then
            log_success "PostgreSQL is ready after ${attempt} attempts"
            return 0
        else
            log_info "Attempt ${attempt}/${max_attempts}: PostgreSQL not ready yet..."
            sleep 2
            attempt=$((attempt + 1))
        fi
    done

    log_error "PostgreSQL failed to start within expected time"
    log_info "Container logs:"
    docker logs ${CONTAINER_NAME} --tail 20
    exit 1
}

# Function to wait for database initialization
wait_for_initialization() {
    log_step "Waiting for database initialization to complete"

    # Check if database already contains data (from persistent volume)
    sleep 5  # Give PostgreSQL a moment to start

    if docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | grep -q -E "[0-9]+" && [ "$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | xargs)" -gt 0 ]; then
        record_count=$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | xargs)
        log_success "Database already initialized with ${record_count} records (using persistent volume)"
        return 0
    fi

    log_info "Fresh database detected - monitoring initialization progress..."
    log_info "This process downloads ~290k news records from HuggingFace and may take 2-5 minutes"

    start_time=$(date +%s)

    # Monitor logs for completion
    timeout=600  # 10 minutes timeout
    elapsed=0

    while [ $elapsed -lt $timeout ]; do
        # Check if initialization completed successfully
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Database initialization completed successfully"; then
            end_time=$(date +%s)
            init_duration=$((end_time - start_time))
            log_success "Database initialization completed in ${init_duration} seconds"
            return 0
        fi

        # Check for initialization failure
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Database initialization failed"; then
            log_error "Database initialization failed!"
            log_info "Recent container logs:"
            docker logs ${CONTAINER_NAME} --tail 20
            exit 1
        fi

        # Check if PostgreSQL skipped initialization (database already exists)
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Skipping initialization"; then
            log_warning "PostgreSQL skipped initialization - database directory already exists"
            log_info "Checking if database contains data..."

            # Wait a bit more for PostgreSQL to be fully ready
            sleep 10

            if docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | grep -q -E "[0-9]+"; then
                record_count=$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" 2>/dev/null | xargs)
                if [ "$record_count" -gt 0 ]; then
                    log_success "Database already contains ${record_count} records"
                    return 0
                else
                    log_error "Database exists but appears empty. You may need to remove the volume and restart."
                    exit 1
                fi
            else
                log_error "Cannot access database. Please check container status."
                exit 1
            fi
        fi

        # Show progress indicators
        if docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Downloading govbrnews dataset"; then
            log_info "📥 Downloading dataset from HuggingFace..."
        elif docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Dataset downloaded successfully"; then
            log_info "✅ Dataset downloaded, processing data..."
        elif docker logs ${CONTAINER_NAME} 2>&1 | grep -q "Inserting data into PostgreSQL"; then
            log_info "💾 Inserting data into PostgreSQL..."
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

    # Test 1: Basic connection and record count
    log_info "Test 1: Checking total record count"
    record_count=$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "SELECT COUNT(*) FROM news;" | xargs)
    log_success "✅ Total records in database: ${record_count}"

    # Test 2: Check schema with new theme column
    log_info "Test 2: Verifying theme_1_level_1 column exists"
    if docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "\d news" | grep -q "theme_1_level_1"; then
        log_success "✅ theme_1_level_1 column exists in schema"
    else
        log_error "❌ theme_1_level_1 column not found in schema"
        exit 1
    fi

    # Test 3: Sample data query
    log_info "Test 3: Querying recent news samples"
    echo -e "\n${YELLOW}Recent news sample:${NC}"
    docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -c "
        SELECT
            LEFT(title, 60) || '...' as title_preview,
            agency,
            published_at::date as date,
            CASE WHEN theme_1_level_1 IS NULL THEN 'No theme' ELSE theme_1_level_1 END as theme
        FROM news
        WHERE published_at > '2025-09-01'
        ORDER BY published_at DESC
        LIMIT 5;"

    # Test 4: Agency statistics
    log_info "Test 4: Agency statistics"
    echo -e "\n${YELLOW}Top 5 agencies by news count:${NC}"
    docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -c "
        SELECT
            agency,
            COUNT(*) as news_count
        FROM news
        WHERE agency IS NOT NULL
        GROUP BY agency
        ORDER BY news_count DESC
        LIMIT 5;"

    # Test 5: Theme column status
    log_info "Test 5: Theme column statistics"
    theme_stats=$(docker exec ${CONTAINER_NAME} psql -U postgres -d govbrnews -t -c "
        SELECT
            COUNT(*) as total,
            COUNT(theme_1_level_1) as with_theme,
            COUNT(*) - COUNT(theme_1_level_1) as without_theme
        FROM news;" | xargs)
    log_success "✅ Theme column ready: ${theme_stats}"
}

# Function to show connection info
show_connection_info() {
    log_step "Connection Information"

    echo -e "${GREEN}🎉 PostgreSQL server is ready!${NC}\n"

    echo -e "${YELLOW}Connection Details:${NC}"
    echo -e "  Host: localhost"
    echo -e "  Port: ${POSTGRES_PORT}"
    echo -e "  Database: govbrnews"
    echo -e "  Username: postgres"
    echo -e "  Password: postgres"

    echo -e "\n${YELLOW}Quick Connection Commands:${NC}"
    echo -e "  # Connect using psql (external):"
    echo -e "  PGPASSWORD=postgres psql -h localhost -p ${POSTGRES_PORT} -U postgres -d govbrnews"

    echo -e "\n  # Connect using Docker exec:"
    echo -e "  docker exec -it ${CONTAINER_NAME} psql -U postgres -d govbrnews"

    echo -e "\n${YELLOW}Management Commands:${NC}"
    echo -e "  # View logs:"
    echo -e "  docker logs -f ${CONTAINER_NAME}"

    echo -e "\n  # Stop container:"
    echo -e "  docker stop ${CONTAINER_NAME}"

    echo -e "\n  # Remove container:"
    echo -e "  docker stop ${CONTAINER_NAME} && docker rm ${CONTAINER_NAME}"

    echo -e "\n${YELLOW}Script Commands:${NC}"
    echo -e "  # Update dataset with latest data (container must be running):"
    echo -e "  ./run-postgres-server.sh refresh"

    echo -e "\n  # Full cleanup (remove container, image, and volume for fresh start):"
    echo -e "  ./run-postgres-server.sh cleanup"

    echo -e "\n  # Show help and available commands:"
    echo -e "  ./run-postgres-server.sh help"
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                GovBR News PostgreSQL Server                    ║"
    echo "║                   Build, Run & Test Script                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"

    # Check if we're in the right directory
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile not found! Please run this script from the docker-postgres/ directory"
        exit 1
    fi

    # Execute main steps
    cleanup_existing
    check_port
    create_volume
    build_image
    run_container
    wait_for_postgres
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
