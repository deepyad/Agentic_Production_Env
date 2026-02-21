# MCP Server (in-repo)

This folder is the **MCP server** for the Agentic Production Framework. The main app only has an **MCP client** (`src/tools/mcp_client.py`); it connects to an MCP server at `MCP_SERVER_URL` and loads tools from it. This server is that place: **register your MCP tools here**.

## Quick start

1. **Install** the MCP SDK (if not already):
   ```bash
   pip install mcp
   ```

2. **Run the server** (default: `http://localhost:8000/mcp`):
   ```bash
   python -m mcp_server
   ```
   Or with env:
   ```bash
   set MCP_PORT=3000
   python -m mcp_server
   ```

3. **Point the main app** at it in `.env`:
   ```env
   MCP_SERVER_URL=http://localhost:8000/mcp
   ```
   (Use `http://localhost:3000/mcp` if you set `MCP_PORT=3000`.)

4. Start the main API; it will load tools from this server and merge them with built-in Support/Billing tools.

## Registering tools

- Edit **`mcp_server/server.py`**.
- Add tools with the `@mcp.tool()` decorator. Use clear docstrings (the LLM sees them).
- Restart the MCP server after changes.

Example:

```python
@mcp.tool()
def my_custom_tool(query: str, limit: int = 10) -> str:
    """Search internal docs by query. Use when the user asks about internal processes."""
    # your implementation
    return "result"
```

## Built-in tools vs MCP tools

| Where | What |
|-------|------|
| **Built-in (this repo)** | LangChain `@tool` in `src/tools/support_tools.py` and `src/tools/billing_tools.py`. No server; agents use them directly. |
| **MCP (this server)** | Tools defined here and exposed over MCP. The main app’s client connects to this server and merges these tools with the built-in ones. |

You can add tools either as **built-in** (in `support_tools.py` / `billing_tools.py`) or as **MCP tools** in this server. Use this server when you want a single, separate process that exposes tools (e.g. different language, or shared across multiple apps).
