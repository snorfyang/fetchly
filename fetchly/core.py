"""fetchly core: fetch a URL to clean Markdown, extract links, and search the web.

All functions return plain JSON-serializable structures so an Agent can read
the result directly through either the CLI or the MCP tools.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import requests
import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as _md

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 fetchly/0.1"
    )
}


def _abs(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def fetch_url(url: str, max_chars: int = 40000) -> dict[str, Any]:
    """Fetch a URL and return clean Markdown plus title and links."""
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()

    # Pass raw bytes so trafilatura / bs4 can detect the real charset
    # (GBK/GB2312 pages would otherwise come back as mojibake).
    markdown = trafilatura.extract(
        r.content,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )

    title = None
    meta = trafilatura.extract_metadata(r.content)
    if meta and meta.title:
        title = meta.title
    if not title:
        t = BeautifulSoup(r.content, "lxml").find("title")
        title = t.get_text(strip=True) if t else url

    if not markdown:
        markdown = _md(str(r.content, errors="replace"), heading_style="ATX") or ""

    if len(markdown) > max_chars:
        markdown = markdown[:max_chars] + "\n\n…[truncated by fetchly]"

    links = extract_links(r.content, url)

    return {
        "url": url,
        "title": title,
        "markdown": markdown,
        "links": links[:60],
        "link_count": len(links),
    }


def extract_links(html_bytes: bytes, base_url: str) -> list[dict[str, str]]:
    """Return absolute links with anchor text, de-duplicated."""
    soup = BeautifulSoup(html_bytes, "lxml")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = _abs(base_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        out.append({"url": abs_url, "text": a.get_text(" ", strip=True)[:200]})
    return out


SEARCH_HEADERS = {
    **HEADERS,
    "Accept-Language": "en-US,en;q=0.9",
}


def search(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Search the web (Bing HTML, en-US market) and return title/url/snippet."""
    r = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "setmkt": "en-US", "cc": "US", "mkt": "en-US"},
        headers=SEARCH_HEADERS,
        timeout=25,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    results: list[dict[str, str]] = []
    for res in soup.select("li.b_algo"):
        a = res.select_one("h2 a")
        if not a:
            continue
        href = a.get("href") or ""
        if not href.startswith("http"):
            continue
        snip = res.select_one(".b_caption p") or res.select_one("p")
        results.append(
            {
                "title": a.get_text(" ", strip=True),
                "url": href,
                "snippet": snip.get_text(" ", strip=True) if snip else "",
            }
        )
        if len(results) >= limit:
            break
    return results


def research(query: str, limit: int = 3) -> dict[str, Any]:
    """Search then fetch the top results, returning snippets plus clean markdown."""
    hits = search(query, limit=limit)
    pages: list[dict[str, Any]] = []
    for h in hits:
        try:
            page = fetch_url(h["url"], max_chars=12000)
            pages.append(
                {"title": h["title"], "url": h["url"], "markdown": page["markdown"]}
            )
        except Exception as exc:  # noqa: BLE001 - keep going on any single failure
            pages.append({"title": h["title"], "url": h["url"], "error": str(exc)})
    return {"query": query, "results": hits, "pages": pages}
