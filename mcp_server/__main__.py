# Run the MCP server when executing: python -m mcp_server
from mcp_server.server import mcp
import os

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)
