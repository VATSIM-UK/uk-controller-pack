import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "auto_airac_actions.py"
    spec = importlib.util.spec_from_file_location("auto_airac_actions_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


auto_airac = _load_module()


def test_airac_cycle_and_tag():
    first_cycle = auto_airac.Airac("2020-01-02")
    second_cycle = auto_airac.Airac("2020-01-30")

    assert first_cycle.cycle() == "2001"
    assert first_cycle.tag() == "2020/01"
    assert second_cycle.cycle() == "2002"
    assert second_cycle.tag() == "2020/02"


def test_current_installation_writes_airac_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class _FakeAirac:
        def tag(self):
            return "2026/03"

    monkeypatch.setattr(auto_airac, "Airac", _FakeAirac)

    installation = auto_airac.CurrentInstallation()

    assert installation.airac == "2026/03"
    assert (tmp_path / "airac.txt").read_text(encoding="utf-8") == "2026/03"


def test_apply_settings_updates_prf_sector_reference(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    uk_root = tmp_path / "UK" / "Data" / "Sector"
    uk_root.mkdir(parents=True)
    sector_file = uk_root / "UK_2026_03.sct"
    sector_file.write_text("dummy", encoding="utf-8")

    profile_file = tmp_path / "UK" / "profile.prf"
    profile_file.write_text("Settings\tsector\tC:\\old\\UK_2025_01.sct\n", encoding="utf-8")

    installation = auto_airac.CurrentInstallation()
    installation.airac = "2026/03"
    installation.ukcp_location = str(tmp_path / "UK")

    assert installation.apply_settings() is None

    updated_profile = profile_file.read_text(encoding="utf-8")
    assert "Settings\tsector\t" in updated_profile
    assert "UK_2026_03.sct" in updated_profile
