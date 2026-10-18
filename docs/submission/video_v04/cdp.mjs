// Minimal CDP driver shared by the discovery and shot scripts.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
export async function open(headed) {
  const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const port = 9300 + Math.floor(Math.random() * 500);
  const profile = mkdtempSync(join(tmpdir(), "radar-cdp-"));
  const chrome = spawn(CHROME, [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run",
    "--no-default-browser-check", "--window-size=1440,900", "--ignore-gpu-blocklist",
    ...(headed ? [] : ["--headless=new"]), "about:blank"], { stdio: "ignore" });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let target;
  for (let i = 0; i < 60 && !target; i++) { await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch {} }
  const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = new Map(); const logs = [];
  ws.onmessage = (m) => { const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === "Runtime.exceptionThrown") logs.push((msg.params.exceptionDetails.exception?.description || "").slice(0, 200)); };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (e) => (await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true })).result?.result?.value;
  await send("Page.enable"); await send("Runtime.enable");
  return {
    sleep, ev, logs, send,
    goto: async (url) => { await send("Page.navigate", { url }); },
    shot: async (path) => { const p = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(path, Buffer.from(p.result.data, "base64")); },
    click: (text) => ev(`(() => { const t = ${JSON.stringify(text)}.toLowerCase(); const b = [...document.querySelectorAll('button, summary, a, [role=tab], [role=button]')].find(x => x.textContent.trim().toLowerCase().startsWith(t)); if (!b) return 'missing'; b.scrollIntoView({block:'center'}); b.click(); return 'ok'; })()`),
    close: () => { ws.close(); chrome.kill(); },
  };
}
