"""Stage the Cloud Run build context: code, contracts, reports and the API's lake tables only.

Plus one view file, lake/views/temporal.json: the graph view's metadata that the agents'
get_graph_facts reads (top-k, minimum co-mentions, NPMI cut, nodes and edges per week). The image
reads it at $RADAR_LAKE/views/temporal.json = /app/lake/views/temporal.json, the path staged here.

The context is a fresh directory (default: build/cloudrun/, git-ignored as build output) so the
repository's .env, the 440 MB edges_weekly and the rest of the lake never reach the image or
Cloud Build. The lake tables are copied in, so the image is self-contained (no volume).

    RADAR_PROFILE=full uv run python deploy/cloudrun_stage.py            # -> build/cloudrun/
    docker build -t radar-api build/cloudrun                             # local test
    gcloud run deploy radar-api --source build/cloudrun ...              # deploy/README.md
"""

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

from push_lake import plan  # push_lake.TABLES, as the Modal Volume; never edges_weekly

from radar.paths import gold, lake

REPO = Path(__file__).resolve().parents[1]
CODE = ("api", "agents", "src/radar", "contracts", "reports")
VIEWS = ("temporal.json",)  # only the graph-facts metadata; never the story or image files
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".pytest_cache")


def requirements() -> str:
    """The API's runtime dependencies: pyproject's core list plus the api extra (never drifts)."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return "\n".join([*project["dependencies"], *project["optional-dependencies"]["api"]]) + "\n"


def stage(out: Path) -> Path:
    tables = plan()  # refuses unless RADAR_PROFILE=full and every table exists
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in CODE:
        shutil.copytree(REPO / rel, out / rel, ignore=SKIP)
    shutil.copy(REPO / "deploy" / "cloudrun" / "Dockerfile", out / "Dockerfile")
    (out / "requirements.txt").write_text(requirements(), encoding="utf-8")
    (out / ".dockerignore").write_text("**/__pycache__\n**/*.pyc\n", encoding="utf-8")
    (out / ".gcloudignore").write_text("**/__pycache__\n**/*.pyc\n", encoding="utf-8")
    gold_dir = out / "lake" / "gold"
    gold_dir.mkdir(parents=True)
    for name, _ in tables:
        shutil.copy(gold(name), gold_dir / f"{name}.parquet")
    views_dir = out / "lake" / "views"
    views_dir.mkdir(parents=True)
    for name in VIEWS:
        src = lake() / "views" / name
        if not src.exists():
            raise SystemExit(f"missing in the lake: views/{name} (run graph/export_views.py)")
        nodes = json.loads(src.read_text(encoding="utf-8"))["nodes"]
        if any(str(n.get("id", "")).startswith("per:") for n in nodes):
            raise SystemExit(
                f"refusing: views/{name} has person nodes (persons never leave the lake)"
            )
        shutil.copy(src, views_dir / name)
    leaked = [p for p in out.rglob("*") if p.name in {".env", "edges_weekly.parquet"}]
    if leaked:
        raise SystemExit(f"refusing: {leaked} must never be staged")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    views = sum((views_dir / n).stat().st_size for n in VIEWS)
    print(
        f"staged {out} ({size / 2**20:.1f} MiB): {', '.join(CODE)}, {len(tables)} lake tables, "
        f"views {', '.join(VIEWS)} ({views / 2**20:.1f} MiB)"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "cloudrun")
    stage(ap.parse_args(argv).out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
