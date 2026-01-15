#!/bin/bash
set -e

# Get the project root directory (one level up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
PROJECT_NAME="grc-mcp-server"   # change this to your compose project name

echo "🔹 Stopping and removing existing containers..."
podman-compose -f "$COMPOSE_FILE" down --remove-orphans

echo "🔹 Removing old images for $PROJECT_NAME..."
# Remove only your project-related images (not all)
podman images | grep "$PROJECT_NAME" | awk '{print $3}' | xargs -r podman rmi -f || true

echo "🔹 Rebuilding and redeploying containers..."
podman-compose -f "$COMPOSE_FILE" up -d --build

echo "✅ Redeployment complete!"
podman ps

