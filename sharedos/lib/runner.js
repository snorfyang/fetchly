// Runs the Python fetchly CLI and returns parsed JSON.
// SharedOS gates *whether* a call is allowed; this module only executes it.
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileP = promisify(execFile);

const BIN = process.env.FETCHLY_BIN ?? "fetchly";
const TIMEOUT_MS = Number(process.env.FETCHLY_TIMEOUT_MS ?? 60000);

export async function runFetchly(tool, args) {
  const argv = [];
  switch (tool) {
    case "web.fetch":
      argv.push("fetch", String(args.url));
      if (typeof args.max_chars === "number") argv.push("--max-chars", String(args.max_chars));
      break;
    case "web.search":
      argv.push("search", String(args.query));
      if (typeof args.limit === "number") argv.push("--limit", String(args.limit));
      break;
    case "web.research":
      argv.push("research", String(args.query));
      if (typeof args.limit === "number") argv.push("--limit", String(args.limit));
      break;
    case "web.summarize":
      argv.push("summarize", String(args.text));
      if (typeof args.sentences === "number") argv.push("--sentences", String(args.sentences));
      break;
    default:
      throw new Error(`no fetchly mapping for tool ${tool}`);
  }

  const { stdout } = await execFileP(BIN, argv, {
    timeout: TIMEOUT_MS,
    maxBuffer: 32 * 1024 * 1024,
  });
  return JSON.parse(stdout);
}
