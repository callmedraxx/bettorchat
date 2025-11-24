"""
Agent creation and management.
"""
from deepagents import create_deep_agent

from app.agents.tools import internet_search
from app.agents.prompts import RESEARCH_INSTRUCTIONS


def create_research_agent():
    """Create a research agent with internet search capabilities."""
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=RESEARCH_INSTRUCTIONS
    )
    return agent


# Export the agent graph for LangGraph CLI
agent = create_research_agent()

