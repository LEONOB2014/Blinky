"""The AI graph's metrics and ForceAtlas2 layout (graph/export_views.py)."""

import pytest

pytest.importorskip("igraph")
pytest.importorskip("numpy")

from graph import export_views as ev  # noqa: E402

EDGES = [
    ("a", "b", 40, 0.6),
    ("b", "c", 30, 0.5),
    ("a", "c", 25, 0.55),
    ("d", "e", 50, 0.7),
    ("e", "f", 20, 0.6),
    ("d", "f", 15, 0.5),
    ("c", "d", 3, 0.12),
]
IDS = ["a", "b", "c", "d", "e", "f", "g"]


@pytest.mark.unit
def test_ai_week_metrics_fill_every_node_with_an_edge():
    pr, wdeg, core = ev._ai_week_metrics(IDS, EDGES)
    assert all(pr[v] is not None and wdeg[v] is not None for v in IDS if v != "g")
    assert pr["g"] is None  # no edge that week: no metric, never zero-filled
    assert wdeg["d"] == 50 + 15 + 3


@pytest.mark.unit
def test_forceatlas2_is_deterministic_and_separates_two_groups():
    pytest.importorskip("leidenalg")
    imp = {v: [0.5] for v in IDS}
    one, meta = ev._ai_layout(IDS, {0: EDGES}, imp)
    two, _ = ev._ai_layout(IDS, {0: EDGES}, imp)
    assert one == two
    assert meta["layout"] == "forceatlas2_linlog" and meta["communities"] >= 2

    def dist(u, v):
        (x1, y1), (x2, y2) = one[IDS.index(u)], one[IDS.index(v)]
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

    assert dist("a", "b") < dist("a", "e")  # the two triangles form two clusters
