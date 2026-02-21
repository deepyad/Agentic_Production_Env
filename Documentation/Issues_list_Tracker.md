# Issues List Tracker (Hypothetical)

This document tracks issues encountered during development and deployment of the Agentic Production Framework, along with their fixes. Written retrospectively for reference.

---

## 1. Hallucination & LLM Quality

### Issue #001: Agents returning incorrect invoice details

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-15 |
| **Severity** | High |

**Description:** Billing agent occasionally returned wrong invoice amounts or dates, despite correct RAG retrieval. Users reported discrepancies.

**Root cause:** LLM was inferring values instead of strictly using RAG context. No faithfulness check enforced.

**Fix / workaround:**
- Added faithfulness score (TFFaithfulnessScorer or LLM-as-judge) after each agent response in supervisor aggregate; threshold 0.8.
- If below threshold, response is blocked and user sees "Verifying details—please hold."
- Integrated Langfuse to log faithfulness scores and alert on drop.
- Updated agent prompts to include "Answer ONLY from the provided context. If unsure, say so."

---

### Issue #002: Support agent escalating when not needed

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-22 |
| **Severity** | Medium |

**Description:** Support agent frequently set `needs_escalation=True` and created tickets even for simple FAQ questions that could be resolved from KB.

**Root cause:** Overly broad escalation logic (keyword-based: "escalat", "ticket") and low confidence threshold.

**Fix / workaround:**
- Tightened escalation logic: require both `needs_escalation=True` and `confidence < 0.7`.
- Added structured output (JSON) for agent: `{ "answer": "...", "escalate": true/false, "reason": "..." }`.
- Tuned confidence threshold to 0.65 for support; 0.75 for billing.
- Documented escalation criteria in system prompt.

---

### Issue #003: Agent "making up" product names

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-01 |
| **Severity** | High |

**Description:** Agents sometimes referenced product names or SKUs not in the KB. Users complained of misleading information.

**Root cause:** No grounding enforcement; LLM extrapolated from similar products.

**Fix / workaround:**
- Added citation extraction: agent must cite source chunk ID for factual claims.
- Implemented post-response check: if product name in reply is not in RAG chunks, block and re-prompt.
- Expanded RAG retrieval `top_k` from 3 to 5 for product-related queries.
- Added de-hallucination agent for billing: second LLM pass validates product IDs against DB.

---

## 2. Performance — Cluster, Pods, Kubernetes

### Issue #004: Supervisor pods OOMKilled under load

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-18 |
| **Severity** | Critical |

**Description:** Supervisor pods restarted frequently during peak (10k+ concurrent users). Logs showed `OOMKilled`.

**Root cause:** Default memory limit (512Mi) insufficient for LangGraph checkpointer + message history. Long conversations consumed more memory.

**Fix / workaround:**
- Increased supervisor pod memory request/limit to 1Gi (request) and 2Gi (limit).
- Added HPA (Horizontal Pod Autoscaler) on memory utilization > 70%.
- Moved checkpointer to Redis (external) instead of in-memory to reduce pod memory.
- Set max conversation turns in state to 20; older turns truncated.

---

### Issue #005: Agent pool pods CPU throttling

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-25 |
| **Severity** | Medium |

**Description:** Billing and Support agent pods showed high CPU throttling (`container_cpu_cfs_throttled_seconds_total`). Latency P99 increased from 2s to 5s.

**Root cause:** CPU request/limit too low (100m/200m). LLM calls + tool execution + RAG retrieval exceeded quota.

**Fix / workaround:**
- Raised CPU request to 500m and limit to 1000m for agent pods.
- Enabled burstable QoS for agent deployments.
- Split heavy RAG retrieval to async pre-fetch where possible.
- Scaled agent pool replicas from 5 to 10 per pool during peak hours (scheduled HPA).

---

### Issue #006: Kubernetes cluster node pool exhaustion

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-05 |
| **Severity** | Critical |

**Description:** New pods stuck in `Pending`; events showed "0/X nodes available: insufficient memory."

**Root cause:** Cluster autoscaler not enabled; node pool fixed at 5 nodes. Black Friday traffic spike exhausted capacity.

**Fix / workaround:**
- Enabled cluster autoscaler with min 5, max 20 nodes.
- Added PodDisruptionBudget (PDB) for supervisor and agent pools to avoid eviction storms.
- Implemented priority classes: supervisor = high, agents = medium.
- Added alerting on pending pods > 2 for 5 minutes.

---

### Issue #007: Slow pod startup (cold start)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-28 |
| **Severity** | Medium |

**Description:** First request after scaling up took 15–20s; subsequent requests < 2s. Users saw timeouts on first interaction.

**Root cause:** MCP client loads tools at agent init; LangChain + OpenAI client lazy load; container cold start.

**Fix / workaround:**
- Added readiness probe with initial delay 30s and period 10s; only route traffic when ready.
- Pre-warmed MCP connection in agent `__init__` (async init on first use, cached).
- Kept minimum 2 replicas per agent pool to avoid full scale-down.
- Documented "warm-up" script for pre-scaling before known peaks.

---

## 3. RAG Accuracy & Retrieval

### Issue #008: RAG returning irrelevant chunks

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-12 |
| **Severity** | High |

**Description:** Agents cited KB articles that did not answer the user question. Relevance score low in evals.

**Root cause:** Embedding model mismatch (indexed with `text-embedding-ada-002`, queried with different model). No metadata filtering.

**Fix / workaround:**
- Standardized on single embedding model (`text-embedding-3-small`) for index and query.
- Re-indexed KB with consistent chunking (512 tokens, overlap 50).
- Added metadata filters: `domain`, `product_line` passed from router to RAG.
- Introduced relevance score threshold: if top chunk score < 0.7, agent says "I couldn't find a direct answer" and suggests escalation.

---

### Issue #009: RAG latency > 500ms

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-20 |
| **Severity** | Medium |

**Description:** RAG retrieval sometimes took 500–800ms, pushing P99 total latency above 3s target.

**Root cause:** Weaviate in different region; large index; no caching for repeated queries.

**Fix / work-around:**
- Co-located Weaviate in same region as agent pods.
- Added Redis cache for RAG results: key = hash(query + top_k + filters), TTL 5 min.
- Reduced `top_k` from 5 to 3 for non-critical paths.
- Async pre-fetch of likely intents based on router suggestion.

---

### Issue #010: Conversation history RAG returning stale data

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-10 |
| **Severity** | Medium |

**Description:** Agents sometimes referred to old invoice IDs or issues from previous turns when user had moved on.

**Root cause:** History RAG used last N turns without recency weighting. Long sessions had diluted context.

**Fix / workaround:**
- Prioritized last 5 turns; older turns included only if semantically similar (when vector history RAG enabled).
- Added "current focus" extraction: last user message intent used to filter history.
- Truncated history to 10 turns max for prompt; beyond that, summarized by separate LLM pass.
- Session TTL set to 24h; beyond that, new session and no cross-session history.

---

## 4. LLM Latency & Time Delay

### Issue #011: LLM response time > 5s

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-14 |
| **Severity** | High |

**Description:** Users reported slow replies. P99 LLM latency was 6–8s during peak.

**Root cause:** Using `gpt-4o` for all agents; model overload on OpenAI side; no streaming.

**Fix / workaround:**
- Switched default to `gpt-4o-mini` for Support and Billing; reserved `gpt-4o` for escalation only.
- Implemented streaming: flush partial response to user as soon as first tokens arrive.
- Added timeout (10s) and retry (1x) for LLM calls; on timeout, return "Please try again in a moment."
- Negotiated higher rate limits with OpenAI; added fallback to Azure OpenAI in same region.

---

### Issue #012: Tool-calling loop adding 3–4s

| Field | Details |
|-------|--------- |
| **Status** | Resolved |
| **Date** | 2025-01-26 |
| **Severity** | Medium |

**Description:** Agent responses with tool use took 6–8s vs 2–3s without tools.

**Root cause:** Sequential tool calls; each tool call = 1 LLM round-trip. Multiple tools invoked in series.

**Fix / workaround:**
- Parallelized independent tool calls (e.g., `look_up_invoice` + `get_refund_status` when both needed).
- Cached tool results: same `invoice_id` lookup within 5 min returned from cache.
- Reduced max tool iterations from 5 to 3; on limit, return best-effort response.
- Moved some MCP tools to sync HTTP where possible to avoid MCP round-trip overhead.

---

## 5. MCP & Tools

### Issue #013: MCP connection failures at startup

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-10 |
| **Severity** | Critical |

**Description:** API failed to start with "MCP failed to load tools: Connection refused."

**Root cause:** MCP server not running; `MCP_SERVER_URL` pointed to wrong port; no retry or fallback.

**Fix / workaround:**
- Added retry (3 attempts, 2s backoff) for MCP tool loading at startup.
- If MCP fails after retries, fail fast with clear error: "MCP_SERVER_URL unreachable. Start MCP server or check URL."
- Documented MCP server startup order in runbook.
- Added health check: `/health` returns 503 if MCP tools not loaded.

---

### Issue #014: MCP tools returning empty or errors

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-30 |
| **Severity** | Medium |

**Description:** Agent invoked `look_up_invoice` but got empty or "Tool error" in some cases.

**Root cause:** MCP server timeout; invalid args passed from LLM; MCP server bug for edge cases.

**Fix / workaround:**
- Wrapped MCP tool calls in try/except; on error, return "I couldn't fetch that. Please try again or contact billing."
- Added input validation for tool args (e.g., `invoice_id` format) before calling MCP.
- Implemented circuit breaker: 3 consecutive MCP failures → mark MCP unhealthy, use only built-in tools for 2 min.
- Logged all MCP errors to Langfuse with tool name and args (PII redacted).

---

## 6. Observability & Monitoring

### Issue #015: No visibility into hallucination rate

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-08 |
| **Severity** | Medium |

**Description:** Could not quantify how often agents hallucinated. Manual review not scalable.

**Root cause:** No scores attached to traces; Langfuse/LangSmith not integrated.

**Fix / workaround:**
- Integrated Langfuse; all LLM and agent spans sent with metadata.
- Added `faithfulness` and `confidence` scores to agent response spans.
- Built Langfuse dashboard: hallucination rate = % of traces with faithfulness < 0.8.
- Set alert: if hallucination rate > 5% over 1h, page on-call.

---

### Issue #016: Missing correlation between infra and app metrics

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-08 |
| **Severity** | Low |

**Description:** Hard to link pod OOM or CPU spike to specific user sessions or agents.

**Root cause:** No shared `trace_id` or `session_id` between Prometheus and Langfuse.

**Fix / workaround:**
- Exported `session_id` and `agent_id` as Prometheus labels from app metrics.
- Added OpenTelemetry trace ID to log lines; Grafana dashboard joins logs + traces by trace_id.
- Created unified dashboard: pick session_id → see Langfuse trace + pod metrics + logs.

---

## 7. Session, State & Persistence

### Issue #017: Conversation state lost after pod restart

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-11 |
| **Severity** | High |

**Description:** Users reported agent "forgetting" the conversation after a few minutes. Multi-turn context lost.

**Root cause:** In-memory checkpointer; Redis not used. Pod restart or scale-down wiped state.

**Fix / workaround:**
- Migrated LangGraph checkpointer to Redis (LangGraph Redis checkpointer).
- Verified Redis cluster in same region; persistence enabled (AOF).
- Added session TTL 24h in Redis; beyond that, new session.
- Documented Redis as critical dependency; added to runbook.

---

### Issue #018: Duplicate messages in conversation history

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-12 |
| **Severity** | Low |

**Description:** ConversationStore sometimes had duplicate turns for same message. Agent saw repeated context.

**Root cause:** Race: API and supervisor both appended turns; idempotency key not used.

**Fix / workaround:**
- Use `(session_id, turn_index)` as idempotency key; skip append if already exists.
- Single writer: only API appends after supervisor returns; supervisor does not append.
- Added `append_turn_if_not_exists` in ConversationStore interface.

---

## 8. Scaling & Throughput

### Issue #019: Queue depth growing during peak

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-02 |
| **Severity** | High |

**Description:** Kafka queue (gateway → supervisor) depth grew to 10k+; latency increased to 30s+.

**Root cause:** Supervisor and agent pools did not scale fast enough; HPA based on CPU lagged behind queue growth.

**Fix / workaround:**
- Added queue depth as HPA metric: scale up when depth > 100.
- Increased max replicas for supervisor from 20 to 50.
- Implemented backpressure: gateway returns 503 when queue depth > 500.
- Scheduled scale-up 30 min before known peaks (e.g., product launch).

---

## 9. Cost & Efficiency

### Issue #020: LLM token cost 2x budget

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-24 |
| **Severity** | Medium |

**Description:** Monthly OpenAI bill exceeded forecast. Token usage high.

**Root cause:** Full conversation history in every prompt; no summarization; `gpt-4o` used for simple queries.

**Fix / workaround:**
- Truncated conversation history to last 10 turns; older summarized.
- Enforced model tiering: gpt-4o-mini for 80% of traffic; gpt-4o only for escalation.
- Cached RAG context for identical queries (same user, same session, same query within 2 min).
- Set token budget alerts; auto-block new sessions if daily spend > threshold.

---

## 10. Security & Auth

### Issue #021: Session ID predictable

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-14 |
| **Severity** | Medium |

**Description:** Security audit found session IDs could be guessed; risk of session hijack.

**Root cause:** Session IDs were UUIDv4 but derived from predictable inputs in some paths.

**Fix / workaround:**
- Use cryptographically secure UUID (uuid4) for all new sessions.
- Validate session_id format; reject invalid or suspicious patterns.
- Added rate limit per IP for session creation (10/min).
- Log session creation with IP; alert on anomalies.

---

## 11. API & Features

### Issue #022: Add GraphQL query API for conversation history (Enhancement)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-20 |
| **Severity** | Low (enhancement) |

**Description:** Need a read-only API for conversation history so dashboards, admin UIs, or analytics can fetch session lists and full conversation turns without REST endpoints per use case.

**Implementation:**
- Added **GraphQL** API at `POST /graphql` using Strawberry (`strawberry-graphql[fastapi]`).
- Schema in `src/graphql/conversation_schema.py`: types `Turn`, `Conversation`, `SessionInfo`; queries `conversation(session_id, limit)` and `sessions(limit)`.
- Resolvers use shared `ConversationStore` (`get_history`, `list_sessions`); context injects store into GraphQL.
- Design doc updated: §5.5 Conversation History Query API (GraphQL), and §7 entrypoint row.

**Reference:** See `Documentation/ARCHITECTURE_DESIGN.md` §5.5 and §7.

---

## Summary Table

| # | Category | Issue | Severity | Status |
|---|----------|-------|----------|--------|
| 001 | Hallucination | Incorrect invoice details | High | Resolved |
| 002 | Hallucination | Over-escalation | Medium | Resolved |
| 003 | Hallucination | Made-up product names | High | Resolved |
| 004 | K8s/Perf | Supervisor OOMKilled | Critical | Resolved |
| 005 | K8s/Perf | CPU throttling | Medium | Resolved |
| 006 | K8s | Node exhaustion | Critical | Resolved |
| 007 | K8s/Perf | Slow pod startup | Medium | Resolved |
| 008 | RAG | Irrelevant chunks | High | Resolved |
| 009 | RAG | RAG latency high | Medium | Resolved |
| 010 | RAG | Stale history | Medium | Resolved |
| 011 | LLM | LLM latency > 5s | High | Resolved |
| 012 | LLM | Tool loop slow | Medium | Resolved |
| 013 | MCP | MCP connection failure | Critical | Resolved |
| 014 | MCP | MCP tool errors | Medium | Resolved |
| 015 | Observability | No hallucination metrics | Medium | Resolved |
| 016 | Observability | Missing trace correlation | Low | Resolved |
| 017 | State | State lost on restart | High | Resolved |
| 018 | State | Duplicate messages | Low | Resolved |
| 019 | Scaling | Queue depth growth | High | Resolved |
| 020 | Cost | Token overrun | Medium | Resolved |
| 021 | Security | Predictable session ID | Medium | Resolved |
| 022 | API/Features | GraphQL query API for conversation history | Low (enhancement) | Resolved |

---

*Document is hypothetical and for reference. Adjust fixes based on actual environment and constraints.*
