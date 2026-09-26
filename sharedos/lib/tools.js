// The fetchly tools as SharedOS tool handlers.
//
// Each tool declares a `requiredCapability` and, for URL-scoped tools, a
// `resolveRequirement` that derives the exact resource from the parsed
// arguments immediately before invocation — so tampering with arguments
// cannot widen scope. The kernel re-authorizes every call; a tool visible in
// the catalogue is still refused if the exact resource/action is not granted.
import { runFetchly } from "./runner.js";

const done = (call, output) => ({
  callId: call.id,
  tool: call.tool,
  status: "succeeded",
  output,
  completedAt: new Date().toISOString(),
});

const failed = (call, error) => ({
  callId: call.id,
  tool: call.tool,
  status: "failed",
  error: { code: "tool_execution_failed", message: String(error?.message ?? error) },
  completedAt: new Date().toISOString(),
});

const web = {
  fetch: {
    definition: {
      name: "web.fetch",
      description: "Fetch a URL and return clean Markdown, title, metadata and extracted links.",
      namespace: "web",
      source: "native",
      readWrite: "read",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["url"],
        properties: {
          url: { type: "string", description: "Absolute http(s) URL" },
          max_chars: { type: "number", description: "Markdown length cap (default 40000)" },
        },
      },
      requiredCapability: {
        resource: { namespace: "web", path: [] },
        action: "fetch",
      },
      annotations: { readOnly: true },
    },
    parseArguments: (a) => {
      const out = { url: String(a.url) };
      if (typeof a.max_chars === "number") out.max_chars = a.max_chars;
      return out;
    },
    resolveRequirement: (context, call) => ({
      resource: {
        namespace: "web",
        path: [new URL(String(call.arguments.url)).hostname],
        owner: context.owner,
      },
      action: "fetch",
    }),
    invoke: async (context, call) => {
      try {
        return done(call, await runFetchly("web.fetch", call.arguments));
      } catch (e) {
        return failed(call, e);
      }
    },
  },

  search: {
    definition: {
      name: "web.search",
      description: "Search the web and return cited results (title, url, snippet).",
      namespace: "web",
      source: "native",
      readWrite: "read",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["query"],
        properties: {
          query: { type: "string" },
          limit: { type: "number", description: "Max results (default 8)" },
        },
      },
      requiredCapability: {
        resource: { namespace: "web", path: [] },
        action: "search",
      },
      annotations: { readOnly: true },
    },
    parseArguments: (a) => {
      const out = { query: String(a.query) };
      if (typeof a.limit === "number") out.limit = a.limit;
      return out;
    },
    invoke: async (context, call) => {
      try {
        return done(call, await runFetchly("web.search", call.arguments));
      } catch (e) {
        return failed(call, e);
      }
    },
  },

  research: {
    definition: {
      name: "web.research",
      description: "Search the web then fetch the top pages, returning snippets plus clean Markdown.",
      namespace: "web",
      source: "native",
      readWrite: "read",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["query"],
        properties: {
          query: { type: "string" },
          limit: { type: "number", description: "How many top pages to fetch (default 3)" },
        },
      },
      requiredCapability: {
        resource: { namespace: "web", path: [] },
        action: "research",
      },
      annotations: { readOnly: true },
    },
    parseArguments: (a) => {
      const out = { query: String(a.query) };
      if (typeof a.limit === "number") out.limit = a.limit;
      return out;
    },
    invoke: async (context, call) => {
      try {
        return done(call, await runFetchly("web.research", call.arguments));
      } catch (e) {
        return failed(call, e);
      }
    },
  },

  summarize: {
    definition: {
      name: "web.summarize",
      description: "Return an extractive summary of text (or a URL), top sentences by keyword frequency.",
      namespace: "web",
      source: "native",
      readWrite: "read",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["text"],
        properties: {
          text: { type: "string", description: "Text, or an http(s) URL" },
          sentences: { type: "number", description: "Number of sentences (default 5)" },
        },
      },
      requiredCapability: {
        resource: { namespace: "web", path: [] },
        action: "summarize",
      },
      annotations: { readOnly: true },
    },
    parseArguments: (a) => {
      const out = { text: String(a.text) };
      if (typeof a.sentences === "number") out.sentences = a.sentences;
      return out;
    },
    invoke: async (context, call) => {
      try {
        return done(call, await runFetchly("web.summarize", call.arguments));
      } catch (e) {
        return failed(call, e);
      }
    },
  },

  // Registered but deliberately NOT granted. This tool is the deny-by-default
  // demonstration: it never appears in the catalogue and every call to it is
  // refused by the kernel before this handler could run.
  post: {
    definition: {
      name: "web.post",
      description: "Submit content to a URL. Requires a separate write grant.",
      namespace: "web",
      source: "native",
      readWrite: "write",
      inputSchema: {
        type: "object",
        additionalProperties: false,
        required: ["url", "body"],
        properties: {
          url: { type: "string" },
          body: { type: "string" },
        },
      },
      requiredCapability: {
        resource: { namespace: "web", path: [] },
        action: "post",
      },
      annotations: { destructive: true },
    },
    parseArguments: (a) => ({ url: String(a.url), body: String(a.body) }),
    invoke: async (context, call) => done(call, { posted: true }),
  },
};

export const fetchlyTools = Object.values(web);
