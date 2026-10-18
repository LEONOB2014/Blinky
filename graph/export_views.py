"""Graph-view exports for the UI and smoke test: temporal sweep and top-10 topic stories.

    RADAR_PROFILE=full uv run --extra graph python -m graph.export_views
    RADAR_PROFILE=full uv run --extra graph python -m graph.export_views --topic org:nvidia

- ``temporal.json``: the last 13 weeks (about 90 days) of ``edges_weekly``, scanned one week at a
  time for low memory: top ``max_nodes`` (1,000) nodes by weighted degree over the span with
  n >= ``min_n`` (20) and NPMI > ``min_npmi`` (0.1), pruned per week to the top-``top_k`` (5)
  edges by NPMI per node, with a precomputed frozen 2D layout in cosmos.gl space units and Spanish
  labels on the top ~30 PageRank nodes and every ranked top-10 topic.
- ``story.json`` and ``story_<slug>.json``: one file per ranked top-10 topic of the latest scored
  week (plus key reference topics when present in the 1-hop ring), indexed in
  ``stories_index.json``, with Spanish labels.

Persons (``per:``) never leave the lake: they are dropped from every node and edge here.
"""

import argparse
import json
import math
import re
import shutil
import sys
import time
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from radar import paths
from radar.contracts import CONTRACTS_DIR

VIEWS_DIR = Path(__file__).resolve().parent / "views"  # the HTML pages copied next to the JSON
WEB_VIEWS_DIR = paths.REPO_ROOT / "web" / "public" / "data" / "views"
PERSON_PREFIX = "per:"
SPAN_WEEKS = 13
MAX_NODES = 1000
MIN_N = 20
MIN_NPMI = 0.1
TOP_K = 5
TOP_LABELS = 30
SPACE_SIZE = 4096.0
SPACE_PAD = 448.0
DECISIONS = ["publicar_ahora", "preparar", "esperar", "no_es_tema_caliente"]
EXTRA_STORY_TOPICS = (
    "org:nvidia",
    "org:microsoft",
    "org:google",
    "org:openai group",
    "thm:TECH_AUTOMATION",
)

_LOC_ES: dict[str, str] = {
    "US": "EE. UU.",
    "CH": "China",
    "UK": "Reino Unido",
    "IN": "India",
    "JA": "Japón",
    "GM": "Alemania",
    "FR": "Francia",
    "CA": "Canadá",
    "AS": "Australia",
    "RS": "Rusia",
    "BR": "Brasil",
    "MX": "México",
    "SP": "España",
    "IT": "Italia",
    "KS": "Corea del Sur",
    "TW": "Taiwán",
    "IS": "Israel",
    "IR": "Irán",
    "SA": "Arabia Saudita",
    "AE": "Emiratos Árabes",
    "SN": "Singapur",
    "SZ": "Suiza",
    "NL": "Países Bajos",
    "SW": "Suecia",
    "BE": "Bélgica",
    "EI": "Irlanda",
    "NZ": "Nueva Zelanda",
    "VM": "Vietnam",
    "TH": "Tailandia",
    "ID": "Indonesia",
    "MY": "Malasia",
    "RP": "Filipinas",
    "TU": "Turquía",
    "UP": "Ucrania",
    "CI": "Chile",
    "AR": "Argentina",
    "CO": "Colombia",
    "PE": "Perú",
    "VE": "Venezuela",
    "UY": "Uruguay",
    "SF": "Sudáfrica",
    "EG": "Egipto",
    "NI": "Nigeria",
    "HK": "Hong Kong",
}

_THEME_ES: dict[str, str] = {
    "USPEC_POLICY1": "Política pública",
    "USPEC_POLITICS_GENERAL1": "Política general",
    "USPEC_UNCERTAINTY1": "Incertidumbre económica",
    "WB_696_PUBLIC_SECTOR_MANAGEMENT": "Gestión del sector público",
    "EPU_ECONOMY_HISTORIC": "Economía y coyuntura",
    "EPU_ECONOMY": "Política económica",
    "EPU_POLICY_GOVERNMENT": "Gobierno y políticas",
    "EPU_POLICY_POLICY": "Diseño de políticas",
    "EPU_POLICY_LAW": "Legislación y normas",
    "EPU_POLICY_REGULATION": "Regulación pública",
    "EPU_POLICY_POLITICAL": "Entorno político",
    "EPU_CATS_REGULATION": "Marco regulatorio",
    "EPU_CATS_NATIONAL_SECURITY": "Seguridad nacional",
    "EPU_CATS_MONETARY_POLICY": "Política monetaria",
    "EPU_CATS_MIGRATION_FEAR_FEAR": "Migración y tensión social",
    "UNGP_FORESTS_RIVERS_OCEANS": "Medio ambiente y ecosistemas",
    "WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES": "Tecnologías de información (TIC)",
    "WB_678_DIGITAL_GOVERNMENT": "Gobierno digital",
    "WB_667_ICT_INFRASTRUCTURE": "Infraestructura digital y TIC",
    "WB_670_ICT_SECURITY": "Ciberseguridad y TIC",
    "WB_658_ENTERPRISE_APPLICATIONS": "Aplicaciones empresariales",
    "WB_652_ICT_APPLICATIONS": "Aplicaciones digitales",
    "WB_672_NETWORK_MANAGEMENT": "Gestión de redes",
    "WB_662_SOCIAL_MEDIA": "Redes sociales",
    "WB_694_BROADCAST_AND_MEDIA": "Medios y telecomunicaciones",
    "SCIENCE": "Ciencia e investigación",
    "GENERAL_GOVERNMENT": "Administración pública",
    "CRISISLEX_CRISISLEXREC": "Gestión de crisis",
    "CRISISLEX_C07_SAFETY": "Seguridad ciudadana",
    "CRISISLEX_T11_UPDATESSYMPATHY": "Impacto social",
    "CRISISLEX_C03_WELLBEING_HEALTH": "Bienestar y salud",
    "LEADER": "Liderazgo ejecutivo",
    "MANMADE_DISASTER_IMPLIED": "Riesgo operativo y tecnológico",
    "WB_2432_FRAGILITY_CONFLICT_AND_VIOLENCE": "Riesgo geopolítico",
    "WB_2433_CONFLICT_AND_VIOLENCE": "Conflictividad",
    "TAX_ECON_PRICE": "Precios y tarifas",
    "WB_831_GOVERNANCE": "Gobernanza institucional",
    "EDUCATION": "Educación",
    "WB_470_EDUCATION": "Sistema educativo",
    "WB_1467_EDUCATION_FOR_ALL": "Acceso a la educación",
    "WB_1484_EDUCATION_SKILLS_DEVELOPMENT_AND_LABOR_MARKET": "Talento y mercado laboral",
    "WB_2131_EMPLOYABILITY_SKILLS_AND_JOBS": "Habilidades y empleabilidad",
    "WB_2670_JOBS": "Empleo y trabajo",
    "WB_2689_JOBS_DIAGNOSTICS": "Diagnóstico de empleo",
    "WB_2769_JOBS_STRATEGIES": "Estrategia laboral",
    "WB_2745_JOB_QUALITY_AND_LABOR_MARKET_PERFORMANCE": "Calidad del empleo",
    "WB_621_HEALTH_NUTRITION_AND_POPULATION": "Salud y población",
    "GENERAL_HEALTH": "Salud general",
    "MEDICAL": "Medicina clínica",
    "WB_635_PUBLIC_HEALTH": "Salud pública",
    "WB_1331_HEALTH_TECHNOLOGIES": "Tecnología médica",
    "WB_1350_PHARMACEUTICALS": "Industria farmacéutica",
    "TAX_FNCACT_PRESIDENT": "Presidencia / dirección",
    "TAX_FNCACT_CEO": "Directores ejecutivos (CEO)",
    "TAX_FNCACT_CHIEF": "Alta dirección",
    "TAX_FNCACT_EXECUTIVE": "Ejecutivos",
    "TAX_FNCACT_DIRECTOR": "Directivos",
    "TAX_FNCACT_LEADERS": "Líderes institucionales",
    "TAX_FNCACT_LEADER": "Liderazgo",
    "TAX_FNCACT_MINISTER": "Ministerios",
    "TAX_FNCACT_OFFICIALS": "Autoridades y funcionarios",
    "TAX_FNCACT_AGENTS": "Agentes y representantes",
    "TAX_WORLDMAMMALS_HUMAN": "Capital humano",
    "TAX_WORLDMAMMALS_HUMANS": "Sociedad y personas",
    "LEGISLATION": "Legislación",
    "WB_1921_PRIVATE_SECTOR_DEVELOPMENT": "Desarrollo del sector privado",
    "WB_1920_FINANCIAL_SECTOR_DEVELOPMENT": "Sector financiero",
    "WB_840_JUSTICE": "Sistema judicial",
    "SOC_INNOVATION": "Innovación tecnológica",
    "MEDIA_MSM": "Medios de comunicación",
    "MEDIA_SOCIAL": "Plataformas sociales",
    "WB_507_ENERGY_AND_EXTRACTIVES": "Energía y recursos",
    "WB_723_PUBLIC_ADMINISTRATION": "Administración pública",
    "CYBER_ATTACK": "Ciberataques",
    "WB_698_TRADE": "Comercio internacional",
    "WB_135_TRANSPORT": "Transporte y logística",
    "WB_832_ANTI_CORRUPTION": "Transparencia y cumplimiento",
    "SOC_POINTSOFINTEREST_UNIVERSITY": "Universidades",
    "SOC_POINTSOFINTEREST_SCHOOL": "Centros educativos",
    "ECON_STOCKMARKET": "Mercado bursátil",
    "ECON_INFLATION": "Inflación",
    "WB_442_INFLATION": "Presión inflacionaria",
    "WB_471_ECONOMIC_GROWTH": "Crecimiento económico",
    "WB_346_COMPETITIVE_INDUSTRIES": "Competitividad industrial",
    "WB_405_BUSINESS_CLIMATE": "Clima de negocios",
    "WB_2530_BUSINESS_ENVIRONMENT": "Entorno empresarial",
    "WB_1281_MANUFACTURING": "Manufactura avanzada",
    "TECH_AUTOMATION": "Automatización e IA",
    "SECURITY_SERVICES": "Servicios de seguridad",
    "TRANSPARENCY": "Transparencia",
}

_TOKEN_ES: dict[str, str] = {
    "GOVERNMENT": "gobierno",
    "POLICY": "política",
    "POLICIES": "políticas",
    "ECONOMY": "economía",
    "ECONOMIC": "económico",
    "EDUCATION": "educación",
    "HEALTH": "salud",
    "SECURITY": "seguridad",
    "SAFETY": "seguridad",
    "JOBS": "empleo",
    "JOB": "empleo",
    "LABOR": "trabajo",
    "MARKET": "mercado",
    "DEVELOPMENT": "desarrollo",
    "MANAGEMENT": "gestión",
    "PUBLIC": "público",
    "PRIVATE": "privado",
    "SECTOR": "sector",
    "DIGITAL": "digital",
    "TECHNOLOGY": "tecnología",
    "TECHNOLOGIES": "tecnologías",
    "INFORMATION": "información",
    "COMMUNICATION": "comunicación",
    "ICT": "TIC",
    "INFRASTRUCTURE": "infraestructura",
    "ENTERPRISE": "empresarial",
    "APPLICATIONS": "aplicaciones",
    "BUSINESS": "negocios",
    "FINANCIAL": "financiero",
    "FINANCE": "finanzas",
    "TRADE": "comercio",
    "INNOVATION": "innovación",
    "SCIENCE": "ciencia",
    "REGULATION": "regulación",
    "LAW": "ley",
    "LEGISLATION": "legislación",
    "JUSTICE": "justicia",
    "ENERGY": "energía",
    "CLIMATE": "clima",
    "ENVIRONMENT": "medio ambiente",
    "NATURAL": "naturales",
    "RESOURCES": "recursos",
    "WATER": "agua",
    "MEDIA": "medios",
    "SOCIAL": "social",
    "NETWORK": "redes",
    "PRICE": "precios",
    "INFLATION": "inflación",
    "STOCKMARKET": "bolsa",
    "CYBER": "ciber",
    "ATTACK": "ataques",
    "AUTOMATION": "automatización",
    "DATA": "datos",
    "SOFTWARE": "software",
    "MINING": "minería",
    "MANUFACTURING": "manufactura",
    "TRANSPORT": "transporte",
    "UNIVERSITY": "universidades",
    "SCHOOL": "escuelas",
    "SKILLS": "habilidades",
    "COMPETITIVE": "competitividad",
    "INDUSTRIES": "industrias",
    "INDUSTRY": "industria",
    "GROWTH": "crecimiento",
    "LEADERS": "líderes",
    "LEADER": "liderazgo",
    "PRESIDENT": "presidencia",
    "EXECUTIVE": "ejecutivos",
    "CEO": "CEO",
    "DIRECTOR": "directivos",
    "MINISTER": "ministerios",
    "OFFICIALS": "funcionarios",
    "AGENTS": "agentes",
}

_ACRONYMS = frozenset(
    {
        "IBM",
        "AMD",
        "AWS",
        "TSMC",
        "SAP",
        "SEC",
        "FTC",
        "EU",
        "UN",
        "NATO",
        "BBC",
        "CNBC",
        "AI",
        "IT",
        "US",
        "UK",
        "NVDA",
        "CEO",
        "TIC",
    }
)


@lru_cache(maxsize=1)
def _taxonomy() -> dict[str, Any]:
    return yaml.safe_load((CONTRACTS_DIR / "taxonomy.yaml").read_text(encoding="utf-8"))


def denied_topic_ids() -> frozenset[str]:
    """``org:<name>`` ids on the ranked-universe deny list (wire services, outlets, artefacts)."""
    deny = _taxonomy().get("ranked_universe", {}).get("org_deny") or []
    return frozenset(f"org:{name.strip().lower()}" for name in deny)


def subtopic_labels() -> dict[str, str]:
    return {k: v["label_es"] for k, v in (_taxonomy().get("subtopics") or {}).items()}


def iso_week(monday: date) -> str:
    y, w, _ = monday.isocalendar()
    return f"{y}-W{w:02d}"


def week_monday(week: str) -> date:
    y, w = week.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def story_slug(topic_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic_id.lower()).strip("_")


def story_filename(topic_id: str) -> str:
    return f"story_{story_slug(topic_id)}.json"


def _no_persons(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.filter(
        ~pl.col("x").str.starts_with(PERSON_PREFIX) & ~pl.col("y").str.starts_with(PERSON_PREFIX)
    )


def _format_org_name(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.lower() == "openai group":
        return "OpenAI"
    words = []
    for w in cleaned.split():
        up = w.upper()
        if up in _ACRONYMS:
            words.append(up)
        elif w.islower():
            words.append(w.capitalize())
        else:
            words.append(w)
    return " ".join(words)


def _format_theme_es(code: str) -> str:
    if code in _THEME_ES:
        return _THEME_ES[code]
    stripped = re.sub(
        r"^(WB_\d+_|EPU_CATS_|EPU_POLICY_|EPU_|TAX_FNCACT_|TAX_ECON_|TAX_ETHNICITY_|"
        r"TAX_WORLDLANGUAGES_|TAX_WORLDMAMMALS_|TAX_|CRISISLEX_[CT]\d+_|CRISISLEX_|"
        r"USPEC_|UNGP_|SOC_POINTSOFINTEREST_|SOC_|ECON_|ENV_|TECH_|MEDIA_|GENERAL_)",
        "",
        code,
    )
    stripped = re.sub(r"\d+$", "", stripped).strip("_")
    if not stripped:
        stripped = code
    tokens = [t for t in stripped.split("_") if t and t not in {"AND", "OF", "FOR", "IN", "THE"}]
    translated = [_TOKEN_ES.get(t.upper(), t.lower()) for t in tokens[:4]]
    phrase = " ".join(translated).strip()
    return phrase[0].upper() + phrase[1:] if phrase else code


def _label(entity_id: str, score_labels: dict[str, str] | None = None) -> str:
    sub_map = subtopic_labels()
    if entity_id in sub_map:
        return sub_map[entity_id]
    etype, raw = entity_id.split(":", 1) if ":" in entity_id else ("", entity_id)
    if etype == "loc":
        return _LOC_ES.get(raw.upper(), f"Región {raw.upper()}")
    if etype == "thm":
        return _format_theme_es(raw)
    if score_labels and entity_id in score_labels:
        candidate = score_labels[entity_id].strip()
        if candidate and candidate.lower() not in {entity_id.lower(), raw.lower()}:
            if candidate.islower():
                return _format_org_name(candidate)
            return candidate[0].upper() + candidate[1:]
    if etype == "org":
        return _format_org_name(raw)
    return raw


def _clean(v: Any) -> Any:
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_clean(x) for x in v]
    return v


def span_weeks(edges: pl.LazyFrame, span: int = SPAN_WEEKS) -> list[date]:
    """The last ``span`` weeks present in the data (a missing week stays missing, never filled)."""
    weeks = sorted(edges.select(pl.col("wk").unique()).collect()["wk"].to_list())
    last = weeks[-1]
    wanted = {last - timedelta(weeks=k) for k in range(span)}
    return [w for w in weeks if w in wanted]


def _prune_top_k_per_node(kept: pl.DataFrame, top_k: int) -> pl.DataFrame:
    """Per week, keep every edge that is among the top-``top_k`` by NPMI of either endpoint."""
    if top_k <= 0 or kept.is_empty():
        return kept
    indexed = kept.with_row_index("_eid")
    both = pl.concat(
        [
            indexed.select(
                "wk", pl.col("x").alias("node"), pl.col("y").alias("other"), "npmi", "n", "_eid"
            ),
            indexed.select(
                "wk", pl.col("y").alias("node"), pl.col("x").alias("other"), "npmi", "n", "_eid"
            ),
        ]
    )
    top_eids = (
        both.sort(
            ["wk", "node", "npmi", "n", "other"],
            descending=[False, False, True, True, False],
        )
        .group_by(["wk", "node"], maintain_order=True)
        .head(top_k)
        .select("_eid")
        .unique()
    )
    return indexed.join(top_eids, on="_eid", how="inner").drop("_eid").sort("wk", "x", "y")


def _precompute_layout(
    n_nodes: int,
    sources: list[int],
    targets: list[int],
    npmis: list[float],
) -> list[tuple[float, float]]:
    """Deterministic 2D force-directed layout on the pruned union graph in cosmos.gl space units."""
    if n_nodes <= 0:
        return []
    if n_nodes == 1:
        mid = SPACE_SIZE / 2.0
        return [(mid, mid)]

    golden = math.pi * (3.0 - math.sqrt(5.0))
    seed_coords = [
        [
            math.sqrt((i + 0.5) / n_nodes) * math.cos(i * golden),
            math.sqrt((i + 0.5) / n_nodes) * math.sin(i * golden),
        ]
        for i in range(n_nodes)
    ]

    pair_weights: dict[tuple[int, int], float] = {}
    for s, t, w in zip(sources, targets, npmis, strict=True):
        if s == t:
            continue
        key = (s, t) if s < t else (t, s)
        pair_weights[key] = pair_weights.get(key, 0.0) + max(0.05, float(w or 0.1))

    raw_coords: list[tuple[float, float]]
    try:
        import igraph as ig

        pairs = list(pair_weights.keys())
        weights = [pair_weights[p] for p in pairs]
        g = ig.Graph(n=n_nodes, edges=pairs, directed=False)
        layout = g.layout_fruchterman_reingold(
            weights=weights if weights else None,
            niter=400,
            seed=seed_coords,
        )
        raw_coords = [(float(pt[0]), float(pt[1])) for pt in layout]
    except Exception:
        raw_coords = [(float(pt[0]), float(pt[1])) for pt in seed_coords]

    # Center on the median and softly compress outlier radii above p90 so peripheral or
    # disconnected nodes never shrink the main connected component into the middle.
    xs_sorted = sorted(p[0] for p in raw_coords)
    ys_sorted = sorted(p[1] for p in raw_coords)
    med_x = xs_sorted[n_nodes // 2]
    med_y = ys_sorted[n_nodes // 2]
    centered = [(x - med_x, y - med_y) for x, y in raw_coords]
    radii = sorted(math.hypot(dx, dy) for dx, dy in centered)
    r_p90 = radii[min(n_nodes - 1, int(0.90 * n_nodes))]
    r_scale = r_p90 if r_p90 > 1e-9 else (radii[-1] if radii[-1] > 1e-9 else 1.0)

    compressed: list[tuple[float, float]] = []
    for dx, dy in centered:
        r = math.hypot(dx, dy)
        if r > r_scale and r > 1e-9:
            r_new = r_scale * (1.0 + 0.35 * math.tanh((r - r_scale) / r_scale))
            scale = r_new / r
            dx, dy = dx * scale, dy * scale
        compressed.append((dx, dy))

    min_x = min(p[0] for p in compressed)
    max_x = max(p[0] for p in compressed)
    min_y = min(p[1] for p in compressed)
    max_y = max(p[1] for p in compressed)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    usable = SPACE_SIZE - 2.0 * SPACE_PAD

    return [
        (
            round(SPACE_PAD + ((x - min_x) / span_x) * usable, 2),
            round(SPACE_PAD + ((y - min_y) / span_y) * usable, 2),
        )
        for x, y in compressed
    ]


def export_temporal(
    edges: pl.LazyFrame | pl.DataFrame,
    node_metrics: pl.LazyFrame | pl.DataFrame,
    scores: pl.LazyFrame | pl.DataFrame | None = None,
    *,
    span: int = SPAN_WEEKS,
    max_nodes: int = MAX_NODES,
    min_n: int = MIN_N,
    min_npmi: float = MIN_NPMI,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    edges_lf, node_metrics_lf = edges.lazy(), node_metrics.lazy()
    weeks = span_weeks(edges_lf, span)
    widx = {w: i for i, w in enumerate(weeks)}

    # Scan one week at a time so Polars never materializes the full 37.8M-row table at once.
    week_frames: list[pl.DataFrame] = []
    for w in weeks:
        df_w = (
            _no_persons(edges_lf)
            .filter(
                (pl.col("wk") == w)
                & (pl.col("n") >= min_n)
                & pl.col("npmi").is_not_null()
                & (pl.col("npmi") > min_npmi)
            )
            .select("wk", "x", "y", "n", "npmi")
            .collect()
        )
        week_frames.append(df_w)

    kept = (
        pl.concat(week_frames)
        if week_frames
        else pl.DataFrame(
            schema={
                "wk": pl.Date,
                "x": pl.String,
                "y": pl.String,
                "n": pl.Int64,
                "npmi": pl.Float64,
            }
        )
    )
    all_deg = (
        pl.concat([kept.select(e=pl.col("x"), n="n"), kept.select(e=pl.col("y"), n="n")])
        .group_by("e")
        .agg(pl.col("n").sum().alias("deg"))
        .sort(["deg", "e"], descending=[True, False])
    )
    deg = all_deg.head(max_nodes)

    denied = denied_topic_ids()
    score_labels: dict[str, str] = {}
    wk_names = {iso_week(w): i for i, w in enumerate(weeks)}
    sc_df: pl.DataFrame | None = None
    if scores is not None:
        sc_cols = scores.lazy().collect_schema().names()
        sel_cols = [
            c
            for c in ("week", "topic_id", "rank", "decision", "label_es", "priority")
            if c in sc_cols
        ]
        sc_df = (
            scores.lazy()
            .filter(
                pl.col("week").is_in(list(wk_names))
                & ~pl.col("topic_id").str.to_lowercase().is_in(sorted(denied))
                & ~pl.col("topic_id").str.to_lowercase().str.starts_with(PERSON_PREFIX)
            )
            .select(sel_cols)
            .collect()
        )
        if "label_es" in sc_df.columns:
            for tid, lbl in sc_df.select("topic_id", "label_es").iter_rows():
                if lbl:
                    score_labels[tid] = str(lbl)
        # Ensure top-10 ranked topics that appear in all_deg are included within max_nodes.
        top_ranked_ids = (
            sc_df.filter(pl.col("rank").is_not_null() & (pl.col("rank") <= 10))["topic_id"]
            .unique()
            .to_list()
        )
        missing_ranked = all_deg.filter(
            pl.col("e").is_in(top_ranked_ids) & ~pl.col("e").is_in(deg["e"].to_list())
        )
        if not missing_ranked.is_empty() and max_nodes > missing_ranked.height:
            deg = (
                pl.concat([deg.head(max_nodes - missing_ranked.height), missing_ranked])
                .unique(subset=["e"])
                .sort(["deg", "e"], descending=[True, False])
                .head(max_nodes)
            )

    ids = deg["e"].to_list()
    idx = {v: i for i, v in enumerate(ids)}
    kept = kept.filter(pl.col("x").is_in(ids) & pl.col("y").is_in(ids)).sort("wk", "x", "y")
    kept = _prune_top_k_per_node(kept, top_k)

    nm_cols = node_metrics_lf.collect_schema().names()
    nm_sel = [
        c for c in ("wk", "entity_id", "pagerank", "pr_rank_delta", "deg_growth") if c in nm_cols
    ]
    pr = (
        node_metrics_lf.filter(pl.col("wk").is_in(weeks) & pl.col("entity_id").is_in(ids))
        .select(nm_sel)
        .collect()
    )
    pagerank: dict[str, list[float | None]] = {v: [None] * len(weeks) for v in ids}
    pr_rank_delta: dict[str, list[int | None]] = {v: [None] * len(weeks) for v in ids}
    deg_growth: dict[str, list[float | None]] = {v: [None] * len(weeks) for v in ids}
    for row in pr.to_dicts():
        wi = widx[row["wk"]]
        ent = row["entity_id"]
        pagerank[ent][wi] = row.get("pagerank")
        if "pr_rank_delta" in row:
            pr_rank_delta[ent][wi] = row.get("pr_rank_delta")
        if "deg_growth" in row:
            deg_growth[ent][wi] = row.get("deg_growth")

    rank: dict[str, list[int | None]] = {v: [None] * len(weeks) for v in ids}
    decision: dict[str, list[str | None]] = {v: [None] * len(weeks) for v in ids}
    if sc_df is not None:
        sc_in_ids = sc_df.filter(pl.col("topic_id").is_in(ids))
        for row in sc_in_ids.to_dicts():
            wi = wk_names[row["week"]]
            ent = row["topic_id"]
            rank[ent][wi] = row.get("rank")
            decision[ent][wi] = row.get("decision")

    # Top ~30 nodes by max PageRank over the span + every ranked top-10 topic get labels.
    max_pr_by_id = {v: max((p for p in pagerank[v] if p is not None), default=0.0) for v in ids}
    top_pr_ids = set(
        sorted(ids, key=lambda v: (max_pr_by_id[v], -idx[v]), reverse=True)[:TOP_LABELS]
    )
    last_w = len(weeks) - 1
    ranked_top10_ids = {
        v for v in ids if last_w >= 0 and rank[v][last_w] is not None and rank[v][last_w] <= 10
    }
    if not ranked_top10_ids:
        ranked_top10_ids = {v for v in ids if any(r is not None and r <= 10 for r in rank[v])}
    label_ids = top_pr_ids | ranked_top10_ids

    sources = [idx[x] for x in kept["x"]]
    targets = [idx[y] for y in kept["y"]]
    npmis = kept["npmi"].to_list()
    coords = _precompute_layout(len(ids), sources, targets, npmis)

    nodes = [
        {
            "id": v,
            "label": _label(v, score_labels),
            "label_es": _label(v, score_labels),
            "etype": v.split(":", 1)[0],
            "x": coords[idx[v]][0],
            "y": coords[idx[v]][1],
            "show_label": v in label_ids,
            "deg_span": int(d),
            "pagerank": pagerank[v],
            "pr_rank_delta": pr_rank_delta[v],
            "deg_growth": deg_growth[v],
            "rank": rank[v],
            "decision": decision[v],
        }
        for v, d in deg.iter_rows()
    ]

    # Precompute each week's top movers (ranked topics first, then fastest rising PageRank nodes)
    # so the TemporalGraph side panel can display them immediately for any selected week.
    top_movers_per_week: list[list[dict[str, Any]]] = []
    for wi in range(len(weeks)):
        ranked_w = [
            {
                "id": n["id"],
                "label_es": n["label_es"],
                "rank": n["rank"][wi],
                "decision": n["decision"][wi],
                "pagerank": n["pagerank"][wi],
                "pr_rank_delta": n["pr_rank_delta"][wi],
                "deg_growth": n["deg_growth"][wi],
            }
            for n in nodes
            if n["rank"][wi] is not None and n["rank"][wi] <= 10
        ]
        ranked_w.sort(key=lambda m: int(m["rank"] or 999))
        seen_ids = {m["id"] for m in ranked_w}
        rising_w = [
            {
                "id": n["id"],
                "label_es": n["label_es"],
                "rank": n["rank"][wi],
                "decision": n["decision"][wi],
                "pagerank": n["pagerank"][wi],
                "pr_rank_delta": n["pr_rank_delta"][wi],
                "deg_growth": n["deg_growth"][wi],
            }
            for n in nodes
            if n["id"] not in seen_ids and n["pagerank"][wi] is not None
        ]
        rising_w.sort(
            key=lambda m: (
                float(m["pr_rank_delta"] or 0),
                float(m["pagerank"] or 0.0),
            ),
            reverse=True,
        )
        top_movers_per_week.append((ranked_w + rising_w)[:10])

    return _clean(
        {
            "_meta": {
                "profile": paths.profile(),
                "view": "temporal",
                "layout": "frozen_fruchterman_reingold_space_4096",
                "weeks": [w.isoformat() for w in weeks],
                "iso_weeks": [iso_week(w) for w in weeks],
                "params": {
                    "span_weeks": span,
                    "max_nodes": max_nodes,
                    "min_n": min_n,
                    "min_npmi_exclusive": min_npmi,
                    "top_k_per_node": top_k,
                    "top_labels": TOP_LABELS,
                },
                "n_nodes": len(nodes),
                "n_labeled_nodes": len(label_ids),
                "n_edges": kept.height,
                "edges_per_week": [kept.filter(pl.col("wk") == w).height for w in weeks],
                "top_movers_per_week": top_movers_per_week,
                "decisions": DECISIONS,
            },
            "nodes": nodes,
            "edges": {
                "source": sources,
                "target": targets,
                "week": [widx[w] for w in kept["wk"]],
                "n": kept["n"].to_list(),
                "npmi": npmis,
            },
        }
    )


def default_story_target(scores: pl.LazyFrame | pl.DataFrame) -> tuple[str, str]:
    """The #1 non-person, non-denied topic of the latest scored week (read, never hard-coded)."""
    lf = scores.lazy()
    week = lf.select(pl.col("week").max()).collect().item()
    denied = denied_topic_ids()
    top = (
        lf.filter(
            (pl.col("week") == week)
            & ~pl.col("topic_id").str.to_lowercase().is_in(sorted(denied))
            & ~pl.col("topic_id").str.starts_with(PERSON_PREFIX)
        )
        .sort(pl.col("rank").fill_null(999_999))
        .select("topic_id")
        .head(1)
        .collect()
    )
    return top.item(), week


def top_story_targets(
    scores: pl.LazyFrame | pl.DataFrame,
    week: str | None = None,
    limit: int = 10,
) -> tuple[str, list[dict[str, Any]]]:
    """The ranked top-``limit`` non-person, non-denied topics of ``week`` (default: latest)."""
    lf = scores.lazy()
    if week is None:
        week = lf.select(pl.col("week").max()).collect().item()
    denied = denied_topic_ids()
    cols = lf.collect_schema().names()
    sort_exprs = [pl.col("rank").fill_null(999_999)]
    desc = [False]
    if "priority" in cols:
        sort_exprs.append(pl.col("priority"))
        desc.append(True)
    df = (
        lf.filter(
            (pl.col("week") == week)
            & ~pl.col("topic_id").str.to_lowercase().is_in(sorted(denied))
            & ~pl.col("topic_id").str.starts_with(PERSON_PREFIX)
        )
        .sort(sort_exprs, descending=desc, nulls_last=True)
        .head(limit)
        .collect()
    )
    return week, [_clean(r) for r in df.to_dicts()]


def export_story(
    edges: pl.LazyFrame | pl.DataFrame,
    ring: pl.LazyFrame | pl.DataFrame,
    topic_id: str,
    week: str,
    scores: pl.LazyFrame | pl.DataFrame | None = None,
) -> dict[str, Any]:
    if topic_id.startswith(PERSON_PREFIX):
        raise ValueError("persons are never exported")
    monday = week_monday(week)
    nbrs = (
        ring.lazy()
        .filter(
            (pl.col("wk") == monday)
            & (pl.col("topic_id") == topic_id)
            & ~pl.col("neighbor").str.starts_with(PERSON_PREFIX)
        )
        .sort("rank")
        .head(20)
        .collect()
    )
    members = [topic_id, *nbrs["neighbor"].to_list()]
    among = (
        _no_persons(edges.lazy())
        .filter(
            (pl.col("wk") == monday)
            & pl.col("x").is_in(members)
            & pl.col("y").is_in(members)
            & (pl.col("x") != topic_id)
            & (pl.col("y") != topic_id)
        )
        .select("x", "y", "n", "npmi")
        .collect()
    )
    score_row = None
    score_labels: dict[str, str] = {}
    if scores is not None:
        rows = (
            scores.lazy()
            .filter((pl.col("week") == week) & (pl.col("topic_id") == topic_id))
            .collect()
            .to_dicts()
        )
        if rows:
            score_row = _clean(rows[0])
            if score_row.get("label_es"):
                score_labels[topic_id] = str(score_row["label_es"])

    topic_label_es = _label(topic_id, score_labels)
    if score_row is not None:
        score_row["label_es"] = topic_label_es

    k = max(1, nbrs.height)
    n_max = max([1, *nbrs["n"].to_list()])
    nodes = [
        {
            "key": topic_id,
            "attributes": {
                "label": topic_label_es,
                "label_es": topic_label_es,
                "x": 0.0,
                "y": 0.0,
                "size": 18,
                "role": "topic",
                "etype": topic_id.split(":", 1)[0],
            },
        }
    ]
    edge_list = []
    for i, (nb, rk, n, npmi) in enumerate(nbrs.select("neighbor", "rank", "n", "npmi").iter_rows()):
        angle = 2 * math.pi * i / k
        nb_label_es = _label(nb, score_labels)
        nodes.append(
            {
                "key": nb,
                "attributes": {
                    "label": nb_label_es,
                    "label_es": nb_label_es,
                    "x": round(math.cos(angle), 6),
                    "y": round(math.sin(angle), 6),
                    "size": 6 + 8 * n / n_max,
                    "role": "ring",
                    "rank": rk,
                    "n": n,
                    "npmi": npmi,
                    "etype": nb.split(":", 1)[0],
                },
            }
        )
        edge_list.append(
            {
                "key": f"t{i}",
                "source": topic_id,
                "target": nb,
                "attributes": {
                    "n": n,
                    "npmi": npmi,
                    "size": 1 + 7 * n / n_max,
                    "kind": "ring",
                },
            }
        )
    for j, (x, y, n, npmi) in enumerate(among.iter_rows()):
        width = 0.3 + 1.2 * min(n, n_max) / n_max  # thinner than ring edges, so the ring reads
        edge_list.append(
            {
                "key": f"a{j}",
                "source": x,
                "target": y,
                "attributes": {"n": n, "npmi": npmi, "size": width, "kind": "among"},
            }
        )
    return _clean(
        {
            "_meta": {
                "profile": paths.profile(),
                "view": "story",
                "topic_id": topic_id,
                "label_es": topic_label_es,
                "week": week,
                "wk": monday.isoformat(),
                "n_ring": nbrs.height,
                "n_among_edges": among.height,
            },
            "attributes": {
                "topic_id": topic_id,
                "label_es": topic_label_es,
                "week": week,
                "scores": score_row,
            },
            "options": {"type": "undirected", "multi": False},
            "nodes": nodes,
            "edges": edge_list,
        }
    )


def _write(obj: dict[str, Any], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=paths.lake() / "views")
    parser.add_argument("--web-out", type=Path, default=WEB_VIEWS_DIR)
    parser.add_argument(
        "--no-web-copy", action="store_true", help="do not copy JSON to web/public/data/views"
    )
    parser.add_argument("--topic", help="story topic id (default: #1 of the latest scored week)")
    parser.add_argument("--week", help="story ISO week, e.g. 2026-W42 (default: latest scored)")
    parser.add_argument("--max-nodes", type=int, default=MAX_NODES)
    parser.add_argument("--min-n", type=int, default=MIN_N)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args(argv)

    edges = pl.scan_parquet(paths.gold("edges_weekly"))
    metrics = pl.scan_parquet(paths.gold("node_metrics_weekly"))
    ring = pl.scan_parquet(paths.gold("topic_context_1hop"))
    scores_path = paths.gold("topic_scores_weekly")
    scores = pl.scan_parquet(scores_path) if scores_path.exists() else None

    t0 = time.perf_counter()
    temporal = export_temporal(
        edges,
        metrics,
        scores,
        max_nodes=args.max_nodes,
        min_n=args.min_n,
        top_k=args.top_k,
    )
    t1 = time.perf_counter()
    size_t = _write(temporal, args.out / "temporal.json")

    topic, week = args.topic, args.week
    top10_rows: list[dict[str, Any]] = []
    if scores is not None:
        s_week, top10_rows = top_story_targets(scores, week=week, limit=10)
        week = week or s_week
        if topic is None and top10_rows:
            topic = str(top10_rows[0]["topic_id"])
    if topic is None or week is None:
        raise SystemExit("no topic_scores_weekly: pass --topic and --week")

    t2 = time.perf_counter()
    monday = week_monday(week)
    # Materialize only the single target week once for all story exports.
    edges_wk = _no_persons(edges).filter(pl.col("wk") == monday).collect()
    ring_wk = ring.filter(
        (pl.col("wk") == monday) & ~pl.col("neighbor").str.starts_with(PERSON_PREFIX)
    ).collect()
    scores_wk = scores.filter(pl.col("week") == week).collect() if scores is not None else None

    story_topics: list[str] = []
    for r in top10_rows:
        tid = str(r["topic_id"])
        if tid not in story_topics:
            story_topics.append(tid)
    if topic not in story_topics:
        story_topics.insert(0, topic)
    ring_topic_set = set(ring_wk["topic_id"].unique().to_list())
    for extra in EXTRA_STORY_TOPICS:
        if extra not in story_topics and extra in ring_topic_set:
            story_topics.append(extra)

    top10_id_set = {str(r["topic_id"]) for r in top10_rows}
    stories_meta: dict[str, dict[str, Any]] = {}
    top10_index: list[dict[str, Any]] = []
    primary_story: dict[str, Any] | None = None
    size_s = 0

    for tid in story_topics:
        st = export_story(edges_wk, ring_wk, tid, week, scores_wk)
        fname = story_filename(tid)
        _write(st, args.out / fname)
        if tid == topic:
            primary_story = st
            size_s = _write(st, args.out / "story.json")
        sc_row = st["attributes"].get("scores") or {}
        entry = {
            "topic_id": tid,
            "label_es": st["_meta"]["label_es"],
            "week": week,
            "rank": sc_row.get("rank"),
            "decision": sc_row.get("decision"),
            "n_ring": st["_meta"]["n_ring"],
            "n_among_edges": st["_meta"]["n_among_edges"],
            "file": fname,
            "in_top10": tid in top10_id_set,
        }
        stories_meta[tid] = entry
        if tid in top10_id_set:
            top10_index.append(entry)

    top10_index.sort(key=lambda e: int(e["rank"] or 999))
    index_obj = {
        "_meta": {
            "profile": paths.profile(),
            "week": week,
            "wk": monday.isoformat(),
            "default_topic": topic,
            "n_top10": len(top10_index),
            "n_total_stories": len(stories_meta),
        },
        "top10": top10_index,
        "stories": stories_meta,
    }
    _write(index_obj, args.out / "stories_index.json")
    t3 = time.perf_counter()

    for page in ("temporal.html", "story.html"):
        shutil.copy(VIEWS_DIR / page, args.out / page)

    if not args.no_web_copy and args.web_out is not None:
        args.web_out.mkdir(parents=True, exist_ok=True)
        for jf in args.out.glob("*.json"):
            shutil.copy(jf, args.web_out / jf.name)

    m = temporal["_meta"]
    n_ring_primary = primary_story["_meta"]["n_ring"] if primary_story else 0
    n_among_primary = primary_story["_meta"]["n_among_edges"] if primary_story else 0
    sys.stdout.write(
        f"temporal: {m['n_nodes']} nodes ({m['n_labeled_nodes']} labeled), "
        f"{m['n_edges']} edges over {len(m['weeks'])} weeks "
        f"({m['weeks'][0]} .. {m['weeks'][-1]}), per week {m['edges_per_week']}, "
        f"{size_t / 1e6:.2f} MB, {t1 - t0:.2f} s\n"
        f"story: {topic} {week} (+{len(stories_meta) - 1} other stories, "
        f"{len(top10_index)} top-10): {n_ring_primary} ring, "
        f"{n_among_primary} edges among them, {size_s / 1e3:.1f} kB, "
        f"{t3 - t2:.2f} s\n"
        f"serve: cd {args.out} && python -m http.server 8765  (temporal.html, story.html)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
