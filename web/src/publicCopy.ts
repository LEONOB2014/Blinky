/** Visible copy: no endpoint names, rule numbers, or "(medido)" after every value. */

const RULE_NUMBER = /\s*\(regla\s+\d+:[^)]*\)/gi;
const MEASURED_PAREN = /\s*\(medido(?:,\s*reglas v1)?\)/gi;
const ESTIMATE_PAREN = /\s*\((?:regla v1,\s*)?estimaci[oó]n\)/gi;
const ESTIMADO_PAREN = /\s*\(estimado(?:,\s*n=\d+)?\)/gi;

export function cleanPublicText(text: string): string {
  return text
    .replace(RULE_NUMBER, "")
    .replace(MEASURED_PAREN, "")
    .replace(ESTIMATE_PAREN, "")
    .replace(ESTIMADO_PAREN, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** ● measured, ○ estimated. A line can carry both. */
export function measureMarks(text: string): string {
  const marks: string[] = [];
  if (/medido/i.test(text)) marks.push("●");
  if (/estimad/i.test(text)) marks.push("○");
  return marks.join("");
}

/** One line safe to show. The raw sentence stays behind Detalles técnicos. */
export function publicLine(text: string): string {
  const marks = measureMarks(text);
  const cleaned = cleanPublicText(text);
  return marks ? `${cleaned} ${marks}` : cleaned;
}

export function markForKind(kind: string | undefined): string {
  return kind === "estimate" || kind === "estimado" ? "○" : "●";
}
