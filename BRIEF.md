# BRIEF: the demo layout (design review findings) — for Grok

Branch `feat/ws5-design-review` · Worktree `../radar-worktrees/feat-ws5-design-review`
Written by the orchestrator, 2026-10-18 05:15 UTC-5, from a design audit of `develop` (e4518d2) on the
full lake. A dev server is running from this worktree (API :8010 full profile, Vite :5180 with HMR); do
not stop them; the orchestrator watches your changes live there. Read `AGENTS.md`, then this file.

## Who looks at it

Business-side judges and LatAm media executives, Spanish. The surface is an app (OPERATE): calm,
scannable, one accent, the graph is the hero, the chat is the product's differentiator. Today it reads
as an engineering console.

## Findings (fix in this order, one commit per item, `style(design): FINDING-NNN — ...`)

1. **FINDING-001 (high): one-viewport workspace.** The default view hides the graph (a "Vista inicial
   de tarjetas" placeholder) and the chat sits at y≈4,970 px of a 7,028 px page. Make the default a
   `100svh` workspace with no page scroll:
   - header bar: brand "Radar de Señal Temprana · 30X", one-line promise, week selector, "Confianza"
     (opens the Trust panel), and data freshness as one human line ("Datos al 18 oct 2026 · 51
     semanas · solo fuentes públicas");
   - left rail (~30%, own scroll): the top 10 as compact rows (rank, name, decision pill, one-line
     why); clicking a row opens its detail (chips, brief, evidence) in a drawer or an inline expansion
     and focuses the topic in the graph;
   - main area (~70%): the temporal GPU graph by default (Radar lens), lens pills and the caption on
     top, legend below;
   - chat dock bottom-right over the graph (reuse the full-screen floating chat), input always
     visible, collapsible; answers in the dock; the agent trace behind "Cómo llegó a esta respuesta".
   - The full-screen mode stays (F / Esc) and hides the rail.
   - The language timeline and the 1-hop table move into the topic detail, not the main page.
2. **FINDING-002 (high): no engineering vocabulary on screen.** Remove from the visible UI: endpoint
   names (`GET /api/...`, `POST /api/chat`, `view_command`), table names in the freshness strip,
   `org:`/`thm:` ids under names, "Modo:", "Vista activa:", "regla N", "cosmos.gl". Keep the
   measured/estimated distinction with a small marker and a legend, not "(medido)" after every value.
   Put the raw details behind one "Detalles técnicos" disclosure (keep it: judges may ask).
3. **FINDING-003 (high): the graph fills its container** in the split view and full screen
   (ResizeObserver → cosmos `setConfig`/`fitView`), never a fixed small box or a half-empty screen.
4. **FINDING-004 (high, demo risk): no WebGL, no black box.** When neither WebGL2 nor WebGL is
   available, show a Spanish message ("Este navegador no tiene aceleración gráfica activada; mostramos
   una imagen del grafo") and a pre-rendered image of the graph: copy `lake/views/temporal.png` (or a
   fresh headed-Chrome capture) to `web/public/data/views/temporal.png` in the copy step; the story
   view falls back to the neighbour list.
5. **FINDING-005 (medium): compact cards.** A row shows rank, name, decision, and at most 3 signals
   (Emergencia, Ventana, Ángulo); the rest in the detail.
6. **FINDING-006 (medium): names and language.** Title-case a lowercase GDELT name when there is no
   `label_es` ("national stock exchange" → "National Stock Exchange"); a Spanish week selector of the
   scored weeks ("Semana 42 · 2026") instead of the native week input; "OTHER" → "Otros"; never print
   `NULL` (use "—").
7. **FINDING-007 (medium): one design system.** CSS variables for color, spacing (4/8 scale), radius
   and type; one accent; the same decision colors everywhere (publicar ahora, preparar, esperar, no es
   tema caliente) in cards, pills, graph legend; body text >= 14px in the dense app, labels >= 12px;
   visible focus rings; touch targets >= 36px.

## Rules

Same data and behavior: never change numbers, never invent text; Spanish copy, short, utility tone.
`bun run build` passes before each commit; `make check && make test` pass. Screenshots (headed Chrome,
1440×900 and 1280×720) after items 1-4 into `lake/views/design/`. Commit locally; the orchestrator
pushes.

## Deadline (UTC-5)

Items 1-4 by **06:45**; 5-7 by **07:30**.

## Addendum (orchestrator, 05:25 UTC-5): two more from the live-site check

8. **FINDING-008 (high, honesty):** the card says "Encaje LatAm: 65% (medido)", but audience fit is a
   rule-based estimate (`why` says "regla v1, estimación"). Mark it estimated wherever it appears.
9. **FINDING-009 (medium):** the trust panel shows the label-quality and backtest reports as raw markdown
   (tables as pipes). Render them properly: either a small markdown-table renderer for the existing
   `evidence/*.json`, or the key numbers as a compact table (coverage, precision@10 with interval,
   baselines, base rate; filter precision/recall vs the model panel, "verificación humana pendiente").

## Addendum (orchestrator, 05:30 UTC-5): review of FINDING-004 and the rail

10. **FINDING-004 follow-up (high):** the no-WebGL image is a full-page screenshot of the OLD UI (old
    cards, `GET /api/radar`, a nested chat): in a demo it looks broken. Use a graph-only render: the
    canvas alone (for example `lake/views/temporal.png` from the smoke test if it shows only the graph,
    or a fresh headed-Chrome capture of just the graph element at the default lens), cropped to the
    graph, with the legend. Verified by the orchestrator in a Chrome window without WebGL.
11. **FINDING-002 follow-up (medium):** the rail's one-line reason still shows internal terms
    ("z_7d 13.5, cuota 7d ..."). Show a plain reason instead, e.g. "Crece 10x frente a la semana pasada"
    or the decision's plain sentence; keep the raw line in the detail and "Detalles técnicos".
