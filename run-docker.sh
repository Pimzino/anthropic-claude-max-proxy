#!/bin/bash

# Anthropic Claude Max Proxy Docker Auto-Setup Script
# Usage: ./run-docker.sh [port]
# Example: ./run-docker.sh 8081

set -e

# Configuration
readonly DEFAULT_PORT=8081
readonly IMAGE_NAME="anthropic-claude-max-proxy"
readonly VOLUME_NAME="claude-tokens"
readonly CONTAINER_NAME="claude-proxy-server"

validate_port_number() {
    local port="$1"

    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        echo "Error: Invalid port number. Please provide a number between 1-65535"
        echo "Usage: $0 [port]"
        echo "Example: $0 8081"
        exit 1
    fi
}

build_docker_image() {
    echo "Step 1: Building Docker image..."

    if ! docker build -t "$IMAGE_NAME" -f docker_scripts/Dockerfile . > /dev/null 2>&1; then
        echo "Docker image build failed"
        exit 1
    fi

    echo "Docker image build completed successfully"
}

setup_docker_volume() {
    echo ""
    echo "Step 2: Setting up Docker volume..."

    if docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
        echo "Docker volume '$VOLUME_NAME' already exists"
        return 0
    fi

    if ! docker volume create "$VOLUME_NAME" > /dev/null 2>&1; then
        echo "Failed to create Docker volume"
        exit 1
    fi

    echo "Docker volume '$VOLUME_NAME' created successfully"
}

run_authentication() {
    echo ""
    echo "Step 3: Running authentication process..."

    if ! docker run -it --rm \
        -v "$VOLUME_NAME:/app/data" \
        "$IMAGE_NAME" python docker_scripts/claude_auth_for_docker.py; then
        echo "Authentication failed."
        exit 1
    fi

    echo ""
}

check_container_running() {
    docker ps -q -f name="$CONTAINER_NAME" | grep -q .
}

check_auth_status() {
    docker run --rm \
        -v "$VOLUME_NAME:/app/data" \
        "$IMAGE_NAME" python docker_scripts/check_auth_status.py 2>/dev/null
}

refresh_auth_if_needed() {
    echo ""
    echo "Checking authentication status..."

    if check_auth_status; then
        echo "✓ Authentication is still valid"
        return 0
    fi

    echo "Authentication expired or missing, refreshing..."
    run_authentication
    return $?
}

cleanup_stopped_named_container() {
    if ! docker ps -aq -f name="$CONTAINER_NAME" -f status=exited | grep -q .; then
        return 0
    fi

    echo "Removing stopped container..."
    docker rm "$CONTAINER_NAME" > /dev/null 2>&1 || true
}

cleanup_orphaned_containers() {
    local orphaned_count=$(docker ps -aq -f ancestor="$IMAGE_NAME" -f status=exited | wc -l)

    if [ "$orphaned_count" -eq 0 ]; then
        return 0
    fi

    echo "Cleaning up $orphaned_count orphaned container(s) from previous runs..."
    docker ps -aq -f ancestor="$IMAGE_NAME" -f status=exited | xargs -r docker rm > /dev/null 2>&1 || true
}

cleanup_existing_container() {
    echo ""
    echo "Step 4: Cleaning up stopped containers..."

    cleanup_stopped_named_container
    cleanup_orphaned_containers
}

stop_and_remove_container() {
    echo ""
    echo "Stopping and removing existing container..."

    docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" > /dev/null 2>&1 || true
    echo "Container stopped and removed"
}

is_port_in_use() {
    local port="$1"
    lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1
}

find_available_port() {
    local start_port="$1"
    local port="$start_port"

    while is_port_in_use "$port"; do
        echo "Port $port is in use, trying $((port + 1))..." >&2
        ((port++))

        # Safety check to avoid infinite loop
        if [ "$port" -gt 65535 ]; then
            echo "Error: No available ports found (checked up to 65535)" >&2
            exit 1
        fi
    done

    echo "$port"
}

check_explicit_port_availability() {
    local port="$1"

    if ! is_port_in_use "$port"; then
        return 0
    fi

    echo "Error: Port $port is already in use."
    echo "Please specify a different port or use the default port (which will auto-find an available port)."
    exit 1
}

resolve_port() {
    local requested_port="$1"
    local port
    local is_default_port=false

    # Determine if using default port or user-specified port
    if [ -z "$requested_port" ]; then
        port="$DEFAULT_PORT"
        is_default_port=true
    else
        port="$requested_port"
        validate_port_number "$port"
    fi

    # Handle port availability based on whether it's default or specified
    if [ "$is_default_port" = false ]; then
        echo "Using port: $port" >&2
        check_explicit_port_availability "$port"
        echo "$port"
        return 0
    fi

    if ! is_port_in_use "$port"; then
        echo "Using port: $port" >&2
        echo "$port"
        return 0
    fi

    echo "Default port $port is in use, finding next available port..." >&2
    port=$(find_available_port "$port")
    echo "Using port: $port" >&2
    echo "$port"
}

start_background_server() {
    local port="$1"

    echo ""
    echo "Step 5: Starting Claude Max Proxy server in background..."

    # Start server in background with container name
    # Run proxy.py directly to bypass menu with proper token file path
    container_id=$(docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$port:8081" \
        -v "$VOLUME_NAME:/app/data" \
        --restart unless-stopped \
        -e TOKEN_FILE=/app/data/tokens.json \
        "$IMAGE_NAME" python proxy.py 2>&1)

    if [ $? -ne 0 ] || [ -z "$container_id" ]; then
        echo "Failed to start server"
        echo "Error details: $container_id"
        exit 1
    fi

    display_success_info "$port"
}

display_success_info() {
    local port="$1"

    echo "Server started successfully in background!"
    echo ""
    echo "Server Details:"
    echo "   Server URL: http://localhost:$port"
    echo "   API Endpoint: http://localhost:$port/v1/messages"
    echo "   API Key: any-placeholder-string"
    echo "   Container Name: $CONTAINER_NAME"
    echo ""
    echo "Useful Commands:"
    echo "   Check status: docker ps -f name=$CONTAINER_NAME"
    echo "   View logs:    docker logs $CONTAINER_NAME -f"
    echo "   Stop server:  docker stop $CONTAINER_NAME"
    echo "   Remove:       docker rm $CONTAINER_NAME"
    echo ""
    echo "Setup completed! Your Claude Max Proxy is running in background."
}

handle_running_container() {
    echo ""
    echo "✓ Container '$CONTAINER_NAME' is already running"

    if ! refresh_auth_if_needed; then
        echo "Authentication refresh failed. Container is still running."
        echo "You may need to manually restart if authentication issues persist."
        return 1
    fi

    echo ""
    echo "Server is already running at http://localhost:8081"
    echo "Everything is up to date!"
    return 0
}

setup_new_container() {
    local requested_port="$1"
    local port

    port=$(resolve_port "$requested_port")

    echo ""

    build_docker_image
    setup_docker_volume
    run_authentication
    cleanup_existing_container
    start_background_server "$port"
}

main() {
    local requested_port="$1"

    echo "Starting Anthropic Claude Max Proxy Docker Setup"

    if check_container_running; then
        handle_running_container
        return $?
    fi

    setup_new_container "$requested_port"
}

# Execute main function with all arguments
main "$@"