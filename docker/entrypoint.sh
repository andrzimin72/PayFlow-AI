#!/bin/bash
# =============================================================================
# Entrypoint Script for PayFlow AI
# =============================================================================
# This script handles service startup based on the SERVICE environment variable.
# It provides a unified entry point for all services.
#
# Usage:
#   SERVICE=api ./entrypoint.sh        # Start FastAPI
#   SERVICE=app ./entrypoint.sh        # Start Streamlit
#   SERVICE=webhook ./entrypoint.sh    # Start webhook listener
#   ./entrypoint.sh shell              # Drop into shell
#   ./entrypoint.sh <custom-command>   # Run custom command
# =============================================================================

set -e

# Default values
SERVICE=${SERVICE:-api}
ENVIRONMENT=${ENVIRONMENT:-production}
LOG_LEVEL=${LOG_LEVEL:-INFO}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[PayFlow AI]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PayFlow AI]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[PayFlow AI]${NC} $1"
}

log_error() {
    echo -e "${RED}[PayFlow AI]${NC} $1"
}

# Display startup banner
show_banner() {
    log "=========================================="
    log "  PayFlow AI - Enterprise Platform"
    log "=========================================="
    log "Service:     $SERVICE"
    log "Environment: $ENVIRONMENT"
    log "Log Level:   $LOG_LEVEL"
    log "Python:      $(python --version)"
    log "=========================================="
}

# Wait for dependencies (Elasticsearch, etc.)
wait_for_dependencies() {
    if [ -n "$ES_HOST" ]; then
        log "Waiting for Elasticsearch at $ES_HOST..."
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if curl -f -s "$ES_HOST/_cluster/health" > /dev/null 2>&1; then
                log_success "Elasticsearch is ready"
                break
            fi
            
            log_warning "Elasticsearch not ready (attempt $attempt/$max_attempts)"
            sleep 2
            attempt=$((attempt + 1))
        done
        
        if [ $attempt -gt $max_attempts ]; then
            log_error "Elasticsearch did not become ready in time"
            exit 1
        fi
    fi
}

# Pre-start checks
pre_start_checks() {
    # Check for required environment variables
    if [ "$SERVICE" = "api" ] || [ "$SERVICE" = "webhook" ]; then
        if [ -z "$PAYPAL_CLIENT_ID" ] || [ -z "$PAYPAL_SECRET" ]; then
            log_warning "PayPal credentials not set. Using sandbox defaults."
        fi
    fi
    
    # Create necessary directories
    mkdir -p logs data
    
    log_success "Pre-start checks completed"
}

# Start the appropriate service
start_service() {
    case "$SERVICE" in
        "api")
            log "Starting FastAPI server..."
            exec uvicorn api:app \
                --host 0.0.0.0 \
                --port ${PORT:-8000} \
                --log-level ${LOG_LEVEL,,} \
                ${ENVIRONMENT:+--reload}
            ;;
        
        "app")
            log "Starting Streamlit dashboard..."
            exec streamlit run app.py \
                --server.port ${PORT:-8501} \
                --server.address 0.0.0.0 \
                --server.headless true \
                --browser.gatherUsageStats false
            ;;
        
        "webhook")
            log "Starting webhook listener..."
            exec python webhook_listener.py
            ;;
        
        "shell")
            log "Starting interactive shell..."
            exec /bin/bash
            ;;
        
        *)
            # If not a known service, treat as custom command
            log "Running custom command: $@"
            exec "$@"
            ;;
    esac
}

# Main execution
main() {
    show_banner
    pre_start_checks
    wait_for_dependencies
    start_service "$@"
}

# Run main function with all arguments
main "$@"