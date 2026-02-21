#!/usr/bin/env bash
# Create Kubernetes secret from .env (or export OPENAI_API_KEY, MCP_SERVER_URL).
# Run from project root. Requires .env or env vars set.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
kubectl create namespace agentic --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic agentic-api-secret -n agentic \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:?Set OPENAI_API_KEY}" \
  --from-literal=MCP_SERVER_URL="${MCP_SERVER_URL:-http://mcp-service:3000/mcp}" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "Secret agentic-api-secret updated in namespace agentic."
