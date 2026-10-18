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
- **Frase** (gancho de reserva; `reports/backtest.md` no deja usar el resultado principal):
  la etiqueta principal es el crecimiento de pageviews de Wikipedia en español y portugués, solo
  coincidencias exactas, 43 semanas evaluables. El radar publicado no le gana al crecimiento del
  conteo crudo en el peor caso (−14,3 puntos, intervalo −20,2 .. −8,6). Por eso no se abre con
  esa cifra. El adelanto mediano de 3,0 semanas (intervalo 2,0 .. 4,0, 47 positivos marcados) es
  de la etiqueta secundaria, el crecimiento de artículos de GDELT en español y portugués, no de
  Wikipedia, así que no llena la frase de adelanto en Wikipedia.
  - Decir: "Qué tema de IA está subiendo esta semana, por qué y desde qué ángulo contarlo, solo
    con fuentes públicas".
- **Si falla:** si la página no carga, abrir el video en el minuto del gancho; si solo falla la
  frescura, decir la fecha de los datos desde `status/WS9.md`.

## 2. Top 10 de la semana (0:30-1:45)

- **Qué hacer:** bajar al "Top 10 semanal"; señalar en la tarjeta #1 las fichas una por una.
- **Qué aparece:** 10 tarjetas de la última semana puntuada (hoy 2026-W42) con etapa, ventana,
  emergencia, saturación, encaje LatAm, ángulo emocional, decisión (preparar/esperar…) y los "por qué".
- **Frase:** "Cada semana el radar ordena unos 430 temas de IA en 2026-W42 (medido,
  `status/WS4.md`: 430 temas puntuados) y muestra diez. Cada ficha dice si está medida o es
  estimación. Esta ventana, por ejemplo, es la estimación de cuántos días faltan para que el tema
  llegue al español, a partir del desfase medido en temas parecidos."
- **Qué decir con honestidad:** `stories.md` (generado 2026-10-18 06:41 UTC, semana 2026-W42) mide
  1 de 10 temas del top con la semana sostenida por un solo patrón de co-mención (concentración
  ≥ 90%) y 1 de 10 con onset en español o portugués en 12 semanas. Si preguntan, decirlo: "esta
  semana 1 de 10 es ráfaga de una sola fuente; por eso las historias usan los otros".
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
  - Backtest (`reports/backtest.md`, medido): "En Wikipedia en español y portugués, coincidencias
    exactas, 43 semanas: el radar publicado acierta 119 de 408 casillas etiquetadas, 29,2%,
    intervalo 24,4 a 34,0, cobertura 408 de 440. El conteo crudo acierta 120 de 378, 31,7%. La
    persistencia, 77 de 426, 18,1%. La tasa base es 1036 de 4085, 25,4%. En el peor caso el radar
    le gana a la persistencia, más 6,4 puntos, intervalo 0,7 a 12,0, y no le gana al conteo crudo.
    El guardia de sindicación baja la precisión etiquetada de 135 de 403, 33,5%, a 119 de 408,
    29,2%. En el crecimiento de noticias en español y portugués, 43 semanas y 430 casillas, el
    radar acierta 57 de 430, 13,3%, intervalo 9,5 a 17,2, frente a una base de 1076 de 15959,
    6,7%, una persistencia de 55 de 430, 12,8%, y un conteo crudo de 1 de 430, 0,2%. El adelanto
    mediano ahí es 3,0 semanas, intervalo 2,0 a 4,0, sobre 47 positivos. La diferencia contra la
    persistencia es 0,5 puntos, intervalo −3,7 a 4,9: no le gana a las dos líneas base."
  - Filtro de IA: no hay precisión ni recall revisados por personas. Las 300 etiquetas humanas
    siguen pendientes (referencia: panel de modelos; verificación humana pendiente). Contra ese
    panel, en la prueba congelada (n = 800) lightgbm tiene precisión 0,9641 [0,9333; 0,9810],
    recall 0,9641 [0,9333; 0,9810] y F1 0,9641 [0,9474; 0,9794]. En las 300 filas de oro, el
    alumno tiene precisión 0,9432 [0,8738; 0,9755] y recall 0,9540 [0,8877; 0,9820]
    (`reports/label_quality.md`, medido).
  - Costo: "Todos los trabajos de BigQuery del proyecto suman 380,75 GB decimales
    (380.749.479.936 bytes facturados en 66 trabajos, medido en `reports/bq_ledger.csv`). El
    registro de Jev suma 981 llamadas y 0,04428430 USD (`reports/jev_ledger.csv`, medido)." Si el
    chat da otra cifra, decir la del chat y que el registro es el corte de este archivo.
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

El backtest ya está en el bloque 4, con denominadores. La revisión humana del filtro no está: se
dice el panel de modelos y que la verificación humana sigue pendiente. No decir ninguna cifra que
no esté en `stories.md`, en `status/` o en los reportes de `reports/`.
