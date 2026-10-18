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
  };
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
  x: number;
  y: number;
  show_label: boolean;
  deg_span: number;
  pagerank: (number | null)[];
  pr_rank_delta: (number | null)[];
  deg_growth: (number | null)[];
  rank: (number | null)[];
  decision: (DecisionValue | null)[];
}

export interface TemporalEdgesColumnar {
  source: number[];
  target: number[];
  week: number[];
  n: number[];
  npmi: number[];
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
  rank?: number;
  n?: number;
  npmi?: number;
  etype: "org" | "thm" | "loc" | string;
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
}

declare global {
  interface Window {
    __metrics?: GraphWindowMetrics;
  }
}
