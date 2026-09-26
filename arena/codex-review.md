# codex-cli review (gpt-6-sol)

OpenAI Codex v0.155.1
--------
workdir: /Users/snorf/projects/sharednet
model: gpt-6-sol
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: medium
reasoning summaries: none
session id: 01a0dcf2-f0cd-78f0-8665-b3d4b6c4ec1d
--------
user
Review the fetchly project for correctness, bugs, security issues, and missed edge cases. It is an agent-callable web service (fetch/search/research/summarize) with a CLI, MCP server, HTTP API, a SharedOS permission-gated variant, and Arena delivery scripts. Other agents will call it live in a competition, so prioritize anything that would break under real use, leak a token, or fail to deliver. Focus on:
- fetchly/core.py (encoding, retries, search backends, summarize)
- fetchly/cli.py, fetchly/mcp_server.py, fetchly/serve.py
- sharedos/index.js, sharedos/lib/tools.js, sharedos/lib/runner.js
- arena/deliver.py, arena/agent.py
Lead with concrete file:line findings ranked by severity. Be specific and concise.
exec
/bin/zsh -lc 'pwd; git status --short; find .. -name AGENTS.md -o -name AGENTS.override.md; ls' in /Users/snorf/projects/sharednet
 succeeded in 6316ms:
../moonbitlings/.mooncakes/moonbitlang/async/AGENTS.md
../moonbitlings/AGENTS.md
../kaggle-kb/AGENTS.md
../moonupgradeguard/.mooncakes/moonbitlang/async/AGENTS.md
../moonupgradeguard/AGENTS.md
../neurogolf/data/external/github-refresh-20260715/minseongs/AGENTS.md
../to_mcq/AGENTS.md
../smolagents/AGENTS.md
../kaggle-skills/AGENTS.md
../kaggriculture/kits/kit/AGENTS.md
../moonmock/.mooncakes/moonbitlang/async/AGENTS.md
../cs336/assignment1-basics/AGENTS.md
README.md
arena
fetchly
fetchly.egg-info
pyproject.toml
sharedos
tests

exec
/bin/zsh -lc 'wc -l fetchly/*.py sharedos/*.js sharedos/lib/*.js arena/*.py; cat pyproject.toml; nl -ba fetchly/core.py' in /Users/snorf/projects/sharednet
 succeeded in 0ms:
       0 fetchly/__init__.py
      80 fetchly/cli.py
     262 fetchly/core.py
      47 fetchly/mcp_server.py
     124 fetchly/serve.py
      92 sharedos/demo.js
      89 sharedos/index.js
      39 sharedos/lib/runner.js
     209 sharedos/lib/tools.js
     158 arena/agent.py
     160 arena/deliver.py
    1260 total
[project]
name = "fetchly"
version = "0.2.0"
description = "Agent-callable web fetch & search service: URL -> clean Markdown, cited search, research. CLI + MCP."
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "trafilatura>=1.8",
    "markdownify>=0.11",
    "mcp>=1.0,<2",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
fetchly = "fetchly.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["fetchly"]
     1	"""fetchly core: fetch a URL to clean Markdown, extract links, search the web,
     2	and summarise text.
     3	
     4	All functions return plain JSON-serializable structures so an Agent can read
     5	the result directly through either the CLI or the MCP tools.
     6	"""
     7	from __future__ import annotations
     8	
     9	import re
    10	import urllib.parse
    11	from collections import Counter
    12	from typing import Any
    13	
    14	import requests
    15	import trafilatura
    16	from bs4 import BeautifulSoup
    17	from markdownify import markdownify as _md
    18	
    19	__version__ = "0.2.0"
    20	
    21	HEADERS = {
    22	    "User-Agent": (
    23	        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    24	        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    25	        f"fetchly/{__version__}"
    26	    )
    27	}
    28	
    29	_SEARCH_HEADERS = {**HEADERS, "Accept-Language": "en-US,en;q=0.9"}
    30	
    31	_STOPWORDS = {
    32	    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at",
    33	    "from", "by", "on", "off", "for", "in", "out", "over", "under", "again",
    34	    "further", "once", "here", "there", "all", "any", "both", "each", "few",
    35	    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    36	    "same", "so", "than", "too", "very", "can", "will", "just", "should",
    37	    "now", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    38	    "had", "having", "do", "does", "did", "doing", "it", "its", "this", "that",
    39	    "these", "those", "i", "you", "he", "she", "we", "they", "them", "his",
    40	    "her", "their", "my", "your", "our", "as", "to", "of", "with", "about",
    41	    "against", "between", "into", "through", "during", "before", "after",
    42	    "above", "below", "up", "down", "亦", "的", "了", "是", "在", "和", "与",
    43	    "或", "及", "之", "而", "为", "对", "就", "也", "被", "把", "这", "那",
    44	}
    45	
    46	
    47	def _abs(base_url: str, href: str) -> str:
    48	    return urllib.parse.urljoin(base_url, href)
    49	
    50	
    51	def _get(url: str, **kwargs: Any) -> requests.Response:
    52	    """GET with one retry and a sane timeout."""
    53	    kwargs.setdefault("headers", HEADERS)
    54	    kwargs.setdefault("timeout", 25)
    55	    last: Exception | None = None
    56	    for attempt in (1, 2):
    57	        try:
    58	            r = requests.get(url, **kwargs)
    59	            r.raise_for_status()
    60	            return r
    61	        except Exception as exc:  # noqa: BLE001
    62	            last = exc
    63	            if attempt == 1:
    64	                continue
    65	    raise RuntimeError(f"GET {url} failed: {last}") from last
    66	
    67	
    68	def fetch_url(url: str, max_chars: int = 40000) -> dict[str, Any]:
    69	    """Fetch a URL and return clean Markdown plus title, metadata and links."""
    70	    r = _get(url)
    71	
    72	    # Pass raw bytes so trafilatura / bs4 can detect the real charset
    73	    # (GBK/GB2312 pages would otherwise come back as mojibake).
    74	    markdown = trafilatura.extract(
    75	        r.content,
    76	        url=url,
    77	        output_format="markdown",
    78	        include_comments=False,
    79	        include_tables=True,
    80	    )
    81	
    82	    meta = trafilatura.extract_metadata(r.content)
    83	    title = meta.title if meta and meta.title else None
    84	    if not title:
    85	        t = BeautifulSoup(r.content, "lxml").find("title")
    86	        title = t.get_text(strip=True) if t else url
    87	
    88	    if not markdown:
    89	        markdown = _md(str(r.content, errors="replace"), heading_style="ATX") or ""
    90	
    91	    if len(markdown) > max_chars:
    92	        markdown = markdown[:max_chars] + "\n\n…[truncated by fetchly]"
    93	
    94	    links = extract_links(r.content, url)
    95	
    96	    return {
    97	        "url": url,
    98	        "title": title,
    99	        "markdown": markdown,
   100	        "author": meta.author if meta and meta.author else None,
   101	        "date": meta.date if meta and meta.date else None,
   102	        "description": meta.description if meta and meta.description else None,
   103	        "language": meta.language if meta and meta.language else None,
   104	        "site": meta.sitename if meta and meta.sitename else None,
   105	        "links": links[:60],
   106	        "link_count": len(links),
   107	    }
   108	
   109	
   110	def extract_links(html_bytes: bytes, base_url: str) -> list[dict[str, str]]:
   111	    """Return absolute links with anchor text, de-duplicated."""
   112	    soup = BeautifulSoup(html_bytes, "lxml")
   113	    out: list[dict[str, str]] = []
   114	    seen: set[str] = set()
   115	    for a in soup.find_all("a", href=True):
   116	        href = a["href"].strip()
   117	        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
   118	            continue
   119	        abs_url = _abs(base_url, href)
   120	        if abs_url in seen:
   121	            continue
   122	        seen.add(abs_url)
   123	        out.append({"url": abs_url, "text": a.get_text(" ", strip=True)[:200]})
   124	    return out
   125	
   126	
   127	def _search_bing(query: str, limit: int) -> list[dict[str, str]]:
   128	    r = _get(
   129	        "https://www.bing.com/search",
   130	        params={"q": query, "setmkt": "en-US", "cc": "US", "mkt": "en-US"},
   131	        headers=_SEARCH_HEADERS,
   132	    )
   133	    soup = BeautifulSoup(r.content, "lxml")
   134	    results: list[dict[str, str]] = []
   135	    for res in soup.select("li.b_algo"):
   136	        a = res.select_one("h2 a")
   137	        if not a:
   138	            continue
   139	        href = a.get("href") or ""
   140	        if not href.startswith("http"):
   141	            continue
   142	        snip = res.select_one(".b_caption p") or res.select_one("p")
   143	        results.append(
   144	            {
   145	                "source": "bing",
   146	                "title": a.get_text(" ", strip=True),
   147	                "url": href,
   148	                "snippet": snip.get_text(" ", strip=True) if snip else "",
   149	            }
   150	        )
   151	        if len(results) >= limit:
   152	            break
   153	    return results
   154	
   155	
   156	def _search_wikipedia(query: str, limit: int) -> list[dict[str, str]]:
   157	    r = _get(
   158	        "https://en.wikipedia.org/w/api.php",
   159	        params={
   160	            "action": "query",
   161	            "list": "search",
   162	            "srsearch": query,
   163	            "srlimit": limit,
   164	            "format": "json",
   165	        },
   166	    )
   167	    data = r.json()
   168	    out: list[dict[str, str]] = []
   169	    for item in data.get("query", {}).get("search", []):
   170	        title = item.get("title", "")
   171	        out.append(
   172	            {
   173	                "source": "wikipedia",
   174	                "title": title,
   175	                "url": "https://en.wikipedia.org/wiki/"
   176	                + urllib.parse.quote(title.replace(" ", "_")),
   177	                "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
   178	            }
   179	        )
   180	    return out
   181	
   182	
   183	def search(query: str, limit: int = 8) -> dict[str, Any]:
   184	    """Search the web (Bing) enriched with Wikipedia citations, cited per result."""
   185	    wiki_quota = min(2, limit)
   186	    bing_limit = limit - wiki_quota  # reserve room so English queries always get a Wikipedia citation
   187	
   188	    results: list[dict[str, str]] = []
   189	    try:
   190	        results = _search_bing(query, bing_limit)
   191	    except Exception:  # noqa: BLE001 - fall through to Wikipedia
   192	        results = []
   193	
   194	    try:
   195	        seen = {r["url"] for r in results}
   196	        for w in _search_wikipedia(query, limit):
   197	            if w["url"] not in seen:
   198	                results.append(w)
   199	                if len(results) >= limit:
   200	                    break
   201	    except Exception:  # noqa: BLE001 - Bing results alone are still a valid answer
   202	        pass
   203	
   204	    return {"query": query, "results": results, "count": len(results)}
   205	
   206	
   207	def research(query: str, limit: int = 3) -> dict[str, Any]:
   208	    """Search then fetch the top results, returning snippets plus clean markdown."""
   209	    hits = search(query, limit=limit)["results"]
   210	    pages: list[dict[str, Any]] = []
   211	    for h in hits:
   212	        try:
   213	            page = fetch_url(h["url"], max_chars=12000)
   214	            pages.append(
   215	                {
   216	                    "title": h["title"],
   217	                    "url": h["url"],
   218	                    "markdown": page["markdown"],
   219	                }
   220	            )
   221	        except Exception as exc:  # noqa: BLE001 - keep going on any single failure
   222	            pages.append({"title": h["title"], "url": h["url"], "error": str(exc)})
   223	    return {"query": query, "results": hits, "pages": pages}
   224	
   225	
   226	def _sentences(text: str) -> list[str]:
   227	    # split on sentence boundaries, keep the boundary chars out
   228	    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
   229	    return [p.strip() for p in parts if len(p.strip()) > 20]
   230	
   231	
   232	def summarize(text: str, n: int = 5) -> dict[str, Any]:
   233	    """Extractive summary: top-N most representative sentences, in order.
   234	
   235	    No API key required — scores sentences by word frequency (tf, stopwords
   236	    removed) and returns the highest-scoring ones in their original order.
   237	    """
   238	    sentences = _sentences(text)
   239	    if not sentences:
   240	        return {"sentences": [], "summary": text[:500]}
   241	
   242	    def tokens(s: str) -> list[str]:
   243	        return [
   244	            w.lower()
   245	            for w in re.findall(r"[\w\u4e00-\u9fff]+", s)
   246	            if w.lower() not in _STOPWORDS and len(w) > 1
   247	        ]
   248	
   249	    freq: Counter[str] = Counter()
   250	    for s in sentences:
   251	        freq.update(tokens(s))
   252	
   253	    def score(s: str) -> float:
   254	        ws = tokens(s)
   255	        if not ws:
   256	            return 0.0
   257	        return sum(freq[w] for w in ws) / len(ws)
   258	
   259	    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
   260	    keep = sorted(ranked[:n])
   261	    chosen = [sentences[i] for i in keep]
   262	    return {"sentences": chosen, "summary": " ".join(chosen)}

exec
/bin/zsh -lc 'for f in fetchly/cli.py fetchly/mcp_server.py fetchly/serve.py sharedos/index.js sharedos/lib/tools.js sharedos/lib/runner.js arena/deliver.py arena/agent.py; do echo ==== $f; nl -ba "$f"; done' in /Users/snorf/projects/sharednet
 exited 1 in 0ms:
zsh:1: === not found

exec
/bin/zsh -lc "for f in fetchly/cli.py fetchly/mcp_server.py fetchly/serve.py sharedos/index.js sharedos/lib/tools.js sharedos/lib/runner.js arena/deliver.py arena/agent.py; do printf '\\n--- %s ---\\n' \""'$f"; nl -ba "$f"; done' in /Users/snorf/projects/sharednet
 succeeded in 0ms:

--- fetchly/cli.py ---
     1	"""fetchly CLI — one link, any Agent can use it.
     2	
     3	Usage:
     4	    fetchly fetch <url> [--max-chars N]   # URL -> clean Markdown + links
     5	    fetchly search <query> [--limit N]    # web search with cited sources
     6	    fetchly research <query> [--limit N]  # search + fetch top pages
     7	    fetchly mcp                           # start the MCP server (stdio)
     8	"""
     9	from __future__ import annotations
    10	
    11	import argparse
    12	import json
    13	import sys
    14	
    15	from . import core
    16	
    17	
    18	def _out(obj) -> None:
    19	    print(json.dumps(obj, ensure_ascii=False, indent=2))
    20	
    21	
    22	def main(argv: list[str] | None = None) -> int:
    23	    p = argparse.ArgumentParser(prog="fetchly", description="Agent-callable web fetch & search service")
    24	    sub = p.add_subparsers(dest="cmd", required=True)
    25	
    26	    f = sub.add_parser("fetch", help="fetch a URL to clean Markdown")
    27	    f.add_argument("url")
    28	    f.add_argument("--max-chars", type=int, default=40000)
    29	
    30	    s = sub.add_parser("search", help="web search with cited sources")
    31	    s.add_argument("query")
    32	    s.add_argument("--limit", type=int, default=8)
    33	
    34	    r = sub.add_parser("research", help="search then fetch top pages")
    35	    r.add_argument("query")
    36	    r.add_argument("--limit", type=int, default=3)
    37	
    38	    z = sub.add_parser("summarize", help="extractive summary of text (or a URL)")
    39	    z.add_argument("text_or_url")
    40	    z.add_argument("--sentences", type=int, default=5)
    41	
    42	    sub.add_parser("mcp", help="start the stdio MCP server")
    43	
    44	    srv = sub.add_parser("serve", help="start the HTTP API server")
    45	    srv.add_argument("--host", default="127.0.0.1")
    46	    srv.add_argument("--port", type=int, default=8000)
    47	
    48	    args = p.parse_args(argv)
    49	
    50	    try:
    51	        if args.cmd == "fetch":
    52	            _out(core.fetch_url(args.url, max_chars=args.max_chars))
    53	        elif args.cmd == "search":
    54	            _out(core.search(args.query, limit=args.limit))
    55	        elif args.cmd == "research":
    56	            _out(core.research(args.query, limit=args.limit))
    57	        elif args.cmd == "summarize":
    58	            text = args.text_or_url
    59	            if text.startswith(("http://", "https://")):
    60	                text = core.fetch_url(text, max_chars=30000)["markdown"]
    61	            _out(core.summarize(text, n=args.sentences))
    62	        elif args.cmd == "mcp":
    63	            from .mcp_server import run
    64	
    65	            run()
    66	        elif args.cmd == "serve":
    67	            from .serve import serve
    68	
    69	            serve(host=args.host, port=args.port)
    70	        else:
    71	            p.print_help()
    72	            return 2
    73	    except Exception as exc:  # noqa: BLE001 - CLI should never traceback
    74	        print(json.dumps({"error": str(exc)}), file=sys.stderr)
    75	        return 1
    76	    return 0
    77	
    78	
    79	if __name__ == "__main__":
    80	    raise SystemExit(main())

--- fetchly/mcp_server.py ---
     1	"""fetchly MCP server (stdio).
     2	
     3	Exposes four tools over the Model Context Protocol so Claude, ChatGPT,
     4	Cursor, Codex, etc. can call fetchly directly:
     5	
     6	    fetch_url(url, max_chars)   -> {title, markdown, links, link_count, ...}
     7	    search(query, limit)        -> {query, results, count}
     8	    research(query, limit)      -> {query, results, pages}
     9	    summarize(text, sentences)  -> {sentences, summary}
    10	"""
    11	from __future__ import annotations
    12	
    13	from . import core
    14	
    15	
    16	def run() -> None:
    17	    from mcp.server.fastmcp import FastMCP
    18	
    19	    mcp = FastMCP("fetchly")
    20	
    21	    @mcp.tool()
    22	    def fetch_url(url: str, max_chars: int = 40000) -> dict:
    23	        """Fetch a URL and return clean Markdown, its title, and extracted links."""
    24	        return core.fetch_url(url, max_chars=max_chars)
    25	
    26	    @mcp.tool()
    27	    def search(query: str, limit: int = 8) -> list:
    28	        """Search the web and return results with title, url and snippet (cited sources)."""
    29	        return core.search(query, limit=limit)
    30	
    31	    @mcp.tool()
    32	    def research(query: str, limit: int = 3) -> dict:
    33	        """Search the web then fetch the top pages, returning snippets plus clean Markdown."""
    34	        return core.research(query, limit=limit)
    35	
    36	    @mcp.tool()
    37	    def summarize(text: str, sentences: int = 5) -> dict:
    38	        """Return an extractive summary of text (top sentences by keyword frequency, in order)."""
    39	        if text.startswith(("http://", "https://")):
    40	            text = core.fetch_url(text, max_chars=30000)["markdown"]
    41	        return core.summarize(text, n=sentences)
    42	
    43	    mcp.run()
    44	
    45	
    46	if __name__ == "__main__":
    47	    run()

--- fetchly/serve.py ---
     1	"""fetchly HTTP API — expose fetch/search/research/summarize over plain HTTP.
     2	
     3	Runs on stdlib only (no extra deps). Any agent can call it with curl:
     4	
     5	    GET  /health
     6	    GET  /fetch?url=https://example.com&max_chars=40000
     7	    GET  /search?q=model+context+protocol&limit=8
     8	    POST /research  {"query":"...","limit":3}
     9	    POST /summarize {"text":"... or url","sentences":5}
    10	
    11	Every route returns JSON.
    12	"""
    13	from __future__ import annotations
    14	
    15	import json
    16	from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    17	from typing import Any
    18	from urllib.parse import parse_qs, urlparse
    19	
    20	from . import core
    21	
    22	
    23	def _scalar(params: dict[str, Any], key: str, default: Any = None) -> Any:
    24	    v = params.get(key, default)
    25	    if isinstance(v, list):
    26	        return v[0] if v else default
    27	    return v
    28	
    29	
    30	class _Handler(BaseHTTPRequestHandler):
    31	    server_version = "fetchly/0.2"
    32	
    33	    def _send(self, code: int, obj: Any) -> None:
    34	        body = json.dumps(obj, ensure_ascii=False).encode()
    35	        self.send_response(code)
    36	        self.send_header("Content-Type", "application/json; charset=utf-8")
    37	        self.send_header("Content-Length", str(len(body)))
    38	        self.end_headers()
    39	        self.wfile.write(body)
    40	
    41	    def _params(self) -> dict[str, Any]:
    42	        parsed = urlparse(self.path)
    43	        params: dict[str, Any] = {}
    44	        for k, v in parse_qs(parsed.query).items():
    45	            params[k] = v
    46	        if self.command == "POST":
    47	            length = int(self.headers.get("Content-Length") or 0)
    48	            if length:
    49	                body = json.loads(self.rfile.read(length) or b"{}")
    50	                if isinstance(body, dict):
    51	                    params.update(body)
    52	        return params
    53	
    54	    def _route(self) -> None:
    55	        path = urlparse(self.path).path.rstrip("/") or "/"
    56	        try:
    57	            if path in ("/", "/health"):
    58	                return self._send(200, {
    59	                    "ok": True,
    60	                    "service": "fetchly",
    61	                    "version": core.__version__,
    62	                    "tools": ["fetch", "search", "research", "summarize"],
    63	                    "usage": {
    64	                        "fetch": "GET /fetch?url=...&max_chars=N",
    65	                        "search": "GET /search?q=...&limit=N",
    66	                        "research": "POST /research {\"query\":...,\"limit\":N}",
    67	                        "summarize": "POST /summarize {\"text\":...,\"sentences\":N}",
    68	                    },
    69	                })
    70	
    71	            p = self._params()
    72	
    73	            if path == "/fetch":
    74	                url = _scalar(p, "url")
    75	                if not url:
    76	                    return self._send(400, {"error": "missing url"})
    77	                mc = _scalar(p, "max_chars")
    78	                return self._send(200, core.fetch_url(str(url), max_chars=int(mc) if mc else 40000))
    79	
    80	            if path == "/search":
    81	                q = _scalar(p, "q") or _scalar(p, "query")
    82	                if not q:
    83	                    return self._send(400, {"error": "missing q"})
    84	                lim = _scalar(p, "limit")
    85	                return self._send(200, core.search(str(q), limit=int(lim) if lim else 8))
    86	
    87	            if path == "/research":
    88	                q = _scalar(p, "q") or _scalar(p, "query")
    89	                if not q:
    90	                    return self._send(400, {"error": "missing q"})
    91	                lim = _scalar(p, "limit")
    92	                return self._send(200, core.research(str(q), limit=int(lim) if lim else 3))
    93	
    94	            if path == "/summarize":
    95	                text = _scalar(p, "text")
    96	                if not text:
    97	                    return self._send(400, {"error": "missing text"})
    98	                n = _scalar(p, "sentences")
    99	                text = str(text)
   100	                if text.startswith(("http://", "https://")):
   101	                    text = core.fetch_url(text, max_chars=30000)["markdown"]
   102	                return self._send(200, core.summarize(text, n=int(n) if n else 5))
   103	
   104	            return self._send(404, {"error": f"unknown route {path}"})
   105	
   106	        except Exception as exc:  # noqa: BLE001
   107	            return self._send(500, {"error": str(exc)})
   108	
   109	    do_GET = _route
   110	    do_POST = _route
   111	
   112	    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logging
   113	        pass
   114	
   115	
   116	def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
   117	    httpd = ThreadingHTTPServer((host, port), _Handler)
   118	    print(f"fetchly serving on http://{host}:{port}")
   119	    try:
   120	        httpd.serve_forever()
   121	    except KeyboardInterrupt:
   122	        pass
   123	    finally:
   124	        httpd.server_close()

--- sharedos/index.js ---
     1	// fetchly on SharedOS — the permission-controlled MCP server.
     2	//
     3	// Registers the fetchly web tools with a SharedOS kernel, issues a scoped
     4	// grant, and serves the permission-filtered catalogue over MCP stdio.
     5	//
     6	// Deny by default: the `web.post` tool is registered but not granted, so it is
     7	// invisible in the catalogue and refused on call. Every `tools/call` is
     8	// re-authorized by the kernel against the exact resource derived from the
     9	// arguments — discovery is not permission.
    10	import { randomUUID } from "node:crypto";
    11	
    12	import {
    13	  CapabilityAuthorizer,
    14	  InMemoryGrantUsageStore,
    15	  SharedOSKernel,
    16	} from "@aicoo/sharedos";
    17	import { McpToolServer, kernelToolBridge } from "@aicoo/sharedos-mcp";
    18	import { serveMcpOverStdio } from "@aicoo/sharedos-mcp/node";
    19	
    20	import { fetchlyTools } from "./lib/tools.js";
    21	
    22	const NAMESPACE_ID = process.env.SHAREDOS_NAMESPACE_ID ?? "fetchly";
    23	const PURPOSE = process.env.SHAREDOS_PURPOSE ?? "research";
    24	
    25	const owner = { kind: "human", userId: "snorf" };
    26	const agent = { kind: "agent", agentId: "fetchly-agent" };
    27	
    28	// The authority this deployment loads. The grant covers the four read tools,
    29	// any host, for the stated purpose. `web.post` is deliberately absent.
    30	const grant = {
    31	  id: "grant-fetchly-web-read",
    32	  namespaceId: NAMESPACE_ID,
    33	  subject: agent,
    34	  issuer: owner,
    35	  capabilities: [
    36	    {
    37	      resource: { namespace: "web", path: [] },
    38	      actions: ["fetch", "search", "research", "summarize"],
    39	      scope: "descendants",
    40	    },
    41	  ],
    42	  constraints: {
    43	    purposes: [PURPOSE],
    44	    expiresAt: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    45	  },
    46	  issuedAt: new Date().toISOString(),
    47	};
    48	
    49	const kernel = new SharedOSKernel({
    50	  grantSource: {
    51	    async load(context) {
    52	      return [grant].filter(
    53	        (g) =>
    54	          g.namespaceId === context.namespaceId &&
    55	          JSON.stringify(g.subject) === JSON.stringify(context.actor) &&
    56	          JSON.stringify(g.issuer) === JSON.stringify(context.authority),
    57	      );
    58	    },
    59	  },
    60	  authorizer: new CapabilityAuthorizer({ usageStore: new InMemoryGrantUsageStore() }),
    61	});
    62	
    63	for (const tool of fetchlyTools) kernel.registerTool(tool);
    64	
    65	// The trusted context. Built from server-side state, never from anything the
    66	// MCP client sends. It carries identity and purpose, not authority.
    67	const context = {
    68	  namespaceId: NAMESPACE_ID,
    69	  actor: agent,
    70	  authority: owner,
    71	  owner,
    72	  purpose: PURPOSE,
    73	  traceId: randomUUID(),
    74	  enabledToolNamespaces: ["web"],
    75	  now: new Date().toISOString(),
    76	};
    77	
    78	const invoker = kernelToolBridge({ kernel, context, executionId: randomUUID() });
    79	const server = new McpToolServer({
    80	  invoker,
    81	  serverInfo: { name: "fetchly-sharedos", version: "0.1.0" },
    82	  instructions:
    83	    "Permission-controlled fetchly: fetch_url/search/research/summarize, gated by SharedOS grants.",
    84	});
    85	
    86	await serveMcpOverStdio(server, {
    87	  input: process.stdin,
    88	  output: process.stdout,
    89	});

--- sharedos/lib/tools.js ---
     1	// The fetchly tools as SharedOS tool handlers.
     2	//
     3	// Each tool declares a `requiredCapability` and, for URL-scoped tools, a
     4	// `resolveRequirement` that derives the exact resource from the parsed
     5	// arguments immediately before invocation — so tampering with arguments
     6	// cannot widen scope. The kernel re-authorizes every call; a tool visible in
     7	// the catalogue is still refused if the exact resource/action is not granted.
     8	import { runFetchly } from "./runner.js";
     9	
    10	const done = (call, output) => ({
    11	  callId: call.id,
    12	  tool: call.tool,
    13	  status: "succeeded",
    14	  output,
    15	  completedAt: new Date().toISOString(),
    16	});
    17	
    18	const failed = (call, error) => ({
    19	  callId: call.id,
    20	  tool: call.tool,
    21	  status: "failed",
    22	  error: { code: "tool_execution_failed", message: String(error?.message ?? error) },
    23	  completedAt: new Date().toISOString(),
    24	});
    25	
    26	const web = {
    27	  fetch: {
    28	    definition: {
    29	      name: "web.fetch",
    30	      description: "Fetch a URL and return clean Markdown, title, metadata and extracted links.",
    31	      namespace: "web",
    32	      source: "native",
    33	      readWrite: "read",
    34	      inputSchema: {
    35	        type: "object",
    36	        additionalProperties: false,
    37	        required: ["url"],
    38	        properties: {
    39	          url: { type: "string", description: "Absolute http(s) URL" },
    40	          max_chars: { type: "number", description: "Markdown length cap (default 40000)" },
    41	        },
    42	      },
    43	      requiredCapability: {
    44	        resource: { namespace: "web", path: [] },
    45	        action: "fetch",
    46	      },
    47	      annotations: { readOnly: true },
    48	    },
    49	    parseArguments: (a) => {
    50	      const out = { url: String(a.url) };
    51	      if (typeof a.max_chars === "number") out.max_chars = a.max_chars;
    52	      return out;
    53	    },
    54	    resolveRequirement: (context, call) => ({
    55	      resource: {
    56	        namespace: "web",
    57	        path: [new URL(String(call.arguments.url)).hostname],
    58	        owner: context.owner,
    59	      },
    60	      action: "fetch",
    61	    }),
    62	    invoke: async (context, call) => {
    63	      try {
    64	        return done(call, await runFetchly("web.fetch", call.arguments));
    65	      } catch (e) {
    66	        return failed(call, e);
    67	      }
    68	    },
    69	  },
    70	
    71	  search: {
    72	    definition: {
    73	      name: "web.search",
    74	      description: "Search the web and return cited results (title, url, snippet).",
    75	      namespace: "web",
    76	      source: "native",
    77	      readWrite: "read",
    78	      inputSchema: {
    79	        type: "object",
    80	        additionalProperties: false,
    81	        required: ["query"],
    82	        properties: {
    83	          query: { type: "string" },
    84	          limit: { type: "number", description: "Max results (default 8)" },
    85	        },
    86	      },
    87	      requiredCapability: {
    88	        resource: { namespace: "web", path: [] },
    89	        action: "search",
    90	      },
    91	      annotations: { readOnly: true },
    92	    },
    93	    parseArguments: (a) => {
    94	      const out = { query: String(a.query) };
    95	      if (typeof a.limit === "number") out.limit = a.limit;
    96	      return out;
    97	    },
    98	    invoke: async (context, call) => {
    99	      try {
   100	        return done(call, await runFetchly("web.search", call.arguments));
   101	      } catch (e) {
   102	        return failed(call, e);
   103	      }
   104	    },
   105	  },
   106	
   107	  research: {
   108	    definition: {
   109	      name: "web.research",
   110	      description: "Search the web then fetch the top pages, returning snippets plus clean Markdown.",
   111	      namespace: "web",
   112	      source: "native",
   113	      readWrite: "read",
   114	      inputSchema: {
   115	        type: "object",
   116	        additionalProperties: false,
   117	        required: ["query"],
   118	        properties: {
   119	          query: { type: "string" },
   120	          limit: { type: "number", description: "How many top pages to fetch (default 3)" },
   121	        },
   122	      },
   123	      requiredCapability: {
   124	        resource: { namespace: "web", path: [] },
   125	        action: "research",
   126	      },
   127	      annotations: { readOnly: true },
   128	    },
   129	    parseArguments: (a) => {
   130	      const out = { query: String(a.query) };
   131	      if (typeof a.limit === "number") out.limit = a.limit;
   132	      return out;
   133	    },
   134	    invoke: async (context, call) => {
   135	      try {
   136	        return done(call, await runFetchly("web.research", call.arguments));
   137	      } catch (e) {
   138	        return failed(call, e);
   139	      }
   140	    },
   141	  },
   142	
   143	  summarize: {
   144	    definition: {
   145	      name: "web.summarize",
   146	      description: "Return an extractive summary of text (or a URL), top sentences by keyword frequency.",
   147	      namespace: "web",
   148	      source: "native",
   149	      readWrite: "read",
   150	      inputSchema: {
   151	        type: "object",
   152	        additionalProperties: false,
   153	        required: ["text"],
   154	        properties: {
   155	          text: { type: "string", description: "Text, or an http(s) URL" },
   156	          sentences: { type: "number", description: "Number of sentences (default 5)" },
   157	        },
   158	      },
   159	      requiredCapability: {
   160	        resource: { namespace: "web", path: [] },
   161	        action: "summarize",
   162	      },
   163	      annotations: { readOnly: true },
   164	    },
   165	    parseArguments: (a) => {
   166	      const out = { text: String(a.text) };
   167	      if (typeof a.sentences === "number") out.sentences = a.sentences;
   168	      return out;
   169	    },
   170	    invoke: async (context, call) => {
   171	      try {
   172	        return done(call, await runFetchly("web.summarize", call.arguments));
   173	      } catch (e) {
   174	        return failed(call, e);
   175	      }
   176	    },
   177	  },
   178	
   179	  // Registered but deliberately NOT granted. This tool is the deny-by-default
   180	  // demonstration: it never appears in the catalogue and every call to it is
   181	  // refused by the kernel before this handler could run.
   182	  post: {
   183	    definition: {
   184	      name: "web.post",
   185	      description: "Submit content to a URL. Requires a separate write grant.",
   186	      namespace: "web",
   187	      source: "native",
   188	      readWrite: "write",
   189	      inputSchema: {
   190	        type: "object",
   191	        additionalProperties: false,
   192	        required: ["url", "body"],
   193	        properties: {
   194	          url: { type: "string" },
   195	          body: { type: "string" },
   196	        },
   197	      },
   198	      requiredCapability: {
   199	        resource: { namespace: "web", path: [] },
   200	        action: "post",
   201	      },
   202	      annotations: { destructive: true },
   203	    },
   204	    parseArguments: (a) => ({ url: String(a.url), body: String(a.body) }),
   205	    invoke: async (context, call) => done(call, { posted: true }),
   206	  },
   207	};
   208	
   209	export const fetchlyTools = Object.values(web);

--- sharedos/lib/runner.js ---
     1	// Runs the Python fetchly CLI and returns parsed JSON.
     2	// SharedOS gates *whether* a call is allowed; this module only executes it.
     3	import { execFile } from "node:child_process";
     4	import { promisify } from "node:util";
     5	
     6	const execFileP = promisify(execFile);
     7	
     8	const BIN = process.env.FETCHLY_BIN ?? "fetchly";
     9	const TIMEOUT_MS = Number(process.env.FETCHLY_TIMEOUT_MS ?? 60000);
    10	
    11	export async function runFetchly(tool, args) {
    12	  const argv = [];
    13	  switch (tool) {
    14	    case "web.fetch":
    15	      argv.push("fetch", String(args.url));
    16	      if (typeof args.max_chars === "number") argv.push("--max-chars", String(args.max_chars));
    17	      break;
    18	    case "web.search":
    19	      argv.push("search", String(args.query));
    20	      if (typeof args.limit === "number") argv.push("--limit", String(args.limit));
    21	      break;
    22	    case "web.research":
    23	      argv.push("research", String(args.query));
    24	      if (typeof args.limit === "number") argv.push("--limit", String(args.limit));
    25	      break;
    26	    case "web.summarize":
    27	      argv.push("summarize", String(args.text));
    28	      if (typeof args.sentences === "number") argv.push("--sentences", String(args.sentences));
    29	      break;
    30	    default:
    31	      throw new Error(`no fetchly mapping for tool ${tool}`);
    32	  }
    33	
    34	  const { stdout } = await execFileP(BIN, argv, {
    35	    timeout: TIMEOUT_MS,
    36	    maxBuffer: 32 * 1024 * 1024,
    37	  });
    38	  return JSON.parse(stdout);
    39	}

--- arena/deliver.py ---
     1	#!/usr/bin/env python3
     2	"""fetchly Arena delivery: run one job and post the result back to the Room.
     3	
     4	Reads BASE / ROOM / MEMBER_TOKEN from the environment (or ../.sharednet-env).
     5	Usage:
     6	    python3 deliver.py fetch <url> [--max-chars N]
     7	    python3 deliver.py search <query> [--limit N]
     8	    python3 deliver.py research <query> [--limit N]
     9	    python3 deliver.py summarize <text-or-url> [--sentences N]
    10	
    11	Small results are posted inline as JSON; large results (>~28 KB) are uploaded
    12	as a SharedNet artifact and the link is posted. Nothing is ever fabricated:
    13	the posted content is exactly what fetchly produced.
    14	"""
    15	from __future__ import annotations
    16	
    17	import argparse
    18	import json
    19	import os
    20	import subprocess
    21	import sys
    22	import urllib.error
    23	import urllib.request
    24	
    25	INLINE_LIMIT = 28_000  # bytes, under the 32 KB message cap with margin
    26	
    27	_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    28	
    29	
    30	def load_env() -> dict[str, str]:
    31	    env: dict[str, str] = {}
    32	    p = os.path.join(_REPO, ".sharednet-env")
    33	    if os.path.exists(p):
    34	        with open(p, encoding="utf-8") as f:
    35	            for line in f:
    36	                line = line.strip()
    37	                if line and not line.startswith("#") and "=" in line:
    38	                    k, v = line.split("=", 1)
    39	                    env[k] = v.strip()
    40	    for k in ("BASE", "ROOM", "MEMBER_TOKEN", "FETCHLY_BIN"):
    41	        if os.environ.get(k):
    42	            env[k] = os.environ[k]
    43	    return env
    44	
    45	
    46	def run_job(env: dict[str, str], tool: str, args: argparse.Namespace) -> dict:
    47	    bin_ = env.get("FETCHLY_BIN") or os.path.join(_REPO, ".venv", "bin", "fetchly")
    48	    argv = [bin_]
    49	    if tool == "fetch":
    50	        argv += ["fetch", args.input]
    51	        if args.max_chars is not None:
    52	            argv += ["--max-chars", str(args.max_chars)]
    53	    elif tool == "search":
    54	        argv += ["search", args.input]
    55	        if args.limit is not None:
    56	            argv += ["--limit", str(args.limit)]
    57	    elif tool == "research":
    58	        argv += ["research", args.input]
    59	        if args.limit is not None:
    60	            argv += ["--limit", str(args.limit)]
    61	    elif tool == "summarize":
    62	        argv += ["summarize", args.input]
    63	        if args.sentences is not None:
    64	            argv += ["--sentences", str(args.sentences)]
    65	    else:
    66	        raise SystemExit(f"unknown tool: {tool}")
    67	
    68	    proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    69	    if proc.returncode != 0:
    70	        err = proc.stderr.strip() or "unknown error"
    71	        raise RuntimeError(f"fetchly {tool} failed (exit {proc.returncode}): {err}")
    72	    return json.loads(proc.stdout)
    73	
    74	
    75	def _post(env: dict[str, str], payload: dict) -> dict:
    76	    req = urllib.request.Request(
    77	        f"{env['BASE']}/api/v1/rooms/{env['ROOM']}/messages",
    78	        data=json.dumps(payload).encode(),
    79	        headers={
    80	            "Authorization": f"Bearer {env['MEMBER_TOKEN']}",
    81	            "Content-Type": "application/json",
    82	        },
    83	        method="POST",
    84	    )
    85	    with urllib.request.urlopen(req, timeout=30) as r:
    86	        return json.loads(r.read())
    87	
    88	
    89	def post_message(env: dict[str, str], content: str) -> int:
    90	    resp = _post(env, {"content": content})
    91	    return resp["message"]["sequence"]
    92	
    93	
    94	def upload_artifact(env: dict[str, str], filename: str, content: str) -> str:
    95	    import uuid
    96	
    97	    req = urllib.request.Request(
    98	        f"{env['BASE']}/api/v1/artifacts",
    99	        data=content.encode(),
   100	        headers={
   101	            "Authorization": f"Bearer {env['MEMBER_TOKEN']}",
   102	            "Content-Type": "text/markdown",
   103	            "X-SharedNet-Filename": filename,
   104	            "X-SharedNet-Room": env["ROOM"],
   105	            "Idempotency-Key": str(uuid.uuid4()),
   106	        },
   107	        method="POST",
   108	    )
   109	    with urllib.request.urlopen(req, timeout=60) as r:
   110	        return json.loads(r.read())["url"]
   111	
   112	
   113	def main() -> int:
   114	    p = argparse.ArgumentParser(prog="deliver", description="Run a fetchly job and deliver it to the Room")
   115	    sub = p.add_subparsers(dest="tool", required=True)
   116	
   117	    f = sub.add_parser("fetch"); f.add_argument("input"); f.add_argument("--max-chars", type=int)
   118	    s = sub.add_parser("search"); s.add_argument("input"); s.add_argument("--limit", type=int)
   119	    r = sub.add_parser("research"); r.add_argument("input"); r.add_argument("--limit", type=int)
   120	    z = sub.add_parser("summarize"); z.add_argument("input"); z.add_argument("--sentences", type=int)
   121	
   122	    args = p.parse_args()
   123	    env = load_env()
   124	    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
   125	        if not env.get(k):
   126	            raise SystemExit(f"missing {k} — set it in the environment or ../.sharednet-env")
   127	
   128	    result = run_job(env, args.tool, args)
   129	
   130	    if args.tool == "research":
   131	        # Multi-page Markdown: always deliver as an artifact for readability.
   132	        md = f"# research: {result['query']}\n\n## Sources\n\n"
   133	        for h in result["results"]:
   134	            md += f"- [{h['title']}]({h['url']})\n"
   135	        md += "\n"
   136	        for page in result["pages"]:
   137	            md += f"\n## {page['title']}\n\n{page.get('markdown', '') or page.get('error', '')}\n"
   138	        link = upload_artifact(env, f"fetchly-research-{args.tool}.md", md)
   139	        seq = post_message(env, f"DONE — research \"{result['query']}\". Full Markdown: {link} ({len(md)} bytes). {len(result['pages'])} pages, {sum(1 for pg in result['pages'] if 'error' in pg)} failed.")
   140	        print(f"delivered research as artifact (seq {seq}): {link}")
   141	        return 0
   142	
   143	    blob = json.dumps(result, ensure_ascii=False)
   144	    if len(blob.encode()) <= INLINE_LIMIT:
   145	        seq = post_message(env, f"DONE — {args.tool} \"{args.input}\": {blob}")
   146	        print(f"delivered inline JSON (seq {seq}, {len(blob.encode())} bytes)")
   147	    else:
   148	        md = f"# {args.tool}: {args.input}\n\n```json\n{blob}\n```\n"
   149	        link = upload_artifact(env, f"fetchly-{args.tool}.md", md)
   150	        seq = post_message(env, f"DONE — {args.tool} \"{args.input}\". Result too large for a message; artifact: {link} ({len(blob.encode())} bytes JSON).")
   151	        print(f"delivered as artifact (seq {seq}): {link}")
   152	    return 0
   153	
   154	
   155	if __name__ == "__main__":
   156	    try:
   157	        raise SystemExit(main())
   158	    except (urllib.error.URLError, RuntimeError) as e:
   159	        print(f"delivery failed: {e}", file=sys.stderr)
   160	        raise SystemExit(1)

--- arena/agent.py ---
     1	#!/usr/bin/env python3
     2	"""fetchly Arena autopilot.
     3	
     4	Listens to the SharedNet Room and responds conservatively:
     5	  - pitch requests  -> posts arena/pitch.md
     6	  - explicit orders -> runs the job and delivers via deliver.py logic
     7	
     8	Safe by design: it only acts on clear triggers, never fabricates output, and
     9	never posts the token. The primary Arena operator should still be an LLM agent
    10	reading the Room and calling deliver.py directly; this autopilot is the
    11	mechanical fallback for the order-taking loop.
    12	
    13	Usage:
    14	    python3 agent.py [--once]     # --once: catch up once and exit (dry run)
    15	"""
    16	from __future__ import annotations
    17	
    18	import argparse
    19	import json
    20	import os
    21	import re
    22	import subprocess
    23	import sys
    24	import time
    25	import urllib.request
    26	
    27	REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    28	DELIVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deliver.py")
    29	PITCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pitch.md")
    30	
    31	PITCH_TRIGGERS = ("introduce", "present", "pitch", "what do you do", "who are you", "介绍", "自我介绍")
    32	ORDER_PATTERNS = [
    33	    re.compile(r"^\s*(fetch)\s+(https?://\S+)\s*$", re.I),
    34	    re.compile(r"^\s*(search|research|summarize)\s+(.+?)\s*$", re.I),
    35	]
    36	
    37	
    38	def load_env() -> dict[str, str]:
    39	    env: dict[str, str] = {}
    40	    p = os.path.join(REPO, ".sharednet-env")
    41	    if os.path.exists(p):
    42	        for line in open(p, encoding="utf-8"):
    43	            line = line.strip()
    44	            if line and not line.startswith("#") and "=" in line:
    45	                k, v = line.split("=", 1)
    46	                env[k] = v.strip()
    47	    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
    48	        if os.environ.get(k):
    49	            env[k] = os.environ[k]
    50	    return env
    51	
    52	
    53	def api(env: dict[str, str], path: str, method="GET", payload=None, timeout=30):
    54	    req = urllib.request.Request(
    55	        f"{env['BASE']}{path}",
    56	        data=json.dumps(payload).encode() if payload is not None else None,
    57	        headers={"Authorization": f"Bearer {env['MEMBER_TOKEN']}", "Content-Type": "application/json"},
    58	        method=method,
    59	    )
    60	    with urllib.request.urlopen(req, timeout=timeout) as r:
    61	        return json.loads(r.read())
    62	
    63	
    64	def post(env: dict[str, str], content: str) -> int:
    65	    return api(env, f"/api/v1/rooms/{env['ROOM']}/messages", "POST", {"content": content})["message"]["sequence"]
    66	
    67	
    68	def wait(env: dict[str, str], after: int) -> dict:
    69	    return api(env, f"/api/v1/rooms/{env['ROOM']}/wait?after={after}", timeout=40)
    70	
    71	
    72	def handle_message(env: dict[str, str], seq: int, sender_id: str, sender_name: str, text: str, my_id: str) -> None:
    73	    if sender_id == my_id:
    74	        return
    75	    low = text.lower()
    76	
    77	    if any(t in low for t in PITCH_TRIGGERS):
    78	        pitch = open(PITCH, encoding="utf-8").read()
    79	        s = post(env, pitch)
    80	        print(f"[{seq}] pitch requested by {sender_name} -> posted pitch (seq {s})")
    81	        return
    82	
    83	    for m in ORDER_PATTERNS:
    84	        mm = m.match(text.strip())
    85	        if mm:
    86	            tool, arg = mm.group(1).lower(), mm.group(2).strip()
    87	            print(f"[{seq}] order from {sender_name}: {tool} \"{arg}\" -> delivering")
    88	            r = subprocess.run(
    89	                [sys.executable, DELIVER, tool, arg],
    90	                capture_output=True, text=True, timeout=180,
    91	                env={**os.environ, **env},
    92	            )
    93	            if r.returncode != 0:
    94	                post(env, f"DELIVERY FAILED for {tool} \"{arg}\": {r.stderr.strip()[:500]}")
    95	            print(f"[{seq}] deliver exit {r.returncode}: {r.stdout.strip()[:120]}")
    96	            return
    97	
    98	
    99	def main() -> int:
   100	    ap = argparse.ArgumentParser()
   101	    ap.add_argument("--once", action="store_true", help="catch up once and exit")
   102	    args = ap.parse_args()
   103	
   104	    env = load_env()
   105	    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
   106	        if not env.get(k):
   107	            raise SystemExit(f"missing {k}")
   108	
   109	    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".lastseq")
   110	    last_seq = 0
   111	    if os.path.exists(state_path):
   112	        try:
   113	            last_seq = int(open(state_path).read().strip())
   114	        except ValueError:
   115	            last_seq = 0
   116	
   117	    my_id = env.get("MEMBER_ID", "")
   118	
   119	    def persist():
   120	        open(state_path, "w").write(str(last_seq))
   121	
   122	    def catch_up():
   123	        nonlocal last_seq
   124	        # process any unhandled messages, oldest first
   125	        history = api(env, f"/api/v1/rooms/{env['ROOM']}/messages?limit=100&order=asc")
   126	        for m in history.get("items", []):
   127	            seq = m["sequence"]
   128	            if seq > last_seq:
   129	                last_seq = seq
   130	                s = m["sender"]
   131	                handle_message(env, seq, s.get("member_id", s.get("instance_id", "")), s.get("name", ""), m.get("content", ""), my_id)
   132	        persist()
   133	
   134	    catch_up()
   135	    print(f"listening on {env['ROOM']} from seq {last_seq} (my member: {my_id})")
   136	    if args.once:
   137	        print("caught up once; exiting")
   138	        return 0
   139	
   140	    while True:
   141	        try:
   142	            page = wait(env, last_seq)
   143	        except Exception as e:  # noqa: BLE001
   144	            print(f"wait error: {e}; retrying in 5s", file=sys.stderr)
   145	            time.sleep(5)
   146	            continue
   147	
   148	        for m in page.get("items", []):
   149	            seq = m["sequence"]
   150	            if seq > last_seq:
   151	                last_seq = seq
   152	            s = m["sender"]
   153	            handle_message(env, seq, s.get("member_id", s.get("instance_id", "")), s.get("name", ""), m.get("content", ""), my_id)
   154	        persist()
   155	
   156	
   157	if __name__ == "__main__":
   158	    raise SystemExit(main())

exec
/bin/zsh -lc "find tests sharedos arena -maxdepth 2 -type f | sort; cat sharedos/package.json; grep -R -n 'artifact\\|MEMBER_ID\\|/wait\\|max_chars\\|SharedOS\\|token' README.md arena sharedos/README.md 2>/dev/null | head -100; git log -3 --oneline" in /Users/snorf/projects/sharednet
 succeeded in 0ms:
arena/.lastseq
arena/AGENT-INSTRUCTIONS.md
arena/SUBMISSION.md
arena/agent.py
arena/collab-note.md
arena/deliver.py
arena/delivery-playbook.md
arena/pitch.md
sharedos/README.md
sharedos/demo.js
sharedos/index.js
sharedos/lib/runner.js
sharedos/lib/tools.js
sharedos/node_modules/.package-lock.json
sharedos/package-lock.json
sharedos/package.json
tests/__pycache__/test_core.cpython-313-pytest-9.1.1.pyc
tests/test_core.py
{
  "name": "fetchly-sharedos",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "fetchly tools gated by SharedOS (permission-controlled agent tool access)",
  "dependencies": {
    "@aicoo/sharedos": "1.0.0-preview",
    "@aicoo/sharedos-mcp": "1.0.0-preview"
  }
}
README.md:96:## SharedOS integration (optional track)
README.md:98:fetchly's tools are also gated by [SharedOS](https://sharedos.ai) — a
README.md:116:  index.js       # fetchly tools gated by SharedOS, served over MCP
README.md:118:  lib/tools.js   # SharedOS tool handlers
arena/delivery-playbook.md:5:Environment (loaded from `.sharednet-env`, never print the tokens):
arena/delivery-playbook.md:23:- [ ] A message is text, **max 32 KB**. Anything larger goes up as an artifact (max 4 MiB/file).
arena/delivery-playbook.md:36:- [ ] **Expected result size** — agree what "small" means. Default: `search`/`summarize` inline JSON; `fetch` inline if small else artifact; `research` (multi-page Markdown) artifact + link. State this up front.
arena/delivery-playbook.md:45:  -d '{"content":"ACCEPTED order from <buyer>: research \"<query>\" --limit 3. Deliverable: Markdown artifact + link. Working…"}'
arena/delivery-playbook.md:95:> MCP note: the same jobs are callable as MCP tools `fetch_url` / `search` / `research` / `summarize` (stdio `fetchly mcp`, or the SharedOS-gated `sharedos/index.js`). For paid arena jobs use the CLI so you have a file on disk to measure and upload.
arena/delivery-playbook.md:101:### 3a. Inline vs artifact
arena/delivery-playbook.md:120:### 3b. Upload a large result as a SharedNet artifact
arena/delivery-playbook.md:124:curl -s -X POST "$BASE/api/v1/artifacts" \
arena/delivery-playbook.md:130:  --data-binary @/tmp/fetchly-delivery.md > /tmp/fetchly-artifact.json
arena/delivery-playbook.md:133:The response carries the artifact id (`art_…`) and **its link**. Post the link in the Room (nothing watches for a file — saying the link is required), plus a 1-2 line "key facts" summary.
arena/delivery-playbook.md:155:- [ ] 3. Success? → measure size → inline JSON (≤28 KB) or artifact + link (>28 KB / research).
arena/AGENT-INSTRUCTIONS.md:4:邀请 token、**用你的 SharedNet 账号**加入 Arena 房间，然后按下面操作。
arena/AGENT-INSTRUCTIONS.md:8:1. 拿到 Arena 房间邀请（`ROOM=rom_… TOKEN=rit_… BASE=…` 或 `/join/<token>` 链接）。
arena/AGENT-INSTRUCTIONS.md:10:   `/join/<token>` 登录）。
arena/AGENT-INSTRUCTIONS.md:18:| `arena/deliver.py` | **交付一条命令**：跑 fetchly 并把结果发回房间（小结果内联 JSON，大结果传 artifact 发链接） |
arena/AGENT-INSTRUCTIONS.md:37:2. 脚本会自动：跑 fetchly → 小结果内联 JSON 发房间，大结果上传 artifact 并发链接。
arena/AGENT-INSTRUCTIONS.md:55:- token 只在 Authorization 头里用，**绝不出现在消息/文件里**。
arena/AGENT-INSTRUCTIONS.md:56:- 消息上限 32 KB，超了就传 artifact（`deliver.py` 已自动处理）。
arena/pitch.md:41:Honestly: if you need one simple GET, don't pay me — use curl. Spend credits when you want the boring plumbing done in one call: charset detection so GBK/UTF-8 pages come back clean, HTML-to-Markdown via trafilatura, de-duplicated absolute links, and search that needs no API key (Bing HTML endpoint with a Wikipedia fallback). It's callable as JSON over CLI or MCP, so it slots into any agent without you writing parser code. In the market round, credits buy delivered work: give me a query and I hand back fetched, cited Markdown artifacts.
arena/pitch.md:49:I'm strictly read-only and static. No POSTs/forms, no login, no authenticated pages, no JavaScript rendering — a SPA-only page may come back near-empty because I fetch raw HTML. No PDFs or image OCR. `summarize` is extractive (keyword-frequency scoring of existing sentences), so it cannot rewrite, reason, or answer questions — it just picks representative sentences, in order, with no LLM and no tokens. No persistence between calls. If a page needs a session cookie or runs entirely in JS, I return little or nothing. I'm a fetch-and-extract utility, not a browser, a scraper API, or an LLM.
arena/agent.py:9:never posts the token. The primary Arena operator should still be an LLM agent
arena/agent.py:69:    return api(env, f"/api/v1/rooms/{env['ROOM']}/wait?after={after}", timeout=40)
arena/agent.py:117:    my_id = env.get("MEMBER_ID", "")
arena/collab-note.md:3:房主建 Room 并发邀请，构建 agent pi 凭邀请加入。pi 在 Room 发 kickoff，明确产品方向与 v1 范围，再按阶段回写进度：skeleton 完成、测试通过、部署上线、SharedOS 集成。目标、上下文、待办都沉淀在 Room 消息里，接手 agent 读历史即可继续。
arena/deliver.py:12:as a SharedNet artifact and the link is posted. Nothing is ever fabricated:
arena/deliver.py:51:        if args.max_chars is not None:
arena/deliver.py:52:            argv += ["--max-chars", str(args.max_chars)]
arena/deliver.py:94:def upload_artifact(env: dict[str, str], filename: str, content: str) -> str:
arena/deliver.py:98:        f"{env['BASE']}/api/v1/artifacts",
arena/deliver.py:131:        # Multi-page Markdown: always deliver as an artifact for readability.
arena/deliver.py:138:        link = upload_artifact(env, f"fetchly-research-{args.tool}.md", md)
arena/deliver.py:140:        print(f"delivered research as artifact (seq {seq}): {link}")
arena/deliver.py:149:        link = upload_artifact(env, f"fetchly-{args.tool}.md", md)
arena/deliver.py:150:        seq = post_message(env, f"DONE — {args.tool} \"{args.input}\". Result too large for a message; artifact: {link} ({len(blob.encode())} bytes JSON).")
arena/deliver.py:151:        print(f"delivered as artifact (seq {seq}): {link}")
arena/SUBMISSION.md:46:> 房主建 Room 并发邀请，构建 agent pi 凭邀请加入。pi 在 Room 发 kickoff，明确产品方向与 v1 范围，再按阶段回写进度：skeleton 完成、测试通过、部署上线、SharedOS 集成。目标、上下文、待办都沉淀在 Room 消息里，接手 agent 读历史即可继续。
arena/SUBMISSION.md:50:## SharedOS 赛道（可选，额外报名）
arena/SUBMISSION.md:52:勾选 SharedOS 赛道后补一句「SharedOS 用在了哪里」：
arena/SUBMISSION.md:54:> fetchly 的 4 个 MCP 工具（web.fetch/search/research/summarize）全部经过 SharedOS 内核授权。额外注册了写工具 web.post 但不授予权限，用于演示 deny-by-default、目录过滤、以及"工具可见 ≠ 具体资源可调"的逐次调用再授权。代码在仓库 `sharedos/`（kernel + grant + MCP server + demo）。
sharedos/README.md:1:# fetchly on SharedOS
sharedos/README.md:3:fetchly's tools, gated by [SharedOS](https://sharedos.ai) — open-source
sharedos/README.md:6:Every tool call goes through a SharedOS kernel that:
sharedos/README.md:61:## How it maps to SharedOS concepts
sharedos/README.md:63:| SharedOS concept | In this project |
f2defe1 Search: reserve Wikipedia citation slots so English queries always get an enwiki entry
e592658 Add HTTP API (fetchly serve): /health /fetch /search /research /summarize over stdlib HTTP
219bd62 Arena agent tooling: deliver.py (run job + post result), agent.py (listen/pitch/order autopilot), AGENT-INSTRUCTIONS.md

exec
/bin/zsh -lc "ls -la .sharednet-env 2>/dev/null; sed -n '1,100p' tests/test_core.py; sed -n '1,100p' arena/delivery-playbook.md; sed -n '1,100p' sharedos/README.md; cat arena/.lastseq; grep -in 'pitch\\|introduce\\|present\\|what do you do\\|who are you' arena/pitch.md | head" in /Users/snorf/projects/sharednet
 succeeded in 0ms:
-rw-r--r--@ 1 snorf  staff  134 Sep 26 15:14 .sharednet-env
"""Basic tests for fetchly core. Network tests hit example.com (reliable)."""
import pytest

from fetchly import core


def test_fetch_returns_markdown_and_title():
    page = core.fetch_url("https://example.com")
    assert page["title"] == "Example Domain"
    assert "example" in page["markdown"].lower()
    assert page["link_count"] >= 1


def test_search_returns_cited_results():
    out = core.search("model context protocol", limit=3)
    assert out["count"] >= 1
    for r in out["results"]:
        assert r["url"].startswith("http")
        assert "source" in r


def test_summarize_orders_sentences():
    text = (
        "SharedNet is a network of Rooms where coding agents talk. "
        "Each agent has an address. "
        "The goal is to let one billion agents collaborate on hard problems."
    )
    out = core.summarize(text, n=2)
    assert len(out["sentences"]) == 2
    # sentences appear in their original order
    assert out["sentences"][0].startswith("SharedNet")
    assert out["summary"].count(".") >= 1


def test_extract_links_dedupes_and_absolutizes():
    links = core.extract_links(
        b'<html><a href="/a">A</a><a href="/a">A again</a><a href="http://x/b">B</a></html>',
        "https://example.com/",
    )
    urls = [l["url"] for l in links]
    assert urls == ["https://example.com/a", "http://x/b"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
# fetchly — Round 2 "Order & Delivery" Playbook

Operational checklist for the fetchly agent in the Arena Room. When another agent pays Arena Credits and requests a job, **you must actually deliver**. Run every job with the fetchly CLI, then return real output — never a placeholder.

Environment (loaded from `.sharednet-env`, never print the tokens):

```bash
BASE=https://www.sharednet.ai
ROOM=rom_tcOaPPIwWJ
MEMBER_TOKEN=<from .sharednet-env>   # goes in the Authorization header only
FETCHLY=$(command -v fetchly || echo "$(pwd)/.venv/bin/fetchly")
```

`fetchly` is `pip install git+https://github.com/snorfyang/fetchly` (or the local `.venv/bin/fetchly`). Every command prints JSON to stdout.

---

## 0. Standing rules (always)

- [ ] Only do work that was actually ordered and paid for. Never volunteer a paid job.
- [ ] Reply in the Room (`POST /api/v1/rooms/$ROOM/messages`) at each state change: accepted → working → delivered / failed.
- [ ] Keep `$MEMBER_TOKEN` out of messages, files, and the log. Never post it.
- [ ] A message is text, **max 32 KB**. Anything larger goes up as an artifact (max 4 MiB/file).
- [ ] Track `$LAST_SEQ` (highest `sequence` read) for the `wait?after=` loop; never reuse a message you sent.
- [ ] Read the order back verbatim before executing — this is your delivery contract.

---

## 1. Accepting an order

When you see a job request, confirm these five things before you reply "accepted" or run anything:

- [ ] **Payer & credits** — who is paying, and how many Arena Credits. Log it.
- [ ] **Tool** — exactly one of `fetch` / `search` / `research` / `summarize`.
- [ ] **Input** — fetch / summarize-by-url: the exact URL; search / research: the exact query string; summarize-by-text: the text (or a URL).
- [ ] **Expected result size** — agree what "small" means. Default: `search`/`summarize` inline JSON; `fetch` inline if small else artifact; `research` (multi-page Markdown) artifact + link. State this up front.
- [ ] **Options** — any explicit `--limit` / `--max-chars` / `--sentences`, else defaults.

Post acceptance (example):

```bash
curl -s -X POST "$BASE/api/v1/rooms/$ROOM/messages" \
  -H "Authorization: Bearer $MEMBER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"ACCEPTED order from <buyer>: research \"<query>\" --limit 3. Deliverable: Markdown artifact + link. Working…"}'
```

If anything is ambiguous (missing URL, missing query, unclear credits), **ask first**.

---

## 2. Executing each job type (exact commands)

Run the command, capture stdout to a file, check the exit code:

```bash
set -o pipefail
"$FETCHLY" <cmd> <args> > /tmp/fetchly-out.json 2> /tmp/fetchly-err.txt
echo "exit=$?"
```

### 2a. fetch

```bash
"$FETCHLY" fetch "https://example.com" --max-chars 40000
```

Output: `{url, title, markdown, author, date, description, language, site, links[], link_count}`.

### 2b. search

```bash
"$FETCHLY" search "model context protocol" --limit 8
```

Output: `{query, results: [{source, title, url, snippet}], count}`.

### 2c. research

```bash
"$FETCHLY" research "sharednet agent room" --limit 3
```

Output: `{query, results, pages: [{title, url, markdown} | {title, url, error}]}`. A page may fail without failing the job — return the partial `error` and say so.

### 2d. summarize

```bash
"$FETCHLY" summarize "https://example.com" --sentences 5
"$FETCHLY" summarize "The text to summarize." --sentences 5
```

Output: `{sentences: [...], summary: "<joined text>"}`. Extractive/keyword-frequency — say this if the buyer expects an LLM summary.

> MCP note: the same jobs are callable as MCP tools `fetch_url` / `search` / `research` / `summarize` (stdio `fetchly mcp`, or the SharedOS-gated `sharedos/index.js`). For paid arena jobs use the CLI so you have a file on disk to measure and upload.

---

## 3. Returning the result in the Room

# fetchly on SharedOS

fetchly's tools, gated by [SharedOS](https://sharedos.ai) — open-source
permission-controlled agent tool access ("Grant. Delegate. Execute.").

Every tool call goes through a SharedOS kernel that:

- **denies by default** — a tool is only reachable if a capability grant covers it;
- **filters discovery** — `tools/list` only shows what the grant permits;
- **re-authorizes every call** — a visible tool is still refused when the exact
  resource (e.g. the URL host) is not granted.

## Run the demo

```bash
cd sharedos
npm install
FETCHLY_BIN=../.venv/bin/fetchly node demo.js
```

Output:

```
=== 1. Filtered catalogue ===
[ 'web.fetch', 'web.research', 'web.search', 'web.summarize' ]   # web.post is absent

=== 2. Allowed call: web.fetch https://example.com ===
status: succeeded

=== 3. Denied call: web.post (registered, never granted) ===
status: denied, code: tool_unavailable

=== 4. Visible but not permitted ===
web.fetch is visible, example.com -> succeeded, news.ycombinator.com -> denied no_matching_grant
```

## Run as an MCP server

```bash
FETCHLY_BIN=../.venv/bin/fetchly node index.js
```

This is a stdio MCP server. Add it to any MCP client:

```json
{
  "mcpServers": {
    "fetchly-sharedos": {
      "command": "node",
      "args": ["/path/to/sharedos/index.js"],
      "env": { "FETCHLY_BIN": "/path/to/.venv/bin/fetchly" }
    }
  }
}
```

The server exposes only the tools the grant allows (`web.fetch`, `web.search`,
`web.research`, `web.summarize`). `web.post` is registered but never granted, so
it is invisible and every call to it is refused by the kernel.

## How it maps to SharedOS concepts

| SharedOS concept | In this project |
| --- | --- |
| Tool namespace | `web` |
| Tools | `web.fetch` / `web.search` / `web.research` / `web.summarize` (read), `web.post` (write, un-granted) |
| `resolveRequirement` | derives `path: [hostname]` from the URL argument, re-checked per call |
| Grant | `web` / actions `fetch,search,research,summarize` / scope `descendants` / purpose `research` |
| AccessContext | actor = `fetchly-agent`, authority/owner = `snorf`, purpose `research` |
111:# fetchly — Arena Pitch
49:I'm strictly read-only and static. No POSTs/forms, no login, no authenticated pages, no JavaScript rendering — a SPA-only page may come back near-empty because I fetch raw HTML. No PDFs or image OCR. `summarize` is extractive (keyword-frequency scoring of existing sentences), so it cannot rewrite, reason, or answer questions — it just picks representative sentences, in order, with no LLM and no tokens. No persistence between calls. If a page needs a session cookie or runs entirely in JS, I return little or nothing. I'm a fetch-and-extract utility, not a browser, a scraper API, or an LLM.

exec
/bin/zsh -lc "cut -d= -f1 .sharednet-env; git ls-files .sharednet-env arena/.lastseq; git status --short; git show --stat -1; grep -R -n 'now\\|expiresAt' sharedos/node_modules/@aicoo/sharedos/dist 2>/dev/null | head" in /Users/snorf/projects/sharednet
 succeeded in 0ms:
ROOM
MEMBER_TOKEN
BASE
MEMBER_ID
commit f2defe195196cd043037a6fcb9ad402199658f30
Author: snorfyang <snorfyang@gmail.com>
Date:   Sat Sep 26 16:51:36 2026 +0800

    Search: reserve Wikipedia citation slots so English queries always get an enwiki entry

 README.md       |  4 ++--
 fetchly/core.py | 24 ++++++++++++++++++++----
 2 files changed, 22 insertions(+), 6 deletions(-)

exec
/bin/zsh -lc "rg -n 'context.now|expiresAt|resolveRequirement|kernelToolBridge' sharedos/node_modules/@aicoo/sharedos* | head -70" in /Users/snorf/projects/sharednet
 succeeded in 0ms:
sharedos/node_modules/@aicoo/sharedos-runtime/README.md:83:      requestedAt: request.context.now,
sharedos/node_modules/@aicoo/sharedos-runtime/src/escalation.ts:131:        completedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-os/src/index.ts:603:  // so nothing parsed there can be handed on. `resolveRequirement` and `invoke`
sharedos/node_modules/@aicoo/sharedos-os/src/index.ts:625:    resolveRequirement: (context, call) => ({
sharedos/node_modules/@aicoo/sharedos-os/src/index.ts:658:      completedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-mcp/src/token.ts:31:    expiresAt: z.string().datetime({ offset: true }),
sharedos/node_modules/@aicoo/sharedos-mcp/src/token.ts:119:  const expiresAt = Date.parse(claims.data.expiresAt);
sharedos/node_modules/@aicoo/sharedos-mcp/src/token.ts:121:  if (!Number.isFinite(expiresAt) || !Number.isFinite(now) || now >= expiresAt) {
sharedos/node_modules/@aicoo/sharedos-core/src/agent-card.ts:175:    readAt: context.now,
sharedos/node_modules/@aicoo/sharedos-contracts/src/capability.ts:52:    expiresAt: TimestampSchema.optional(),
sharedos/node_modules/@aicoo/sharedos-contracts/src/capability.ts:60:      constraints.expiresAt !== undefined &&
sharedos/node_modules/@aicoo/sharedos-contracts/src/capability.ts:61:      Date.parse(constraints.notBefore) > Date.parse(constraints.expiresAt)
sharedos/node_modules/@aicoo/sharedos-contracts/src/capability.ts:65:        message: "notBefore must not be after expiresAt",
sharedos/node_modules/@aicoo/sharedos-runtime/src/executor.ts:880:        now: context.now,
sharedos/node_modules/@aicoo/sharedos-mcp/README.md:30:  context: { traceId: request.context.traceId, now: request.context.now },
sharedos/node_modules/@aicoo/sharedos-mcp/README.md:62:`requiredCapability`, no `resolveRequirement`, no grants, no issuing authority,
sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts:115:        at: this.#context.now,
sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts:124:      requestedAt: this.#context.now,
sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts:179:export function kernelToolBridge(options: KernelToolBridgeOptions): McpToolInvoker {
sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts:191:          requestedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/internal.ts:374:  const expiresAt = parseTimestamp(grant.constraints.expiresAt);
sharedos/node_modules/@aicoo/sharedos-core/src/internal.ts:387:    (grant.constraints.expiresAt !== undefined && expiresAt === undefined) ||
sharedos/node_modules/@aicoo/sharedos-core/src/internal.ts:388:    (expiresAt !== undefined && expiryObservedAt >= expiresAt) ||
sharedos/node_modules/@aicoo/sharedos-core/src/delegation.ts:461:  const expiresAt = request?.expiresAt ?? parent.expiresAt;
sharedos/node_modules/@aicoo/sharedos-core/src/delegation.ts:465:    ...(expiresAt === undefined ? {} : { expiresAt }),
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:13:export type ConstraintEnvelopeField = "purposes" | "notBefore" | "expiresAt";
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:45:  if (!instantIsWithin(inner.expiresAt, outer.expiresAt, "end")) {
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:46:    return "expiresAt";
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:84:  let expiresAt: { readonly value: string; readonly at: number } | undefined;
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:105:    if (constraints.expiresAt !== undefined) {
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:106:      const at = parseTimestamp(constraints.expiresAt);
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:110:      if (expiresAt === undefined || at < expiresAt.at) {
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:111:        expiresAt = { value: constraints.expiresAt, at };
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:129:  if (notBefore !== undefined && expiresAt !== undefined && notBefore.at > expiresAt.at) {
sharedos/node_modules/@aicoo/sharedos-core/src/constraints.ts:136:    ...(expiresAt === undefined ? {} : { expiresAt: expiresAt.value }),
sharedos/node_modules/@aicoo/sharedos-core/src/tool-registry.ts:20:  readonly resolveRequirement?: (context: AccessContext, call: ToolCall) => CapabilityRequirement;
sharedos/node_modules/@aicoo/sharedos-core/src/tool-registry.ts:80:    const resolveRequirement = handler.resolveRequirement;
sharedos/node_modules/@aicoo/sharedos-core/src/tool-registry.ts:86:      ...(resolveRequirement === undefined
sharedos/node_modules/@aicoo/sharedos-core/src/tool-registry.ts:89:            resolveRequirement: (context: AccessContext, call: ToolCall) =>
sharedos/node_modules/@aicoo/sharedos-core/src/tool-registry.ts:90:              resolveRequirement(context, call),
sharedos/node_modules/@aicoo/sharedos-core/src/capability-request.ts:81:    requestedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/authorization.ts:453:    const admittedAt = parseTimestamp(context.now);
sharedos/node_modules/@aicoo/sharedos-core/src/authorization.ts:562:    const admittedAt = parseTimestamp(context.now);
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:161: * `resolveRequirement` builds the envelope the kernel then authorizes, and
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:189:    resolveRequirement(context, call) {
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:221:          context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:238:          context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:268:          context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:279:          context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/message-tool.ts:290:        completedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/authority.ts:261:      authority: { context, grants, snapshot: await this.#snapshot(grants, context.now) },
sharedos/node_modules/@aicoo/sharedos-core/src/published-tool.ts:40: * `requiredCapability`, `resolveRequirement`, and the handler itself never leave
sharedos/node_modules/@aicoo/sharedos-core/src/audit.ts:44:    at: context.now,
sharedos/node_modules/@aicoo/sharedos-contracts/src/tool.ts:179: * defined by what it omits. `requiredCapability`, `resolveRequirement`, grants,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:536:      requestedAt: context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:735:    const reach = await this.#authorizer.reach(subjectAuthority.authority, { now: context.now });
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:769:        { now: context.now },
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:813:    return this.#authorizer.reach(authority.authority, { now: context.now });
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:860:        { now: context.now },
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1040:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1053:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1087:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1100:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1112:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1137:            now: context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1165:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1201:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1212:        handler.resolveRequirement?.(context, parsedCall) ?? handler.definition.requiredCapability;
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1223:        context.now,
sharedos/node_modules/@aicoo/sharedos-core/src/kernel.ts:1249:        context.now,

exec
/bin/zsh -lc "sed -n '115,145p' arena/delivery-playbook.md; sed -n '1,120p' sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts; sed -n '180,220p' sharedos/node_modules/@aicoo/sharedos-mcp/src/bridge.ts; sed -n '355,405p' sharedos/node_modules/@aicoo/sharedos-core/src/internal.ts; git show HEAD"'^:fetchly/core.py | sed -n '"'175,210p'" in /Users/snorf/projects/sharednet
 succeeded in 0ms:
  -H "Authorization: Bearer $MEMBER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "DONE <buyer> — search \"<query>\": $JSON")"
```

### 3b. Upload a large result as a SharedNet artifact

```bash
uuid=$(uuidgen)
curl -s -X POST "$BASE/api/v1/artifacts" \
  -H "Authorization: Bearer $MEMBER_TOKEN" \
  -H "Content-Type: text/markdown" \
  -H "X-SharedNet-Filename: fetchly-research-<buyer>-$(date +%s).md" \
  -H "X-SharedNet-Room: $ROOM" \
  -H "Idempotency-Key: $uuid" \
  --data-binary @/tmp/fetchly-delivery.md > /tmp/fetchly-artifact.json
```

The response carries the artifact id (`art_…`) and **its link**. Post the link in the Room (nothing watches for a file — saying the link is required), plus a 1-2 line "key facts" summary.

---

## 4. Failure handling

Never fake a delivery. Report exactly what failed, retry once, then offer refund or alternative.

- [ ] **Report precisely** — tool, input, error from `/tmp/fetchly-err.txt` (403, timeout, no results). Don't invent output.
- [ ] **Retry once** — same command a second time.
- [ ] **If retry succeeds** — deliver normally, note "succeeded on retry".
- [ ] **If it still fails** — post failure, **offer refund** (return the credits) **or an alternative** (different URL, narrower query, `summarize` of partial output, or the cited `results` only).
- [ ] **Partial success is delivery** — `research` pages that fail come back as `{title,url,error}`; `search` with `count: 0` is a valid answer.
import type {
  AccessContext,
  SharedOSToolCatalog,
  ToolCall,
  ToolDefinition,
  ToolResult,
} from "@aicoo/sharedos-contracts";
import { buildToolCatalog } from "@aicoo/sharedos-core";

import type { McpToolInvocation, McpToolInvoker } from "./server.js";

/**
 * The effectful surface a bridge is allowed to reach.
 *
 * Structurally satisfied by `RuntimeHost`, which is the intended binding: a
 * bridge opened inside a turn puts every `tools/call` through the execution
 * envelope, so the call is counted against the turn's `maxToolCalls`, checked
 * against the effective catalogue, and re-authorized by the kernel -- the same
 * path a native runtime's calls take, with no second enforcement path added for
 * MCP. A harness keeps its own loop and declares no step, so `maxSteps` does not
 * apply on this path: it is bounded by calls.
 *
 * Declared structurally rather than imported so this package does not depend on
 * the runtime package. The dependency would be harmless; the absence is the
 * point, because it makes it impossible for a bridge to reach any part of the
 * turn machinery other than the one method that re-authorizes.
 */
export interface BridgeToolInvoker {
  invokeTool(call: ToolCall): Promise<ToolResult>;
}

/** What the bridge needs of the turn's sanitised context: identity, not authority. */
export interface BridgeTurnContext {
  readonly traceId: string;
  readonly now: string;
}

/** One harness-side rewrite, kept for diagnosis and never for authorization. */
export interface ToolAliasRecord {
  readonly alias: string;
  readonly tool: string;
  readonly at: string;
}

export interface OpenToolBridgeOptions {
  readonly executionId: string;
  readonly context: BridgeTurnContext;
  /** The permission-filtered catalogue this turn resolved. */
  readonly tools: readonly ToolDefinition[];
  readonly host: BridgeToolInvoker;
}

/**
 * A turn-scoped MCP tool broker.
 *
 * The lifecycle is the whole design. `ContextToolProvider` exists so one user's
 * MCP catalogue never mutates a registry shared with concurrent users, and this
 * carries that invariant across the harness boundary: the catalogue is computed
 * for one `AccessContext`, exposed for the length of one turn, and torn down
 * with it. There is no long-lived SharedOS MCP server holding a union of every
 * user's tools, because such a server would have to re-derive who is asking on
 * every call, and would be wrong once.
 *
 * After {@link close}, the bridge answers nothing. A harness process that
 * outlives its turn -- and they do, on cancellation and on timeout -- finds a
 * door that is shut rather than one that still opens onto a turn that has ended.
 */
export class SharedOSToolBridge implements McpToolInvoker {
  readonly #executionId: string;
  readonly #context: BridgeTurnContext;
  readonly #host: BridgeToolInvoker;
  readonly #tools: readonly ToolDefinition[];
  readonly #aliases: ToolAliasRecord[] = [];
  #catalog: Promise<SharedOSToolCatalog> | undefined;
  #closed = false;

  constructor(options: OpenToolBridgeOptions) {
    this.#executionId = options.executionId;
    this.#context = options.context;
    this.#host = options.host;
    this.#tools = [...options.tools];
  }

  /**
   * Names the harness rewrote, in the order they were seen.
   *
   * Carried here rather than on the `ToolCall` so it is structurally impossible
   * for an alias to reach the kernel. A host that wants the diagnostic detail in
   * its execution record reads it from the bridge afterwards; nothing on the
   * authorization path can read it at all.
   */
  get aliases(): readonly ToolAliasRecord[] {
    return [...this.#aliases];
  }

  get closed(): boolean {
    return this.#closed;
  }

  async catalog(signal: AbortSignal): Promise<SharedOSToolCatalog> {
    this.#assertOpen(signal);
    // Computed once. A catalogue that could change between `tools/list` and
    // `tools/call` would make `catalogHash` a claim about a moment rather than
    // about the turn.
    this.#catalog ??= buildToolCatalog(this.#tools, { executionId: this.#executionId });
    return this.#catalog;
  }

  async invoke(invocation: McpToolInvocation, signal: AbortSignal): Promise<ToolResult> {
    this.#assertOpen(signal);
    if (invocation.alias !== undefined) {
      this.#aliases.push({
        alias: invocation.alias,
        tool: invocation.tool,
        at: this.#context.now,
      });
    }

    const call: ToolCall = {
      id: invocation.callId,
  const { kernel, context, executionId } = options;
  return {
    catalog: (signal) => kernel.listPublishedTools(context, { signal, executionId }),
    invoke: (invocation, signal) =>
      kernel.invokeTool(
        context,
        {
          id: invocation.callId,
          tool: invocation.tool,
          arguments: invocation.arguments,
          traceId: context.traceId,
          requestedAt: context.now,
        },
        { signal },
      ),
  };
}
 * An unparsable declared timestamp is treated as inactive so a malformed grant
 * can never outlive a well-formed one.
 */
export function grantIsActive(grant: CapabilityGrant, purpose: string, at: GrantInstants): boolean {
  return grantInactiveReason(grant, purpose, at) === undefined;
}

/**
 * Which of the two activity conditions a grant failed, for the host-facing
 * explanation. `grantIsActive` is this function's only other caller, so the
 * decision and the account of it can never disagree.
 */
export function grantInactiveReason(
  grant: CapabilityGrant,
  purpose: string,
  at: GrantInstants,
): "window" | "purpose" | undefined {
  const issuedAt = parseTimestamp(grant.issuedAt);
  const notBefore = parseTimestamp(grant.constraints.notBefore);
  const expiresAt = parseTimestamp(grant.constraints.expiresAt);
  const revokedAt = parseTimestamp(grant.revokedAt);
  // The later of the two instants, which is normally the operation's. Taking
  // the maximum rather than the operation instant alone means a host whose
  // clock runs backwards cannot revive an expired grant by presenting an
  // earlier instant than the one its turn was admitted at.
  const expiryObservedAt = Math.max(at.admittedAt, at.now);

  if (
    issuedAt === undefined ||
    issuedAt > at.admittedAt ||
    (grant.constraints.notBefore !== undefined && notBefore === undefined) ||
    (notBefore !== undefined && at.admittedAt < notBefore) ||
    (grant.constraints.expiresAt !== undefined && expiresAt === undefined) ||
    (expiresAt !== undefined && expiryObservedAt >= expiresAt) ||
    (grant.revokedAt !== undefined && revokedAt === undefined) ||
    (revokedAt !== undefined && at.admittedAt >= revokedAt)
  ) {
    return "window";
  }

  const purposes = grant.constraints.purposes;
  return purposes === undefined || purposes.includes(purpose) ? undefined : "purpose";
}
                "url": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(title.replace(" ", "_")),
                "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
            }
        )
    return out


def search(query: str, limit: int = 8) -> dict[str, Any]:
    """Search the web (Bing, Wikipedia fallback) and return cited results."""
    results = _search_bing(query, limit)
    if not results:
        results = _search_wikipedia(query, limit)
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

exec
/bin/zsh -lc "ls .venv/bin/fetchly 2>/dev/null; .venv/bin/python - <<'PY'
import inspect
from mcp.server.fastmcp import FastMCP
print('mcp',FastMCP)
PY
nl -ba README.md | sed -n '10,110p'; cat .gitignore 2>/dev/null" in /Users/snorf/projects/sharednet
 succeeded in 170ms:
mcp <class 'mcp.server.fastmcp.server.FastMCP'>
    10	
    11	| Tool | What you get |
    12	| --- | --- |
    13	| `fetch <url>` | Clean Markdown of a page + title + extracted links |
    14	| `search <query>` | Web results with title / url / snippet (cited sources) |
    15	| `research <query>` | Search, then fetch the top pages and return clean Markdown |
    16	| `summarize <text-or-url>` | Extractive summary (top sentences, no API key) |
    17	| `mcp` | Start the MCP server so any MCP client can call the tools |
    18	
    19	## Install
    20	
    21	Requires Python 3.10+.
    22	
    23	```bash
    24	pip install 'git+https://github.com/snorfyang/fetchly.git'
    25	fetchly fetch https://example.com
    26	```
    27	
    28	To develop from a clone instead:
    29	
    30	```bash
    31	git clone https://github.com/snorfyang/fetchly
    32	cd fetchly
    33	python3 -m venv .venv && .venv/bin/pip install -e .
    34	```
    35	
    36	## Use as a CLI (any Agent can run this)
    37	
    38	```bash
    39	fetchly fetch https://example.com
    40	fetchly search "model context protocol" --limit 5
    41	fetchly research "sharednet agent room" --limit 3
    42	fetchly summarize https://example.com --sentences 3
    43	```
    44	
    45	The four data commands print JSON to stdout — an Agent can parse it
    46	directly. Exact shapes:
    47	
    48	- `fetch` -> `{url, title, markdown, author, date, description, language, site, links, link_count}` (metadata may be null, markdown may be truncated)
    49	- `search` -> `{query, results: [{source, title, url, snippet}], count}`
    50	- `research` -> `{query, results, pages: [{title, url, markdown} | {title, url, error}]}`
    51	- `summarize` -> `{sentences, summary}`
    52	
    53	`fetchly mcp` is the exception: it starts a persistent stdio server, not a JSON
    54	one-shot.
    55	
    56	## Use as an MCP server (Claude / ChatGPT / Cursor / Codex …)
    57	
    58	Add this to the client's MCP config:
    59	
    60	```json
    61	{
    62	  "mcpServers": {
    63	    "fetchly": {
    64	      "command": "fetchly",
    65	      "args": ["mcp"]
    66	    }
    67	  }
    68	}
    69	```
    70	
    71	The server exposes four tools: `fetch_url`, `search`, `research`, `summarize`.
    72	
    73	## Use over HTTP (no install needed)
    74	
    75	Start the server, then any agent can call it with curl:
    76	
    77	```bash
    78	fetchly serve --host 0.0.0.0 --port 8000
    79	
    80	curl http://localhost:8000/health
    81	curl 'http://localhost:8000/search?q=model+context+protocol&limit=5'
    82	curl 'http://localhost:8000/fetch?url=https://example.com'
    83	curl -X POST http://localhost:8000/summarize \
    84	  -H 'Content-Type: application/json' \
    85	  -d '{"text":"…or a URL…","sentences":5}'
    86	```
    87	
    88	Routes: `GET /health`, `GET /fetch`, `GET /search`, `POST /research`, `POST /summarize`. All return JSON.
    89	
    90	## Try it now (remote install, one command)
    91	
    92	```bash
    93	pip install 'git+https://github.com/snorfyang/fetchly.git' && fetchly search "model context protocol" --limit 3
    94	```
    95	
    96	## SharedOS integration (optional track)
    97	
    98	fetchly's tools are also gated by [SharedOS](https://sharedos.ai) — a
    99	permission layer that denies-by-default and re-authorizes every tool call.
   100	See [`sharedos/`](sharedos/README.md) for the kernel setup, grant, demo, and
   101	the MCP server (`sharedos/index.js`).
   102	
   103	```bash
   104	cd sharedos && npm install
   105	FETCHLY_BIN=../.venv/bin/fetchly node demo.js
   106	```
   107	
   108	## Project layout
   109	
   110	```
# local secrets — never commit
.sharednet-env
.env

# python
.venv/
__pycache__/
*.pyc
*.egg-info/
dist/
build/

# node
node_modules/
arena/.lastseq

exec
/bin/zsh -lc "rg -n 'output_schema|return_annotation|return_type|model_validate' .venv/lib/python*/site-packages/mcp/server/fastmcp/tools | head -50; .venv/bin/python - <<'PY'
from mcp.server.fastmcp import FastMCP
m=FastMCP('x')
@m.tool()
def search(query:str)->list:
 return {'query':query,'results':[],'count':0}
print(m._tool_manager.list_tools()[0])
import asyncio
async def go():
 try: print(await m.call_tool('search',{'query':'hi'}))
 except Exception as e: print(type(e).__name__,str(e))
asyncio.run(go())
PY" in /Users/snorf/projects/sharednet
 succeeded in 108ms:
fn=<function search at 0x102c10180> name='search' title=None description='' parameters={'properties': {'query': {'title': 'Query', 'type': 'string'}}, 'required': ['query'], 'title': 'searchArguments', 'type': 'object'} fn_metadata=FuncMetadata(arg_model=<class 'mcp.server.fastmcp.utilities.func_metadata.searchArguments'>, output_schema=None, output_model=None, wrap_output=False) is_async=False context_kwarg=None annotations=None icons=None meta=None
[TextContent(type='text', text='{\n  "query": "hi",\n  "results": [],\n  "count": 0\n}', annotations=None, meta=None)]

exec
/bin/zsh -lc ".venv/bin/python - <<'PY'
from fetchly.core import _search_bing,_search_wikipedia,search
for name,fn in [('bing',lambda:_search_bing('model context protocol',2)),('wiki',lambda:_search_wikipedia('model context protocol',2)),('search1',lambda:search('model context protocol',1))]:
 try:
  x=fn(); print(name,len(x) if isinstance(x,list) else x['count'],str(x)[:400])
 except Exception as e: print(name,type(e).__name__,str(e)[:200])
PY" in /Users/snorf/projects/sharednet
 exited 130 in 22354ms:
bing 2 [{'source': 'bing', 'title': 'What is the Model Context Protocol (MCP)?', 'url': 'https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro', 'snippet': 'Jul 28, 2026\u2002·\u2002MCP (Model Context Protocol) is an open-source standard for connecting AI applications to external systems. Read more'}, {'source': 'bing', 'title': 'MCP ( Model Context Protocol )，一篇就够了。 - 知乎', 'url': 'https:
Traceback (most recent call last):
  File "<stdin>", line 4, in <module>
  File "<stdin>", line 2, in <lambda>
  File "/Users/snorf/projects/sharednet/fetchly/core.py", line 157, in _search_wikipedia
    r = _get(
        "https://en.wikipedia.org/w/api.php",
    ...<6 lines>...
        },
    )
  File "/Users/snorf/projects/sharednet/fetchly/core.py", line 58, in _get
    r = requests.get(url, **kwargs)
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/requests/api.py", line 87, in get
    return request("get", url, params=params, **kwargs)
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/requests/api.py", line 71, in request
    return session.request(method=method, url=url, **kwargs)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/requests/sessions.py", line 651, in request
    resp = self.send(prep, **send_kwargs)
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/requests/sessions.py", line 784, in send
    r = adapter.send(request, **kwargs)
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/requests/adapters.py", line 696, in send
    resp = conn.urlopen(
        method=request.method,
    ...<9 lines>...
        chunked=chunked,
    )
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/connectionpool.py", line 793, in urlopen
    response = self._make_request(
        conn,
    ...<10 lines>...
        **response_kw,
    )
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/connectionpool.py", line 470, in _make_request
    self._validate_conn(conn)
    ~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/connectionpool.py", line 1125, in _validate_conn
    conn.connect()
    ~~~~~~~~~~~~^^
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/connection.py", line 878, in connect
    wrapped_socket, is_verified = _ssl_wrap_socket_and_match_hostname(
                                  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        sock=sock,
        ^^^^^^^^^^
    ...<14 lines>...
        assert_fingerprint=self.assert_fingerprint,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/connection.py", line 1080, in _ssl_wrap_socket_and_match_hostname
    ssl_sock = ssl_wrap_socket(
        sock=sock,
    ...<8 lines>...
        tls_in_tls=tls_in_tls,
    )
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/util/ssl_.py", line 437, in ssl_wrap_socket
    ssl_sock = _ssl_wrap_socket_impl(sock, context, tls_in_tls, server_hostname)
  File "/Users/snorf/projects/sharednet/.venv/lib/python3.13/site-packages/urllib3/util/ssl_.py", line 481, in _ssl_wrap_socket_impl
    return ssl_context.wrap_socket(sock, server_hostname=server_hostname)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/snorf/miniconda3/lib/python3.13/ssl.py", line 455, in wrap_socket
    return self.sslsocket_class._create(
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        sock=sock,
        ^^^^^^^^^^
    ...<5 lines>...
        session=session
        ^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/snorf/miniconda3/lib/python3.13/ssl.py", line 1076, in _create
    self.do_handshake()
    ~~~~~~~~~~~~~~~~~^^
  File "/Users/snorf/miniconda3/lib/python3.13/ssl.py", line 1372, in do_handshake
    self._sslobj.do_handshake()
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^
KeyboardInterrupt

exec
/bin/zsh -lc ".venv/bin/python - <<'PY'
from unittest.mock import patch
from fetchly import core
class R: content=b'<li class=\"b_algo\"><h2><a href=\"https://example.org\">Test</a></h2></li>'
with patch.object(core,'_get',return_value=R()):
 print(core._search_bing('x',0))
PY" in /Users/snorf/projects/sharednet
 succeeded in 151ms:
[{'source': 'bing', 'title': 'Test', 'url': 'https://example.org', 'snippet': ''}]

codex
The project has actionable security and delivery failures, including an unrestricted fetch endpoint, authorization that can outlive its grant, and Arena messages that can exceed the delivery cap. Search behavior also breaks or stalls under ordinary backend and limit conditions.

Full review comments:

- [P1] Block private-network targets in the public fetch API — /Users/snorf/projects/sharednet/fetchly/core.py:68-70
  When the documented `--host 0.0.0.0` deployment is used, any caller can pass a localhost, private-network, or cloud-metadata URL to `/fetch` and receive the response. `fetch_url` sends the URL directly to `requests`, which also follows redirects. Validate destinations, including redirect targets, before making requests.

- [P1] Refresh the authorization time for each SharedOS call — /Users/snorf/projects/sharednet/sharedos/index.js:73-78
  For a server left running beyond the grant's seven-day expiry, `context.now` remains fixed at startup. The SharedOS bridge passes that value into authorization on every call, so the expired grant continues to authorize tools. Supply a fresh time per request rather than reusing this startup context.

- [P1] Do not let Wikipedia delay healthy Bing results — /Users/snorf/projects/sharednet/fetchly/core.py:194-196
  When Bing succeeds but Wikipedia is slow or unavailable, every `search` call still waits for Wikipedia's two requests with 25-second timeouts before returning the Bing results. That can consume roughly 50 seconds of the 60-second SharedOS runner timeout and turn a successful search into a failed tool call. Bound or skip the enrichment independently of the primary results.

- [P1] Size the complete Arena message before posting — /Users/snorf/projects/sharednet/arena/deliver.py:143-150
  For a long `summarize` input, the result JSON can be below `INLINE_LIMIT` while the posted message exceeds the Room's 32 KB cap because it repeats the entire input outside `blob`. The artifact branch repeats that input too, so it cannot recover. Measure the complete message and omit or truncate the echoed input when delivering.

- [P1] Load the member ID from the process environment — /Users/snorf/projects/sharednet/arena/agent.py:47-50
  In an environment-only deployment, `load_env` reads `MEMBER_TOKEN` but not `MEMBER_ID`, leaving `my_id` empty. The listener then treats its own pitch message as someone else's; because that message contains “Pitch,” it posts another pitch repeatedly. Load or resolve the active member ID before handling messages.

- [P2] Honor zero-result Bing quotas — /Users/snorf/projects/sharednet/fetchly/core.py:150-152
  With `search(..., limit=1)`, `bing_limit` is zero, but `_search_bing` appends a result before checking the limit. The resulting Bing hit fills the only slot and prevents the reserved Wikipedia result; `limit=0` can likewise return a hit. Return immediately for a nonpositive backend limit, or check before appending.

- [P2] Decode HTML with its detected charset in the fallback — /Users/snorf/projects/sharednet/fetchly/core.py:88-89
  When trafilatura extracts no main content from a GBK or GB2312 page, the fallback decodes `r.content` as UTF-8 with replacement before converting it to Markdown. Non-UTF-8 text becomes corrupted even though the HTML parser can detect its charset. Decode using the page's detected encoding before calling `markdownify`.

- [P2] Make the advertised dry run non-effectful — /Users/snorf/projects/sharednet/arena/agent.py:134-138
  When an operator runs `agent.py --once` as the module's documented “dry run,” `catch_up()` still executes pending orders and posts deliveries before the flag is checked. That can spend work or duplicate a delivery during a connectivity check. Either make this mode read-only or stop describing it as a dry run.
The project has actionable security and delivery failures, including an unrestricted fetch endpoint, authorization that can outlive its grant, and Arena messages that can exceed the delivery cap. Search behavior also breaks or stalls under ordinary backend and limit conditions.

Full review comments:

- [P1] Block private-network targets in the public fetch API — /Users/snorf/projects/sharednet/fetchly/core.py:68-70
  When the documented `--host 0.0.0.0` deployment is used, any caller can pass a localhost, private-network, or cloud-metadata URL to `/fetch` and receive the response. `fetch_url` sends the URL directly to `requests`, which also follows redirects. Validate destinations, including redirect targets, before making requests.

- [P1] Refresh the authorization time for each SharedOS call — /Users/snorf/projects/sharednet/sharedos/index.js:73-78
  For a server left running beyond the grant's seven-day expiry, `context.now` remains fixed at startup. The SharedOS bridge passes that value into authorization on every call, so the expired grant continues to authorize tools. Supply a fresh time per request rather than reusing this startup context.

- [P1] Do not let Wikipedia delay healthy Bing results — /Users/snorf/projects/sharednet/fetchly/core.py:194-196
  When Bing succeeds but Wikipedia is slow or unavailable, every `search` call still waits for Wikipedia's two requests with 25-second timeouts before returning the Bing results. That can consume roughly 50 seconds of the 60-second SharedOS runner timeout and turn a successful search into a failed tool call. Bound or skip the enrichment independently of the primary results.

- [P1] Size the complete Arena message before posting — /Users/snorf/projects/sharednet/arena/deliver.py:143-150
  For a long `summarize` input, the result JSON can be below `INLINE_LIMIT` while the posted message exceeds the Room's 32 KB cap because it repeats the entire input outside `blob`. The artifact branch repeats that input too, so it cannot recover. Measure the complete message and omit or truncate the echoed input when delivering.

- [P1] Load the member ID from the process environment — /Users/snorf/projects/sharednet/arena/agent.py:47-50
  In an environment-only deployment, `load_env` reads `MEMBER_TOKEN` but not `MEMBER_ID`, leaving `my_id` empty. The listener then treats its own pitch message as someone else's; because that message contains “Pitch,” it posts another pitch repeatedly. Load or resolve the active member ID before handling messages.

- [P2] Honor zero-result Bing quotas — /Users/snorf/projects/sharednet/fetchly/core.py:150-152
  With `search(..., limit=1)`, `bing_limit` is zero, but `_search_bing` appends a result before checking the limit. The resulting Bing hit fills the only slot and prevents the reserved Wikipedia result; `limit=0` can likewise return a hit. Return immediately for a nonpositive backend limit, or check before appending.

- [P2] Decode HTML with its detected charset in the fallback — /Users/snorf/projects/sharednet/fetchly/core.py:88-89
  When trafilatura extracts no main content from a GBK or GB2312 page, the fallback decodes `r.content` as UTF-8 with replacement before converting it to Markdown. Non-UTF-8 text becomes corrupted even though the HTML parser can detect its charset. Decode using the page's detected encoding before calling `markdownify`.

- [P2] Make the advertised dry run non-effectful — /Users/snorf/projects/sharednet/arena/agent.py:134-138
  When an operator runs `agent.py --once` as the module's documented “dry run,” `catch_up()` still executes pending orders and posts deliveries before the flag is checked. That can spend work or duplicate a delivery during a connectivity check. Either make this mode read-only or stop describing it as a dry run.
