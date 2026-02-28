# Issues List Tracker (Hypothetical)

This document tracks issues encountered during development and deployment of the Agentic Production Framework, along with their fixes. Written retrospectively for reference.

## Table of Contents

- [1. Hallucination & LLM Quality](#1-hallucination-llm-quality)
  - [Issue #001: Agents returning incorrect invoice details](#issue-001)
  - [Issue #002: Support agent escalating when not needed](#issue-002)
  - [Issue #003: Agent "making up" product names](#issue-003)
- [2. Performance — Cluster, Pods, Kubernetes](#2-performance-kubernetes)
  - [Issue #004: Supervisor pods OOMKilled under load](#issue-004)
  - [Issue #005: Agent pool pods CPU throttling](#issue-005)
  - [Issue #006: Kubernetes cluster node pool exhaustion](#issue-006)
  - [Issue #007: Slow pod startup (cold start)](#issue-007)
- [3. RAG Accuracy & Retrieval](#3-rag-accuracy-retrieval)
  - [Issue #008: RAG returning irrelevant chunks](#issue-008)
  - [Issue #009: RAG latency > 500ms](#issue-009)
  - [Issue #010: Conversation history RAG returning stale data](#issue-010)
- [4. LLM Latency & Time Delay](#4-llm-latency)
  - [Issue #011: LLM response time > 5s](#issue-011)
  - [Issue #012: Tool-calling loop adding 3–4s](#issue-012)
- [5. MCP & Tools](#5-mcp-tools)
  - [Issue #013: MCP connection failures at startup](#issue-013)
  - [Issue #014: MCP tools returning empty or errors](#issue-014)
- [6. Observability & Monitoring](#6-observability-monitoring)
  - [Issue #015: No visibility into hallucination rate](#issue-015)
  - [Issue #016: Missing correlation between infra and app metrics](#issue-016)
  - [Issue #027: Offline RAG evaluation with RAGAS (Enhancement)](#issue-027)
- [7. Session, State & Persistence](#7-session-state-persistence)
  - [Issue #017: Conversation state lost after pod restart](#issue-017)
  - [Issue #018: Duplicate messages in conversation history](#issue-018)
- [8. Scaling & Throughput](#8-scaling-throughput)
  - [Issue #019: Queue depth growing during peak](#issue-019)
- [9. Cost & Efficiency](#9-cost-efficiency)
  - [Issue #020: LLM token cost 2x budget](#issue-020)
- [10. Security & Auth](#10-security-auth)
  - [Issue #021: Session ID predictable](#issue-021)
- [11. API & Features](#11-api-features)
  - [Issue #022: Add GraphQL query API for conversation history (Enhancement)](#issue-022)
- [12. Optimization & Inference](#12-optimization-inference)
  - [Issue #023: LLM memory and cost too high (model quantization)](#issue-023)
  - [Issue #024: Inference throughput insufficient (dynamic batching)](#issue-024)
  - [Issue #025: High latency for repeated or similar queries (KV cache)](#issue-025)
  - [Issue #026: Need faster GPU inference (TensorRT-LLM on A100)](#issue-026)
- [Summary Table](#summary-table)

---

<a id="1-hallucination-llm-quality"></a>
## 1. Hallucination & LLM Quality

<a id="issue-001"></a>
### Issue #001: Agents returning incorrect invoice details

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-08 |
| **Severity** | High |

**Description:** Billing agent occasionally returned wrong invoice amounts or dates, despite correct RAG retrieval. Users reported discrepancies.

**Root cause:** LLM was inferring values instead of strictly using RAG context. No faithfulness check enforced.

**Fix / workaround:**
- Added faithfulness score (TFFaithfulnessScorer or LLM-as-judge) after each agent response in supervisor aggregate; threshold 0.8.
- If below threshold, response is blocked and user sees "Verifying details—please hold."
- Integrated Langfuse to log faithfulness scores and alert on drop.
- Updated agent prompts to include "Answer ONLY from the provided context. If unsure, say so."

---

<a id="issue-002"></a>
### Issue #002: Support agent escalating when not needed

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-01-15 |
| **Severity** | Medium |

**Description:** Support agent frequently set `needs_escalation=True` and created tickets even for simple FAQ questions that could be resolved from KB.

**Root cause:** Overly broad escalation logic (keyword-based: "escalat", "ticket") and low confidence threshold.

**Fix / workaround:**
- Tightened escalation logic: require both `needs_escalation=True` and `confidence < 0.7`.
- Added structured output (JSON) for agent: `{ "answer": "...", "escalate": true/false, "reason": "..." }`.
- Tuned confidence threshold to 0.65 for support; 0.75 for billing.
- Documented escalation criteria in system prompt.

---

<a id="issue-003"></a>
### Issue #003: Agent "making up" product names

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-12 |
| **Severity** | High |

**Description:** Agents sometimes referenced product names or SKUs not in the KB. Users complained of misleading information.

**Root cause:** No grounding enforcement; LLM extrapolated from similar products.

**Fix / workaround:**
- Added citation extraction: agent must cite source chunk ID for factual claims.
- Implemented post-response check: if product name in reply is not in RAG chunks, block and re-prompt.
- Expanded RAG retrieval `top_k` from 3 to 5 for product-related queries.
- Added de-hallucination agent for billing: second LLM pass validates product IDs against DB.

---

<a id="2-performance-kubernetes"></a>
## 2. Performance — Cluster, Pods, Kubernetes

<a id="issue-004"></a>
### Issue #004: Supervisor pods OOMKilled under load

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-02-20 |
| **Severity** | Critical |

**Description:** Supervisor pods restarted frequently during peak (10k+ concurrent users). Logs showed `OOMKilled`.

**Root cause:** Default memory limit (512Mi) insufficient for LangGraph checkpointer + message history. Long conversations consumed more memory.

**Fix / workaround:**
- Increased supervisor pod memory request/limit to 1Gi (request) and 2Gi (limit).
- Added HPA (Horizontal Pod Autoscaler) on memory utilization > 70%.
- Moved checkpointer to Redis (external) instead of in-memory to reduce pod memory.
- Set max conversation turns in state to 20; older turns truncated.

---

<a id="issue-005"></a>
### Issue #005: Agent pool pods CPU throttling

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-03-05 |
| **Severity** | Medium |

**Description:** Billing and Support agent pods showed high CPU throttling (`container_cpu_cfs_throttled_seconds_total`). Latency P99 increased from 2s to 5s.

**Root cause:** CPU request/limit too low (100m/200m). LLM calls + tool execution + RAG retrieval exceeded quota.

**Fix / workaround:**
- Raised CPU request to 500m and limit to 1000m for agent pods.
- Enabled burstable QoS for agent deployments.
- Split heavy RAG retrieval to async pre-fetch where possible.
- Scaled agent pool replicas from 5 to 10 per pool during peak hours (scheduled HPA).

---

<a id="issue-006"></a>
### Issue #006: Kubernetes cluster node pool exhaustion

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-03-18 |
| **Severity** | Critical |

**Description:** New pods stuck in `Pending`; events showed "0/X nodes available: insufficient memory."

**Root cause:** Cluster autoscaler not enabled; node pool fixed at 5 nodes. Black Friday traffic spike exhausted capacity.

**Fix / workaround:**
- Enabled cluster autoscaler with min 5, max 20 nodes.
- Added PodDisruptionBudget (PDB) for supervisor and agent pools to avoid eviction storms.
- Implemented priority classes: supervisor = high, agents = medium.
- Added alerting on pending pods > 2 for 5 minutes.

---

<a id="issue-007"></a>
### Issue #007: Slow pod startup (cold start)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-04-02 |
| **Severity** | Medium |

**Description:** First request after scaling up took 15–20s; subsequent requests < 2s. Users saw timeouts on first interaction.

**Root cause:** MCP client loads tools at agent init; LangChain + OpenAI client lazy load; container cold start.

**Fix / workaround:**
- Added readiness probe with initial delay 30s and period 10s; only route traffic when ready.
- Pre-warmed MCP connection in agent `__init__` (async init on first use, cached).
- Kept minimum 2 replicas per agent pool to avoid full scale-down.
- Documented "warm-up" script for pre-scaling before known peaks.

---

<a id="3-rag-accuracy-retrieval"></a>
## 3. RAG Accuracy & Retrieval

<a id="issue-008"></a>
### Issue #008: RAG returning irrelevant chunks

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-04-22 |
| **Severity** | High |

**Description:** Agents cited KB articles that did not answer the user question. Relevance score low in evals.

**Root cause:** Embedding model mismatch (indexed with `text-embedding-ada-002`, queried with different model). No metadata filtering.

**Fix / workaround:**
- Standardized on single embedding model (`text-embedding-3-small`) for index and query.
- Re-indexed KB with consistent chunking (512 tokens, overlap 50).
- Added metadata filters: `domain`, `product_line` passed from router to RAG.
- Introduced relevance score threshold: if top chunk score < 0.7, agent says "I couldn't find a direct answer" and suggests escalation.

---

<a id="issue-009"></a>
### Issue #009: RAG latency > 500ms

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-05-10 |
| **Severity** | Medium |

**Description:** RAG retrieval sometimes took 500–800ms, pushing P99 total latency above 3s target.

**Root cause:** Weaviate in different region; large index; no caching for repeated queries.

**Fix / work-around:**
- Co-located Weaviate in same region as agent pods.
- Added Redis cache for RAG results: key = hash(query + top_k + filters), TTL 5 min.
- Reduced `top_k` from 5 to 3 for non-critical paths.
- Async pre-fetch of likely intents based on router suggestion.

---

<a id="issue-010"></a>
### Issue #010: Conversation history RAG returning stale data

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-05-28 |
| **Severity** | Medium |

**Description:** Agents sometimes referred to old invoice IDs or issues from previous turns when user had moved on.

**Root cause:** History RAG used last N turns without recency weighting. Long sessions had diluted context.

**Fix / workaround:**
- Prioritized last 5 turns; older turns included only if semantically similar (when vector history RAG enabled).
- Added "current focus" extraction: last user message intent used to filter history.
- Truncated history to 10 turns max for prompt; beyond that, summarized by separate LLM pass.
- Session TTL set to 24h; beyond that, new session and no cross-session history.

---

<a id="4-llm-latency"></a>
## 4. LLM Latency & Time Delay

<a id="issue-011"></a>
### Issue #011: LLM response time > 5s

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-06-05 |
| **Severity** | High |

**Description:** Users reported slow replies. P99 LLM latency was 6–8s during peak.

**Root cause:** Using `gpt-4o` for all agents; model overload on OpenAI side; no streaming.

**Fix / workaround:**
- Switched default to `gpt-4o-mini` for Support and Billing; reserved `gpt-4o` for escalation only.
- Implemented streaming: flush partial response to user as soon as first tokens arrive.
- Added timeout (10s) and retry (1x) for LLM calls; on timeout, return "Please try again in a moment."
- Negotiated higher rate limits with OpenAI; added fallback to Azure OpenAI in same region.

---

<a id="issue-012"></a>
### Issue #012: Tool-calling loop adding 3–4s

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-06-20 |
| **Severity** | Medium |

**Description:** Agent responses with tool use took 6–8s vs 2–3s without tools.

**Root cause:** Sequential tool calls; each tool call = 1 LLM round-trip. Multiple tools invoked in series.

**Fix / workaround:**
- Parallelized independent tool calls (e.g., `look_up_invoice` + `get_refund_status` when both needed).
- Cached tool results: same `invoice_id` lookup within 5 min returned from cache.
- Reduced max tool iterations from 5 to 3; on limit, return best-effort response.
- Moved some MCP tools to sync HTTP where possible to avoid MCP round-trip overhead.

---

<a id="5-mcp-tools"></a>
## 5. MCP & Tools

<a id="issue-013"></a>
### Issue #013: MCP connection failures at startup

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-07-08 |
| **Severity** | Critical |

**Description:** API failed to start with "MCP failed to load tools: Connection refused."

**Root cause:** MCP server not running; `MCP_SERVER_URL` pointed to wrong port; no retry or fallback.

**Fix / workaround:**
- Added retry (3 attempts, 2s backoff) for MCP tool loading at startup.
- If MCP fails after retries, fail fast with clear error: "MCP_SERVER_URL unreachable. Start MCP server or check URL."
- Documented MCP server startup order in runbook.
- Added health check: `/health` returns 503 if MCP tools not loaded.

---

<a id="issue-014"></a>
### Issue #014: MCP tools returning empty or errors

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-07-25 |
| **Severity** | Medium |

**Description:** Agent invoked `look_up_invoice` but got empty or "Tool error" in some cases.

**Root cause:** MCP server timeout; invalid args passed from LLM; MCP server bug for edge cases.

**Fix / workaround:**
- Wrapped MCP tool calls in try/except; on error, return "I couldn't fetch that. Please try again or contact billing."
- Added input validation for tool args (e.g., `invoice_id` format) before calling MCP.
- Implemented circuit breaker: 3 consecutive MCP failures → mark MCP unhealthy, use only built-in tools for 2 min.
- Logged all MCP errors to Langfuse with tool name and args (PII redacted).

---

<a id="6-observability-monitoring"></a>
## 6. Observability & Monitoring

<a id="issue-015"></a>
### Issue #015: No visibility into hallucination rate

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-08-03 |
| **Severity** | Medium |

**Description:** Could not quantify how often agents hallucinated. Manual review not scalable.

**Root cause:** No scores attached to traces; Langfuse/LangSmith not integrated.

**Fix / workaround:**
- Integrated Langfuse; all LLM and agent spans sent with metadata.
- Added `faithfulness` and `confidence` scores to agent response spans.
- Built Langfuse dashboard: hallucination rate = % of traces with faithfulness < 0.8.
- Set alert: if hallucination rate > 5% over 1h, page on-call.

---

<a id="issue-016"></a>
### Issue #016: Missing correlation between infra and app metrics

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-08-19 |
| **Severity** | Low |

**Description:** Hard to link pod OOM or CPU spike to specific user sessions or agents.

**Root cause:** No shared `trace_id` or `session_id` between Prometheus and Langfuse.

**Fix / workaround:**
- Exported `session_id` and `agent_id` as Prometheus labels from app metrics.
- Added OpenTelemetry trace ID to log lines; Grafana dashboard joins logs + traces by trace_id.
- Created unified dashboard: pick session_id → see Langfuse trace + pod metrics + logs.

---

<a id="issue-027"></a>
### Issue #027: Offline RAG evaluation with RAGAS (Enhancement)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-10-15 |
| **Severity** | Low (enhancement) |

**Description:** Need a way to evaluate RAG quality offline (faithfulness, answer relevancy) on test sets or sampled production data, without adding latency to the request path.

**Fix / workaround:**
- Implemented **RAGAS** evaluation script: **`scripts/eval_ragas.py`**. Runs offline or in CI; consumes (user_input, retrieved_contexts, response, optional reference) samples; computes faithfulness and answer relevancy via RAGAS (LLM-based metrics).
- Added `ragas` to `requirements.txt`. Sample data: built-in in script or `scripts/sample_ragas_data.json`; custom data via `--data path/to/samples.json`; results via `--output results.json`.
- Documented in **Documentation/RAGAS_AND_FAITHFULNESS.md** (where RAGAS sits, how to run, relation to runtime faithfulness and observability). Architecture: **ARCHITECTURE_DESIGN.md** §7 (Implemented Code Artifacts) and §9 (Evals).

---

<a id="7-session-state-persistence"></a>
## 7. Session, State & Persistence

<a id="issue-017"></a>
### Issue #017: Conversation state lost after pod restart

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-09-02 |
| **Severity** | High |

**Description:** Users reported agent "forgetting" the conversation after a few minutes. Multi-turn context lost.

**Root cause:** In-memory checkpointer; Redis not used. Pod restart or scale-down wiped state.

**Fix / workaround:**
- Migrated LangGraph checkpointer to Redis (LangGraph Redis checkpointer).
- Verified Redis cluster in same region; persistence enabled (AOF).
- Added session TTL 24h in Redis; beyond that, new session.
- Documented Redis as critical dependency; added to runbook.

---

<a id="issue-018"></a>
### Issue #018: Duplicate messages in conversation history

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-09-22 |
| **Severity** | Low |

**Description:** ConversationStore sometimes had duplicate turns for same message. Agent saw repeated context.

**Root cause:** Race: API and supervisor both appended turns; idempotency key not used.

**Fix / workaround:**
- Use `(session_id, turn_index)` as idempotency key; skip append if already exists.
- Single writer: only API appends after supervisor returns; supervisor does not append.
- Added `append_turn_if_not_exists` in ConversationStore interface.

---

<a id="8-scaling-throughput"></a>
## 8. Scaling & Throughput

<a id="issue-019"></a>
### Issue #019: Queue depth growing during peak

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-10-10 |
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

<a id="issue-020"></a>
### Issue #020: LLM token cost 2x budget

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-10-28 |
| **Severity** | Medium |

**Description:** Monthly OpenAI bill exceeded forecast. Token usage high.

**Root cause:** Full conversation history in every prompt; no summarization; `gpt-4o` used for simple queries.

**Fix / workaround:**
- Truncated conversation history to last 10 turns; older summarized.
- Enforced model tiering: gpt-4o-mini for 80% of traffic; gpt-4o only for escalation.
- Cached RAG context for identical queries (same user, same session, same query within 2 min).
- Set token budget alerts; auto-block new sessions if daily spend > threshold.

---

<a id="10-security-auth"></a>
## 10. Security & Auth

<a id="issue-021"></a>
### Issue #021: Session ID predictable

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-11-12 |
| **Severity** | Medium |

**Description:** Security audit found session IDs could be guessed; risk of session hijack.

**Root cause:** Session IDs were UUIDv4 but derived from predictable inputs in some paths.

**Fix / workaround:**
- Use cryptographically secure UUID (uuid4) for all new sessions.
- Validate session_id format; reject invalid or suspicious patterns.
- Added rate limit per IP for session creation (10/min).
- Log session creation with IP; alert on anomalies.

---

<a id="11-api-features"></a>
## 11. API & Features

<a id="issue-022"></a>
### Issue #022: Add GraphQL query API for conversation history (Enhancement)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-12-05 |
| **Severity** | Low (enhancement) |

**Description:** Need a read-only API for conversation history so dashboards, admin UIs, or analytics can fetch session lists and full conversation turns without REST endpoints per use case.

**Implementation:**
- Added **GraphQL** API at `POST /graphql` using Strawberry (`strawberry-graphql[fastapi]`).
- Schema in `src/graphql/conversation_schema.py`: types `Turn`, `Conversation`, `SessionInfo`; queries `conversation(session_id, limit)` and `sessions(limit)`.
- Resolvers use shared `ConversationStore` (`get_history`, `list_sessions`); context injects store into GraphQL.
- Design doc updated: §5.5 Conversation History Query API (GraphQL), and §7 entrypoint row.

**Reference:** See `Documentation/ARCHITECTURE_DESIGN.md` §5.5 and §7.

---

<a id="12-optimization-inference"></a>
## 12. Optimization & Inference

<a id="issue-023"></a>
### Issue #023: LLM memory and cost too high (model quantization)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2025-12-12 |
| **Severity** | High |

**Description:** Self-hosted or edge LLM inference consumed too much memory per model instance; GPU nodes were expensive and limited how many replicas we could run.

**Root cause:** Models were loaded in full precision (16-bit FP16/BF16). No quantization; each instance required 2x model size in VRAM.

**Fix / workaround:**
- **Model quantization:** Migrated from 16-bit to **4-bit** using **AWQ** (Activation-aware Weight Quantization) and **LLM.int8** for sensitive layers where needed.
- Achieved **~75% memory reduction** per instance; same GPU can now run 4x more concurrent model replicas or larger batch sizes.
- Validated quality on support/billing evals; minimal accuracy drop for our use case. Documented quantization pipeline and calibration dataset in runbook.

---

<a id="issue-024"></a>
### Issue #024: Inference throughput insufficient (dynamic batching)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2026-01-08 |
| **Severity** | High |

**Description:** During peak, LLM inference could not keep up with request rate. Per-request latency was acceptable but total throughput (requests/sec) capped; queue depth grew.

**Root cause:** Static batching or single-request inference; GPU utilization was low when requests arrived unevenly.

**Fix / workaround:**
- Adopted **vLLM** with **continuous batching**: incoming requests are added to the batch as soon as slots free up; finished sequences leave the batch without waiting for the whole batch.
- Achieved **~4x throughput** vs previous static-batch setup at similar latency.
- Tuned max batch size and chunk size for our GPU (A100 80GB); added metrics for batch fill rate and GPU utilization.

---

<a id="issue-025"></a>
### Issue #025: High latency for repeated or similar queries (KV cache)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2026-01-22 |
| **Severity** | Medium |

**Description:** Users with repeated or similar prompts (e.g. same system prompt + RAG prefix, or retries) still paid full prefill cost every time. P99 latency for “warm” patterns was no better than cold.

**Root cause:** No reuse of key-value (KV) cache across requests; each request recomputed attention for the full context.

**Fix / workaround:**
- Enabled **prefix caching** (KV cache reuse) for common prefixes: system prompt, shared RAG context, and conversation history prefix where identical across requests.
- Integrated with vLLM/TensorRT-LLM prefix caching APIs; hashed prefix to decide reuse.
- Achieved **~60% latency reduction** for requests that shared long prefixes (e.g. same RAG doc block). Monitored cache hit rate and eviction in dashboards.

---

<a id="issue-026"></a>
### Issue #026: Need faster GPU inference (TensorRT-LLM on A100)

| Field | Details |
|-------|---------|
| **Status** | Resolved |
| **Date** | 2026-02-05 |
| **Severity** | High |

**Description:** Even with quantization and batching, baseline inference engine left GPU underutilized; we needed lower latency and higher tokens/sec for real-time chat.

**Root cause:** Generic inference stack (e.g. Hugging Face + PyTorch) not optimized for NVIDIA A100; kernel fusion and memory layout suboptimal.

**Fix / workaround:**
- Deployed **TensorRT-LLM** on **A100 GPUs** for production inference: compiled model with TensorRT-LLM for A100, enabling fused kernels, in-flight batching, and efficient memory use.
- Run inference in dedicated TensorRT-LLM service; API/supervisor call this service instead of loading the model in-app. Kept fallback to vLLM or OpenAI for non-GPU nodes.
- Documented build and deploy pipeline (model export → TensorRT-LLM build → container); added health checks and versioning for model updates.

---

<a id="summary-table"></a>
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
| 023 | Optimization | LLM memory/cost — model quantization (AWQ/LLM.int8, 4-bit) | High | Resolved |
| 024 | Optimization | Throughput — vLLM + continuous batching | High | Resolved |
| 025 | Optimization | Latency — KV cache / prefix caching for repeated queries | Medium | Resolved |
| 026 | Optimization | Inference engine — TensorRT-LLM on A100 GPUs | High | Resolved |
| 027 | Observability | Offline RAG evaluation with RAGAS (enhancement) | Low | Resolved |

---
