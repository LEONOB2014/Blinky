"""Pre-demo check of the public radar: the Netlify site and the Cloud Run API, with latencies.

The API URL is read at run time (`RADAR_API_URL`, else `gcloud run services describe radar-api`),
never stored in git. Only `--chat` sends one real turn to the Media Master, which spends Nebius
credit; the rest are cheap reads.

    make demo-check                 # reads only
    make demo-check ARGS=--chat     # plus one chat turn
"""

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import dotenv_values

from radar.paths import REPO_ROOT

SITE = "https://radar-senal-temprana.netlify.app"
SERVICE, REGION = "radar-api", "us-central1"
CHAT_QUESTION = "¿Qué tema de IA sube esta semana y por qué?"


def api_url() -> str:
    if os.environ.get("RADAR_API_URL"):
        return os.environ["RADAR_API_URL"].rstrip("/")
    project = os.environ.get("GCP_PROJECT_ID") or dotenv_values(REPO_ROOT / ".env").get(
        "GCP_PROJECT_ID"
    )
    cmd = ["gcloud", "run", "services", "describe", SERVICE, f"--region={REGION}"]
    cmd += [f"--project={project}"] if project else []
    out = subprocess.run(
        [*cmd, "--format=value(status.url)"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip().rstrip("/")


class Checks:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, float, str]] = []
        self.client = httpx.Client(timeout=120, follow_redirects=True)

    def run(self, name: str, fn: Callable[[], tuple[bool, str]]) -> None:
        start = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as err:  # noqa: BLE001 (a failed check is reported, not raised)
            ok, detail = False, f"{type(err).__name__}: {err}"[:120]
        self.rows.append((name, ok, time.perf_counter() - start, detail))

    def get(self, url: str) -> httpx.Response:
        return self.client.get(url)

    def report(self) -> bool:
        width = max(len(r[0]) for r in self.rows)
        print(f"{'check':{width}}  result  seconds  detail")
        for name, ok, secs, detail in self.rows:
            print(f"{name:{width}}  {'PASS' if ok else 'FAIL':6}  {secs:7.2f}  {detail}")
        passed = sum(ok for _, ok, _, _ in self.rows)
        print(f"\n{passed}/{len(self.rows)} passed")
        return passed == len(self.rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chat", action="store_true", help="send one real chat turn (Nebius credit)")
    args = ap.parse_args(argv)
    c = Checks()
    api = api_url()
    state: dict[str, Any] = {}

    def site_page() -> tuple[bool, str]:
        r = c.get(f"{SITE}/")
        return r.status_code == 200 and "<div id=" in r.text, f"HTTP {r.status_code}"

    def site_static_top10() -> tuple[bool, str]:
        r = c.get(f"{SITE}/data/radar/latest.json")
        state["static"] = [x["topic_id"] for x in r.json()] if r.status_code == 200 else []
        return len(state["static"]) == 10, f"HTTP {r.status_code}, {len(state['static'])} topics"

    def api_freshness() -> tuple[bool, str]:
        r = c.get(f"{api}/api/freshness")
        body = r.json()
        week = body["tables"].get("topic_scores_weekly")
        ok = r.status_code == 200 and body["profile"] == "full" and bool(week)
        daily = body["tables"].get("daily_topic")
        return ok, f"profile {body['profile']}, scores {week}, daily {daily}"

    def api_top10() -> tuple[bool, str]:
        r = c.get(f"{api}/api/radar")
        state["live"] = [x["topic_id"] for x in r.json()] if r.status_code == 200 else []
        top = state["live"][0] if state["live"] else "-"
        return len(state["live"]) == 10, f"HTTP {r.status_code}, #1 {top}"

    def live_matches_static() -> tuple[bool, str]:
        same = state.get("live") == state.get("static")
        return same, "same top 10" if same else "live and static differ: re-run make deploy-static"

    def api_timeline() -> tuple[bool, str]:
        topic = state["live"][0]
        r = c.get(f"{api}/api/topic/{quote(topic, safe='')}/timeline")
        days = len({x["dt"] for x in r.json()}) if r.status_code == 200 else 0
        return r.status_code == 200 and days > 0, f"{topic}: {days} days"

    def api_ring() -> tuple[bool, str]:
        topic = state["live"][0]
        r = c.get(f"{api}/api/topic/{quote(topic, safe='')}/context")
        ring = r.json() if r.status_code == 200 else []
        persons = sum(1 for x in ring if x["neighbor"].startswith("per:"))
        return bool(ring) and not persons, f"{topic}: {len(ring)} neighbours, {persons} persons"

    def api_chat() -> tuple[bool, str]:
        r = c.client.post(f"{api}/api/chat", json={"message": CHAT_QUESTION})
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:80]}"
        body = r.json()
        ok = bool(body.get("answer_es")) and bool(body.get("trace"))
        steps, cards = len(body.get("trace", [])), len(body.get("decision_cards", []))
        return ok, f"{steps} trace steps, {cards} cards"

    c.run("site: page", site_page)
    c.run("site: static top 10", site_static_top10)
    c.run("api: freshness", api_freshness)
    c.run("api: top 10", api_top10)
    c.run("live top 10 == static top 10", live_matches_static)
    c.run("api: timeline of #1", api_timeline)
    c.run("api: 1-hop ring of #1", api_ring)
    if args.chat:
        c.run("api: one chat turn", api_chat)
    return 0 if c.report() else 1


if __name__ == "__main__":
    sys.exit(main())
