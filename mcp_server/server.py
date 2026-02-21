"""
MCP server for this project. Register your tools here.

Run this server, then set MCP_SERVER_URL in .env (e.g. http://localhost:8000/mcp)
so the main app's MCP client can load these tools.

  python -m mcp_server
  # or: uv run python -m mcp_server

Requires: pip install mcp
"""
import os

from mcp.server.fastmcp import FastMCP

# Create the MCP server. Name appears in MCP clients.
mcp = FastMCP(
    "Agentic Production MCP",
    json_response=True,
)


# --- Register your tools below. The main app discovers them via MCP_SERVER_URL. ---


@mcp.tool()
def ping() -> str:
    """Health check: returns 'pong'. Use to verify the MCP server is reachable."""
    return "pong"


@mcp.tool()
def echo(message: str) -> str:
    """Echo back the given message. Example MCP tool."""
    return message


# Add more tools here, e.g.:
# @mcp.tool()
# def your_tool(arg: str) -> str:
#     """Description for the LLM."""
#     return "result"


if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)
