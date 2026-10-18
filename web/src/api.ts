import type {
  ChatRequest,
  ChatResponse,
  FreshnessResponse,
  TopicContext1Hop,
  TopicDaily,
  TopicScoreWeekly,
} from "./types/contracts";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface RadarResult {
  items: TopicScoreWeekly[];
  emptyReason: string | null;
}

export async function fetchFreshness(): Promise<FreshnessResponse> {
  const resp = await fetch(`${API_BASE}/api/freshness`);
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
  const resp = await fetch(`${API_BASE}/api/radar?${params.toString()}`);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar /api/radar`);
  }
  const emptyReason = resp.headers.get("X-Radar-Empty-Reason");
  const items = (await resp.json()) as TopicScoreWeekly[];
  return { items, emptyReason };
}

export async function fetchTopicTimeline(topicId: string): Promise<TopicDaily[]> {
  const resp = await fetch(
    `${API_BASE}/api/topic/${encodeURIComponent(topicId)}/timeline`,
  );
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
  const resp = await fetch(
    `${API_BASE}/api/topic/${encodeURIComponent(topicId)}/context${query}`,
  );
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} al consultar contexto de ${topicId}`);
  }
  return (await resp.json()) as TopicContext1Hop[];
}

export async function sendChatTurn(payload: ChatRequest): Promise<ChatResponse> {
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
