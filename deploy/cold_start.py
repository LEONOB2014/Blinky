"""Measure a true cold start of the Cloud Run API: wait for idle, then time the first requests.

Cloud Run scales an idle service to zero after roughly 15 minutes (not guaranteed). This script
reads the request logs, waits until the service has had no request for `--idle-min` minutes, then
times `/api/freshness`, `/api/radar` and (with `--chat`) one chat turn, and checks the logs for a
container start after the first request, so a warm instance is never reported as a cold start.
The service URL comes from gcloud at run time and is never printed into git.

    uv run python deploy/cold_start.py --chat            # waits, measures, prints a table
"""

import argparse
import datetime as dt
import os
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values

from radar.paths import REPO_ROOT

SERVICE, REGION = "radar-api", "us-central1"


def project() -> str:
    return os.environ.get("GCP_PROJECT_ID") or dotenv_values(REPO_ROOT / ".env")["GCP_PROJECT_ID"]


def gcloud(*args: str) -> str:
    cmd = ["gcloud", *args, f"--project={project()}"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603


def service_url() -> str:
    return gcloud(
        "run", "services", "describe", SERVICE, f"--region={REGION}", "--format=value(status.url)"
    ).rstrip("/")


def last_request() -> dt.datetime | None:
    out = gcloud(
        "logging", "read",
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
        "AND httpRequest.requestUrl:*",
        "--limit=1", "--freshness=1d", "--format=value(timestamp)",
    )  # fmt: skip
    return dt.datetime.fromisoformat(out.replace("Z", "+00:00")) if out else None


def container_starts_since(since: dt.datetime) -> int:
    out = gcloud(
        "logging", "read",
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
        f'AND timestamp>="{since.strftime("%Y-%m-%dT%H:%M:%SZ")}" '
        'AND textPayload:"Started server process"',  # one line per container start
        "--limit=20", "--format=value(timestamp)",
    )  # fmt: skip
    return len([line for line in out.splitlines() if line.strip()])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--idle-min", type=float, default=17.0)
    ap.add_argument("--chat", action="store_true", help="also time one chat turn (Nebius credit)")
    ap.add_argument("--max-wait-min", type=float, default=60.0)
    args = ap.parse_args(argv)

    deadline = time.time() + args.max_wait_min * 60
    while True:
        last = last_request()
        idle = (dt.datetime.now(dt.UTC) - last).total_seconds() / 60 if last else float("inf")
        print(f"{dt.datetime.now(dt.UTC):%H:%M:%S}Z idle {idle:.1f} min", flush=True)
        if idle >= args.idle_min:
            break
        if time.time() > deadline:
            print("gave up waiting: the service kept receiving requests")
            return 2
        time.sleep(60)

    url = service_url()
    started = dt.datetime.now(dt.UTC)
    rows = []
    client = httpx.Client(timeout=180)
    steps = [("GET /api/freshness (first)", "get", "/api/freshness", None)]
    steps += [("GET /api/radar", "get", "/api/radar", None)]
    steps += [("GET /api/radar (warm)", "get", "/api/radar", None)]
    if args.chat:
        body = {"message": "¿Qué tema de IA sube esta semana y por qué?"}
        steps.append(("POST /api/chat", "post", "/api/chat", body))
    for name, method, path, body in steps:
        t0 = time.perf_counter()
        resp = client.post(url + path, json=body) if method == "post" else client.get(url + path)
        rows.append((name, resp.status_code, time.perf_counter() - t0))
    time.sleep(20)  # let the logs arrive
    starts = container_starts_since(started - dt.timedelta(seconds=5))
    print(f"\nmeasured at {started:%Y-%m-%d %H:%M}Z after {idle:.1f} min idle")
    for name, code, secs in rows:
        print(f"{name:28} HTTP {code}  {secs:6.2f} s")
    print(
        f"container starts logged after the first request: {starts} "
        f"({'cold start confirmed' if starts else 'no start logged: the instance was warm'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
