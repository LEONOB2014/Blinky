// Measure a view in local Chrome through the DevTools protocol (no extra packages; Bun or Node 22+).
//
//   bun graph/views/measure.mjs <url> <screenshot.png> [waitSeconds] [--headed]
//
// Launches Chrome with a throwaway profile, opens <url>, polls window.__metrics until the sweep is
// done (or waitSeconds pass), prints the metrics as JSON and saves a screenshot. --headed opens a
// real window, which is the reliable way to get the Mac's GPU (headless may fall back to software).
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, shot, waitArg] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const headed = process.argv.includes("--headed");
const waitSeconds = Number(waitArg || 60);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "radar-cdp-"));
const args = [
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run",
  "--no-default-browser-check", "--window-size=1440,900", "--ignore-gpu-blocklist",
  ...(headed ? [] : ["--headless=new", "--use-angle=metal", "--enable-gpu"]),
  "about:blank",
];
const chrome = spawn(CHROME, args, { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    target = list.find((t) => t.type === "page");
  } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
const logs = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    const d = msg.params.exceptionDetails;
    logs.push(`exception: ${d.exception?.description || d.text}`.slice(0, 400));
  }
  if (msg.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(msg.params.type)) {
    logs.push(`${msg.params.type}: ${msg.params.args.map((a) => a.value ?? a.description).join(" ")}`.slice(0, 400));
  }
  if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") {
    logs.push(`log: ${msg.params.entry.text} ${msg.params.entry.url || ""}`.slice(0, 400));
  }
};
const send = (method, params = {}) =>
  new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) =>
  (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }))
    .result?.result?.value;

await send("Page.enable");
await send("Runtime.enable");
await send("Log.enable");
await send("Page.navigate", { url });
const t0 = Date.now();
let metrics = {};
while (Date.now() - t0 < waitSeconds * 1000) {
  await sleep(1000);
  metrics = (await evaluate("JSON.stringify(window.__metrics || {})")) || "{}";
  metrics = JSON.parse(metrics);
  if (metrics.error || metrics.sweep_done || metrics.story_rendered_ms) break;
}
const png = await send("Page.captureScreenshot", { format: "png" });
if (png.result?.data) writeFileSync(shot, Buffer.from(png.result.data, "base64"));
metrics.harness = { headed, waited_s: (Date.now() - t0) / 1000, logs: logs.slice(0, 20) };
console.log(JSON.stringify(metrics, null, 1));
ws.close();
chrome.kill();
process.exit(0);
