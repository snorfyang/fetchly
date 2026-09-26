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

> Note: the SharedOS check authorizes the *initial* URL host. The underlying
> CLI `fetch` follows redirects; redirect-target host re-authorization is not
> wired through SharedOS yet (the standalone HTTP API does re-check every hop).
| Grant | `web` / actions `fetch,search,research,summarize` / scope `descendants` / purpose `research` |
| AccessContext | actor = `fetchly-agent`, authority/owner = `snorf`, purpose `research` |
