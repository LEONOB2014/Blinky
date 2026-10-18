import pytest
from evidence_titles import title_key


@pytest.mark.unit
def test_a_site_suffix_is_the_same_story():
    a = "Wall Street muscles higher despite more swings for AI stocks"
    assert title_key(a) == title_key(a + " - Boston News, Weather, Sports")
    assert title_key(a) == title_key(a + " | The Motley Fool")
    assert title_key(a) == title_key(a + " :: Markets")


@pytest.mark.unit
def test_an_escaped_dash_before_the_site_is_decoded():
    a = "AI agents are hacking without human oversight. How did we get here?"
    assert title_key(a) == title_key(a + " &#x2013; PolitiFact")
    assert title_key("Forum discusses&#xA0;technological innovation in surgery") == title_key(
        "Forum discusses technological innovation in surgery"
    )


@pytest.mark.unit
def test_real_title_text_is_kept():
    # too little would remain: "Earnings - Q3" is not a site suffix
    assert title_key("Earnings - Q3") != title_key("Earnings - Q4")
    # a long last segment is title text, not a site name
    long_tail = "Nvidia beats estimates - and says demand for its newest chips will outlast supply"
    assert "outlast supply" in title_key(long_tail)
    # only the last segment goes: the earlier "- aber richtig" stays in the key
    key = title_key("Symptome online checken mit KI und Chatbots - aber richtig | Gesundheit")
    assert key == "symptome online checken mit ki und chatbots aber richtig"


@pytest.mark.unit
def test_empty_titles_have_no_key():
    assert title_key(None) is None and title_key("") is None and title_key(" - ") is None
