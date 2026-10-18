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
    edgeCounts: number[];
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
        const decision: DecisionValue =
          node.decision?.[w] ?? "no_es_tema_caliente";

        const priority =
          (isFocused ? 10000 : 0) +
          (isTop10 ? 5000 - (rk ?? 10) * 100 : 0) +
          (decision === "publicar_ahora" || decision === "preparar" ? 600 : 0) +
          pr * 100000 +
          Math.max(0, dg) * 40;

        candidates.push({
          idx: i,
          id: node.id,
          text: node.label_es || node.label || node.id,
          x: sx,
          y: sy,
          priority,
          decision,
          isFocused,
        });
      }

      candidates.sort((a, b) => b.priority - a.priority);

      // Greedy bounding-box collision avoidance so labels never overlap
      const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
      const accepted: LabelItem[] = [];
      const maxLabels = 24;

      for (const cand of candidates) {
        if (accepted.length >= maxLabels && !cand.isFocused) break;
        const estW = Math.min(185, Math.max(54, cand.text.length * 6.4 + 14));
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
    if (!data || !canvasHostRef.current) return;
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
    const bucketSrc: number[][] = Array.from({ length: nWeeks }, () => []);
    const bucketTgt: number[][] = Array.from({ length: nWeeks }, () => []);
    const bucketNpmi: number[][] = Array.from({ length: nWeeks }, () => []);
    const srcCol = data.edges.source;
    const tgtCol = data.edges.target;
    const wkCol = data.edges.week;
    const npmiCol = data.edges.npmi;
    for (let e = 0; e < srcCol.length; e++) {
      const w = wkCol[e];
      if (w >= 0 && w < nWeeks) {
        bucketSrc[w].push(srcCol[e]);
        bucketTgt[w].push(tgtCol[e]);
        bucketNpmi[w].push(npmiCol[e]);
      }
    }

    const linksPerWeek: Float32Array[] = [];
    const widthsPerWeek: Float32Array[] = [];
    const sizesPerWeek: Float32Array[] = [];
    const colorsPerWeek: Float32Array[] = [];
    const edgeCounts: number[] = [];

    for (let w = 0; w < nWeeks; w++) {
      const m = bucketSrc[w].length;
      edgeCounts.push(m);
      const links = new Float32Array(m * 2);
      const widths = new Float32Array(m);
      for (let e = 0; e < m; e++) {
        links[e * 2] = bucketSrc[w][e];
        links[e * 2 + 1] = bucketTgt[w][e];
        const npmi = bucketNpmi[w][e] ?? 0.2;
        widths[e] = Math.max(0.45, Math.min(2.2, npmi * 2.5));
      }
      linksPerWeek.push(links);
      widthsPerWeek.push(widths);

      const sizes = new Float32Array(nNodes);
      const colors = new Float32Array(nNodes * 4);
      for (let i = 0; i < nNodes; i++) {
        const node = data.nodes[i];
        const isFocused = highlightSet.has(node.id.toLowerCase());
        const pr = node.pagerank?.[w] ?? 0.0002;
        const dg = node.deg_growth?.[w] ?? 0;
        const dec = node.decision?.[w] ?? null;
        const rk = node.rank?.[w] ?? null;
        const isTop10 = rk !== null && rk >= 1 && rk <= 10;

        const prNorm = Math.min(1, Math.sqrt(Math.max(0, pr) / 0.008));
        let sz = 3.2 + prNorm * 9.0;
        if (isTop10) sz = Math.max(sz, 12.0);
        if (isFocused) sz = Math.max(sz, 15.0);
        sizes[i] = sz;

        if (isFocused) {
          colors[i * 4] = 244 / 255;
          colors[i * 4 + 1] = 63 / 255;
          colors[i * 4 + 2] = 94 / 255;
          colors[i * 4 + 3] = 1.0;
        } else if (dec === "publicar_ahora") {
          colors[i * 4] = 34 / 255;
          colors[i * 4 + 1] = 197 / 255;
          colors[i * 4 + 2] = 94 / 255;
          colors[i * 4 + 3] = 0.96;
        } else if (dec === "preparar") {
          colors[i * 4] = 56 / 255;
          colors[i * 4 + 1] = 189 / 255;
          colors[i * 4 + 2] = 248 / 255;
          colors[i * 4 + 3] = 0.95;
        } else if (dec === "esperar") {
          colors[i * 4] = 245 / 255;
          colors[i * 4 + 1] = 158 / 255;
          colors[i * 4 + 2] = 11 / 255;
          colors[i * 4 + 3] = 0.9;
        } else if (dg >= 0.4) {
          colors[i * 4] = 45 / 255;
          colors[i * 4 + 1] = 212 / 255;
          colors[i * 4 + 2] = 191 / 255;
          colors[i * 4 + 3] = 0.82;
        } else {
          colors[i * 4] = 100 / 255;
          colors[i * 4 + 1] = 116 / 255;
          colors[i * 4 + 2] = 139 / 255;
          colors[i * 4 + 3] = 0.55;
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
      edgeCounts,
    };

    const graph = new Graph(host, {
      spaceSize: 4096,
      backgroundColor: "#0f172a",
      pointDefaultSize: 4,
      linkDefaultWidth: 0.65,
      linkDefaultColor: [148 / 255, 163 / 255, 184 / 255, 0.16],
      curvedLinks: false,
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
          n_edges_w: edgeCounts[initialW] ?? 0,
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
      n_edges_w: weekArraysRef.current?.edgeCounts[weekIdx] ?? 0,
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

  const isoWeeks = data?._meta?.iso_weeks ?? data?._meta?.weeks ?? [];
  const currentWeekStr =
    isoWeeks[weekIdx] ?? data?._meta?.weeks?.[weekIdx] ?? week ?? "2026-W42";
  const currentEdgesCount =
    data?._meta?.edges_per_week?.[weekIdx] ??
    weekArraysRef.current?.edgeCounts[weekIdx] ??
    0;
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
              {data._meta.params.top_k_per_node} NPMI/nodo, medido)
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
              <span className="legend-dot legend-grow" /> En ascenso (grado +40%)
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-ctx" /> Contexto IA
            </span>
          </div>
        </div>

        <aside
          className="temporal-movers-aside"
          aria-label="Mayores subidas de la semana"
        >
          <div className="movers-header">
            <h4>Temas destacados ({currentWeekStr})</h4>
            <span className="muted">
              Top priorizados y subidas de grado (medido)
            </span>
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
                      {m.label_es}
                    </button>
                    <span className={`decision-badge decision-${dec}`}>
                      {DECISION_LABELS_ES[dec]}
                    </span>
                  </div>
                  <div className="mover-meta">
                    <code>{m.id}</code>
                    {m.deg_growth != null && (
                      <>
                        {" "}
                        · grado{" "}
                        <strong>
                          {m.deg_growth >= 0 ? "+" : ""}
                          {(m.deg_growth * 100).toFixed(0)}%
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
