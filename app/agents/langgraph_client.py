"""
LangGraph SDK client for connecting to deployed agents.
"""
import os
from langgraph_sdk.client import get_client

from app.core.config import settings


def get_langgraph_client():
    """Get LangGraph SDK client configured from settings."""
    api_key = settings.LANGGRAPH_API_KEY or os.getenv("LANGGRAPH_API_KEY")
    api_url = settings.LANGGRAPH_API_URL or os.getenv("LANGGRAPH_API_URL")
    
    if not api_key:
        raise ValueError("LANGGRAPH_API_KEY must be set")
    if not api_url:
        raise ValueError("LANGGRAPH_API_URL must be set")
    
    client = get_client(
        url=api_url,
        api_key=api_key,
        headers={
            "X-Auth-Scheme": "langsmith-api-key",
        },
    )
    return client


def get_agent_id():
    """Get the agent ID from settings or environment."""
    return settings.LANGGRAPH_AGENT_ID or os.getenv("LANGGRAPH_AGENT_ID")

