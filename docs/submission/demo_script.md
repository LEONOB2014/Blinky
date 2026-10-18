# Guion de la demo (5 minutos, v0.3)

Sitio público: https://radar-senal-temprana.netlify.app (la API en vivo está detrás; si cae, el sitio
lee su copia estática y todo funciona salvo el chat).

**Lo que pide el reto, en el orden de la demo.** El jurado lee la entrega contra el reto: cómo
descubrir, de forma confiable y sin gastar una fortuna, qué temas despegan, por qué funcionan y si
encajan con la audiencia. Cada bloque responde una parte, con la fuerza honesta de su respuesta
(detalle y fuentes en `submission_text.md`, "Lo que pide el reto y lo que responde el radar"):

| Pregunta del reto | Bloque | Qué se muestra | Fuerza de la respuesta |
|---|---|---|---|
| El entregable: "los 10 temas de IA que más crecen esta semana, por qué y cómo lo adaptamos" | 2 | "Despegando" y "Lo más grande", con sus "por qué", familia, ángulo y la línea de la comunidad | Respondida, aguas arriba de LinkedIn: 10/10 temas de IA en W41 y W42 (medido) |
| 1. ¿Cómo se detecta una tendencia cuando apenas empieza a crecer? | 2 y 4 | Emergencia, ventana y el backtest de IA | La lista es relevante; el backtest no supera al azar: 25,6% frente a una base de 25,4% (medido) |
| 2. ¿Por qué funcionó: gancho, formato, tema, momento, autor? | 3 | Tono y ángulo, lentes Familia y Postura, comunidad IA, etapa y ventana | Respondida para el tema; para la pieza, solo en parte: la hoja manual de 30X tiene 0 filas (medido) |
| 3. ¿Cómo se filtra lo relevante para ejecutivos de LatAm que aprenden IA? | 2 y 3 | El léxico de IA, encaje (regla v1, estimación), ángulo y la cobertura en español y portugués escrita por código | Respondida con reglas de código; revisión humana del filtro pendiente |
| Sin gastar una fortuna | 4 | El costo de BigQuery, Jev y los modelos | Unos pocos dólares en total (estimado), frente a "miles de dólares al año" |

**La pantalla:** todo cabe en una sola vista.

- **Arriba:** el título, el selector de semana, el botón **Confianza**, la frescura y la leyenda
  medido / estimado.
- **A la izquierda:** las dos listas, con los botones **Despegando** (el top 10 por emergencia) y
  **Lo más grande** (por volumen).
  - Un clic en una tarjeta la abre con sus fichas, la familia, la línea **Comunidad IA**, **Brief** y
    **Evidencia** (cerrados) y la serie diaria por idioma.
- **En el centro:** el grafo de los temas de IA en GPU, con **▶ Reproducir 13 semanas** y
  **Pantalla completa (F)**. Tiene 10 lentes:
  - Radar, Historia, Puente, Momento, Novedad, Comunidades, Emoción, Ventana;
  - **Familia** (las 11 familias del léxico);
  - **Postura** (promotores frente a críticos).
- **Abajo a la derecha:** la píldora **Pregúntale al Maestro de Medios**, que abre el chat.

**Antes de empezar (T-15 min):**

1. Correr `make demo-check` (lecturas, sin costo; por defecto `RADAR_SOURCE=ai`, así que exige un top
   10 de temas `ai:`) y, una sola vez, `make demo-check ARGS=--chat`. Todo debe dar PASS. La última
   corrida está en `status/WS9.md`.
2. Regenerar las historias:
   `RADAR_SOURCE=ai RADAR_PROFILE=full uv run python scripts/showcase_stories.py`.
   - Regenera `stories.md` con el top 10 de IA vigente; el `stories.md` actual es de v0.2.
   - Los temas y cifras que se dicen en voz alta salen de ese archivo y de `submission_text.md`, no
     de este guion.
3. **Confianza:** comprobar si la respuesta de confianza y el panel ya leen `reports/backtest_ai.md`.
   Hoy (`agents/trust.py`, `agents/tools.get_backtest` y `deploy/evidence.py`) leen
   `reports/backtest.md`, el de v0.2 (29,2%). Si no está arreglado, en el bloque 4 decir las cifras de
   IA de este guion y presentar las del panel como la comparación con v0.2.
4. Abrir el sitio en Chrome con ventana visible (nunca headless: el grafo usa WebGL), a 1440x900 o
   más.
5. El chat tiene un límite de 10 preguntas cada 10 minutos por visitante (y 500 al día). No ensayar
   desde la misma red en los 10 minutos previos.
6. **Brief** y **Evidencia** se quedan cerrados, y no se pregunta por la lista de artículos: muestran
   titulares de noticias.
7. Plan B a mano: el video grabado (`video_plan.md`) y los GIF y capturas de `docs/media/`.

| Tiempo | Bloque |
|---|---|
| 0:00-0:30 | 1. Gancho: el radar ahora es de IA |
| 0:30-1:45 | 2. Despegando y Lo más grande |
| 1:45-3:00 | 3. Por qué: Familia, Postura y la comunidad IA |
| 3:00-4:00 | 4. Confianza y costo |
| 4:00-5:00 | 5. Cierre: 13 semanas |

---

## 1. Gancho (0:00-0:30)

- **Qué hacer:** la vista inicial, sin tocar nada.
- **Qué aparece:** el título, la frescura, la lista "Despegando" a la izquierda y el grafo de temas de
  IA en el centro.
- **Frase:** "Qué tema de IA está subiendo esta semana, por qué y desde qué ángulo contarlo, solo con
  fuentes públicas. En la versión anterior el top 10 eran bancos y supermercados: GDELT no reconoce a
  OpenAI como organización (`org:openai` no existe en todo el año, medido). Ahora el radar puntúa
  110 temas de IA curados, incluida la oposición a la IA, y el top 10 es 10 de 10 de IA."
- **Si falla:** si la página no carga, abrir el video en el minuto del gancho.

## 2. Despegando y Lo más grande (0:30-1:45)

- **Qué hacer:**
  1. Con **Despegando** activo, hacer clic en la tarjeta #1 y señalar sus fichas: familia, etapa,
     ventana, ángulo, decisión y la línea **Comunidad IA**.
  2. Pulsar **Lo más grande**.
- **Qué aparece:**
  - en Despegando, el top 10 por emergencia de 2026-W42, cada ficha marcada medida (●) o estimada
    (○);
  - en Lo más grande, los temas con más artículos de la semana, cada uno con su puesto en
    emergencia ("Despegando: #58" para OpenAI).
- **Frase:** "Dos listas, porque un editor necesita las dos. Lo más grande de 2026-W42 es Nvidia, con
  4.718 artículos, OpenAI con 2.691, Microsoft, Google, Anthropic, los agentes y ChatGPT (medido, 6 días
  con datos). Pero OpenAI va en el puesto 58 de lo que despega: lo que despega es otra cosa. Esta
  semana despegan las alianzas y adquisiciones, Google DeepMind, la bolsa de IA, los fichajes entre
  laboratorios y, ojo, las protestas y los artistas contra la IA."
- **Si falla:** si la API no responde, el sitio cambia solo a la copia estática; seguir igual. Si Lo
  más grande no aparece en la copia estática, decir las cifras de la frase.

## 3. Por qué: Familia, Postura y la comunidad IA (1:45-3:00)

- **Qué hacer:**
  1. Lente **Familia** (2 s) y luego **Postura**.
  2. Abrir la píldora y preguntar: "¿Qué está discutiendo la comunidad IA esta semana?".
  3. Preguntar: "¿Qué dicen los críticos de la IA esta semana?". El grafo pasa a la lente **Postura**.
- **Qué aparece:**
  - en Postura, los promotores y los críticos como dos campos del grafo;
  - en el chat, primero la línea que escribe el código: "La comunidad IA esta semana (…; señal no
    validada: no entra en el backtest): investigación … publicaciones sobre … temas; …" o "Los
    críticos de la IA esta semana …";
  - después, la explicación corta del modelo y la traza: cada paso, la herramienta y la verificación
    del Auditor.
- **Frase:** "Además de las noticias, el radar escucha a la comunidad IA: 3.636 publicaciones de
  23 fuentes públicas, papers, constructores, aceleradoras como Y Combinator y los críticos (medido). Es
  una señal sin validar y se dice así: no entra en el backtest. El código escribe las cifras, el
  modelo las explica y el Auditor rechaza cualquier número que no venga de los datos."
- **Con honestidad:** la señal de los críticos es pequeña: 45 publicaciones en 15 semanas (medido). Si
  la respuesta muestra pocos conteos, decirlo.
- **Si falla:** si el chat da 429 (límite) o 503, mostrar `docs/media/radar-chat.gif` y quedarse en la
  lente Postura.

## 4. Confianza y costo (3:00-4:00)

- **Qué hacer:**
  1. En el chat, preguntar: "¿Cuánto puedo confiar en el radar? ¿Hay backtest?".
  2. Pulsar **Confianza** para abrir el panel; **Ocultar confianza** lo cierra.
- **Qué aparece:** la respuesta calibrada, cuya línea de confianza escribe el código. Ver el punto 3 de
  "Antes de empezar": si todavía lee el backtest de v0.2, presentarla como la comparación.
- **Frases y cifras** (`reports/backtest_ai.md`, medido, 43 semanas):
  - **Etiqueta secundaria:** "La lista ahora es de IA, pero el backtest no le gana al azar. En el
    crecimiento de noticias en español y portugués, el top 10 acierta 110 de 430, 25,6%, intervalo
    22,3 a 28,8, frente a una base de 25,4%. Le gana a la persistencia, 12,3%, y no al conteo crudo,
    27,2%. El adelanto mediano es 2,0 semanas."
  - **Etiqueta principal:** "En Wikipedia, solo 27 de los 101 temas tienen artículo. La cobertura,
    89,5%, queda bajo la regla del 90%, así que damos cotas: 27,7% en casillas etiquetadas frente a
    26,5% de base. No se sostiene en el peor caso."
  - **Comparación con v0.2:** "v0.2 acertaba 29,2% frente a 25,4%, pero sobre una lista que no era de
    IA."
  - **Agentes** (`status/WS0-agents.md`, medido): "En 28 preguntas repetidas 3 veces, el anclaje a los
    datos es 0,964, entre 0,93 y 1,00 según la repetición."
  - **Costo:** "BigQuery: 389,72 GB en 74 trabajos (medido), 0 dólares dentro del nivel gratuito y
    2,21 a precio de lista (estimado). Jev: 981 llamadas, 0,044 dólares (medido). Modelos de lenguaje:
    unos 4,2 dólares (estimado). Ningún servicio de scraping."
- **Si falla:** las cifras están en este bloque; decirlas sin el chat.

## 5. Cierre: 13 semanas (4:00-5:00)

- **Qué hacer:**
  1. Lente **Radar**, **Pantalla completa (F)** y **▶ Reproducir 13 semanas**.
  2. Salir con Esc y hacer clic en la tarjeta #1: lente **Historia**.
- **Qué aparece:** el grafo de co-menciones entre temas de IA semana a semana, y el #1 con sus vecinos
  de 1 salto.
- **Frase:** "Esto es lo que el radar ve debajo de las tarjetas: cómo se arma la conversación de IA
  semana a semana, quién la promueve y quién se opone."
- **Si falla:** reproducir `docs/media/radar-play.gif` o el bloque 5 del video.

---

No decir ninguna cifra que no esté en `submission_text.md`, `stories.md` (regenerado), `status/` o
`reports/`. La revisión humana del filtro no está: se dice el panel de modelos y que la verificación
humana sigue pendiente.
