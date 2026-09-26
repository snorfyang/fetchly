#!/usr/bin/env python3
"""fetchly Arena autopilot.

Listens to the SharedNet Room and responds conservatively:
  - pitch requests  -> posts arena/pitch.md
  - explicit orders -> runs the job and delivers via deliver.py logic

Safe by design: it only acts on clear triggers, never fabricates output, and
never posts the token. The primary Arena operator should still be an LLM agent
reading the Room and calling deliver.py directly; this autopilot is the
mechanical fallback for the order-taking loop.

Usage:
    python3 agent.py [--once]     # --once: catch up once and exit (dry run)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELIVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deliver.py")
PITCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pitch.md")

PITCH_TRIGGERS = ("introduce", "present", "pitch", "what do you do", "who are you", "介绍", "自我介绍")
ORDER_PATTERNS = [
    re.compile(r"^\s*(fetch)\s+(https?://\S+)\s*$", re.I),
    re.compile(r"^\s*(search|research|summarize)\s+(.+?)\s*$", re.I),
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = os.path.join(REPO, ".sharednet-env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip()
    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def api(env: dict[str, str], path: str, method="GET", payload=None, timeout=30):
    req = urllib.request.Request(
        f"{env['BASE']}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {env['MEMBER_TOKEN']}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post(env: dict[str, str], content: str) -> int:
    return api(env, f"/api/v1/rooms/{env['ROOM']}/messages", "POST", {"content": content})["message"]["sequence"]


def wait(env: dict[str, str], after: int) -> dict:
    return api(env, f"/api/v1/rooms/{env['ROOM']}/wait?after={after}", timeout=40)


def handle_message(env: dict[str, str], seq: int, sender_id: str, sender_name: str, text: str, my_id: str) -> None:
    if sender_id == my_id:
        return
    low = text.lower()

    if any(t in low for t in PITCH_TRIGGERS):
        pitch = open(PITCH, encoding="utf-8").read()
        s = post(env, pitch)
        print(f"[{seq}] pitch requested by {sender_name} -> posted pitch (seq {s})")
        return

    for m in ORDER_PATTERNS:
        mm = m.match(text.strip())
        if mm:
            tool, arg = mm.group(1).lower(), mm.group(2).strip()
            print(f"[{seq}] order from {sender_name}: {tool} \"{arg}\" -> delivering")
            r = subprocess.run(
                [sys.executable, DELIVER, tool, arg],
                capture_output=True, text=True, timeout=180,
                env={**os.environ, **env},
            )
            if r.returncode != 0:
                post(env, f"DELIVERY FAILED for {tool} \"{arg}\": {r.stderr.strip()[:500]}")
            print(f"[{seq}] deliver exit {r.returncode}: {r.stdout.strip()[:120]}")
            return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="catch up once and exit")
    args = ap.parse_args()

    env = load_env()
    for k in ("BASE", "ROOM", "MEMBER_TOKEN"):
        if not env.get(k):
            raise SystemExit(f"missing {k}")

    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".lastseq")
    last_seq = 0
    if os.path.exists(state_path):
        try:
            last_seq = int(open(state_path).read().strip())
        except ValueError:
            last_seq = 0

    my_id = env.get("MEMBER_ID", "")

    def persist():
        open(state_path, "w").write(str(last_seq))

    def catch_up():
        nonlocal last_seq
        # process any unhandled messages, oldest first
        history = api(env, f"/api/v1/rooms/{env['ROOM']}/messages?limit=100&order=asc")
        for m in history.get("items", []):
            seq = m["sequence"]
            if seq > last_seq:
                last_seq = seq
                s = m["sender"]
                handle_message(env, seq, s.get("member_id", s.get("instance_id", "")), s.get("name", ""), m.get("content", ""), my_id)
        persist()

    catch_up()
    print(f"listening on {env['ROOM']} from seq {last_seq} (my member: {my_id})")
    if args.once:
        print("caught up once; exiting")
        return 0

    while True:
        try:
            page = wait(env, last_seq)
        except Exception as e:  # noqa: BLE001
            print(f"wait error: {e}; retrying in 5s", file=sys.stderr)
            time.sleep(5)
            continue

        for m in page.get("items", []):
            seq = m["sequence"]
            if seq > last_seq:
                last_seq = seq
            s = m["sender"]
            handle_message(env, seq, s.get("member_id", s.get("instance_id", "")), s.get("name", ""), m.get("content", ""), my_id)
        persist()


if __name__ == "__main__":
    raise SystemExit(main())
