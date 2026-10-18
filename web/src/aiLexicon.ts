/** Family and stance for `ai:` topics. Colours match `graph/export_views.py`. */

export interface LexiconEntry {
  label_es: string;
  family: string;
  stance: "promoter" | "critic" | "neutral" | string;
}

export interface PaletteEntry {
  id: string;
  label: string;
  color: string;
}

/** Keys match `contracts/ai_lexicon.yaml` families. Hex matches `graph/export_views.py`. */
export const FAMILY_PALETTE: PaletteEntry[] = [
  { id: "labs", label: "Laboratorios", color: "#6d28d9" },
  { id: "models", label: "Modelos", color: "#2563eb" },
  { id: "products", label: "Productos y asistentes", color: "#0891b2" },
  { id: "techniques", label: "Técnicas", color: "#0f766e" },
  { id: "infra", label: "Infraestructura y chips", color: "#b45309" },
  { id: "research", label: "Investigación y open source", color: "#7c3aed" },
  { id: "business", label: "Negocio e inversión", color: "#047857" },
  { id: "policy", label: "Regulación y política", color: "#1d4ed8" },
  { id: "safety", label: "Seguridad y riesgo", color: "#b91c1c" },
  { id: "opposition", label: "Oposición y crítica", color: "#c2410c" },
  { id: "society", label: "Sociedad y trabajo", color: "#a16207" },
];

export const STANCE_PALETTE: PaletteEntry[] = [
  { id: "promoter", label: "Impulsores", color: "#1d4ed8" },
  { id: "critic", label: "Críticos", color: "#c2410c" },
  { id: "neutral", label: "Neutros", color: "#64748b" },
];

const FAMILY_BY_ID = new Map(FAMILY_PALETTE.map((entry) => [entry.id, entry]));
const STANCE_BY_ID = new Map(STANCE_PALETTE.map((entry) => [entry.id, entry]));

/** Id prefix in `ai:<prefix>:<slug>` when the lexicon file has not landed yet. */
const PREFIX_FAMILY: Record<string, string> = {
  lab: "labs",
  model: "models",
  product: "products",
  tech: "techniques",
  infra: "infra",
  research: "research",
  biz: "business",
  policy: "policy",
  risk: "safety",
  critic: "opposition",
  society: "society",
};

export function familyEntry(family: string | null | undefined): PaletteEntry | null {
  if (!family) return null;
  return FAMILY_BY_ID.get(family) ?? { id: family, label: family, color: "#64748b" };
}

export function stanceEntry(stance: string | null | undefined): PaletteEntry {
  if (!stance) return STANCE_BY_ID.get("neutral") as PaletteEntry;
  return STANCE_BY_ID.get(stance) ?? { id: stance, label: stance, color: "#64748b" };
}

export function familyForTopic(
  topicId: string,
  familyFromCard?: string | null,
): PaletteEntry | null {
  const fromCard = familyEntry(familyFromCard);
  if (fromCard) return fromCard;
  if (!topicId.startsWith("ai:")) return null;
  const prefix = topicId.split(":")[1] ?? "";
  return familyEntry(PREFIX_FAMILY[prefix] ?? null);
}

/** One category's measured item count for a topic-week. */
export interface CommunityCategoryCount {
  category: string;
  n_items: number;
}

/** Fields the client needs from `community_topic_weekly` to join a card. */
export interface CommunityTopicRow {
  topic_id: string;
  week: string;
  category: string;
  n_items: number;
}

/** Category counts for one `ai:` topic-week. Null means that card has no community line data. */
export interface CommunitySignal {
  categories: CommunityCategoryCount[];
}

/** Rows for one topic-week. Non-`ai:` topics and weeks with no row return null. */
export function communityFromRows(
  topicId: string,
  week: string,
  rows: readonly CommunityTopicRow[] | null | undefined,
): CommunitySignal | null {
  if (!topicId.startsWith("ai:")) return null;
  const categories = (rows ?? [])
    .filter((row) => row.topic_id === topicId && row.week === week)
    .map((row) => ({ category: row.category, n_items: row.n_items }));
  if (categories.length === 0) return null;
  return { categories };
}

const COMMUNITY_CATEGORY_ORDER = [
  "research",
  "practitioners",
  "builders",
  "vision",
  "media",
  "critics",
] as const;

const COMMUNITY_CATEGORY_ES: Record<(typeof COMMUNITY_CATEGORY_ORDER)[number], string> = {
  research: "investigación",
  practitioners: "práctica",
  builders: "construcción",
  vision: "visión",
  media: "medios",
  critics: "crítica",
};

const NO_COMMUNITY = "Comunidad IA: sin señal de esta semana";

/**
 * Spanish line from measured category counts. No source type, so this never says papers
 * or charlas, and it never invents a count.
 */
export function communityLine(community: CommunitySignal | null | undefined): string {
  const totals = new Map<string, number>();
  for (const row of community?.categories ?? []) {
    if (!(row.category in COMMUNITY_CATEGORY_ES)) continue;
    if (!Number.isInteger(row.n_items) || row.n_items < 1) continue;
    totals.set(row.category, (totals.get(row.category) ?? 0) + row.n_items);
  }
  const present = COMMUNITY_CATEGORY_ORDER.filter((category) => totals.has(category)).sort(
    (a, b) =>
      (totals.get(b) ?? 0) - (totals.get(a) ?? 0) ||
      COMMUNITY_CATEGORY_ORDER.indexOf(a) - COMMUNITY_CATEGORY_ORDER.indexOf(b),
  );
  if (present.length === 0) return NO_COMMUNITY;
  if (present.length === 1) {
    const category = present[0];
    const count = totals.get(category);
    const piezas = count === 1 ? "pieza" : "piezas";
    return `La comunidad IA lo discute: ${count} ${piezas} de ${COMMUNITY_CATEGORY_ES[category]}`;
  }
  const parts = present.map(
    (category) => `${totals.get(category)} de ${COMMUNITY_CATEGORY_ES[category]}`,
  );
  return `La comunidad IA lo discute: ${parts.join(", ")}`;
}
