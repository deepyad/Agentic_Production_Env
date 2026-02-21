#!/usr/bin/env bash
# Deploy to AKS using Azure overlay (ACR image). Creates/updates namespace and applies manifests.
# Usage: ./infra/scripts/azure-deploy.sh <ACR_NAME> [IMAGE_TAG]
# Example: ./infra/scripts/azure-deploy.sh myregistry latest
# Prerequisites: 1) Image already pushed to ACR (run azure-build-push.sh). 2) kubectl context set to your AKS cluster. 3) Secret created (create-secret-from-env.sh or edit secret.yaml).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ACR_NAME="${1:?Usage: $0 <ACR_NAME> [IMAGE_TAG]   (ACR_NAME = ACR login name, e.g. myregistry)"}"
IMAGE_TAG="${2:-latest}"
OVERLAY_DIR="infra/kubernetes/overlays/azure"
KUSTOMIZATION="${OVERLAY_DIR}/kustomization.yaml"

# Patch overlay with ACR name and tag (restore after apply)
cp "$KUSTOMIZATION" "${KUSTOMIZATION}.bak"
sed -e "s/YOUR_ACR_NAME/${ACR_NAME}/g" -e "s/newTag: latest/newTag: ${IMAGE_TAG}/" "${KUSTOMIZATION}.bak" > "$KUSTOMIZATION"

echo "Applying Azure overlay (ACR: ${ACR_NAME}.azurecr.io, tag: ${IMAGE_TAG})..."
kubectl apply -k "$OVERLAY_DIR"

mv "${KUSTOMIZATION}.bak" "$KUSTOMIZATION"

echo "Deploy applied. Check: kubectl get pods -n agentic"
