"""Teacher panel labeling and 100-article pilot on Nebius Token Factory (WS2b).

Implements:
1. Licence registry for candidate open-weight teachers on Nebius (only permissive licences allowing
   training on outputs, such as Apache-2.0 and MIT, qualify).
2. 100-article stratified pilot across all 5 candidate teachers, measuring latency, token usage,
   estimated cost, JSON validity rate (dropping any model with >5% invalid JSON), and agreement.
3. Two-family teacher panel + 3rd tie-breaker on the 4,000 sampled articles (and active-learning
   rounds), cached resumably by ``gkg_id`` under ``lake/labels/teacher/``.
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import polars as pl
import yaml
from dotenv import load_dotenv

from radar.paths import REPO_ROOT, lake

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

# Candidate teacher models on Nebius with verified Hugging Face model-card licences and
# estimated per-1M-token rates (USD, estimate from Nebius Token Factory public pricing).
TEACHER_CATALOG: dict[str, dict[str, Any]] = {
    "Qwen/Qwen3-235B-A22B-Instruct-2507": {
        "slug": "qwen3_235b",
        "family": "qwen",
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507/blob/main/LICENSE",
        "trainable_outputs": True,
        "input_usd_per_1m": 0.20,
        "output_usd_per_1m": 0.60,
    },
    "openai/gpt-oss-120b": {
        "slug": "gpt_oss_120b",
        "family": "gpt-oss",
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/openai/gpt-oss-120b/blob/main/README.md",
        "trainable_outputs": True,
        "input_usd_per_1m": 0.15,
        "output_usd_per_1m": 0.60,
    },
    "deepseek-ai/DeepSeek-V4-Pro": {
        "slug": "deepseek_v4_pro",
        "family": "deepseek",
        "license": "MIT",
        "license_url": "https://huggingface.co/deepseek-ai",
        "trainable_outputs": True,
        "input_usd_per_1m": 0.30,
        "output_usd_per_1m": 0.90,
    },
    "Qwen/Qwen3.5-397B-A17B": {
        "slug": "qwen3_5_397b",
        "family": "qwen",
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Qwen/Qwen3.5-397B-A17B/blob/main/LICENSE",
        "trainable_outputs": True,
        "input_usd_per_1m": 0.40,
        "output_usd_per_1m": 1.20,
    },
    "Qwen/Qwen3-30B-A3B-Instruct-2507": {
        "slug": "qwen3_30b",
        "family": "qwen",
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507/blob/main/LICENSE",
        "trainable_outputs": True,
        "input_usd_per_1m": 0.10,
        "output_usd_per_1m": 0.30,
    },
}


def valid_subtopics() -> frozenset[str]:
    tax = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
    return frozenset(tax["subtopics"].keys())


SUBTOPICS = valid_subtopics()
SUBTOPIC_LIST_STR = ", ".join(sorted(SUBTOPICS))

SYSTEM_PROMPT = (
    "You are an expert news taxonomy curator for an AI intelligence radar serving Latin American "
    "executives (30X). Classify the given news article from its title, URL path, GKG themes, and "
    "organizations.\n"
    "Respond ONLY with a single valid JSON object (no markdown fences, no commentary) matching:\n"
    '{"is_ai": <bool>, "subtopics": [<zero or more valid subtopic IDs>], '
    '"brand_safe": <bool>, "confidence": <float 0.0 to 1.0>}\n\n'
    "Rules:\n"
    "1. is_ai: true ONLY if the article is genuinely about Artificial Intelligence (LLMs, "
    "generative AI, AI agents, machine learning, AI chips/datacenters, AI regulation/safety, "
    "AI business adoption/investments, or AI in science/health/education/climate/work). "
    "General IT, cybersecurity, cloud, smartphones, gadgets, gaming, stock tickers, or general "
    "news about tech companies (Google, Apple, Microsoft, Amazon, Meta, Tesla) that is NOT "
    "specifically about AI must be false.\n"
    f"2. subtopics: array of 0 to 3 IDs from [{SUBTOPIC_LIST_STR}]. "
    "Must be [] when is_ai is false.\n"
    "3. brand_safe: true if appropriate for a B2B executive education brand to discuss on "
    "LinkedIn (business, technology, policy, science, labour, climate, cybersecurity news "
    "are brand_safe=true); false ONLY for explicit/NSFW/adult content, graphic violence/gore, "
    "hate speech, or illegal scams.\n"
    "4. confidence: your calibrated probability (0.0 to 1.0) that your is_ai label is correct."
)


@dataclass(frozen=True)
class ParsedLabel:
    is_ai: bool
    subtopics: list[str]
    brand_safe: bool
    confidence: float


def clean_url_path(url: str) -> str:
    """Extract domain + path from URL, trimming query strings and fragments."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").removeprefix("www.")
        path = parsed.path or ""
        return f"{host}{path}"[:240]
    except ValueError:
        return url[:240]


def format_article_prompt(row: dict[str, Any]) -> str:
    """Build the compact article prompt from title, URL path, top themes, and orgs."""
    title = (row.get("title") or "").strip()[:300]
    url_path = clean_url_path(row.get("url") or "")
    themes = (row.get("top_themes") or "").strip()[:300]
    orgs = (row.get("top_orgs") or "").strip()[:200]
    lang = (row.get("lang") or "eng").strip()
    return (
        f"Language: {lang}\n"
        f"Title: {title}\n"
        f"URL path: {url_path}\n"
        f"Themes: {themes or 'none'}\n"
        f"Organizations: {orgs or 'none'}"
    )


JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_and_validate_label(raw_text: str | None) -> ParsedLabel | None:
    """Validate teacher JSON output against the contract; return None if invalid."""
    if not raw_text:
        return None
    text = raw_text.strip()
    # Strip <think>...</think> blocks if any reasoning model includes them
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = JSON_OBJ_RE.search(text)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    is_ai = obj.get("is_ai")
    brand_safe = obj.get("brand_safe")
    subtopics = obj.get("subtopics")
    confidence = obj.get("confidence")

    if not isinstance(is_ai, bool) or not isinstance(brand_safe, bool):
        return None
    if not isinstance(subtopics, list) or not all(isinstance(s, str) for s in subtopics):
        return None
    # Filter/validate subtopic IDs
    invalid = [s for s in subtopics if s not in SUBTOPICS]
    if invalid:
        return None
    norm_subtopics = sorted(set(subtopics)) if is_ai else []
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        return None
    conf_val = float(confidence)
    if not (0.0 <= conf_val <= 1.0):
        return None
    return ParsedLabel(
        is_ai=is_ai,
        subtopics=norm_subtopics,
        brand_safe=brand_safe,
        confidence=round(conf_val, 4),
    )


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    spec = TEACHER_CATALOG.get(model, {"input_usd_per_1m": 0.20, "output_usd_per_1m": 0.60})
    return round(
        (prompt_tokens * spec["input_usd_per_1m"] + completion_tokens * spec["output_usd_per_1m"])
        / 1_000_000.0,
        8,
    )


def nebius_api_key() -> str:
    load_dotenv(REPO_ROOT / ".env")
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set in .env")
    return key


def configured_teachers() -> list[str] | None:
    """Optional override from CURATOR_TEACHER_MODELS (comma-separated model names)."""
    load_dotenv(REPO_ROOT / ".env")
    val = (os.environ.get("CURATOR_TEACHER_MODELS") or "").strip()
    if not val:
        return None
    return [m.strip() for m in val.split(",") if m.strip()]


def load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    """Load cached valid teacher responses keyed by gkg_id."""
    if not cache_path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with cache_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("gkg_id") and rec.get("valid"):
                out[rec["gkg_id"]] = rec
    return out


def call_teacher_one(
    client: httpx.Client,
    model: str,
    row: dict[str, Any],
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call Nebius chat completions for one article at temperature=0."""
    spec = TEACHER_CATALOG.get(model, {})
    if spec and not spec.get("trainable_outputs", False):
        raise ValueError(f"Model {model} licence does not permit training on outputs")
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_article_prompt(row)},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    t0 = time.perf_counter()
    last_err = ""
    for attempt in range(3):
        try:
            resp = client.post("/chat/completions", json=body)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(0.8 * (2**attempt))
                continue
            latency_ms = int((time.perf_counter() - t0) * 1000)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            usage = data.get("usage") or {}
            p_tok = int(usage.get("prompt_tokens") or 0)
            c_tok = int(usage.get("completion_tokens") or 0)
            tot_tok = int(usage.get("total_tokens") or (p_tok + c_tok))
            parsed = parse_and_validate_label(content)
            cost = estimate_cost_usd(model, p_tok, c_tok)
            if parsed is None:
                return {
                    "gkg_id": row["gkg_id"],
                    "model": model,
                    "valid": False,
                    "error": f"invalid_json: {(content or '')[:120]}",
                    "latency_ms": latency_ms,
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "total_tokens": tot_tok,
                    "cost_usd_est": cost,
                }
            return {
                "gkg_id": row["gkg_id"],
                "model": model,
                "valid": True,
                "is_ai": parsed.is_ai,
                "subtopics": parsed.subtopics,
                "brand_safe": parsed.brand_safe,
                "confidence": parsed.confidence,
                "latency_ms": latency_ms,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": tot_tok,
                "cost_usd_est": cost,
            }
        except httpx.HTTPError as exc:
            last_err = f"http_error: {type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(0.8 * (2**attempt))
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "gkg_id": row["gkg_id"],
        "model": model,
        "valid": False,
        "error": last_err,
        "latency_ms": latency_ms,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd_est": 0.0,
    }


def label_rows_with_model(
    rows: list[dict[str, Any]],
    model: str,
    cache_dir: Path | None = None,
    workers: int = 24,
    timeout_s: float = 45.0,
    max_tokens: int = 500,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Label a list of article rows with one teacher model, caching by gkg_id."""
    t_dir = cache_dir or (lake() / "labels" / "teacher")
    t_dir.mkdir(parents=True, exist_ok=True)
    slug = TEACHER_CATALOG.get(model, {}).get("slug") or re.sub(r"[^a-zA-Z0-9_]", "_", model)
    cache_path = t_dir / f"{slug}.jsonl"

    cached = load_cache(cache_path)
    todo = [r for r in rows if r["gkg_id"] not in cached]

    new_records: list[dict[str, Any]] = []
    if todo:
        key = nebius_api_key()
        limits = httpx.Limits(max_connections=workers + 4, max_keepalive_connections=workers)
        with (
            httpx.Client(
                base_url=NEBIUS_BASE_URL,
                headers={"Authorization": f"Bearer {key}"},
                timeout=timeout_s,
                limits=limits,
            ) as client,
            cache_path.open("a", encoding="utf-8") as fh,
            concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool,
        ):
            futures = [pool.submit(call_teacher_one, client, model, r, max_tokens) for r in todo]
            done_count = 0
            for fut in concurrent.futures.as_completed(futures):
                rec = fut.result()
                new_records.append(rec)
                if rec.get("valid"):
                    cached[rec["gkg_id"]] = rec
                    fh.write(json.dumps(rec) + "\n")
                    done_count += 1
                    if done_count % 100 == 0:
                        fh.flush()

    results_for_rows = [cached[r["gkg_id"]] for r in rows if r["gkg_id"] in cached]
    failed_attempts = [r for r in new_records if not r.get("valid")]
    all_counted = failed_attempts + results_for_rows
    n_total = len(rows)
    n_valid = len(results_for_rows)
    n_invalid = n_total - n_valid
    latencies = sorted(int(r.get("latency_ms") or 0) for r in results_for_rows if r)
    p_tok = sum(int(r.get("prompt_tokens") or 0) for r in all_counted if r)
    c_tok = sum(int(r.get("completion_tokens") or 0) for r in all_counted if r)
    cost = sum(float(r.get("cost_usd_est") or 0.0) for r in all_counted if r)

    stats = {
        "model": model,
        "slug": slug,
        "family": TEACHER_CATALOG.get(model, {}).get("family", "unknown"),
        "license": TEACHER_CATALOG.get(model, {}).get("license", "unknown"),
        "requested_rows": n_total,
        "new_api_calls": len(todo),
        "valid_rows": n_valid,
        "invalid_rows": n_invalid,
        "failure_rate": round(n_invalid / max(1, n_total), 4),
        "mean_latency_ms": round(sum(latencies) / max(1, len(latencies)), 1) if latencies else 0.0,
        "p50_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
        "p90_latency_ms": latencies[int(0.9 * (len(latencies) - 1))] if latencies else 0,
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "total_tokens": p_tok + c_tok,
        "cost_usd_est": round(cost, 6),
        "positive_is_ai_rate": round(
            sum(1 for r in results_for_rows if r and r.get("is_ai")) / max(1, n_valid), 4
        ),
    }
    return cached, stats


def select_pilot_rows(df: pl.DataFrame, n: int = 100) -> list[dict[str, Any]]:
    """Deterministic 100-row stratified subset of sample.parquet (38/25/12/25)."""
    quotas = {"ring1": 38, "ring2": 25, "ring3": 12, "rejected": 25}
    parts: list[pl.DataFrame] = []
    for stratum, q in quotas.items():
        sub = df.filter(pl.col("stratum") == stratum).sort("rn_stratum").head(q)
        parts.append(sub)
    out = pl.concat(parts).head(n)
    return out.to_dicts()


def resolve_panel_row(
    gkg_id: str,
    r1: dict[str, Any] | None,
    r2: dict[str, Any] | None,
    r3: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine two primary teachers and an optional tie-breaker into one consensus panel label."""
    valid_list = [r for r in (r1, r2, r3) if r is not None and r.get("valid")]
    if not valid_list:
        return {
            "gkg_id": gkg_id,
            "is_ai": False,
            "subtopics": [],
            "brand_safe": True,
            "confidence": 0.5,
            "is_ai_agree": False,
            "brand_safe_agree": False,
            "tie_broken": False,
            "n_teachers": 0,
        }

    is_ai_agree = (
        r1 is not None
        and r2 is not None
        and r1.get("valid")
        and r2.get("valid")
        and bool(r1["is_ai"]) == bool(r2["is_ai"])
    )
    brand_safe_agree = (
        r1 is not None
        and r2 is not None
        and r1.get("valid")
        and r2.get("valid")
        and bool(r1["brand_safe"]) == bool(r2["brand_safe"])
    )

    ai_votes = sum(1 for r in valid_list if r.get("is_ai"))
    bs_votes = sum(1 for r in valid_list if r.get("brand_safe"))
    majority = len(valid_list) / 2.0
    is_ai = ai_votes > majority
    brand_safe = bs_votes >= majority

    if is_ai:
        ai_voters = [r for r in valid_list if r.get("is_ai")]
        counts: dict[str, int] = {}
        for r in ai_voters:
            for st in r.get("subtopics") or []:
                counts[st] = counts.get(st, 0) + 1
        min_votes = 2 if len(ai_voters) >= 2 else 1
        chosen = sorted(st for st, c in counts.items() if c >= min_votes)
        if not chosen and counts:
            # Fallback to union of top subtopics if the AI voters named disjoint subtopics
            chosen = sorted(counts.keys())[:2]
        subtopics = chosen[:3]
    else:
        subtopics = []

    matching_confs = [
        float(r.get("confidence", 0.8)) for r in valid_list if bool(r.get("is_ai")) == is_ai
    ]
    avg_conf = sum(matching_confs) / max(1, len(matching_confs))
    if not is_ai_agree:
        avg_conf = min(avg_conf, 0.75)

    return {
        "gkg_id": gkg_id,
        "is_ai": is_ai,
        "subtopics": subtopics,
        "brand_safe": brand_safe,
        "confidence": round(avg_conf, 4),
        "is_ai_agree": bool(is_ai_agree),
        "brand_safe_agree": bool(brand_safe_agree),
        "tie_broken": r3 is not None and bool(r3.get("valid")),
        "n_teachers": len(valid_list),
        "t1_is_ai": r1.get("is_ai") if r1 and r1.get("valid") else None,
        "t2_is_ai": r2.get("is_ai") if r2 and r2.get("valid") else None,
        "t3_is_ai": r3.get("is_ai") if r3 and r3.get("valid") else None,
        "t1_brand_safe": r1.get("brand_safe") if r1 and r1.get("valid") else None,
        "t2_brand_safe": r2.get("brand_safe") if r2 and r2.get("valid") else None,
        "t3_brand_safe": r3.get("brand_safe") if r3 and r3.get("valid") else None,
        "t1_subtopics": ";".join(r1.get("subtopics") or []) if r1 and r1.get("valid") else "",
        "t2_subtopics": ";".join(r2.get("subtopics") or []) if r2 and r2.get("valid") else "",
        "t3_subtopics": ";".join(r3.get("subtopics") or []) if r3 and r3.get("valid") else "",
    }


def run_pilot(
    sample_df: pl.DataFrame,
    candidates: list[str] | None = None,
    cache_dir: Path | None = None,
    workers: int = 16,
) -> dict[str, Any]:
    """Run the 100-article pilot on all candidate teachers and pick the panel."""
    models = candidates or list(TEACHER_CATALOG.keys())
    pilot_rows = select_pilot_rows(sample_df, n=100)
    pilot_ids = [r["gkg_id"] for r in pilot_rows]

    model_stats: dict[str, dict[str, Any]] = {}
    model_caches: dict[str, dict[str, dict[str, Any]]] = {}
    for model in models:
        spec = TEACHER_CATALOG.get(model, {})
        if not spec.get("trainable_outputs", False):
            continue
        cache, stats = label_rows_with_model(
            pilot_rows, model=model, cache_dir=cache_dir, workers=workers
        )
        model_stats[model] = stats
        model_caches[model] = cache
        print(
            f"[pilot] {model}: valid={stats['valid_rows']}/{stats['requested_rows']} "
            f"(fail={stats['failure_rate']:.1%}), p50={stats['p50_latency_ms']}ms, "
            f"tokens={stats['total_tokens']:,}, cost=${stats['cost_usd_est']:.4f} (estimate)"
        )

    # Filter qualifying teachers: trainable_outputs=True and failure_rate <= 0.05
    qualifying = [
        m for m, st in model_stats.items() if st["failure_rate"] <= 0.05 and st["valid_rows"] >= 95
    ]

    # Compute pairwise agreement on is_ai across the 100 pilot rows
    pairwise: dict[str, float] = {}
    for i, m1 in enumerate(qualifying):
        for m2 in qualifying[i + 1 :]:
            c1, c2 = model_caches[m1], model_caches[m2]
            both = [gid for gid in pilot_ids if gid in c1 and gid in c2]
            if both:
                agree = sum(1 for gid in both if c1[gid]["is_ai"] == c2[gid]["is_ai"]) / len(both)
                pairwise[f"{TEACHER_CATALOG[m1]['slug']}__vs__{TEACHER_CATALOG[m2]['slug']}"] = (
                    round(agree, 4)
                )

    # Pick 2 primary teachers from different families
    # Sort qualifying by (failure_rate, p50_latency_ms)
    qualifying_sorted = sorted(
        qualifying,
        key=lambda m: (model_stats[m]["failure_rate"], model_stats[m]["p50_latency_ms"]),
    )
    override = configured_teachers()
    if override and len(override) >= 2:
        selected = override[:3]
    else:
        primary_1 = qualifying_sorted[0] if qualifying_sorted else models[0]
        fam_1 = TEACHER_CATALOG.get(primary_1, {}).get("family")
        diff_fam = [
            m for m in qualifying_sorted if TEACHER_CATALOG.get(m, {}).get("family") != fam_1
        ]
        primary_2 = (
            diff_fam[0]
            if diff_fam
            else (qualifying_sorted[1] if len(qualifying_sorted) > 1 else primary_1)
        )
        remaining = [m for m in qualifying_sorted if m not in (primary_1, primary_2)]
        tie_breaker = remaining[0] if remaining else primary_1
        selected = [primary_1, primary_2, tie_breaker]

    summary = {
        "pilot_n": len(pilot_rows),
        "candidates": model_stats,
        "qualifying_models": qualifying,
        "pairwise_is_ai_agreement": pairwise,
        "selected_panel": {
            "teacher_1": selected[0],
            "teacher_2": selected[1] if len(selected) > 1 else selected[0],
            "tie_breaker": selected[2] if len(selected) > 2 else selected[0],
        },
    }
    t_dir = cache_dir or (lake() / "labels" / "teacher")
    t_dir.mkdir(parents=True, exist_ok=True)
    (t_dir / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def label_dataset_with_panel(
    df: pl.DataFrame,
    panel: dict[str, str],
    cache_dir: Path | None = None,
    workers: int = 28,
    output_name: str = "panel_labels.parquet",
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Label every row in df with teacher_1 and teacher_2, and break ties with tie_breaker."""
    t_dir = cache_dir or (lake() / "labels" / "teacher")
    t_dir.mkdir(parents=True, exist_ok=True)
    rows = df.to_dicts()

    t1_model = panel["teacher_1"]
    t2_model = panel["teacher_2"]
    t3_model = panel["tie_breaker"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pair_pool:
        fut1 = pair_pool.submit(label_rows_with_model, rows, t1_model, t_dir, workers)
        fut2 = pair_pool.submit(label_rows_with_model, rows, t2_model, t_dir, workers)
        c1, st1 = fut1.result()
        c2, st2 = fut2.result()
    print(
        f"[panel T1] {t1_model}: valid={st1['valid_rows']}/{st1['requested_rows']}, "
        f"new_calls={st1['new_api_calls']}, cost=${st1['cost_usd_est']:.4f} (estimate)"
    )
    print(
        f"[panel T2] {t2_model}: valid={st2['valid_rows']}/{st2['requested_rows']}, "
        f"new_calls={st2['new_api_calls']}, cost=${st2['cost_usd_est']:.4f} (estimate)"
    )

    # Identify rows where T1 and T2 disagree on is_ai or brand_safe, or where one failed
    disagree_rows: list[dict[str, Any]] = []
    for r in rows:
        gid = r["gkg_id"]
        r1 = c1.get(gid)
        r2 = c2.get(gid)
        if (
            not r1
            or not r2
            or bool(r1["is_ai"]) != bool(r2["is_ai"])
            or bool(r1["brand_safe"]) != bool(r2["brand_safe"])
        ):
            disagree_rows.append(r)

    c3, st3 = label_rows_with_model(disagree_rows, t3_model, cache_dir=t_dir, workers=workers)
    print(
        f"[panel T3 tie-breaker] {t3_model}: disagreed_rows={len(disagree_rows)}, "
        f"valid={st3['valid_rows']}/{st3['requested_rows']}, "
        f"cost=${st3['cost_usd_est']:.4f} (estimate)"
    )

    resolved: list[dict[str, Any]] = []
    for r in rows:
        gid = r["gkg_id"]
        need_t3 = any(d["gkg_id"] == gid for d in disagree_rows)
        rec = resolve_panel_row(gid, c1.get(gid), c2.get(gid), c3.get(gid) if need_t3 else None)
        rec["subtopics_str"] = ";".join(rec["subtopics"])
        resolved.append(rec)

    panel_df = pl.DataFrame(resolved)
    joined = df.join(panel_df, on="gkg_id", how="left")
    out_path = t_dir / output_name
    joined.write_parquet(out_path, compression="zstd")

    both_valid = [r["gkg_id"] for r in rows if r["gkg_id"] in c1 and r["gkg_id"] in c2]
    is_ai_agree_rate = sum(1 for gid in both_valid if c1[gid]["is_ai"] == c2[gid]["is_ai"]) / max(
        1, len(both_valid)
    )
    bs_agree_rate = sum(
        1 for gid in both_valid if c1[gid]["brand_safe"] == c2[gid]["brand_safe"]
    ) / max(1, len(both_valid))
    # Agreement of each teacher with the final panel label
    panel_map = {r["gkg_id"]: r for r in resolved}
    t1_eval_ids = [r["gkg_id"] for r in rows if r["gkg_id"] in c1]
    t2_eval_ids = [r["gkg_id"] for r in rows if r["gkg_id"] in c2]
    t1_vs_panel = sum(
        1 for gid in t1_eval_ids if c1[gid]["is_ai"] == panel_map[gid]["is_ai"]
    ) / max(1, len(t1_eval_ids))
    t2_vs_panel = sum(
        1 for gid in t2_eval_ids if c2[gid]["is_ai"] == panel_map[gid]["is_ai"]
    ) / max(1, len(t2_eval_ids))
    t3_eval_ids = [d["gkg_id"] for d in disagree_rows if d["gkg_id"] in c3]
    t3_vs_panel_ties = sum(
        1 for gid in t3_eval_ids if c3[gid]["is_ai"] == panel_map[gid]["is_ai"]
    ) / max(1, len(t3_eval_ids))

    summary = {
        "rows_labeled": joined.height,
        "panel": panel,
        "teacher_1_stats": st1,
        "teacher_2_stats": st2,
        "tie_breaker_stats": st3,
        "both_primary_valid": len(both_valid),
        "disagreed_rows": len(disagree_rows),
        "is_ai_agreement_t1_t2": round(is_ai_agree_rate, 4),
        "brand_safe_agreement_t1_t2": round(bs_agree_rate, 4),
        "t1_vs_panel_is_ai_agreement": round(t1_vs_panel, 4),
        "t2_vs_panel_is_ai_agreement": round(t2_vs_panel, 4),
        "t3_vs_panel_on_ties": round(t3_vs_panel_ties, 4),
        "panel_positive_is_ai": int(panel_df["is_ai"].sum()),
        "panel_positive_is_ai_rate": round(float(panel_df["is_ai"].mean()), 4),
        "panel_brand_safe_rate": round(float(panel_df["brand_safe"].mean()), 4),
        "total_cost_usd_est": round(
            st1["cost_usd_est"] + st2["cost_usd_est"] + st3["cost_usd_est"], 6
        ),
    }
    summary_name = output_name.replace(".parquet", "_summary.json")
    (t_dir / summary_name).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return joined, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pilot-only", action="store_true", help="run only the 100-article pilot")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args(argv)

    sample_path = lake() / "labels" / "sample.parquet"
    if not sample_path.exists():
        raise SystemExit(f"Missing {sample_path}; run pipelines/taxonomy/sample.py first")

    sample_df = pl.read_parquet(sample_path)
    pilot_path = lake() / "labels" / "teacher" / "pilot_summary.json"
    if pilot_path.exists() and not args.pilot_only:
        pilot_summary = json.loads(pilot_path.read_text(encoding="utf-8"))
    else:
        pilot_summary = run_pilot(sample_df, workers=min(args.workers, 20))
    if args.pilot_only:
        print(json.dumps(pilot_summary, indent=2))
        return 0

    _, panel_summary = label_dataset_with_panel(
        sample_df,
        panel=pilot_summary["selected_panel"],
        workers=args.workers,
        output_name="panel_labels.parquet",
    )
    print(json.dumps(panel_summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
