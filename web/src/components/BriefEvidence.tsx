import { useEffect, useState } from "react";
import {
  type CardLoad,
  type EvidenceArticle,
  type TopicBrief,
  loadBrief,
  loadEvidence,
} from "../demoCards";
import { markForKind } from "../publicCopy";

function Pending({ testId, path, label }: { testId: string; path: string; label: string }) {
  return (
    <p className="pendiente" data-testid={testId} data-source={path}>
      {label} pendiente
    </p>
  );
}

export function BriefBlock({ topicId, week }: { topicId: string; week: string }) {
  const [state, setState] = useState<CardLoad<TopicBrief>>({ status: "loading" });

  useEffect(() => {
    let live = true;
    void loadBrief(week, topicId).then((next) => {
      if (live) setState(next);
    });
    return () => {
      live = false;
    };
  }, [topicId, week]);

  return (
    <div
      className="brief-block"
      data-testid="brief-block"
      onClick={(event) => event.stopPropagation()}
    >
      <details>
        <summary>Brief</summary>
        {state.status === "loading" && <p>Cargando brief…</p>}
        {state.status === "error" && <p className="error-box">{state.message}</p>}
        {state.status === "pending" && (
          <Pending testId="brief-pending" path={state.path} label="Brief" />
        )}
        {state.status === "ready" && <BriefBody brief={state.data} />}
      </details>
    </div>
  );
}

function BriefBody({ brief }: { brief: TopicBrief }) {
  const fields: { label: string; value: string | undefined }[] = [
    { label: "Qué pasó", value: brief.what_happened_es },
    { label: "Por qué LatAm", value: brief.why_latam_es },
    { label: "Ángulo", value: brief.angle_es },
    { label: "Gancho", value: brief.hook_es },
    { label: "Formato", value: brief.format_es },
  ];
  return (
    <div className="brief-body">
      <div className="card-top">
        <strong data-testid="brief-headline">{brief.headline_es || "Sin titular en el archivo"}</strong>
        <span
          className={brief.auditor_ok ? "badge auditor-ok" : "badge auditor-review"}
          data-testid="auditor-badge"
        >
          {brief.auditor_ok ? "verificado por el Auditor" : "revisar"}
        </span>
      </div>
      {fields.map((field) =>
        field.value ? (
          <p key={field.label}>
            <span className="brief-label">{field.label}:</span> {field.value}
          </p>
        ) : null,
      )}
      {brief.numbers_cited && brief.numbers_cited.length > 0 && (
        <div className="chips-row">
          {brief.numbers_cited.map((item, index) => (
            <span key={`${item.name}-${index}`} className="chip">
              {item.name}: <strong>{String(item.value)}</strong> {markForKind(item.kind)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function EvidenceBlock({ topicId, week }: { topicId: string; week: string }) {
  const [state, setState] = useState<CardLoad<EvidenceArticle[]>>({ status: "loading" });

  useEffect(() => {
    let live = true;
    void loadEvidence(week, topicId).then((next) => {
      if (live) setState(next);
    });
    return () => {
      live = false;
    };
  }, [topicId, week]);

  return (
    <div
      className="evidence-block"
      data-testid="evidence-block"
      onClick={(event) => event.stopPropagation()}
    >
      <details>
        <summary>
          Evidencia
          {state.status === "ready" ? ` (${state.data.length} de hasta 5)` : ""}
        </summary>
        {state.status === "loading" && <p>Cargando evidencia…</p>}
        {state.status === "error" && <p className="error-box">{state.message}</p>}
        {state.status === "pending" && (
          <Pending testId="evidence-pending" path={state.path} label="Evidencia" />
        )}
        {state.status === "ready" && (
          <ul className="evidence-list">
            {state.data.map((article, index) => (
              <li key={`${article.url ?? index}`}>
                {article.url ? (
                  <a href={article.url} target="_blank" rel="noopener noreferrer">
                    {article.title || article.url}
                  </a>
                ) : (
                  <span>{article.title || "Sin título"}</span>
                )}
                <span className="muted">
                  {" "}
                  · {article.source || "medio pendiente"} · {article.dt || "fecha pendiente"} ·{" "}
                  {article.lang_bucket || "idioma pendiente"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  );
}

interface IndexTopic {
  topic_id: string;
  label_es?: string;
  week?: string;
  rank?: number | null;
  in_top10?: boolean;
}

/** Top 10 from stories_index when /api/radar returned no rows. */
export function StoryIndexCards() {
  const [rows, setRows] = useState<IndexTopic[] | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let live = true;
    void fetch(`${import.meta.env.BASE_URL}data/views/stories_index.json`)
      .then(async (resp) => {
        if (!resp.ok) throw new Error(String(resp.status));
        return (await resp.json()) as { top10?: IndexTopic[]; stories?: Record<string, IndexTopic> };
      })
      .then((data) => {
        if (!live) return;
        const top = data.top10 ?? [];
        const refs = Object.values(data.stories ?? {}).filter((row) => row.in_top10 === false);
        setRows([...top, ...refs]);
      })
      .catch(() => {
        if (live) setMissing(true);
      });
    return () => {
      live = false;
    };
  }, []);

  if (missing) {
    return (
      <p className="pendiente" data-testid="story-index-pending">
        Índice de historias pendiente
      </p>
    );
  }
  if (!rows) return <p>Cargando índice de historias…</p>;
  const top = rows.filter((row) => row.in_top10 !== false);
  const refs = rows.filter((row) => row.in_top10 === false);
  return (
    <div data-testid="static-brief-list">
      <p className="muted">
        La API no devolvió el top 10. Brief y evidencia de {top.length} temas.
      </p>
      <TopicBriefList rows={top} />
      {refs.length > 0 && (
        <details className="brief-block" data-testid="reference-briefs">
          <summary>Referencias fuera del top 10 ({refs.length})</summary>
          <TopicBriefList rows={refs} />
        </details>
      )}
    </div>
  );
}

function TopicBriefList({ rows }: { rows: IndexTopic[] }) {
  return (
    <div className="cards-grid">
      {rows.map((row) => (
        <article
          key={row.topic_id}
          className="topic-card"
          data-testid={`static-card-${row.topic_id}`}
        >
          <div className="card-top">
            <span className="rank-badge">#{row.rank ?? "-"}</span>
            <h3>
              {row.label_es || row.topic_id}
            </h3>
          </div>
          <BriefBlock topicId={row.topic_id} week={row.week ?? ""} />
          <EvidenceBlock topicId={row.topic_id} week={row.week ?? ""} />
        </article>
      ))}
    </div>
  );
}
