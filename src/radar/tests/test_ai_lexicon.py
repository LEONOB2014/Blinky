"""The AI lexicon (contracts/ai_lexicon.yaml): the radar's ranked unit."""

import re
from pathlib import Path

import pytest
import yaml

LEXICON = Path(__file__).resolve().parents[3] / "contracts" / "ai_lexicon.yaml"
PREFIXES = (
    "lab",
    "model",
    "product",
    "tech",
    "infra",
    "research",
    "biz",
    "policy",
    "risk",
    "critic",
    "society",
)


@pytest.fixture(scope="module")
def lexicon():
    return yaml.safe_load(LEXICON.read_text(encoding="utf-8"))


def ids_for(lexicon, text):
    return {
        e["id"]
        for e in lexicon["entries"]
        if any(re.search(p, text.lower()) for p in e["patterns"])
    }


@pytest.mark.unit
def test_entries_are_valid_and_unique(lexicon):
    ids = [e["id"] for e in lexicon["entries"]]
    assert len(ids) == len(set(ids))
    for e in lexicon["entries"]:
        assert e["id"].split(":")[0] in PREFIXES, e["id"]
        assert e["family"] in lexicon["families"], e["id"]
        assert e["stance"] in {"promoter", "critic", "neutral"}, e["id"]
        assert e["label_es"] and e["patterns"], e["id"]
        for p in e["patterns"]:
            re.compile(p)
            # BigQuery runs RE2: no lookarounds or backreferences
            assert not re.search(r"\(\?[=!<]|\\[1-9]", p), (e["id"], p)
            assert p == p.lower() or "\\" in p, (e["id"], p)


@pytest.mark.unit
def test_the_critics_have_their_own_camp(lexicon):
    critics = [e for e in lexicon["entries"] if e["stance"] == "critic"]
    assert len(critics) >= 15
    assert {"critic:pause_ai", "risk:existential", "policy:eu_ai_act"} <= {e["id"] for e in critics}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("OpenAI launches GPT-5 agents for enterprise", {"lab:openai", "model:gpt", "tech:agents"}),
        ("la UE aprueba la ley de inteligencia artificial", {"policy:eu_ai_act"}),
        ("PauseAI protesters call for a moratorium on superintelligence", {"critic:pause_ai"}),
        (
            "Nvidia releases Nemotron open models on Hugging Face",
            {"lab:nvidia_models", "research:hugging_face"},
        ),
        ("Former OpenAI researchers launch a robotics startup", {"biz:talent_moves"}),
    ],
)
def test_headlines_map_to_ai_topics(lexicon, text, expected):
    assert expected <= ids_for(lexicon, text)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text", ["Kroger expands checkout to new stores", "travel agents expect a busy season"]
)
def test_non_ai_headlines_match_nothing(lexicon, text):
    assert ids_for(lexicon, text) == set()
