# Historias de muestra (showcase)

Generado por `scripts/showcase_stories.py` el 2026-10-18 06:41 UTC desde el lake completo (`topic_scores_weekly` hasta 2026-W42, `daily_topic` hasta 2026-10-18). Semana puntuada: **2026-W42**. Todas las cifras salen de las herramientas de los agentes (`agents/tools.py`); se regenera cada vez que WS4 recalcula.

Reglas (calculadas por código, no a mano):

- **Onset de un idioma:** primera semana de las últimas 12 con >= 5 artículos del anillo 1 en ese idioma y >= 3x la mediana de las semanas anteriores (las semanas sin artículos cuentan 0; los días `is_missing` quedan fuera). Si no hay, se dice: sin señal. Es una regla semanal de presentación; el chip de ventana usa la regla diaria de WS4 (`models/window.py`: onset = primer día con z_7d > 2).
- **Concentración:** artículos que co-mencionan al vecino más fuerte del anillo / artículos del tema esa semana. >= 90% indica que un solo patrón de co-mención (típicamente copia sindicada de agencia) sostiene la semana: se marca y no se elige como historia.
- **Historias:** los 3 temas mejor puestos de la semana sin esa marca.

## Diagnóstico del top 10

| Puesto | Tema | Etapa | Decisión | Artículos semana | Concentración | Onset EN | Onset ES/PT | Historia |
|---|---|---|---|---|---|---|---|---|
| 1 | `org:marsh mclennan` | semilla | preparar | 44 | 66% | 2026-W42 | — | sí |
| 2 | `org:rocket lab` | emergente | esperar | 23 | 13% | 2026-W31 | — | sí |
| 3 | `org:national stock exchange` | emergente | preparar | 24 | 62% | 2026-W33 | — | sí |
| 4 | `org:university college london` | emergente | preparar | 23 | 57% | 2026-W31 | — |  |
| 5 | `org:citigroup` | emergente | esperar | 149 | 57% | 2026-W31 | 2026-W39 |  |
| 6 | `org:sandisk` | emergente | esperar | 107 | 14% | 2026-W31 | — |  |
| 7 | `org:comcast` | emergente | preparar | 52 | 40% | 2026-W31 | — |  |
| 8 | `org:kroger` | emergente | preparar | 201 | 93% ⚠ | 2026-W31 | — |  |
| 9 | `org:founders fund` | emergente | esperar | 20 | 60% | 2026-W37 | — |  |
| 10 | `org:sb energy` | emergente | esperar | 28 | 29% | 2026-W31 | — |  |

Lectura honesta (medido): 1 de 10 temas tienen una semana sostenida por un solo patrón de co-mención (⚠); 1 de 10 muestran onset en español/portugués en 12 semanas. Donde no hay onset en español, la ventana del chip es la estimación del modelo (desfase típico medido sobre otros temas), no una observación de este tema.

## 1. Marsh & McLennan Companies (`org:marsh mclennan`), puesto #1

- **Etapa y decisión:** semilla, **preparar** (prioridad 0.60; emergencia percentil 92, medido).
- **Subtemas:** Inversión y mercados, Chips e infraestructura.
- **Ventana (chip):** `sin_estimacion`; desfase típico inglés→español/portugués 14.5 días (mediana de 46 pares de onsets de temas con el mismo subtema principal, medido por WS4).
- **Onset en inglés:** 2026-W42; **onset en español/portugués:** sin onset en 12 semanas (sin señal).
- **Ángulo emocional:** Explicador neutral (carga emocional sin dato esta semana).
- **Concentración de la semana:** 66% de sus 44 artículos co-mencionan al vecino más fuerte (medido).

**Serie semanal (artículos del anillo 1, medido):**

| Semana | W35 | W36 | W37 | W38 | W39 | W40 | W41 | W42 |
|---|---|---|---|---|---|---|---|---|
| Total | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 44 |
| Inglés | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 44 |
| Español + portugués | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Aristas que lo impulsan (anillo de 1 salto, semana 2026-W42, medido):**

| # | Vecino | Co-menciones (n) | NPMI |
|---|---|---|---|
| 1 | `thm:WB_1649_UNEMPLOYMENT_BENEFITS` | 29 | 0.876 |
| 2 | `thm:WB_752_CONTRIBUTORY_BENEFITS` | 29 | 0.856 |
| 3 | `thm:UNGP_SUPPORT_FOR_PEOPLE_WHO_CANT_WORK` | 29 | 0.833 |
| 4 | `thm:NATURAL_DISASTER_DROWN` | 15 | 0.785 |
| 5 | `thm:WB_751_SOCIAL_INSURANCE` | 29 | 0.762 |

**Por qué (del Analista de señales, texto generado por código):**

- Decisión: preparar (regla 4: emergencia y prioridad altas; la ventana sigue abierta o no hay estimación)
- Emergencia: percentil 92 de la semana (cuota 7d más de 10 veces vs. semana previa) (medido)
- Etapa: semilla, saturación 0.00 (medido, reglas v1)
- Encaje con la audiencia: 0.65 (regla v1, estimación)

**Qué podría publicar 30X:** Pieza con ángulo «Explicador neutral» sobre Marsh & McLennan Companies dentro de «Inversión y mercados», explicada por su contexto (WB_1649_UNEMPLOYMENT_BENEFITS, WB_752_CONTRIBUTORY_BENEFITS, UNGP_SUPPORT_FOR_PEOPLE_WHO_CANT_WORK), antes de que el tema llegue al español (sugerencia editorial, no es una medición).

## 2. Rocket Lab (`org:rocket lab`), puesto #2

- **Etapa y decisión:** emergente, **esperar** (prioridad 0.42; emergencia percentil 72, medido).
- **Subtemas:** Inversión y mercados, Energía y clima, Chips e infraestructura, Salud y ciencia, Regulación y política, Modelos y LLMs, Creatividad y medios.
- **Ventana (chip):** `dias_restantes`, ~12 días restantes (estimación); desfase típico inglés→español/portugués 14.5 días (mediana de 46 pares de onsets de temas con el mismo subtema principal, medido por WS4).
- **Onset en inglés:** 2026-W31; **onset en español/portugués:** sin onset en 12 semanas (sin señal).
- **Ángulo emocional:** Giro (carga emocional percentil 92, medido).
- **Concentración de la semana:** 13% de sus 23 artículos co-mencionan al vecino más fuerte (medido).

**Serie semanal (artículos del anillo 1, medido):**

| Semana | W35 | W36 | W37 | W38 | W39 | W40 | W41 | W42 |
|---|---|---|---|---|---|---|---|---|
| Total | 13 | 24 | 10 | 7 | 9 | 9 | 8 | 23 |
| Inglés | 13 | 24 | 10 | 7 | 9 | 9 | 8 | 23 |
| Español + portugués | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Aristas que lo impulsan (anillo de 1 salto, semana 2026-W42, medido):**

| # | Vecino | Co-menciones (n) | NPMI |
|---|---|---|---|
| 1 | `org:penske automotive` | 3 | 0.777 |
| 2 | `org:penske corp` | 3 | 0.777 |
| 3 | `org:mitsui` | 3 | 0.746 |
| 4 | `org:penske automotive group` | 3 | 0.746 |
| 5 | `org:prologis` | 3 | 0.746 |

**Por qué (del Analista de señales, texto generado por código):**

- Decisión: esperar (regla 5: señal presente, sin la emergencia o la prioridad que piden publicar o preparar)
- Emergencia: percentil 72 de la semana (z_7d 13.5, cuota 7d +211% vs. semana previa) (medido)
- Etapa: emergente, saturación 0.14 (medido, reglas v1)
- Carga emocional: percentil 92; ángulo «Giro» (medido)
- Encaje con la audiencia: 0.55 (regla v1, estimación)

**Qué podría publicar 30X:** Pieza con ángulo «Giro» sobre Rocket Lab dentro de «Inversión y mercados», explicada por su contexto (penske automotive, penske corp, mitsui), antes de que el tema llegue al español (sugerencia editorial, no es una medición).

## 3. national stock exchange (`org:national stock exchange`), puesto #3

- **Etapa y decisión:** emergente, **preparar** (prioridad 0.40; emergencia percentil 90, medido).
- **Subtemas:** Energía y clima, Agentes de IA, Adopción empresarial, Seguridad y riesgos, Inversión y mercados.
- **Ventana (chip):** `dias_restantes`, ~5 días restantes (estimación); desfase típico inglés→español/portugués 11 días (mediana de 164 pares de onsets de temas con el mismo subtema principal, medido por WS4).
- **Onset en inglés:** 2026-W33; **onset en español/portugués:** sin onset en 12 semanas (sin señal).
- **Ángulo emocional:** Oportunidad / cómo aprovecharlo (carga emocional percentil 58, medido).
- **Concentración de la semana:** 62% de sus 24 artículos co-mencionan al vecino más fuerte (medido).

**Serie semanal (artículos del anillo 1, medido):**

| Semana | W35 | W36 | W37 | W38 | W39 | W40 | W41 | W42 |
|---|---|---|---|---|---|---|---|---|
| Total | 2 | 3 | 5 | 0 | 2 | 0 | 0 | 24 |
| Inglés | 2 | 3 | 5 | 0 | 2 | 0 | 0 | 24 |
| Español + portugués | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**Aristas que lo impulsan (anillo de 1 salto, semana 2026-W42, medido):**

| # | Vecino | Co-menciones (n) | NPMI |
|---|---|---|---|
| 1 | `org:nifty private bank` | 15 | 0.939 |
| 2 | `org:nifty realty` | 15 | 0.939 |
| 3 | `org:head of research at geojit investments` | 15 | 0.931 |
| 4 | `thm:ECON_WORLDCURRENCIES_THE_RUPEE` | 15 | 0.890 |
| 5 | `thm:ECON_GOLDPRICE` | 15 | 0.884 |

**Por qué (del Analista de señales, texto generado por código):**

- Decisión: preparar (regla 4: emergencia y prioridad altas; la ventana sigue abierta o no hay estimación)
- Emergencia: percentil 90 de la semana (z_7d 26.0, cuota 7d más de 10 veces vs. semana previa) (medido)
- Etapa: emergente, saturación 0.25 (medido, reglas v1)
- Carga emocional: percentil 58; ángulo «Oportunidad / cómo aprovecharlo» (medido)
- Encaje con la audiencia: 0.52 (regla v1, estimación)

**Qué podría publicar 30X:** Pieza con ángulo «Oportunidad / cómo aprovecharlo» sobre national stock exchange dentro de «Energía y clima», explicada por su contexto (nifty private bank, nifty realty, head of research at geojit investments), antes de que el tema llegue al español (sugerencia editorial, no es una medición).
