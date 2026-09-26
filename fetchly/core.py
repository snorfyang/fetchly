"""fetchly core: fetch a URL to clean Markdown, extract links, search the web,
and summarise text.

All functions return plain JSON-serializable structures so an Agent can read
the result directly through either the CLI or the MCP tools.
"""
from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from typing import Any

import requests
import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as _md

__version__ = "0.2.0"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        f"fetchly/{__version__}"
    )
}

_SEARCH_HEADERS = {**HEADERS, "Accept-Language": "en-US,en;q=0.9"}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at",
    "from", "by", "on", "off", "for", "in", "out", "over", "under", "again",
    "further", "once", "here", "there", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should",
    "now", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing", "it", "its", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "them", "his",
    "her", "their", "my", "your", "our", "as", "to", "of", "with", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "up", "down", "亦", "的", "了", "是", "在", "和", "与",
    "或", "及", "之", "而", "为", "对", "就", "也", "被", "把", "这", "那",
}


def _abs(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _get(url: str, **kwargs: Any) -> requests.Response:
    """GET with one retry and a sane timeout."""
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 25)
    last: Exception | None = None
    for attempt in (1, 2):
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == 1:
                continue
    raise RuntimeError(f"GET {url} failed: {last}") from last


def fetch_url(url: str, max_chars: int = 40000) -> dict[str, Any]:
    """Fetch a URL and return clean Markdown plus title, metadata and links."""
    r = _get(url)

    # Pass raw bytes so trafilatura / bs4 can detect the real charset
    # (GBK/GB2312 pages would otherwise come back as mojibake).
    markdown = trafilatura.extract(
        r.content,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )

    meta = trafilatura.extract_metadata(r.content)
    title = meta.title if meta and meta.title else None
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
        "author": meta.author if meta and meta.author else None,
        "date": meta.date if meta and meta.date else None,
        "description": meta.description if meta and meta.description else None,
        "language": meta.language if meta and meta.language else None,
        "site": meta.sitename if meta and meta.sitename else None,
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


def _search_bing(query: str, limit: int) -> list[dict[str, str]]:
    r = _get(
        "https://www.bing.com/search",
        params={"q": query, "setmkt": "en-US", "cc": "US", "mkt": "en-US"},
        headers=_SEARCH_HEADERS,
    )
    soup = BeautifulSoup(r.content, "lxml")
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
                "source": "bing",
                "title": a.get_text(" ", strip=True),
                "url": href,
                "snippet": snip.get_text(" ", strip=True) if snip else "",
            }
        )
        if len(results) >= limit:
            break
    return results


def _search_wikipedia(query: str, limit: int) -> list[dict[str, str]]:
    r = _get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
        },
    )
    data = r.json()
    out: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        out.append(
            {
                "source": "wikipedia",
                "title": title,
                "url": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(title.replace(" ", "_")),
                "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
            }
        )
    return out


def search(query: str, limit: int = 8) -> dict[str, Any]:
    """Search the web (Bing) enriched with Wikipedia citations, cited per result."""
    wiki_quota = min(2, limit)
    bing_limit = limit - wiki_quota  # reserve room so English queries always get a Wikipedia citation

    results: list[dict[str, str]] = []
    try:
        results = _search_bing(query, bing_limit)
    except Exception:  # noqa: BLE001 - fall through to Wikipedia
        results = []

    try:
        seen = {r["url"] for r in results}
        for w in _search_wikipedia(query, limit):
            if w["url"] not in seen:
                results.append(w)
                if len(results) >= limit:
                    break
    except Exception:  # noqa: BLE001 - Bing results alone are still a valid answer
        pass

    return {"query": query, "results": results, "count": len(results)}


def research(query: str, limit: int = 3) -> dict[str, Any]:
    """Search then fetch the top results, returning snippets plus clean markdown."""
    hits = search(query, limit=limit)["results"]
    pages: list[dict[str, Any]] = []
    for h in hits:
        try:
            page = fetch_url(h["url"], max_chars=12000)
            pages.append(
                {
                    "title": h["title"],
                    "url": h["url"],
                    "markdown": page["markdown"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep going on any single failure
            pages.append({"title": h["title"], "url": h["url"], "error": str(exc)})
    return {"query": query, "results": hits, "pages": pages}


def _sentences(text: str) -> list[str]:
    # split on sentence boundaries, keep the boundary chars out
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 20]


def summarize(text: str, n: int = 5) -> dict[str, Any]:
    """Extractive summary: top-N most representative sentences, in order.

    No API key required — scores sentences by word frequency (tf, stopwords
    removed) and returns the highest-scoring ones in their original order.
    """
    sentences = _sentences(text)
    if not sentences:
        return {"sentences": [], "summary": text[:500]}

    def tokens(s: str) -> list[str]:
        return [
            w.lower()
            for w in re.findall(r"[\w\u4e00-\u9fff]+", s)
            if w.lower() not in _STOPWORDS and len(w) > 1
        ]

    freq: Counter[str] = Counter()
    for s in sentences:
        freq.update(tokens(s))

    def score(s: str) -> float:
        ws = tokens(s)
        if not ws:
            return 0.0
        return sum(freq[w] for w in ws) / len(ws)

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
    keep = sorted(ranked[:n])
    chosen = [sentences[i] for i in keep]
    return {"sentences": chosen, "summary": " ".join(chosen)}
