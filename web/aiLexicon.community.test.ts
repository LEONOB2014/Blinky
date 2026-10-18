import { describe, expect, test } from "bun:test";

import { communityFromRows, communityLine } from "./src/aiLexicon.ts";

const NONE = "Comunidad IA: sin señal de esta semana";

describe("communityLine", () => {
  test("says there is no signal when the topic-week has no rows", () => {
    expect(communityLine(null)).toBe(NONE);
    expect(communityLine(undefined)).toBe(NONE);
    expect(communityLine({ categories: [] })).toBe(NONE);
  });

  test("names the one measured category", () => {
    expect(communityLine({ categories: [{ category: "research", n_items: 61 }] })).toBe(
      "La comunidad IA lo discute: 61 piezas de investigación",
    );
    expect(communityLine({ categories: [{ category: "research", n_items: 1 }] })).toBe(
      "La comunidad IA lo discute: 1 pieza de investigación",
    );
  });

  test("lists several categories in the sensor order, without a source type", () => {
    expect(
      communityLine({
        categories: [
          { category: "builders", n_items: 6 },
          { category: "research", n_items: 50 },
        ],
      }),
    ).toBe("La comunidad IA lo discute: 50 de investigación, 6 de construcción");
  });

  test("sums duplicate categories and drops an unknown one", () => {
    expect(
      communityLine({
        categories: [
          { category: "research", n_items: 4 },
          { category: "research", n_items: 3 },
          { category: "papers", n_items: 9 },
        ],
      }),
    ).toBe("La comunidad IA lo discute: 7 piezas de investigación");
  });

  test("does not invent a count from a non-positive or fractional item count", () => {
    expect(
      communityLine({
        categories: [
          { category: "media", n_items: 0 },
          { category: "critics", n_items: 1.5 },
        ],
      }),
    ).toBe(NONE);
  });

  test("joins only the ai topic-week and ignores other rows", () => {
    const rows = [
      { topic_id: "ai:tech:fine_tuning", week: "2026-W42", category: "research", n_items: 61 },
      { topic_id: "ai:tech:fine_tuning", week: "2026-W42", category: "builders", n_items: 2 },
      { topic_id: "ai:tech:fine_tuning", week: "2026-W41", category: "research", n_items: 9 },
      { topic_id: "org:nvidia", week: "2026-W42", category: "research", n_items: 4 },
    ];
    expect(communityFromRows("org:nvidia", "2026-W42", rows)).toBeNull();
    expect(communityFromRows("ai:biz:mergers_deals", "2026-W42", rows)).toBeNull();
    expect(communityLine(communityFromRows("ai:tech:fine_tuning", "2026-W42", rows))).toBe(
      "La comunidad IA lo discute: 61 de investigación, 2 de construcción",
    );
  });
});
