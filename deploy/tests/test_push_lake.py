import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import push_lake  # noqa: E402


def _gold(monkeypatch, tmp_path: Path, name: str, frame: pl.DataFrame) -> None:
    frame.write_parquet(tmp_path / f"{name}.parquet")
    monkeypatch.setattr(push_lake, "gold", lambda n: tmp_path / f"{n}.parquet")


@pytest.mark.unit
def test_the_ai_radar_tables_ship_and_its_edges_do_not():
    for table in ("topic_ai_scores_weekly", "topic_ai_daily", "community_topic_weekly"):
        assert table in push_lake.TABLES
    assert {"edges_weekly", "edges_ai_weekly"} <= push_lake.NEVER
    assert not push_lake.NEVER & set(push_lake.TABLES)


@pytest.mark.unit
def test_a_person_topic_is_refused(monkeypatch, tmp_path):
    _gold(
        monkeypatch, tmp_path, "topic_ai_daily", pl.DataFrame({"topic_id": ["ai:lab:x", "per:x"]})
    )
    with pytest.raises(SystemExit, match="person rows"):
        push_lake.guard("topic_ai_daily")


@pytest.mark.unit
def test_titles_only_ship_in_the_evidence_table(monkeypatch, tmp_path):
    rows = pl.DataFrame({"topic_id": ["ai:lab:x"], "title": ["t"], "url": ["https://example.org"]})
    _gold(monkeypatch, tmp_path, "community_topic_weekly", rows)
    with pytest.raises(SystemExit, match="title/URL columns"):
        push_lake.guard("community_topic_weekly")
    _gold(monkeypatch, tmp_path, "topic_evidence_weekly", rows)
    push_lake.guard("topic_evidence_weekly")  # allowed: public news, image and site only
