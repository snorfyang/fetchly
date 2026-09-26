// Demonstration: SharedOS gatekeeping, exercised directly against the kernel.
// Prints (1) the filtered catalogue, (2) an allowed call, (3) a denied call.
import { randomUUID } from "node:crypto";

import {
  CapabilityAuthorizer,
  InMemoryGrantUsageStore,
  SharedOSKernel,
} from "@aicoo/sharedos";

import { fetchlyTools } from "./lib/tools.js";

const owner = { kind: "human", userId: "snorf" };
const agent = { kind: "agent", agentId: "fetchly-agent" };

const grant = {
  id: "grant-fetchly-web-read",
  namespaceId: "fetchly",
  subject: agent,
  issuer: owner,
  capabilities: [
    {
      resource: { namespace: "web", path: [] },
      actions: ["fetch", "search", "research", "summarize"],
      scope: "descendants",
    },
  ],
  constraints: { purposes: ["research"] },
  issuedAt: new Date().toISOString(),
};

const kernel = new SharedOSKernel({
  grantSource: { async load() { return [grant]; } },
  authorizer: new CapabilityAuthorizer({ usageStore: new InMemoryGrantUsageStore() }),
});
for (const t of fetchlyTools) kernel.registerTool(t);

const context = {
  namespaceId: "fetchly",
  actor: agent,
  authority: owner,
  owner,
  purpose: "research",
  traceId: randomUUID(),
  enabledToolNamespaces: ["web"],
  now: new Date().toISOString(),
};

const call = (tool, args) => ({
  id: randomUUID(),
  tool,
  arguments: args,
  traceId: context.traceId,
  requestedAt: new Date().toISOString(),
});

console.log("=== 1. Filtered catalogue (tools the grant makes visible) ===");
const visible = await kernel.listTools(context);
console.log(visible.map((t) => t.name));

console.log("\n=== 2. Allowed call: web.fetch https://example.com ===");
const allowed = await kernel.invokeTool(context, call("web.fetch", { url: "https://example.com" }));
console.log(JSON.stringify(allowed, null, 2));

console.log("\n=== 3. Denied call: web.post (registered, never granted) ===");
const denied = await kernel.invokeTool(context, call("web.post", { url: "https://example.com", body: "hi" }));
console.log({ status: denied.status, code: denied.error?.code });

// 4. Discovery is not permission: a tool that IS visible is still refused
//    when the exact resource (the URL host) is not granted.
console.log("\n=== 4. Visible but not permitted: fetch only example.com ===");
const restricted = new SharedOSKernel({
  grantSource: {
    async load() {
      return [{
        ...grant,
        id: "grant-fetchly-example-only",
        capabilities: [
          { resource: { namespace: "web", path: ["example.com"] }, actions: ["fetch"], scope: "exact" },
        ],
      }];
    },
  },
  authorizer: new CapabilityAuthorizer({ usageStore: new InMemoryGrantUsageStore() }),
});
for (const t of fetchlyTools) restricted.registerTool(t);
const visible2 = await restricted.listTools(context);
console.log("catalogue still shows:", visible2.map((t) => t.name));
const okFetch = await restricted.invokeTool(context, call("web.fetch", { url: "https://example.com" }));
console.log("fetch example.com ->", okFetch.status);
const badFetch = await restricted.invokeTool(context, call("web.fetch", { url: "https://news.ycombinator.com" }));
console.log("fetch news.ycombinator.com ->", badFetch.status, badFetch.error?.code);
