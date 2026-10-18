import { useEffect, useState } from "react";
import {
  type CardLoad,
  type LedgersFile,
  type TrustReport,
  kindLabel,
  readStaticJson,
} from "../demoCards";

function ReportBody({ report }: { report: TrustReport }) {
  if (report.markdown) {
    return (
      <pre className="trust-markdown" data-testid="trust-markdown">
        {report.markdown}
      </pre>
    );
  }
  return (
    <div>
      {report.sections?.map((section, index) => (
        <section key={`${section.heading ?? "s"}-${index}`}>
          {section.heading && <h4>{section.heading}</h4>}
          {section.bullets?.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {section.tables?.map((table, tableIndex) => (
            <table key={tableIndex} className="trust-table">
              <tbody>
                {table.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {Object.entries(row).map(([key, value]) => (
                      <td key={key}>
                        <span className="muted">{key}: </span>
                        {String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </section>
      ))}
    </div>
  );
}

function ReportSlot({
  title,
  path,
  testId,
  state,
}: {
  title: string;
  path: string;
  testId: string;
  state: CardLoad<TrustReport>;
}) {
  return (
    <section className="trust-slot" data-testid={testId}>
      <h3>{title}</h3>
      {state.status === "loading" && <p>Cargando…</p>}
      {state.status === "error" && <p className="error-box">{state.message}</p>}
      {state.status === "pending" && (
        <p className="pendiente">
          {title} pendiente <code>{state.path}</code>
        </p>
      )}
      {state.status === "ready" && (
        <>
          <p className="muted">
            Fuente: <code>{state.data.source ?? path}</code> · {kindLabel(state.data.kind)}. El
            texto es el informe, no un resumen reescrito.
          </p>
          <ReportBody report={state.data} />
        </>
      )}
    </section>
  );
}

export function TrustPanel() {
  const [backtest, setBacktest] = useState<CardLoad<TrustReport>>({ status: "loading" });
  const [labels, setLabels] = useState<CardLoad<TrustReport>>({ status: "loading" });
  const [ledgers, setLedgers] = useState<CardLoad<LedgersFile>>({ status: "loading" });

  useEffect(() => {
    let live = true;
    void readStaticJson("evidence/backtest.json").then((next) => {
      if (live) setBacktest(next as CardLoad<TrustReport>);
    });
    void readStaticJson("evidence/label_quality.json").then((next) => {
      if (live) setLabels(next as CardLoad<TrustReport>);
    });
    void readStaticJson("evidence/ledgers.json").then((next) => {
      if (live) setLedgers(next as CardLoad<LedgersFile>);
    });
    return () => {
      live = false;
    };
  }, []);

  const bq = ledgers.status === "ready" ? ledgers.data.bigquery : undefined;
  const jev = ledgers.status === "ready" ? ledgers.data.jev : undefined;

  return (
    <section className="panel trust-panel" data-testid="trust-panel" aria-labelledby="trust-heading">
      <div className="panel-header">
        <h2 id="trust-heading">Confianza</h2>
      </div>
      <p className="muted">
        Backtest, precisión y exhaustividad del filtro, y totales de BigQuery y Jev. Cada cifra
        muestra su denominador y si es medido o estimado. Un archivo que no está se queda en
        pendiente.
      </p>
      {ledgers.status === "loading" && <p>Cargando ledgers…</p>}
      {ledgers.status === "error" && <p className="error-box">{ledgers.message}</p>}
      {ledgers.status === "pending" && (
        <p className="pendiente" data-testid="trust-ledgers-pending">
          Ledgers pendiente <code>{ledgers.path}</code>
        </p>
      )}
      {ledgers.status === "ready" && (
        <div className="trust-ledgers" data-testid="trust-ledgers">
          {bq ? (
            <p>
              BigQuery: <strong>{bq.billed_gb}</strong> GB facturados en <strong>{bq.jobs}</strong>{" "}
              jobs ({bq.billed_bytes?.toLocaleString()} bytes, {kindLabel(bq.kind)}, fuente{" "}
              <code>{bq.source}</code>).
            </p>
          ) : (
            <p className="pendiente">BigQuery pendiente</p>
          )}
          {bq?.billed_gb_by_workstream && (
            <div className="chips-row">
              {Object.entries(bq.billed_gb_by_workstream).map(([ws, gb]) => (
                <span key={ws} className="chip">
                  {ws}: {gb} GB ({kindLabel(bq.kind)})
                </span>
              ))}
            </div>
          )}
          {jev ? (
            <p>
              Jev: <strong>{jev.cost_usd}</strong> USD en <strong>{jev.calls}</strong> llamadas,{" "}
              {jev.input_tokens?.toLocaleString()} tokens de entrada, latencia mediana{" "}
              {jev.median_latency_ms ?? "n/d"} ms sobre {jev.calls} llamadas ({kindLabel(jev.kind)},
              fuente <code>{jev.source}</code>).
            </p>
          ) : (
            <p className="pendiente">Jev pendiente</p>
          )}
        </div>
      )}
      <ReportSlot title="Backtest" path="evidence/backtest.json" testId="trust-backtest" state={backtest} />
      <ReportSlot
        title="Calidad del filtro"
        path="evidence/label_quality.json"
        testId="trust-labels"
        state={labels}
      />
    </section>
  );
}
