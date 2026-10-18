# Fact sheet for the v0.4 demo video (the ONLY source of numbers and claims)

Every number is measured unless marked (estimate). Do not add numbers, names or claims that are not here.

## Who
- Presenter: Andrés Leonardo Becerra López, AI Engineer. LinkedIn: linkedin.com/in/andres-leonardo-becerra-lopez-01a01995
- Team name: Equipo Blinky. Mascot: Blinky, an AI-generated robot avatar with a "Blinka Task" badge.
- Challenge: Reto 30X "Radar de Contenido". Live app: radar-senal-temprana.netlify.app

## The problem (30X's own framing)
- 30X's media team decides which AI topics to cover for LatAm executives.
- Paid social-scraping services cost thousands of dollars a year and answer only half the question: data, but not
  why something works, whether a trend is starting or already copied, or whether it fits the audience.
- 30X's example question: "¿cuáles son los 10 temas de IA que más están creciendo esta semana en LinkedIn, por qué y
  cómo lo adaptamos?"

## The key insight (the presenter's plan)
- AI topics for executives do not originate on LinkedIn. They surface first in supply-side and technical sources
  (arXiv/Hugging Face papers, GitHub, Hacker News, X), then in news (GDELT), then in search and reference attention
  (Google Trends, Wikipedia; Spanish later than English), and only then become LinkedIn carousels and Instagram reels.
- A radar that watches the open, upstream layers and measures how far each topic has travelled down that chain can
  say what is about to land on LinkedIn, not what landed last week.
- LinkedIn/Instagram are used only through sanctioned channels: 30X's own analytics, the Instagram Graph API for
  public business/creator accounts, and a community-as-sensor loop. LinkedIn bans automated collection; the radar
  never scrapes it.
- What the radar watches TODAY: GDELT news, Wikipedia pageviews in Spanish and Portuguese, and an AI community sensor
  (3,636 items from 25 public sources over 13 weeks: Hugging Face papers and model releases, AI Engineer, Y Combinator,
  The Batch, practitioner newsletters, safety and critic organisations). GitHub, Hacker News, X and Google Trends are
  in the plan, not yet built.

## GDELT (public facts from GDELT's own documentation)
- GDELT monitors the world's news media in print, broadcast and web form; its Global Knowledge Graph (GKG) extracts,
  for every article, the people, organisations, places, themes and the TONE of the article.
- GDELT 2.0 updates every 15 minutes and translates news in 65 languages in real time.
- It is open data, queryable in Google BigQuery.

## GDELT in this project (measured)
- Window: 2025-11-01 to 2026-10-18, 51 weeks.
- 4,031,651 AI-related articles classified in three rings; 1,623,903 in the AI ring.
- Cost: BigQuery 389.7 GB billed over 74 jobs, $0 inside the monthly free tier (about $2.2 at list price, estimate).
- Value: tone and polarity per article and per topic and day; co-mentions between topics; timing per language
  (when a topic explodes in English and has not reached Spanish yet).

## From news to content (how the radar uses the graph and the tone)
- Ranked unit: a curated lexicon of 110 AI topics in 11 families (labs and models, products, techniques such as
  agents, RAG and open weights, infrastructure, research, business, policy, safety, and the opposition to AI).
- Weekly co-mention graph: 105 topics, 13 weeks; in 2026-W42, 86 topics and 147 links. Links weighted by NPMI
  (how much more often two topics appear together than by chance).
- One-hop ring of each topic: its strongest neighbours that week (at least 3 shared articles, NPMI above 0.1, top 20),
  so you see what a topic connects to and which articles back it.
- Graph heuristics: PageRank (importance), k-core, Leiden communities (7 communities), bridges between sectors
  ("Puente" lens), new links ("Novedad"), acceleration ("Momento").
- Tone: GDELT gives each article's tone; the radar computes, per topic and week, the emotional charge (extremity,
  polarity, controversy, tone shift) and picks the framing angle: Alerta/riesgo, Oportunidad, Debate, Giro or
  Explicador neutral.
- "Postura" lens: promoters vs critics of AI, so the opposing camp is visible.
- For each topic the card says: emergence percentile, stage, saturation, the window (estimated days until it lands in
  Spanish), audience fit (rule v1, estimate), the angle, a decision (publicar ahora / preparar / esperar) computed by
  code, a Spanish brief, the evidence (up to 5 articles), and what the AI community says.

## The app (what the clips show)
- "Despegando": the emergence top 10, the AI topics rising faster than their own history. Week 2026-W42 #1:
  "Alianzas y adquisiciones en IA"; #2 Google DeepMind; #3 "Bolsa y acciones de IA".
- "Lo más grande": the week's leaders by volume. W42: Nvidia 4,718 articles, OpenAI 2,691, Microsoft IA 2,153,
  Google IA 2,116, Anthropic 1,938.
- The graph plays 13 weeks; 10 lenses: Radar, Historia, Puente, Momento, Novedad, Comunidades, Emoción, Ventana,
  Familia, Postura.
- Media Master chat: 8 agents on Qwen3-30B (Nebius). Code writes the facts, the model explains them, an Auditor checks
  every number. Release eval (28 questions x 3): grounding 0.964 (0.93-1.00); decisions and routing 1.000.
- Trust panel: the backtest says honestly that the ranking is relevant but not yet better than chance on its labels
  (secondary label 25.6% vs base 25.4%); it is an early signal, not a guarantee.

## Engineering (measured)
- End-to-end browser matrix: 130 of 130 lens x week cells pass; 13 weeks play at 116-121 fps.
- Deployed on Google Cloud Run and Netlify; traces in LangSmith; CI on every PR; secrets in Secret Manager.
- Browsers without WebGL2 get a fallback image instead of a blank canvas.

## Cost and the ask
- Cloud Run about $13 a month with a warm instance (estimate); chat about $0.001 per answer (estimate);
  Jev $0.044 for 981 calls (measured); Netlify and LangSmith on free tiers.
- The ask: a 4-week pilot with 30X's media team. They read the weekly radar and share their own post analytics, so the
  audience fit learns from what actually performs for their followers.
