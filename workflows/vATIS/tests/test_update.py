import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "update.py"
    spec = importlib.util.spec_from_file_location("vatis_update_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vatis_update = _load_module()


class _FakeDatetime:
    @classmethod
    def now(cls):
        class _Now:
            @staticmethod
            def strftime(_fmt):
                return "20260309"

        return _Now()


def test_update_files_increments_serial_for_same_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(vatis_update, "datetime", _FakeDatetime)

    input_dir = tmp_path / "_vATIS"
    input_dir.mkdir()
    profile = input_dir / "test.json"
    profile.write_text(json.dumps({"updateSerial": 2026030901}), encoding="utf-8")

    vatis_update.update_files(["test.json"])

    data = json.loads(profile.read_text(encoding="utf-8"))
    assert data["updateSerial"] == 2026030902
    assert data["updateUrl"].endswith("/_vATIS/test.json")


def test_update_files_resets_serial_for_new_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(vatis_update, "datetime", _FakeDatetime)

    input_dir = tmp_path / "_vATIS"
    input_dir.mkdir()
    profile = input_dir / "all.json"
    profile.write_text(json.dumps({"updateSerial": 2026030805}), encoding="utf-8")

    # Empty file list triggers update for all JSON files in _vATIS.
    vatis_update.update_files([])

    data = json.loads(profile.read_text(encoding="utf-8"))
    assert data["updateSerial"] == 2026030901
