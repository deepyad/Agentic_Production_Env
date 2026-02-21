# Agentic Production Framework

LangGraph + LLM multi-agent framework for chatbot-style customer support at scale.

**Documentation:**

- **[Documentation/README.md](Documentation/README.md)** — Quick start, API (chat, health, GraphQL, HITL), project structure, tools, guardrails, router, HITL.
- **[Documentation/ARCHITECTURE_DESIGN.md](Documentation/ARCHITECTURE_DESIGN.md)** — Full architecture, diagrams, deployment, observability, HITL module.
- **[Documentation/CODE_WALKTHROUGH.md](Documentation/CODE_WALKTHROUGH.md)** — File-by-file walkthrough and request flow.
- **[Documentation/Issues_list_Tracker.md](Documentation/Issues_list_Tracker.md)** — Hypothetical issues and fixes (reference).

Quick start: `pip install -r requirements.txt`, set `.env` (see `Documentation/README.md`), then `python main.py`.

**Docker & Kubernetes:** See `infra/` for Dockerfile and Kubernetes manifests (namespace, deployment, service, HPA, scripts). Build: `./infra/scripts/build.sh`; deploy: `kubectl apply -k infra/kubernetes` (after creating the secret).
