"""Curator article classifier cascade: local calibrated student + Jev when in doubt (WS2b).

Implements:
1. OpenRouter Decisions API client (``POST https://openrouter.ai/api/alpha/decisions``,
   model ``typesafe/jev-1.14``) with ``noul`` questions for ``is_ai`` and ``brand_safe`` and
   ``choice`` question for ``main_subtopic``.
2. Spend guard enforcing ``JEV_RUN_CAP_USD`` (default $1.00) and ``JEV_DEV_CAP_USD`` (default
   $3.00) from ``reports/jev_ledger.csv`` (time, model, input tokens, cost, latency; no article
   text), plus deterministic disk caching keyed on ``(model, state, questions)``.
3. Validation-split threshold curve and per-confidence-bin paired comparison between student and
   Jev against panel labels (routing a bin to Jev only where Jev measurably beats the student).
4. Public ``classify(article)`` interface returning
   ``{decision, probability, decided_by: "student"|"jev", cost_usd}``.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import polars as pl
from dotenv import load_dotenv
from pipelines.taxonomy import student, teacher

from radar.paths import REPO_ROOT, lake

OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "typesafe/jev-1.14"
DEFAULT_RUN_CAP_USD = 1.00
DEFAULT_DEV_CAP_USD = 3.00
ESTIMATED_MAX_CALL_COST_USD = 0.0002

LEDGER_PATH = REPO_ROOT / "reports" / "jev_ledger.csv"
LEDGER_COLUMNS = ["ts_utc", "model", "input_tokens", "cost_usd", "latency_ms"]

_LEDGER_LOCK = threading.Lock()
_RUN_SPEND_USD = 0.0

JEV_QUESTIONS: dict[str, Any] = {
    "is_ai": {
        "type": "noul",
        "instructions": "Is this news article genuinely about Artificial Intelligence?",
        "criteria": {
            "true": (
                "The article is specifically about Artificial Intelligence, LLMs, generative AI, "
                "AI agents, machine learning, AI chips/datacenters, AI regulation/safety, or "
                "AI business adoption and applications."
            ),
            "false": (
                "The article is general IT, cloud, smartphones, cybersecurity, gaming, stock "
                "tickers, or general news about a tech company where AI is not a main subject."
            ),
        },
    },
    "brand_safe": {
        "type": "noul",
        "instructions": (
            "Is this topic brand-safe for a B2B executive education brand (30X) "
            "to discuss on LinkedIn?"
        ),
        "criteria": {
            "true": (
                "Appropriate business, technology, policy, science, labour, climate, "
                "or industry news."
            ),
            "false": "Explicit/NSFW content, graphic violence/gore, hate speech, or illegal scams.",
        },
    },
    "main_subtopic": {
        "type": "choice",
        "instructions": "Which of the 12 AI subtopics best describes this article?",
        "criteria": {
            "agents": "Autonomous AI agents, agentic workflows, tool-using copilots.",
            "llms_models": (
                "Foundation models, LLMs, multimodal models, model benchmarks and releases."
            ),
            "chips_infra": (
                "GPUs, AI chips, semiconductors, AI data centers, compute infrastructure."
            ),
            "regulation_policy": (
                "AI legislation, government policy, copyright law, antitrust, governance."
            ),
            "education": "AI in schools, universities, student learning, executive upskilling.",
            "jobs_work": "Workforce impact, automation of jobs, hiring, layoffs, workplace skills.",
            "business_adoption": (
                "Enterprise AI deployment, ROI, productivity, corporate workflows."
            ),
            "safety_risk": "AI safety, alignment, deepfakes, misinformation, cyber attacks, fraud.",
            "creative_media": "Generative AI in art, music, film, media, content creation.",
            "health_science": (
                "AI in healthcare, medicine, drug discovery, biology, scientific research."
            ),
            "funding_markets": (
                "Venture capital, AI startups, IPOs, valuations, stock market moves."
            ),
            "energy_climate": (
                "Data-center power grid, nuclear/renewable energy for AI, water use, climate."
            ),
        },
    },
}


class JevCapExceededError(RuntimeError):
    """Raised before a Jev call that would exceed the per-run or cumulative development cap."""


def jev_config() -> tuple[str, float, float]:
    """Return (jev_model, run_cap_usd, dev_cap_usd) from environment / .env."""
    load_dotenv(REPO_ROOT / ".env")
    model = (os.environ.get("JEV_MODEL") or "").strip() or DEFAULT_JEV_MODEL
    run_cap = float((os.environ.get("JEV_RUN_CAP_USD") or "").strip() or DEFAULT_RUN_CAP_USD)
    dev_cap = float((os.environ.get("JEV_DEV_CAP_USD") or "").strip() or DEFAULT_DEV_CAP_USD)
    return model, run_cap, dev_cap


def openrouter_api_key() -> str:
    load_dotenv(REPO_ROOT / ".env")
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
    return key


def read_jev_ledger(path: Path = LEDGER_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cumulative_jev_spend_usd(path: Path = LEDGER_PATH) -> float:
    rows = read_jev_ledger(path)
    return round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 8)


def append_jev_ledger(
    model: str,
    input_tokens: int,
    cost_usd: float,
    latency_ms: int,
    path: Path = LEDGER_PATH,
    now: dt.datetime | None = None,
) -> None:
    now = now or dt.datetime.now(dt.UTC)
    row = {
        "ts_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
        "input_tokens": str(int(input_tokens)),
        "cost_usd": f"{cost_usd:.8f}",
        "latency_ms": str(int(latency_ms)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow(row)


def build_jev_state(article: dict[str, Any]) -> dict[str, str]:
    """Construct the structured state dictionary sent to Jev."""
    return {
        "title": (article.get("title") or "").strip()[:300],
        "url_path": teacher.clean_url_path(article.get("url") or ""),
        "themes": (article.get("top_themes") or "").strip()[:280],
        "organizations": (article.get("top_orgs") or "").strip()[:180],
        "language": (article.get("lang") or "eng").strip(),
    }


def cache_key(model: str, state: dict[str, Any], questions: dict[str, Any]) -> str:
    payload = json.dumps(
        {"model": model, "state": state, "questions": questions},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_jev_cache(cache_path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = cache_path or (lake() / "labels" / "jev_cache.jsonl")
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "key" in rec:
                    out[rec["key"]] = rec
            except json.JSONDecodeError:
                continue
    return out


def _extract_noul(ans: Any, default: float = 0.5) -> float:
    if isinstance(ans, int | float) and not isinstance(ans, bool):
        return float(ans)
    if isinstance(ans, dict):
        for k in ("noul", "probability", "value", "score"):
            v = ans.get(k)
            if isinstance(v, int | float) and not isinstance(v, bool):
                return float(v)
    return default


def _extract_choice(ans: Any, default: str = "llms_models") -> tuple[str, dict[str, float]]:
    if isinstance(ans, str):
        return ans, {}
    if isinstance(ans, dict):
        ch = ans.get("choice") or ans.get("value") or default
        probs = ans.get("probabilities") or {}
        return str(ch), {str(k): float(v) for k, v in probs.items() if isinstance(v, int | float)}
    return default, {}


def call_jev(
    article: dict[str, Any],
    client: httpx.Client | None = None,
    cache: dict[str, dict[str, Any]] | None = None,
    cache_path: Path | None = None,
    ledger_path: Path = LEDGER_PATH,
    questions: dict[str, Any] = JEV_QUESTIONS,
) -> dict[str, Any]:
    """Query Jev via OpenRouter Decisions API with cache and spend guard."""
    global _RUN_SPEND_USD
    model, run_cap, dev_cap = jev_config()
    state = build_jev_state(article)
    key = cache_key(model, state, questions)

    c_path = cache_path or (lake() / "labels" / "jev_cache.jsonl")
    if cache is None:
        cache = load_jev_cache(c_path)
    if key in cache:
        hit = dict(cache[key])
        hit["cached"] = True
        hit["cost_usd"] = 0.0
        return hit

    with _LEDGER_LOCK:
        cum_spend = cumulative_jev_spend_usd(ledger_path)
        if run_cap < _RUN_SPEND_USD + ESTIMATED_MAX_CALL_COST_USD:
            raise JevCapExceededError(
                f"Jev run spend ${_RUN_SPEND_USD:.4f} would exceed JEV_RUN_CAP_USD=${run_cap:.2f}"
            )
        if cum_spend + ESTIMATED_MAX_CALL_COST_USD > dev_cap:
            raise JevCapExceededError(
                f"Jev cumulative spend ${cum_spend:.4f} would exceed JEV_DEV_CAP_USD=${dev_cap:.2f}"
            )

    body = {"model": model, "state": state, "questions": questions}
    own_client = client is None
    if own_client:
        api_key = openrouter_api_key()
        client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )
    try:
        t0 = time.perf_counter()
        last_exc: Exception | None = None
        data: dict[str, Any] = {}
        latency_ms = 0
        for attempt in range(4):
            try:
                resp = client.post(OPENROUTER_DECISIONS_URL, json=body)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(0.8 * (2**attempt))
                    continue
                resp.raise_for_status()
                latency_ms = int((time.perf_counter() - t0) * 1000)
                data = resp.json()
                break
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(0.8 * (2**attempt))
        else:
            raise RuntimeError(f"Jev call failed after retries: {last_exc}")
    finally:
        if own_client and client is not None:
            client.close()

    answers = data.get("answers") or data.get("decisions") or {}
    usage = data.get("usage") or {}
    in_tok = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    cost_usd = float(usage.get("cost") or 0.0)
    resolved_model = str(data.get("model") or model)

    p_ai = _extract_noul(answers.get("is_ai"), default=0.5)
    p_bs = _extract_noul(answers.get("brand_safe"), default=0.95)
    main_st, st_probs = _extract_choice(answers.get("main_subtopic"), default="llms_models")

    is_ai = p_ai >= 0.5
    brand_safe = p_bs >= 0.5
    if is_ai:
        extra = [st for st, p in st_probs.items() if p >= 0.25 and st in teacher.SUBTOPICS]
        subtopics = (
            sorted(set([main_st] + extra))[:3] if main_st in teacher.SUBTOPICS else extra[:3]
        )
    else:
        subtopics = []

    rec = {
        "key": key,
        "gkg_id": article.get("gkg_id", ""),
        "model": resolved_model,
        "is_ai_prob": round(p_ai, 4),
        "is_ai": is_ai,
        "brand_safe_prob": round(p_bs, 4),
        "brand_safe": brand_safe,
        "main_subtopic": main_st if is_ai else "none",
        "subtopics": subtopics,
        "input_tokens": in_tok,
        "cost_usd": round(cost_usd, 8),
        "latency_ms": latency_ms,
        "cached": False,
    }

    with _LEDGER_LOCK:
        _RUN_SPEND_USD += cost_usd
        append_jev_ledger(resolved_model, in_tok, cost_usd, latency_ms, path=ledger_path)
        c_path.parent.mkdir(parents=True, exist_ok=True)
        with c_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        cache[key] = rec

    return rec


def batch_call_jev(
    rows: list[dict[str, Any]],
    workers: int = 12,
    cache_path: Path | None = None,
    ledger_path: Path = LEDGER_PATH,
) -> dict[str, dict[str, Any]]:
    """Run Jev on a batch of articles concurrently, respecting the spend guard and cache."""
    c_path = cache_path or (lake() / "labels" / "jev_cache.jsonl")
    cache = load_jev_cache(c_path)
    api_key = openrouter_api_key()
    results: dict[str, dict[str, Any]] = {}

    with (
        httpx.Client(
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        ) as client,
        concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        fut_map = {
            pool.submit(
                call_jev,
                r,
                client=client,
                cache=cache,
                cache_path=c_path,
                ledger_path=ledger_path,
            ): r["gkg_id"]
            for r in rows
        }
        for fut in concurrent.futures.as_completed(fut_map):
            gid = fut_map[fut]
            results[gid] = fut.result()
    return results


def paired_accuracy_bootstrap(
    y_true: np.ndarray,
    pred_student: np.ndarray,
    pred_jev: np.ndarray,
    n_boot: int = 500,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Return (delta_acc = acc_jev - acc_student, ci95_low, ci95_high) via paired bootstrap."""
    if len(y_true) == 0:
        return 0.0, 0.0, 0.0
    s_ok = (pred_student == y_true).astype(float)
    j_ok = (pred_jev == y_true).astype(float)
    diff = j_ok - s_ok
    delta = float(np.mean(diff))
    if len(diff) < 2:
        return round(delta, 4), round(delta, 4), round(delta, 4)
    rng = np.random.default_rng(seed)
    n = len(diff)
    boot = [float(np.mean(diff[rng.integers(0, n, size=n)])) for _ in range(n_boot)]
    return (
        round(delta, 4),
        round(float(np.percentile(boot, 2.5)), 4),
        round(float(np.percentile(boot, 97.5)), 4),
    )


def evaluate_bins_and_thresholds(
    val_df: pl.DataFrame,
    jev_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare student vs Jev per confidence bin and across target Jev share thresholds on val."""
    rows = val_df.to_dicts()
    rows = [r for r in rows if r["gkg_id"] in jev_map]

    y_true = np.array([1 if r["is_ai"] else 0 for r in rows])
    p_stud = np.array([float(r["student_is_ai_prob"]) for r in rows])
    pred_stud = (p_stud >= 0.5).astype(int)
    p_jev = np.array([float(jev_map[r["gkg_id"]]["is_ai_prob"]) for r in rows])
    pred_jev = (p_jev >= 0.5).astype(int)
    dist = np.abs(p_stud - 0.5)

    # 1. Per-confidence-bin comparison (5 bins of |p - 0.5|)
    bin_edges = [(0.0, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 0.5001)]
    bins_report: list[dict[str, Any]] = []
    routed_bins: list[str] = []

    for low_d, high_d in bin_edges:
        mask = (dist >= low_d) & (dist < high_d)
        n_bin = int(mask.sum())
        p_band = (
            f"[{0.5 - high_d:.2f}, {0.5 - low_d:.2f}) U "
            f"({0.5 + low_d:.2f}, {0.5 + min(0.5, high_d):.2f}]"
        )
        label = f"|p-0.5| in [{low_d:.2f}, {min(0.5, high_d):.2f})"
        if n_bin == 0:
            bins_report.append({"bin": label, "prob_band": p_band, "n": 0})
            continue
        yt = y_true[mask]
        ps = pred_stud[mask]
        pj = pred_jev[mask]
        acc_s = float(np.mean(ps == yt))
        acc_j = float(np.mean(pj == yt))
        f1_s = float(student.f1_score(yt, ps, zero_division=0))
        f1_j = float(student.f1_score(yt, pj, zero_division=0))
        delta, ci_lo, ci_hi = paired_accuracy_bootstrap(yt, ps, pj)
        # Route bin to Jev only if Jev's accuracy on that bin beats the student's on val
        beats = bool(acc_j > acc_s)
        if beats:
            routed_bins.append(label)
        bins_report.append(
            {
                "bin": label,
                "prob_band": p_band,
                "dist_low": low_d,
                "dist_high": round(min(0.5, high_d), 2),
                "n": n_bin,
                "share_of_val": round(n_bin / max(1, len(rows)), 4),
                "student_accuracy": round(acc_s, 4),
                "jev_accuracy": round(acc_j, 4),
                "student_f1": round(f1_s, 4),
                "jev_f1": round(f1_j, 4),
                "paired_acc_delta_jev_minus_student": delta,
                "paired_acc_delta_ci95": [ci_lo, ci_hi],
                "route_to_jev": beats,
            }
        )

    # Determine [t_low, t_high] from routed bins (or [0.5, 0.5] if Jev never beats student)
    if routed_bins:
        max_routed_d = max(b["dist_high"] for b in bins_report if b.get("route_to_jev"))

        t_low = round(0.5 - max_routed_d, 4)
        t_high = round(0.5 + max_routed_d, 4)
    else:
        t_low, t_high = 0.5, 0.5

    # 2. Threshold curve across symmetric [0.5 - d, 0.5 + d] windows for target Jev shares
    curve: list[dict[str, Any]] = []
    mean_jev_cost = float(np.mean([jev_map[r["gkg_id"]].get("cost_usd") or 0.000045 for r in rows]))
    if mean_jev_cost <= 0:
        mean_jev_cost = 0.000045

    for target_share in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]:
        if target_share <= 0.0:
            tl, th = 0.5, 0.5
            use_jev = np.zeros(len(rows), dtype=bool)
        elif target_share >= 1.0:
            tl, th = 0.0, 1.0
            use_jev = np.ones(len(rows), dtype=bool)
        else:
            d_thresh = float(np.quantile(dist, target_share))
            tl, th = round(0.5 - d_thresh, 4), round(0.5 + d_thresh, 4)
            use_jev = (p_stud >= tl) & (p_stud <= th)

        c_prob = np.where(use_jev, p_jev, p_stud)
        m = student.binary_metrics(y_true, c_prob)
        actual_share = float(np.mean(use_jev))
        curve.append(
            {
                "target_jev_share": target_share,
                "actual_jev_share": round(actual_share, 4),
                "t_low": tl,
                "t_high": th,
                "f1": m["f1"],
                "f1_ci95": m["f1_ci95"],
                "precision": m["precision"],
                "recall": m["recall"],
                "cost_per_1000_articles_usd": round(actual_share * 1000.0 * mean_jev_cost, 4),
            }
        )

    # Chosen cascade metrics on val
    chosen_use_jev = (
        (p_stud >= t_low) & (p_stud <= t_high)
        if t_low < t_high
        else np.zeros(len(rows), dtype=bool)
    )
    chosen_prob = np.where(chosen_use_jev, p_jev, p_stud)
    chosen_metrics = student.binary_metrics(y_true, chosen_prob)
    chosen_share = float(np.mean(chosen_use_jev))

    return {
        "val_n": len(rows),
        "student_only_val": student.binary_metrics(y_true, p_stud),
        "jev_only_val": student.binary_metrics(y_true, p_jev),
        "confidence_bins": bins_report,
        "routed_bins": routed_bins,
        "selected_thresholds": {
            "t_low": t_low,
            "t_high": t_high,
            "jev_share": round(chosen_share, 4),
            "cost_per_1000_articles_usd": round(chosen_share * 1000.0 * mean_jev_cost, 4),
            "cascade_val_metrics": chosen_metrics,
        },
        "threshold_curve": curve,
        "mean_jev_call_cost_usd": round(mean_jev_cost, 8),
    }


_CACHED_BUNDLE: dict[str, Any] | None = None
_CACHED_THRESHOLDS: tuple[float, float] | None = None


def _get_bundle_and_thresholds() -> tuple[dict[str, Any], float, float]:
    global _CACHED_BUNDLE, _CACHED_THRESHOLDS
    model_dir = lake() / "models" / "curator"
    if _CACHED_BUNDLE is None:
        _CACHED_BUNDLE = student.load_student_bundle(model_dir / "student_bundle.joblib")
    if _CACHED_THRESHOLDS is None:
        cfg_path = model_dir / "cascade_config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            st = cfg.get("selected_thresholds") or {}
            _CACHED_THRESHOLDS = (float(st.get("t_low", 0.5)), float(st.get("t_high", 0.5)))
        else:
            _CACHED_THRESHOLDS = (0.5, 0.5)
    return _CACHED_BUNDLE, _CACHED_THRESHOLDS[0], _CACHED_THRESHOLDS[1]


def classify(
    article: dict[str, Any],
    bundle: dict[str, Any] | None = None,
    t_low: float | None = None,
    t_high: float | None = None,
    embedding: np.ndarray | None = None,
) -> dict[str, Any]:
    """Classify one article with the student, routing to Jev only when prob in [t_low, t_high].

    Returns ``{decision, probability, decided_by: "student"|"jev", cost_usd}`` plus top-level
    convenience keys ``is_ai``, ``brand_safe``, ``subtopics``.
    """
    if bundle is None or t_low is None or t_high is None:
        b_loaded, tl_loaded, th_loaded = _get_bundle_and_thresholds()
        bundle = bundle or b_loaded
        t_low = tl_loaded if t_low is None else t_low
        t_high = th_loaded if t_high is None else t_high

    if embedding is None:
        emb_mat, _ = student.embed_rows([article])
    else:
        emb_mat = embedding.reshape(1, -1)

    stud_pred = student.predict_with_bundle(bundle, [article], emb_mat)[0]
    p_stud = float(stud_pred["student_is_ai_prob"])

    in_doubt = (t_low < t_high) and (t_low <= p_stud <= t_high)
    if not in_doubt:
        decision = {
            "is_ai": bool(stud_pred["student_is_ai"]),
            "brand_safe": bool(stud_pred["student_brand_safe"]),
            "subtopics": list(stud_pred["student_subtopics"]),
            "main_subtopic": str(stud_pred["student_main_subtopic"]),
        }
        return {
            "decision": decision,
            "is_ai": decision["is_ai"],
            "brand_safe": decision["brand_safe"],
            "subtopics": decision["subtopics"],
            "probability": round(p_stud, 4),
            "decided_by": "student",
            "cost_usd": 0.0,
        }

    jev_res = call_jev(article)
    decision = {
        "is_ai": bool(jev_res["is_ai"]),
        "brand_safe": bool(jev_res["brand_safe"]),
        "subtopics": list(jev_res["subtopics"]),
        "main_subtopic": str(jev_res["main_subtopic"]),
    }
    return {
        "decision": decision,
        "is_ai": decision["is_ai"],
        "brand_safe": decision["brand_safe"],
        "subtopics": decision["subtopics"],
        "probability": round(float(jev_res["is_ai_prob"]), 4),
        "decided_by": "jev",
        "cost_usd": float(jev_res["cost_usd"]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args(argv)

    model_dir = lake() / "models" / "curator"
    val_path = model_dir / "val_predictions.parquet"
    if not val_path.exists():
        raise SystemExit(f"Missing {val_path}; run pipelines/taxonomy/student.py first")

    val_df = pl.read_parquet(val_path)
    val_rows = val_df.to_dicts()
    jev_map = batch_call_jev(val_rows, workers=args.workers)

    cascade_summary = evaluate_bins_and_thresholds(val_df, jev_map)

    test_path = model_dir / "test_predictions.parquet"
    if test_path.exists():
        test_df = pl.read_parquet(test_path)
        test_rows = test_df.to_dicts()
        tl = float(cascade_summary["selected_thresholds"]["t_low"])
        th = float(cascade_summary["selected_thresholds"]["t_high"])
        doubt_test_rows = [
            r for r in test_rows if tl < th and tl <= float(r["student_is_ai_prob"]) <= th
        ]
        jev_test_map = (
            batch_call_jev(doubt_test_rows, workers=args.workers) if doubt_test_rows else {}
        )
        y_te = np.array([1 if r["is_ai"] else 0 for r in test_rows])
        p_te_stud = np.array([float(r["student_is_ai_prob"]) for r in test_rows])
        p_te_casc = np.array(
            [
                float(jev_test_map[r["gkg_id"]]["is_ai_prob"])
                if r["gkg_id"] in jev_test_map
                else float(r["student_is_ai_prob"])
                for r in test_rows
            ]
        )
        cascade_summary["selected_thresholds"]["test_jev_routed_n"] = len(doubt_test_rows)
        cascade_summary["selected_thresholds"]["test_jev_share"] = round(
            len(doubt_test_rows) / max(1, len(test_rows)), 4
        )
        cascade_summary["selected_thresholds"]["student_only_test_metrics"] = (
            student.binary_metrics(y_te, p_te_stud)
        )
        cascade_summary["selected_thresholds"]["cascade_test_metrics"] = student.binary_metrics(
            y_te, p_te_casc
        )

    cascade_summary["ledger_cumulative_spend_usd"] = cumulative_jev_spend_usd()
    cascade_summary["ledger_total_calls"] = len(read_jev_ledger())

    (model_dir / "cascade_config.json").write_text(
        json.dumps(cascade_summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(cascade_summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
