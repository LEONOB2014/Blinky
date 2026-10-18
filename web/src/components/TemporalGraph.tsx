import { Graph } from "@cosmos.gl/graph";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DecisionValue } from "../types/contracts";
import type { TemporalGraphData, TemporalMover } from "../types/views";

interface TemporalGraphProps {
  week?: string | null;
  focusTopic?: string | null;
  highlight?: string[];
  onSelectTopic?: (topicId: string) => void;
  onOpenStory?: (topicId: string) => void;
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

const DECISION_CODE_TO_VALUE: Record<number, DecisionValue> = {
  3: "publicar_ahora",
  2: "preparar",
  1: "esperar",
  0: "no_es_tema_caliente",
};

const DECISION_LABELS_ES: Record<DecisionValue, string> = {
  publicar_ahora: "Publicar ahora",
  preparar: "Preparar",
  esperar: "Esperar",
  no_es_tema_caliente: "No es tema caliente",
};

export function TemporalGraph({
  week,
  focusTopic,
  highlight = [],
  onSelectTopic,
  onOpenStory,
}: TemporalGraphProps) {
  const canvasHostRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const dataRef = useRef<TemporalGraphData | null>(null);
  const weekArraysRef = useRef<{
    links: Float32Array[];
    widths: Float32Array[];
    sizes: Float32Array[];
    colors: Float32Array[];
  } | null>(null);

  const [data, setData] = useState<TemporalGraphData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [weekIdx, setWeekIdx] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);
  const [labels, setLabels] = useState<LabelItem[]>([]);
  const [metricsSnapshot, setMetricsSnapshot] = useState<{
    firstFrameMs?: number;
    fpsPlaying?: number;
    medianSwitchMs?: number;
  }>({});

  const highlightSet = useMemo(() => {
    const s = new Set<string>(highlight.map((h) => h.toLowerCase()));
    if (focusTopic) s.add(focusTopic.toLowerCase());
    return s;
  }, [highlight, focusTopic]);

  const recomputeLabels = useCallback(
    (w: number) => {
      const d = dataRef.current;
      const g = graphRef.current;
      const host = canvasHostRef.current;
      if (!d || !g || !host) return;

      const rect = host.getBoundingClientRect();
      const width = rect.width || 680;
      const height = rect.height || 460;

      const prArr = d.node_metrics.pagerank_pct;
      const decArr = d.node_metrics.decision_code;
      const rankArr = d.node_metrics.rank;
      const degGrowthArr = d.node_metrics.deg_growth;

      const candidates: LabelItem[] = [];
      for (let i = 0; i < d.nodes.length; i++) {
        const nodeId = d.nodes[i];
        const isFocused = highlightSet.has(nodeId.toLowerCase());
        const rk = rankArr?.[i]?.[w] ?? null;
        const isTop10 = rk !== null && rk >= 1 && rk <= 10;
        const show = d.show_label?.[i] || isTop10 || isFocused;
        if (!show) continue;

        const pos = d.positions[i];
        if (!pos) continue;
        const screen = g.spaceToScreenPosition([pos[0], pos[1]]);
        const sx = screen[0];
        const sy = screen[1];
        if (sx < 24 || sx > width - 24 || sy < 18 || sy > height - 18) {
          continue;
        }

        const pr = prArr?.[i]?.[w] ?? 0;
        const dg = degGrowthArr?.[i]?.[w] ?? 0;
        const decCode = decArr?.[i]?.[w] ?? 0;
        const decision = DECISION_CODE_TO_VALUE[decCode] ?? "no_es_tema_caliente";

        const priority =
          (isFocused ? 10000 : 0) +
          (isTop10 ? 5000 - (rk ?? 10) * 100 : 0) +
          (decCode >= 2 ? 600 : 0) +
          pr * 3 +
          Math.max(0, dg) * 40;

        candidates.push({
          idx: i,
          id: nodeId,
          text: d.labels_es?.[i] || d.labels?.[i] || nodeId,
          x: sx,
          y: sy,
          priority,
          decision,
          isFocused,
        });
      }

      candidates.sort((a, b) => b.priority - a.priority);

      // Greedy bounding-box collision avoidance so labels stay readable
      const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
      const accepted: LabelItem[] = [];
      const maxLabels = 24;

      for (const cand of candidates) {
        if (accepted.length >= maxLabels && !cand.isFocused) break;
        const estW = Math.min(180, Math.max(54, cand.text.length * 6.4 + 14));
        const estH = 20;
        const box = {
          x0: cand.x - estW / 2,
          y0: cand.y - estH - 5,
          x1: cand.x + estW / 2,
          y1: cand.y + 4,
        };
        let collides = false;
        for (const p of placed) {
          if (
            box.x0 < p.x1 &&
            box.x1 > p.x0 &&
            box.y0 < p.y1 &&
            box.y1 > p.y0
          ) {
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

  const applyWeekToGraph = useCallback(
    (w: number) => {
      const g = graphRef.current;
      const arrays = weekArraysRef.current;
      if (!g || !arrays) return;
      const clamped = Math.max(0, Math.min(w, arrays.links.length - 1));
      g.setLinks(arrays.links[clamped]);
      g.setLinkWidths(arrays.widths[clamped]);
      g.setPointSizes(arrays.sizes[clamped]);
      g.setPointColors(arrays.colors[clamped]);
      g.render(0, 0);
      recomputeLabels(clamped);
    },
    [recomputeLabels],
  );

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
        window.__metrics = {
          ...window.__metrics,
          t_fetch_ms: Math.round((tFetchDone - t0) * 10) / 10,
          t_parse_ms: Math.round((tParseDone - tFetchDone) * 10) / 10,
          n_nodes: parsed.nodes.length,
          n_weeks: parsed.weeks.length,
        };
        dataRef.current = parsed;
        setData(parsed);

        const defaultIdx =
          week && parsed.weeks.includes(week)
            ? parsed.weeks.indexOf(week)
            : parsed.weeks.length - 1;
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
    const idx = data.weeks.indexOf(week);
    if (idx >= 0) {
      setWeekIdx(idx);
    }
  }, [week, data]);

  // Initialize cosmos.gl Graph once `data` and `canvasHostRef` are available
  useEffect(() => {
    if (!data || !canvasHostRef.current) return;
    const host = canvasHostRef.current;
    const tInit0 = performance.now();

    const nNodes = data.nodes.length;
    const nWeeks = data.weeks.length;
    const positions = new Float32Array(nNodes * 2);
    for (let i = 0; i < nNodes; i++) {
      const xy = data.positions?.[i] ?? [2048, 2048];
      positions[i * 2] = xy[0];
      positions[i * 2 + 1] = xy[1];
    }

    const prArr = data.node_metrics.pagerank_pct;
    const dgArr = data.node_metrics.deg_growth;
    const decArr = data.node_metrics.decision_code;
    const rankArr = data.node_metrics.rank;

    const linksPerWeek: Float32Array[] = [];
    const widthsPerWeek: Float32Array[] = [];
    const sizesPerWeek: Float32Array[] = [];
    const colorsPerWeek: Float32Array[] = [];

    for (let w = 0; w < nWeeks; w++) {
      const rawEdges = data.edges_by_week[w] ?? [];
      const links = new Float32Array(rawEdges.length * 2);
      const widths = new Float32Array(rawEdges.length);
      for (let e = 0; e < rawEdges.length; e++) {
        links[e * 2] = rawEdges[e][0];
        links[e * 2 + 1] = rawEdges[e][1];
        const npmi = rawEdges[e][3] ?? 0.2;
        widths[e] = Math.max(0.45, Math.min(2.2, npmi * 2.5));
      }
      linksPerWeek.push(links);
      widthsPerWeek.push(widths);

      const sizes = new Float32Array(nNodes);
      const colors = new Float32Array(nNodes * 4);
      for (let i = 0; i < nNodes; i++) {
        const nodeId = data.nodes[i].toLowerCase();
        const isFocused = highlightSet.has(nodeId);
        const pr = prArr?.[i]?.[w] ?? 20;
        const dg = dgArr?.[i]?.[w] ?? 0;
        const dec = decArr?.[i]?.[w] ?? 0;
        const rk = rankArr?.[i]?.[w] ?? null;
        const isTop10 = rk !== null && rk >= 1 && rk <= 10;

        let sz = 2.8 + (pr / 100) * 8.5;
        if (isTop10) sz = Math.max(sz, 11.5);
        if (isFocused) sz = Math.max(sz, 14.5);
        sizes[i] = sz;

        if (isFocused) {
          // Rose highlight
          colors[i * 4] = 244;
          colors[i * 4 + 1] = 63;
          colors[i * 4 + 2] = 94;
          colors[i * 4 + 3] = 255;
        } else if (dec === 3) {
          // publicar_ahora: emerald green
          colors[i * 4] = 34;
          colors[i * 4 + 1] = 197;
          colors[i * 4 + 2] = 94;
          colors[i * 4 + 3] = 245;
        } else if (dec === 2) {
          // preparar: bright sky blue
          colors[i * 4] = 56;
          colors[i * 4 + 1] = 189;
          colors[i * 4 + 2] = 248;
          colors[i * 4 + 3] = 240;
        } else if (dec === 1) {
          // esperar: amber
          colors[i * 4] = 245;
          colors[i * 4 + 1] = 158;
          colors[i * 4 + 2] = 11;
          colors[i * 4 + 3] = 225;
        } else if (dg >= 0.35) {
          // Fast-growing unranked neighbor: teal
          colors[i * 4] = 45;
          colors[i * 4 + 1] = 212;
          colors[i * 4 + 2] = 191;
          colors[i * 4 + 3] = 195;
        } else {
          // Background context node: slate
          colors[i * 4] = 100;
          colors[i * 4 + 1] = 116;
          colors[i * 4 + 2] = 139;
          colors[i * 4 + 3] = 135;
        }
      }
      sizesPerWeek.push(sizes);
      colorsPerWeek.push(colors);
    }

    weekArraysRef.current = {
      links: linksPerWeek,
      widths: widthsPerWeek,
      sizes: sizesPerWeek,
      colors: colorsPerWeek,
    };

    const graph = new Graph(host, {
      spaceSize: 4096,
      backgroundColor: "#0f172a",
      pointDefaultSize: 4,
      linkDefaultWidth: 0.7,
      linkDefaultColor: [148, 163, 184, 42],
      curvedLinks: false,
      scalePointsOnZoom: true,
      enableSimulation: false,
      rescalePositions: false,
      fitViewOnInit: false,
      attribution: "",
      onZoom: () => {
        const currentW = weekIdxRef.current;
        recomputeLabels(currentW);
      },
      onClick: (index) => {
        if (index !== undefined && data.nodes[index]) {
          onSelectTopic?.(data.nodes[index]);
        }
      },
    });

    graphRef.current = graph;
    const initialW = Math.max(0, Math.min(weekIdx, nWeeks - 1));
    graph.setPointPositions(positions);
    graph.setLinks(linksPerWeek[initialW]);
    graph.setLinkWidths(widthsPerWeek[initialW]);
    graph.setPointSizes(sizesPerWeek[initialW]);
    graph.setPointColors(colorsPerWeek[initialW]);
    graph.render(0, 0);

    let disposed = false;
    void graph.ready.then(() => {
      if (disposed) return;
      graph.fitView(0, 0.08, false);
      requestAnimationFrame(() => {
        if (disposed) return;
        const firstFrameMs =
          Math.round(
            ((window.__metrics?.t_fetch_ms ?? 0) +
              (window.__metrics?.t_parse_ms ?? 0) +
              (performance.now() - tInit0)) *
              10,
          ) / 10;

        // Detect WebGL renderer string
        let renderer = "WebGL2 (cosmos.gl)";
        const canvas = host.querySelector("canvas");
        const gl =
          canvas?.getContext("webgl2") || canvas?.getContext("webgl");
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
          n_edges_w: (data.edges_by_week[initialW] ?? []).length,
        };
        setMetricsSnapshot((prev) => ({ ...prev, firstFrameMs }));
        recomputeLabels(initialW);
      });
    });

    return () => {
      disposed = true;
      graph.destroy();
      graphRef.current = null;
    };
  }, [data, highlightSet]);

  const weekIdxRef = useRef<number>(weekIdx);
  useEffect(() => {
    weekIdxRef.current = weekIdx;
    if (!data || !graphRef.current) return;
    const t0 = performance.now();
    applyWeekToGraph(weekIdx);
    const dt = Math.round((performance.now() - t0) * 100) / 100;
    const list = window.__metrics?.week_switch_ms ?? [];
    list.push(dt);
    window.__metrics = {
      ...window.__metrics,
      week_switch_ms: list,
      n_edges_w: (data.edges_by_week[weekIdx] ?? []).length,
    };
  }, [weekIdx, data, applyWeekToGraph]);

  // Play animation across weeks & record FPS + switch times
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
    const totalWeeks = data.weeks.length;
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

  const currentWeekStr = data?.weeks[weekIdx] ?? week ?? "2026-W42";
  const currentEdgesCount = data?.edges_by_week[weekIdx]?.length ?? 0;
  const topMovers: TemporalMover[] =
    data?._meta?.top_movers_per_week?.[weekIdx] ?? [];

  return (
    <div className="temporal-graph-container" data-testid="temporal-graph">
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
            max={Math.max(0, (data?.weeks.length ?? 1) - 1)}
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
              {data._meta.top_k} NPMI/nodo, medido)
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

      <div className="temporal-split">
        <div className="temporal-canvas-wrap">
          {loading && (
            <div className="graph-loading-overlay">
              Cargando grafo temporal GPU (`temporal.json`)...
            </div>
          )}
          <div
            ref={canvasHostRef}
            className="temporal-canvas-host"
            data-testid="temporal-canvas-host"
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
                title={`${lbl.text} (${lbl.id})`}
              >
                {lbl.text}
              </button>
            ))}
          </div>
          <div className="graph-legend">
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
              <span className="legend-dot legend-grow" /> En ascenso (grado +35%)
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-ctx" /> Contexto IA
            </span>
          </div>
        </div>

        <aside className="temporal-movers-aside" aria-label="Mayores subidas de la semana">
          <div className="movers-header">
            <h4>Subidas de la semana ({currentWeekStr})</h4>
            <span className="muted">Crecimiento de grado vs media 4 sem (medido)</span>
          </div>
          <ul className="movers-list">
            {topMovers.map((m) => (
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
                    {m.label_es}
                  </button>
                  <span className={`decision-badge decision-${m.decision}`}>
                    {DECISION_LABELS_ES[m.decision]}
                  </span>
                </div>
                <div className="mover-meta">
                  <code>{m.id}</code> · grado{" "}
                  <strong>
                    {m.deg_growth >= 0 ? "+" : ""}
                    {(m.deg_growth * 100).toFixed(0)}%
                  </strong>{" "}
                  · PageRank <strong>{m.pagerank_pct.toFixed(0)} pct</strong>
                </div>
              </li>
            ))}
          </ul>
          {metricsSnapshot.firstFrameMs !== undefined && (
            <div className="graph-perf-footer">
              Render GPU (`@cosmos.gl/graph` 3.5.1): 1er cuadro{" "}
              <strong>{metricsSnapshot.firstFrameMs} ms</strong>
              {metricsSnapshot.fpsPlaying !== undefined && (
                <>
                  {" "}
                  · <strong>{metricsSnapshot.fpsPlaying} fps</strong>
                </>
              )}
              {metricsSnapshot.medianSwitchMs !== undefined && (
                <>
                  {" "}
                  · cambio sem <strong>{metricsSnapshot.medianSwitchMs} ms</strong>
                </>
              )}{" "}
              (medido)
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
