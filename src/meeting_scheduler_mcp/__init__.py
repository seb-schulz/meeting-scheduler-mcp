"""
Meeting Scheduler MCP package initialization.
"""

from fastmcp import FastMCP

from .tools import get_free_slots, save_draft_and_block_slot, search_emails

# Initialize FastMCP instance
mcp = FastMCP(
    name="Meeting Scheduler",
    instructions="A meeting scheduler that searches emails, manages calendars, and schedules meetings with full email threading support.",
)

# Register tools
mcp.tool(search_emails)
mcp.tool(get_free_slots)
mcp.tool(save_draft_and_block_slot)

__all__ = [
    "mcp",
    "search_emails",
    "get_free_slots",
    "save_draft_and_block_slot",
]
