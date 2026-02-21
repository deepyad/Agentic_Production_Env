#!/usr/bin/env bash
# Deploy to Kubernetes (apply kustomization). Run from project root.
# Ensure: 1) image is built and available to cluster, 2) secret values are set.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"
kubectl apply -k infra/kubernetes
echo "Deploy applied. Check: kubectl get pods -n agentic"
