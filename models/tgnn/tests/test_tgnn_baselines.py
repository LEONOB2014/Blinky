"""EdgeBank and persistence baselines on the committed dev slice (never reported)."""

import importlib.util
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from radar.fixtures import DEV_DIR

pytestmark = pytest.mark.unit

# models/ has no package marker (other workstreams own it), so load the module by path.
_spec = importlib.util.spec_from_file_location(
    "tgnn_baselines", Path(__file__).resolve().parents[1] / "baselines.py"
)
bl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bl)


@pytest.fixture(scope="module")
def edges():
    return pl.read_parquet(DEV_DIR / "edges_weekly.parquet")


@pytest.fixture(scope="module")
def per_pair(edges):
    return bl.evaluate(edges)


def test_query_rank_uses_the_mean_position_of_ties():
    negatives = {"a", "b", "c", "d"}
    assert bl.query_rank({"v"}, "v", negatives) == 1  # only the true node remembered
    assert bl.query_rank({"v", "a", "b"}, "v", negatives) == 2  # tied with 2 -> 1 + 2/2
    assert bl.query_rank({"a"}, "v", negatives) == 1 + 1 + 3 / 2
    assert bl.query_rank(set(), "v", negatives) == 1 + 4 / 2  # random reference


def test_every_edge_of_the_next_week_gives_two_queries(edges, per_pair):
    weeks = sorted(edges["wk"].unique())
    expected = 2 * edges.filter(pl.col("wk") != weeks[0]).height
    total = per_pair.filter((pl.col("target") == "all") & (pl.col("model") == "edgebank"))
    assert total["queries"].sum() == expected
    assert per_pair["wk_t"].n_unique() == len(weeks) - 1


def test_edgebank_equals_persistence_on_the_first_pair(per_pair):
    first = per_pair.filter(pl.col("wk_t") == per_pair["wk_t"].min())
    by_model = {(r["target"], r["model"]): r["rr_sum"] for r in first.iter_rows(named=True)}
    for target in bl.TARGETS:
        assert by_model[(target, "edgebank")] == pytest.approx(by_model[(target, "persistence")])


def test_new_edges_are_a_subset_of_all(per_pair):
    q = per_pair.filter(pl.col("model") == "random").pivot("target", index="wk_t", values="queries")
    assert (q["new"] <= q["all"]).all()
    assert (q["new"] > 0).all()


def test_a_gap_breaks_the_pair_and_resets_memory(edges):
    gap = edges.filter(pl.col("wk") != date(2026, 9, 21))
    pairs = bl.evaluate(gap)
    assert date(2026, 9, 14) not in pairs["wk_t"].to_list()
    after = pairs.filter(pl.col("wk_t") == date(2026, 9, 28))
    by_model = {(r["target"], r["model"]): r["rr_sum"] for r in after.iter_rows(named=True)}
    assert by_model[("all", "edgebank")] == pytest.approx(by_model[("all", "persistence")])


def test_summary_has_no_interval_below_ten_pairs(per_pair):
    summary = bl.summarize(per_pair)
    assert summary.height == len(bl.TARGETS) * len(bl.MODELS)
    assert summary["ci_low"].null_count() == summary.height
    assert summary["mrr"].is_between(0, 1).all()


def test_interval_brackets_the_mrr_with_ten_or_more_pairs(per_pair):
    # The dev slice has 7 real pairs; repeating them (shifted 10 weeks) exercises the code path.
    doubled = pl.concat([per_pair, per_pair.with_columns(pl.col("wk_t") + pl.duration(weeks=10))])
    summary = bl.summarize(doubled)
    assert (summary["week_pairs"] == 14).all()
    assert ((summary["ci_low"] <= summary["mrr"]) & (summary["mrr"] <= summary["ci_high"])).all()
