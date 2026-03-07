#!/home/gslee/llm-api-vault/venv/bin/python3
"""MCP Web Search Server using Camoufox.

Provides web_search and fetch_page tools via MCP protocol.

Run:
    python mcp_web_search_server.py
    # or with mcp cli:
    mcp run mcp_web_search_server.py
"""

from mcp.server.fastmcp import FastMCP

from web_search import fetch_page, format_results, search

mcp = FastMCP("web-search", description="Web search using Camoufox anti-detect browser")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo via a stealth browser.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        Formatted search results with titles, URLs, and snippets.
    """
    results = search(query, max_results=max_results)
    return format_results(results)


@mcp.tool()
def read_webpage(url: str) -> str:
    """Fetch and read the text content of a webpage.

    Args:
        url: The URL to fetch.

    Returns:
        The visible text content of the page.
    """
    text = fetch_page(url)
    # Truncate to avoid overwhelming context
    if len(text) > 15000:
        text = text[:15000] + "\n\n[... content truncated ...]"
    return text


if __name__ == "__main__":
    mcp.run(transport="stdio")
