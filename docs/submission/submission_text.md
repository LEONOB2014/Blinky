# Texto de la entrega (borrador)

Borrador para la entrega de las 11:30. Los huecos `[PENDIENTE: …]` se llenan cuando lleguen los números
(backtest 05:00; P/R del filtro revisado por humanos 06:30). Cada cifra lleva su fuente en el repo;
antes de enviar, verificar las que cambian con `make demo-check` y `scripts/showcase_stories.py`.

---

## Radar de Señal Temprana · 30X

**Qué tema de IA está por llegar a LinkedIn en español, por qué, y desde qué ángulo emocional contarlo
a ejecutivos de LatAm. Solo con fuentes públicas.**

[PENDIENTE: frase de gancho según el backtest. Si la mediana de adelanto es de al menos 1 semana con
intervalo por encima de cero: "El radar marca temas N semanas antes de que crezca la atención en
Wikipedia en español (medido, n semanas)". Si no, se queda la frase de arriba.]

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

Un chat con agentes (el Maestro de Medios y sus especialistas) responde preguntas sobre la semana. El
código calcula cada decisión y el modelo solo la explica. El Auditor rechaza cualquier número que no
venga de una herramienta, y la traza de cada respuesta es visible.

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
| Backtest (adelanto vs. atención en Wikipedia es/pt; precision@10) | [PENDIENTE: backtest] | `reports/backtest.md` |
| Filtro de IA revisado por humanos (precisión / recall) | [PENDIENTE: P/R humano, 06:30] | `reports/label_quality.md` |
| Filtro de IA contra el panel de modelos (prueba congelada, n = 800) | F1 0,964 [0,947; 0,979] (medido; referencia = etiquetas del panel, no humanas) | `reports/label_quality.md` |
| Costo de BigQuery | [actualizar: 376,83 GB facturados en 63 trabajos a la 01:10 (medido)] | `reports/bq_ledger.csv` |
| Sitio y API en vivo | [actualizar: 8/8 PASS con latencias] | `status/WS9.md` (`make demo-check`) |

Dónde no hay señal, se dice. En la semana 2026-W42, 5 de los 10 temas del top se sostienen en un solo
patrón de co-mención (copia sindicada de agencia). Solo 2 de 10 muestran ya un onset en
español/portugués en 12 semanas (medido, `docs/submission/stories.md`; se regenera con cada
recálculo).

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
