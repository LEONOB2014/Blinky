import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchFreshness,
  fetchRadar,
  fetchTopicContext,
  fetchTopicTimeline,
  sendChatTurn,
} from "./api";
import { StoryGraph } from "./components/StoryGraph";
import { TemporalGraph } from "./components/TemporalGraph";
import type {
  AgentTraceStep,
  DecisionCard,
  DecisionValue,
  FreshnessResponse,
  LangBucket,
  TopicContext1Hop,
  TopicDaily,
  TopicScoreWeekly,
  TopicWindow,
  ViewCommand,
  ViewMode,
} from "./types/contracts";

const SUBTOPICS: Array<{ id: string; label_es: string }> = [
  { id: "regulation_policy", label_es: "Regulación y política" },
  { id: "agents", label_es: "Agentes de IA" },
  { id: "llms_models", label_es: "Modelos y LLMs" },
  { id: "chips_infra", label_es: "Chips e infraestructura" },
  { id: "business_adoption", label_es: "Adopción empresarial" },
  { id: "jobs_work", label_es: "Empleo y trabajo" },
  { id: "education", label_es: "Educación" },
  { id: "safety_risk", label_es: "Seguridad y riesgos" },
  { id: "creative_media", label_es: "Creatividad y medios" },
  { id: "health_science", label_es: "Salud y ciencia" },
  { id: "funding_markets", label_es: "Inversión y mercados" },
  { id: "ai_all", label_es: "IA en general" },
];

const SUBTOPIC_LABELS: Record<string, string> = Object.fromEntries(
  SUBTOPICS.map((st) => [st.id, st.label_es]),
);

// Real topic ids on the full lake (GDELT names: "org:openai group", not "org:openai").
const CONTEXT_ENTITIES = [
  "org:nvidia",
  "org:microsoft",
  "org:google",
  "org:openai group",
  "thm:TECH_AUTOMATION",
];

/** Card title: the taxonomy label for subtopics, the name for org:/thm: topics. */
function topicName(topicId: string, labelEs?: string | null): string {
  if (SUBTOPIC_LABELS[topicId]) return SUBTOPIC_LABELS[topicId];
  if (labelEs && labelEs !== topicId) return labelEs;
  const idx = topicId.indexOf(":");
  return idx >= 0 ? topicId.slice(idx + 1) : topicId;
}

/** Options for a topic selector: the fixed list plus the selected topic when it is not in it. */
function withSelected(ids: string[], selected: string): string[] {
  return ids.includes(selected) ? ids : [selected, ...ids];
}

const QUICK_QUESTIONS = [
  "Muéstrame el grafo de la semana",
  "¿Qué está pasando con Nvidia? Muéstramelo en el grafo",
  "¿Qué tema de IA sube esta semana y por qué? Muéstramelo en el grafo",
  "¿Cuál es el ángulo para ejecutivos de LatAm esta semana?",
  "¿Qué tan frescos están los datos y cuánto ha costado en BigQuery?",
];

const KNOWN_CHAT_TOPICS: Array<{ pattern: RegExp; topic_id: string }> = [
  { pattern: /\bnvidia\b/i, topic_id: "org:nvidia" },
  { pattern: /\bmicrosoft\b/i, topic_id: "org:microsoft" },
  { pattern: /\bgoogle\b/i, topic_id: "org:google" },
  { pattern: /\bopenai\b/i, topic_id: "org:openai group" },
  { pattern: /\bmarsh\s*mclennan\b/i, topic_id: "org:marsh mclennan" },
  { pattern: /\bbroadcom\b/i, topic_id: "org:broadcom" },
  { pattern: /\boracle\b/i, topic_id: "org:oracle" },
  { pattern: /\btsmc\b|\btaiwan semiconductor\b/i, topic_id: "org:taiwan semiconductor manufacturing" },
  { pattern: /\bautomatizaci[oó]n\b|\btech_automation\b/i, topic_id: "thm:TECH_AUTOMATION" },
];

function resolveChatViewCommand(
  message: string,
  commands: ViewCommand[],
  defaultWeek?: string,
): ViewCommand | null {
  const matchedTopic = KNOWN_CHAT_TOPICS.find((k) => k.pattern.test(message))?.topic_id ?? null;
  const asksWeeklyTemporal =
    /\bgrafo\s+(?:de\s+la\s+semana|temporal|semanal)\b/i.test(message) && !matchedTopic;
  const asksGraph = /\bgrafo\b|\bmapa\b|\bvisualiza/i.test(message);

  if (commands.length > 0) {
    const last = { ...commands[commands.length - 1] };
    if (asksWeeklyTemporal) {
      last.view = "temporal";
    } else if (matchedTopic && last.view === "story" && !last.focus_topic) {
      last.focus_topic = matchedTopic;
    } else if (matchedTopic && asksGraph) {
      last.view = "story";
      last.focus_topic = last.focus_topic || matchedTopic;
    }
    return last;
  }

  if (asksWeeklyTemporal) {
    return {
      view: "temporal",
      week: defaultWeek ?? null,
      focus_topic: null,
      highlight: [],
      color_by: "tone",
      caption_es: "Grafo temporal de co-menciones de la semana (cosmos.gl GPU)",
    };
  }
  if (asksGraph && matchedTopic) {
    return {
      view: "story",
      week: defaultWeek ?? null,
      focus_topic: matchedTopic,
      highlight: [matchedTopic],
      color_by: "tone",
      caption_es: `Historia de 1 salto para ${matchedTopic}`,
    };
  }
  if (asksGraph) {
    return {
      view: "temporal",
      week: defaultWeek ?? null,
      focus_topic: null,
      highlight: [],
      color_by: "tone",
      caption_es: "Grafo temporal de la semana",
    };
  }
  return null;
}

const LANG_COLORS: Record<LangBucket, string> = {
  eng: "#2563eb",
  spa: "#dc2626",
  por: "#059669",
  other: "#7c3aed",
};

const DECISION_LABELS: Record<DecisionValue, string> = {
  publicar_ahora: "Publicar ahora",
  preparar: "Preparar",
  esperar: "Esperar",
  no_es_tema_caliente: "No es tema caliente",
};

function formatWindow(w: TopicWindow): string {
  switch (w.state) {
    case "dias_restantes":
      return `~${w.days_left ?? "?"} días restantes (estimado, n=${w.n_onsets})`;
    case "en_cualquier_momento":
      return `En cualquier momento (estimado, n=${w.n_onsets})`;
    case "ya_en_espanol":
      return `Ya en español (medido, n=${w.n_onsets})`;
    case "sin_estimacion":
    default:
      return `Sin estimación (n=${w.n_onsets})`;
  }
}

function getInitialViewFromUrl(): ViewCommand {
  if (typeof window === "undefined") {
    return {
      view: "cards",
      week: null,
      focus_topic: null,
      highlight: [],
      color_by: "tone",
      caption_es: "Vista inicial de tarjetas (esperando comando del Cartógrafo)",
    };
  }
  const params = new URLSearchParams(window.location.search);
  const v = params.get("view") as ViewMode | null;
  const topic = params.get("topic");
  const wk = params.get("week");
  if (v === "temporal" || v === "story") {
    return {
      view: v,
      week: wk,
      focus_topic: topic,
      highlight: topic ? [topic] : [],
      color_by: "tone",
      caption_es:
        v === "temporal"
          ? "Grafo temporal semanal (13 semanas · cosmos.gl GPU)"
          : `Anillo de historia de 1 salto (${topic ?? "Top #1"})`,
    };
  }
  return {
    view: "cards",
    week: null,
    focus_topic: null,
    highlight: [],
    color_by: "tone",
    caption_es: "Vista inicial de tarjetas (esperando comando del Cartógrafo)",
  };
}

export function App() {
  const [freshness, setFreshness] = useState<FreshnessResponse | null>(null);
  const [radarItems, setRadarItems] = useState<TopicScoreWeekly[]>([]);
  const [radarEmptyReason, setRadarEmptyReason] = useState<string | null>(null);
  // ISO week ("2026-W42") of the radar; empty until freshness gives the latest scored week.
  const [radarWeek, setRadarWeek] = useState<string>("");
  const [selectedTopic, setSelectedTopic] = useState<string>("regulation_policy");
  const [timeline, setTimeline] = useState<TopicDaily[]>([]);
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);
  const [selectedEntity, setSelectedEntity] = useState<string>(CONTEXT_ENTITIES[0]);
  const [contextRing, setContextRing] = useState<TopicContext1Hop[]>([]);

  const [chatInput, setChatInput] = useState<string>(QUICK_QUESTIONS[0]);
  const [conversationId, setConversationId] = useState<string | undefined>(
    undefined,
  );
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [chatCards, setChatCards] = useState<DecisionCard[]>([]);
  const [traceSteps, setTraceSteps] = useState<AgentTraceStep[]>([]);
  const [activeView, setActiveView] = useState<ViewCommand>(getInitialViewFromUrl);
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Split View & Fullscreen state (Addendum 2 Must #2)
  const [splitPct, setSplitPct] = useState<number>(35);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isCardsDrawerOpen, setIsCardsDrawerOpen] = useState<boolean>(false);
  const [isFloatingChatOpen, setIsFloatingChatOpen] = useState<boolean>(true);
  const splitContainerRef = useRef<HTMLDivElement | null>(null);

  // Keyboard shortcut listener: F/f for fullscreen toggle, Esc for exit
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const isInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (e.key === "Escape") {
        setIsFullscreen(false);
        setIsCardsDrawerOpen(false);
      } else if (
        (e.key === "f" || e.key === "F") &&
        !isInput &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey
      ) {
        e.preventDefault();
        setIsFullscreen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Dragging handlers for divider
  const handleDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDividerTouchStart = useCallback(() => {
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;
    function handleMove(clientX: number) {
      if (!splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const rawPct = ((clientX - rect.left) / rect.width) * 100;
      const clamped = Math.min(60, Math.max(20, rawPct));
      setSplitPct(clamped);
    }
    function onMouseMove(e: MouseEvent) {
      handleMove(e.clientX);
    }
    function onTouchMove(e: TouchEvent) {
      if (e.touches.length > 0) handleMove(e.touches[0].clientX);
    }
    function onEnd() {
      setIsDragging(false);
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onEnd);
    window.addEventListener("touchmove", onTouchMove);
    window.addEventListener("touchend", onEnd);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onEnd);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onEnd);
    };
  }, [isDragging]);

  useEffect(() => {
    void fetchFreshness()
      .then((f) => {
        setFreshness(f);
        // Default week: the latest scored week (falls back to the API's own default).
        setRadarWeek(f.tables.topic_scores_weekly ?? "latest");
      })
      .catch((err: unknown) => {
        console.error(err);
        setRadarWeek("latest");
      });
  }, []);

  useEffect(() => {
    if (!radarWeek) return;
    void fetchRadar(radarWeek === "latest" ? undefined : radarWeek)
      .then((res) => {
        setRadarItems(res.items);
        setRadarEmptyReason(res.emptyReason);
        if (res.items.length > 0) {
          selectTopic(res.items[0].topic_id);
        }
      })
      .catch((err: unknown) => {
        console.error(err);
        setRadarItems([]);
      });
  }, [radarWeek]);

  function selectTopic(topicId: string) {
    setSelectedTopic(topicId);
    // Subtopics have no 1-hop ring; org:/thm: topics do.
    if (topicId.includes(":")) setSelectedEntity(topicId);
  }

  const contextWeek = radarWeek && radarWeek !== "latest" ? radarWeek : undefined;

  useEffect(() => {
    setTimelineLoading(true);
    void fetchTopicTimeline(selectedTopic)
      .then((rows) => {
        setTimeline(rows);
      })
      .catch((err: unknown) => {
        console.error(err);
        setTimeline([]);
      })
      .finally(() => {
        setTimelineLoading(false);
      });
  }, [selectedTopic]);

  useEffect(() => {
    void fetchTopicContext(selectedEntity, contextWeek)
      .then(setContextRing)
      .catch((err: unknown) => {
        console.error(err);
        setContextRing([]);
      });
  }, [selectedEntity, contextWeek]);

  const timelineByDate = useMemo(() => {
    const dates = Array.from(new Set(timeline.map((r) => r.dt))).sort();
    const byLang: Record<LangBucket, Map<string, TopicDaily>> = {
      eng: new Map(),
      spa: new Map(),
      por: new Map(),
      other: new Map(),
    };
    for (const row of timeline) {
      byLang[row.lang_bucket]?.set(row.dt, row);
    }
    return { dates, byLang };
  }, [timeline]);

  const langTotals = useMemo(() => {
    const summary: Record<
      LangBucket,
      { articles: number; latestShare: number | null; meanTone: number | null }
    > = {
      eng: { articles: 0, latestShare: null, meanTone: null },
      spa: { articles: 0, latestShare: null, meanTone: null },
      por: { articles: 0, latestShare: null, meanTone: null },
      other: { articles: 0, latestShare: null, meanTone: null },
    };
    const toneCount: Record<LangBucket, { sum: number; n: number }> = {
      eng: { sum: 0, n: 0 },
      spa: { sum: 0, n: 0 },
      por: { sum: 0, n: 0 },
      other: { sum: 0, n: 0 },
    };
    for (const row of timeline) {
      if (row.is_missing) continue;
      const bucket = summary[row.lang_bucket];
      if (!bucket) continue;
      bucket.articles += row.n_articles;
      if (row.share_of_day !== null) {
        bucket.latestShare = row.share_of_day;
      }
      if (row.mean_tone !== null && row.mean_tone !== undefined) {
        toneCount[row.lang_bucket].sum += row.mean_tone * row.n_articles;
        toneCount[row.lang_bucket].n += row.n_articles;
      }
    }
    for (const lang of ["eng", "spa", "por", "other"] as LangBucket[]) {
      if (toneCount[lang].n > 0) {
        summary[lang].meanTone = toneCount[lang].sum / toneCount[lang].n;
      }
    }
    return summary;
  }, [timeline]);

  async function handleChatSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = chatInput.trim();
    if (!trimmed || chatLoading) return;
    setChatLoading(true);
    setChatError(null);
    const immediateCmd = resolveChatViewCommand(trimmed, [], contextWeek);
    if (immediateCmd) {
      setActiveView(immediateCmd);
      if (immediateCmd.view === "temporal" || immediateCmd.view === "story") {
        setIsFullscreen(true);
      }
      if (immediateCmd.focus_topic) {
        selectTopic(immediateCmd.focus_topic);
      }
    }
    try {
      const res = await sendChatTurn({
        message: trimmed,
        conversation_id: conversationId,
        week: contextWeek,
      });
      setConversationId(res.conversation_id);
      setChatAnswer(res.answer_es);
      setChatCards(res.decision_cards);
      setTraceSteps(res.trace);
      const resolvedCmd = resolveChatViewCommand(
        trimmed,
        res.view_commands,
        contextWeek,
      );
      if (resolvedCmd) {
        setActiveView(resolvedCmd);
        if (resolvedCmd.view === "temporal" || resolvedCmd.view === "story") {
          setIsFullscreen(true);
        }
        if (resolvedCmd.focus_topic) {
          selectTopic(resolvedCmd.focus_topic);
        }
      }
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : String(err));
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <div className="app-shell">
      {freshness?.profile === "dev" && (
        <div className="dev-banner" role="status" data-testid="dev-banner">
          <strong>⚠️ Perfil activo: datos de desarrollo</strong> (`RADAR_PROFILE=dev` ·
          corte real en `fixtures/dev/`, los números de este corte no se reportan como
          resultado final).
        </div>
      )}

      <header className="app-header">
        <div>
          <h1>Radar de Señal Temprana · 30X</h1>
          <p className="subtitle">
            Qué temas de IA están subiendo antes de saturarse en español, por qué y desde
            qué ángulo contarlos a ejecutivos de LatAm (solo fuentes públicas).
          </p>
        </div>
        <div className="freshness-box">
          <div className="freshness-title">
            Frescura de datos (`GET /api/freshness`) · perfil:{" "}
            <code>{freshness?.profile ?? "..."}</code>
          </div>
          <div className="freshness-grid">
            {freshness &&
              Object.entries(freshness.tables).map(([table, dt]) => (
                <span key={table} className="freshness-chip">
                  <code>{table}</code>: {dt ?? "pendiente"}
                </span>
              ))}
          </div>
        </div>
      </header>

      <main className="split-view-container" ref={splitContainerRef}>
        {/* Left column: Top 10 cards + Chat + Timeline + Context + Trace */}
        <div className="split-left-pane" style={{ width: `${splitPct}%` }}>
          <section className="panel" aria-labelledby="top10-heading">
            <div className="panel-header">
              <h2 id="top10-heading">Top 10 semanal (`GET /api/radar`)</h2>
              <label className="week-picker">
                Semana{" "}
                <input
                  type="week"
                  aria-label="Semana ISO del radar"
                  value={radarWeek === "latest" ? "" : radarWeek}
                  max={freshness?.tables.topic_scores_weekly ?? undefined}
                  onChange={(e) => setRadarWeek(e.target.value || "latest")}
                />
              </label>
            </div>

            {radarItems.length === 0 ? (
              <div className="empty-state" data-testid="radar-empty-notice">
                <p>
                  <strong>Tabla `topic_scores_weekly` pendiente:</strong>{" "}
                  <code>{radarEmptyReason ?? "sin filas todavía"}</code>
                </p>
                <p>
                  Sin tarjetas para esta semana. Explora abajo las series diarias reales
                  por subtema y el anillo de 1 salto:
                </p>
                <div className="subtopic-pills">
                  {SUBTOPICS.map((st) => (
                    <button
                      key={st.id}
                      type="button"
                      className={
                        selectedTopic === st.id ? "pill pill-active" : "pill"
                      }
                      onClick={() => selectTopic(st.id)}
                    >
                      {st.label_es} (<code>{st.id}</code>)
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="cards-grid">
                {radarItems.map((card) => (
                  <article
                    key={card.topic_id}
                    className={
                      selectedTopic === card.topic_id
                        ? "topic-card topic-card-selected"
                        : "topic-card"
                    }
                    data-testid={`radar-card-${card.rank ?? card.topic_id}`}
                    onClick={() => {
                      selectTopic(card.topic_id);
                      setActiveView({
                        view: "story",
                        week: card.week,
                        focus_topic: card.topic_id,
                        highlight: [card.topic_id],
                        color_by: "tone",
                        caption_es: `Historia de 1 salto: ${topicName(
                          card.topic_id,
                          card.label_es,
                        )} (${card.topic_id})`,
                      });
                    }}
                  >
                    <div className="card-top">
                      <span className="rank-badge">#{card.rank ?? "-"}</span>
                      <h3>
                        {topicName(card.topic_id, card.label_es)}{" "}
                        <code className="topic-id">{card.topic_id}</code>
                      </h3>
                      <span className={`decision-badge decision-${card.decision}`}>
                        {DECISION_LABELS[card.decision]}
                      </span>
                    </div>
                    <div className="chips-row">
                      <span className="chip">Etapa: {card.stage}</span>
                      <span className="chip chip-window">
                        Ventana: {formatWindow(card.window)}
                      </span>
                      {card.emergence_pct != null && (
                        <span className="chip">
                          Emergencia: {card.emergence_pct.toFixed(1)} pct (medido)
                        </span>
                      )}
                      {card.saturation != null && (
                        <span className="chip">
                          Saturación: {(card.saturation * 100).toFixed(1)}% (medido)
                        </span>
                      )}
                      {card.audience_fit != null && (
                        <span className="chip">
                          Encaje LatAm: {(card.audience_fit * 100).toFixed(0)}% (medido)
                        </span>
                      )}
                      {card.emotional_charge_pct != null && (
                        <span className="chip">
                          Carga emocional: {card.emotional_charge_pct.toFixed(0)} pct
                          (medido)
                        </span>
                      )}
                      {card.framing_angle && (
                        <span className="chip">Ángulo: {card.framing_angle}</span>
                      )}
                    </div>
                    {card.why.length > 0 && (
                      <ul className="why-list">
                        {card.why.map((reason, idx) => (
                          <li key={idx}>{reason}</li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="panel" aria-labelledby="chat-heading">
            <div className="panel-header">
              <h2 id="chat-heading">Maestro de Medios (`POST /api/chat`)</h2>
              {conversationId && (
                <span className="badge">Sesión: {conversationId}</span>
              )}
            </div>

            <div className="quick-prompts">
              {QUICK_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="pill"
                  onClick={() => setChatInput(q)}
                >
                  {q}
                </button>
              ))}
            </div>

            <form className="chat-form" onSubmit={handleChatSubmit}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Pregunta al Maestro de Medios en español..."
                maxLength={2000}
              />
              <button type="submit" disabled={chatLoading}>
                {chatLoading ? "Consultando..." : "Preguntar"}
              </button>
            </form>

            {chatError && (
              <div className="error-box" role="alert">
                <strong>Estado del runtime:</strong> {chatError}
              </div>
            )}

            {chatAnswer && (
              <div className="chat-answer" data-testid="chat-answer">
                <pre className="answer-text">{chatAnswer}</pre>
              </div>
            )}

            {chatCards.length > 0 && (
              <div className="decision-cards-list">
                <h3>Tarjetas de decisión (`decision_card`)</h3>
                {chatCards.map((dc) => (
                  <div key={`${dc.topic_id}-${dc.week}`} className="decision-card">
                    <div className="card-top">
                      <strong>{dc.topic_id}</strong>
                      <span className={`decision-badge decision-${dc.decision}`}>
                        {DECISION_LABELS[dc.decision]}
                      </span>
                      <span className="badge">
                        Auditor: {dc.auditor_ok ? "verificado" : "alerta"}
                      </span>
                    </div>
                    <p>{dc.justification_es}</p>
                    <div className="chips-row">
                      {dc.kpis.map((kpi, i) => (
                        <span key={i} className="chip">
                          {kpi.name}: <strong>{String(kpi.value)}</strong>{" "}
                          {kpi.unit ?? ""} (
                          {kpi.kind === "measured" ? "medido" : "estimado"} ·{" "}
                          <code>{kpi.source}</code>)
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="panel" aria-labelledby="timeline-heading">
            <div className="panel-header">
              <h2 id="timeline-heading">
                Serie diaria por idioma (`GET /api/topic/{selectedTopic}/timeline`)
              </h2>
              <select
                aria-label="Seleccionar tema para la serie diaria"
                value={selectedTopic}
                onChange={(e) => selectTopic(e.target.value)}
              >
                {withSelected(
                  SUBTOPICS.map((st) => st.id),
                  selectedTopic,
                ).map((id) => (
                  <option key={id} value={id}>
                    {topicName(id)} ({id})
                  </option>
                ))}
              </select>
            </div>

            {timelineLoading ? (
              <p>Cargando serie diaria...</p>
            ) : (
              <>
                <div className="lang-summary-grid">
                  {(["eng", "spa", "por", "other"] as LangBucket[]).map((lang) => {
                    const info = langTotals[lang];
                    return (
                      <div key={lang} className="lang-stat-card">
                        <div className="lang-stat-header">
                          <span
                            className="lang-dot"
                            style={{ backgroundColor: LANG_COLORS[lang] }}
                          />
                          <strong>{lang.toUpperCase()}</strong>
                        </div>
                        <div>
                          Artículos (serie completa):{" "}
                          <strong>{info.articles.toLocaleString()}</strong> (medido)
                        </div>
                        <div>
                          Última participación:{" "}
                          <strong>
                            {info.latestShare !== null
                              ? `${(info.latestShare * 100).toFixed(3)}%`
                              : "NULL"}
                          </strong>{" "}
                          (medido)
                        </div>
                        <div>
                          Tono medio:{" "}
                          <strong>
                            {info.meanTone !== null
                              ? info.meanTone.toFixed(2)
                              : "NULL"}
                          </strong>{" "}
                          (medido)
                        </div>
                      </div>
                    );
                  })}
                </div>

                <TimelineChart
                  dates={timelineByDate.dates}
                  byLang={timelineByDate.byLang}
                />
              </>
            )}
          </section>

          <section className="panel" aria-labelledby="context-heading">
            <div className="panel-header">
              <h2 id="context-heading">
                Anillo de contexto 1-salto (`GET /api/topic/{selectedEntity}/context`)
              </h2>
              <select
                aria-label="Seleccionar entidad para contexto de 1 salto"
                value={selectedEntity}
                onChange={(e) => setSelectedEntity(e.target.value)}
              >
                {withSelected(CONTEXT_ENTITIES, selectedEntity).map((ent) => (
                  <option key={ent} value={ent}>
                    {topicName(ent)} ({ent})
                  </option>
                ))}
              </select>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Vecino</th>
                    <th>Co-menciones n (medido)</th>
                    <th>NPMI (medido)</th>
                    <th>Semana</th>
                  </tr>
                </thead>
                <tbody>
                  {contextRing.length === 0 && (
                    <tr>
                      <td colSpan={5} className="muted">
                        Sin anillo para este tema en la semana elegida.
                      </td>
                    </tr>
                  )}
                  {contextRing.map((row) => (
                    <tr key={row.neighbor}>
                      <td>{row.rank}</td>
                      <td>
                        <code>{row.neighbor}</code>
                      </td>
                      <td>{row.n}</td>
                      <td>{row.npmi.toFixed(4)}</td>
                      <td>{row.wk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel" aria-labelledby="trace-heading">
            <div className="panel-header">
              <h2 id="trace-heading">
                Traza de agentes (`agent_trace` · {traceSteps.length} pasos)
              </h2>
              <span className="badge">Contrato: agent_trace</span>
            </div>
            {traceSteps.length === 0 ? (
              <p className="muted">
                Envía una pregunta en el panel del Maestro de Medios para inspeccionar
                cada delegación, herramienta, latencia y verificación del Auditor.
              </p>
            ) : (
              <div className="table-scroll">
                <table className="data-table" data-testid="trace-table">
                  <thead>
                    <tr>
                      <th>Paso</th>
                      <th>Agente</th>
                      <th>Acción</th>
                      <th>Herramienta</th>
                      <th>Latencia</th>
                      <th>Resumen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traceSteps.map((s) => (
                      <tr key={s.step}>
                        <td>{s.step}</td>
                        <td>
                          <code>{s.agent}</code>
                        </td>
                        <td>
                          <span className={`action-tag action-${s.action}`}>
                            {s.action}
                          </span>
                        </td>
                        <td>
                          <code>{s.tool ?? "-"}</code>
                        </td>
                        <td>{s.latency_ms != null ? `${s.latency_ms} ms` : "-"}</td>
                        <td className="trace-summary">{s.result_summary ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        {/* Draggable Divider (Addendum 2 Must #2) */}
        <div
          className={`split-divider ${isDragging ? "is-dragging" : ""}`}
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={splitPct}
          aria-label="Ajustar ancho de paneles"
          tabIndex={0}
          onMouseDown={handleDividerMouseDown}
          onTouchStart={handleDividerTouchStart}
          title="Arrastra para cambiar la proporción de paneles"
        >
          <div className="divider-grip" />
        </div>

        {/* Right column: Graph panel with Fullscreen & Drawer & Floating Chat */}
        <div
          className="split-right-pane"
          style={{ width: `calc(${100 - splitPct}% - 12px)` }}
        >
          <section
            className={
              isFullscreen
                ? "panel view-placeholder view-panel-fullscreen"
                : "panel view-placeholder"
            }
            aria-labelledby="view-heading"
            data-testid="view-command-area"
          >
            <div className="panel-header">
              <h2 id="view-heading">
                {isFullscreen ? "⛶ Pantalla completa · " : ""}
                Vista controlada por agentes (`view_command`)
              </h2>
              <div className="view-mode-switcher">
                <button
                  type="button"
                  className={
                    activeView.view === "cards" ? "pill pill-active" : "pill"
                  }
                  data-testid="view-btn-cards"
                  onClick={() =>
                    setActiveView((prev) => ({
                      ...prev,
                      view: "cards",
                      caption_es:
                        "Vista de tarjetas activa (haz clic en una tarjeta o pide el grafo al Cartógrafo)",
                    }))
                  }
                >
                  Tarjetas
                </button>
                <button
                  type="button"
                  className={
                    activeView.view === "temporal" ? "pill pill-active" : "pill"
                  }
                  data-testid="view-btn-temporal"
                  onClick={() =>
                    setActiveView((prev) => ({
                      ...prev,
                      view: "temporal",
                      caption_es:
                        "Grafo temporal semanal de co-menciones (13 semanas · cosmos.gl GPU)",
                    }))
                  }
                >
                  Grafo temporal (GPU)
                </button>
                <button
                  type="button"
                  className={
                    activeView.view === "story" ? "pill pill-active" : "pill"
                  }
                  data-testid="view-btn-story"
                  onClick={() =>
                    setActiveView((prev) => ({
                      ...prev,
                      view: "story",
                      focus_topic:
                        prev.focus_topic ??
                        (selectedTopic.includes(":") ? selectedTopic : null),
                      caption_es: `Historia de 1 salto (${
                        prev.focus_topic ?? selectedTopic
                      })`,
                    }))
                  }
                >
                  Historia 1-salto
                </button>
                {isFullscreen ? (
                  <>
                    <button
                      type="button"
                      className="btn-drawer-toggle"
                      onClick={() => setIsCardsDrawerOpen((prev) => !prev)}
                      aria-expanded={isCardsDrawerOpen}
                    >
                      {isCardsDrawerOpen ? "✕ Ocultar tarjetas" : "☰ Tarjetas Top 10"}
                    </button>
                    <button
                      type="button"
                      className="btn-fullscreen-exit"
                      onClick={() => {
                        setIsFullscreen(false);
                        setIsCardsDrawerOpen(false);
                      }}
                      title="Presiona Esc para salir"
                    >
                      ✕ Salir (Esc)
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn-fullscreen-toggle"
                    onClick={() => setIsFullscreen(true)}
                    title="Presiona F para pantalla completa"
                  >
                    ⛶ Pantalla completa (F)
                  </button>
                )}
                <span className="badge">Vista activa: {activeView.view}</span>
              </div>
            </div>
            <p className="view-caption">{activeView.caption_es}</p>
            <div className="chips-row">
              <span className="chip">
                Modo: <code>{activeView.view}</code>
              </span>
              <span className="chip">
                Color por: <code>{activeView.color_by}</code>
              </span>
              <span className="chip">
                Semana: <code>{activeView.week ?? "última con datos"}</code>
              </span>
              {activeView.focus_topic && (
                <span className="chip">
                  Foco: <code>{activeView.focus_topic}</code>
                </span>
              )}
            </div>

            {activeView.view === "temporal" && (
              <TemporalGraph
                week={activeView.week ?? contextWeek}
                focusTopic={activeView.focus_topic}
                highlight={activeView.highlight}
                onSelectTopic={(topicId) => selectTopic(topicId)}
                onOpenStory={(topicId) => {
                  selectTopic(topicId);
                  setActiveView({
                    view: "story",
                    week: activeView.week ?? contextWeek ?? null,
                    focus_topic: topicId,
                    highlight: [topicId],
                    color_by: "tone",
                    caption_es: `Historia de 1 salto: ${topicId}`,
                  });
                }}
              />
            )}

            {activeView.view === "story" && (
              <StoryGraph
                focusTopic={activeView.focus_topic}
                highlight={activeView.highlight}
                onSelectTopic={(topicId) => selectTopic(topicId)}
              />
            )}

            {activeView.view === "cards" && (
              <p className="muted view-cards-hint">
                Haz clic en cualquier tarjeta del Top 10 a la izquierda para abrir su
                anillo de 1 salto en <code>sigma</code>, o pulsa{" "}
                <strong>Grafo temporal (GPU)</strong> / pregunta al Maestro de Medios{" "}
                <em>«Muéstrame el grafo de la semana»</em>.
              </p>
            )}

            {/* Collapsible drawer in fullscreen */}
            {isFullscreen && isCardsDrawerOpen && (
              <aside className="fullscreen-cards-drawer" aria-label="Cajón de tarjetas Top 10">
                <div className="drawer-header">
                  <h3>Tarjetas Top 10 semanal</h3>
                  <button
                    type="button"
                    className="btn-fullscreen-exit"
                    onClick={() => setIsCardsDrawerOpen(false)}
                  >
                    ✕
                  </button>
                </div>
                <div className="drawer-cards-list">
                  {radarItems.map((card) => (
                    <div
                      key={card.topic_id}
                      className="drawer-card-item"
                      onClick={() => {
                        selectTopic(card.topic_id);
                        setActiveView({
                          view: "story",
                          week: card.week,
                          focus_topic: card.topic_id,
                          highlight: [card.topic_id],
                          color_by: "tone",
                          caption_es: `Historia de 1 salto: ${topicName(
                            card.topic_id,
                            card.label_es,
                          )} (${card.topic_id})`,
                        });
                        setIsCardsDrawerOpen(false);
                      }}
                    >
                      <div className="drawer-card-top">
                        <span className="rank-badge">#{card.rank ?? "-"}</span>
                        <span className={`decision-badge decision-${card.decision}`}>
                          {DECISION_LABELS[card.decision]}
                        </span>
                      </div>
                      <div className="drawer-card-name">
                        {topicName(card.topic_id, card.label_es)}
                      </div>
                      <div className="chips-row">
                        <span className="chip">{formatWindow(card.window)}</span>
                        {card.emergence_pct != null && (
                          <span className="chip">
                            Emergencia: {card.emergence_pct.toFixed(0)} pct
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </aside>
            )}

            {/* Fullscreen Floating Chat */}
            {isFullscreen && (
              <aside
                className="fullscreen-floating-chat"
                aria-label="Chat flotante del Maestro de Medios"
              >
                <div className="floating-chat-header">
                  <h4>💬 Maestro de Medios</h4>
                  <button
                    type="button"
                    className="pill"
                    onClick={() => setIsFloatingChatOpen((prev) => !prev)}
                  >
                    {isFloatingChatOpen ? "▼ Minimizar" : "▲ Expandir"}
                  </button>
                </div>
                {isFloatingChatOpen && (
                  <div className="floating-chat-body">
                    <div className="quick-prompts">
                      {QUICK_QUESTIONS.slice(0, 3).map((q) => (
                        <button
                          key={q}
                          type="button"
                          className="pill"
                          onClick={() => setChatInput(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                    <form className="chat-form" onSubmit={handleChatSubmit}>
                      <input
                        type="text"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        placeholder="Pregunta en pantalla completa..."
                        maxLength={2000}
                      />
                      <button type="submit" disabled={chatLoading}>
                        {chatLoading ? "..." : "Enviar"}
                      </button>
                    </form>
                    {chatAnswer && (
                      <pre className="answer-text">{chatAnswer}</pre>
                    )}
                  </div>
                )}
              </aside>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function TimelineChart({
  dates,
  byLang,
}: {
  dates: string[];
  byLang: Record<LangBucket, Map<string, TopicDaily>>;
}) {
  if (dates.length === 0) {
    return <p className="muted">Sin datos para este tema.</p>;
  }
  const width = 640;
  const height = 180;
  const padX = 36;
  const padY = 20;

  let maxArticles = 1;
  for (const lang of ["eng", "spa", "por", "other"] as LangBucket[]) {
    for (const row of byLang[lang].values()) {
      if (!row.is_missing && row.n_articles > maxArticles) {
        maxArticles = row.n_articles;
      }
    }
  }

  function buildSegments(lang: LangBucket): string[] {
    const segments: string[] = [];
    let current: string[] = [];
    dates.forEach((dt, i) => {
      const row = byLang[lang].get(dt);
      if (!row || row.is_missing) {
        if (current.length > 1) segments.push(current.join(" "));
        current = [];
        return;
      }
      const x =
        padX + (i / Math.max(1, dates.length - 1)) * (width - padX * 2);
      const y =
        height -
        padY -
        (row.n_articles / maxArticles) * (height - padY * 2);
      current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    });
    if (current.length > 1) segments.push(current.join(" "));
    return segments;
  }

  return (
    <div className="chart-wrap">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="timeline-svg"
        role="img"
        aria-label="Serie diaria de artículos por idioma"
      >
        <line
          x1={padX}
          y1={height - padY}
          x2={width - padX}
          y2={height - padY}
          stroke="#cbd5e1"
        />
        {(["eng", "spa", "por", "other"] as LangBucket[]).map((lang) =>
          buildSegments(lang).map((pts, idx) => (
            <polyline
              key={`${lang}-${idx}`}
              fill="none"
              stroke={LANG_COLORS[lang]}
              strokeWidth="2"
              points={pts}
            />
          )),
        )}
        <text x={padX} y={14} fontSize="11" fill="#475569">
          Máx diario: {maxArticles} artículos (días is_missing quedan NULL)
        </text>
        <text x={padX} y={height - 4} fontSize="10" fill="#64748b">
          {dates[0]}
        </text>
        <text
          x={width - padX}
          y={height - 4}
          fontSize="10"
          fill="#64748b"
          textAnchor="end"
        >
          {dates[dates.length - 1]}
        </text>
      </svg>
    </div>
  );
}
