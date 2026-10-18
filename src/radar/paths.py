"""Where the data lives. Every workstream resolves paths here, never through machine paths.

`RADAR_PROFILE=dev` (the default, and what CI uses) reads the committed real dev slice in
`fixtures/dev/`; `RADAR_PROFILE=full` reads the shared lake (`RADAR_LAKE`, default `<repo>/lake`).
Numbers computed on the dev profile are never reported.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = ("dev", "full")


def profile() -> str:
    value = os.environ.get("RADAR_PROFILE", "dev")
    if value not in PROFILES:
        raise ValueError(f"RADAR_PROFILE must be one of {PROFILES}, got {value!r}")
    return value


def lake() -> Path:
    """The shared lake: ``RADAR_LAKE`` when set, else ``<repo>/lake`` (a symlink in worktrees)."""
    return Path(os.environ.get("RADAR_LAKE") or REPO_ROOT / "lake")


def gold(name: str) -> Path:
    """A gold table for the active profile.

    dev:  ``<repo>/fixtures/dev/<name>.parquet``
    full: ``<lake>/gold/<name>.parquet``
    """
    if profile() == "dev":
        return REPO_ROOT / "fixtures" / "dev" / f"{name}.parquet"
    return lake() / "gold" / f"{name}.parquet"
