#!/bin/bash
# =============================================================================
# Health Check Script for PayFlow AI
# =============================================================================
# This script checks the health of the running service based on the SERVICE
# environment variable. Used by Docker's HEALTHCHECK directive.
#
# Exit codes:
#   0 = Healthy
#   1 = Unhealthy
# =============================================================================

set -e

# Determine which service is running
SERVICE=${SERVICE:-api}
PORT=${PORT:-8000}

# Function to check HTTP endpoint
check_http() {
    local url=$1
    local timeout=${2:-5}
    
    if curl -f -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" | grep -q "200"; then
        return 0
    else
        return 1
    fi
}

# Function to check if process is running
check_process() {
    local process_name=$1
    
    if pgrep -f "$process_name" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Health check logic based on service type
case "$SERVICE" in
    "api")
        # FastAPI has a /health endpoint
        if check_http "http://localhost:${PORT}/health"; then
            echo "✓ API is healthy"
            exit 0
        else
            echo "✗ API is unhealthy"
            exit 1
        fi
        ;;
    
    "webhook")
        # Webhook listener has a /health endpoint
        if check_http "http://localhost:${PORT}/health"; then
            echo "✓ Webhook listener is healthy"
            exit 0
        else
            echo "✗ Webhook listener is unhealthy"
            exit 1
        fi
        ;;
    
    "app")
        # Streamlit doesn't have a built-in health endpoint
        # Check if the process is running and port is listening
        if check_process "streamlit" && \
           netstat -tuln 2>/dev/null | grep -q ":${PORT}" || \
           ss -tuln 2>/dev/null | grep -q ":${PORT}"; then
            echo "✓ Streamlit app is healthy"
            exit 0
        else
            echo "✗ Streamlit app is unhealthy"
            exit 1
        fi
        ;;
    
    *)
        echo "✗ Unknown service: $SERVICE"
        exit 1
        ;;
esac