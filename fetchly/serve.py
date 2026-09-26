"""fetchly HTTP API — expose fetch/search/research/summarize over plain HTTP.

Runs on stdlib only (no extra deps). Any agent can call it with curl:

    GET  /health
    GET  /fetch?url=https://example.com&max_chars=40000
    GET  /search?q=model+context+protocol&limit=8
    POST /research  {"query":"...","limit":3}
    POST /summarize {"text":"... or url","sentences":5}

Every route returns JSON.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import core


def _scalar(params: dict[str, Any], key: str, default: Any = None) -> Any:
    v = params.get(key, default)
    if isinstance(v, list):
        return v[0] if v else default
    return v


class _Handler(BaseHTTPRequestHandler):
    server_version = "fetchly/0.2"

    def _send(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _params(self) -> dict[str, Any]:
        parsed = urlparse(self.path)
        params: dict[str, Any] = {}
        for k, v in parse_qs(parsed.query).items():
            params[k] = v
        if self.command == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                body = json.loads(self.rfile.read(length) or b"{}")
                if isinstance(body, dict):
                    params.update(body)
        return params

    def _route(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path in ("/", "/health"):
                return self._send(200, {
                    "ok": True,
                    "service": "fetchly",
                    "version": core.__version__,
                    "tools": ["fetch", "search", "research", "summarize"],
                    "usage": {
                        "fetch": "GET /fetch?url=...&max_chars=N",
                        "search": "GET /search?q=...&limit=N",
                        "research": "POST /research {\"query\":...,\"limit\":N}",
                        "summarize": "POST /summarize {\"text\":...,\"sentences\":N}",
                    },
                })

            p = self._params()

            if path == "/fetch":
                url = _scalar(p, "url")
                if not url:
                    return self._send(400, {"error": "missing url"})
                mc = _scalar(p, "max_chars")
                return self._send(200, core.fetch_url(str(url), max_chars=int(mc) if mc else 40000))

            if path == "/search":
                q = _scalar(p, "q") or _scalar(p, "query")
                if not q:
                    return self._send(400, {"error": "missing q"})
                lim = _scalar(p, "limit")
                return self._send(200, core.search(str(q), limit=int(lim) if lim else 8))

            if path == "/research":
                q = _scalar(p, "q") or _scalar(p, "query")
                if not q:
                    return self._send(400, {"error": "missing q"})
                lim = _scalar(p, "limit")
                return self._send(200, core.research(str(q), limit=int(lim) if lim else 3))

            if path == "/summarize":
                text = _scalar(p, "text")
                if not text:
                    return self._send(400, {"error": "missing text"})
                n = _scalar(p, "sentences")
                text = str(text)
                if text.startswith(("http://", "https://")):
                    text = core.fetch_url(text, max_chars=30000)["markdown"]
                return self._send(200, core.summarize(text, n=int(n) if n else 5))

            return self._send(404, {"error": f"unknown route {path}"})

        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})

    do_GET = _route
    do_POST = _route

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logging
        pass


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"fetchly serving on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
