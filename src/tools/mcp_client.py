"""MCP (Model Context Protocol) integration: load tools from MCP servers. Required. Uses langchain-mcp-adapters."""
import asyncio
import os
from typing import Any

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def load_mcp_tools_sync(server_url: str | None = None) -> list[Any]:
    """
    Load tools from an MCP server. Required. Set MCP_SERVER_URL env var (e.g. http://localhost:3000/mcp).
    Raises if MCP is not configured or fails to load.
    """
    if not MCP_AVAILABLE:
        raise RuntimeError("MCP is required. Install: pip install langchain-mcp-adapters")

    url = server_url or os.getenv("MCP_SERVER_URL", "").strip()
    if not url:
        raise ValueError("MCP_SERVER_URL is required. Set it in .env (e.g. MCP_SERVER_URL=http://localhost:3000/mcp)")

    async def _load() -> list[Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await load_mcp_tools(session)

    try:
        return asyncio.run(_load())
    except Exception as e:
        raise RuntimeError(f"MCP failed to load tools from {url}: {e}") from e


def get_tools_with_mcp(built_in_tools: list[Any]) -> list[Any]:
    """
    Return built-in tools merged with MCP tools. MCP tools are loaded from MCP_SERVER_URL (required).
    """
    tools = list(built_in_tools)
    mcp_tools = load_mcp_tools_sync()
    tools.extend(mcp_tools)
    return tools
