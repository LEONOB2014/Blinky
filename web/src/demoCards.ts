/** Static brief, evidence, and trust files. A missing file is pendiente, never invented copy. */

const BASE = `${import.meta.env.BASE_URL}data`;

export type CardLoad<T> =
  | { status: "loading" }
  | { status: "pending"; path: string }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

export interface CitedNumber {
  name: string;
  value: number | string;
  kind: "measured" | "estimate" | string;
  source: string;
}

export interface TopicBrief {
  week?: string;
  topic_id: string;
  headline_es?: string;
  what_happened_es?: string;
  why_latam_es?: string;
  angle_es?: string;
  hook_es?: string;
  format_es?: string;
  auditor_ok?: boolean;
  numbers_cited?: CitedNumber[];
}

export interface EvidenceArticle {
  title?: string | null;
  url?: string;
  source?: string;
  dt?: string;
  lang_bucket?: string;
  evidence_rank?: number;
}

export interface EvidenceFile {
  topic_id?: string;
  weeks?: Record<string, EvidenceArticle[]>;
}

export interface TrustReport {
  available?: boolean;
  source?: string;
  reason?: string;
  kind?: string;
  markdown?: string;
  title?: string;
  sections?: {
    heading?: string | null;
    tables?: Record<string, string>[][];
    bullets?: string[];
  }[];
}

export interface LedgerSide {
  source?: string;
  jobs?: number;
  billed_bytes?: number;
  billed_gb?: number;
  billed_gb_by_workstream?: Record<string, number>;
  calls?: number;
  input_tokens?: number;
  cost_usd?: number;
  median_latency_ms?: number | null;
  kind?: string;
}

/** evidence/trust_summary.json (deploy/evidence.py, built by agents/trust.py). */
export interface TrustSummaryPoint {
  id: string;
  texto: string;
  kind: "measured" | "estimate" | "status" | "rule";
}

export interface TrustSummaryFile {
  available?: boolean;
  points: TrustSummaryPoint[];
  sources?: string[];
}

export interface LedgersFile {
  bigquery?: LedgerSide;
  jev?: LedgerSide;
}

const jsonCache = new Map<string, Promise<CardLoad<unknown>>>();

export function readStaticJson(path: string): Promise<CardLoad<unknown>> {
  const hit = jsonCache.get(path);
  if (hit) return hit;
  const pending = fetch(`${BASE}/${path}`)
    .then(async (resp): Promise<CardLoad<unknown>> => {
      if (resp.status === 404) return { status: "pending", path };
      if (!resp.ok) return { status: "error", message: `HTTP ${resp.status} ${path}` };
      const text = await resp.text();
      // Vite serves index.html for a missing static file. That is pendiente, not a crash.
      if (text.trimStart().startsWith("<")) return { status: "pending", path };
      let data: unknown;
      try {
        data = JSON.parse(text) as unknown;
      } catch {
        return { status: "pending", path };
      }
      if (
        data &&
        typeof data === "object" &&
        "available" in data &&
        (data as { available?: boolean }).available === false
      ) {
        return { status: "pending", path };
      }
      return { status: "ready", data };
    })
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : "error de red";
      return { status: "error", message } as CardLoad<unknown>;
    });
  jsonCache.set(path, pending);
  return pending;
}

function briefRows(data: unknown): TopicBrief[] {
  if (Array.isArray(data)) return data as TopicBrief[];
  if (data && typeof data === "object") {
    const body = data as { briefs?: unknown; items?: unknown };
    if (Array.isArray(body.briefs)) return body.briefs as TopicBrief[];
    if (Array.isArray(body.items)) return body.items as TopicBrief[];
  }
  return [];
}

export async function loadBrief(week: string, topicId: string): Promise<CardLoad<TopicBrief>> {
  if (!week) return { status: "pending", path: "briefs/<semana>.json" };
  const path = `briefs/${week}.json`;
  const file = await readStaticJson(path);
  if (file.status !== "ready") return file;
  const row = briefRows(file.data).find((item) => item.topic_id === topicId);
  if (!row) return { status: "pending", path };
  return { status: "ready", data: row };
}

export async function loadEvidence(
  week: string,
  topicId: string,
): Promise<CardLoad<EvidenceArticle[]>> {
  const slug = topicId
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const path = `evidence/topics/${slug}.json`;
  const file = await readStaticJson(path);
  if (file.status !== "ready") return file;
  const weeks = (file.data as EvidenceFile).weeks ?? {};
  const articles = weeks[week];
  if (!articles || articles.length === 0) return { status: "pending", path };
  return { status: "ready", data: articles.slice(0, 5) };
}

export function kindLabel(kind: string | undefined): "medido" | "estimado" {
  return kind === "estimate" || kind === "estimado" ? "estimado" : "medido";
}
