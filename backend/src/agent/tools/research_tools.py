"""Ordinary tools available to declarative research subagents."""

import os

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web when a configured web-search provider is available."""
    if not os.getenv("WEB_SEARCH_PROVIDER_KEY"):
        return "Web search is not configured: WEB_SEARCH_PROVIDER_KEY is required."
    return "Web search provider integration is not configured for this deployment."
