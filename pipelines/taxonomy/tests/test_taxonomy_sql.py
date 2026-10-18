"""The ring and subtopic rules in bq_sql/ copy contracts/taxonomy.yaml: keep them identical."""

import re

import pytest
import yaml

from radar.paths import REPO_ROOT

TAXONOMY = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
S4A = (REPO_ROOT / "bq_sql" / "s4a_article_segment.sql").read_text(encoding="utf-8")
S4 = (REPO_ROOT / "bq_sql" / "s4_aggregates.sql").read_text(encoding="utf-8")


def _topic_rules() -> dict[str, tuple[str, str | None]]:
    block = S4[S4.index("CREATE OR REPLACE TABLE `radar.topic_rules`") :]
    block = block[: block.index("]);")]
    rules = {}
    for m in re.finditer(
        r"\(?'([a-z_]+)'(?: AS topic)?, r'([^']*)'(?: AS re)?, ([^\n]*?)\),?\n", block
    ):
        theme = re.match(r"r'([^']*)'", m.group(3))
        rules[m.group(1)] = (m.group(2), theme.group(1) if theme else None)
    return rules


@pytest.mark.unit
def test_every_subtopic_has_a_rule():
    assert set(_topic_rules()) == set(TAXONOMY["subtopics"])


@pytest.mark.unit
def test_energy_climate_rule_is_the_taxonomy_one():
    spec = TAXONOMY["subtopics"]["energy_climate"]
    text_re, theme_re = _topic_rules()["energy_climate"]
    assert text_re == spec["re"]
    assert theme_re == "^(" + "|".join(spec["themes_prefix"]) + ")"


@pytest.mark.unit
def test_domain_prefixes_are_the_taxonomy_ones():
    found = dict(
        re.findall(
            r"\(?(?:STRUCT\()?'([a-z_]+)'(?: AS domain)?, r'\(\?:\^\|;\)\(\?:([^)]*)\)'", S4A
        )
    )
    expected = {d: "|".join(spec["themes_prefix"]) for d, spec in TAXONOMY["domains"].items()}
    assert found == expected


@pytest.mark.unit
def test_ring_one_is_the_core_ai_rule():
    rule = TAXONOMY["rings"]["ai"]["rule"]
    assert f"({rule}) AS ai" in S4A


@pytest.mark.unit
def test_ring_three_requires_a_tech_org_and_comes_after_ring_two():
    case = S4A[S4A.index("CASE") : S4A.index("END AS segment")]
    assert case.index("'ai'") < case.index("'it'") < case.index("'ai_domain'")
    assert "ARRAY_LENGTH(domain_hits) > 0 AND tech_org" in case
