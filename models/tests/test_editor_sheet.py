"""The blind editor-test sheet on the dev slice (2026-W42, subtopics)."""

import pytest

from models import editor_sheet as es


@pytest.fixture(scope="module")
def lists():
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_PROFILE", "dev")
    try:
        return es.lists("2026-W42")
    finally:
        mp.undo()


def test_both_lists_have_ten_ranked_units(lists):
    radar, base = lists
    assert len(radar) == len(set(radar)) == 10
    assert len(base) == len(set(base)) == 10
    assert "ai_all" not in radar + base


def test_overlap_is_shown_once_and_marked(lists):
    radar, base = lists
    its = es.items(radar, base)
    ids = [it["topic_id"] for it in its]
    assert len(ids) == len(set(ids)) == len(set(radar) | set(base))
    both = {it["topic_id"] for it in its if it["list"] == "both"}
    assert both == set(radar) & set(base)


def test_order_is_fixed_by_the_seed(lists):
    assert es.items(*lists) == es.items(*lists)
    assert [it["item"] for it in es.items(*lists)] == list(range(1, len(es.items(*lists)) + 1))


def test_sheet_hides_the_source(lists):
    its = es.items(*lists)
    text = es.render("2026-W42", its, {})
    assert "radar" not in text.lower().split("generated")[0]
    assert "raw_count_growth" not in text


def test_tally_counts_yes_per_list_and_rater(lists):
    its = es.items(*lists)
    rows = es.render("2026-W42", its, {}).splitlines()
    filled = []
    for line in rows:
        m = es.ROW.match(line)
        if m:
            # rater A says yes to every item, rater B to none
            line = line.rsplit("|", 3)[0] + "| sí | no |"
        filled.append(line)
    out = es.tally("\n".join(filled), its)
    n_radar = sum(1 for it in its if it["list"] == "radar")
    n_base = sum(1 for it in its if it["list"] == "raw_count_growth")
    assert out["overlap"] == sum(1 for it in its if it["list"] == "both")
    assert out["raters"]["Evaluador A"] == {
        "radar": f"{n_radar}/{n_radar}",
        "raw_count_growth": f"{n_base}/{n_base}",
    }
    assert out["raters"]["Evaluador B"]["radar"] == f"0/{n_radar}"
