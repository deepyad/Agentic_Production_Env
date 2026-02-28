# Agentic Production Framework

LangGraph + LLM multi-agent framework for chatbot-style customer support at scale. See `ARCHITECTURE_DESIGN.md` for the full design.

## Environment

**Use this conda env only:** `D:\MyDrive\Technology\AnacondaInstallation\env\genai_env`  
(e.g. `conda activate D:\MyDrive\Technology\AnacondaInstallation\env\genai_env` before running or installing).

## Quick Start

```bash
# Activate conda env (see Environment above), then:
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

- **GET /health** — Health check (when AgentOps enabled: agent circuit states, MCP status)
- **POST /chat** — Send a message, get a reply
- **GET /graphql** — GraphQL for conversation history (e.g. `conversation(session_id, limit)`, `sessions(limit)`)
- **GET /hitl/pending** — Pending escalations (sessions waiting for a human; when `HITL_HANDLER=ticket`)
- **POST /hitl/pending/{session_id}/clear** — Mark a session as picked up by a human

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
├── api.py              # FastAPI entrypoint (chat, health, graphql, hitl/pending)
├── config.py           # Configuration
├── router.py           # Session router (intent → agent pools)
├── registry.py         # Agent registry
├── supervisor.py       # LangGraph supervisor graph
├── agent_ops/          # Circuit breaker, health (optional)
├── hitl/               # Human-in-the-loop: escalation handlers (stub, ticket, email)
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

Input/output guardrails block off-topic, policy-violating, and prompt-injection content. Enabled by default (`GUARDRAILS_ENABLED=true`). **Runtime guardrails** run on **every user request** in production: `guard_input` on the user message before the agent, `guard_output` on the agent reply. Use `SimpleGuardrailService` (keyword-based) or plug in a third-party implementation (Guardrails AI, LLM Guard — see ARCHITECTURE_DESIGN). **Giskard** is for **CI/scanning only** (finds vulnerabilities before release); it does not check live traffic. For continuous protection in production, use runtime guardrails; for pre-release checks, add Giskard to CI.

## Router Intent

Default: **keyword-based** mapping. Set `USE_TF_INTENT=true` and install `tensorflow` to use a small Keras intent classifier (trains from synthetic data or load from `TF_INTENT_MODEL_PATH`).

- **billing** — invoice, bill, payment, refund
- **tech** — tech, error, bug, install, troubleshoot
- **escalation** — human, agent, escalate, speak to someone
- **support** — default

## HITL (human-in-the-loop)

When the supervisor escalates (low faithfulness score or agent-requested), the **escalate** node calls a HITL handler so the system can create tickets or notify humans. Module: `src/hitl/` (stub, ticket, email handlers). Config: `HITL_ENABLED` (default true), `HITL_HANDLER` (stub \| ticket \| email; default ticket), `HITL_EMAIL_TO`. With `HITL_HANDLER=ticket`, **GET /hitl/pending** lists pending escalations; **POST /hitl/pending/{session_id}/clear** marks a session as picked up. See `ARCHITECTURE_DESIGN.md` and `CODE_WALKTHROUGH.md` §3.20.

**Infra:** Docker and Kubernetes assets are in `infra/` (Dockerfile, namespace, deployment, service, HPA, scripts). See `infra/README.md`.

Replace router and RAG stubs with Weaviate in production (set `WEAVIATE_URL` and optionally use `WeaviateRAGService`). **Intent router:** default is keyword-based; set `USE_TF_INTENT=true` (and install `tensorflow`) to use a small Keras intent classifier. **Faithfulness scoring:** set `USE_TF_FAITHFULNESS=true` to use a TensorFlow-trained model (response vs RAG context) in the supervisor aggregate; if score &lt; threshold, escalates to HITL. **HITL:** `HITL_ENABLED`, `HITL_HANDLER` (stub \| ticket \| email), `HITL_EMAIL_TO`. **Inference backend:** default is OpenAI (`INFERENCE_BACKEND=openai`). For self-hosted (vLLM, TensorRT-LLM, or any OpenAI-compatible server), set `INFERENCE_BACKEND=self_hosted` and `INFERENCE_URL=http://your-server:8000`; optional `INFERENCE_API_KEY`. See `src/inference/backend.py`. **RAG evaluation (RAGAS):** offline/CI only — `python scripts/eval_ragas.py` (see `Observability_Details.md` and `ARCHITECTURE_DESIGN.md` §7, §9).

**Observability (Langfuse):** Set `LANGFUSE_SECRET_KEY` (and `LANGFUSE_PUBLIC_KEY`, optional `LANGFUSE_BASE_URL`) to enable tracing and faithfulness scores per request. See `Observability_Details.md` §7.

Env: `OPENAI_API_KEY`, `MCP_SERVER_URL` (required); `DEFAULT_MODEL`, `TOP_P`, `GUARDRAILS_ENABLED`, `WEAVIATE_*`, `USE_TF_INTENT`, `TF_INTENT_MODEL_PATH`, `USE_TF_FAITHFULNESS`, `TF_FAITHFULNESS_MODEL_PATH`, `HITL_*`, `INFERENCE_BACKEND`, `INFERENCE_URL`, `INFERENCE_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL` (optional).
