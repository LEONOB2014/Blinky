import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { communityLine, familyForTopic } from "./aiLexicon";
import {
  fetchFreshness,
  fetchRadar,
  fetchTopicContext,
  fetchTopicTimeline,
  sendChatTurn,
} from "./api";
import { BriefBlock, EvidenceBlock, StoryIndexCards } from "./components/BriefEvidence";
import { StoryGraph } from "./components/StoryGraph";
import { TemporalGraph } from "./components/TemporalGraph";
import { TrustPanel } from "./components/TrustPanel";
import { type GraphLens, lensForQuestion, lensFromCommand } from "./lenses";
import { displayName, publicLine } from "./publicCopy";
import { placeNamedTopic, type StoryPlacement } from "./temporalNodes";
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

/** Story lens on the GPU graph when the topic is one of the 1,000 nodes. */
function namedTopicView(
  topicId: string,
  week: string | null | undefined,
  label: string,
  placement: StoryPlacement,
): ViewCommand {
  if (placement === "gpu") {
    return {
      view: "temporal",
      week,
      focus_topic: topicId,
      highlight: [topicId],
      color_by: "segment",
      caption_es: `Historia en el grafo temporal: ${label} está entre los 1.000 nodos.`,
    };
  }
  const captionEs =
    placement === "sigma"
      ? `${label} no está entre los 1.000 nodos del grafo temporal; anillo de 1 salto.`
      : `Anillo de 1 salto: ${label}. No se pudo comprobar si está en el grafo temporal.`;
  return {
    view: "story",
    week,
    focus_topic: topicId,
    highlight: [topicId],
    color_by: "segment",
    caption_es: captionEs,
  };
}

/** Card title: the taxonomy label for subtopics, the name for org:/thm: topics. */
function topicName(topicId: string, labelEs?: string | null): string {
  if (SUBTOPIC_LABELS[topicId]) return SUBTOPIC_LABELS[topicId];
  if (labelEs && labelEs !== topicId) return displayName(labelEs);
  const idx = topicId.indexOf(":");
  return displayName(idx >= 0 ? topicId.slice(idx + 1) : topicId);
}

function weekOptionLabel(isoWeek: string): string {
  const match = /^(\d{4})-W(\d{2})$/.exec(isoWeek);
  if (!match) return isoWeek;
  return `Semana ${Number(match[2])} · ${match[1]}`;
}

const LANG_LABELS: Record<LangBucket, string> = {
  eng: "ENG",
  spa: "SPA",
  por: "POR",
  other: "Otros",
};

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
    last.color_by = lensFromCommand(last.color_by, message, last.focus_topic ?? matchedTopic);
    return last;
  }

  const lens = lensForQuestion(message, matchedTopic);
  if (asksWeeklyTemporal) {
    return {
      view: "temporal",
      week: defaultWeek ?? null,
      focus_topic: null,
      highlight: [],
      color_by: lens === "segment" ? "decision" : lens,
      caption_es: "Grafo temporal de co-menciones de la semana",
    };
  }
  if (asksGraph && matchedTopic) {
    return {
      view: "story",
      week: defaultWeek ?? null,
      focus_topic: matchedTopic,
      highlight: [matchedTopic],
      color_by: lens,
      caption_es: `Historia de 1 salto para ${matchedTopic}`,
    };
  }
  if (asksGraph) {
    return {
      view: "temporal",
      week: defaultWeek ?? null,
      focus_topic: null,
      highlight: [],
      color_by: lens === "segment" ? "decision" : lens,
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
  const n = `n=${w.n_onsets}`;
  switch (w.state) {
    case "dias_restantes":
      return `~${w.days_left ?? "?"} días restantes · ${n} ○`;
    case "en_cualquier_momento":
      return `En cualquier momento · ${n} ○`;
    case "ya_en_espanol":
      return `Ya en español · ${n} ●`;
    case "sin_estimacion":
    default:
      return `Sin estimación · ${n}`;
  }
}

function shortWindow(w: TopicWindow): string {
  switch (w.state) {
    case "dias_restantes":
      return `Ventana ~${w.days_left ?? "?"} días`;
    case "en_cualquier_momento":
      return "En cualquier momento";
    case "ya_en_espanol":
      return "Ya en español";
    case "sin_estimacion":
    default:
      return "Ventana sin estimar";
  }
}

function FamilyChip({
  topicId,
  family,
  familyEs,
}: {
  topicId: string;
  family?: string | null;
  familyEs?: string | null;
}) {
  const entry = familyForTopic(topicId, family);
  if (!entry) return null;
  return (
    <span className="family-chip" style={{ color: entry.color, borderColor: entry.color }}>
      {familyEs || entry.label}
    </span>
  );
}

function CommunityNote({ card }: { card: TopicScoreWeekly }) {
  if (!card.topic_id.startsWith("ai:") && card.community == null) return null;
  return <p className="community-line">{communityLine(card.community)}</p>;
}

function RowSignals({ card }: { card: TopicScoreWeekly }) {
  return (
    <span className="rail-signals">
      {card.emergence_pct != null && (
        <span>Emergencia p{Math.round(card.emergence_pct)}</span>
      )}
      <span>{shortWindow(card.window)}</span>
      {card.framing_angle ? <span>Ángulo {card.framing_angle}</span> : null}
    </span>
  );
}

const ES_MONTHS = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
];

/** Newest calendar day in the freshness payload (ISO dates only; week ids are not days). */
function newestCalendarDay(freshness: FreshnessResponse | null): string | null {
  if (!freshness) return null;
  let best: string | null = null;
  for (const value of Object.values(freshness.tables)) {
    if (value && /^\d{4}-\d{2}-\d{2}$/.test(value) && (best === null || value > best)) {
      best = value;
    }
  }
  return best;
}

function formatDayEs(iso: string): string {
  const [year, month, day] = iso.split("-");
  const monthName = ES_MONTHS[Number(month) - 1] ?? month;
  return `${Number(day)} ${monthName} ${year}`;
}

interface CoverageSpan {
  dt_max: string;
  span_weeks: number;
}

/** One human freshness line. The week count comes from daily_topic's date span. */
function freshnessLine(freshness: FreshnessResponse | null, coverage: CoverageSpan | null): string {
  const day = newestCalendarDay(freshness);
  const dated = day ? `Datos al ${formatDayEs(day)}` : "Datos";
  const weeks =
    coverage && day && coverage.dt_max === day ? `${coverage.span_weeks} semanas` : null;
  return [dated, weeks, "solo fuentes públicas"].filter(Boolean).join(" · ");
}

const DEFAULT_TEMPORAL_VIEW: ViewCommand = {
  view: "temporal",
  week: null,
  focus_topic: null,
  highlight: [],
  color_by: "decision",
  caption_es: "Grafo temporal semanal (13 semanas)",
};

function getInitialViewFromUrl(): ViewCommand {
  if (typeof window === "undefined") {
    return DEFAULT_TEMPORAL_VIEW;
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
      color_by: v === "story" ? "segment" : "decision",
      caption_es:
        v === "temporal"
          ? "Grafo temporal semanal (13 semanas)"
          : `Anillo de historia de 1 salto (${topic ?? "Top #1"})`,
    };
  }
  if (v === "cards") {
    return {
      view: "cards",
      week: wk,
      focus_topic: topic,
      highlight: topic ? [topic] : [],
      color_by: "decision",
      caption_es: "Vista inicial de tarjetas (esperando comando del Cartógrafo)",
    };
  }
  return DEFAULT_TEMPORAL_VIEW;
}

export function App() {
  const [freshness, setFreshness] = useState<FreshnessResponse | null>(null);
  const [coverage, setCoverage] = useState<CoverageSpan | null>(null);
  const [radarItems, setRadarItems] = useState<TopicScoreWeekly[]>([]);
  const [radarEmptyReason, setRadarEmptyReason] = useState<string | null>(null);
  // ISO week ("2026-W42") of the radar; empty until freshness gives the latest scored week.
  const [radarWeek, setRadarWeek] = useState<string>("");
  const [scoredWeeks, setScoredWeeks] = useState<string[]>([]);
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
  const [detailTopicId, setDetailTopicId] = useState<string | null>(null);

  // A shared ?view=story link still lands on the GPU story lens when the topic
  // is one of the 1,000 nodes. Later opens go through openNamedTopic.
  useEffect(() => {
    const topic = activeView.focus_topic;
    if (activeView.view !== "story" || !topic) return;
    let cancelled = false;
    void placeNamedTopic(topic).then((placement) => {
      if (cancelled || placement === "unknown") return;
      setActiveView((prev) => {
        if (prev.view !== "story" || prev.focus_topic !== topic) return prev;
        return namedTopicView(topic, prev.week, topic, placement);
      });
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showTrust, setShowTrust] = useState(false);
  const trustButtonRef = useRef<HTMLButtonElement>(null);
  const returnTrustFocus = useRef(false);
  const [isCardsDrawerOpen, setIsCardsDrawerOpen] = useState<boolean>(false);
  const [isFloatingChatOpen, setIsFloatingChatOpen] = useState<boolean>(false);
  const [dockExpanded, setDockExpanded] = useState(false);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const focusChatOnExpand = useRef(false);
  const activeLens = lensFromCommand(
    activeView.color_by,
    "",
    activeView.focus_topic ?? null,
  );

  const selectLens = useCallback((lens: GraphLens) => {
    setActiveView((prev) => ({ ...prev, color_by: lens }));
  }, []);

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
        if (showTrust) {
          returnTrustFocus.current = true;
          setShowTrust(false);
          return;
        }
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
  }, [showTrust]);

  useEffect(() => {
    if (!showTrust && returnTrustFocus.current) {
      returnTrustFocus.current = false;
      trustButtonRef.current?.focus();
    }
  }, [showTrust]);

  useEffect(() => {
    if (dockExpanded && focusChatOnExpand.current) {
      focusChatOnExpand.current = false;
      chatInputRef.current?.focus();
    }
  }, [dockExpanded]);

  function expandDock() {
    focusChatOnExpand.current = true;
    setDockExpanded(true);
  }

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
    void fetch(`${import.meta.env.BASE_URL}data/radar/weeks.json`)
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data: unknown) => {
        if (!data || typeof data !== "object" || !("weeks" in data)) return;
        const weeks = (data as { weeks: unknown }).weeks;
        if (!Array.isArray(weeks)) return;
        setScoredWeeks(weeks.filter((week): week is string => typeof week === "string"));
      })
      .catch(() => undefined);
    void fetch(`${import.meta.env.BASE_URL}data/coverage.json`)
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data: unknown) => {
        if (!data || typeof data !== "object") return;
        const row = data as { dt_max?: unknown; span_weeks?: unknown };
        if (typeof row.dt_max === "string" && typeof row.span_weeks === "number") {
          setCoverage({ dt_max: row.dt_max, span_weeks: row.span_weeks });
        }
      })
      .catch(() => undefined);
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
    setSelectedEntity(topicId);
  }

  async function openNamedTopic(
    topicId: string,
    week: string | null | undefined,
    label: string,
    fullscreen: boolean,
  ) {
    const placement = await placeNamedTopic(topicId);
    const cmd = namedTopicView(topicId, week, label, placement);
    setActiveView(cmd);
    if (fullscreen && (cmd.view === "temporal" || cmd.view === "story")) {
      setIsFullscreen(true);
    }
    setDetailTopicId(topicId);
    selectTopic(topicId);
  }

  async function applyViewCommand(cmd: ViewCommand) {
    if (cmd.view === "story" && cmd.focus_topic) {
      await openNamedTopic(cmd.focus_topic, cmd.week, cmd.focus_topic, false);
      return;
    }
    setActiveView(cmd);
    if (cmd.focus_topic) {
      setDetailTopicId(cmd.focus_topic);
      selectTopic(cmd.focus_topic);
    }
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
      void applyViewCommand(immediateCmd);
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
      setDockExpanded(true);
      setIsFloatingChatOpen(true);
      const resolvedCmd = resolveChatViewCommand(
        trimmed,
        res.view_commands,
        contextWeek,
      );
      if (resolvedCmd) {
        void applyViewCommand(resolvedCmd);
      }
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : String(err));
    } finally {
      setChatLoading(false);
    }
  }

  const detailCard =
    radarItems.find((card) => card.topic_id === detailTopicId) ?? null;

  return (
    <div className={`app-shell workspace${isFullscreen ? " workspace-fs" : ""}`}>
      {freshness?.profile === "dev" && (
        <div className="dev-banner" role="status" data-testid="dev-banner">
          <strong>⚠️ Perfil activo: datos de desarrollo</strong> (`RADAR_PROFILE=dev` ·
          corte real en `fixtures/dev/`, los números de este corte no se reportan como
          resultado final).
        </div>
      )}

      <header className="app-header workspace-header">
        <div className="brand-block">
          <h1>Radar de Señal Temprana · 30X</h1>
          <p className="subtitle">
            Qué temas de IA están subiendo antes de saturarse en español, por qué y desde
            qué ángulo contarlos a ejecutivos de LatAm (solo fuentes públicas).
          </p>
        </div>
        <div className="header-actions">
          <label className="week-picker">
            Semana{" "}
            <select
              aria-label="Semana puntuada"
              value={
                scoredWeeks.includes(radarWeek)
                  ? radarWeek
                  : (scoredWeeks.at(-1) ?? (radarWeek === "latest" ? "" : radarWeek))
              }
              onChange={(e) => setRadarWeek(e.target.value)}
            >
              {(scoredWeeks.length > 0
                ? scoredWeeks
                : radarWeek && radarWeek !== "latest"
                  ? [radarWeek]
                  : []
              ).map((week) => (
                <option key={week} value={week}>
                  {weekOptionLabel(week)}
                </option>
              ))}
            </select>
          </label>
          <button
            ref={trustButtonRef}
            type="button"
            className={showTrust ? "pill pill-active" : "pill"}
            data-testid="trust-toggle"
            onClick={() => setShowTrust((open) => !open)}
          >
            {showTrust ? "Ocultar confianza" : "Confianza"}
          </button>
          <p className="freshness-line" data-testid="freshness-line">
            {freshnessLine(freshness, coverage)}
          </p>
          <p className="measure-legend">● medido · ○ estimado</p>
          <details className="tech-details">
            <summary>Detalles técnicos</summary>
            <div className="freshness-grid">
              {freshness &&
                Object.entries(freshness.tables).map(([table, dt]) => (
                  <span key={table} className="freshness-chip">
                    <code>{table}</code>: {dt ?? "pendiente"}
                  </span>
                ))}
              {freshness && (
                <span className="freshness-chip">
                  perfil: <code>{freshness.profile}</code>
                </span>
              )}
              {detailTopicId && (
                <span className="freshness-chip">
                  tema: <code>{detailTopicId}</code>
                </span>
              )}
            </div>
            {radarEmptyReason && <p className="muted">{radarEmptyReason}</p>}
            {detailCard && detailCard.why.length > 0 && (
              <ul className="why-list">
                {detailCard.why.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            )}
          </details>
        </div>
      </header>

      {showTrust && (
        <div className="trust-overlay">
          <TrustPanel />
        </div>
      )}

      <div className="workspace-body">
        <aside className="workspace-rail" aria-labelledby="top10-heading">
          <div className="panel-header rail-header">
            <h2 id="top10-heading">Top 10 semanal</h2>
          </div>

          {radarItems.length === 0 ? (
            <div className="empty-state" data-testid="radar-empty-notice">
              <p>
                <strong>Sin temas puntuados para esta semana.</strong>
              </p>
              <p>Elige un subtema para ver su serie diaria y su anillo de 1 salto:</p>
              <div className="subtopic-pills">
                {SUBTOPICS.map((st) => (
                  <button
                    key={st.id}
                    type="button"
                    className={selectedTopic === st.id ? "pill pill-active" : "pill"}
                    onClick={() => {
                      setDetailTopicId(st.id);
                      selectTopic(st.id);
                    }}
                  >
                    {st.label_es}
                  </button>
                ))}
              </div>
              <StoryIndexCards />
            </div>
          ) : (
            <div className="cards-grid rail-list">
              {radarItems.map((card) => {
                const open = detailTopicId === card.topic_id;
                return (
                  <article
                    key={card.topic_id}
                    className={
                      selectedTopic === card.topic_id
                        ? "topic-card topic-card-selected"
                        : "topic-card"
                    }
                    data-testid={`radar-card-${card.rank ?? card.topic_id}`}
                  >
                    <button
                      type="button"
                      className="rail-row"
                      onClick={() => {
                        setDetailTopicId(card.topic_id);
                        void openNamedTopic(
                          card.topic_id,
                          card.week,
                          topicName(card.topic_id, card.label_es),
                          false,
                        );
                      }}
                    >
                      <span className="rank-badge">#{card.rank ?? "-"}</span>
                      <span className="rail-name">
                        {topicName(card.topic_id, card.label_es)}
                        <FamilyChip
                          topicId={card.topic_id}
                          family={card.family}
                          familyEs={card.family_es}
                        />
                        {(card.topic_id.startsWith("ai:") || card.community != null) && (
                          <span className="community-line">{communityLine(card.community)}</span>
                        )}
                      </span>
                      <span className={`decision-badge decision-${card.decision}`}>
                        {DECISION_LABELS[card.decision]}
                      </span>
                      <RowSignals card={card} />
                    </button>
                    {open && (
                      <TopicDetail
                        card={card}
                        timelineLoading={timelineLoading}
                        langTotals={langTotals}
                        timelineByDate={timelineByDate}
                        contextRing={contextRing}
                        selectedTopic={selectedTopic}
                        onSelectTopic={selectTopic}
                      />
                    )}
                  </article>
                );
              })}
            </div>
          )}

          {detailTopicId && !detailCard && (
            <article className="topic-card topic-card-selected">
              <h3>{topicName(detailTopicId)}</h3>
              <TopicSeries
                timelineLoading={timelineLoading}
                langTotals={langTotals}
                timelineByDate={timelineByDate}
                contextRing={contextRing}
                selectedTopic={selectedTopic}
                onSelectTopic={selectTopic}
              />
            </article>
          )}
        </aside>

        <section
          className={
            isFullscreen
              ? "workspace-stage view-panel-fullscreen"
              : "workspace-stage"
          }
          aria-label="Grafo"
          data-testid="view-command-area"
        >
          {activeView.view === "temporal" && (
            <TemporalGraph
              week={activeView.week ?? contextWeek}
              focusTopic={activeView.focus_topic}
              highlight={activeView.highlight}
              colorBy={activeLens}
              captionEs={activeView.caption_es}
              isFullscreen={isFullscreen}
              dockOpen={dockExpanded}
              onToggleFullscreen={() => setIsFullscreen((prev) => !prev)}
              onLensChange={selectLens}
              onSelectTopic={(topicId) => {
                setDetailTopicId(topicId);
                selectTopic(topicId);
              }}
              onOpenStory={(topicId) => {
                void openNamedTopic(
                  topicId,
                  activeView.week ?? contextWeek ?? null,
                  topicId,
                  false,
                );
              }}
            />
          )}

          {activeView.view === "story" && (
            <StoryGraph
              focusTopic={activeView.focus_topic}
              highlight={activeView.highlight}
              colorBy={activeLens}
              captionEs={activeView.caption_es}
              isFullscreen={isFullscreen}
              onToggleFullscreen={() => setIsFullscreen((prev) => !prev)}
              onLensChange={selectLens}
              onSelectTopic={(topicId) => {
                setDetailTopicId(topicId);
                selectTopic(topicId);
              }}
            />
          )}

          {activeView.view === "cards" && (
            <p className="muted view-cards-hint">
              Haz clic en cualquier tarjeta del Top 10 a la izquierda para abrir su
              historia (en el grafo temporal si el tema está entre los 1.000 nodos), o pulsa{" "}
              <strong>Grafo temporal (GPU)</strong> / pregunta al Maestro de Medios{" "}
              <em>«Muéstrame el grafo de la semana»</em>.
            </p>
          )}

          {activeView.view !== "temporal" && (
            <div className="stage-switch">
              <button
                type="button"
                className="pill"
                data-testid="view-btn-temporal"
                onClick={() =>
                  setActiveView((prev) => ({
                    ...prev,
                    view: "temporal",
                    color_by: "decision",
                    caption_es: "Grafo temporal semanal (13 semanas)",
                  }))
                }
              >
                Grafo temporal (GPU)
              </button>
            </div>
          )}

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
                      void openNamedTopic(
                        card.topic_id,
                        card.week,
                        topicName(card.topic_id, card.label_es),
                        false,
                      );
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
                    <RowSignals card={card} />
                  </div>
                ))}
              </div>
            </aside>
          )}

          {dockExpanded ? (
          <aside
            className="fullscreen-floating-chat chat-dock"
            aria-label="Maestro de Medios"
            data-testid="media-dock"
          >
            <div className="floating-chat-header">
              <h2>Maestro de Medios</h2>
              <div className="chat-dock-actions">
                <button type="button" className="pill" onClick={() => setDockExpanded(false)}>
                  Cerrar
                </button>
                {isFullscreen && (
                  <button
                    type="button"
                    className="pill"
                    onClick={() => setIsCardsDrawerOpen((prev) => !prev)}
                    aria-expanded={isCardsDrawerOpen}
                  >
                    {isCardsDrawerOpen ? "Ocultar top 10" : "Top 10"}
                  </button>
                )}
                <button
                  type="button"
                  className="pill"
                  onClick={() => setIsFloatingChatOpen((prev) => !prev)}
                  aria-expanded={isFloatingChatOpen}
                >
                  {isFloatingChatOpen ? "Ocultar respuesta" : "Ver respuesta"}
                </button>
              </div>
            </div>
            {isFloatingChatOpen && (
              <div className="floating-chat-body">
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
                    <h3>Tarjetas de decisión</h3>
                    {chatCards.map((dc) => (
                      <div key={`${dc.topic_id}-${dc.week}`} className="decision-card">
                        <div className="card-top">
                          <strong>{topicName(dc.topic_id)}</strong>
                          <span className={`decision-badge decision-${dc.decision}`}>
                            {DECISION_LABELS[dc.decision]}
                          </span>
                          <span className="badge">
                            Auditor: {dc.auditor_ok ? "verificado" : "alerta"}
                          </span>
                        </div>
                        <p>{dc.justification_es}</p>
                      </div>
                    ))}
                  </div>
                )}
                <details className="trace-disclosure">
                  <summary>Cómo llegó a esta respuesta</summary>
                  {traceSteps.length === 0 ? (
                    <p className="muted">
                      Envía una pregunta para ver cada paso de la respuesta.
                    </p>
                  ) : (
                    <div className="table-scroll">
                      <table className="data-table" data-testid="trace-table">
                        <thead>
                          <tr>
                            <th>Paso</th>
                            <th>Agente</th>
                            <th>Acción</th>
                            <th>Resumen</th>
                          </tr>
                        </thead>
                        <tbody>
                          {traceSteps.map((s) => (
                            <tr key={s.step}>
                              <td>{s.step}</td>
                              <td>{s.agent}</td>
                              <td>
                                <span className={`action-tag action-${s.action}`}>
                                  {s.action}
                                </span>
                              </td>
                              <td className="trace-summary">{s.result_summary ?? "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </details>
              </div>
            )}
            <form className="chat-form" onSubmit={handleChatSubmit}>
              <input
                ref={chatInputRef}
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Pregunta al Maestro de Medios en español..."
                maxLength={2000}
                aria-label="Pregunta al Maestro de Medios"
              />
              <button type="submit" disabled={chatLoading}>
                {chatLoading ? "Consultando..." : "Preguntar"}
              </button>
            </form>
          </aside>
          ) : (
            <button
              type="button"
              className="chat-dock-pill"
              data-testid="media-dock"
              aria-expanded="false"
              onClick={expandDock}
              onFocus={expandDock}
            >
              Pregúntale al Maestro de Medios
            </button>
          )}
        </section>
      </div>
    </div>
  );
}

function TopicDetail({
  card,
  timelineLoading,
  langTotals,
  timelineByDate,
  contextRing,
  selectedTopic,
  onSelectTopic,
}: {
  card: TopicScoreWeekly;
  timelineLoading: boolean;
  langTotals: Record<
    LangBucket,
    { articles: number; latestShare: number | null; meanTone: number | null }
  >;
  timelineByDate: { dates: string[]; byLang: Record<LangBucket, Map<string, TopicDaily>> };
  contextRing: TopicContext1Hop[];
  selectedTopic: string;
  onSelectTopic: (topicId: string) => void;
}) {
  return (
    <div className="rail-detail">
      <div className="chips-row">
        <span className="chip">Etapa: {card.stage}</span>
        <span className="chip chip-window">Ventana: {formatWindow(card.window)}</span>
        {card.emergence_pct != null && (
          <span className="chip">Emergencia: {card.emergence_pct.toFixed(1)} pct ●</span>
        )}
        {card.saturation != null && (
          <span className="chip">Saturación: {(card.saturation * 100).toFixed(1)}% ●</span>
        )}
        {card.audience_fit != null && (
          <span className="chip">Encaje LatAm: {(card.audience_fit * 100).toFixed(0)}% ○</span>
        )}
        {card.emotional_charge_pct != null && (
          <span className="chip">
            Carga emocional: {card.emotional_charge_pct.toFixed(0)} pct ●
          </span>
        )}
        {card.framing_angle && <span className="chip">Ángulo: {card.framing_angle}</span>}
        <FamilyChip topicId={card.topic_id} family={card.family} familyEs={card.family_es} />
      </div>
      <CommunityNote card={card} />
      {card.why.length > 0 && (
        <ul className="why-list">
          {card.why.map((reason, idx) => (
            <li key={idx}>{publicLine(reason)}</li>
          ))}
        </ul>
      )}
      <BriefBlock topicId={card.topic_id} week={card.week} />
      <EvidenceBlock topicId={card.topic_id} week={card.week} />
      <TopicSeries
        timelineLoading={timelineLoading}
        langTotals={langTotals}
        timelineByDate={timelineByDate}
        contextRing={contextRing}
        selectedTopic={selectedTopic}
        onSelectTopic={onSelectTopic}
      />
    </div>
  );
}

function TopicSeries({
  timelineLoading,
  langTotals,
  timelineByDate,
  contextRing,
  selectedTopic,
  onSelectTopic,
}: {
  timelineLoading: boolean;
  langTotals: Record<
    LangBucket,
    { articles: number; latestShare: number | null; meanTone: number | null }
  >;
  timelineByDate: { dates: string[]; byLang: Record<LangBucket, Map<string, TopicDaily>> };
  contextRing: TopicContext1Hop[];
  selectedTopic: string;
  onSelectTopic: (topicId: string) => void;
}) {
  return (
    <div className="topic-series">
      <div className="panel-header">
        <h3>Serie diaria por idioma</h3>
        <select
          aria-label="Seleccionar tema para la serie diaria"
          value={selectedTopic}
          onChange={(e) => onSelectTopic(e.target.value)}
        >
          {withSelected(SUBTOPICS.map((st) => st.id), selectedTopic).map((id) => (
            <option key={id} value={id}>
              {topicName(id)}
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
                    <span className="lang-dot" style={{ backgroundColor: LANG_COLORS[lang] }} />
                    <strong>{LANG_LABELS[lang]}</strong>
                  </div>
                  <div>
                    Artículos (serie completa): <strong>{info.articles.toLocaleString()}</strong> ●
                  </div>
                  <div>
                    Última participación:{" "}
                    <strong>
                      {info.latestShare !== null
                        ? `${(info.latestShare * 100).toFixed(3)}%`
                        : "—"}
                    </strong>{" "}
                    ●
                  </div>
                  <div>
                    Tono medio:{" "}
                    <strong>{info.meanTone !== null ? info.meanTone.toFixed(2) : "—"}</strong> ●
                  </div>
                </div>
              );
            })}
          </div>
          <TimelineChart dates={timelineByDate.dates} byLang={timelineByDate.byLang} />
        </>
      )}
      <h3 className="series-context-title">Anillo de 1 salto</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Vecino</th>
              <th>Co-menciones</th>
              <th>NPMI</th>
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
                <td>{topicName(row.neighbor)}</td>
                <td>{row.n}</td>
                <td>{row.npmi.toFixed(4)}</td>
                <td>{row.wk}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
        <text x={padX} y={14} fontSize="12" fill="#475569">
          Máx diario: {maxArticles} artículos (los días sin datos quedan en —)
        </text>
        <text x={padX} y={height - 4} fontSize="12" fill="#64748b">
          {dates[0]}
        </text>
        <text
          x={width - padX}
          y={height - 4}
          fontSize="12"
          fill="#64748b"
          textAnchor="end"
        >
          {dates[dates.length - 1]}
        </text>
      </svg>
    </div>
  );
}
