"""The AI community sensor: parsing and lexicon matching, offline."""

import datetime as dt

import polars as pl
import pytest

pytest.importorskip("defusedxml")

from crosssource import community  # noqa: E402

RFS_PAGE = """<h2>Fall 2026</h2><div>Startup Jobs</div><div>Log in</div>
<h3>Multiplayer AI</h3><div>Ada</div><div>Lovelace</div>
<p>AI agents are the most powerful new tool a team has, but people use them alone.</p>
<p>Anyone on a team should be able to drop into the same live agent session to watch it.</p>
<h3>Compute at Sea</h3><div>Alan</div><div>Turing</div>
<div>Partner at a fund</div>
<p>Artificial intelligence is running out of compute, electricity and land.</p>"""


@pytest.mark.unit
def test_rfs_items_keep_titles_and_text_but_never_author_names():
    items = community._rfs_items(RFS_PAGE)
    assert [t for t, _ in items] == ["Multiplayer AI", "Compute at Sea"]
    text = " ".join(b for _, b in items)
    assert "Lovelace" not in text and "Turing" not in text and "Partner at a fund" not in text


@pytest.mark.unit
def test_items_match_the_lexicon_and_aggregate_by_iso_week():
    day = dt.date(2026, 10, 14)
    rows = [
        community._item(
            {"id": "hf", "category": "research", "kind": "rss"},
            day,
            "Nvidia releases Nemotron on Hugging Face",
        ),
        community._item(
            {"id": "pause", "category": "critics", "kind": "rss"},
            day,
            "PauseAI calls for a moratorium on superintelligence",
        ),
        community._item(
            {"id": "misc", "category": "media", "kind": "rss"}, day, "Kroger opens new stores"
        ),
    ]
    matched = community.match_lexicon(pl.DataFrame(rows))
    assert {"ai:lab:nvidia_models", "ai:research:hugging_face", "ai:critic:pause_ai"} <= set(
        matched["topic_id"]
    )
    assert "misc" not in set(matched["source_id"])
    weekly = community.weekly(matched)
    assert set(weekly["week"]) == {"2026-W42"}
    assert weekly.filter(pl.col("topic_id") == "ai:critic:pause_ai")["category"].to_list() == [
        "critics"
    ]
