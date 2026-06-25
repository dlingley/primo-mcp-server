import os
import sys


def main() -> None:
    """Entry point for the purduelibrary-mcp-server command."""
    from purduelibrary_mcp_server.server import mcp

    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if len(sys.argv) > 1 and sys.argv[1] in ("sse", "stdio"):
        transport = sys.argv[1]

    if transport == "sse":
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8000"))
        print(f"Starting MCP server on sse transport at http://{host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")
