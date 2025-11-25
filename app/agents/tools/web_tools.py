"""
Web search tools for agents.
"""
import os
from typing import Literal
from langchain.tools import tool

from tavily import TavilyClient
from app.core.config import settings


# Initialize Tavily client
_tavily_api_key = settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY")
if not _tavily_api_key:
    raise ValueError("TAVILY_API_KEY must be set in environment variables or config")

tavily_client = TavilyClient(api_key=_tavily_api_key)


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> str:
    """Run a web search using Tavily.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        topic: Topic category (general, news, finance)
        include_raw_content: Whether to include raw content in results
    
    Returns:
        Search results as formatted string
    """
    results = tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
    
    # Format results
    if isinstance(results, dict):
        formatted = []
        formatted.append(f"Search results for: {query}\n")
        for i, result in enumerate(results.get("results", []), 1):
            formatted.append(f"{i}. {result.get('title', 'No title')}")
            formatted.append(f"   URL: {result.get('url', 'No URL')}")
            formatted.append(f"   {result.get('content', 'No content')}\n")
        return "\n".join(formatted)
    
    return str(results)

