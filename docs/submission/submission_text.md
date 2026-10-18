# Texto de la entrega (borrador)

Borrador para la entrega de las 11:30. Cifras refrescadas desde sus fuentes el 2026-10-18 a las
07:50 UTC-5. La revisión humana del filtro no llegó: se cita el panel de modelos y se dice que sigue
pendiente. Cada cifra lleva su fuente en el repo; antes de enviar, verificar las que cambian con
`make demo-check` y `scripts/showcase_stories.py`.

---

## Radar de Señal Temprana · 30X

**Qué tema de IA está por llegar a LinkedIn en español, por qué, y desde qué ángulo emocional contarlo
a ejecutivos de LatAm. Solo con fuentes públicas.**

- Sitio: https://radar-senal-temprana.netlify.app
- Código: https://github.com/LEONOB2014/Blinky

### Lo que pide el reto y lo que responde el radar

El reto pregunta cómo un equipo de contenido puede descubrir, de forma confiable y sin gastar una
fortuna, qué temas y formatos están despegando en redes, por qué funcionan y si encajan con su
audiencia. Hoy eso depende de servicios de scraping pagados que cuestan miles de dólares al año y
responden la mitad. Estas son las tres preguntas del reto, con la fuerza honesta de cada respuesta.

**1. ¿Cómo se detecta una tendencia cuando apenas está empezando a crecer?**

- **Qué hace el radar:** cada tema tiene un puntaje de **emergencia**, el percentil esa semana de su
  volumen inesperado, su crecimiento, su aceleración y sus vecinos nuevos en el grafo (medido). También
  tiene una **ventana**, la estimación de cuántos días faltan para que llegue al
  español y al portugués. La ventana sale del desfase mediano inglés → español/portugués medido en
  temas del mismo subtema.
- **Qué tan bien funciona** (`reports/backtest.md`, medido, 43 semanas):
  - en el crecimiento de artículos en español y portugués, el radar marca los temas con un adelanto
    mediano de **3,0 semanas** (intervalo 2,0 .. 4,0, 47 positivos);
  - en la etiqueta principal (pageviews de Wikipedia en español y portugués), el top 10 publicado
    acierta el **29,2%** de las veces (119/408, intervalo 24,4% .. 34,0%), frente a una tasa base de
    **25,4%**;
  - le gana a la persistencia (repetir lo que ya subió) incluso en el peor caso, +6,4 puntos
    (0,7 .. 12,0). **No le gana** al crecimiento del conteo crudo: −14,3 puntos (−20,2 .. −8,6) en
    el peor caso.
- **Lectura:** es una señal temprana mejor que el azar y que la persistencia, no una garantía. Por eso
  el radar lo dice en cada respuesta de confianza.

**2. ¿Cómo se explica por qué una pieza funcionó: el gancho, el formato, el tema, el momento, quién la
publicó?**

- **Respondido para el tema:** por qué sube un tema y cuándo contarlo.
  - **Crecimiento:** la serie diaria por idioma y la emergencia.
  - **Tono y ángulo emocional:** una regla de código sobre el tono de las noticias elige alerta,
    oportunidad, debate, giro o explicador.
  - **Conexiones:** el anillo de 1 salto en el grafo de co-menciones (con quién aparece el tema y con
    qué fuerza, NPMI) y las lentes Puente y Novedad.
  - **Evidencia:** hasta 5 artículos por tema y semana, con cuántos artículos y de cuántos medios
    (1.191 artículos, 0 duplicados, medido).
  - **Momento:** la etapa, la saturación y la ventana.
- **Solo en parte para la pieza:** el gancho, el formato y el autor de una publicación concreta no se
  pueden leer en las noticias, y el radar no toca LinkedIn. El brief en español de cada tema, escrito
  por el modelo, propone un gancho y un formato (carrusel, video corto, post de texto o newsletter), y
  la evidencia nombra los medios, nunca personas. Eso propone, pero no mide qué pieza funcionó.
- **Cómo se cierra:** con la hoja manual de las publicaciones públicas de 30X (`pipelines/social/`).
  - Una persona anota de cada publicación el formato, la fecha, la cuenta y las reacciones, comentarios
    y compartidos que la plataforma muestra en público. No hay automatización.
  - El importador valida la hoja y calcula el engagement por cada 1.000 seguidores.
  - El paso siguiente cruza cada publicación con lo que el radar decía de su tema esa semana.
  - La hoja y el importador están hechos y probados, pero la hoja tiene 0 publicaciones hoy (medido):
    esta parte espera los datos de 30X.

**3. ¿Cómo se filtra lo que es relevante para una audiencia concreta, como ejecutivos y equipos de
Latinoamérica aprendiendo IA?**

- **Filtro de IA:** un modelo alumno separa las noticias de IA. Contra el panel de modelos tiene
  precisión 0,9641 en la prueba congelada (n = 800, medido); la revisión humana sigue pendiente.
- **Encaje con la audiencia:** un puntaje por tema (regla v1, estimación) que combina el subtema y el
  peso de LatAm o del español y el portugués en la cobertura del tema. Entra en la prioridad que
  ordena el top 10. Una prueba ciega del editor (`reports/editor_test.md`, 20 temas) está lista para
  medirlo; aún no tiene respuestas.
- **Ángulo:** el ángulo emocional de cada tema, para contarlo a ejecutivos.
- **Cobertura en español y portugués escrita por código:** cada respuesta del chat sobre un tema trae
  la línea "Cobertura en español y portugués de …: N artículos en español y M en portugués, de T". El
  modelo no la puede cambiar.
- **Auditoría de LatAm:** si esa línea da 0 artículos en español y portugués, el Auditor marca
  cualquier frase que diga que el tema crece o está presente en Latinoamérica y añade una advertencia
  (determinista, en código).

**El entregable de ejemplo:** "¿cuáles son los 10 temas de IA que más están creciendo esta semana en
LinkedIn, por qué y cómo lo adaptamos?".

- El radar entrega cada semana los 10 temas de IA con más prioridad, con sus "por qué" marcados como
  medidos o estimados, el ángulo y un brief en español para adaptarlos.
- No mide el crecimiento dentro de LinkedIn. Mide el de las noticias globales antes de que el tema
  llegue al español (ver "Por qué miramos aguas arriba de LinkedIn").

**El costo:** unos pocos dólares en total, no miles al año (ver "Sin gastar una fortuna").

### Sin gastar una fortuna

El reto compara con servicios de scraping que cuestan miles de dólares al año. Lo que costó el radar,
de punta a punta:

| Qué | Costo | Fuente |
|---|---|---|
| BigQuery (GDELT, 69 trabajos) | **0 USD** dentro del nivel gratuito de 1 TiB al mes (estimado): se facturaron 0,35 TiB, todos en octubre de 2026 (medido). A precio de lista, 6,25 USD por TiB, serían **2,18 USD** (estimado) | `reports/bq_ledger.csv` |
| Jev (casos dudosos del filtro) | **0,044 USD**, 981 llamadas (medido) | `reports/jev_ledger.csv` |
| Modelos de lenguaje en Nebius | Unos **3,7 USD** registrados (estimado desde los tokens medidos). Etiquetado con el panel de modelos: unos 2,30 USD. Corridas de evaluación y pruebas de los agentes con estimación registrada: unos 1,37 USD. Comprobaciones del chat en vivo: menos de 0,05 USD. Las evaluaciones anteriores a las 05:05 UTC-5 del 18 de octubre no tienen estimación registrada (unos 0,2 USD por evaluación completa, estimado) | `reports/label_quality.md`, `status/WS2.md`, `status/WS0-agents.md`, `status/WS9.md` |
| Servicio de scraping | **0 USD**: no se usa ninguno | — |

Cada trabajo de BigQuery pasa por un dry run y un tope de gasto antes de correr, y cada llamada
a Jev queda en su registro.

### Por qué miramos aguas arriba de LinkedIn

LinkedIn prohíbe la recolección automática en su acuerdo de usuario, así que el radar no lo toca.
En su lugar mira la cadena abierta que viene antes: GDELT, que según su propia documentación sigue
noticias de todo el mundo en 65 idiomas. Lo que se valida es si un tema marcado gana atención de
referencia después, en las pageviews de Wikipedia en español y portugués. LinkedIn solo se observa a
través de la analítica propia de 30X, anotada a mano y con su permiso.

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

Cada semana el radar puntúa los temas de IA de las noticias globales y muestra los 10 con más prioridad.
En la semana 2026-W42 puntuó 430 temas (medido, `topic_scores_weekly`). Cada tarjeta dice:

- en qué **etapa** está el tema (semilla, emergente…) y cuánto se ha **saturado**;
- la **ventana**: cuánto falta para que llegue al español y al portugués. Es una estimación hecha con
  el desfase mediano inglés → español/portugués medido en temas del mismo subtema;
- el **encaje** con la audiencia de 30X y el **ángulo emocional** para contarlo (alerta, oportunidad,
  debate, giro, explicador);
- la **decisión** (publicar, preparar, esperar…) con sus "por qué", cada uno marcado como medido o
  estimación.

Todo cabe en una pantalla: el top 10 a la izquierda y el grafo de la semana en el centro, con 8
lentes (Radar, Historia, Puente, Momento, Novedad, Comunidades, Emoción y Ventana). El chat vive en una
píldora abajo a la derecha, "Pregúntale al Maestro de Medios".

El chat con agentes (el Maestro de Medios y sus especialistas) responde preguntas sobre la semana y
mueve el grafo. El código calcula cada decisión y escribe por su cuenta las líneas que importan: la
decisión del radar, la cobertura en español y portugués, la evidencia (cuántos artículos y de cuántos
medios) y, si se pregunta por confianza, la precisión del backtest con su intervalo. El modelo solo
explica. El Auditor rechaza cualquier número que no venga de una herramienta y marca las frases de
confianza sin matiz. La traza de cada respuesta es visible.

### Cómo

1. **Datos:** GDELT GKG 2.0 en BigQuery, del 1 de noviembre de 2025 al 18 de octubre de 2026.
   - 4.031.651 artículos clasificados en tres anillos (`status/WS1.md`, medido): IA (1.623.903),
     TI y tecnología (contexto) y dominios con empresas tecnológicas (contexto).
   - Solo se puntúa el anillo de IA.
   - Cada trabajo de BigQuery pasa por un dry run y un tope de gasto, y queda en
     `reports/bq_ledger.csv`.
2. **Etiquetas:** un panel de modelos con licencia abierta etiqueta una muestra estratificada. Un
   modelo alumno calibrado filtra el resto (`reports/label_quality.md`).
3. **Señales:** series diarias por tema e idioma, con ventanas de 7 días ajustadas por día de la
   semana. Los días sin datos de la fuente quedan vacíos, nunca en cero.
4. **Grafo:** co-menciones semanales con NPMI, el anillo de 1 salto de cada tema y métricas de nodo
   (PageRank, comunidades Leiden).
5. **Puntuación:** seis puntajes, la ventana y una regla de decisión por código.
6. **Agentes:** Qwen3-30B (Nebius) con herramientas sobre el lake, con trazas y evaluación.
7. **Despliegue:**
   - la API (FastAPI sobre DuckDB) corre en Google Cloud Run, con límite de uso del chat;
   - la interfaz corre en Netlify, con una copia estática que funciona si la API cae.

### La evidencia

| Qué | Resultado | Fuente |
|---|---|---|
| Backtest, etiqueta principal: pageviews de Wikipedia es+pt, coincidencias exactas, 43 semanas (2025-W49 a 2026-W39). Precisión@10 en casillas etiquetadas | Radar publicado 119/408 = 29,2% (intervalo bootstrap 95% por semanas 24,4% .. 34,0%); cobertura 408/440 = 92,7%; peor caso 27,0%, mejor caso 34,3%. Conteo crudo 120/378 = 31,7% (26,8% .. 37,0%); peor 27,3%, mejor 41,4%. Persistencia 77/426 = 18,1% (14,8% .. 21,3%); peor 17,5%, mejor 20,7%. Tasa base 1036/4085 = 25,4%. Peor caso del radar menos mejor caso del conteo crudo: −14,3 puntos (−20,2 .. −8,6), no se sostiene. Peor caso del radar menos mejor caso de la persistencia: +6,4 puntos (0,7 .. 12,0), se sostiene. Sin el guardia de sindicación la precisión etiquetada es 135/403 = 33,5%: el guardia cuesta precisión en esta etiqueta. No hay adelanto medido en Wikipedia | `reports/backtest.md` |
| Backtest, etiqueta secundaria: crecimiento de artículos GDELT es+pt, 43 semanas, cobertura 430/430 | Radar publicado 57/430 = 13,3% (9,5% .. 17,2%). Tasa base 1076/15959 = 6,7%. Persistencia 55/430 = 12,8% (9,1% .. 17,0%). Conteo crudo 1/430 = 0,2% (0,0% .. 0,7%). Diferencia contra la persistencia: 0,5 puntos (−3,7 .. 4,9): no le gana a las dos líneas base. Adelanto mediano 3,0 semanas (2,0 .. 4,0) sobre 47 positivos marcados, de la primera marca al pico dentro de 8 semanas | `reports/backtest.md` |
| Filtro de IA revisado por humanos (precisión / recall) | Verificación humana pendiente. Las 300 filas de `lake/labels/gold_sheet.csv` aún no tienen la etiqueta de la persona. Referencia: panel de modelos | `reports/label_quality.md` |
| Filtro de IA contra el panel de modelos (prueba congelada, n = 800) | lightgbm, calibración isotónica: precisión 0,9641 [0,9333; 0,9810], recall 0,9641 [0,9333; 0,9810], F1 0,9641 [0,9474; 0,9794] (medido; referencia = etiquetas del panel, no humanas) | `reports/label_quality.md` |
| El mismo filtro en las 300 filas de oro, contra el panel y no contra personas | Alumno: precisión 0,9432 [0,8738; 0,9755], recall 0,9540 [0,8877; 0,9820], F1 0,9486 [0,9166; 0,9773] (n = 300, medido) | `reports/label_quality.md` |
| Costo de BigQuery | 384,35 GB decimales (384.346.095.616 bytes facturados en 69 trabajos, medido) | `reports/bq_ledger.csv` |
| Costo de Jev | 981 llamadas, 0,04428430 USD acumulados (medido) | `reports/jev_ledger.csv` |
| Evaluación de los agentes (25 preguntas × 3 repeticiones = 75 corridas, lago completo) | Último experimento completo, `trust-calibration`: anclaje a los datos (grounding) 0,960 [0,92; 1,00], utilidad v2 0,750 [0,74; 0,76], utilidad v1 0,707 [0,69; 0,73], enrutamiento 1,000, 6.358 tokens por turno (medido; entre corchetes, mínimo y máximo de las 3 repeticiones). "Puedes confiar" aparece en 0 de 75 respuestas, frente a 3 de 75 antes de la calibración (medido). Evaluación de la versión v0.2.0: anclaje 1,000 (75/75), utilidad v2 0,663 [0,63; 0,70] (medido) | `status/WS0-agents.md` |
| Evidencia de los temas | 1.191 artículos, hasta 5 por tema y semana: 240 pares tema-semana, 212 temas, 8 semanas. 0 duplicados por título normalizado (medido el 2026-10-18) | `topic_evidence_weekly` en el lake; `pipelines/ingest/evidence_titles.py` |
| Sitio y API en vivo | Redespliegue del 2026-10-18 a las 07:15 UTC-5 (revisión 00007): `make demo-check` 7/7, con chat 8/8 (un turno de chat 12,4 s), y 5 de 5 preguntas de chat cumplen lo esperado (medido). Desde las 07:35 UTC-5 la API tiene una instancia siempre encendida (min-instances = 1, revisión 00008), así que no hay arranque en frío. Comprobación de las 07:49 UTC-5, 7/7 (medido, segundos en el portátil, red incluida): página 0,75 s, top 10 estático 0,23 s, frescura 0,71 s (la primera petición; con min-instances = 0 el arranque en frío medido fue 5,37 s), top 10 de la API 0,79 s, igualdad con el estático 0,00 s, serie del primero 0,66 s, anillo de 1 salto 0,74 s | `status/WS9.md` (`make demo-check`) |

Dónde no hay señal, se dice. En la semana 2026-W42, 1 de 10 temas del top se sostiene en un solo
patrón de co-mención (copia sindicada de agencia) y 1 de 10 muestra ya un onset en
español o portugués en 12 semanas (medido, `docs/submission/stories.md`, generado 2026-10-18
06:41 UTC; se regenera con cada recálculo).

### Fuentes y términos de uso

Solo fuentes públicas: GDELT (BigQuery, datos abiertos), Wikipedia y Wikidata, y la analítica propia de
30X. LinkedIn nunca se toca. No se guardan titulares, URLs ni nombres de personas en el repositorio:
las personas nunca se puntúan y se excluyen de los grafos que se sirven.

### Stack

- Datos: Python 3.12, uv, BigQuery, DuckDB, Polars, Parquet.
- Modelos: scikit-learn y LightGBM; igraph y Leiden para el grafo.
- API e interfaz: FastAPI; React y Vite.
- Grafo en GPU: cosmos.gl y sigma.js.
- Agentes: Qwen3-30B en Nebius, trazas en LangSmith.
- Despliegue: Google Cloud Run y Netlify.
- Calidad: contratos JSON Schema, pre-commit y Conventional Commits.
