#!/usr/bin/env bash
# Build image and push to Azure Container Registry (ACR).
# Usage: ./infra/scripts/azure-build-push.sh <ACR_NAME> [IMAGE_TAG]
# Example: ./infra/scripts/azure-build-push.sh myregistry v1.0
# Requires: az CLI, docker, and az login + az acr login
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ACR_NAME="${1:?Usage: $0 <ACR_NAME> [IMAGE_TAG]   (ACR_NAME = Azure Container Registry login name, e.g. myregistry)"}"
IMAGE_TAG="${2:-latest}"
IMAGE_NAME="agentic-api"
FULL_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Logging in to ACR ${ACR_NAME}..."
az acr login --name "$ACR_NAME"

echo "Building image..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f infra/docker/Dockerfile .

echo "Tagging and pushing ${FULL_IMAGE}..."
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$FULL_IMAGE"
docker push "$FULL_IMAGE"

echo "Done. Image pushed to ${FULL_IMAGE}"
echo "Deploy with: ./infra/scripts/azure-deploy.sh $ACR_NAME $IMAGE_TAG"
