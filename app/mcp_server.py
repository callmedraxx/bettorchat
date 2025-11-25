"""
MCP Server for Sports Betting Tools.

This server exposes betting tools via the Model Context Protocol (MCP).
Run with: python -m app.mcp_server

To use with Claude Desktop or other MCP clients, configure the server in your MCP settings.
"""
import asyncio
import sys
from typing import Any, Sequence
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from app.agents.tools.betting_tools import (
    fetch_live_odds,
    fetch_player_props,
    fetch_live_game_stats,
    fetch_injury_reports,
    detect_arbitrage_opportunities,
    fetch_futures,
    fetch_grader,
    fetch_historical_odds,
    image_to_bet_analysis,
    generate_bet_deep_link,
    read_url_content,
    detect_user_location,
    fetch_available_sports,
    fetch_available_leagues,
    fetch_available_markets,
    fetch_available_sportsbooks,
)


# Create MCP server instance
server = Server("sports-betting-tools")


def langchain_tool_to_mcp_tool(tool) -> Tool:
    """Convert a LangChain tool to an MCP Tool."""
    # Get tool schema
    tool_schema = {}
    if hasattr(tool, 'args_schema') and tool.args_schema:
        tool_schema = tool.args_schema.schema()
    
    # Extract properties and required fields
    properties = tool_schema.get("properties", {})
    required = tool_schema.get("required", [])
    
    return Tool(
        name=tool.name,
        description=tool.description,
        inputSchema={
            "type": "object",
            "properties": properties,
            "required": required,
        }
    )


# Register all betting tools
betting_tools = [
    fetch_live_odds,
    fetch_player_props,
    fetch_live_game_stats,
    fetch_injury_reports,
    detect_arbitrage_opportunities,
    fetch_futures,
    fetch_grader,
    fetch_historical_odds,
    image_to_bet_analysis,
    generate_bet_deep_link,
    read_url_content,
    detect_user_location,
    fetch_available_sports,
    fetch_available_leagues,
    fetch_available_markets,
    fetch_available_sportsbooks,
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [langchain_tool_to_mcp_tool(tool) for tool in betting_tools]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Call a tool by name with arguments."""
    # Find the tool
    tool_map = {tool.name: tool for tool in betting_tools}
    
    if name not in tool_map:
        raise ValueError(f"Tool {name} not found")
    
    tool = tool_map[name]
    
    # Invoke the tool
    try:
        result = tool.invoke(arguments)
        return [TextContent(type="text", text=str(result))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
