"""Memorization baselines for weekly link prediction (WS7, plan P2): EdgeBank and persistence.

    RADAR_PROFILE=full uv run python models/tgnn/baselines.py    # writes reports/tgnn.md
    uv run python models/tgnn/baselines.py                       # dev: stdout only, never reported

Task: for each pair of consecutive weeks (t, t+1) in ``edges_weekly`` (exactly 7 days apart; a
gap breaks the pair, never filled), predict the edges of week t+1. Two target sets:

- ``new``: edges of t+1 that were absent in week t (the brief's new-edge prediction);
- ``all``: every edge of t+1.

Each positive edge (u, v) gives two queries, u -> v and v -> u. A query ranks the true node
against every other node of week t+1, minus the query node and its other true neighbours that
week (the filtered setting). Scores are binary memories:

- persistence: 1 if the pair is an edge in week t;
- EdgeBank (unlimited memory): 1 if the pair was an edge in any week up to t.

Ties are ranked at their mean position (the expected rank under random tie-breaking), so a
query with no memory scores like the random reference, 1 / (1 + N/2) for N negatives.
MRR = mean of 1 / rank over queries. With 10 or more week pairs the report adds a 95% bootstrap
interval over week pairs; below that it prints the counts only.
"""

import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from radar import paths

WEEK = timedelta(days=7)
MODELS = ("persistence", "edgebank", "random")
TARGETS = ("new", "all")
MIN_PAIRS_FOR_INTERVAL = 10
BOOTSTRAP = 1000
SEED = 7
REPORT = paths.REPO_ROOT / "reports" / "tgnn.md"

Adjacency = dict[str, set[str]]


def week_adjacency(week: pl.DataFrame) -> Adjacency:
    adj: Adjacency = defaultdict(set)
    for x, y in week.select("x", "y").iter_rows():
        adj[x].add(y)
        adj[y].add(x)
    return adj


def query_rank(memory: set[str], true_node: str, negatives: set[str]) -> float:
    """Mean-position rank of ``true_node`` among ``negatives`` under binary memory scores."""
    return _rank(true_node in memory, len(memory & negatives), len(negatives))


def _rank(remembered: bool, hits: int, n_neg: int) -> float:
    if remembered:
        return 1 + hits / 2
    return 1 + hits + (n_neg - hits) / 2


def evaluate_pair(last: Adjacency, bank: Adjacency, nxt: Adjacency) -> list[dict]:
    """One row per (target, model) for the pair (t, t+1).

    ``last`` is week t, ``bank`` every edge of the contiguous weeks up to t. A node's negatives
    are the same for all its true neighbours, so its memory hits are counted once.
    """
    nodes = set(nxt)
    empty: set[str] = set()
    sums = {(tg, m): 0.0 for tg in TARGETS for m in MODELS}
    counts = dict.fromkeys(TARGETS, 0)
    for u, true_nbrs in nxt.items():
        negatives = nodes - true_nbrs - {u}
        mem = {"persistence": last.get(u, empty), "edgebank": bank.get(u, empty), "random": empty}
        hits = {m: len(mem[m] & negatives) for m in MODELS}
        for v in true_nbrs:
            recip = {m: 1 / _rank(v in mem[m], hits[m], len(negatives)) for m in MODELS}
            for tg in TARGETS:
                if tg == "new" and v in mem["persistence"]:
                    continue
                counts[tg] += 1
                for m in MODELS:
                    sums[(tg, m)] += recip[m]
    return [
        {"target": tg, "model": m, "queries": counts[tg], "rr_sum": sums[(tg, m)]}
        for tg in TARGETS
        for m in MODELS
    ]


def evaluate(edges: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    """Per week pair, target and model: queries and the sum of reciprocal ranks.

    Streams one week at a time. EdgeBank's memory restarts after a gap, so it only spans
    contiguous weeks up to t.
    """
    lf = edges.lazy()
    weeks = sorted(lf.select(pl.col("wk").unique()).collect()["wk"].to_list())
    rows = []
    bank: Adjacency = defaultdict(set)
    last: Adjacency | None = None
    prev_wk: date | None = None
    for wk in weeks:
        adj = week_adjacency(lf.filter(pl.col("wk") == wk).collect())
        if last is not None and prev_wk is not None and wk - prev_wk == WEEK:
            for row in evaluate_pair(last, bank, adj):
                rows.append({"wk_t": prev_wk, "wk_next": wk, **row})
        else:
            bank = defaultdict(set)
        for u, vs in adj.items():
            bank[u] |= vs
        last, prev_wk = adj, wk
    return pl.DataFrame(rows)


def summarize(per_pair: pl.DataFrame) -> pl.DataFrame:
    """MRR per target and model over all week pairs, with a bootstrap interval when enough."""
    out = []
    for (target, model), g in per_pair.group_by("target", "model", maintain_order=True):
        q, s = g["queries"].to_list(), g["rr_sum"].to_list()
        n_pairs = len(q)
        lo = hi = None
        if n_pairs >= MIN_PAIRS_FOR_INTERVAL:
            rng = random.Random(SEED)  # noqa: S311 (bootstrap resampling, not crypto)
            stats = []
            for _ in range(BOOTSTRAP):
                idx = [rng.randrange(n_pairs) for _ in range(n_pairs)]
                tq = sum(q[i] for i in idx)
                stats.append(sum(s[i] for i in idx) / tq if tq else 0.0)
            stats.sort()
            lo, hi = stats[int(0.025 * BOOTSTRAP)], stats[int(0.975 * BOOTSTRAP) - 1]
        out.append(
            {
                "target": target,
                "model": model,
                "week_pairs": n_pairs,
                "queries": sum(q),
                "mrr": sum(s) / sum(q) if sum(q) else None,
                "ci_low": lo,
                "ci_high": hi,
            }
        )
    return pl.DataFrame(out)


def render(
    summary: pl.DataFrame, per_pair: pl.DataFrame, edges: pl.DataFrame | pl.LazyFrame
) -> str:
    stats = edges.lazy().select(
        first=pl.col("wk").min(), last=pl.col("wk").max(), n_weeks=pl.col("wk").n_unique(),
        n_edges=pl.len(),
    ).collect().row(0, named=True)  # fmt: skip
    lines = [
        "# TGNN baselines: EdgeBank and persistence (WS7, P2)",
        "",
        f"Profile: `{paths.profile()}`. Input: `edges_weekly`, {stats['n_weeks']} weeks "
        f"({stats['first']} .. {stats['last']}), {stats['n_edges']:,} edges (measured). "
        "Code: `models/tgnn/baselines.py` (task, filtering and tie rule in its docstring).",
        "",
        "Every number below is *(measured)*. MRR = mean of 1/rank over queries; each positive "
        "edge gives two queries. `random` is the all-ties reference.",
        "",
        "| target | model | week pairs | queries | MRR | 95% interval |",
        "|---|---|---|---|---|---|",
    ]
    for r in summary.iter_rows(named=True):
        ci = (
            f"{r['ci_low']:.4f} .. {r['ci_high']:.4f}"
            if r["ci_low"] is not None
            else f"none (< {MIN_PAIRS_FOR_INTERVAL} week pairs)"
        )
        mrr = f"{r['mrr']:.4f}" if r["mrr"] is not None else "n/a"
        lines.append(
            f"| {r['target']} | {r['model']} | {r['week_pairs']} | {r['queries']:,} | {mrr} "
            f"| {ci} |"
        )
    lines += ["", "## Per week pair", "", "| t | t+1 | target | model | queries | MRR |",
              "|---|---|---|---|---|---|"]  # fmt: skip
    for r in per_pair.sort("wk_t", "target", "model").iter_rows(named=True):
        mrr = f"{r['rr_sum'] / r['queries']:.4f}" if r["queries"] else "n/a"
        lines.append(
            f"| {r['wk_t']} | {r['wk_next']} | {r['target']} | {r['model']} | "
            f"{r['queries']:,} | {mrr} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    edges = pl.scan_parquet(paths.gold("edges_weekly"))
    per_pair = evaluate(edges)
    text = render(summarize(per_pair), per_pair, edges)
    if paths.profile() == "full":
        Path(REPORT).write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {REPORT}\n")
    else:
        sys.stdout.write("dev profile: printed only, never reported\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
