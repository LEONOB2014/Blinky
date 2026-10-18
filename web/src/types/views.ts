import type { DecisionValue, TopicStage } from "./contracts";

export interface TemporalMover {
  id: string;
  label_es: string;
  deg_growth: number;
  pagerank_pct: number;
  decision: DecisionValue;
}

export interface TemporalGraphMeta {
  n_nodes: number;
  n_labeled: number;
  n_edges_total: number;
  edges_per_week: number[];
  n_weeks: number;
  min_n: number;
  max_nodes: number;
  top_k: number;
  layout: string;
  top_movers_per_week: TemporalMover[][];
}

export interface TemporalGraphData {
  weeks: string[];
  nodes: string[];
  labels: string[];
  labels_es: string[];
  show_label: boolean[];
  positions: [number, number][];
  node_metrics: Record<string, (number | null)[][]>;
  edges_by_week: [number, number, number, number][][];
  _meta: TemporalGraphMeta;
}

export interface StoryNode {
  id: string;
  label: string;
  label_es: string;
  role: "center" | "neighbor";
  rank: number;
  n?: number;
  npmi?: number;
  segment: string | null;
  domain: string | null;
}

export interface StoryEdge {
  source: string;
  target: string;
  n: number;
  npmi: number;
}

export interface StoryCenterScores {
  rank?: number | null;
  priority?: number | null;
  decision?: DecisionValue | null;
  stage?: TopicStage | null;
  emergence_pct?: number | null;
  saturation?: number | null;
  audience_fit?: number | null;
  emotional_charge_pct?: number | null;
  framing_angle?: string | null;
  label_es?: string | null;
}

export interface StoryGraphData {
  wk: string;
  center: string;
  center_label?: string;
  center_label_es?: string;
  center_scores: StoryCenterScores;
  nodes: StoryNode[];
  edges: StoryEdge[];
  _meta: {
    n_nodes: number;
    n_edges: number;
    slug?: string;
  };
}

export interface StoriesIndexEntry {
  topic_id: string;
  slug: string;
  file: string;
  label_es: string;
  rank: number | null;
  in_top10?: boolean;
  priority: number | null;
  decision: DecisionValue | null;
  stage: TopicStage | null;
  emergence_pct: number | null;
  n_neighbors: number;
}

export interface StoriesIndexData {
  wk: string;
  default_topic_id: string | null;
  stories: StoriesIndexEntry[];
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
