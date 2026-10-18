import Graph from "graphology";
import Sigma from "sigma";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DecisionValue } from "../types/contracts";
import type {
  StoriesIndexData,
  StoriesIndexEntry,
  StoryGraphData,
} from "../types/views";

interface StoryGraphProps {
  focusTopic?: string | null;
  highlight?: string[];
  onSelectTopic?: (topicId: string) => void;
}

const DECISION_LABELS_ES: Record<DecisionValue, string> = {
  publicar_ahora: "Publicar ahora",
  preparar: "Preparar",
  esperar: "Esperar",
  no_es_tema_caliente: "No es tema caliente",
};

const SEGMENT_COLORS: Record<string, string> = {
  ai: "#2563eb",
  ai_domain: "#059669",
  it: "#d97706",
};

function resolveStoryEntry(
  index: StoriesIndexData,
  requestedTopic: string | null | undefined,
): {
  entry: StoriesIndexEntry | null;
  exactMatch: boolean;
  requestedClean: string | null;
} {
  const stories = index.stories ?? [];
  if (stories.length === 0) {
    return { entry: null, exactMatch: false, requestedClean: null };
  }
  if (!requestedTopic || !requestedTopic.trim()) {
    const def =
      stories.find((s) => s.topic_id === index.default_topic_id) ?? stories[0];
    return { entry: def, exactMatch: true, requestedClean: null };
  }

  const raw = requestedTopic.trim();
  const q = raw.toLowerCase();
  const qNoPrefix = q.includes(":") ? q.slice(q.indexOf(":") + 1).trim() : q;

  // 1. Exact topic_id or slug match
  const exact = stories.find(
    (s) =>
      s.topic_id.toLowerCase() === q ||
      s.topic_id.toLowerCase() === `org:${qNoPrefix}` ||
      s.topic_id.toLowerCase() === `thm:${qNoPrefix}` ||
      s.slug.toLowerCase() === q.replace(/[^a-z0-9]+/g, "_"),
  );
  if (exact) {
    return { entry: exact, exactMatch: true, requestedClean: raw };
  }

  // 2. Partial match on topic_id or Spanish label
  const partial = stories.find(
    (s) =>
      s.topic_id.toLowerCase().includes(qNoPrefix) ||
      s.label_es.toLowerCase().includes(qNoPrefix),
  );
  if (partial) {
    return { entry: partial, exactMatch: true, requestedClean: raw };
  }

  // 3. Fallback to default (#1 ranked topic)
  const fallback =
    stories.find((s) => s.topic_id === index.default_topic_id) ?? stories[0];
  return { entry: fallback, exactMatch: false, requestedClean: raw };
}

export function StoryGraph({
  focusTopic,
  highlight = [],
  onSelectTopic,
}: StoryGraphProps) {
  const sigmaContainerRef = useRef<HTMLDivElement | null>(null);
  const sigmaRef = useRef<Sigma | null>(null);

  const [indexData, setIndexData] = useState<StoriesIndexData | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [unmatchedTopicNotice, setUnmatchedTopicNotice] = useState<
    string | null
  >(null);
  const [storyData, setStoryData] = useState<StoryGraphData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const highlightSet = useMemo(
    () => new Set(highlight.map((h) => h.toLowerCase())),
    [highlight],
  );

  // Load stories_index.json once
  useEffect(() => {
    let cancelled = false;
    fetch("/data/views/stories_index.json")
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(
            `HTTP ${res.status} al cargar /data/views/stories_index.json`,
          );
        }
        const parsed = (await res.json()) as StoriesIndexData;
        if (cancelled) return;
        setIndexData(parsed);
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

  // Resolve `focusTopic` whenever `indexData` or `focusTopic` changes
  useEffect(() => {
    if (!indexData) return;
    const { entry, exactMatch, requestedClean } = resolveStoryEntry(
      indexData,
      focusTopic,
    );
    if (!entry) return;
    setSelectedSlug(entry.slug);
    if (!exactMatch && requestedClean) {
      setUnmatchedTopicNotice(
        `El tema "${requestedClean}" no está entre las 10 historias priorizadas de ${indexData.wk}. Mostrando #1 (${entry.label_es} · ${entry.topic_id}).`,
      );
    } else if (entry.in_top10 === false || entry.rank == null) {
      setUnmatchedTopicNotice(
        `Nota: "${entry.label_es}" (${entry.topic_id}) no figura en el Top 10 priorizado de ${indexData.wk} (tema maduro/referencia); abajo se muestra su anillo real de 1 salto medido en GDELT.`,
      );
    } else {
      setUnmatchedTopicNotice(null);
    }
  }, [indexData, focusTopic]);

  // Fetch the selected `story_<slug>.json`
  useEffect(() => {
    if (!indexData || !selectedSlug) return;
    const entry = indexData.stories.find((s) => s.slug === selectedSlug);
    const fileUrl = `/data/views/${entry?.file ?? "story.json"}`;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(fileUrl)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status} al cargar ${fileUrl}`);
        }
        const parsed = (await res.json()) as StoryGraphData;
        if (cancelled) return;
        setStoryData(parsed);
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
  }, [indexData, selectedSlug]);

  // Instantiate Sigma 3.0.3 when `storyData` changes
  useEffect(() => {
    if (!storyData || !sigmaContainerRef.current) return;
    const container = sigmaContainerRef.current;
    const t0 = performance.now();

    if (sigmaRef.current) {
      sigmaRef.current.kill();
      sigmaRef.current = null;
    }

    const g = new Graph();
    const neighbors = storyData.nodes
      .filter((n) => n.role !== "center")
      .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

    const maxNeighborN = Math.max(
      1,
      ...neighbors.map((n) => n.n ?? 1),
    );
    const maxEdgeN = Math.max(
      1,
      ...storyData.edges.map((e) => e.n ?? 1),
    );

    const centerNode = storyData.nodes.find((n) => n.role === "center");
    const centerId = storyData.center;
    const centerLabelEs =
      storyData.center_label_es ||
      centerNode?.label_es ||
      storyData.center_scores?.label_es ||
      centerId;

    g.addNode(centerId, {
      x: 0,
      y: 0,
      size: 22,
      color: "#e11d48",
      label: `★ ${centerLabelEs}`,
    });

    // Two concentric rings by rank so 20 Spanish labels never overlap
    const innerCount = Math.min(8, neighbors.length);
    const outerCount = Math.max(0, neighbors.length - innerCount);

    neighbors.forEach((n, idx) => {
      const isInner = idx < innerCount;
      const ringIdx = isInner ? idx : idx - innerCount;
      const ringTotal = isInner ? innerCount : Math.max(1, outerCount);
      const radius = isInner ? 1.0 : 1.72;
      const angleOffset = isInner ? -Math.PI / 2 : -Math.PI / 2 + Math.PI / ringTotal;
      const angle = angleOffset + (2 * Math.PI * ringIdx) / ringTotal;

      const ratio = Math.sqrt((n.n ?? 1) / maxNeighborN);
      const nodeSize = 8.5 + ratio * 9.5;
      const isHighlighted = highlightSet.has(n.id.toLowerCase());
      const segColor = isHighlighted
        ? "#e11d48"
        : SEGMENT_COLORS[n.segment ?? "ai"] ?? "#475569";

      const displayLabel = `#${n.rank} ${n.label_es || n.label}`;
      g.addNode(n.id, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        size: nodeSize,
        color: segColor,
        label: displayLabel,
      });
    });

    storyData.edges.forEach((e, idx) => {
      if (!g.hasNode(e.source) || !g.hasNode(e.target)) return;
      if (g.hasEdge(e.source, e.target) || g.hasEdge(e.target, e.source)) return;
      const isSpoke = e.source === centerId || e.target === centerId;
      const width = isSpoke
        ? 1.6 + Math.sqrt((e.n ?? 1) / maxEdgeN) * 5.4
        : 0.7 + Math.sqrt((e.n ?? 1) / maxEdgeN) * 1.8;
      g.addEdgeWithKey(`e_${idx}`, e.source, e.target, {
        size: width,
        color: isSpoke ? "#64748b" : "#cbd5e1",
      });
    });

    const renderer = new Sigma(g, container, {
      renderLabels: true,
      labelRenderedSizeThreshold: 0,
      labelSize: 12,
      labelWeight: "600",
      labelColor: { color: "#0f172a" },
      defaultEdgeType: "line",
      stagePadding: 38,
      zIndex: true,
    });

    renderer.on("clickNode", ({ node }) => {
      onSelectTopic?.(node);
    });

    sigmaRef.current = renderer;
    const elapsed = Math.round((performance.now() - t0) * 10) / 10;
    window.__metrics = {
      ...window.__metrics,
      story_rendered_ms: elapsed,
      story_center: storyData.center,
      story_n_nodes: storyData.nodes.length,
    };

    return () => {
      renderer.kill();
      sigmaRef.current = null;
    };
  }, [storyData, highlightSet]);

  const top10Stories = useMemo(
    () => (indexData?.stories ?? []).filter((s) => s.in_top10 !== false && s.rank != null),
    [indexData],
  );
  const referenceStories = useMemo(
    () => (indexData?.stories ?? []).filter((s) => s.in_top10 === false || s.rank == null),
    [indexData],
  );

  const scores = storyData?.center_scores;
  const neighborsList = useMemo(
    () =>
      (storyData?.nodes ?? [])
        .filter((n) => n.role !== "center")
        .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)),
    [storyData],
  );

  return (
    <div className="story-graph-container" data-testid="story-graph">
      <div className="story-selector-bar">
        <div className="story-selector-group">
          <span className="story-selector-title">Top 10 ({indexData?.wk ?? "2026-W42"}):</span>
          {top10Stories.map((s) => (
            <button
              key={s.slug}
              type="button"
              className={
                selectedSlug === s.slug ? "pill pill-active" : "pill"
              }
              data-testid={`story-pill-${s.slug}`}
              onClick={() => {
                setSelectedSlug(s.slug);
                setUnmatchedTopicNotice(null);
                onSelectTopic?.(s.topic_id);
              }}
            >
              #{s.rank} {s.label_es}
            </button>
          ))}
        </div>
        {referenceStories.length > 0 && (
          <div className="story-selector-group">
            <span className="story-selector-title">Referencia (fuera del Top 10):</span>
            {referenceStories.map((s) => (
              <button
                key={s.slug}
                type="button"
                className={
                  selectedSlug === s.slug ? "pill pill-active" : "pill"
                }
                data-testid={`story-pill-${s.slug}`}
                onClick={() => {
                  setSelectedSlug(s.slug);
                  setUnmatchedTopicNotice(
                    `Nota: "${s.label_es}" (${s.topic_id}) no está en el Top 10 priorizado de ${indexData?.wk ?? "2026-W42"}; viendo su anillo de 1 salto medido.`,
                  );
                  onSelectTopic?.(s.topic_id);
                }}
              >
                {s.label_es}
              </button>
            ))}
          </div>
        )}
      </div>

      {unmatchedTopicNotice && (
        <div
          className="story-notice-banner"
          role="status"
          data-testid="story-notice-banner"
        >
          {unmatchedTopicNotice}
        </div>
      )}

      {error && (
        <div className="error-box" role="alert">
          Error al cargar la vista de historia: {error}
        </div>
      )}

      {/* Scores row beside/above the story canvas */}
      {storyData && (
        <div className="story-scores-row" data-testid="story-scores-row">
          <span className="rank-badge">
            {scores?.rank != null ? `#${scores.rank} Top-10` : "Referencia"}
          </span>
          <strong className="story-center-title">
            {storyData.center_label_es ?? storyData.center}{" "}
            <code className="topic-id">{storyData.center}</code>
          </strong>
          {scores?.decision && (
            <span className={`decision-badge decision-${scores.decision}`}>
              {DECISION_LABELS_ES[scores.decision]}
            </span>
          )}
          {scores?.stage && <span className="chip">Etapa: {scores.stage}</span>}
          {scores?.emergence_pct != null && (
            <span className="chip">
              Emergencia: <strong>{scores.emergence_pct.toFixed(1)} pct</strong> (medido)
            </span>
          )}
          {scores?.saturation != null && (
            <span className="chip">
              Saturación:{" "}
              <strong>{(scores.saturation * 100).toFixed(1)}%</strong> (medido)
            </span>
          )}
          {scores?.audience_fit != null && (
            <span className="chip">
              Encaje LatAm:{" "}
              <strong>{(scores.audience_fit * 100).toFixed(0)}%</strong> (medido)
            </span>
          )}
          {scores?.emotional_charge_pct != null && (
            <span className="chip">
              Carga emocional:{" "}
              <strong>{scores.emotional_charge_pct.toFixed(0)} pct</strong> (medido)
            </span>
          )}
          {scores?.framing_angle && (
            <span className="chip">Ángulo: {scores.framing_angle}</span>
          )}
        </div>
      )}

      <div className="story-split">
        <div className="story-canvas-wrap">
          {loading && (
            <div className="graph-loading-overlay">
              Cargando anillo de 1 salto (`sigma` 3.0.3)...
            </div>
          )}
          <div
            ref={sigmaContainerRef}
            className="story-sigma-host"
            data-testid="story-sigma-host"
          />
          <div className="graph-legend graph-legend-light">
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#e11d48" }}
              />{" "}
              Tema central
            </span>
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#2563eb" }}
              />{" "}
              Núcleo IA (`ai`)
            </span>
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#059669" }}
              />{" "}
              Dominio IA (`ai_domain`)
            </span>
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#d97706" }}
              />{" "}
              TI general (`it`)
            </span>
            <span className="legend-item muted">
              Grosor de arista = co-menciones n (medido)
            </span>
          </div>
        </div>

        <aside
          className="story-neighbors-aside"
          aria-label="Vecinos de 1 salto por rango"
        >
          <div className="movers-header">
            <h4>
              Anillo 1-salto ({neighborsList.length} vecinos · {storyData?.wk ?? "2026-W42"})
            </h4>
            <span className="muted">
              Ordenado por rango de NPMI · clic para explorar
            </span>
          </div>
          <ul className="movers-list">
            {neighborsList.slice(0, 12).map((nb) => (
              <li key={nb.id} className="mover-item">
                <div className="mover-top">
                  <button
                    type="button"
                    className="mover-link"
                    onClick={() => onSelectTopic?.(nb.id)}
                  >
                    #{nb.rank} {nb.label_es || nb.label}
                  </button>
                  <span className="chip">{nb.segment ?? "ai"}</span>
                </div>
                <div className="mover-meta">
                  <code>{nb.id}</code> · n=<strong>{nb.n ?? 0}</strong> · NPMI{" "}
                  <strong>{(nb.npmi ?? 0).toFixed(3)}</strong> (medido)
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
