# Agentic Production Framework

LangGraph + LLM multi-agent framework for chatbot-style customer support at scale. See `ARCHITECTURE_DESIGN.md` for the full design.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set required env vars
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-..., MCP_SERVER_URL=http://localhost:3000/mcp
# Optional: TOP_P, GUARDRAILS_ENABLED, WEAVIATE_URL, WEAVIATE_INDEX (see .env.example)

# Run the API
python main.py
# or: uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

## API

- **GET /health** — Health check
- **POST /chat** — Send a message, get a reply

### Chat Request

```json
{
  "user_id": "user_123",
  "message": "I need help with my invoice",
  "session_id": "optional-session-id"
}
```

### Chat Response

```json
{
  "session_id": "uuid",
  "reply": "Agent response...",
  "agent_id": "billing"
}
```

## Project Structure

```
src/
├── api.py              # FastAPI entrypoint (chat endpoint)
├── config.py           # Configuration
├── router.py           # Session router (intent → agent pools)
├── registry.py         # Agent registry
├── supervisor.py       # LangGraph supervisor graph
├── agents/             # Agent pool subgraphs (Support, Billing)
│   ├── support.py
│   └── billing.py
├── tools/              # LangChain tools + MCP (required)
│   ├── support_tools.py
│   ├── billing_tools.py
│   └── mcp_client.py
└── shared_services/    # RAG, history RAG, guardrails, intent classifier, session, conversation (stubs)
    ├── rag.py
    ├── guardrails.py
    ├── faithfulness.py        # FaithfulnessScorer, TFFaithfulnessScorer (aggregate)
    ├── history_rag.py
    ├── intent_classifier.py   # KeywordIntentClassifier, TFIntentClassifier (router)
    ├── session_store.py
    └── conversation_store.py
```

## Tools

- **Support agent:** `search_knowledge_base`, `create_support_ticket`
- **Billing agent:** `look_up_invoice`, `get_refund_status`, `create_refund_request`

MCP is required: set `MCP_SERVER_URL` (e.g. `http://localhost:3000/mcp`) in `.env`. Start an MCP server exposing tools before running the API.

## Guardrails

Input/output guardrails block off-topic or policy-violating content. Enabled by default (`GUARDRAILS_ENABLED=true`). `guard_input` runs on the user message before the agent; `guard_output` filters the agent reply. Use `SimpleGuardrailService` (keyword-based) or plug in a custom `GuardrailService`.

## Router Intent

Default: **keyword-based** mapping. Set `USE_TF_INTENT=true` and install `tensorflow` to use a small Keras intent classifier (trains from synthetic data or load from `TF_INTENT_MODEL_PATH`).

- **billing** — invoice, bill, payment, refund
- **tech** — tech, error, bug, install, troubleshoot
- **escalation** — human, agent, escalate, speak to someone
- **support** — default

**Infra:** Docker and Kubernetes assets are in `infra/` (Dockerfile, namespace, deployment, service, HPA, scripts). See `infra/README.md`.

Replace router and RAG stubs with Weaviate in production (set `WEAVIATE_URL` and optionally use `WeaviateRAGService`). **Intent router:** default is keyword-based; set `USE_TF_INTENT=true` (and install `tensorflow`) to use a small Keras intent classifier. **Faithfulness scoring:** set `USE_TF_FAITHFULNESS=true` to use a TensorFlow-trained model (response vs RAG context) in the supervisor aggregate; if score &lt; threshold, escalates. Env: `OPENAI_API_KEY`, `MCP_SERVER_URL` (required); `DEFAULT_MODEL`, `TOP_P`, `GUARDRAILS_ENABLED`, `WEAVIATE_*`, `USE_TF_INTENT`, `TF_INTENT_MODEL_PATH`, `USE_TF_FAITHFULNESS`, `TF_FAITHFULNESS_MODEL_PATH` (optional).
