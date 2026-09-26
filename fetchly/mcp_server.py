"""fetchly MCP server (stdio).

Exposes four tools over the Model Context Protocol so Claude, ChatGPT,
Cursor, Codex, etc. can call fetchly directly:

    fetch_url(url, max_chars)   -> {title, markdown, links, link_count, ...}
    search(query, limit)        -> {query, results, count}
    research(query, limit)      -> {query, results, pages}
    summarize(text, sentences)  -> {sentences, summary}
"""
from __future__ import annotations

from . import core


def run() -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("fetchly")

    @mcp.tool()
    def fetch_url(url: str, max_chars: int = 40000) -> dict:
        """Fetch a URL and return clean Markdown, its title, and extracted links."""
        return core.fetch_url(url, max_chars=max_chars)

    @mcp.tool()
    def search(query: str, limit: int = 8) -> list:
        """Search the web and return results with title, url and snippet (cited sources)."""
        return core.search(query, limit=limit)

    @mcp.tool()
    def research(query: str, limit: int = 3) -> dict:
        """Search the web then fetch the top pages, returning snippets plus clean Markdown."""
        return core.research(query, limit=limit)

    @mcp.tool()
    def summarize(text: str, sentences: int = 5) -> dict:
        """Return an extractive summary of text (top sentences by keyword frequency, in order)."""
        if text.startswith(("http://", "https://")):
            text = core.fetch_url(text, max_chars=30000)["markdown"]
        return core.summarize(text, n=sentences)

    mcp.run()


if __name__ == "__main__":
    run()
