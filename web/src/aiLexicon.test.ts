import { communityFromRows, communityLine } from "./aiLexicon";

function check(actual: unknown, expected: unknown): void {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) {
    throw new Error(`expected ${right} got ${left}`);
  }
}

check(communityLine(null), "Comunidad IA: sin señal de esta semana");
check(communityLine(undefined), "Comunidad IA: sin señal de esta semana");
check(communityLine({ categories: [] }), "Comunidad IA: sin señal de esta semana");
check(
  communityLine({ categories: [{ category: "research", n_items: 61 }] }),
  "La comunidad IA lo discute: 61 piezas de investigación",
);
check(
  communityLine({ categories: [{ category: "research", n_items: 1 }] }),
  "La comunidad IA lo discute: 1 pieza de investigación",
);
check(
  communityLine({
    categories: [
      { category: "builders", n_items: 6 },
      { category: "research", n_items: 50 },
    ],
  }),
  "La comunidad IA lo discute: 50 de investigación, 6 de construcción",
);

const rows = [
  { topic_id: "ai:tech:fine_tuning", week: "2026-W42", category: "research", n_items: 61 },
  { topic_id: "ai:tech:fine_tuning", week: "2026-W42", category: "builders", n_items: 2 },
  { topic_id: "ai:tech:fine_tuning", week: "2026-W41", category: "research", n_items: 9 },
  { topic_id: "org:nvidia", week: "2026-W42", category: "research", n_items: 4 },
];
check(communityFromRows("org:nvidia", "2026-W42", rows), null);
check(communityFromRows("ai:biz:mergers_deals", "2026-W42", rows), null);
check(
  communityLine(communityFromRows("ai:tech:fine_tuning", "2026-W42", rows)),
  "La comunidad IA lo discute: 61 de investigación, 2 de construcción",
);
check(
  communityLine(communityFromRows("ai:tech:fine_tuning", "2026-W41", rows)),
  "La comunidad IA lo discute: 9 piezas de investigación",
);

console.log("communityLine ok");
