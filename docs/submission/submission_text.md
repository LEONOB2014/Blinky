# Texto de la entrega (borrador)

Borrador para la entrega de las 11:30. Cifras refrescadas desde sus fuentes el 2026-10-18 a las
07:50 UTC-5. La revisión humana del filtro no llegó: se cita el panel de modelos y se dice que sigue
pendiente. Cada cifra lleva su fuente en el repo; antes de enviar, verificar las que cambian con
`make demo-check` y `scripts/showcase_stories.py`.

---

## Radar de Señal Temprana · 30X

**Qué tema de IA está por llegar a LinkedIn en español, por qué, y desde qué ángulo emocional contarlo
a ejecutivos de LatAm. Solo con fuentes públicas.**

El gancho de arriba se queda. `reports/backtest.md` no deja abrir con la etiqueta principal
(pageviews de Wikipedia en español y portugués, coincidencias exactas, 43 semanas): la ventaja del
radar publicado sobre el crecimiento del conteo crudo no se sostiene en el peor caso (−14,3 puntos,
intervalo −20,2 .. −8,6). El adelanto mediano de 3,0 semanas (intervalo 2,0 .. 4,0, 47 positivos)
es de la etiqueta secundaria, crecimiento de artículos de GDELT en español y portugués, no de
Wikipedia.

- Sitio: https://radar-senal-temprana.netlify.app
- Código: https://github.com/LEONOB2014/Blinky

### Qué hace

Cada semana el radar puntúa los temas de IA de las noticias globales y muestra los 10 con más prioridad.
En la semana 2026-W42 puntuó 430 temas (medido, `topic_scores_weekly`). Cada tarjeta dice:

- en qué **etapa** está el tema (semilla, emergente…) y cuánto se ha **saturado**;
- la **ventana**: cuánto falta para que llegue al español y al portugués. Es una estimación hecha con
  el desfase mediano inglés → español/portugués medido en temas del mismo subtema;
- el **encaje** con la audiencia de 30X y el **ángulo emocional** para contarlo (alerta, oportunidad,
  giro, explicador);
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
