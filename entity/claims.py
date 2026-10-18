"""Read Wikidata claim ids out of a real API payload."""

from __future__ import annotations


def claim_ids(container: dict, prop: str) -> tuple[str, ...]:
    """Ids of one property. ``container`` is an entity or a wbgetclaims payload."""
    claims = container.get("claims", container)
    if not isinstance(claims, dict):
        return ()
    found: list[str] = []
    for statement in claims.get(prop) or []:
        if not isinstance(statement, dict):
            continue
        snak = statement.get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        value = (snak.get("datavalue") or {}).get("value")
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            found.append(value["id"])
    return tuple(found)
