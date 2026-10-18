import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  fetchFreshness,
  fetchRadar,
  fetchTopicContext,
  fetchTopicTimeline,
  sendChatTurn,
} from "./api";
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

const CONTEXT_ENTITIES = [
  "org:google",
  "org:openai",
  "org:microsoft",
  "org:meta",
  "thm:ECON_STOCKMARKET",
];

const QUICK_QUESTIONS = [
  "¿Qué tema de IA sube esta semana y por qué? Muéstramelo en el grafo",
  "¿Cuál es el ángulo para ejecutivos de LatAm esta semana?",
  "¿Qué tan frescos están los datos y cuánto ha costado en BigQuery?",
];

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

export function App() {
  const [freshness, setFreshness] = useState<FreshnessResponse | null>(null);
  const [radarItems, setRadarItems] = useState<TopicScoreWeekly[]>([]);
  const [radarEmptyReason, setRadarEmptyReason] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string>("regulation_policy");
  const [timeline, setTimeline] = useState<TopicDaily[]>([]);
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);
  const [selectedEntity, setSelectedEntity] = useState<string>("org:google");
  const [contextRing, setContextRing] = useState<TopicContext1Hop[]>([]);

  const [chatInput, setChatInput] = useState<string>(QUICK_QUESTIONS[0]);
  const [conversationId, setConversationId] = useState<string | undefined>(
    undefined,
  );
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [chatCards, setChatCards] = useState<DecisionCard[]>([]);
  const [traceSteps, setTraceSteps] = useState<AgentTraceStep[]>([]);
  const [activeView, setActiveView] = useState<ViewCommand>({
    view: "cards",
    week: null,
    focus_topic: null,
    highlight: [],
    color_by: "tone",
    caption_es: "Vista inicial de tarjetas (esperando comando del Cartógrafo)",
  });
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    void fetchFreshness()
      .then(setFreshness)
      .catch((err: unknown) => {
        console.error(err);
      });

    void fetchRadar()
      .then((res) => {
        setRadarItems(res.items);
        setRadarEmptyReason(res.emptyReason);
        if (res.items.length > 0) {
          setSelectedTopic(res.items[0].topic_id);
        }
      })
      .catch((err: unknown) => {
        console.error(err);
      });
  }, []);

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
    void fetchTopicContext(selectedEntity)
      .then(setContextRing)
      .catch((err: unknown) => {
        console.error(err);
        setContextRing([]);
      });
  }, [selectedEntity]);

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
    try {
      const res = await sendChatTurn({
        message: trimmed,
        conversation_id: conversationId,
      });
      setConversationId(res.conversation_id);
      setChatAnswer(res.answer_es);
      setChatCards(res.decision_cards);
      setTraceSteps(res.trace);
      if (res.view_commands.length > 0) {
        setActiveView(res.view_commands[res.view_commands.length - 1]);
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

      <main className="main-grid">
        {/* Left column: Top 10 cards + Timeline + 1-hop context */}
        <div className="left-col">
          <section className="panel" aria-labelledby="top10-heading">
            <div className="panel-header">
              <h2 id="top10-heading">Top 10 semanal (`GET /api/radar`)</h2>
              <span className="badge">Contrato: topic_scores_weekly</span>
            </div>

            {radarItems.length === 0 ? (
              <div className="empty-state" data-testid="radar-empty-notice">
                <p>
                  <strong>Tabla `topic_scores_weekly` pendiente:</strong>{" "}
                  <code>{radarEmptyReason ?? "sin filas todavía"}</code>
                </p>
                <p>
                  Mientras WS4 entrega `topic_scores_weekly`, explora abajo las series
                  diarias reales del corte (`daily_topic`, 8 semanas medidas) y el anillo
                  de 1 salto (`edges_weekly`, 12,000 aristas medidas):
                </p>
                <div className="subtopic-pills">
                  {SUBTOPICS.map((st) => (
                    <button
                      key={st.id}
                      type="button"
                      className={
                        selectedTopic === st.id ? "pill pill-active" : "pill"
                      }
                      onClick={() => setSelectedTopic(st.id)}
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
                    onClick={() => setSelectedTopic(card.topic_id)}
                  >
                    <div className="card-top">
                      <span className="rank-badge">#{card.rank ?? "-"}</span>
                      <h3>{card.label_es}</h3>
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

          <section className="panel" aria-labelledby="timeline-heading">
            <div className="panel-header">
              <h2 id="timeline-heading">
                Serie diaria por idioma (`GET /api/topic/{selectedTopic}/timeline`)
              </h2>
              <select
                aria-label="Seleccionar tema para la serie diaria"
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
              >
                {SUBTOPICS.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.label_es} ({st.id})
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
                          Artículos (8 sem):{" "}
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
                {CONTEXT_ENTITIES.map((ent) => (
                  <option key={ent} value={ent}>
                    {ent}
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
                  {contextRing.slice(0, 10).map((row) => (
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
        </div>

        {/* Right column: View Command placeholder + Chat panel + Agent Trace panel */}
        <div className="right-col">
          <section
            className="panel view-placeholder"
            aria-labelledby="view-heading"
            data-testid="view-command-area"
          >
            <div className="panel-header">
              <h2 id="view-heading">Vista controlada por agentes (`view_command`)</h2>
              <span className="badge">Vista activa: {activeView.view}</span>
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
