"""The evidence title key, mirrored from bq_sql/s14_topic_evidence_weekly.sql (CTE `keyed`).

Two evidence articles are the same story when their keys match: HTML dash and no-break-space
entities decoded, the trailing site suffix dropped (the last " - X", " | X" or " :: X" segment, X at
most 40 characters without another separator, only when at least 25 characters remain), then
lowercased with every run of non-letters and non-digits collapsed. The data test uses it.
"""

import re

_DASH_ENTITIES = re.compile(r"&#x(?:2012|2013|2014|2015);", re.I)
_SPACE_ENTITIES = re.compile(r"&#x(?:a0|202f);|&nbsp;", re.I)
_SUFFIX = re.compile(r"\s+(?:-|–|—|\||::)\s+[^-–—|:]{1,40}$")
_NON_WORD = re.compile(r"[^\w]+")
MIN_KEPT = 25


def title_key(title: str | None) -> str | None:
    if not title:
        return None
    decoded = _SPACE_ENTITIES.sub(" ", _DASH_ENTITIES.sub(" - ", title))
    stripped = _SUFFIX.sub("", decoded)
    kept = stripped if len(stripped.strip()) >= MIN_KEPT else decoded
    return _NON_WORD.sub(" ", kept.lower()).replace("_", " ").strip() or None
