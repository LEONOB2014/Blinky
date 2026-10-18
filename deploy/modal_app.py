"""The radar API (api/app.py, FastAPI) on Modal: CPU only, the lake tables on a Modal Volume.

    uv run --extra deploy modal serve deploy/modal_app.py    # temporary URL, live reload
    uv run --extra deploy modal deploy deploy/modal_app.py   # stable URL (maintainer's approval)

The image carries only the code the API imports (api/, agents/, src/radar/) and the files it reads
(contracts/, reports/); never `.env`, the lake or the web. The lake comes from the Volume
`radar-lake` (filled by deploy/push_lake.py) mounted at /lake, so `RADAR_LAKE=/lake` and
`RADAR_PROFILE=full` resolve `lake/gold/<name>.parquet` exactly as on a laptop.

The Nebius key for /api/chat comes from the Modal Secret `radar-nebius` (key `NEBIUS_API_KEY`),
created by the maintainer. Without it (`RADAR_NEBIUS_SECRET=0` at serve/deploy time) the read
endpoints work and /api/chat answers 503, as the API does locally without a key.
"""

import os
import tomllib
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[1]
APP_DIR = "/root/app"
VOLUME_NAME = "radar-lake"
NEBIUS_MODAL_REF = "radar-nebius"  # the name of the Modal Secret object, not a value

# Runtime dependencies of api/ and agents/: pyproject's core list plus the api extra.
_PROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
PACKAGES = [*_PROJECT["dependencies"], *_PROJECT["optional-dependencies"]["api"]]
IGNORE = ["**/__pycache__/**", "**/tests/**", "**/*.pyc"]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(*PACKAGES)
    .env(
        {
            "RADAR_PROFILE": "full",
            "RADAR_LAKE": "/lake",
            "PYTHONPATH": f"{APP_DIR}:{APP_DIR}/src",
        }
    )
    .add_local_dir(REPO / "api", f"{APP_DIR}/api", ignore=IGNORE)
    .add_local_dir(REPO / "agents", f"{APP_DIR}/agents", ignore=IGNORE)
    .add_local_dir(REPO / "src" / "radar", f"{APP_DIR}/src/radar", ignore=IGNORE)
    .add_local_dir(REPO / "contracts", f"{APP_DIR}/contracts")
    .add_local_dir(REPO / "reports", f"{APP_DIR}/reports")
)

lake = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
with_secret = os.environ.get("RADAR_NEBIUS_SECRET") != "0"
secrets = [modal.Secret.from_name(NEBIUS_MODAL_REF)] if with_secret else []

app = modal.App("radar-api", image=image)


@app.function(volumes={"/lake": lake}, secrets=secrets, timeout=300, scaledown_window=600)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    from api.app import app as fastapi_app

    return fastapi_app
