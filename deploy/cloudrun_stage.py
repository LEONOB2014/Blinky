"""Stage the Cloud Run build context: code, contracts, reports and the 7 lake tables, nothing else.

The context is a fresh directory (default: build/cloudrun/, git-ignored as build output) so the
repository's .env, the 440 MB edges_weekly and the rest of the lake never reach the image or
Cloud Build. The lake tables are copied in, so the image is self-contained (no volume).

    RADAR_PROFILE=full uv run python deploy/cloudrun_stage.py            # -> build/cloudrun/
    docker build -t radar-api build/cloudrun                             # local test
    gcloud run deploy radar-api --source build/cloudrun ...              # deploy/README.md
"""

import argparse
import shutil
import sys
from pathlib import Path

from push_lake import plan  # the same 7 tables as the Modal Volume, never edges_weekly

from radar.paths import gold

REPO = Path(__file__).resolve().parents[1]
CODE = ("api", "agents", "src/radar", "contracts", "reports")
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".pytest_cache")
# Runtime dependencies of api/ and agents/ (pyproject.toml core + the api extra).
REQUIREMENTS = """\
duckdb>=1.1.0
polars>=1.10.0
pyarrow>=18.0.0
pydantic>=2.9.0
jsonschema>=4.23.0
pyyaml>=6.0.2
python-dotenv>=1.0.0
httpx>=0.27.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
"""


def stage(out: Path) -> Path:
    tables = plan()  # refuses unless RADAR_PROFILE=full and every table exists
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in CODE:
        shutil.copytree(REPO / rel, out / rel, ignore=SKIP)
    shutil.copy(REPO / "deploy" / "cloudrun" / "Dockerfile", out / "Dockerfile")
    (out / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (out / ".dockerignore").write_text("**/__pycache__\n**/*.pyc\n", encoding="utf-8")
    (out / ".gcloudignore").write_text("**/__pycache__\n**/*.pyc\n", encoding="utf-8")
    gold_dir = out / "lake" / "gold"
    gold_dir.mkdir(parents=True)
    for name, _ in tables:
        shutil.copy(gold(name), gold_dir / f"{name}.parquet")
    leaked = [p for p in out.rglob("*") if p.name in {".env", "edges_weekly.parquet"}]
    if leaked:
        raise SystemExit(f"refusing: {leaked} must never be staged")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"staged {out} ({size / 2**20:.1f} MiB): {', '.join(CODE)}, {len(tables)} lake tables")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "cloudrun")
    stage(ap.parse_args(argv).out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
