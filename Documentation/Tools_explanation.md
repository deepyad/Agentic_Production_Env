# Tools Flow Explanation

This document explains how tools are defined, loaded, and used by the Support and Billing agents—including the relationship between built-in tools, the MCP client, and the LLM.

---

## 1. Who Calls Whom

**The agents call the MCP client**, not the other way around.

When each agent is **created**, it:

1. Gets its **built-in** tools (from `support_tools.py` or `billing_tools.py`).
2. Calls **`get_tools_with_mcp(built_in)`**, which **inside** uses the MCP client to load MCP tools and merge them with `built_in`.
3. Keeps that **single combined list** and binds it to the LLM.

So: **agent init** → **get_tools_with_mcp(built_in)** → **mcp_client** is used inside that function to add MCP tools.

---

## 2. Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  APP STARTUP (e.g. api.py loads → build_supervisor() → create_supervisor_graph())  │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  create_support_agent() / create_billing_agent()                         │
│  → SupportAgent.__init__() or BillingAgent.__init__()                    │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
  built_in = get_support_tools()   (or get_billing_tools())
  → returns e.g. [search_knowledge_base, create_support_ticket]     (support)
  → or [look_up_invoice, get_refund_status, request_refund]         (billing)
         │
         ▼
  self.tools = get_tools_with_mcp(built_in)
         │
         │   ┌──────────────────────────────────────────────────────┐
         │   │  get_tools_with_mcp (mcp_client.py):                  │
         │   │    tools = list(built_in)                            │
         │   │    mcp_tools = load_mcp_tools_sync()  ◄── MCP client  │
         │   │         → connects to MCP_SERVER_URL                  │
         │   │         → loads tools from MCP server                  │
         │   │    tools.extend(mcp_tools)                            │
         │   │    return tools  (built-in + MCP in one list)         │
         │   └──────────────────────────────────────────────────────┘
         ▼
  self.llm = ChatOpenAI(...).bind_tools(self.tools)
  → LLM now "knows" all tools (built-in + MCP) for this agent
```

So:

- **Built-in tools** come from `support_tools.py` / `billing_tools.py`.
- **MCP tools** are loaded only inside **`get_tools_with_mcp()`** (which uses **`load_mcp_tools_sync()`** in `mcp_client.py`).
- The **agent** is the one that calls `get_tools_with_mcp(built_in)` and then uses the returned list as `self.tools` and passes it to **`bind_tools(self.tools)`**.

---

## 3. At Request Time (When a User Sends a Message)

```
User message → Supervisor → route to e.g. Support agent
                                    │
                                    ▼
                    Agent runs with messages + RAG context
                                    │
                                    ▼
                    LLM (with bind_tools(self.tools)) may return tool_calls
                                    │
                                    ▼
                    Agent loop: for each tool_call:
                      tool = tool_map[tool_name]   ← from self.tools (same list from init)
                      result = tool.invoke(args)
                    (no distinction here between "built-in" vs "MCP" – same list)
```

So at runtime the agent doesn't "call the MCP client again". It just uses **`self.tools`** (the list it built at init: built-in + MCP). That list was built **by** the agent **using** the MCP client inside **`get_tools_with_mcp()`**.

---

## 4. Where Tools Are Defined vs Registered

### Tool definitions (built-in)

| File | What's defined |
|------|-----------------|
| **`src/tools/support_tools.py`** | Support tools via `@tool`: e.g. KB search, create ticket. Returned as a list by **`get_support_tools()`**. |
| **`src/tools/billing_tools.py`** | Billing tools via `@tool`: e.g. invoice lookup, refund status/request. Returned by **`get_billing_tools()`**. |
| **`src/tools/mcp_client.py`** | MCP tools: **`load_mcp_tools_sync()`** loads tools from the MCP server; **`get_tools_with_mcp(built_in)`** merges `built_in` with those MCP tools. |

### Tool registration (binding to the LLM)

Registration happens in the **agent constructors**, when building the tool list and calling **`bind_tools(self.tools)`** on the LLM.

- **Support agent** — `src/agents/support.py`:  
  `built_in = get_support_tools()` → `self.tools = get_tools_with_mcp(built_in)` → `self.llm = ChatOpenAI(...).bind_tools(self.tools)`.

- **Billing agent** — `src/agents/billing.py`:  
  Same pattern with `get_billing_tools()`.

There is no other central "tool registry"; each agent registers its own combined list (built-in + MCP) via **`bind_tools(self.tools)`** in **`support.py`** and **`billing.py`**.

---

## 5. Short Summary

| Question | Answer |
|----------|--------|
| Are tools "first called in MCP client" and then used by agents? | No. The **agents** run first (at init). They get built-in tools, then call **`get_tools_with_mcp(built_in)`**, and **inside that** the MCP client is used to load MCP tools and merge. |
| Who drives the flow? | **Agents** (support/billing) drive it. They call `get_tools_with_mcp()`, which uses the MCP client to add MCP tools to their list. |
| When are MCP tools loaded? | Once per agent, when the agent is **created** (during supervisor graph build). |
| When are tools actually executed? | At **request time**, when the LLM returns tool_calls and the agent invokes the matching tool from **`self.tools`** (the same combined list from init). |

**Bottom line:** Agents own the tool list; they **use** the MCP client during init to **add** MCP tools to that list, then use the combined list for every request.
