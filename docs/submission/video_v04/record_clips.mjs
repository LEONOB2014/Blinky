// Record the live radar at 1920x1080 in headed Chrome (WebGL): one frame folder per scene, with timestamps.
import { open } from "./cdp.mjs";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const OUT = process.argv[2];
const URL = "https://radar-senal-temprana.netlify.app/";
const b = await open(true);
await b.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
// Click like a visitor: no scrollIntoView.
const clickText = (text) => b.ev(`(() => { const t = ${JSON.stringify(text.toLowerCase())}; const x = [...document.querySelectorAll("button, summary, a, [role=tab], [role=button]")].find((e) => e.textContent.trim().toLowerCase().startsWith(t)); if (!x) return "missing"; x.click(); return "ok"; })()`);
const pill = (sel, text) => b.ev(`(() => { const x = [...document.querySelectorAll(${JSON.stringify(sel)})].find((e) => e.textContent.trim() === ${JSON.stringify(text)}); if (!x) return "missing"; x.click(); return "ok"; })()`);
const lens = (t) => pill(".lens-pills-bar button", t);
const frame = async (dir, i) => { const p = await b.send("Page.captureScreenshot", { format: "jpeg", quality: 88 });
  writeFileSync(join(dir, `f${String(i).padStart(4, "0")}.jpg`), Buffer.from(p.result.data, "base64")); };
const record = async (name, ms, during) => {
  const dir = join(OUT, name); mkdirSync(dir, { recursive: true });
  const t0 = Date.now(); const stamps = []; let i = 0; let p = null;
  while (Date.now() - t0 < ms) { await frame(dir, i); stamps.push([i, Date.now() - t0]); i++; if (!p && during) p = during(); }
  if (p) await p;
  writeFileSync(join(dir, "stamps.json"), JSON.stringify(stamps));
  console.log(name, i, "frames in", ms, "ms");
};
const fresh = async () => { await b.goto(URL); await b.sleep(10000);
  await b.ev(`document.querySelectorAll("details[open]").forEach((d) => (d.open = false))`); };
await fresh();
await record("01_default", 5000);
await record("02_card_ring", 9000, async () => { await b.sleep(800); console.log("card", await clickText("#1")); await b.sleep(600);
  await b.ev(`document.querySelectorAll("details[open]").forEach((d) => (d.open = false))`); });
await fresh();
await record("03_leaders", 8000, async () => { await b.sleep(1000); console.log("leaders", await pill("button", "Lo más grande")); });
await fresh();
await record("04_play", 11000, async () => { await b.sleep(500); console.log("play", await clickText("▶ Reproducir")); });
await b.sleep(1500);
await record("05_lenses", 17500, async () => {
  for (const l of ["Radar", "Familia", "Postura", "Emoción", "Momento", "Comunidades", "Puente", "Novedad"]) { console.log("lens", l, await lens(l)); await b.sleep(2100); }
});
await lens("Familia"); await b.sleep(1200);
await record("06_trust", 7000, async () => { await b.sleep(800); console.log("trust", await pill("button", "Confianza")); });
await pill("button", "Ocultar confianza"); await b.sleep(800);
await fresh();
await record("07_chat", 45000, async () => {
  await b.sleep(800); await clickText("Pregúntale"); await b.sleep(1200);
  await b.ev(`(() => { const i = [...document.querySelectorAll("input, textarea")].find((x) => /Pregunta|Maestro/i.test(x.placeholder || "")) || document.querySelector(".chat-dock input, .chat-dock textarea");
    const proto = i.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(i, "¿Qué es lo más grande esta semana en IA?");
    i.dispatchEvent(new Event("input", { bubbles: true })); })()`);
  await b.sleep(700); console.log("ask", await clickText("Preguntar"));
});
const answer = await b.ev(`(() => { const d = document.querySelector("[data-testid=media-dock]"); return d ? d.innerText : "none"; })()`);
writeFileSync(join(OUT, "chat-answer.txt"), answer);
console.log("answer chars", answer.length, "loading", /Consultando/.test(answer));
console.log("logs", JSON.stringify(b.logs.slice(0, 5)));
b.close(); process.exit(0);
