"""Web search module using Camoufox (anti-detect Firefox browser).

Scrapes DuckDuckGo search results using a stealth browser to avoid bot detection.
"""

import re
from urllib.parse import parse_qs, quote_plus, urlparse

from camoufox.sync_api import Camoufox


def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web via DuckDuckGo using Camoufox.

    Returns a list of dicts with keys: title, url, snippet.
    """
    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    results = []

    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # DuckDuckGo Lite uses a table-based layout
        # Try the lite results first, fall back to html layout
        rows = page.query_selector_all("table:last-of-type tr")
        current = {}
        for row in rows:
            link = row.query_selector("a.result-link")
            snippet_el = row.query_selector("td.result-snippet")

            if link:
                if current.get("title"):
                    results.append(current)
                    if len(results) >= max_results:
                        break
                raw_url = link.get_attribute("href") or ""
                # Extract real URL from DuckDuckGo redirect
                parsed = urlparse(raw_url)
                uddg = parse_qs(parsed.query).get("uddg")
                clean_url = uddg[0] if uddg else raw_url.lstrip("/")
                current = {
                    "title": link.inner_text().strip(),
                    "url": clean_url,
                    "snippet": "",
                }
            elif snippet_el and current.get("title"):
                current["snippet"] = snippet_el.inner_text().strip()

        if current.get("title") and len(results) < max_results:
            results.append(current)

    return results


def fetch_page(url: str, timeout: int = 30000) -> str:
    """Fetch a page's text content using Camoufox.

    Returns the visible text content of the page.
    """
    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        page.goto(url, timeout=timeout)
        page.wait_for_load_state("domcontentloaded")
        text = page.inner_text("body")
    return text


def format_results(results: list[dict]) -> str:
    """Format search results as readable text for injection into chat context."""
    if not results:
        return "No search results found."
    lines = ["Web search results:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "Python web scraping 2025"
    print(f"Searching: {query}\n")
    results = search(query)
    print(format_results(results))
