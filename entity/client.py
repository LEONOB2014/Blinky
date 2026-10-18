"""Wikimedia HTTP client: disk cache, tenacity retries, and a rate under 20 requests/second.

Wikimedia's 2026 gateway returns 429 when a client bursts. This client starts slowly, speeds up
only after a streak of successes, and on 429 sleeps for Retry-After and stays slow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from radar.paths import REPO_ROOT, lake

log = logging.getLogger(__name__)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# wbgetentities accepts 50 ids. 20 keeps each payload small enough to cache cleanly.
_ENTITY_BATCH = 20
# Stay strictly under the brief's 20 requests/second ceiling.
MIN_INTERVAL_SECONDS = 0.05
# First minute is cautious. After a clean streak the interval drops, never below FLOOR_INTERVAL.
START_INTERVAL_SECONDS = 6.5
FLOOR_INTERVAL_SECONDS = 0.4


class RetryableStatusError(Exception):
    """A response Wikimedia asked us to send again (429, 5xx, or maxlag)."""

    def __init__(self, response: httpx.Response, retry_after: float | None) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response
        self.retry_after = retry_after


class RateLimiter:
    """Spaces calls. The interval never drops below ``floor`` seconds."""

    def __init__(
        self,
        *,
        start_interval: float = START_INTERVAL_SECONDS,
        floor: float = FLOOR_INTERVAL_SECONDS,
        now: Any = time.monotonic,
        sleep: Any = time.sleep,
    ) -> None:
        if floor < MIN_INTERVAL_SECONDS:
            raise ValueError("interval must stay under 20 requests per second")
        self.interval = start_interval
        self.floor = floor
        self._next = 0.0
        self._ok_streak = 0
        self._locked_slow = False
        self._now = now
        self._sleep = sleep

    def wait(self) -> None:
        now = self._now()
        if now < self._next:
            self._sleep(self._next - now)
            now = self._now()
        self._next = now + self.interval

    def reward(self) -> None:
        """Speed up only after a clean streak, and only once per step."""
        self._ok_streak += 1
        if self._locked_slow:
            return
        target = max(1.0, self.floor)
        if self._ok_streak >= 12 and self.interval > target:
            self.interval = target
            log.info(
                "request interval now %.2fs after %s successes",
                self.interval,
                self._ok_streak,
            )
        elif self._ok_streak >= 52 and self.interval > self.floor:
            self.interval = self.floor
            log.info("request interval now %.2fs", self.floor)

    def penalize(self, retry_after: float | None) -> None:
        """Double the gap after a 429. Tenacity already waits out Retry-After."""
        del retry_after
        self._ok_streak = 0
        self._locked_slow = True
        self.interval = min(30.0, max(self.interval * 2, self.floor))
        log.info("request interval now %.2fs after HTTP 429", self.interval)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _wait_strategy(retry_state: Any) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RetryableStatusError) and exc.retry_after:
        return exc.retry_after
    return wait_exponential_jitter(initial=1, max=30)(retry_state)


def user_agent() -> str:
    """The configured Wikimedia User-Agent. The value is never logged."""
    load_dotenv(REPO_ROOT / ".env")
    value = os.environ.get("WIKIMEDIA_USER_AGENT", "").strip()
    if not value:
        raise RuntimeError("WIKIMEDIA_USER_AGENT is empty; set it in .env")
    return value


def _json_error(body: bytes) -> str | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        code = payload["error"].get("code")
        if isinstance(code, str):
            return code
    return None


class WikimediaClient:
    """GET JSON from Wikidata or the Wikimedia REST API, with a disk cache under the lake."""

    def __init__(self, agent: str, raw_root: Path | None = None) -> None:
        self.raw_root = raw_root or (lake() / "raw")
        self.limiter = RateLimiter()
        # Pageviews 429 below about 1 request/second. Wikidata tolerated 0.40s.
        # Keep this host at 6.5s (about 9/min), under the unidentified 10/min cap.
        self.pageview_limiter = RateLimiter(start_interval=6.5, floor=6.5)
        self.stats: Counter[str] = Counter()
        self._http = httpx.Client(
            headers={"User-Agent": agent, "Api-User-Agent": agent, "Accept": "application/json"},
            timeout=httpx.Timeout(120.0, connect=15.0),
            follow_redirects=True,
        )
        self._parents: dict[str, tuple[str, ...]] = {}

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> WikimediaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @classmethod
    def open(cls) -> WikimediaClient:
        return cls(user_agent())

    def search(self, query: str, language: str) -> dict[str, Any] | None:
        digest = hashlib.sha256(f"{language}\n{query}".encode()).hexdigest()
        cache = self.raw_root / "wikidata" / "wbsearchentities" / language / f"{digest}.json"
        return self._get_json(
            WIKIDATA_API,
            {
                "action": "wbsearchentities",
                "search": query,
                "language": language,
                "format": "json",
                "limit": 5,
                "type": "item",
            },
            cache,
        )

    def entities(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        """Return ``{qid: raw wbgetentities payload}`` for each id, batching uncached ids."""
        found: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for qid in dict.fromkeys(qids):
            cached = self._read_json(self._entity_path(qid))
            if cached is not None:
                self.stats["cache_hits"] += 1
                found[qid] = cached
            else:
                missing.append(qid)
        for start in range(0, len(missing), _ENTITY_BATCH):
            chunk = missing[start : start + _ENTITY_BATCH]
            payload = self._fetch_entity_batch(chunk)
            if payload is None:
                for qid in chunk:
                    one = self._fetch_entity_batch([qid])
                    if one is not None:
                        found.update(one)
                continue
            found.update(payload)
        return found

    def parents(self, qid: str) -> tuple[str, ...]:
        """P279 (subclass of) ids for one class. Cached per QID."""
        if qid in self._parents:
            return self._parents[qid]
        cache = self.raw_root / "wikidata" / "wbgetclaims" / f"{qid}_P279.json"
        payload = self._get_json(
            WIKIDATA_API,
            {
                "action": "wbgetclaims",
                "entity": qid,
                "property": "P279",
                "format": "json",
            },
            cache,
        )
        from entity.claims import claim_ids

        ids = () if payload is None else claim_ids(payload, "P279")
        self._parents[qid] = ids
        return ids

    def get_bytes(self, url: str, cache: Path) -> tuple[int, bytes]:
        """GET one REST URL. Caches 200 and 404. Other final statuses count as failures."""
        cached = self._read_cached(cache)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached
        try:
            response = self._send_with_retry(url, None, self.pageview_limiter)
        except (RetryError, httpx.TransportError, RetryableStatusError):
            self.stats["failed"] += 1
            return 0, b""
        status = response.status_code
        body = response.content
        if status in {200, 404}:
            self._write_cached(cache, status, body)
        if status != 200:
            self.stats["failed"] += 1
        else:
            self.stats["ok"] += 1
        return status, body

    def _entity_path(self, qid: str) -> Path:
        return self.raw_root / "wikidata" / "wbgetentities" / f"{qid}.json"

    def _fetch_entity_batch(self, qids: list[str]) -> dict[str, dict[str, Any]] | None:
        params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels|sitelinks|claims",
            "languages": "es|en|pt",
            "sitefilter": "eswiki|enwiki|ptwiki",
            "format": "json",
        }
        digest = hashlib.sha256("|".join(qids).encode()).hexdigest()
        batch_cache = self.raw_root / "wikidata" / "wbgetentities_batch" / f"{digest}.json"
        payload = self._get_json(WIKIDATA_API, params, batch_cache)
        if payload is None or "entities" not in payload:
            return None
        found: dict[str, dict[str, Any]] = {}
        for qid, entity in payload["entities"].items():
            envelope = {"entities": {qid: entity}, "success": payload.get("success", 1)}
            self._write_json(self._entity_path(qid), envelope)
            found[qid] = envelope
        return found

    def _get_json(self, url: str, params: dict[str, Any], cache: Path) -> dict[str, Any] | None:
        cached = self._read_cached(cache)
        if cached is not None:
            self.stats["cache_hits"] += 1
            status, body = cached
            if status != 200:
                return None
            return json.loads(body)
        try:
            response = self._send_with_retry(url, params)
        except (RetryError, httpx.TransportError, RetryableStatusError):
            self.stats["failed"] += 1
            return None
        status = response.status_code
        body = response.content
        if status == 200 and _json_error(body) is None:
            self._write_cached(cache, status, body)
            self.stats["ok"] += 1
            return json.loads(body)
        if status == 404:
            self._write_cached(cache, status, body)
        self.stats["failed"] += 1
        return None

    def _send_with_retry(
        self,
        url: str,
        params: dict[str, Any] | None,
        limiter: RateLimiter | None = None,
    ) -> httpx.Response:
        chosen = self.limiter if limiter is None else limiter
        retrying = Retrying(
            retry=retry_if_exception_type((httpx.TransportError, RetryableStatusError)),
            wait=_wait_strategy,
            stop=stop_after_attempt(8),
            reraise=True,
        )
        return retrying(self._send_once, url, params, chosen)

    def _send_once(
        self,
        url: str,
        params: dict[str, Any] | None,
        limiter: RateLimiter,
    ) -> httpx.Response:
        limiter.wait()
        self.stats["network"] += 1
        try:
            response = self._http.get(url, params=params)
        except httpx.TransportError:
            self.stats["retried"] += 1
            limiter.penalize(None)
            raise
        if response.status_code in {429, 500, 502, 503, 504}:
            self.stats["retried"] += 1
            if response.status_code == 429:
                self.stats["http_429"] += 1
            retry_after = _retry_after_seconds(response)
            limiter.penalize(retry_after)
            log.info("HTTP %s; backing off", response.status_code)
            raise RetryableStatusError(response, retry_after)
        # maxlag is the database asking us to wait. It is not a rate-limit penalty.
        error_code = _json_error(response.content) if response.status_code == 200 else None
        if error_code in {"maxlag", "readonly"}:
            self.stats["retried"] += 1
            log.info("wikidata %s; retrying", error_code)
            raise RetryableStatusError(response, 5)
        limiter.reward()
        return response

    def _read_cached(self, path: Path) -> tuple[int, bytes] | None:
        code_path = Path(str(path) + ".code")
        if path.exists() and code_path.exists():
            return int(code_path.read_text(encoding="utf-8")), path.read_bytes()
        return None

    def _write_cached(self, path: Path, status: int, body: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        Path(str(path) + ".code").write_text(str(status), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        cached = self._read_cached(path)
        if cached is None or cached[0] != 200:
            return None
        return json.loads(cached[1])

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self._write_cached(path, 200, json.dumps(payload).encode("utf-8"))
