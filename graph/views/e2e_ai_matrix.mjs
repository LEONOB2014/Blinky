// End-to-end matrix of the AI temporal graph in headed Chrome (WebGL, Retina viewport 1440x900):
// every lens x every week (errors, drawn canvas, top-10 labels, non-finite positions), play in
// Familia and Postura (end week, fps), and selection of four leaders at W42 and W30.
//   node graph/views/e2e_ai_matrix.mjs http://127.0.0.1:5186/ /tmp/e2e   # a local build in AI mode
//   python3 graph/views/e2e_ai_matrix.py /tmp/e2e                         # the pass/fail table
// The page must serve the AI views (export_views --ai) and an API with RADAR_SOURCE=ai.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const [url, out] = process.argv.slice(2);
mkdirSync(join(out, "cells"), { recursive: true });
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const port = 9600 + Math.floor(Math.random() * 300);
const chrome = spawn(CHROME, [`--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "radar-e2e-"))}`,
  "--no-first-run", "--no-default-browser-check", "--window-size=1440,900", "--ignore-gpu-blocklist", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 60 && !target; i++) { await sleep(250); try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const logs = [];
ws.onmessage = (m) => { const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") { const d = msg.params.exceptionDetails; logs.push(`exception: ${d.exception?.description || d.text}`.slice(0, 300)); }
  if (msg.method === "Runtime.consoleAPICalled" && ["error", "warning", "assert"].includes(msg.params.type))
    logs.push(`console.${msg.params.type}: ${msg.params.args.map((a) => a.value ?? a.description).join(" ")}`.slice(0, 300));
  if (msg.method === "Log.entryAdded" && ["error", "warning"].includes(msg.params.entry.level)) logs.push(`log.${msg.params.entry.level}: ${msg.params.entry.text} ${msg.params.entry.url || ""}`.slice(0, 300)); };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (e) => (await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true })).result?.result?.value;
await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false });
const goto = async () => { await send("Page.navigate", { url }); await sleep(11000);
  await ev(`document.querySelectorAll("[data-testid=media-dock]").forEach((x) => (x.style.visibility = "hidden"))`); };
const lens = (t) => ev(`(() => { const x = [...document.querySelectorAll(".lens-pills-bar button")].find((e) => e.textContent.trim() === ${JSON.stringify(t)}); if (!x) return "missing"; x.click(); return "ok"; })()`);
const cell = () => ev(`(() => { const w = document.querySelector(".temporal-canvas-wrap"); const r = w.getBoundingClientRect(); const m = window.__metrics || {};
  return { week: document.querySelector("[data-testid=temporal-week-label]")?.textContent?.trim(), labels: [...w.querySelectorAll(".graph-node-label")].map((e) => e.title || e.textContent.trim()),
    nan: m.nan_positions, npos: m.n_positions, fps: m.fps_playing, clip: { x: r.left, y: r.top, w: r.width, h: r.height } }; })()`);
// The canvas alone: labels and legend are page elements over it, hidden for the shot.
const shot = async (file, c) => {
  await ev(`document.querySelectorAll(".temporal-labels-overlay, .graph-legend").forEach((x) => (x.style.visibility = "hidden"))`);
  await sleep(150);
  const p = await send("Page.captureScreenshot", { format: "png", clip: { x: c.x, y: c.y, width: c.w, height: c.h, scale: 0.5 } });
  writeFileSync(file, Buffer.from(p.result.data, "base64"));
  await ev(`document.querySelectorAll(".temporal-labels-overlay, .graph-legend").forEach((x) => (x.style.visibility = ""))`);
};

await goto();
const data = await ev(`fetch("/data/views/temporal.json").then((r) => r.json()).then((d) => ({ weeks: d._meta.iso_weeks ?? d._meta.weeks,
  top10: (d._meta.iso_weeks ?? d._meta.weeks).map((_, w) => d.nodes.filter((n) => (n.rank?.[w] ?? 0) >= 1 && n.rank[w] <= 10).map((n) => n.label_es || n.label || n.id)) }))`);
const LENSES = ["Radar", "Historia", "Puente", "Momento", "Novedad", "Comunidades", "Emoción", "Ventana", "Familia", "Postura"];
const rows = [];
for (const L of LENSES) {
  const l0 = logs.length; const lr = await lens(L); await sleep(1500);
  for (let w = 0; w < data.weeks.length; w++) {
    const e0 = logs.length;
    const badge = await ev(setWeekExpr(w)); await sleep(900);
    const c = await cell();
    const file = join(out, "cells", `${L}_${data.weeks[w]}.png`);
    await shot(file, c.clip);
    const top = data.top10[w]; const have = new Set(c.labels);
    rows.push({ lens: L, lens_click: lr, week: data.weeks[w], badge: c.week, top10_total: top.length, top10_labelled: top.filter((t) => have.has(t)).length,
      labels: c.labels.length, missing_top10: top.filter((t) => !have.has(t)), nan: c.nan, npos: c.npos, errors: logs.slice(e0), file });
  }
  if (logs.length > l0) console.log(L, "new log entries:", logs.length - l0);
}
function setWeekExpr(i) { return `(() => { const s = document.querySelector("input[type=range]"); if (!s) return "missing";
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(s, "${i}");
  s.dispatchEvent(new Event("input", { bubbles: true })); s.dispatchEvent(new Event("change", { bubbles: true })); return "ok"; })()`; }
// play in Familia and Postura
const play = [];
for (const L of ["Familia", "Postura"]) {
  await goto(); await lens(L); await sleep(1500); const e0 = logs.length;
  await ev(`(() => { const b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim().startsWith("▶ Reproducir")); b.click(); })()`);
  let last = ""; const t0 = Date.now();
  for (let i = 0; i < 60; i++) { await sleep(1000); last = (await cell()).week; const playing = await ev(`!![...document.querySelectorAll("button")].find((x) => x.textContent.trim().startsWith("⏸") || x.textContent.includes("Pausar"))`); if (!playing && i > 2) break; }
  const c = await cell();
  play.push({ lens: L, end_week: c.week, fps: c.fps, seconds: Math.round((Date.now() - t0) / 1000), nan: c.nan, errors: logs.slice(e0) });
}
// selection
const sel = [];
for (const wk of [data.weeks.length - 1, 0]) {
  for (const name of ["Nvidia", "OpenAI", "Anthropic", "Agentes de IA"]) {
    await goto(); const e0 = logs.length;
    await ev(setWeekExpr(wk)); await sleep(800);
    await ev(`(() => { const b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim() === "Lo más grande"); b && b.click(); })()`); await sleep(1500);
    const how = await ev(`(() => { const rows = [...document.querySelectorAll(".workspace-rail button, .workspace-rail [role=button]")]; const r = rows.find((x) => x.textContent.includes(${JSON.stringify(name)})); if (!r) return "not in rail"; r.click(); return "rail"; })()`);
    await sleep(5000);
    const c = await cell();
    const banner = await ev(`document.querySelector(".graph-lens-banner")?.textContent?.replace(/\\s+/g, " ").trim().slice(0, 90)`);
    const file = join(out, "cells", `select_${name.replace(/\W+/g, "_")}_${data.weeks[wk]}.png`); await shot(file, c.clip);
    sel.push({ topic: name, week_set: data.weeks[wk], badge: c.week, how, focus_labelled: c.labels.includes(name), labels: c.labels.length, banner, nan: c.nan, errors: logs.slice(e0), file });
  }
}
writeFileSync(join(out, "matrix.json"), JSON.stringify({ weeks: data.weeks, rows, play, sel, all_logs: logs }, null, 1));
console.log("cells", rows.length, "play", play.length, "selection", sel.length, "log entries", logs.length);
ws.close(); chrome.kill(); process.exit(0);
