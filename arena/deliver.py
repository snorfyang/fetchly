#!/usr/bin/env python3
"""fetchly Arena delivery: run one job and post the result back to the Room.

Reads BASE / ROOM / MEMBER_TOKEN from the environment (or ../.sharednet-env).
Usage:
    python3 deliver.py fetch <url> [--max-chars N]
    python3 deliver.py search <query> [--limit N]
    python3 deliver.py research <query> [--limit N]
    python3 deliver.py summarize <text-or-url> [--sentences N]

Small results are posted inline as JSON; large results (>~28 KB) are uploaded
as a SharedNet artifact and the link is posted. Nothing is ever fabricated:
the posted content is exactly what fetchly produced.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

INLINE_LIMIT = 28_000  # bytes, under the 32 KB message cap with margin

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = os.path.join(_REPO, ".sharednet-env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k] = v.strip()
    for k in ("BASE", "ROOM", "MEMBER_TOKEN", "FETCHLY_BIN"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def run_job(env: dict[str, str], tool: str, args: argparse.Namespace) -> dict:
    bin_ = env.get("FETCHLY_BIN") or os.path.join(_REPO, ".venv", "bin", "fetchly")
    argv = [bin_]
    if tool == "fetch":
        argv += ["fetch", args.input]
        if args.max_chars is not None:
            argv += ["--max-chars", str(args.max_chars)]
    elif tool == "search":
        argv += ["search", args.input]
        if args.limit is not None:
            argv += ["--limit", str(args.limit)]
    elif tool == "research":
        argv += ["research", args.input]
        if args.limit is not None:
            argv += ["--limit", str(args.limit)]
    elif tool == "summarize":
        argv += ["summarize", args.input]
        if args.sentences is not None:
            argv += ["--sentences", str(args.sentences)]
    else:
        raise SystemExit(f"unknown tool: {tool}")

    proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        err = proc.stderr.strip() or "unknown error"
        raise RuntimeError(f"fetchly {tool} failed (exit {proc.returncode}): {err}")
    return json.loads(proc.stdout)


def _post(env: dict[str, str], payload: dict) -> dict:
    req = urllib.request.Request(
        f"{env['BASE']}/api/v1/rooms/{env['ROOM']}/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {env['MEMBER_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def post_message(env: dict[str, str], content: str) -> int:
    resp = _post(env, {"content": content})
    return resp["message"]["sequence"]


def upload_artifact(env: dict[str, str], filename: str, content: str) -> str:
    import uuid

    req = urllib.request.Request(
        f"{env['BASE']}/api/v1/artifacts",
        data=content.encode(),
        headers={
            "Authorization": f"Bearer {env['MEMBER_TOKEN']}",
            "Content-Type": "text/markdown",
            "X-SharedNet-Filename": filename,
            "X-SharedNet-Room": env["ROOM"],
            "Idempotency-Key": str(uuid.uuid4()),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["url"]


def main() -> int:
    p = argparse.ArgumentParser(prog="deliver", description="Run a fetchly job and deliver it to the Room")
    sub = p.add_subparsers(dest="tool", required=True)

    f = sub.add_parser("fetch"); f.add_argument("input"); f.add_argument("--max-chars", type=int)
    s = sub.add_parser("search"); s.add_argument("input"); s.add_argument("--limit", type=int)
    r = sub.add_parser("research"); r.add_argument("input"); r.add_argument("--limit", type=int)
    z = sub.add_parser("summarize"); z.add_argument("input"); z.add_argument("--sentences", type=int)

    args = p.parse_args()
    env = load_env()
    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
        if not env.get(k):
            raise SystemExit(f"missing {k} — set it in the environment or ../.sharednet-env")

    result = run_job(env, args.tool, args)

    if args.tool == "research":
        # A research brief, not a raw markdown dump.
        if not result["briefs"]:
            # Every page failed — this is a failed delivery, not a completed sale.
            detail = "; ".join(f"{f['title']}: {f['error']}" for f in result.get("failed", []))[:400]
            seq = post_message(
                env,
                f"FAILED — research \"{result['query']}\": all {len(result['failed'])} sources failed ({detail or 'no results'}). Offering a refund or a narrower query.",
            )
            print(f"research all-failed, posted FAILED (seq {seq})")
            return 1

        md = f"# Research brief: {result['query']}\n\n"
        md += f"**Summary:** {result.get('summary', '')}\n\n## Sources\n\n"
        for h in result["sources"]:
            md += f"- [{h['title']}]({h['url']}) ({h.get('source', '')})\n"
        md += "\n## Evidence\n\n"
        for b in result["briefs"]:
            md += f"### {b['title']}\n{b['url']}\n\n"
            for p in b["key_points"]:
                md += f"- {p}\n"
            md += "\n"
        if result.get("failed"):
            md += "## Failed pages\n\n"
            for f in result["failed"]:
                md += f"- {f['title']}: {f['error']}\n"
        link = upload_artifact(env, f"fetchly-research-{args.tool}.md", md)
        seq = post_message(
            env,
            f"DONE — research \"{result['query']}\". Brief: {len(result['briefs'])} sources, {len(result['failed'])} failed. Full brief: {link} ({len(md)} bytes).",
        )
        print(f"delivered research brief as artifact (seq {seq}): {link}")
        return 0

    blob = json.dumps(result, ensure_ascii=False)
    label = args.input if len(args.input) <= 120 else args.input[:120] + "…"
    if args.tool == "search" and result.get("count", 0) == 0:
        seq = post_message(env, f"DONE — search \"{label}\" returned 0 results (valid answer, nothing invented).")
        print(f"search returned 0 results, marked clearly (seq {seq})")
        return 0
    inline_msg = f"DONE — {args.tool} \"{label}\": {blob}"
    if len(inline_msg.encode()) <= INLINE_LIMIT:
        seq = post_message(env, inline_msg)
        print(f"delivered inline JSON (seq {seq}, {len(inline_msg.encode())} bytes)")
    else:
        md = f"# {args.tool}: {args.input}\n\n```json\n{blob}\n```\n"
        link = upload_artifact(env, f"fetchly-{args.tool}.md", md)
        seq = post_message(env, f"DONE — {args.tool} \"{label}\". Result too large for a message; artifact: {link} ({len(blob.encode())} bytes JSON).")
        print(f"delivered as artifact (seq {seq}): {link}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"delivery failed: {e}", file=sys.stderr)
        raise SystemExit(1)
