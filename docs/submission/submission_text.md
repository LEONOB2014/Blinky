# Texto de la entrega (v0.3, borrador)

Borrador para la entrega de las 11:30. Cifras refrescadas desde sus fuentes el 2026-10-18 a las
10:30 UTC-5. Cada cifra lleva su fuente en el repo y dice si es medida o estimada. Antes de enviar,
verificar las que cambian con `make demo-check` (por defecto `RADAR_SOURCE=ai`) y con
`RADAR_SOURCE=ai RADAR_PROFILE=full uv run python scripts/showcase_stories.py`. La revisión humana
del filtro no llegó: se cita el panel de modelos y se dice que sigue pendiente.

---

## Radar de Señal Temprana · 30X

**Qué tema de IA está por llegar a LinkedIn en español, por qué, y desde qué ángulo emocional contarlo
a ejecutivos de LatAm. Solo con fuentes públicas.**

- Sitio: https://radar-senal-temprana.netlify.app
- Código: https://github.com/LEONOB2014/Blinky

### Qué cambió en v0.3 y por qué

**El top 10 de v0.2 no era de IA.** En la semana 2026-W42 lo encabezaban Marsh McLennan, Rocket Lab,
Kroger y Comcast.

- **La causa (medida en el lake):** el radar puntuaba las organizaciones que GDELT extrae de los
  artículos de IA, y GDELT no reconoce a las organizaciones nativas de IA.
  - `org:openai` no existe en todo el año. Solo aparecen variantes como "openai foundation"
    (1.154 artículos) u "openai group" (624), medido en `topic_daily`.
  - El universo era de bancos, energía y comercio que salen en noticias de IA.
- **El arreglo:** la unidad que se puntúa ahora es un **léxico curado de IA**, `ai:<id>`
  (`contracts/ai_lexicon.yaml`).
  - Son **110 temas en 11 familias:** laboratorios, modelos, productos, técnicas, infraestructura y
    chips, investigación, negocio, regulación, seguridad, **oposición y crítica**, y sociedad y
    trabajo.
  - Cada tema tiene una postura: 64 promotores, 28 neutrales y **18 críticos**. La oposición a la IA
    es parte del radar, no un ruido.
  - El léxico se cruza con el título y la URL de cada artículo de IA en BigQuery. GDELT sigue dando el
    tono, la emoción, el momento y el desfase hacia el español.
- **Resultado (medido):** **10 de 10 temas de IA** en el top 10 de 2026-W41 y en el de 2026-W42
  (`topic_ai_scores_weekly`).

### Dos listas: lo que despega y lo más grande

- **"Despegando"** es el top 10 por emergencia: lo que sube más de lo esperado, antes de saturarse.
  En 2026-W42 (medido):
  - Alianzas y adquisiciones en IA · Google DeepMind · Bolsa y acciones de IA;
  - Fichajes, salidas y spin-offs en los laboratorios · Protestas y rechazo social a la IA ·
    Artistas y creadores contra la IA;
  - Rondas y valuaciones de IA · Ajuste fino y entrenamiento · Pesos abiertos y open source ·
    Robótica e IA física.
- **"Lo más grande"** es la lista por volumen de artículos de la semana, en todos los idiomas, con los
  días sin datos fuera. 2026-W42 tiene 6 días con datos (medido, `/api/leaders`):
  - Nvidia 4.718 · OpenAI 2.691 · Microsoft IA 2.153 · Google IA 2.116 · Anthropic 1.938 ·
    Agentes de IA 996 · ChatGPT 929.
- **Por qué son dos:** la emergencia oculta a los gigantes por diseño (OpenAI va en el puesto 58 de
  emergencia, medido). Un editor necesita las dos: lo grande para no perderse lo obvio, y lo que
  despega para llegar antes.

### El sensor de la comunidad IA

Qué publican quienes trabajan en IA, separado de las noticias (`crosssource/community.py`,
`community_topic_weekly`):

- **Fuentes:** 23 fuentes públicas, todas con publicaciones (medido).
  - investigación: papers y modelos de Hugging Face;
  - práctica: boletines de practicantes, W&B, podcasts;
  - construcción: AI Engineer, Y Combinator y sus Requests for Startups, CoreWeave;
  - visión, medios (The Batch);
  - críticos: FLI, CAIS, AI Now, MIRI y boletines críticos.
- **Volumen:** **3.636 publicaciones** en 15 semanas, 2026-W28 a 2026-W42 (medido a las 10:26
  UTC-5; el sensor sigue sumando). Por categoría: investigación 2.593, construcción 621, práctica
  162, medios 120, visión 95 y críticos 45.
- **Cómo se usa:**
  - cada tarjeta trae una línea "Comunidad IA" con sus conteos;
  - el chat responde "¿qué discute la comunidad IA?" y "¿qué dicen los críticos?" con una línea
    escrita por el código.
- **Con honestidad:** es una **señal no validada**. La mayoría de las fuentes guarda poco historial,
  así que nunca entra en el backtest. Los títulos se quedan en el lake: el radar solo muestra
  conteos.

### Lo que pide el reto y lo que responde el radar

El reto pregunta cómo un equipo de contenido puede descubrir, de forma confiable y sin gastar una
fortuna, qué temas y formatos están despegando en redes, por qué funcionan y si encajan con su
audiencia. Hoy eso depende de servicios de scraping pagados que cuestan miles de dólares al año y
responden la mitad. Estas son las tres preguntas del reto, con la fuerza honesta de cada respuesta.

**1. ¿Cómo se detecta una tendencia cuando apenas está empezando a crecer?**

- **Qué hace el radar:** cada tema tiene un puntaje de **emergencia**, el percentil esa semana de su
  volumen inesperado, su crecimiento, su aceleración y sus vecinos nuevos en el grafo de IA (medido).
  También tiene una **ventana**, la estimación de cuántos días faltan para que llegue al español y al
  portugués, a partir del desfase medido en temas de la misma familia.
- **Qué tan bien funciona** (`reports/backtest_ai.md`, medido, 43 semanas, 101 temas de IA):
  - **La lista ahora es relevante, pero el backtest no muestra más acierto que el azar.**
  - En el crecimiento de artículos en español y portugués (etiqueta secundaria), el top 10 acierta el
    **25,6%** (110/430, intervalo 22,3% .. 28,8%), frente a una tasa base de **25,4%**.
  - Le gana a la persistencia (12,3%; diferencia +13,3 puntos, 9,1 .. 17,2). **No le gana** al
    crecimiento del conteo crudo (27,2%; diferencia −1,6 puntos, −5,6 .. 2,3).
  - Adelanto mediano de **2,0 semanas** (2,0 .. 3,0) sobre 91 positivos marcados.
  - En la etiqueta principal (pageviews de Wikipedia en español y portugués), solo 27 de los 101
    temas tienen artículo en Wikipedia. La cobertura (89,5%) queda bajo la regla del 90%, así que se
    reportan cotas:
    - acierto en casillas etiquetadas 27,7% (24,0% .. 31,2%), frente a una base de 26,5%;
    - en el peor caso no le gana ni al conteo crudo ni a la persistencia.
  - **Comparación con v0.2** (`reports/backtest.md`):
    - En la etiqueta principal v0.2 acertaba 29,2% (24,4% .. 34,0%) frente a 25,4%, y le ganaba a la
      persistencia en el peor caso.
    - En la secundaria acertaba 13,3% frente a una base de 6,7%. Esa base era baja porque, entre
      4.945 organizaciones, la mayoría no crece.
    - v0.2 tenía más señal sobre una lista que no era de IA. v0.3 tiene una lista de IA y, por ahora,
      no más señal que el azar.
- **Lectura:** el radar de IA es una lectura temprana ordenada y explicada, no un predictor probado.
  Lo dice en cada respuesta de confianza.

**2. ¿Cómo se explica por qué una pieza funcionó: el gancho, el formato, el tema, el momento, quién la
publicó?**

- **Respondido para el tema:** por qué sube un tema y cuándo contarlo.
  - **Crecimiento:** la serie diaria por idioma y la emergencia.
  - **Tono y ángulo emocional:** una regla de código sobre el tono de las noticias elige alerta,
    oportunidad, debate, giro o explicador.
  - **Conexiones:** el grafo de co-menciones entre temas de IA, con las lentes **Familia** y
    **Postura** (promotores frente a críticos).
  - **Evidencia y comunidad:** los artículos del tema con cuántos medios, y lo que publica la
    comunidad IA.
  - **Momento:** la etapa, la saturación y la ventana.
- **Solo en parte para la pieza:** el gancho, el formato y el autor de una publicación concreta no se
  pueden leer en las noticias, y el radar no toca LinkedIn. El brief en español de cada tema, escrito
  por el modelo y revisado por el Auditor, propone un gancho y un formato. Eso propone, pero no mide
  qué pieza funcionó.
- **Cómo se cierra:** con la hoja manual de las publicaciones públicas de 30X (`pipelines/social/`).
  La hoja y el importador están hechos y probados, pero la hoja tiene 0 publicaciones hoy (medido):
  esta parte espera los datos de 30X.

**3. ¿Cómo se filtra lo que es relevante para una audiencia concreta, como ejecutivos y equipos de
Latinoamérica aprendiendo IA?**

- **Qué es IA:** el léxico curado decide qué es un tema de IA. El filtro de artículos que alimenta
  el radar es la regla de GDELT: precisión 0,75 (0,66 .. 0,82) y recall 0,97 (0,90 .. 0,99) en 300
  noticias, contra el panel de modelos. El clasificador entrenado (precisión 0,94) está validado contra
  el panel, pero aún no alimenta el radar. La revisión humana sigue pendiente
  (`reports/label_quality.md`).
- **Encaje con la audiencia:** un puntaje por tema (regla v1, estimación) que combina la familia
  (negocio e inversión) y el peso de LatAm o del español y el portugués en la cobertura.
- **Cobertura en español y portugués escrita por código:** cada respuesta sobre un tema trae "N
  artículos en español y M en portugués, de T". El Auditor marca cualquier frase que diga que el tema
  crece en Latinoamérica si esa línea da 0.
- **Briefs coherentes:** si un brief dice "casi nadie lo cuenta en español" y sus propios datos dicen
  otra cosa, el código lo rechaza y, si persiste, escribe la cobertura medida. Los 20 briefs de W41 y
  W42 pasan el Auditor 20/20 (medido).

**El entregable de ejemplo:** "¿cuáles son los 10 temas de IA que más están creciendo esta semana en
LinkedIn, por qué y cómo lo adaptamos?".

- El radar entrega cada semana los 10 temas de IA que despegan y los más grandes, con sus "por qué"
  marcados como medidos o estimados, el ángulo, la línea de la comunidad y un brief en español.
- No mide el crecimiento dentro de LinkedIn. Mide el de las noticias globales y el de la comunidad IA
  antes de que el tema llegue al español (ver "Por qué miramos aguas arriba de LinkedIn").

**El costo:** unos pocos dólares en total, no miles al año (ver "Sin gastar una fortuna").

### Los agentes

El chat (el Maestro de Medios y sus especialistas, Qwen3-30B en Nebius) responde sobre la semana y
mueve el grafo. **El código decide y escribe las líneas que importan; el modelo solo explica.**

- **Líneas escritas por el código:**
  - la decisión del radar y "lo más grande de la semana";
  - la cobertura en español y portugués;
  - la evidencia (artículos y medios), cómo se arma el grafo y la comunidad IA;
  - y, si se pregunta por confianza, la calibración: acierto, intervalo, base y qué supera y qué no.
- **El Auditor** rechaza cualquier número que no venga de una herramienta. También marca las frases
  de confianza sin matiz, las afirmaciones sobre LatAm sin cobertura y los conteos de medios
  equivocados. La traza de cada respuesta es visible.
- **Evaluación de la versión v0.3** (`release-v0.3.0`, 28 preguntas × 3 repeticiones, medido;
  entre corchetes, mínimo y máximo de las 3 repeticiones):
  - anclaje a los datos (grounding) **0,964** [0,93; 1,00];
  - utilidad v2 0,619 [0,60; 0,64];
  - enrutamiento y decisiones 1,000.
  - Las 3 preguntas nuevas sobre la comunidad quedaron flojas en esa corrida. Tras dos arreglos
    llegan a utilidad v2 0,500 [0,42; 0,58], con anclaje 9/9 (medido). Están señaladas como el punto
    débil.

### Sin gastar una fortuna

El reto compara con servicios de scraping que cuestan miles de dólares al año. Lo que costó el radar,
de punta a punta:

| Qué | Costo | Fuente |
|---|---|---|
| BigQuery (GDELT y el léxico de IA, 74 trabajos) | **0 USD** dentro del nivel gratuito de 1 TiB al mes (estimado): se facturaron 389,72 GB, 0,35 TiB, todos en octubre de 2026 (medido). A precio de lista, 6,25 USD por TiB, serían **2,21 USD** (estimado) | `reports/bq_ledger.csv` |
| Jev (casos dudosos del filtro) | **0,044 USD**, 981 llamadas (medido) | `reports/jev_ledger.csv` |
| Modelos de lenguaje en Nebius | Unos **4,2 USD** registrados (estimado desde los tokens medidos): unos 3,7 USD hasta las 07:50 UTC-5, más unos 0,54 USD de los briefs y evaluaciones de v0.3. Las evaluaciones anteriores a las 05:05 UTC-5 no tienen estimación registrada | `status/WS0-agents.md`, `status/WS4.md`, `reports/label_quality.md` |
| Fuentes de la comunidad | **0 USD**: APIs y feeds públicos | `crosssource/community.py` |
| Servicio de scraping | **0 USD**: no se usa ninguno | — |

Cada trabajo de BigQuery pasa por un dry run y un tope de gasto antes de correr, y cada llamada a Jev
queda en su registro.

### Por qué miramos aguas arriba de LinkedIn

LinkedIn prohíbe la recolección automática en su acuerdo de usuario, así que el radar no lo toca.
En su lugar mira la cadena abierta que viene antes:

- GDELT, que según su propia documentación sigue noticias de todo el mundo en 65 idiomas;
- la comunidad IA, en sus APIs y feeds públicos.

Lo que se valida es si un tema marcado gana atención de referencia después, en Wikipedia y en las
noticias en español y portugués. LinkedIn solo se observa a través de la analítica propia de 30X,
anotada a mano y con su permiso.

### JEV

El reto sugiere a JEV como aliado, y el radar lo usa donde más rinde: en cascada.

- El modelo alumno clasifica cada noticia y solo manda a Jev los casos dudosos, con probabilidad
  entre 0,20 y 0,80. Eso es el 3,12% de las noticias (medido en validación).
- Costo: **0,0014 USD por cada 1.000 noticias** (medido), y 0,044 USD en total por 981 llamadas
  (medido, `reports/jev_ledger.csv`).
- **Con honestidad:** en los casos dudosos Jev acertó 9 de 10 frente a 7 de 10 del alumno, pero el
  intervalo (+0,00 .. +0,50) toca el cero. Los datos aún no prueban que Jev mejore el filtro.
  Mantenerlo para esos casos es una decisión de diseño, barata, no una mejora medida
  (`reports/label_quality.md`).

### Qué hace

Cada semana el radar puntúa los temas de IA del léxico y muestra dos listas: "Despegando" y "Lo más
grande". En 2026-W42 puntuó 76 temas con al menos 20 artículos (medido, `topic_ai_scores_weekly`).
Cada tarjeta dice:

- la **familia** y la **postura** del tema;
- en qué **etapa** está (semilla, emergente…) y cuánto se ha **saturado**;
- la **ventana**: cuánto falta para que llegue al español y al portugués (estimación);
- el **encaje** con la audiencia de 30X y el **ángulo emocional** para contarlo;
- la línea **Comunidad IA**;
- la **decisión** (publicar, preparar, esperar…) con sus "por qué", cada uno marcado como medido o
  estimación.

Todo cabe en una pantalla:

- a la izquierda, las dos listas;
- en el centro, el grafo de la semana con 10 lentes: Radar, Historia, Puente, Momento, Novedad,
  Comunidades, Emoción, Ventana, **Familia** y **Postura**;
- el chat vive en una píldora abajo a la derecha, "Pregúntale al Maestro de Medios".

### Cómo

1. **Datos:** GDELT GKG 2.0 en BigQuery, del 1 de noviembre de 2025 al 18 de octubre de 2026.
   - 1.623.903 artículos de IA (`status/WS1.md`, medido).
   - El léxico se cruza con su título y URL (`bq_sql/s15`, `s16`), y cada trabajo queda en
     `reports/bq_ledger.csv`.
2. **Léxico y comunidad:** 110 temas curados, sin personas. Las fuentes de la comunidad que llevan
   nombre de persona viven solo en el lake, fuera de git.
3. **Señales:** series diarias por tema e idioma, con ventanas de 7 días. Los días sin datos de la
   fuente quedan vacíos, nunca en cero.
4. **Grafo:** co-menciones semanales entre temas de IA con NPMI, el anillo de 1 salto y la nueva
   tasa de vecinos.
5. **Puntuación:** seis puntajes, la ventana y una regla de decisión por código, más la lista por
   volumen.
6. **Agentes:** Qwen3-30B (Nebius) con herramientas sobre el lake, trazas en LangSmith y evaluación
   congelada por versión (v1, v2, v3).
7. **Despliegue:**
   - la API (FastAPI sobre DuckDB) corre en Google Cloud Run, con límite de uso del chat;
   - la interfaz corre en Netlify, con una copia estática que funciona si la API cae.

### La evidencia

| Qué | Resultado | Fuente |
|---|---|---|
| Top 10 de IA | 10/10 temas de IA en 2026-W41 y en 2026-W42 (medido). En v0.2 eran organizaciones de finanzas, energía y comercio | `topic_ai_scores_weekly` |
| Backtest de IA, etiqueta secundaria: crecimiento de artículos GDELT es+pt, 43 semanas, cobertura 430/430 | Radar 110/430 = 25,6% (22,3% .. 28,8%). Tasa base 802/3152 = 25,4%. Conteo crudo 117/430 = 27,2% (23,3% .. 31,2%). Persistencia 53/430 = 12,3% (9,3% .. 15,6%). Contra el conteo crudo −1,6 puntos (−5,6 .. 2,3), no le gana; contra la persistencia +13,3 (9,1 .. 17,2), le gana. Adelanto mediano 2,0 semanas (2,0 .. 3,0), 91 positivos | `reports/backtest_ai.md` |
| Backtest de IA, etiqueta principal: pageviews de Wikipedia es+pt de los títulos del léxico (27 de 101 temas con artículo) | Cobertura 394/440 = 89,5%, bajo la regla del 90%: se dan cotas. Acierto en casillas etiquetadas 109/394 = 27,7% (24,0% .. 31,2%); peor caso 24,8%, mejor 35,2%. Tasa base 254/959 = 26,5%. En el peor caso no le gana al conteo crudo (−10,0 puntos, −13,6 .. −6,6) ni a la persistencia (+0,9, −4,5 .. 5,7) | `reports/backtest_ai.md` |
| Backtest de v0.2 (comparación) | Etiqueta principal 119/408 = 29,2% (24,4% .. 34,0%) frente a 25,4%; secundaria 57/430 = 13,3% frente a 6,7% (medido) | `reports/backtest.md` |
| Filtro de IA que alimenta el radar (regla de GDELT), contra el panel, 300 noticias | Precisión 0,75 (0,66 .. 0,82), recall 0,97 (0,90 .. 0,99). Clasificador entrenado: precisión 0,94, recall 0,95, validado pero no conectado. Revisión humana pendiente | `reports/label_quality.md` |
| Comunidad IA | 3.636 publicaciones de 23 fuentes públicas, 15 semanas (medido a las 10:26 UTC-5); señal no validada, fuera del backtest | `community_topic_weekly`, `crosssource/community.py` |
| Agentes, versión v0.3 (28 × 3) | Anclaje 0,964 [0,93; 1,00], utilidad v2 0,619 [0,60; 0,64], utilidad v1 0,658 [0,62; 0,69], enrutamiento 1,000 (medido) | `status/WS0-agents.md` |
| Agentes, versión v0.2 (25 × 3, comparación) | Anclaje 1,000, utilidad v2 0,663 [0,63; 0,70] (medido) | `status/WS0-agents.md` |
| Briefs de W41 y W42 | Auditor 20/20; 4 afirmaciones de cobertura corregidas por el código; 0 contradicciones restantes (medido) | `status/WS4.md` |
| Costo de BigQuery | 389,72 GB decimales en 74 trabajos (medido) | `reports/bq_ledger.csv` |
| Costo de Jev | 981 llamadas, 0,0443 USD (medido) | `reports/jev_ledger.csv` |

Dónde no hay señal, se dice: el backtest de IA no supera al azar, y la comunidad es una señal sin
validar.

### Fuentes y términos de uso

Solo fuentes públicas: GDELT (BigQuery, datos abiertos), Wikipedia y Wikidata, los feeds y APIs
públicos de la comunidad IA y la analítica propia de 30X. LinkedIn nunca se toca. No se guardan
titulares, URLs ni nombres de personas en el repositorio: las personas nunca se puntúan y se excluyen
de los grafos que se sirven.

### Stack

- Datos: Python 3.12, uv, BigQuery, DuckDB, Polars, Parquet.
- Modelos: scikit-learn y LightGBM; igraph y Leiden para el grafo.
- API e interfaz: FastAPI; React y Vite.
- Grafo en GPU: cosmos.gl y sigma.js.
- Agentes: Qwen3-30B en Nebius, trazas en LangSmith.
- Despliegue: Google Cloud Run y Netlify.
- Calidad: contratos JSON Schema, pre-commit y Conventional Commits.
