#!/usr/bin/env bash
# Build Docker image for Agentic API. Run from project root.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"
IMAGE_NAME="${IMAGE_NAME:-agentic-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
docker build -t "$IMAGE_NAME:$IMAGE_TAG" -f infra/docker/Dockerfile .
echo "Built $IMAGE_NAME:$IMAGE_TAG"
