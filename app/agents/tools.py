"""
Tools for agents.
"""
import os
from typing import Literal

from tavily import TavilyClient

from app.core.config import settings


# Initialize Tavily client
_tavily_api_key = settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY")
if not _tavily_api_key:
    raise ValueError("TAVILY_API_KEY must be set in environment variables or config")

tavily_client = TavilyClient(api_key=_tavily_api_key)


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

