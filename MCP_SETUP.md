# MCP Server Setup Guide

This guide explains how to set up and use the MCP (Model Context Protocol) server for sports betting tools.

## What is MCP?

MCP (Model Context Protocol) is a protocol that allows AI applications to access external tools and data sources. Our MCP server exposes all the sports betting tools (OpticOdds API wrappers) so they can be used by MCP-compatible clients like Claude Desktop.

## Installation

1. **Install the MCP package:**
   ```bash
   pip install mcp
   ```

2. **Set up environment variables:**
   Make sure you have your OpticOdds API key set:
   ```bash
   export OPTICODDS_API_KEY="your-api-key"
   ```

## Running the MCP Server

### Option 1: Direct Python execution
```bash
python -m app.mcp_server
```

### Option 2: Using the script
```bash
python app/mcp_server.py
```

The server will run on stdio (standard input/output), which is the standard way MCP servers communicate.

## Configuring Claude Desktop

To use this MCP server with Claude Desktop:

1. **Find your Claude Desktop config file:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`

2. **Add the MCP server configuration:**
   ```json
   {
     "mcpServers": {
       "sports-betting-tools": {
         "command": "python",
         "args": [
           "-m",
           "app.mcp_server"
         ],
         "cwd": "/path/to/your/project"
       }
     }
   }
   ```

   Replace `/path/to/your/project` with the actual path to your project directory.

3. **Restart Claude Desktop** for the changes to take effect.

## Available Tools

The MCP server exposes the following tools:

- `fetch_live_odds` - Get live betting odds for fixtures
- `fetch_player_props` - Get player proposition odds
- `fetch_live_game_stats` - Get live in-game statistics
- `fetch_injury_reports` - Get current injury reports
- `detect_arbitrage_opportunities` - Find arbitrage opportunities
- `fetch_futures` - Get futures markets and odds
- `fetch_grader` - Get bet settlement/grading information
- `fetch_historical_odds` - Get historical odds data
- `image_to_bet_analysis` - Analyze betting images
- `generate_bet_deep_link` - Generate deep links to sportsbooks
- `read_url_content` - Read content from URLs

## Testing the Server

You can test the MCP server using the MCP Inspector or by connecting it to Claude Desktop and asking Claude to use the tools.

## Troubleshooting

1. **Server won't start:**
   - Make sure `OPTICODDS_API_KEY` is set
   - Check that all dependencies are installed: `pip install -r requirements.txt`

2. **Tools not appearing in Claude Desktop:**
   - Verify the config file path is correct
   - Check that the `cwd` path is absolute and correct
   - Restart Claude Desktop after making config changes

3. **Tool execution errors:**
   - Check that your OpticOdds API key is valid
   - Verify network connectivity
   - Check the server logs for detailed error messages

## Development

To modify the MCP server:

1. Edit `app/mcp_server.py`
2. Add or remove tools from the `betting_tools` list
3. Restart the server

The server uses stdio for communication, so it's designed to be run as a subprocess by MCP clients.

