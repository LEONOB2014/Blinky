/**
 * TypeScript definitions derived directly from `contracts/*.schema.json` and `contracts/api.yaml`.
 */

export type Profile = "dev" | "full";
export type Segment = "ai" | "it" | "ai_domain";
export type LangBucket = "eng" | "spa" | "por" | "other";

export type TopicStage =
  | "semilla"
  | "emergente"
  | "en_pico"
  | "saturado"
  | "en_declive";

export type DecisionValue =
  | "publicar_ahora"
  | "preparar"
  | "esperar"
  | "no_es_tema_caliente";

export type WindowState =
  | "dias_restantes"
  | "en_cualquier_momento"
  | "ya_en_espanol"
  | "sin_estimacion";

export interface TopicWindow {
  state: WindowState;
  days_left: number | null;
  typical_lag_days?: number | null;
  n_onsets: number;
}

/** `contracts/topic_scores_weekly.schema.json` */
export interface TopicScoreWeekly {
  week: string;
  topic_id: string;
  label_es: string;
  subtopics?: string[];
  primary_subtopic: string;
  emergence_pct?: number | null;
  stage: TopicStage;
  saturation?: number | null;
  audience_fit?: number | null;
  outperformance?: number | null;
  emotional_charge_pct?: number | null;
  framing_angle?: string | null;
  window: TopicWindow;
  priority: number;
  rank?: number | null;
  decision: DecisionValue;
  why: string[];
  evidence_ids: string[];
  has_wikipedia_es_pt?: boolean;
  profile: Profile;
}

/** `contracts/topic_daily.schema.json` */
export interface TopicDaily {
  topic_id: string;
  dt: string;
  lang_bucket: LangBucket;
  segment: "ai";
  n_articles: number;
  share_of_day: number | null;
  mean_tone?: number | null;
  mean_polarity?: number | null;
  is_missing: boolean;
}

/** `contracts/topic_context_1hop.schema.json` */
export interface TopicContext1Hop {
  wk: string;
  topic_id: string;
  neighbor: string;
  rank: number;
  n: number;
  npmi: number;
  neighbor_segment?: Segment | null;
  neighbor_domain?: string | null;
}

/** `contracts/decision_card.schema.json` */
export interface DecisionCardKpi {
  name: string;
  value: number | string | null;
  unit?: string | null;
  kind: "measured" | "estimate";
  source: string;
}

export interface SuggestedContent {
  format?: string;
  hooks?: string[];
  outline?: string[];
}

export interface DecisionCard {
  topic_id: string;
  week: string;
  decision: DecisionValue;
  kpis: DecisionCardKpi[];
  justification_es: string;
  context_1hop?: string[];
  evidence_ids: string[];
  suggested_content?: SuggestedContent | null;
  auditor_ok: boolean;
}

/** `contracts/view_command.schema.json` */
export type ViewMode = "story" | "temporal" | "cards";
export type ViewColorBy = "tone" | "arousal" | "community" | "segment";

export interface ViewFilter {
  segment?: Segment[];
  lang_bucket?: LangBucket[];
  hops?: 1 | 2;
}

export interface ViewCommand {
  view: ViewMode;
  week?: string | null;
  focus_topic?: string | null;
  highlight?: string[];
  color_by: ViewColorBy;
  filter?: ViewFilter;
  caption_es: string;
}

/** `contracts/agent_trace.schema.json` */
export type AgentName =
  | "media_master"
  | "scout"
  | "curator"
  | "signal_analyst"
  | "cartographer"
  | "audience_strategist"
  | "editor"
  | "auditor";

export type AgentAction =
  | "delegate"
  | "tool_call"
  | "tool_result"
  | "answer"
  | "veto";

export interface AgentTraceStep {
  conversation_id: string;
  step: number;
  agent: AgentName;
  action: AgentAction;
  tool?: string | null;
  arguments?: Record<string, unknown> | null;
  result_summary?: string | null;
  latency_ms?: number | null;
  tokens?: number | null;
  model?: string | null;
}

/** `GET /api/freshness` */
export interface FreshnessResponse {
  profile: Profile;
  tables: Record<string, string | null>;
  newest?: Record<string, string | null>;
}

/** `POST /api/chat` */
export interface ChatRequest {
  conversation_id?: string;
  message: string;
  week?: string;
}

export interface ChatResponse {
  conversation_id: string;
  answer_es: string;
  decision_cards: DecisionCard[];
  view_commands: ViewCommand[];
  trace: AgentTraceStep[];
}
