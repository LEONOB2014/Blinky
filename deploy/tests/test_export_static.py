import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import export_static  # noqa: E402


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "dev"])
def test_export_refuses_outside_the_full_profile(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("RADAR_PROFILE", raising=False)
    else:
        monkeypatch.setenv("RADAR_PROFILE", value)
    with pytest.raises(SystemExit, match="refusing"):
        export_static.export(tmp_path / "data")
    assert not (tmp_path / "data").exists()


@pytest.mark.unit
def test_slug_matches_the_web_rule():
    # web/src/api.ts: id.toLowerCase().replace(/[^a-z0-9]+/g, "_"), trimmed of "_"
    assert export_static.slug("org:openai group") == "org_openai_group"
    assert export_static.slug("thm:TECH_AUTOMATION") == "thm_tech_automation"
    assert export_static.slug("regulation_policy") == "regulation_policy"
    assert export_static.slug("org:at&t") == "org_at_t"
