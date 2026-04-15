import hashlib
import importlib.util
import pathlib
import sys
import types

import pytest


@pytest.fixture(scope="module")
def updater_module():
    module_path = pathlib.Path(__file__).resolve().parents[1] / "Updater.py"

    # Provide a lightweight dulwich.objects.Blob stub for test environments
    # where dulwich is not installed.
    if "dulwich.objects" not in sys.modules:
        dulwich_mod = types.ModuleType("dulwich")
        objects_mod = types.ModuleType("dulwich.objects")

        class Blob:
            @staticmethod
            def from_string(data: bytes):
                return types.SimpleNamespace(id=hashlib.sha1(data).hexdigest().encode())

        objects_mod.Blob = Blob
        dulwich_mod.objects = objects_mod
        sys.modules.setdefault("dulwich", dulwich_mod)
        sys.modules["dulwich.objects"] = objects_mod

    spec = importlib.util.spec_from_file_location("updater_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def updater_app(updater_module):
    return updater_module.UpdaterApp.__new__(updater_module.UpdaterApp)


def test_normalize_version_pads_month(updater_module):
    assert updater_module.normalize_version("2025_01") == "2025_01"
    assert updater_module.normalize_version("2025_09a") == "2025_09a"


def test_normalize_version_leaves_non_matching_values(updater_module):
    assert updater_module.normalize_version("") == ""
    assert updater_module.normalize_version("v1.2.3") == "v1.2.3"


def test_get_local_path_strips_uk_prefix(updater_app):
    assert updater_app.get_local_path("UK/Data/file.txt") == "Data/file.txt"
    assert updater_app.get_local_path("README.md") == "README.md"


def test_get_changed_files_between_tags_detects_changes_and_prf(updater_app, tmp_path, monkeypatch):
    from_root = tmp_path / "from_release" / "UK"
    to_root = tmp_path / "to_release" / "UK"

    (from_root / "Data").mkdir(parents=True)
    (from_root / "Profiles").mkdir(parents=True)
    (from_root / "Data" / "keep.txt").write_text("same", encoding="utf-8")
    (from_root / "Data" / "change.txt").write_text("old", encoding="utf-8")
    (from_root / "Profiles" / "old.prf").write_text("oldprf", encoding="utf-8")

    (to_root / "Data").mkdir(parents=True)
    (to_root / "Profiles").mkdir(parents=True)
    (to_root / "Data" / "keep.txt").write_text("same", encoding="utf-8")
    (to_root / "Data" / "change.txt").write_text("new", encoding="utf-8")
    (to_root / "Data" / "new.txt").write_text("new file", encoding="utf-8")
    (to_root / "Profiles" / "new.prf").write_text("newprf", encoding="utf-8")

    roots = {"from": str(from_root), "to": str(to_root)}
    monkeypatch.setattr(
        updater_app,
        "download_release_snapshot_for_tag",
        lambda tag: roots[tag],
    )

    updated, removed, prf_modified = updater_app.get_changed_files_between_tags("from", "to")

    assert updated == ["UK/Data/change.txt", "UK/Data/new.txt", "UK/Profiles/new.prf"]
    assert removed == ["UK/Profiles/old.prf"]
    assert prf_modified is True

    assert not (tmp_path / "from_release").exists()
    assert not (tmp_path / "to_release").exists()


def test_get_changed_files_between_tags_respects_uk_only_filter(updater_app, tmp_path, monkeypatch):
    from_root = tmp_path / "f" / "UK"
    to_root = tmp_path / "t" / "UK"
    from_root.mkdir(parents=True)
    to_root.mkdir(parents=True)
    (to_root / "file.txt").write_text("content", encoding="utf-8")

    monkeypatch.setattr(
        updater_app,
        "download_release_snapshot_for_tag",
        lambda tag: str(from_root if tag == "from" else to_root),
    )
    monkeypatch.setattr(updater_app, "is_user_file", lambda path: False)

    updated, removed, prf_modified = updater_app.get_changed_files_between_tags("from", "to")

    assert updated == []
    assert removed == []
    assert prf_modified is False
    assert not (tmp_path / "f").exists()
    assert not (tmp_path / "t").exists()


class _DummyButton:
    def __init__(self):
        self.states = []

    def config(self, **kwargs):
        self.states.append(kwargs.get("state"))


class _DummyThread:
    instances = []

    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon
        self.started = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True


def test_start_update_disables_button_and_starts_background_thread(updater_module, updater_app, monkeypatch):
    updater_app.update_button = _DummyButton()
    _DummyThread.instances = []
    monkeypatch.setattr(updater_module.threading, "Thread", _DummyThread)

    updater_app.start_update()

    assert updater_app.update_button.states == ["disabled"]
    assert len(_DummyThread.instances) == 1
    assert _DummyThread.instances[0].target == updater_app._run_update_safely
    assert _DummyThread.instances[0].daemon is True
    assert _DummyThread.instances[0].started is True


def test_run_update_safely_reenables_button_when_updater_is_current(updater_app, monkeypatch):
    updater_app.update_button = _DummyButton()
    calls = []

    monkeypatch.setattr(updater_app, "ensure_updater_current", lambda: True)
    monkeypatch.setattr(updater_app, "update_if_needed", lambda: calls.append("updated"))

    updater_app._run_update_safely()

    assert calls == ["updated"]
    assert updater_app.update_button.states == ["normal"]


def test_run_update_safely_reenables_button_when_updater_check_fails(updater_app, monkeypatch):
    updater_app.update_button = _DummyButton()
    calls = []

    monkeypatch.setattr(updater_app, "ensure_updater_current", lambda: False)
    monkeypatch.setattr(updater_app, "update_if_needed", lambda: calls.append("updated"))

    updater_app._run_update_safely()

    assert calls == []
    assert updater_app.update_button.states == ["normal"]


def test_start_gng_flow_starts_background_thread(updater_module, updater_app, monkeypatch):
    _DummyThread.instances = []
    monkeypatch.setattr(updater_module.threading, "Thread", _DummyThread)

    updater_app.start_gng_flow()

    assert len(_DummyThread.instances) == 1
    assert _DummyThread.instances[0].target == updater_app.gng_update_flow
    assert _DummyThread.instances[0].daemon is True
    assert _DummyThread.instances[0].started is True