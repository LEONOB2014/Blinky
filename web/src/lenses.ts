import type { ViewColorBy } from "./types/contracts";

/** Lenses the GPU graph and the story graph both draw. `arousal` aliases `tone`. */
export const GRAPH_LENSES = [
  "decision",
  "segment",
  "bridge",
  "momentum",
  "novelty",
  "community",
  "tone",
  "window",
  "family",
  "postura",
] as const;

export type GraphLens = (typeof GRAPH_LENSES)[number];

export const LENS_NAMES: Record<GraphLens, string> = {
  decision: "Radar (Decisión)",
  segment: "Historia (Anillos)",
  bridge: "Puente (Conexión entre sectores)",
  momentum: "Momento (Aceleración)",
  novelty: "Novedad (Enlaces nuevos)",
  community: "Comunidades (Leiden)",
  tone: "Emoción (Tono)",
  window: "Ventana (Horizonte)",
  family: "Familia",
  postura: "Postura",
};

const GRAPH_LENS_SET: ReadonlySet<string> = new Set(GRAPH_LENSES);

export function isGraphLens(value: string | null | undefined): value is GraphLens {
  return !!value && GRAPH_LENS_SET.has(value);
}

/** Map a view_command color_by onto a lens the graph can draw. */
export function graphLensFromColorBy(colorBy: string | null | undefined): GraphLens {
  if (colorBy === "arousal") return "tone";
  if (isGraphLens(colorBy)) return colorBy;
  return "decision";
}

// Same order as agents/runtime.py view_lens, so a click and a chat answer pick one lens.
const TONE_Q = /tono|emoci|sentimiento|[aá]nimo|negativ|positiv/i;
const POSTURA_Q = /qui[eé]n se opone|se oponen|opositor|cr[ií]tic|regulaci[oó]n|postura/i;
const WINDOW_Q = /ventana|espa[nñ]ol|portugu|llega|a punto|d[ií]as quedan/i;
const NOVELTY_Q =
  /nuev[oa]s? (conexion|relacion|v[ií]nculo)|(conexion|relacion|v[ií]nculo)\w* nuev|qu[eé] cambi/i;
const MOMENTUM_Q = /impulso|acelera|sube m[aá]s r[aá]pido|ganando/i;
const BRIDGE_Q =
  /puente|conect|cruza|otros? (dominios?|sectores?)|cl[ií]ma|salud|educaci|empleo/i;

export function lensForQuestion(message: string, entity: string | null): GraphLens {
  if (TONE_Q.test(message)) return "tone";
  if (POSTURA_Q.test(message)) return "postura";
  if (WINDOW_Q.test(message)) return "window";
  if (NOVELTY_Q.test(message)) return "novelty";
  if (MOMENTUM_Q.test(message)) return "momentum";
  if (BRIDGE_Q.test(message) && !entity) return "bridge";
  return entity ? "segment" : "decision";
}

export function lensFromCommand(
  colorBy: ViewColorBy | string | null | undefined,
  message: string,
  entity: string | null,
): GraphLens {
  if (colorBy === "arousal" || isGraphLens(colorBy)) return graphLensFromColorBy(colorBy);
  return lensForQuestion(message, entity);
}
