import { Graph, type GraphConfig } from "@cosmos.gl/graph";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { browserHasGraphics } from "../graphics";
import { displayName } from "../publicCopy";
import { type GraphLens, LENS_NAMES, graphLensFromColorBy } from "../lenses";
import type { DecisionValue } from "../types/contracts";
import type { TemporalGraphData, TemporalMover, TemporalNodeEntry } from "../types/views";

export type LensMode = GraphLens;

export interface TemporalGraphProps {
  week?: string | null;
  focusTopic?: string | null;
  highlight?: string[];
  colorBy?: string;
  captionEs?: string | null;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
  onSelectTopic?: (topicId: string) => void;
  onOpenStory?: (topicId: string) => void;
  onLensChange?: (lens: LensMode) => void;
  /** Retriggers the fit when the chat dock opens or collapses. */
  dockOpen?: boolean;
}

interface LabelItem {
  idx: number;
  id: string;
  text: string;
  x: number;
  y: number;
  priority: number;
  decision: DecisionValue;
  isFocused: boolean;
}

interface TooltipItem {
  node: TemporalNodeEntry;
  screenX: number;
  screenY: number;
  topNeighbors: Array<{ id: string; label_es: string; n: number; npmi: number }>;
  edgeStates: { new: number; growing: number; persisting: number; fading: number };
}

const DECISION_LABELS_ES: Record<DecisionValue, string> = {
  publicar_ahora: "Publicar ahora",
  preparar: "Preparar",
  esperar: "Esperar",
  no_es_tema_caliente: "No es tema caliente",
};

// Qualitative categorical palette for Leiden communities
/** Skip a reheat when the current week has at least this many links. */
const REHEAT_LINK_CAP = 50_000;
const REHEAT_CAP_MS = 2500;
const REHEAT_TICK_MS = 100;
const REHEAT_STABLE_TICKS = 3;
const LAYOUT_SAMPLE_INDEXES = [0, 100, 250, 500, 750, 999];
const FIT_PAD = 0.08;

type ViewTransform = { k: number; x: number; y: number };

function zoomApi(graph: Graph): {
  getTransform: (positions: number[], scale?: number, padding?: number) => ViewTransform;
} | null {
  const zoom = (
    graph as unknown as {
      zoomInstance?: {
        getTransform: (positions: number[], scale?: number, padding?: number) => ViewTransform;
      };
    }
  ).zoomInstance;
  return zoom ?? null;
}

/** How far the chat dock intrudes into the canvas, in CSS pixels. */
function dockIntrusion(host: HTMLElement): { right: number; bottom: number } {
  const dock = document.querySelector("[data-testid='media-dock']");
  if (!dock) return { right: 0, bottom: 0 };
  const h = host.getBoundingClientRect();
  const d = dock.getBoundingClientRect();
  const overlapW = Math.min(h.right, d.right) - Math.max(h.left, d.left);
  const overlapH = Math.min(h.bottom, d.bottom) - Math.max(h.top, d.top);
  if (overlapW <= 1 || overlapH <= 1) return { right: 0, bottom: 0 };
  return {
    right: Math.max(0, h.right - d.left) + 10,
    bottom: Math.max(0, h.bottom - d.top) + 10,
  };
}

function dockObstacle(host: HTMLElement): { x0: number; y0: number; x1: number; y1: number } | null {
  const dock = document.querySelector("[data-testid='media-dock']");
  if (!dock) return null;
  const h = host.getBoundingClientRect();
  const d = dock.getBoundingClientRect();
  const box = {
    x0: d.left - h.left,
    y0: d.top - h.top,
    x1: d.right - h.left,
    y1: d.bottom - h.top,
  };
  if (box.x1 < 0 || box.y1 < 0 || box.x0 > h.width || box.y0 > h.height) return null;
  return box;
}

/**
 * fitView only pads every side by the same fraction. Place the points in the
 * larger of the two rectangles that clear the dock: above it, or to its left.
 */
function fitClearingCorner(graph: Graph, host: HTMLElement): void {
  const zoom = zoomApi(graph);
  const positions = graph.getPointPositions();
  if (!zoom || positions.length < 2) {
    graph.fitView(0, FIT_PAD, false);
    return;
  }
  const fitted = zoom.getTransform(positions, undefined, 0);
  if (!Number.isFinite(fitted.k) || fitted.k <= 0) {
    graph.fitView(0, FIT_PAD, false);
    return;
  }
  graph.setViewTransform(fitted);

  const width = host.getBoundingClientRect().width;
  const height = host.getBoundingClientRect().height;
  if (width < 2 || height < 2) return;

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < positions.length; i += 2) {
    const sx = positions[i];
    const sy = positions[i + 1];
    if (!Number.isFinite(sx) || !Number.isFinite(sy)) continue;
    const screen = graph.spaceToScreenPosition([sx, sy]);
    if (screen[0] < minX) minX = screen[0];
    if (screen[0] > maxX) maxX = screen[0];
    if (screen[1] < minY) minY = screen[1];
    if (screen[1] > maxY) maxY = screen[1];
  }
  if (!Number.isFinite(minX) || maxX - minX < 1 || maxY - minY < 1) return;

  const unitsW = (maxX - minX) / fitted.k;
  const unitsH = (maxY - minY) / fitted.k;
  const scaleCx = ((minX + maxX) / 2 - fitted.x) / fitted.k;
  const scaleCy = ((minY + maxY) / 2 - fitted.y) / fitted.k;
  const place = (safeW: number, safeH: number): ViewTransform | null => {
    const innerW = safeW * (1 - FIT_PAD * 2);
    const innerH = safeH * (1 - FIT_PAD * 2);
    if (innerW < 40 || innerH < 40 || unitsW < 1 || unitsH < 1) return null;
    const k = Math.min(innerW / unitsW, innerH / unitsH);
    if (!Number.isFinite(k) || k <= 0) return null;
    return {
      k,
      x: safeW / 2 - scaleCx * k,
      y: safeH / 2 - scaleCy * k,
    };
  };

  const { right, bottom } = dockIntrusion(host);
  const above = bottom > 1 ? place(width, height - bottom) : null;
  const beside = right > 1 ? place(width - right, height) : null;
  const clearing = [above, beside].filter((item): item is ViewTransform => item !== null);
  const best = clearing.length > 0 ? clearing.reduce((a, b) => (b.k > a.k ? b : a)) : place(width, height);
  if (best) graph.setViewTransform(best);
}

/** deg_growth is a natural log. Show exp(log) − 1, as a percent or a ratio. */
function formatDegreeGrowth(logGrowth: number): string {
  const ratio = Math.exp(logGrowth);
  if (!Number.isFinite(ratio)) return "n/d";
  const pct = (ratio - 1) * 100;
  if (Math.abs(pct) >= 1000) {
    return `×${ratio.toFixed(ratio >= 100 ? 0 : 1)}`;
  }
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(0)}%`;
}

const COMMUNITY_COLORS: Array<[number, number, number]> = [
  [56, 189, 248], // sky blue
  [251, 146, 60], // orange
  [168, 85, 247], // purple
  [34, 197, 94], // emerald
  [244, 63, 94], // rose
  [250, 204, 21], // yellow
  [45, 212, 191], // teal
  [129, 140, 248], // indigo
];

export function TemporalGraph({
  week,
  focusTopic,
  highlight = [],
  colorBy = "decision",
  captionEs,
  isFullscreen = false,
  onToggleFullscreen,
  onSelectTopic,
  onOpenStory,
  onLensChange,
  dockOpen = false,
}: TemporalGraphProps) {
  const canvasHostRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const graphConfigRef = useRef<GraphConfig | null>(null);
  const graphReadyRef = useRef(false);
  const dataRef = useRef<TemporalGraphData | null>(null);
  const [data, setData] = useState<TemporalGraphData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [noGraphics, setNoGraphics] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [weekIdx, setWeekIdx] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);
  const activeLens = graphLensFromColorBy(colorBy);
  const activeLensRef = useRef(activeLens);
  activeLensRef.current = activeLens;
  const reheatRef = useRef<() => void>(() => {});
  const reheatTokenRef = useRef(0);
  // Null until the first time a live graph sees a lens. That pass stays frozen.
  const reheatKeyRef = useRef<string | null>(null);
  const [labels, setLabels] = useState<LabelItem[]>([]);
  const [hoveredTooltip, setHoveredTooltip] = useState<TooltipItem | null>(null);
  const [metricsSnapshot, setMetricsSnapshot] = useState<{
    firstFrameMs?: number;
    fpsPlaying?: number;
    medianSwitchMs?: number;
    fpsRelayout?: number;
    settleTimeMs?: number;
  }>({});

  const highlightSet = useMemo(() => {
    const s = new Set<string>(highlight.map((h) => h.toLowerCase()));
    if (focusTopic) s.add(focusTopic.toLowerCase());
    return s;
  }, [highlight, focusTopic]);

  // Index map of node id -> position index
  const nodeIdMap = useMemo(() => {
    const map = new Map<string, number>();
    if (data?.nodes) {
      data.nodes.forEach((n, i) => map.set(n.id.toLowerCase(), i));
    }
    return map;
  }, [data]);

  const focusTopicIdx = useMemo(() => {
    if (!focusTopic) return null;
    return nodeIdMap.get(focusTopic.toLowerCase()) ?? null;
  }, [focusTopic, nodeIdMap]);

  // Cached week link lookups
  const weekLinkMapRef = useRef<
    Array<{
      src: number[];
      tgt: number[];
      n: number[];
      npmi: number[];
      edgeState: string[];
      nGrowth: number[];
      crossRing: boolean[];
      incidentMap: Map<number, number[]>;
    }>
  >([]);

  const recomputeLabels = useCallback(
    (w: number) => {
      const d = dataRef.current;
      const g = graphRef.current;
      const host = canvasHostRef.current;
      if (!d || !g || !host) return;

      const rect = host.getBoundingClientRect();
      const width = rect.width || 680;
      const height = rect.height || 440;

      const candidates: LabelItem[] = [];
      for (let i = 0; i < d.nodes.length; i++) {
        const node = d.nodes[i];
        const isFocused = highlightSet.has(node.id.toLowerCase());
        const rk = node.rank?.[w] ?? null;
        const isTop10 = rk !== null && rk >= 1 && rk <= 10;
        const show = node.show_label || isTop10 || isFocused;
        if (!show) continue;

        const screen = g.spaceToScreenPosition([node.x, node.y]);
        const sx = screen[0];
        const sy = screen[1];
        if (sx < 28 || sx > width - 28 || sy < 18 || sy > height - 22) {
          continue;
        }

        const pr = node.pagerank?.[w] ?? 0;
        const dg = node.deg_growth?.[w] ?? 0;
        const decision: DecisionValue = node.decision?.[w] ?? "no_es_tema_caliente";

        const priority =
          (isFocused ? 10000 : 0) +
          (isTop10 ? 5000 - (rk ?? 10) * 100 : 0) +
          (decision === "publicar_ahora" || decision === "preparar" ? 600 : 0) +
          pr * 100000 +
          Math.max(0, dg) * 40;

        candidates.push({
          idx: i,
          id: node.id,
          text: displayName(node.label_es || node.label || node.id),
          x: sx,
          y: sy,
          priority,
          decision,
          isFocused,
        });
      }

      candidates.sort((a, b) => b.priority - a.priority);

      const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
      const accepted: LabelItem[] = [];
      const maxLabels = 26;
      const obstacle = dockObstacle(host);

      for (const cand of candidates) {
        if (accepted.length >= maxLabels && !cand.isFocused) break;
        const estW = Math.min(185, Math.max(54, cand.text.length * 6.4 + 14));
        const estH = 20;
        const half = estW / 2;
        const pad = 4;
        if (cand.x - half < pad) cand.x = half + pad;
        if (cand.x + half > width - pad) cand.x = width - pad - half;
        if (cand.x - half < pad || cand.x + half > width - pad) continue;
        const box = {
          x0: cand.x - half,
          y0: cand.y - estH - 5,
          x1: cand.x + half,
          y1: cand.y + 4,
        };
        if (
          obstacle &&
          box.x0 < obstacle.x1 &&
          box.x1 > obstacle.x0 &&
          box.y0 < obstacle.y1 &&
          box.y1 > obstacle.y0
        ) {
          continue;
        }
        let collides = false;
        for (const p of placed) {
          if (box.x0 < p.x1 && box.x1 > p.x0 && box.y0 < p.y1 && box.y1 > p.y0) {
            collides = true;
            break;
          }
        }
        if (!collides || cand.isFocused) {
          placed.push(box);
          accepted.push(cand);
        }
      }

      setLabels(accepted);
    },
    [highlightSet],
  );

  // Apply lens styling to graph
  const applyLensToGraph = useCallback(
    (w: number, lens: LensMode, opts?: { reheat?: boolean }) => {
      const g = graphRef.current;
      const d = dataRef.current;
      const wMap = weekLinkMapRef.current[w];
      if (!g || !d || !wMap) return;

      const nNodes = d.nodes.length;
      const mLinks = wMap.src.length;

      const sizes = new Float32Array(nNodes);
      const colors = new Float32Array(nNodes * 4);
      const links = new Float32Array(mLinks * 2);
      const linkWidths = new Float32Array(mLinks);
      const linkColors = new Float32Array(mLinks * 4);
      const linkStrength = new Float32Array(mLinks);

      // Assemble links buffer
      for (let e = 0; e < mLinks; e++) {
        links[e * 2] = wMap.src[e];
        links[e * 2 + 1] = wMap.tgt[e];
      }

      // Compute week maximums for relative scaling
      let maxBetweenness = 0.005;
      for (let i = 0; i < nNodes; i++) {
        const b = d.nodes[i].betweenness?.[w] ?? 0;
        if (b > maxBetweenness) maxBetweenness = b;
      }

      const focusIdx = focusTopicIdx;
      const focusIncidentSet =
        focusIdx !== null ? new Set(wMap.incidentMap.get(focusIdx) ?? []) : null;

      // 1. Style nodes by lens
      for (let i = 0; i < nNodes; i++) {
        const node = d.nodes[i];
        const isFocused = highlightSet.has(node.id.toLowerCase());
        const rk = node.rank?.[w] ?? null;
        const isTop10 = rk !== null && rk >= 1 && rk <= 10;
        const imp = node.importance?.[w] ?? 0.3;
        const dec = node.decision?.[w] ?? "no_es_tema_caliente";
        const ring = node.ring ?? "ai_domain";

        let sz = 3.5 + imp * 8.5;
        let r = 100 / 255;
        let gCol = 116 / 255;
        let b = 139 / 255;
        let a = 0.55;

        switch (lens) {
          case "decision": {
            // Highlight is a halo (size), not a new colour: the cartographer
            // highlights the whole top 10, and those nodes must keep their decision.
            if (dec === "publicar_ahora") {
              r = 34 / 255;
              gCol = 197 / 255;
              b = 94 / 255;
              a = 0.98;
            } else if (dec === "preparar") {
              r = 56 / 255;
              gCol = 189 / 255;
              b = 248 / 255;
              a = 0.96;
            } else if (dec === "esperar") {
              r = 245 / 255;
              gCol = 158 / 255;
              b = 11 / 255;
              a = 0.92;
            } else {
              r = 100 / 255;
              gCol = 116 / 255;
              b = 139 / 255;
              a = 0.45;
            }
            if (isFocused) sz = Math.max(sz, 16.0);
            else if (isTop10) sz = Math.max(sz, 13.0);
            break;
          }

          case "segment": {
            if (isFocused) {
              r = 255 / 255;
              gCol = 255 / 255;
              b = 255 / 255;
              a = 1.0;
              sz = Math.max(sz, 18.0);
            } else if (ring === "ai") {
              r = 168 / 255;
              gCol = 85 / 255;
              b = 247 / 255;
              a = 0.98; // core AI: bright magenta
            } else if (ring === "it") {
              r = 14 / 255;
              gCol = 165 / 255;
              b = 233 / 255;
              a = 0.95; // IT tech: cyan
            } else {
              r = 249 / 255;
              gCol = 115 / 255;
              b = 22 / 255;
              a = 0.92; // Domain: orange
            }
            if (focusIdx !== null && i !== focusIdx) {
              const isNeighbor = focusIncidentSet?.has(i);
              if (!isNeighbor) a = 0.15;
            }
            break;
          }

          case "bridge": {
            const cr = node.cross_ring_share?.[w] ?? 0;
            const bet = node.betweenness?.[w] ?? 0;
            sz = 3.2 + Math.min(1.0, bet / maxBetweenness) * 16.0;
            // Sequential gradient: dark navy -> violet -> bright amber gold
            if (cr >= 0.7) {
              r = 250 / 255;
              gCol = 204 / 255;
              b = 21 / 255;
              a = 1.0;
            } else if (cr >= 0.35) {
              r = 249 / 255;
              gCol = 115 / 255;
              b = 22 / 255;
              a = 0.95;
            } else if (cr > 0.05) {
              r = 168 / 255;
              gCol = 85 / 255;
              b = 247 / 255;
              a = 0.88;
            } else {
              r = 30 / 255;
              gCol = 58 / 255;
              b = 138 / 255;
              a = 0.55;
            }
            break;
          }

          case "momentum": {
            const mom = node.momentum?.[w] ?? 0.5;
            sz = 3.2 + imp * 8.5;
            if (mom >= 0.9) {
              r = 239 / 255;
              gCol = 68 / 255;
              b = 68 / 255;
              a = 1.0;
              sz = Math.max(sz * 1.5, 14.0); // Top decile glow boost
            } else if (mom >= 0.7) {
              r = 249 / 255;
              gCol = 115 / 255;
              b = 22 / 255;
              a = 0.95;
            } else if (mom >= 0.4) {
              r = 148 / 255;
              gCol = 163 / 255;
              b = 184 / 255;
              a = 0.65;
            } else {
              r = 59 / 255;
              gCol = 130 / 255;
              b = 246 / 255;
              a = 0.8;
            }
            break;
          }

          case "novelty": {
            const newRate = node.new_nbr_rate?.[w] ?? 0;
            sz = 3.2 + imp * 8.5;
            if (newRate >= 0.35) {
              r = 6 / 255;
              gCol = 182 / 255;
              b = 212 / 255;
              a = 1.0; // Neon cyan
            } else if (newRate >= 0.2) {
              r = 45 / 255;
              gCol = 212 / 255;
              b = 191 / 255;
              a = 0.88;
            } else {
              r = 71 / 255;
              gCol = 85 / 255;
              b = 105 / 255;
              a = 0.55;
            }
            break;
          }

          case "community": {
            const cId = node.community_week?.[w] ?? null;
            if (cId !== null && cId >= 0) {
              const pal = COMMUNITY_COLORS[cId % COMMUNITY_COLORS.length];
              r = pal[0] / 255;
              gCol = pal[1] / 255;
              b = pal[2] / 255;
              a = 0.92;
            } else {
              r = 100 / 255;
              gCol = 116 / 255;
              b = 139 / 255;
              a = 0.4;
            }
            break;
          }

          case "tone": {
            const toneVal = node.tone?.[w] ?? 0.0;
            sz = 3.2 + imp * 8.5;
            if (toneVal >= 1.0) {
              r = 37 / 255;
              gCol = 99 / 255;
              b = 235 / 255;
              a = 0.95; // Blue positive
            } else if (toneVal <= -1.0) {
              r = 239 / 255;
              gCol = 68 / 255;
              b = 68 / 255;
              a = 0.95; // Red negative
            } else {
              r = 148 / 255;
              gCol = 163 / 255;
              b = 184 / 255;
              a = 0.65;
            }
            break;
          }

          case "window": {
            const winState = node.window_state?.[w] ?? "sin_estimacion";
            if (winState === "dias_restantes") {
              r = 16 / 255;
              gCol = 185 / 255;
              b = 129 / 255;
              a = 0.98; // Emerald
            } else if (winState === "en_cualquier_momento") {
              r = 139 / 255;
              gCol = 92 / 255;
              b = 246 / 255;
              a = 0.95; // Violet
            } else if (winState === "ya_en_espanol") {
              r = 56 / 255;
              gCol = 189 / 255;
              b = 248 / 255;
              a = 0.9; // Sky blue
            } else {
              r = 100 / 255;
              gCol = 116 / 255;
              b = 139 / 255;
              a = 0.45;
            }
            break;
          }
        }

        sizes[i] = sz;
        colors[i * 4] = r;
        colors[i * 4 + 1] = gCol;
        colors[i * 4 + 2] = b;
        colors[i * 4 + 3] = a;
      }

      // 2. Style links by lens & edge properties
      for (let e = 0; e < mLinks; e++) {
        const u = wMap.src[e];
        const v = wMap.tgt[e];
        const nVal = wMap.n[e];
        const npmiVal = wMap.npmi[e];
        const state = wMap.edgeState[e];
        const isCross = wMap.crossRing[e];

        let width = Math.max(0.45, Math.min(2.8, Math.log(nVal + 1) * 0.45));
        let alpha = Math.max(0.12, Math.min(0.85, npmiVal));
        // Resting links stay weak. Each lens raises a different class, so two
        // lenses pull the same nodes toward different neighbours.
        let strength = 0.15;
        let lr = 148 / 255;
        let lg = 163 / 255;
        let lb = 184 / 255;

        switch (lens) {
          case "decision": {
            const uTop = (d.nodes[u].rank?.[w] ?? 999) <= 10;
            const vTop = (d.nodes[v].rank?.[w] ?? 999) <= 10;
            if (uTop || vTop) {
              strength = 1.0;
              width = Math.max(width, 1.8);
              alpha = Math.max(alpha, 0.7);
              lr = 56 / 255;
              lg = 189 / 255;
              lb = 248 / 255;
            } else {
              strength = 0.25;
              alpha *= 0.5;
            }
            break;
          }

          case "segment": {
            const sameRing = d.nodes[u].ring === d.nodes[v].ring;
            if (focusIdx !== null && (u === focusIdx || v === focusIdx)) {
              strength = 1.35;
              width = Math.max(width, 2.4);
              alpha = 0.95;
              lr = 250 / 255;
              lg = 204 / 255;
              lb = 21 / 255;
            } else if (sameRing) {
              strength = 0.7;
            } else {
              strength = 0.12;
              alpha = 0.08;
            }
            break;
          }

          case "bridge": {
            if (isCross) {
              strength = 0.95;
              width = Math.max(width, 2.0);
              alpha = 0.85;
              lr = 251 / 255;
              lg = 191 / 255;
              lb = 36 / 255; // Highlight cross-ring in gold
            } else {
              alpha = 0.08;
              strength = 0.2;
            }
            break;
          }

          case "momentum": {
            if (state === "growing") {
              strength = 0.9;
              width = Math.max(width, 2.2);
              alpha = 0.92;
              lr = 249 / 255;
              lg = 115 / 255;
              lb = 22 / 255; // Bright orange for growing
            }
            break;
          }

          case "novelty": {
            if (state === "new") {
              strength = 0.95;
              width = Math.max(width, 2.2);
              alpha = 0.95;
              lr = 34 / 255;
              lg = 211 / 255;
              lb = 238 / 255; // Bright neon cyan
            } else if (state === "fading") {
              alpha = 0.06;
              strength = 0.1;
            }
            break;
          }

          case "community": {
            const cu = d.nodes[u].community_week?.[w];
            const cv = d.nodes[v].community_week?.[w];
            if (cu !== null && cu === cv) {
              strength = 1.1; // Strengthen intra-community edges
              alpha = Math.max(alpha, 0.7);
            } else {
              strength = 0.12;
              alpha = 0.06;
            }
            break;
          }

          case "tone": {
            const tu = d.nodes[u].tone?.[w] ?? 0;
            const tv = d.nodes[v].tone?.[w] ?? 0;
            const samePole = (tu >= 1 && tv >= 1) || (tu <= -1 && tv <= -1);
            if (samePole) {
              strength = 1.15;
              width = Math.max(width, 1.6);
              alpha = Math.max(alpha, 0.75);
            } else {
              strength = 0.1;
              alpha *= 0.45;
            }
            break;
          }

          case "window": {
            const wu = d.nodes[u].window_state?.[w] ?? null;
            const wv = d.nodes[v].window_state?.[w] ?? null;
            const shared =
              wu !== null && wv !== null && wu === wv && wu !== "sin_estimacion";
            if (shared) {
              strength = 1.2;
              width = Math.max(width, 1.7);
              alpha = Math.max(alpha, 0.8);
            } else {
              strength = 0.1;
              alpha *= 0.4;
            }
            break;
          }
        }

        if (
          highlightSet.has(d.nodes[u].id.toLowerCase()) ||
          highlightSet.has(d.nodes[v].id.toLowerCase())
        ) {
          strength = Math.max(strength, 1.35);
        }

        linkWidths[e] = width;
        linkStrength[e] = strength;
        linkColors[e * 4] = lr;
        linkColors[e * 4 + 1] = lg;
        linkColors[e * 4 + 2] = lb;
        linkColors[e * 4 + 3] = alpha;
      }

      g.setLinks(links);
      g.setLinkWidths(linkWidths);
      g.setLinkStrength(linkStrength);
      g.setPointSizes(sizes);
      g.setPointColors(colors);
      try {
        g.setLinkColors(linkColors);
      } catch {
        // Fallback for earlier versions
      }

      // Lens-driven clustering if window lens
      if (lens === "window") {
        const clusters: (number | undefined)[] = new Array(nNodes);
        for (let i = 0; i < nNodes; i++) {
          const st = d.nodes[i].window_state?.[w];
          clusters[i] =
            st === "dias_restantes"
              ? 1
              : st === "en_cualquier_momento"
                ? 2
                : st === "ya_en_espanol"
                  ? 3
                  : undefined;
        }
        try {
          g.setPointClusters(clusters);
          const strength = new Float32Array(nNodes).fill(0.45);
          g.setPointClusterStrength(strength);
        } catch {
          // Ignore if clustering not supported
        }
      } else {
        // A cluster assignment survives the next lens until it is cleared.
        try {
          g.setPointClusters(new Array<number | undefined>(nNodes).fill(undefined));
          g.setPointClusterStrength(new Float32Array(nNodes));
        } catch {
          // Ignore if clustering not supported
        }
      }

      g.setPinnedPoints(focusIdx !== null ? [focusIdx] : null);
      // Upload pending colours, widths and strengths without zeroing alpha.
      // render(0, 0) would stop the simulation after one frame.
      g.render(undefined, 0);
      recomputeLabels(w);

      if (opts?.reheat && lens === "segment" && focusIdx !== null) {
        try {
          g.setPointPosition(focusIdx, 2048, 2048);
        } catch {
          // No-op before the first render.
        }
        try {
          // enableSimulation false: zoom must not start a second simulation.
          g.zoomToPointByIndex(focusIdx, 400, 1.8, true, false);
        } catch {
          // ignore
        }
      }

      if (opts?.reheat) reheatRef.current();
    },
    [focusTopicIdx, highlightSet, recomputeLabels],
  );

  // Reheat from the strengths and pins just uploaded. Settle time is wall
  // clock until graph.progress stops changing (or the cap). fps is rAF during
  // that same interval, not a fixed timer.
  const reheatSimulation = useCallback(() => {
    const g = graphRef.current;
    const d = dataRef.current;
    if (!g || !d) return;

    const lens = activeLensRef.current;
    const nLinks = weekLinkMapRef.current[weekIdxRef.current]?.src.length ?? 0;
    if (nLinks >= REHEAT_LINK_CAP) {
      window.__metrics = {
        ...window.__metrics,
        active_lens: lens,
        reheat_skipped: `links>=${REHEAT_LINK_CAP}`,
      };
      return;
    }

    const token = ++reheatTokenRef.current;
    const t0 = performance.now();
    let frames = 0;
    let rafId = 0;
    const onFrame = () => {
      if (reheatTokenRef.current !== token) return;
      frames += 1;
      rafId = requestAnimationFrame(onFrame);
    };
    rafId = requestAnimationFrame(onFrame);

    const readSample = (): number[] => {
      const pos = g.getPointPositions();
      const sample: number[] = [];
      for (const i of LAYOUT_SAMPLE_INDEXES) {
        if (i >= d.nodes.length) continue;
        sample.push(Math.round(pos[i * 2] * 10) / 10, Math.round(pos[i * 2 + 1] * 10) / 10);
      }
      return sample;
    };
    let before: number[] = [];
    try {
      before = readSample();
    } catch {
      before = [];
    }

    try {
      // The graph is constructed with enableSimulation false so the exported
      // layout stays frozen. start() is a no-op until the flag is on.
      g.setConfigPartial({ enableSimulation: true });
      g.start(0.3);
    } catch {
      cancelAnimationFrame(rafId);
      window.__metrics = {
        ...window.__metrics,
        active_lens: lens,
        reheat_skipped: "start_failed",
      };
      return;
    }

    let lastProgress = g.progress;
    let stableTicks = 0;
    const timer = window.setInterval(() => {
      if (reheatTokenRef.current !== token) {
        window.clearInterval(timer);
        cancelAnimationFrame(rafId);
        return;
      }
      const progress = g.progress;
      const elapsed = performance.now() - t0;
      if (Number.isFinite(progress) && Math.abs(progress - lastProgress) < 1e-4) {
        stableTicks += 1;
      } else {
        stableTicks = 0;
      }
      lastProgress = progress;
      const settled =
        stableTicks >= REHEAT_STABLE_TICKS || !g.isSimulationRunning || elapsed >= REHEAT_CAP_MS;
      if (!settled) return;

      window.clearInterval(timer);
      cancelAnimationFrame(rafId);
      try {
        g.pause();
      } catch {
        // Already stopped.
      }
      const settleTimeMs = Math.round((performance.now() - t0) * 10) / 10;
      const fpsRelayout =
        Math.round((frames / Math.max(0.01, settleTimeMs / 1000)) * 10) / 10;
      let sample: number[] = [];
      try {
        sample = readSample();
      } catch {
        sample = [];
      }
      let layoutMoved: number | undefined;
      if (before.length > 0 && before.length === sample.length) {
        let acc = 0;
        for (let i = 0; i < sample.length; i++) acc += Math.abs(sample[i] - before[i]);
        layoutMoved = Math.round((acc / sample.length) * 10) / 10;
      }
      const byLens = { ...(window.__metrics?.layout_by_lens ?? {}) };
      const otherLens = Object.keys(byLens).find((key) => key !== lens);
      let layoutDelta: number | undefined;
      const other = otherLens ? byLens[otherLens] : undefined;
      if (other && other.length === sample.length && sample.length > 0) {
        let acc = 0;
        for (let i = 0; i < sample.length; i++) acc += Math.abs(sample[i] - other[i]);
        layoutDelta = Math.round((acc / sample.length) * 10) / 10;
      }
      byLens[lens] = sample;
      window.__metrics = {
        ...window.__metrics,
        active_lens: lens,
        fps_relayout: fpsRelayout,
        settle_time_ms: settleTimeMs,
        layout_sample: sample,
        layout_by_lens: byLens,
        layout_delta: layoutDelta,
        layout_moved: layoutMoved,
        sim_progress: Number.isFinite(progress) ? Math.round(progress * 1000) / 1000 : undefined,
        reheat_count: (window.__metrics?.reheat_count ?? 0) + 1,
        reheat_skipped: undefined,
      };
      setMetricsSnapshot((prev) => ({
        ...prev,
        fpsRelayout,
        settleTimeMs,
      }));
    }, REHEAT_TICK_MS);
  }, []);
  reheatRef.current = reheatSimulation;

  // Fetch temporal.json once
  useEffect(() => {
    let cancelled = false;
    const t0 = performance.now();
    setLoading(true);
    setError(null);

    fetch("/data/views/temporal.json")
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status} al cargar /data/views/temporal.json`);
        }
        const tFetchDone = performance.now();
        const text = await res.text();
        const parsed = JSON.parse(text) as TemporalGraphData;
        const tParseDone = performance.now();

        if (cancelled) return;
        const isoWeeks = parsed._meta.iso_weeks ?? parsed._meta.weeks;
        window.__metrics = {
          ...window.__metrics,
          t_fetch_ms: Math.round((tFetchDone - t0) * 10) / 10,
          t_parse_ms: Math.round((tParseDone - tFetchDone) * 10) / 10,
          n_nodes: parsed.nodes.length,
          n_weeks: isoWeeks.length,
        };
        dataRef.current = parsed;
        setData(parsed);

        let defaultIdx = isoWeeks.length - 1;
        if (week) {
          const idxIso = isoWeeks.indexOf(week);
          const idxWk = parsed._meta.weeks.indexOf(week);
          if (idxIso >= 0) defaultIdx = idxIso;
          else if (idxWk >= 0) defaultIdx = idxWk;
        }
        setWeekIdx(Math.max(0, defaultIdx));
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Update week index when prop `week` changes
  useEffect(() => {
    if (!data || !week) return;
    const isoWeeks = data._meta.iso_weeks ?? data._meta.weeks;
    const idxIso = isoWeeks.indexOf(week);
    const idxWk = data._meta.weeks.indexOf(week);
    if (idxIso >= 0) setWeekIdx(idxIso);
    else if (idxWk >= 0) setWeekIdx(idxWk);
  }, [week, data]);

  // Initialize cosmos.gl Graph once `data` and `canvasHostRef` are available
  useEffect(() => {
    if (!data) return;
    if (!browserHasGraphics()) {
      setNoGraphics(true);
      setLoading(false);
      return;
    }
    if (!canvasHostRef.current) return;
    // A new graph has not seen a lens yet. StrictMode's second setup must reheat
    // a focused story instead of treating the destroyed graph's key as current.
    reheatKeyRef.current = null;
    const host = canvasHostRef.current;
    const tInit0 = performance.now();

    const nNodes = data.nodes.length;
    const nWeeks = data._meta.weeks.length;
    const positions = new Float32Array(nNodes * 2);
    for (let i = 0; i < nNodes; i++) {
      const node = data.nodes[i];
      positions[i * 2] = node.x ?? 2048;
      positions[i * 2 + 1] = node.y ?? 2048;
    }

    // Group columnar edges by week index
    const linkMapByWeek = Array.from({ length: nWeeks }, () => ({
      src: [] as number[],
      tgt: [] as number[],
      n: [] as number[],
      npmi: [] as number[],
      edgeState: [] as string[],
      nGrowth: [] as number[],
      crossRing: [] as boolean[],
      incidentMap: new Map<number, number[]>(),
    }));

    const srcCol = data.edges.source;
    const tgtCol = data.edges.target;
    const wkCol = data.edges.week;
    const nCol = data.edges.n;
    const npmiCol = data.edges.npmi;
    const stateCol = data.edges.edge_state ?? [];
    const growthCol = data.edges.n_growth ?? [];
    const crossCol = data.edges.cross_ring ?? [];

    for (let e = 0; e < srcCol.length; e++) {
      const w = wkCol[e];
      if (w >= 0 && w < nWeeks) {
        const u = srcCol[e];
        const v = tgtCol[e];
        const entry = linkMapByWeek[w];
        entry.src.push(u);
        entry.tgt.push(v);
        entry.n.push(nCol[e]);
        entry.npmi.push(npmiCol[e]);
        entry.edgeState.push(stateCol[e] ?? "persisting");
        entry.nGrowth.push(growthCol[e] ?? 0);
        entry.crossRing.push(crossCol[e] ?? false);

        if (!entry.incidentMap.has(u)) entry.incidentMap.set(u, []);
        if (!entry.incidentMap.has(v)) entry.incidentMap.set(v, []);
        entry.incidentMap.get(u)!.push(v);
        entry.incidentMap.get(v)!.push(u);
      }
    }
    weekLinkMapRef.current = linkMapByWeek;

    // setConfig replaces the whole config, so a resize must pass this same object.
    const config: GraphConfig = {
      spaceSize: 4096,
      backgroundColor: "#0f172a",
      pointDefaultSize: 4,
      linkDefaultWidth: 0.65,
      linkDefaultColor: [148 / 255, 163 / 255, 184 / 255, 0.16],
      curvedLinks: true,
      linkColorInterpolateFromEndpoints: true,
      scalePointsOnZoom: true,
      enableSimulation: false,
      rescalePositions: false,
      fitViewOnInit: false,
      attribution: "",
      onZoom: () => {
        recomputeLabels(weekIdxRef.current);
      },
      onClick: (index) => {
        if (index !== undefined && data.nodes[index]) {
          onSelectTopic?.(data.nodes[index].id);
        }
      },
    };
    graphConfigRef.current = config;
    const graph = new Graph(host, config);

    graphRef.current = graph;
    const initialW = Math.max(0, Math.min(weekIdx, nWeeks - 1));
    graph.setPointPositions(positions);

    let disposed = false;
    void graph.ready.then(() => {
      if (disposed) return;
      // A lens change that already reheated owns the buffers. Otherwise upload
      // the current lens without starting the simulation.
      if (reheatTokenRef.current === 0) {
        applyLensRef.current(initialW, activeLensRef.current);
      }
      fitClearingCorner(graph, host);
      graphReadyRef.current = true;

      requestAnimationFrame(() => {
        if (disposed) return;
        const firstFrameMs =
          Math.round(
            ((window.__metrics?.t_fetch_ms ?? 0) +
              (window.__metrics?.t_parse_ms ?? 0) +
              (performance.now() - tInit0)) *
              10,
          ) / 10;

        let renderer = "WebGL2";
        const canvas = host.querySelector("canvas");
        const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl");
        if (gl) {
          const dbg = gl.getExtension("WEBGL_debug_renderer_info");
          renderer = dbg
            ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL))
            : String(gl.getParameter(gl.RENDERER));
        }

        window.__metrics = {
          ...window.__metrics,
          renderer,
          t_first_frame_ms: firstFrameMs,
          n_edges_w: linkMapByWeek[initialW]?.src.length ?? 0,
        };
        setMetricsSnapshot((prev) => ({ ...prev, firstFrameMs }));
        recomputeLabels(initialW);
      });
    });

    return () => {
      disposed = true;
      graphReadyRef.current = false;
      graphConfigRef.current = null;
      graph.destroy();
      graphRef.current = null;
    };
  }, [data]);

  const weekIdxRef = useRef<number>(weekIdx);
  const applyLensRef = useRef(applyLensToGraph);
  applyLensRef.current = applyLensToGraph;
  const recomputeLabelsRef = useRef(recomputeLabels);
  recomputeLabelsRef.current = recomputeLabels;

  // The library resizes its drawing buffer on its own. The camera stays framed
  // for the old box until we pass the full config and fit the new host size.
  useEffect(() => {
    const host = canvasHostRef.current;
    if (!host || !data || typeof ResizeObserver === "undefined") return;
    let frame = 0;
    let lastW = -1;
    let lastH = -1;

    const fitToHost = () => {
      frame = 0;
      const g = graphRef.current;
      const cfg = graphConfigRef.current;
      if (!g || !cfg || !graphReadyRef.current) return;
      const rect = host.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return;
      g.setConfig(cfg);
      applyLensRef.current(weekIdxRef.current, activeLensRef.current);
      fitClearingCorner(g, host);
      recomputeLabelsRef.current(weekIdxRef.current);
    };

    const scheduleFit = () => {
      if (!graphReadyRef.current) return;
      const rect = host.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return;
      if (
        lastW >= 0 &&
        Math.abs(rect.width - lastW) < 2 &&
        Math.abs(rect.height - lastH) < 2
      ) {
        return;
      }
      lastW = rect.width;
      lastH = rect.height;
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(fitToHost);
    };

    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (!rect || rect.width < 2 || rect.height < 2) return;
      scheduleFit();
    });
    observer.observe(host);

    // The first size often arrives before the graph is ready. Keep trying
    // until a fit lands, or that size is remembered and the labels never show.
    let tries = 0;
    const kick = () => {
      tries += 1;
      scheduleFit();
      if (lastW < 0 && tries < 180) {
        frame = requestAnimationFrame(kick);
      }
    };
    kick();

    return () => {
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [data]);

  // Opening the dock does not resize the canvas. Refit so labels clear it.
  useEffect(() => {
    const host = canvasHostRef.current;
    const g = graphRef.current;
    if (!host || !g || !graphReadyRef.current) return;
    const frame = requestAnimationFrame(() => {
      fitClearingCorner(g, host);
      recomputeLabelsRef.current(weekIdxRef.current);
    });
    return () => cancelAnimationFrame(frame);
  }, [dockOpen]);

  useEffect(() => {
    return () => {
      reheatTokenRef.current += 1;
    };
  }, []);

  // Week playback is a frozen sweep: upload colours and links, do not start().
  useEffect(() => {
    weekIdxRef.current = weekIdx;
    if (!data || !graphRef.current) return;
    const t0 = performance.now();
    applyLensRef.current(weekIdx, activeLensRef.current);
    const dt = Math.round((performance.now() - t0) * 100) / 100;
    const list = window.__metrics?.week_switch_ms ?? [];
    list.push(dt);
    window.__metrics = {
      ...window.__metrics,
      week_switch_ms: list,
      n_edges_w: weekLinkMapRef.current[weekIdx]?.src.length ?? 0,
    };
  }, [weekIdx, data]);

  // Pill clicks and chat answers both change color_by / focus. That is the
  // only path that reheats. The unfocused first paint stays on the exported
  // layout. A story that opens already focused still pins and zooms.
  useEffect(() => {
    if (!data || !graphRef.current) return;
    const key = `${activeLens}|${focusTopic ?? ""}|${highlight.join("\n")}`;
    if (reheatKeyRef.current === key) return;
    const first = reheatKeyRef.current === null;
    reheatKeyRef.current = key;
    if (first && !focusTopic) return;
    applyLensRef.current(weekIdxRef.current, activeLens, { reheat: true });
  }, [activeLens, focusTopic, highlight, data]);

  // Pill clicks write the same color_by a chat answer writes (App.onLensChange).
  const handleSelectLens = (lens: LensMode) => {
    onLensChange?.(lens);
  };

  // Play animation across weeks
  useEffect(() => {
    if (!playing || !data) return;
    let rafId = 0;
    let frames = 0;
    const tStart = performance.now();
    const countFrame = () => {
      frames += 1;
      rafId = requestAnimationFrame(countFrame);
    };
    rafId = requestAnimationFrame(countFrame);

    let stepCount = 0;
    const totalWeeks = data._meta.weeks.length;
    const interval = window.setInterval(() => {
      stepCount += 1;
      setWeekIdx((prev) => (prev + 1) % totalWeeks);
      if (stepCount >= totalWeeks) {
        const elapsedSec = Math.max(0.1, (performance.now() - tStart) / 1000);
        const fps = Math.round((frames / elapsedSec) * 10) / 10;
        const switches = window.__metrics?.week_switch_ms ?? [];
        const sorted = [...switches].sort((a, b) => a - b);
        const medianSwitch =
          sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : 0;
        window.__metrics = {
          ...window.__metrics,
          fps_playing: fps,
          sweep_done: true,
        };
        setMetricsSnapshot((prev) => ({
          ...prev,
          fpsPlaying: fps,
          medianSwitchMs: medianSwitch,
        }));
        setPlaying(false);
      }
    }, 220);

    return () => {
      window.clearInterval(interval);
      cancelAnimationFrame(rafId);
    };
  }, [playing, data]);

  // Hover node tooltip details builder
  const handleNodeHover = (nodeIdx: number, ev: React.MouseEvent) => {
    const d = dataRef.current;
    const wMap = weekLinkMapRef.current[weekIdx];
    if (!d || !wMap || !d.nodes[nodeIdx]) return;
    const node = d.nodes[nodeIdx];
    const neighbors: Array<{ id: string; label_es: string; n: number; npmi: number }> = [];
    const states = { new: 0, growing: 0, persisting: 0, fading: 0 };

    for (let e = 0; e < wMap.src.length; e++) {
      let other = -1;
      if (wMap.src[e] === nodeIdx) other = wMap.tgt[e];
      else if (wMap.tgt[e] === nodeIdx) other = wMap.src[e];
      if (other >= 0) {
        const st = wMap.edgeState[e] as "new" | "growing" | "persisting" | "fading";
        if (st in states) states[st] += 1;
        const oNode = d.nodes[other];
        neighbors.push({
          id: oNode.id,
          label_es: displayName(oNode.label_es || oNode.label || oNode.id),
          n: wMap.n[e],
          npmi: wMap.npmi[e],
        });
      }
    }
    neighbors.sort((a, b) => b.n - a.n);

    setHoveredTooltip({
      node,
      screenX: ev.clientX,
      screenY: ev.clientY,
      topNeighbors: neighbors.slice(0, 3),
      edgeStates: states,
    });
  };

  const isoWeeks = data?._meta?.iso_weeks ?? data?._meta?.weeks ?? [];
  const currentWeekStr =
    isoWeeks[weekIdx] ?? data?._meta?.weeks?.[weekIdx] ?? week ?? "2026-W42";
  const currentEdgesCount =
    data?._meta?.edges_per_week?.[weekIdx] ??
    weekLinkMapRef.current[weekIdx]?.src.length ??
    0;
  const topMovers: TemporalMover[] =
    data?._meta?.top_movers_per_week?.[weekIdx] ?? [];

  return (
    <div
      className={`temporal-graph-container${isFullscreen ? " temporal-fullscreen" : ""}`}
      data-testid="temporal-graph"
    >
      {/* Top Banner with Caption & Lens Switcher */}
      <div className="graph-lens-banner">
        <div className="lens-banner-left">
          <span className="lens-current-badge">
            Lente activo: <strong>{LENS_NAMES[activeLens]}</strong>
          </span>
          {captionEs && <span className="lens-caption-text">{captionEs}</span>}
        </div>
        <div className="lens-pills-bar" role="group" aria-label="Lentes del grafo">
          {(Object.keys(LENS_NAMES) as LensMode[]).map((lens) => (
            <button
              key={lens}
              type="button"
              className={`pill lens-pill${activeLens === lens ? " pill-active" : ""}`}
              onClick={() => handleSelectLens(lens)}
              data-testid={`lens-btn-${lens}`}
            >
              {LENS_NAMES[lens].split(" ")[0]}
            </button>
          ))}
          {onToggleFullscreen && (
            <button
              type="button"
              className="pill fs-toggle-pill"
              onClick={onToggleFullscreen}
              title="Alternar pantalla completa (tecla F)"
            >
              {isFullscreen ? "🗗 Salir (Esc)" : "⛶ Pantalla completa (F)"}
            </button>
          )}
        </div>
      </div>

      <div className="graph-toolbar">
        <button
          type="button"
          className={playing ? "graph-btn graph-btn-active" : "graph-btn"}
          data-testid="temporal-play-btn"
          onClick={() => setPlaying((p) => !p)}
          disabled={!data}
        >
          {playing ? "⏸ Pausar" : "▶ Reproducir 13 semanas"}
        </button>

        <label className="graph-slider-label">
          <span>Semana:</span>
          <input
            type="range"
            min={0}
            max={Math.max(0, isoWeeks.length - 1)}
            value={weekIdx}
            onChange={(e) => {
              setPlaying(false);
              setWeekIdx(Number(e.target.value));
            }}
            aria-label="Seleccionar semana del grafo temporal"
            data-testid="temporal-week-slider"
          />
          <strong className="graph-week-badge" data-testid="temporal-week-label">
            {currentWeekStr}
          </strong>
        </label>

        <span className="graph-stats-chip">
          {data ? (
            <>
              <strong>{data.nodes.length.toLocaleString()}</strong> nodos ·{" "}
              <strong>{currentEdgesCount.toLocaleString()}</strong> aristas (top-
              {data._meta.params.top_k_per_node} NPMI/nodo) ●
            </>
          ) : (
            "Cargando..."
          )}
        </span>
      </div>

      {error && (
        <div className="error-box" role="alert">
          No se pudo cargar el grafo temporal: {error}
        </div>
      )}

      {/* Focus topic notice if topic requested is outside the temporal top-1000 */}
      {focusTopic && focusTopicIdx === null && (
        <div className="graph-notice-box">
          <span>
            Este tema no figura entre los 1.000 nodos del grafo de esta semana.
          </span>
          {onOpenStory && (
            <button
              type="button"
              className="pill pill-primary"
              onClick={() => onOpenStory(focusTopic)}
            >
              Ver anillo de 1 salto
            </button>
          )}
        </div>
      )}

      <div className="temporal-split">
        <div className="temporal-canvas-wrap">
          {noGraphics ? (
            <div className="graph-fallback" data-testid="graph-fallback">
              <p>
                Este navegador no tiene aceleración gráfica activada; mostramos una imagen del grafo
              </p>
              <img src="/fallback/temporal.png" alt="Grafo temporal semanal" />
            </div>
          ) : (
            <>
          {loading && (
            <div className="graph-loading-overlay">
              Cargando el grafo…
            </div>
          )}
          <div
            ref={canvasHostRef}
            className="temporal-canvas-host"
            data-testid="temporal-canvas-host"
            onMouseLeave={() => setHoveredTooltip(null)}
          />
          <div className="temporal-labels-overlay" aria-hidden="true">
            {labels.map((lbl) => (
              <button
                key={lbl.id}
                type="button"
                className={`graph-node-label graph-label-${lbl.decision}${
                  lbl.isFocused ? " graph-label-focused" : ""
                }`}
                style={{
                  left: `${lbl.x}px`,
                  top: `${lbl.y}px`,
                }}
                onClick={() => onSelectTopic?.(lbl.id)}
                onMouseEnter={(ev) => handleNodeHover(lbl.idx, ev)}
                title={lbl.text}
              >
                {lbl.text}
              </button>
            ))}
          </div>

          {/* Lens Legend */}
          <div className="graph-legend">
            {activeLens === "decision" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-pub" /> Publicar ahora
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-prep" /> Preparar
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-esp" /> Esperar
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-ctx" /> Otros temas
                </span>
              </>
            )}
            {activeLens === "segment" && (
              <>
                <span className="legend-item">
                  Sector: IA / TI / otros sectores
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-ring-ai" /> IA
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-ring-it" /> TI
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-ring-dom" /> otros sectores
                </span>
              </>
            )}
            {activeLens === "bridge" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-bridge-high" /> cruce de sector 70%+ (Oro)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-bridge-mid" /> cruce de sector 35%+ (Naranja)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-bridge-low" /> mismo sector (Azul marino)
                </span>
                <span className="legend-item">
                  Tamaño = betweenness normalizada
                </span>
              </>
            )}
            {activeLens === "momentum" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-mom-top" /> Top 10% (Glow rojo)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-mom-high" /> Alto (Naranja)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-mom-low" /> Bajo (Azul)
                </span>
                <span className="legend-item">
                  Aristas naranjas = Crecientes (n +50%)
                </span>
              </>
            )}
            {activeLens === "novelty" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-nov-new" /> Nuevas conexiones (Cian)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-nov-pers" /> Persistentes (Gris)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-nov-fade" /> En declive (Atenuadas)
                </span>
              </>
            )}
            {activeLens === "community" && (
              <>
                <span className="legend-item">
                  Colores = Comunidades Leiden (seed 42, intra-semana)
                </span>
                <span className="legend-item">
                  Aristas intra-comunidad reforzadas
                </span>
              </>
            )}
            {activeLens === "tone" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-tone-pos" /> Tono positivo (&gt; +1.0)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-tone-neu" /> Tono neutro (-1.0 a +1.0)
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-tone-neg" /> Tono negativo (&lt; -1.0)
                </span>
              </>
            )}
            {activeLens === "window" && (
              <>
                <span className="legend-item">
                  <span className="legend-dot legend-win-days" /> Días restantes
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-win-any" /> En cualquier momento
                </span>
                <span className="legend-item">
                  <span className="legend-dot legend-win-es" /> Ya en español
                </span>
              </>
            )}
          </div>
            </>
          )}
        </div>

        <aside className="temporal-movers-aside" aria-label="Mayores subidas de la semana">
          <div className="movers-header">
            <h4>Temas destacados ({currentWeekStr})</h4>
            <span className="muted">Top priorizados y subidas de grado ●</span>
          </div>
          <ul className="movers-list">
            {topMovers.map((m) => {
              const dec = m.decision ?? "no_es_tema_caliente";
              return (
                <li key={m.id} className="mover-item">
                  <div className="mover-top">
                    <button
                      type="button"
                      className="mover-link"
                      onClick={() => {
                        onSelectTopic?.(m.id);
                        onOpenStory?.(m.id);
                      }}
                    >
                      {m.rank != null ? `#${m.rank} ` : ""}
                      {displayName(m.label_es)}
                    </button>
                    <span className={`decision-badge decision-${dec}`}>
                      {DECISION_LABELS_ES[dec]}
                    </span>
                  </div>
                  <div className="mover-meta">
                    {m.deg_growth != null && Number.isFinite(m.deg_growth) && (
                      <>
                        grado{" "}
                        <strong title="variación del grado">
                          {formatDegreeGrowth(m.deg_growth)}
                        </strong>
                      </>
                    )}
                    {m.pr_rank_delta != null && (
                      <>
                        {" "}
                        · ΔPR{" "}
                        <strong>
                          {m.pr_rank_delta >= 0 ? "+" : ""}
                          {m.pr_rank_delta}
                        </strong>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          {metricsSnapshot.firstFrameMs !== undefined && (
            <div className="graph-perf-footer">
              Render GPU: 1er cuadro <strong>{metricsSnapshot.firstFrameMs} ms</strong>
              {metricsSnapshot.fpsPlaying !== undefined && (
                <> · <strong>{metricsSnapshot.fpsPlaying} fps</strong></>
              )}
              {metricsSnapshot.medianSwitchMs !== undefined && (
                <> · cambio <strong>{metricsSnapshot.medianSwitchMs} ms</strong></>
              )}
              {metricsSnapshot.fpsRelayout !== undefined && (
                <> · re-layout <strong>{metricsSnapshot.fpsRelayout} fps</strong> ({metricsSnapshot.settleTimeMs} ms)</>
              )}{" "}
              ●
            </div>
          )}
        </aside>
      </div>

      {/* Hover Node Tooltip (Addendum 3 Nice) */}
      {hoveredTooltip && (
        <div
          className="graph-hover-tooltip"
          style={{
            left: `${Math.min(window.innerWidth - 260, hoveredTooltip.screenX + 14)}px`,
            top: `${Math.max(10, hoveredTooltip.screenY - 140)}px`,
          }}
        >
          <div className="tooltip-title">
            <strong>{displayName(hoveredTooltip.node.label_es)}</strong>
            <span
              className={`badge ring-badge-${hoveredTooltip.node.ring}`}
              title="Sector: IA / TI / otros sectores"
            >
              {hoveredTooltip.node.ring.toUpperCase() === "OTHER"
                ? "Otros"
                : hoveredTooltip.node.ring.toUpperCase()}
            </span>
          </div>
          <div className="tooltip-sub">
            {hoveredTooltip.node.domain ?? ""}
          </div>
          <div className="tooltip-metrics-grid">
            <div>
              Importancia:{" "}
              <strong>
                {hoveredTooltip.node.importance?.[weekIdx] !== null &&
                hoveredTooltip.node.importance?.[weekIdx] !== undefined
                  ? `${(hoveredTooltip.node.importance[weekIdx]! * 100).toFixed(0)}%`
                  : "N/D"}
              </strong>
            </div>
            <div>
              Betweenness:{" "}
              <strong>
                {hoveredTooltip.node.betweenness?.[weekIdx] !== null &&
                hoveredTooltip.node.betweenness?.[weekIdx] !== undefined
                  ? hoveredTooltip.node.betweenness[weekIdx]!.toFixed(4)
                  : "N/D"}
              </strong>
            </div>
            <div>
              cruce de sector:{" "}
              <strong>
                {hoveredTooltip.node.cross_ring_share?.[weekIdx] !== null &&
                hoveredTooltip.node.cross_ring_share?.[weekIdx] !== undefined
                  ? `${(hoveredTooltip.node.cross_ring_share[weekIdx]! * 100).toFixed(0)}%`
                  : "N/D"}
              </strong>
            </div>
            <div>
              Momento:{" "}
              <strong>
                {hoveredTooltip.node.momentum?.[weekIdx] !== null &&
                hoveredTooltip.node.momentum?.[weekIdx] !== undefined
                  ? `${(hoveredTooltip.node.momentum[weekIdx]! * 100).toFixed(0)}%`
                  : "N/D"}
              </strong>
            </div>
          </div>
          {hoveredTooltip.topNeighbors.length > 0 && (
            <div className="tooltip-neighbors">
              <span className="tooltip-section-label">Vecinos principales:</span>
              <ul>
                {hoveredTooltip.topNeighbors.map((nbr) => (
                  <li key={nbr.id}>
                    {nbr.label_es} (n={nbr.n}, npmi={nbr.npmi.toFixed(2)})
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="tooltip-states">
            Nuevas: {hoveredTooltip.edgeStates.new} · Crecientes:{" "}
            {hoveredTooltip.edgeStates.growing} · Fading: {hoveredTooltip.edgeStates.fading}
          </div>
        </div>
      )}
    </div>
  );
}
