import type { DecisionValue, TopicScoreWeekly } from "./contracts";

export interface TemporalMover {
  id: string;
  label_es: string;
  rank: number | null;
  decision: DecisionValue | null;
  pagerank: number | null;
  pr_rank_delta: number | null;
  deg_growth: number | null;
}

export interface TemporalGraphMeta {
  profile: string;
  view: string;
  layout: string;
  weeks: string[];
  iso_weeks: string[];
  params: {
    span_weeks: number;
    max_nodes: number;
    min_n: number;
    min_npmi_exclusive: number;
    top_k_per_node: number;
    top_labels: number;
    ai_only?: boolean;
  };
  default_color_by?: string;
  family_legend?: Array<{ id: string; label_es: string; color: string }>;
  stance_legend?: Array<{ id: string; label_es: string; color: string }>;
  n_nodes: number;
  n_labeled_nodes: number;
  n_edges: number;
  edges_per_week: number[];
  top_movers_per_week: TemporalMover[][];
  decisions: string[];
}

export interface TemporalNodeEntry {
  id: string;
  label: string;
  label_es: string;
  etype: string;
  family?: string | null;
  family_es?: string | null;
  stance?: string | null;
  ring: "ai" | "it" | "ai_domain";
  domain?: string | null;
  x: number;
  y: number;
  show_label: boolean;
  deg_span: number;
  pagerank: (number | null)[];
  importance: (number | null)[];
  pr_rank_delta: (number | null)[];
  deg_growth: (number | null)[];
  momentum: (number | null)[];
  betweenness: (number | null)[];
  cross_ring_share: (number | null)[];
  community_week: (number | null)[];
  new_nbr_rate: (number | null)[];
  kcore: (number | null)[];
  tone: (number | null)[];
  emotional_charge_pct: (number | null)[];
  window_state: (string | null)[];
  rank: (number | null)[];
  decision: (DecisionValue | null)[];
}

export interface TemporalEdgesColumnar {
  source: number[];
  target: number[];
  week: number[];
  n: number[];
  npmi: number[];
  edge_state: ("new" | "growing" | "persisting" | "fading")[];
  n_growth: number[];
  cross_ring: boolean[];
}

export interface TemporalGraphData {
  _meta: TemporalGraphMeta;
  nodes: TemporalNodeEntry[];
  edges: TemporalEdgesColumnar;
}

export interface StoryNodeAttributes {
  label: string;
  label_es: string;
  x: number;
  y: number;
  size: number;
  role: "topic" | "ring";
  ring: "ai" | "it" | "ai_domain";
  domain?: string | null;
  rank?: number;
  n?: number;
  npmi?: number;
  etype: "org" | "thm" | "loc" | string;
  family?: string | null;
  family_es?: string | null;
  stance?: string | null;
  betweenness?: number | null;
  cross_ring_share?: number | null;
  community_week?: number | null;
  importance?: number | null;
  momentum?: number | null;
  new_nbr_rate?: number | null;
  pagerank?: number | null;
  pr_rank_delta?: number | null;
  deg_growth?: number | null;
  kcore?: number | null;
  edge_state?: "new" | "growing" | "persisting" | "fading";
  n_growth?: number;
}

export interface StoryNodeEntry {
  key: string;
  attributes: StoryNodeAttributes;
}

export interface StoryEdgeAttributes {
  n: number;
  npmi: number;
  size: number;
  kind: "ring" | "among";
  edge_state?: "new" | "growing" | "persisting" | "fading";
  n_growth?: number;
  cross_ring?: boolean;
}

export interface StoryEdgeEntry {
  key: string;
  source: string;
  target: string;
  attributes: StoryEdgeAttributes;
}

export interface StoryGraphData {
  _meta: {
    profile: string;
    view: string;
    topic_id: string;
    label_es: string;
    week: string;
    wk: string;
    n_ring: number;
    n_among_edges: number;
  };
  attributes: {
    topic_id: string;
    label_es: string;
    week: string;
    scores: Partial<TopicScoreWeekly> | null;
  };
  options?: {
    type: string;
    multi: boolean;
  };
  nodes: StoryNodeEntry[];
  edges: StoryEdgeEntry[];
}

export interface StoriesIndexEntry {
  topic_id: string;
  label_es: string;
  week: string;
  rank: number | null;
  decision: DecisionValue | null;
  n_ring: number;
  n_among_edges: number;
  file: string;
  in_top10: boolean;
}

export interface StoriesIndexData {
  _meta: {
    profile: string;
    week: string;
    wk: string;
    default_topic: string;
    n_top10: number;
    n_total_stories: number;
  };
  top10: StoriesIndexEntry[];
  stories: Record<string, StoriesIndexEntry>;
}

export interface GraphWindowMetrics {
  /** AI graph: volume leaders labelled for the displayed week. */
  leader_labels?: number;
  leaders_week?: string;
  renderer?: string;
  t_fetch_ms?: number;
  t_parse_ms?: number;
  t_first_frame_ms?: number;
  n_nodes?: number;
  n_edges_w?: number;
  n_weeks?: number;
  fps_playing?: number;
  week_switch_ms?: number[];
  sweep_done?: boolean;
  story_rendered_ms?: number;
  story_center?: string;
  story_n_nodes?: number;
  active_lens?: string;
  fps_relayout?: number;
  settle_time_ms?: number;
  /** Point positions after the last reheat, sampled at fixed indices (measured). */
  layout_sample?: number[];
  /** One sample per lens, so two lenses can be compared (measured). */
  layout_by_lens?: Record<string, number[]>;
  /** Mean absolute difference between this lens's sample and another lens (measured). */
  layout_delta?: number;
  sim_progress?: number;
  reheat_count?: number;
  /** Mean absolute move of the sample during the last reheat (measured). */
  layout_moved?: number;
  reheat_skipped?: string;
  is_fullscreen?: boolean;
  split_ratio?: number;
}

declare global {
  interface Window {
    __metrics?: GraphWindowMetrics;
  }
}
