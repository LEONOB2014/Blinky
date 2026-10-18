import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cloudrun_stage  # noqa: E402

from agents import tools  # noqa: E402


def _view(lake: Path, ids: list[str]) -> None:
    (lake / "views").mkdir(parents=True)
    (lake / "views" / "temporal.json").write_text(
        json.dumps(
            {
                "_meta": {
                    "iso_weeks": ["2026-W42"],
                    "params": {"top_k_per_node": 5, "min_n": 20, "min_npmi_exclusive": 0.1},
                    "edges_per_week": [1],
                },
                "nodes": [{"id": i} for i in ids],
                "edges": {"source": [0], "target": [1], "week": [0]},
            }
        ),
        encoding="utf-8",
    )
    (lake / "views" / "story.json").write_text("{}", encoding="utf-8")


@pytest.fixture
def lake(tmp_path, monkeypatch):
    lake = tmp_path / "lake"
    monkeypatch.setenv("RADAR_LAKE", str(lake))
    monkeypatch.setattr(cloudrun_stage, "plan", lambda: [])  # no gold tables in this test
    return lake


@pytest.mark.unit
def test_stage_copies_only_the_graph_facts_view_to_the_path_the_tool_reads(
    lake, tmp_path, monkeypatch
):
    _view(lake, ["org:a", "thm:b"])
    out = cloudrun_stage.stage(tmp_path / "out")
    staged = sorted(p.relative_to(out).as_posix() for p in (out / "lake" / "views").iterdir())
    assert staged == ["lake/views/temporal.json"]  # not story.json or anything else
    # the image sets RADAR_LAKE=/app/lake over the staged context: the tool must find the file there
    dockerfile = (out / "Dockerfile").read_text(encoding="utf-8")
    assert "RADAR_LAKE=/app/lake" in dockerfile and "COPY . ." in dockerfile
    monkeypatch.setenv("RADAR_LAKE", str(out / "lake"))
    monkeypatch.setattr(tools, "profile", lambda: "full")
    facts = tools.get_graph_facts()
    assert facts["available"] and facts["conexiones_por_tema"] == 5 and facts["temas_semana"] == 2


@pytest.mark.unit
def test_stage_refuses_a_missing_view_or_one_with_persons(lake, tmp_path):
    with pytest.raises(SystemExit, match="missing in the lake: views/temporal.json"):
        cloudrun_stage.stage(tmp_path / "out")
    _view(lake, ["org:a", "per:someone"])
    with pytest.raises(SystemExit, match="person nodes"):
        cloudrun_stage.stage(tmp_path / "out")
