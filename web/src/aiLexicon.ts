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

export interface CommunitySignal {
  n_papers?: number | null;
  n_talks?: number | null;
  n_items?: number | null;
  hf_upvotes?: number | null;
  label_es?: string | null;
}

/** Placeholder until WP4 writes `community` onto the card. No invented counts. */
export function communityLine(community: CommunitySignal | null | undefined): string {
  if (!community) return "Comunidad IA: sin señal de esta semana";
  if (community.label_es) return `Comunidad IA: ${community.label_es}`;
  const parts: string[] = [];
  if (community.n_papers != null) parts.push(`${community.n_papers} papers`);
  if (community.n_talks != null) parts.push(`${community.n_talks} charlas`);
  if (parts.length === 0 && community.n_items != null) {
    parts.push(`${community.n_items} piezas`);
  }
  if (parts.length === 0) return "Comunidad IA: sin señal de esta semana";
  return `La comunidad IA lo discute: ${parts.join(", ")}`;
}
