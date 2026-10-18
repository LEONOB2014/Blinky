"""Where the lake lives. Every workstream resolves paths here, never through machine paths."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def lake() -> Path:
    """The shared lake: ``RADAR_LAKE`` when set, else ``<repo>/lake`` (a symlink in worktrees)."""
    return Path(os.environ.get("RADAR_LAKE") or REPO_ROOT / "lake")


def gold(name: str) -> Path:
    """A gold table, e.g. ``gold("daily_topic")`` -> ``<lake>/gold/daily_topic.parquet``."""
    return lake() / "gold" / f"{name}.parquet"
