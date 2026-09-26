"""fetchly CLI — one link, any Agent can use it.

Usage:
    fetchly fetch <url> [--max-chars N]   # URL -> clean Markdown + links
    fetchly search <query> [--limit N]    # web search with cited sources
    fetchly research <query> [--limit N]  # search + fetch top pages
    fetchly mcp                           # start the MCP server (stdio)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import core


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fetchly", description="Agent-callable web fetch & search service")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch a URL to clean Markdown")
    f.add_argument("url")
    f.add_argument("--max-chars", type=int, default=40000)

    s = sub.add_parser("search", help="web search with cited sources")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=8)

    r = sub.add_parser("research", help="search then produce a compact research brief")
    r.add_argument("query")
    r.add_argument("--limit", type=int, default=3)

    z = sub.add_parser("summarize", help="extractive summary of text (or a URL)")
    z.add_argument("text_or_url")
    z.add_argument("--sentences", type=int, default=5)

    sub.add_parser("mcp", help="start the stdio MCP server")

    srv = sub.add_parser("serve", help="start the HTTP API server")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)

    args = p.parse_args(argv)

    try:
        if args.cmd == "fetch":
            _out(core.fetch_url(args.url, max_chars=args.max_chars))
        elif args.cmd == "search":
            _out(core.search(args.query, limit=args.limit))
        elif args.cmd == "research":
            _out(core.research(args.query, limit=args.limit))
        elif args.cmd == "summarize":
            text = args.text_or_url
            if text.startswith(("http://", "https://")):
                text = core.fetch_url(text, max_chars=30000)["markdown"]
            _out(core.summarize(text, n=args.sentences))
        elif args.cmd == "mcp":
            from .mcp_server import run

            run()
        elif args.cmd == "serve":
            from .serve import serve

            serve(host=args.host, port=args.port)
        else:
            p.print_help()
            return 2
    except Exception as exc:  # noqa: BLE001 - CLI should never traceback
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
