#!/bin/bash
# Script to run the MCP server

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set working directory to project root
cd "$(dirname "$0")"

# Run the MCP server
python -m app.mcp_server

