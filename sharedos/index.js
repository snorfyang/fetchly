// fetchly on SharedOS — the permission-controlled MCP server.
//
// Registers the fetchly web tools with a SharedOS kernel, issues a scoped
// grant, and serves the permission-filtered catalogue over MCP stdio.
//
// Deny by default: the `web.post` tool is registered but not granted, so it is
// invisible in the catalogue and refused on call. Every `tools/call` is
// re-authorized by the kernel against the exact resource derived from the
// arguments — discovery is not permission.
import { randomUUID } from "node:crypto";

import {
  CapabilityAuthorizer,
  InMemoryGrantUsageStore,
  SharedOSKernel,
} from "@aicoo/sharedos";
import { McpToolServer } from "@aicoo/sharedos-mcp";
import { serveMcpOverStdio } from "@aicoo/sharedos-mcp/node";

import { fetchlyTools } from "./lib/tools.js";

const NAMESPACE_ID = process.env.SHAREDOS_NAMESPACE_ID ?? "fetchly";
const PURPOSE = process.env.SHAREDOS_PURPOSE ?? "research";

const owner = { kind: "human", userId: "snorf" };
const agent = { kind: "agent", agentId: "fetchly-agent" };

// The authority this deployment loads. The grant covers the four read tools,
// any host, for the stated purpose. `web.post` is deliberately absent.
const grant = {
  id: "grant-fetchly-web-read",
  namespaceId: NAMESPACE_ID,
  subject: agent,
  issuer: owner,
  capabilities: [
    {
      resource: { namespace: "web", path: [] },
      actions: ["fetch", "search", "research", "summarize"],
      scope: "descendants",
    },
  ],
  constraints: {
    purposes: [PURPOSE],
    expiresAt: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
  },
  issuedAt: new Date().toISOString(),
};

const kernel = new SharedOSKernel({
  grantSource: {
    async load(context) {
      return [grant].filter(
        (g) =>
          g.namespaceId === context.namespaceId &&
          JSON.stringify(g.subject) === JSON.stringify(context.actor) &&
          JSON.stringify(g.issuer) === JSON.stringify(context.authority),
      );
    },
  },
  authorizer: new CapabilityAuthorizer({ usageStore: new InMemoryGrantUsageStore() }),
});

for (const tool of fetchlyTools) kernel.registerTool(tool);

// The trusted context. Built from server-side state, never from anything the
// MCP client sends. It carries identity and purpose, not authority. A FRESH
// context (fresh `now` and `traceId`) is built per call so grant expiry is
// actually enforced and each call gets its own audit trace.
const executionId = randomUUID();

function freshContext() {
  return {
    namespaceId: NAMESPACE_ID,
    actor: agent,
    authority: owner,
    owner,
    purpose: PURPOSE,
    traceId: randomUUID(),
    enabledToolNamespaces: ["web"],
    now: new Date().toISOString(),
  };
}

const invoker = {
  async catalog(signal) {
    return kernel.listPublishedTools(freshContext(), { executionId, signal });
  },
  async invoke(invocation, signal) {
    const ctx = freshContext();
    const call = {
      id: invocation.callId,
      tool: invocation.tool,
      arguments: invocation.arguments,
      traceId: ctx.traceId,
      requestedAt: new Date().toISOString(),
    };
    return kernel.invokeTool(ctx, call, { signal });
  },
};
const server = new McpToolServer({
  invoker,
  serverInfo: { name: "fetchly-sharedos", version: "0.1.0" },
  instructions:
    "Permission-controlled fetchly: fetch_url/search/research/summarize, gated by SharedOS grants.",
});

await serveMcpOverStdio(server, {
  input: process.stdin,
  output: process.stdout,
});
