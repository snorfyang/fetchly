# fetchly

**One link, any Agent can use.** fetchly turns any URL into clean Markdown and
does web search with cited sources — callable from the CLI or as an MCP server.

> Built during SharedNet "Trial Zero" (Sep 2026) with Agent collaboration in
> Room `rom_tcOaPPIwWJ`.

## What it does

| Tool | What you get |
| --- | --- |
| `fetch <url>` | Clean Markdown of a page + title + extracted links |
| `search <query>` | Web results with title / url / snippet (cited sources) |
| `research <query>` | Search, then fetch the top pages and return clean Markdown |
| `summarize <text-or-url>` | Extractive summary (top sentences, no API key) |
| `mcp` | Start the MCP server so any MCP client can call the tools |

## Install

Requires Python 3.10+.

```bash
pip install 'git+https://github.com/snorfyang/fetchly.git'
fetchly fetch https://example.com
```

To develop from a clone instead:

```bash
git clone https://github.com/snorfyang/fetchly
cd fetchly
python3 -m venv .venv && .venv/bin/pip install -e .
```

## Use as a CLI (any Agent can run this)

```bash
fetchly fetch https://example.com
fetchly search "model context protocol" --limit 5
fetchly research "sharednet agent room" --limit 3
fetchly summarize https://example.com --sentences 3
```

The four data commands print JSON to stdout — an Agent can parse it
directly. Exact shapes:

- `fetch` -> `{url, title, markdown, author, date, description, language, site, links, link_count}` (metadata may be null, markdown may be truncated)
- `search` -> `{query, results: [{source, title, url, snippet}], count}`
- `research` -> `{query, results, pages: [{title, url, markdown} | {title, url, error}]}`
- `summarize` -> `{sentences, summary}`

`fetchly mcp` is the exception: it starts a persistent stdio server, not a JSON
one-shot.

## Use as an MCP server (Claude / ChatGPT / Cursor / Codex …)

Add this to the client's MCP config:

```json
{
  "mcpServers": {
    "fetchly": {
      "command": "fetchly",
      "args": ["mcp"]
    }
  }
}
```

The server exposes four tools: `fetch_url`, `search`, `research`, `summarize`.

## Use over HTTP (no install needed)

Start the server, then any agent can call it with curl:

```bash
fetchly serve --host 0.0.0.0 --port 8000

curl http://localhost:8000/health
curl 'http://localhost:8000/search?q=model+context+protocol&limit=5'
curl 'http://localhost:8000/fetch?url=https://example.com'
curl -X POST http://localhost:8000/summarize \
  -H 'Content-Type: application/json' \
  -d '{"text":"…or a URL…","sentences":5}'
```

Routes: `GET /health`, `GET /fetch`, `GET /search`, `POST /research`, `POST /summarize`. All return JSON.

## Try it now (remote install, one command)

```bash
pip install 'git+https://github.com/snorfyang/fetchly.git' && fetchly search "model context protocol" --limit 3
```

## SharedOS integration (optional track)

fetchly's tools are also gated by [SharedOS](https://sharedos.ai) — a
permission layer that denies-by-default and re-authorizes every tool call.
See [`sharedos/`](sharedos/README.md) for the kernel setup, grant, demo, and
the MCP server (`sharedos/index.js`).

```bash
cd sharedos && npm install
FETCHLY_BIN=../.venv/bin/fetchly node demo.js
```

## Project layout

```
fetchly/
  core.py        # fetch / search / research / summarize logic
  cli.py         # CLI entry point
  mcp_server.py  # MCP stdio server (4 tools)
sharedos/
  index.js       # fetchly tools gated by SharedOS, served over MCP
  demo.js        # authorization demo (filtered catalog, deny-by-default)
  lib/tools.js   # SharedOS tool handlers
  lib/runner.js  # shells out to the fetchly CLI
pyproject.toml
```

## Notes

- `search` uses the Bing HTML endpoint (en-US market), enriched with Wikipedia
  citations, so no API key is needed.
- `fetch` uses trafilatura + charset detection, so GBK/UTF-8 pages both come
  back clean.
- `summarize` is extractive (keyword-frequency scoring), so it needs no LLM.
