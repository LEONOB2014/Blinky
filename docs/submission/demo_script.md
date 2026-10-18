# Guion de la demo (5 minutos)

Sitio público: https://radar-senal-temprana.netlify.app (la API en vivo está detrás; si cae, el sitio
lee su copia estática y todo funciona salvo el chat).

**Antes de empezar (T-15 min):**

1. `make demo-check` (lecturas, sin costo) y, una sola vez, `make demo-check ARGS=--chat`. Todo debe
   dar PASS. El resultado de la última corrida está en `status/WS9.md`.
2. `RADAR_PROFILE=full uv run python scripts/showcase_stories.py`: regenera `stories.md` con el top
   10 vigente. Los temas y cifras que se dicen en voz alta salen de ese archivo, no de este guion.
3. Abrir en Chrome con ventana visible (nunca headless, el grafo usa WebGL):
   - pestaña 1: el sitio público;
   - pestaña 2: la vista temporal, `lake/views/temporal.html` servida en local con
     `cd lake/views && python -m http.server 8765` (luego `http://localhost:8765/temporal.html`);
   - pestaña 3: la vista de historia del #1 (`story.html` en el mismo servidor).
4. El chat tiene un límite de 10 preguntas cada 10 minutos por IP. No ensayar las preguntas del chat en
   los 10 minutos previos desde la misma red.
5. Plan B a mano: el video grabado (`video_plan.md`) y las capturas en `lake/demo/` (fuera de git).

| Tiempo | Bloque |
|---|---|
| 0:00-0:30 | 1. Gancho |
| 0:30-1:45 | 2. Top 10 de la semana |
| 1:45-3:00 | 3. Por qué y cómo adaptarlo |
| 3:00-4:00 | 4. Confianza |
| 4:00-5:00 | 5. Cierre: grafo temporal e historia del #1 |

---

## 1. Gancho (0:00-0:30)

- **Qué hacer:** pestaña 1, arriba de la página (título y frescura de datos).
- **Qué aparece:** "Radar de Señal Temprana · 30X", las fechas de frescura por tabla y el perfil
  `full`.
- **Frase** (elegir según el backtest, `[PENDIENTE: backtest]`, llega 05:00):
  - si la mediana de adelanto medida es de al menos 1 semana con intervalo por encima de cero:
    "El radar marca temas [PENDIENTE: N] semanas antes de que crezca la atención en Wikipedia en
    español (medido sobre [PENDIENTE: n] semanas)".
  - si no: "Qué tema de IA está subiendo esta semana, por qué y desde qué ángulo contarlo a
    ejecutivos de LatAm, solo con fuentes públicas".
- **Si falla:** si la página no carga, abrir el video en el minuto del gancho; si solo falla la
  frescura, decir la fecha de los datos desde `status/WS9.md`.

## 2. Top 10 de la semana (0:30-1:45)

- **Qué hacer:** bajar al "Top 10 semanal"; señalar en la tarjeta #1 las fichas una por una.
- **Qué aparece:** 10 tarjetas de la última semana puntuada (hoy 2026-W42) con etapa, ventana,
  emergencia, saturación, encaje LatAm, ángulo emocional, decisión (preparar/esperar…) y los "por qué".
- **Frase:** "Cada semana el radar ordena unos [de `stories.md`: 430 en 2026-W42] temas de IA y
  muestra diez. Cada ficha dice si está medida o es estimación. Esta ventana, por ejemplo, es la
  estimación de cuántos días faltan para que el tema llegue al español, a partir del desfase medido en
  temas parecidos."
- **Qué decir con honestidad:** `stories.md` tiene el diagnóstico de los 10: cuántos se sostienen en
  un solo patrón de co-mención (copia sindicada) y cuáles tienen ya onset en español. Si preguntan,
  decirlo: "esta semana N de 10 son ráfagas de una sola fuente; por eso las historias usan los otros".
- **Si falla:** si la API no responde, el sitio cambia solo a la copia estática (mismo top 10,
  comprobado por `make demo-check`); seguir igual.

## 3. Por qué y cómo adaptarlo (1:45-3:00)

- **Qué hacer:**
  1. Elegir la historia 1 de `stories.md` en el selector de la serie y del anillo de contexto.
  2. En el chat, preguntar: "¿Cuál es el ángulo para ejecutivos de LatAm esta semana?".
  3. Si sobra tiempo, preguntar: "Prepara un guion de 30 a 45 segundos en español sobre [tema de la
     historia 1]".
- **Qué aparece:**
  - la serie diaria por idioma del tema;
  - el anillo de 1 salto (vecinos, co-menciones n, NPMI);
  - la respuesta del Maestro de Medios con tarjetas de decisión y la traza de agentes (cada paso, la
    herramienta, la latencia y la verificación del Auditor).
- **Frase:** "El código decide y el modelo explica: cada número de la respuesta viene de una
  herramienta, y el Auditor rechaza cualquier cifra que no esté en los datos. Aquí está la traza."
- **Si falla:** si el chat da 429 (límite), decir el límite y mostrar la captura del chat ensayado;
  si da 503 o se cae, la API no tiene clave o está caída: usar la captura. La serie y el anillo
  funcionan desde la copia estática.

## 4. Confianza (3:00-4:00)

- **Qué hacer:** en el chat, preguntar: "¿Qué tan frescos están los datos y cuánto ha costado en
  BigQuery?"; luego mostrar las cifras de esta tabla (diapositiva o pantalla).
- **Qué aparece:** frescura por tabla y el costo acumulado del registro de BigQuery.
- **Frases y cifras:**
  - Backtest: "[PENDIENTE: backtest: adelanto mediano, precision@10, intervalos, n]".
  - Filtro de IA: "[PENDIENTE: P/R del filtro revisado por humanos, 06:30]". Si no llega a tiempo,
    decir lo que hay y contra qué: F1 0.964 en la partición de prueba congelada (n = 800), medido
    contra etiquetas del panel de modelos maestros, no humanas (`reports/label_quality.md`).
  - Costo: "Todos los trabajos de BigQuery del proyecto, incluido el historial del 1 de noviembre de
    2025 al 18 de octubre de 2026, suman [cifra del chat] GB facturados". A la 01:10 eran 376,83 GB
    en 63 trabajos (medido en `reports/bq_ledger.csv`); decir la cifra actualizada que dé el chat.
  - Fuentes: "Solo fuentes públicas: GDELT en BigQuery, Wikipedia y Wikidata, y la analítica propia de
    30X. LinkedIn no se toca nunca."
- **Si falla:** las cifras están en esta tabla; decirlas sin el chat.

## 5. Cierre: grafo temporal e historia del #1 (4:00-5:00)

- **Qué hacer:**
  1. Pestaña 2 (vista temporal): darle play a las 13 semanas.
  2. Pestaña 3 (vista de historia del #1).
- **Qué aparece:**
  - en la vista temporal, el grafo de co-menciones de noticias de IA, semana a semana. El tamaño del
    nodo es su PageRank de esa semana y los temas puntuados van coloreados por decisión. Medido por
    WS3 en Chrome visible: la exportación completa reproduce el barrido a unos 107 fps.
  - en la vista de historia, el tema #1 en el centro con su anillo de vecinos y las aristas entre
    ellos.
- **Frase:** "Esto es lo que el radar ve debajo de las tarjetas: cómo se arma la conversación semana a
  semana, y para el tema #1, quién lo empuja."
- **Si falla:** reproducir el clip grabado del barrido (bloque 5 del video). Si tampoco hay video,
  cerrar en las tarjetas con la frase del gancho.

---

Huecos que se llenan cuando llegan los números: `[PENDIENTE: backtest]` (05:00) y
`[PENDIENTE: P/R del filtro revisado por humanos]` (06:30). No decir ninguna cifra que no esté en
`stories.md`, en `status/` o en los reportes de `reports/`.
