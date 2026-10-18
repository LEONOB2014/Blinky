# Guion de la demo (5 minutos)

Sitio público: https://radar-senal-temprana.netlify.app (la API en vivo está detrás; si cae, el sitio
lee su copia estática y todo funciona salvo el chat).

**Lo que pide el reto, en el orden de la demo.** El jurado lee la entrega contra el reto: cómo
descubrir, de forma confiable y sin gastar una fortuna, qué temas despegan, por qué funcionan y si
encajan con la audiencia. Cada bloque responde una parte, con la fuerza honesta de su respuesta
(detalle y fuentes en `submission_text.md`, "Lo que pide el reto y lo que responde el radar"):

| Pregunta del reto | Bloque | Qué se muestra | Fuerza de la respuesta |
|---|---|---|---|
| El entregable: "los 10 temas de IA que más crecen esta semana, por qué y cómo lo adaptamos" | 2 | El top 10 de la semana con sus "por qué" y el ángulo | Respondida, aguas arriba de LinkedIn: mide noticias globales, no LinkedIn |
| 1. ¿Cómo se detecta una tendencia cuando apenas empieza a crecer? | 2 y 4 | Emergencia, ventana y el backtest | Adelanto mediano 3,0 semanas (2,0 .. 4,0); acierta 29,2% frente a 25,4% de base; le gana a la persistencia, no al conteo crudo (medido) |
| 2. ¿Por qué funcionó: gancho, formato, tema, momento, autor? | 3 y 5 | Tono y ángulo, conexiones del grafo, evidencia, etapa y ventana | Respondida para el tema; para la pieza, solo en parte: la hoja manual de las publicaciones de 30X lo cierra y hoy tiene 0 filas (medido) |
| 3. ¿Cómo se filtra lo relevante para ejecutivos de LatAm que aprenden IA? | 2 y 3 | Encaje (regla v1, estimación), ángulo, la línea de cobertura en español y portugués y la auditoría de LatAm | Respondida con reglas de código; la prueba ciega del editor está lista y sin respuestas |
| Sin gastar una fortuna | 4 | El costo de BigQuery, Jev y los modelos | Unos pocos dólares en total (estimado), frente a "miles de dólares al año" |

**La pantalla:** todo cabe en una sola vista.

- Arriba: el título, el selector de semana, el botón **Confianza**, la frescura ("Datos al …",
  semanas, solo fuentes públicas) y la leyenda medido / estimado.
- A la izquierda: el **Top 10 semanal**. Un clic en una tarjeta la abre con sus fichas, **Brief** y
  **Evidencia** (cerrados) y la serie diaria por idioma.
- En el centro: el grafo de la semana en GPU, con **▶ Reproducir 13 semanas**, **Pantalla completa (F)**
  y las 8 lentes:
  - **Radar** (decisión);
  - **Historia** (anillos);
  - **Puente** (conexión entre sectores);
  - **Momento** (aceleración);
  - **Novedad** (enlaces nuevos);
  - **Comunidades** (Leiden);
  - **Emoción** (tono);
  - **Ventana** (horizonte).
- Abajo a la derecha: la píldora **Pregúntale al Maestro de Medios**, que abre el chat.

**Antes de empezar (T-15 min):**

1. `make demo-check` (lecturas, sin costo) y, una sola vez, `make demo-check ARGS=--chat`. Todo debe
   dar PASS. El resultado de la última corrida está en `status/WS9.md`.
2. `RADAR_PROFILE=full uv run python scripts/showcase_stories.py`: regenera `stories.md` con el top
   10 vigente. Los temas y cifras que se dicen en voz alta salen de ese archivo, no de este guion.
3. Abrir el sitio en Chrome con ventana visible (nunca headless: el grafo usa WebGL), a 1440x900 o
   más. Una sola pestaña basta.
4. El chat tiene un límite de 10 preguntas cada 10 minutos por visitante (y 500 al día en total). No
   ensayar las preguntas del chat en los 10 minutos previos desde la misma red.
5. **Brief** y **Evidencia** se quedan cerrados, y no se pregunta por la lista de artículos:
   muestran titulares de noticias.
6. Plan B a mano: el video grabado (`video_plan.md`) y los GIF y capturas de `docs/media/`.
7. El encuadre del grafo después de una respuesta del chat y la lente Historia con los vecinos
   nombrados llegan con el arreglo `fix/ws5-dock-badge-fit`. Comprobar que está desplegado; si no,
   la Historia se acerca a un solo nodo sin nombres: en el bloque 5, quedarse en el barrido.

| Tiempo | Bloque |
|---|---|
| 0:00-0:30 | 1. Gancho |
| 0:30-1:45 | 2. Top 10 de la semana |
| 1:45-3:00 | 3. Por qué, cómo adaptarlo y las lentes |
| 3:00-4:00 | 4. Confianza |
| 4:00-5:00 | 5. Cierre: 13 semanas e historia del #1 |

---

## 1. Gancho (0:00-0:30)

- **Qué hacer:** la vista inicial, sin tocar nada.
- **Qué aparece:** "Radar de Señal Temprana · 30X", la frescura de los datos, el top 10 a la
  izquierda y el grafo de la semana en el centro, coloreado por decisión.
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

- **Qué hacer:** hacer clic en la tarjeta #1 del top 10 y señalar sus fichas una por una.
- **Qué aparece:**
  - 10 tarjetas de la última semana puntuada (hoy 2026-W42), cada una con emergencia, ventana,
    ángulo y decisión (preparar, esperar…);
  - en la tarjeta abierta: etapa, ventana, emergencia, saturación, encaje LatAm, ángulo emocional
    y los "por qué" de la decisión, cada ficha marcada como medida (●) o estimada (○);
  - el grafo cambia a la lente **Historia** con el tema y sus vecinos de 1 salto.
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

## 3. Por qué, cómo adaptarlo y las lentes (1:45-3:00)

- **Qué hacer:**
  1. Abrir la píldora **Pregúntale al Maestro de Medios** y preguntar: "¿Cuál es el ángulo para
     ejecutivos de LatAm esta semana?".
  2. Preguntar: "Muéstrame el grafo de la semana". El grafo vuelve a la lente **Radar**, encuadrado
     y con los nombres del top 10.
  3. Recorrer las lentes con un clic cada una, unos 2 s por lente: **Momento**, **Puente**,
     **Comunidades**, **Novedad**. Si sobra tiempo, **Emoción** y **Ventana**.
- **Qué aparece:**
  - en la respuesta, primero las líneas que escribe el código y el modelo no puede cambiar:
    "Decisión del radar: …" y la cobertura en español y portugués ("… artículos en español y …
    en portugués, de …");
  - luego la explicación del modelo, con las tarjetas de decisión y la traza de agentes (cada paso,
    la herramienta, la latencia y la verificación del Auditor);
  - en cada lente, el mismo grafo coloreado por otra señal; la leyenda de abajo dice qué significa
    cada color.
- **Frase:** "El código decide y el modelo explica: la decisión, la cobertura y la evidencia las
  escribe el código, cada número de la respuesta viene de una herramienta, y el Auditor rechaza
  cualquier cifra que no esté en los datos. Aquí está la traza."
- **Si falla:**
  - si el chat da 429 (límite), decir el límite y mostrar `docs/media/radar-chat.gif`;
  - si da 503 o se cae, la API no tiene clave o está caída: usar el GIF. Las lentes, la serie y el
    anillo funcionan desde la copia estática;
  - si la insignia "Powered by Netlify" tapa la píldora, hacer clic en el texto visible de la
    píldora, a la izquierda de la insignia.

## 4. Confianza (3:00-4:00)

- **Qué hacer:**
  1. En el chat, preguntar: "¿Cuánto puedo confiar en el radar? ¿Hay backtest?".
  2. Pulsar **Confianza** (arriba a la derecha) para abrir el panel con el backtest y la calidad del
     filtro; **Ocultar confianza** lo cierra.
  3. Si sobra tiempo, preguntar: "¿Qué tan frescos están los datos y cuánto ha costado en
     BigQuery?".
- **Qué aparece:** la respuesta calibrada. Su línea de confianza la escribe el código a partir de
  `reports/backtest.md`: el top 10 publicado acierta el 29,2% de las veces (intervalo del 95%: 24,4%
  a 34,0%), frente a un 25,4% de un tema al azar; supera a la persistencia incluso en el peor caso y
  no supera a la regla simple de crecimiento de menciones (31,7%). Las etiquetas humanas del filtro
  siguen pendientes. Cierra con "Úsalo como señal temprana, no como garantía."
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
  - Agentes (`status/WS0-agents.md`, medido): "En 25 preguntas repetidas 3 veces, 72 de 75
    respuestas tienen cada número anclado a los datos (0,960, entre 0,92 y 1,00 según la
    repetición), con utilidad 0,750. Después de calibrar la respuesta de confianza, 'puedes
    confiar' aparece en 0 de 75 respuestas, frente a 3 de 75 antes."
  - Filtro de IA: no hay precisión ni recall revisados por personas. Las 300 etiquetas humanas
    siguen pendientes (referencia: panel de modelos; verificación humana pendiente). Contra ese
    panel, en la prueba congelada (n = 800) lightgbm tiene precisión 0,9641 [0,9333; 0,9810],
    recall 0,9641 [0,9333; 0,9810] y F1 0,9641 [0,9474; 0,9794]. En las 300 filas de oro, el
    alumno tiene precisión 0,9432 [0,8738; 0,9755] y recall 0,9540 [0,8877; 0,9820]
    (`reports/label_quality.md`, medido).
  - Costo: "Todos los trabajos de BigQuery del proyecto suman 384,35 GB decimales
    (384.346.095.616 bytes facturados en 69 trabajos, medido en `reports/bq_ledger.csv`): 0 dólares
    dentro del nivel gratuito, 2,18 a precio de lista (estimado). El registro de Jev suma 981
    llamadas y 0,04428430 USD (`reports/jev_ledger.csv`, medido). Los modelos de lenguaje, unos 3,7
    dólares registrados (estimado). El reto habla de miles de dólares al año en scraping; aquí no hay
    ningún servicio de scraping." Si el chat da otra cifra, decir la del chat y que el registro es el
    corte de este archivo.
  - Fuentes: "Solo fuentes públicas: GDELT en BigQuery, Wikipedia y Wikidata, y la analítica propia de
    30X. LinkedIn no se toca nunca."
- **Si falla:** las cifras están en este bloque; decirlas sin el chat. El panel **Confianza** lee
  los reportes y no depende del modelo.

## 5. Cierre: 13 semanas e historia del #1 (4:00-5:00)

- **Qué hacer:**
  1. Lente **Radar**, **Pantalla completa (F)** y **▶ Reproducir 13 semanas**.
  2. Salir con Esc y hacer clic en la tarjeta #1: lente **Historia**.
- **Qué aparece:**
  - en el barrido, el grafo de co-menciones de noticias de IA semana a semana: el tamaño del nodo es
    su importancia de esa semana y los temas puntuados van coloreados por decisión. El primer cuadro
    tardó 0,55 s con WebGL (ANGLE Metal) en el ensayo de las 07:15 UTC-5 (medido, `status/WS9.md`);
  - en la historia, el tema #1 encuadrado con sus vecinos de 1 salto y sus nombres.
- **Frase:** "Esto es lo que el radar ve debajo de las tarjetas: cómo se arma la conversación semana a
  semana, y para el tema #1, con qué se conecta."
- **Si falla:** reproducir `docs/media/radar-play.gif` (el barrido) o el bloque 5 del video. Si
  tampoco hay video, cerrar en las tarjetas con la frase del gancho.

---

El backtest y la evaluación de los agentes ya están en el bloque 4, con denominadores. La revisión
humana del filtro no está: se dice el panel de modelos y que la verificación humana sigue pendiente.
No decir ninguna cifra que no esté en `stories.md`, en `status/` o en los reportes de `reports/`.
