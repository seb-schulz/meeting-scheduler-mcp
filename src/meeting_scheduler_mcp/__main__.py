"""
Entry point for the meeting scheduler MCP server.
"""

import logging

from . import mcp

logger = logging.getLogger(__name__)


def main():
    """Starts the server for local development."""
    logger.info("Server running at http://0.0.0.0:8000")

    # Start the FastMCP server with HTTP transport
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
