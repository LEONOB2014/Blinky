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

const ETYPE_COLORS: Record<string, string> = {
  org: "#2563eb",
  thm: "#059669",
  loc: "#d97706",
};

const EXTRA_THEME_LABELS_ES: Record<string, string> = {
  "thm:WB_1649_UNEMPLOYMENT_BENEFITS": "Subsidios de desempleo",
  "thm:WB_752_CONTRIBUTORY_BENEFITS": "Prestaciones contributivas",
  "thm:UNGP_SUPPORT_FOR_PEOPLE_WHO_CANT_WORK": "Protección laboral y apoyo",
  "thm:NATURAL_DISASTER_DROWN": "Riesgo climático e inundaciones",
  "thm:WB_751_SOCIAL_INSURANCE": "Seguridad social",
  "thm:ECON_BANKRUPTCY": "Reestructuración y quiebras",
  "thm:TAX_FNCACT_ECONOMISTS": "Economistas",
  "thm:WB_2747_UNEMPLOYMENT": "Desempleo (BM)",
  "thm:UNEMPLOYMENT": "Desempleo",
  "thm:UNGP_JOB_OPPORTUNITIES_EMPLOYMENT": "Oportunidades de empleo",
  "thm:TAX_FNCACT_PRINCIPAL": "Directores principales",
  "thm:TAX_FNCACT_CHIEF_FINANCIAL_OFFICER": "Directores financieros (CFO)",
  "thm:TAX_FNCACT_ANALYST": "Analistas de mercado",
  "thm:TAX_FNCACT_ANALYSTS": "Analistas financieros",
  "thm:TAX_FNCACT_INVESTOR": "Inversionistas",
  "thm:TAX_FNCACT_INVESTORS": "Inversores institucionales",
  "thm:TAX_FNCACT_SHAREHOLDERS": "Accionistas",
  "thm:TAX_FNCACT_TRADER": "Operadores bursátiles",
  "thm:TAX_FNCACT_TRADERS": "Operadores de mercado",
  "thm:ECON_STOCKMARKET": "Mercado bursátil",
};

function cleanSpanishLabel(id: string, rawEs?: string | null): string {
  if (EXTRA_THEME_LABELS_ES[id]) return EXTRA_THEME_LABELS_ES[id];
  if (rawEs && rawEs.trim()) return rawEs;
  return id;
}

function resolveStoryEntry(
  index: StoriesIndexData,
  requestedTopic: string | null | undefined,
): {
  entry: StoriesIndexEntry | null;
  exactMatch: boolean;
  requestedClean: string | null;
} {
  const allEntries = Object.values(index.stories ?? {});
  if (allEntries.length === 0) {
    return { entry: null, exactMatch: false, requestedClean: null };
  }
  const defaultTopic = index._meta?.default_topic;
  if (!requestedTopic || !requestedTopic.trim()) {
    const def =
      (defaultTopic ? index.stories?.[defaultTopic] : undefined) ??
      index.top10?.[0] ??
      allEntries[0];
    return { entry: def, exactMatch: true, requestedClean: null };
  }

  const raw = requestedTopic.trim();
  const q = raw.toLowerCase();
  const qNoPrefix = q.includes(":") ? q.slice(q.indexOf(":") + 1).trim() : q;

  // 1. Exact topic_id or file match
  const exact = allEntries.find(
    (s) =>
      s.topic_id.toLowerCase() === q ||
      s.topic_id.toLowerCase() === `org:${qNoPrefix}` ||
      s.topic_id.toLowerCase() === `thm:${qNoPrefix}` ||
      s.file.toLowerCase() === `story_${q.replace(/[^a-z0-9]+/g, "_")}.json`,
  );
  if (exact) {
    return { entry: exact, exactMatch: true, requestedClean: raw };
  }

  // 2. Partial match on topic_id or Spanish label
  const partial = allEntries.find(
    (s) =>
      s.topic_id.toLowerCase().includes(qNoPrefix) ||
      s.label_es.toLowerCase().includes(qNoPrefix),
  );
  if (partial) {
    return { entry: partial, exactMatch: true, requestedClean: raw };
  }

  // 3. Fallback to default (#1 ranked topic)
  const fallback =
    (defaultTopic ? index.stories?.[defaultTopic] : undefined) ??
    index.top10?.[0] ??
    allEntries[0];
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
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
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
    setSelectedTopicId(entry.topic_id);
    const wkLabel = indexData._meta?.week ?? "2026-W42";
    if (!exactMatch && requestedClean) {
      setUnmatchedTopicNotice(
        `El tema "${requestedClean}" no está entre las 10 historias priorizadas de ${wkLabel}. Mostrando #1 (${entry.label_es} · ${entry.topic_id}).`,
      );
    } else if (!entry.in_top10) {
      const rankInfo =
        entry.rank != null ? `puesto #${entry.rank}` : "sin rango Top-10";
      setUnmatchedTopicNotice(
        `Nota: "${entry.label_es}" (${entry.topic_id}) no está en las 10 historias priorizadas de ${wkLabel} (${rankInfo}, decisión: ${entry.decision ?? "referencia"}); abajo se muestra su anillo real de 1 salto medido en GDELT.`,
      );
    } else {
      setUnmatchedTopicNotice(null);
    }
  }, [indexData, focusTopic]);

  // Fetch the selected `story_<slug>.json`
  useEffect(() => {
    if (!indexData || !selectedTopicId) return;
    const entry = indexData.stories?.[selectedTopicId];
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
  }, [indexData, selectedTopicId]);

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
    const centerEntry = storyData.nodes.find(
      (n) => n.attributes.role === "topic",
    );
    const neighbors = storyData.nodes
      .filter((n) => n.attributes.role !== "topic")
      .sort((a, b) => (a.attributes.rank ?? 99) - (b.attributes.rank ?? 99));

    const maxNeighborN = Math.max(
      1,
      ...neighbors.map((n) => n.attributes.n ?? 1),
    );
    const maxSpokeN = Math.max(
      1,
      ...storyData.edges
        .filter((e) => e.attributes.kind === "ring")
        .map((e) => e.attributes.n ?? 1),
    );

    const centerId = storyData._meta.topic_id || centerEntry?.key || "";
    const centerLabelEs = cleanSpanishLabel(
      centerId,
      storyData._meta.label_es || centerEntry?.attributes.label_es,
    );

    g.addNode(centerId, {
      x: 0,
      y: 0,
      size: 22,
      color: "#e11d48",
      label: `★ ${centerLabelEs}`,
    });

    // Two staggered concentric rings (10 inner + 10 outer) so Spanish labels stay well separated
    const innerCount = Math.min(10, neighbors.length);
    const outerCount = Math.max(0, neighbors.length - innerCount);

    neighbors.forEach((n, idx) => {
      const attr = n.attributes;
      const rk = attr.rank ?? idx + 1;
      const isInner = idx < innerCount;
      const ringIdx = isInner ? idx : idx - innerCount;
      const ringTotal = isInner ? innerCount : Math.max(1, outerCount);
      const radius = isInner ? 1.05 : 1.78;
      const angleOffset = isInner
        ? -Math.PI / 2
        : -Math.PI / 2 + Math.PI / ringTotal;
      const angle = angleOffset + (2 * Math.PI * ringIdx) / ringTotal;

      const ratio = Math.sqrt((attr.n ?? 1) / maxNeighborN);
      // Inner top-12 nodes get size >= 11.2 so their labels always render; outer 13..20 show label on hover
      const nodeSize =
        rk <= 12 ? 11.4 + ratio * 6.5 : 7.5 + ratio * 3.0;
      const isHighlighted = highlightSet.has(n.key.toLowerCase());
      const nodeColor = isHighlighted
        ? "#e11d48"
        : ETYPE_COLORS[attr.etype] ?? "#2563eb";

      const lblEs = cleanSpanishLabel(n.key, attr.label_es || attr.label);
      const displayLabel = `#${rk} ${lblEs}`;
      g.addNode(n.key, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        size: nodeSize,
        color: nodeColor,
        label: displayLabel,
      });
    });

    // Add all 20 spoke edges (center -> neighbor) and only the top 10 strongest intra-ring chords
    const spokeEdges = storyData.edges.filter(
      (e) => e.attributes.kind === "ring",
    );
    const topAmongEdges = storyData.edges
      .filter((e) => e.attributes.kind === "among")
      .sort((a, b) => (b.attributes.npmi ?? 0) - (a.attributes.npmi ?? 0))
      .slice(0, 10);

    for (const e of [...spokeEdges, ...topAmongEdges]) {
      if (!g.hasNode(e.source) || !g.hasNode(e.target)) continue;
      if (g.hasEdge(e.source, e.target) || g.hasEdge(e.target, e.source)) {
        continue;
      }
      const isSpoke = e.attributes.kind === "ring";
      const width = isSpoke
        ? 1.8 + Math.sqrt((e.attributes.n ?? 1) / maxSpokeN) * 5.2
        : 0.65;
      g.addEdgeWithKey(e.key, e.source, e.target, {
        size: width,
        color: isSpoke ? "#94a3b8" : "#f1f5f9",
      });
    }

    const renderer = new Sigma(g, container, {
      renderLabels: true,
      labelRenderedSizeThreshold: 11.0,
      labelSize: 12,
      labelWeight: "600",
      labelColor: { color: "#0f172a" },
      defaultEdgeType: "line",
      stagePadding: 42,
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
      story_center: centerId,
      story_n_nodes: storyData.nodes.length,
    };

    return () => {
      renderer.kill();
      sigmaRef.current = null;
    };
  }, [storyData, highlightSet]);

  const top10Stories = useMemo(() => indexData?.top10 ?? [], [indexData]);
  const referenceStories = useMemo(
    () =>
      Object.values(indexData?.stories ?? {}).filter((s) => !s.in_top10),
    [indexData],
  );

  const scores = storyData?.attributes?.scores ?? null;
  const neighborsList = useMemo(
    () =>
      (storyData?.nodes ?? [])
        .filter((n) => n.attributes.role !== "topic")
        .sort((a, b) => (a.attributes.rank ?? 99) - (b.attributes.rank ?? 99)),
    [storyData],
  );
  const wkLabel = indexData?._meta?.week ?? "2026-W42";

  return (
    <div className="story-graph-container" data-testid="story-graph">
      <div className="story-selector-bar">
        <div className="story-selector-group">
          <span className="story-selector-title">Top 10 ({wkLabel}):</span>
          {top10Stories.map((s) => (
            <button
              key={s.topic_id}
              type="button"
              className={
                selectedTopicId === s.topic_id ? "pill pill-active" : "pill"
              }
              data-testid={`story-pill-${s.topic_id}`}
              onClick={() => {
                setSelectedTopicId(s.topic_id);
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
            <span className="story-selector-title">
              Referencia (fuera del Top 10):
            </span>
            {referenceStories.map((s) => (
              <button
                key={s.topic_id}
                type="button"
                className={
                  selectedTopicId === s.topic_id ? "pill pill-active" : "pill"
                }
                data-testid={`story-pill-${s.topic_id}`}
                onClick={() => {
                  setSelectedTopicId(s.topic_id);
                  const rankInfo =
                    s.rank != null ? `puesto #${s.rank}` : "sin rango Top-10";
                  setUnmatchedTopicNotice(
                    `Nota: "${s.label_es}" (${s.topic_id}) no está en las 10 historias priorizadas de ${wkLabel} (${rankInfo}); viendo su anillo real de 1 salto medido.`,
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
            {scores?.rank != null && scores.rank <= 10
              ? `#${scores.rank} Top-10`
              : scores?.rank != null
                ? `#${scores.rank} (fuera Top-10)`
                : "Referencia"}
          </span>
          <strong className="story-center-title">
            {storyData._meta.label_es ?? storyData._meta.topic_id}{" "}
            <code className="topic-id">{storyData._meta.topic_id}</code>
          </strong>
          {scores?.decision && (
            <span className={`decision-badge decision-${scores.decision}`}>
              {DECISION_LABELS_ES[scores.decision]}
            </span>
          )}
          {scores?.stage && <span className="chip">Etapa: {scores.stage}</span>}
          {scores?.emergence_pct != null && (
            <span className="chip">
              Emergencia:{" "}
              <strong>{scores.emergence_pct.toFixed(1)} pct</strong> (medido)
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
              <strong>{(scores.audience_fit * 100).toFixed(0)}%</strong>{" "}
              (medido)
            </span>
          )}
          {scores?.emotional_charge_pct != null && (
            <span className="chip">
              Carga emocional:{" "}
              <strong>{scores.emotional_charge_pct.toFixed(0)} pct</strong>{" "}
              (medido)
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
              Organización (`org:`)
            </span>
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#059669" }}
              />{" "}
              Tema GDELT (`thm:`)
            </span>
            <span className="legend-item">
              <span
                className="legend-dot"
                style={{ backgroundColor: "#d97706" }}
              />{" "}
              País / región (`loc:`)
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
              Anillo 1-salto ({neighborsList.length} vecinos · {wkLabel})
            </h4>
            <span className="muted">
              Ordenado por rango de NPMI · clic para explorar
            </span>
          </div>
          <ul className="movers-list">
            {neighborsList.slice(0, 12).map((nb) => {
              const attr = nb.attributes;
              return (
                <li key={nb.key} className="mover-item">
                  <div className="mover-top">
                    <button
                      type="button"
                      className="mover-link"
                      onClick={() => onSelectTopic?.(nb.key)}
                    >
                      #{attr.rank}{" "}
                      {cleanSpanishLabel(nb.key, attr.label_es || attr.label)}
                    </button>
                    <span className="chip">{attr.etype}</span>
                  </div>
                  <div className="mover-meta">
                    <code>{nb.key}</code> · n=<strong>{attr.n ?? 0}</strong> ·
                    NPMI <strong>{(attr.npmi ?? 0).toFixed(3)}</strong> (medido)
                  </div>
                </li>
              );
            })}
          </ul>
        </aside>
      </div>
    </div>
  );
}
