"""
Web search tools for agents.
"""
import os
from typing import Literal
from langchain.tools import tool

from tavily import TavilyClient
from app.core.config import settings


# Initialize Tavily client (optional - only if API key is available)
_tavily_api_key = settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY")
tavily_client = None
if _tavily_api_key:
    try:
        tavily_client = TavilyClient(api_key=_tavily_api_key)
    except Exception:
        tavily_client = None


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
    if not tavily_client:
        return f"Web search is not available. TAVILY_API_KEY must be set in environment variables to use this feature. Your query was: {query}"
    
    try:
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
    except Exception as e:
        return f"Error performing web search: {str(e)}"

