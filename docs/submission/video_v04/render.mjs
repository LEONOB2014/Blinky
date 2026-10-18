// Render HTML files to PNG in headless Chrome: node render.mjs <jobs.json>  ([{html, png, w, h, transparent}])
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const port = 9500 + Math.floor(Math.random() * 300);
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [`--remote-debugging-port=${port}`, "--headless=new",
  `--user-data-dir=${mkdtempSync(join(tmpdir(), "radar-render-"))}`, "--no-first-run", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let t; for (let i = 0; i < 60 && !t; i++) { await sleep(250); try { t = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === "page"); } catch {} }
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map();
ws.onmessage = (m) => { const msg = JSON.parse(m.data); if (msg.id && pend.has(msg.id)) { pend.get(msg.id)(msg); pend.delete(msg.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Page.enable");
for (const j of jobs) {
  await send("Emulation.setDeviceMetricsOverride", { width: j.w, height: j.h, deviceScaleFactor: 1, mobile: false });
  await send("Emulation.setDefaultBackgroundColorOverride", j.transparent ? { color: { r: 0, g: 0, b: 0, a: 0 } } : {});
  await send("Page.navigate", { url: "file://" + j.html }); await sleep(1400);
  await send("Runtime.evaluate", { expression: "document.fonts.ready", awaitPromise: true });
  const p = await send("Page.captureScreenshot", { format: "png", omitBackground: !!j.transparent });
  writeFileSync(j.png, Buffer.from(p.result.data, "base64"));
}
console.log("rendered", jobs.length); ws.close(); chrome.kill(); process.exit(0);
