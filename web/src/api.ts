import type {
  ChatRequest,
  ChatResponse,
  FreshnessResponse,
  TopicContext1Hop,
  TopicDaily,
  TopicScoreWeekly,
} from "./types/contracts";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

// Static fallback (deploy/export_static.py writes web/public/data/): used when the live API is
// unreachable (network error or HTTP 5xx), always with VITE_DATA_MODE=static, and in a production
// build without VITE_API_BASE_URL (a static host has no /api). Once the API has failed, the session
// stays on the static files so every panel does not wait for a timeout.
const STATIC_BASE = `${import.meta.env.BASE_URL}data`;
let useStatic =
  import.meta.env.VITE_DATA_MODE === "static" || (import.meta.env.PROD && !API_BASE);

export function isStaticMode(): boolean {
  return useStatic;
}

/** Same rule as deploy/export_static.py slug(). */
export function staticSlug(topicId: string): string {
  return topicId
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

async function fetchStatic<T>(path: string, empty: T): Promise<T> {
  const resp = await fetch(`${STATIC_BASE}/${path}`);
  if (resp.status === 404) {
    return empty;
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al leer datos estáticos ${path}`);
  }
  return (await resp.json()) as T;
}

/** Live API first; on a network error or 5xx, switch to the static export for the session. */
async function liveOrStatic(url: string): Promise<Response | null> {
  if (useStatic) {
    return null;
  }
  try {
    const resp = await fetch(url);
    if (resp.status >= 500) {
      useStatic = true;
      return null;
    }
    return resp;
  } catch {
    useStatic = true;
    return null;
  }
}

export interface RadarResult {
  items: TopicScoreWeekly[];
  emptyReason: string | null;
}

export async function fetchFreshness(): Promise<FreshnessResponse> {
  const resp = await liveOrStatic(`${API_BASE}/api/freshness`);
  if (resp === null) {
    return fetchStatic<FreshnessResponse>("freshness.json", { profile: "full", tables: {} });
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar /api/freshness`);
  }
  return (await resp.json()) as FreshnessResponse;
}

export async function fetchRadar(week?: string, limit = 10): Promise<RadarResult> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (week) {
    params.set("week", week);
  }
  const resp = await liveOrStatic(`${API_BASE}/api/radar?${params.toString()}`);
  if (resp === null) {
    const items = await fetchStatic<TopicScoreWeekly[] | null>(
      `radar/${week ?? "latest"}.json`,
      null,
    );
    if (items === null) {
      return { items: [], emptyReason: `semana ${week} no incluida en la exportación estática` };
    }
    return {
      items: items.slice(0, limit),
      emptyReason: items.length ? null : `sin temas puntuados para ${week ?? "la última semana"}`,
    };
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar /api/radar`);
  }
  const emptyReason = resp.headers.get("X-Radar-Empty-Reason");
  const items = (await resp.json()) as TopicScoreWeekly[];
  return { items, emptyReason };
}

export async function fetchTopicTimeline(topicId: string): Promise<TopicDaily[]> {
  const resp = await liveOrStatic(
    `${API_BASE}/api/topic/${encodeURIComponent(topicId)}/timeline`,
  );
  if (resp === null) {
    return fetchStatic<TopicDaily[]>(`timeline/${staticSlug(topicId)}.json`, []);
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar timeline de ${topicId}`);
  }
  return (await resp.json()) as TopicDaily[];
}

export async function fetchTopicContext(
  topicId: string,
  week?: string,
): Promise<TopicContext1Hop[]> {
  const query = week ? `?week=${encodeURIComponent(week)}` : "";
  const resp = await liveOrStatic(
    `${API_BASE}/api/topic/${encodeURIComponent(topicId)}/context${query}`,
  );
  if (resp === null) {
    return fetchStatic<TopicContext1Hop[]>(
      `context/${staticSlug(topicId)}/${week ?? "latest"}.json`,
      [],
    );
  }
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar contexto de ${topicId}`);
  }
  return (await resp.json()) as TopicContext1Hop[];
}

export async function sendChatTurn(payload: ChatRequest): Promise<ChatResponse> {
  // Chat never flips the session to static: a 503 here only means the agents have no key.
  if (useStatic) {
    throw new Error(
      "El chat necesita la API en vivo; esta página muestra la exportación estática.",
    );
  }
  const resp = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }
  return (await resp.json()) as ChatResponse;
}
