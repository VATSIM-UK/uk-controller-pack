import hashlib
import importlib.util
import itertools
import pathlib
import shutil
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


@pytest.fixture
def snapshot_app(updater_module, tmp_path):
    """An app wired to throwaway base/local/upstream trees, with captured logs."""
    app = updater_module.UpdaterApp.__new__(updater_module.UpdaterApp)
    app.base_dir = str(tmp_path / "install")
    app.messages = []
    app.log = app.messages.append

    base = tmp_path / "base" / "UK"
    upstream = tmp_path / "upstream" / "UK"
    for d in (base, upstream, pathlib.Path(app.base_dir)):
        d.mkdir(parents=True, exist_ok=True)

    def apply(rel, base_text=None, local_text=None, upstream_text=None, conflicts=None):
        for root, text in ((base, base_text), (upstream, upstream_text),
                           (pathlib.Path(app.base_dir), local_text)):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                if target.exists():
                    target.unlink()
                continue
            data = text.encode("utf-8") if isinstance(text, str) else text
            target.write_bytes(data)

        changed = app.merge_or_replace_file_from_snapshots(
            f"UK/{rel}", str(base), str(upstream), conflicts
        )
        result = pathlib.Path(app.base_dir) / rel
        return changed, (result.read_bytes() if result.exists() else None)

    app.apply = apply
    return app


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


def test_merge_text_three_way_merges_non_overlapping_changes(updater_module):
    base = "line1\nline2\nline3\n"
    local = "line1\nline2-local\nline3\n"
    upstream = "line1\nline2\nline3-upstream\n"

    merged, had_conflict = updater_module.UpdaterApp._merge_text_three_way(
        base, local, upstream
    )

    assert had_conflict is False
    assert merged == "line1\nline2-local\nline3-upstream\n"


def test_merge_text_three_way_flags_major_conflict_and_prefers_upstream(updater_module):
    base = "line1\nline2\nline3\n"
    local = "line1\nline2-local\nline3\n"
    upstream = "line1\nline2-upstream\nline3\n"

    merged, had_conflict = updater_module.UpdaterApp._merge_text_three_way(
        base, local, upstream
    )

    assert had_conflict is True
    assert merged == upstream


PACK_PRF = (
    "Settings\tsector\tUK\\Data\\Sector\\UK_2026_07.sct\n"
    "Settings\talias\t\\..\\Data\\Alias\\Heathrow_Alias.txt\n"
    "Plugins\tPlugin0\t\\..\\Data\\Plugin\\vSMR\\vSMR.dll\n"
    "Plugins\tPlugin0Display0\tSMR radar display\n"
    "Plugins\tPlugin1\t\\..\\Data\\Plugin\\VFPC\\VFPC.dll\n"
    "LastSession\tserver\tAUTOMATIC\n"
)

# What the Configurator appends after the user runs it.
CONFIGURED_TAIL = (
    "\n"
    "LastSession\trealname\tJane Doe\n"
    "LastSession\tcertificate\t1234567\n"
    "LastSession\trating\t4\n"
    "LastSession\tcallsign\tJD_OBS\n"
    "LastSession\tpassword\ts3cret\n"
    "\n"
    "Settings\tAselKey\t5177344\n"
)


def _prf_lines(data):
    return data.decode("utf-8").replace("\r\n", "\n").strip().split("\n")


def test_prf_merge_keeps_configurator_settings_and_applies_release(snapshot_app):
    local = PACK_PRF.replace("Plugin1\t", "Plugin1\t") + CONFIGURED_TAIL
    upstream = PACK_PRF.replace("UK_2026_07.sct", "UK_2026_08.sct")

    changed, data = snapshot_app.apply("Heathrow/Heathrow.prf", PACK_PRF, local, upstream)
    lines = _prf_lines(data)

    assert changed is True
    # The release's new AIRAC sector file is applied...
    assert "Settings\tsector\tUK\\Data\\Sector\\UK_2026_08.sct" in lines
    # ...without discarding anything the Configurator wrote.
    assert "LastSession\trealname\tJane Doe" in lines
    assert "LastSession\tcertificate\t1234567" in lines
    assert "LastSession\tpassword\ts3cret" in lines
    assert "LastSession\tcallsign\tJD_OBS" in lines
    assert "Settings\tAselKey\t5177344" in lines


def test_prf_merge_keeps_user_identity_even_when_release_changes_it(snapshot_app):
    local = PACK_PRF + "LastSession\tcallsign\tJD_OBS\n"
    upstream = PACK_PRF + "LastSession\tcallsign\tEGLL_TWR\n"

    _, data = snapshot_app.apply("a.prf", PACK_PRF, local, upstream)

    assert "LastSession\tcallsign\tJD_OBS" in _prf_lines(data)


def test_prf_merge_appends_user_plugin_and_renumbers(snapshot_app):
    local = PACK_PRF + "Plugins\tPlugin2\t\\..\\Data\\Plugin\\DiscordEuroscope.dll\n"
    upstream = PACK_PRF + (
        "Plugins\tPlugin2\t\\..\\Data\\Plugin\\CDM\\CDM.dll\n"
        "Plugins\tPlugin2Display0\tSMR radar display\n"
    )

    _, data = snapshot_app.apply("a.prf", PACK_PRF, local, upstream)
    lines = _prf_lines(data)

    # The release owns the low indices; the user's plugin is appended after it.
    assert "Plugins\tPlugin2\t\\..\\Data\\Plugin\\CDM\\CDM.dll" in lines
    assert "Plugins\tPlugin2Display0\tSMR radar display" in lines
    assert "Plugins\tPlugin3\t\\..\\Data\\Plugin\\DiscordEuroscope.dll" in lines

    indices = [
        int(l.split("\t")[1][len("Plugin"):])
        for l in lines
        if l.startswith("Plugins\tPlugin") and "Display" not in l.split("\t")[1]
    ]
    assert indices == list(range(len(indices)))


def test_prf_merge_never_drops_a_release_plugin_missing_locally(snapshot_app):
    # A stale local profile is indistinguishable from a deliberate removal,
    # so the release's plugin list must always win.
    local = "\n".join(
        l for l in PACK_PRF.split("\n") if "VFPC" not in l
    )
    _, data = snapshot_app.apply("a.prf", PACK_PRF, local, PACK_PRF + "Settings\tnew\t1\n")

    assert "Plugins\tPlugin1\t\\..\\Data\\Plugin\\VFPC\\VFPC.dll" in _prf_lines(data)


def test_prf_merge_ignores_line_ending_drift(snapshot_app):
    # A local install with CRLF endings has not been customised at all.
    local = PACK_PRF.replace("\n", "\r\n")
    upstream = PACK_PRF.replace("UK_2026_07.sct", "UK_2026_08.sct")

    changed, data = snapshot_app.apply("a.prf", PACK_PRF, local, upstream)

    assert changed is True
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert "Settings\tsector\tUK\\Data\\Sector\\UK_2026_08.sct" in _prf_lines(data)
    assert not any("conflict" in m.lower() for m in snapshot_app.messages)


def test_settings_merge_keeps_disjoint_edits_from_both_sides(snapshot_app):
    base = "m_ShowControllers:1\nm_PlanesListX:21\nm_PlanesListY:695\n"
    local = base.replace("m_PlanesListX:21", "m_PlanesListX:900")
    upstream = base.replace("m_ShowControllers:1", "m_ShowControllers:0")

    _, data = snapshot_app.apply("Data/Settings/Screen.txt", base, local, upstream)
    lines = _prf_lines(data)

    assert "m_PlanesListX:900" in lines
    assert "m_ShowControllers:0" in lines


def test_plugins_txt_merge_keeps_cpdlc_password_before_end_marker(snapshot_app):
    base = "PLUGINS\nRDF Plugin for Euroscope:Radius:10\nEND\n"
    local = base.replace("END", "vSMR Vatsim UK:cpdlc_password:abc123\nEND")
    upstream = base.replace("Radius:10", "Radius:20")

    _, data = snapshot_app.apply(
        "Data/Settings/Local/Heathrow/Plugins.txt", base, local, upstream
    )
    lines = _prf_lines(data)

    assert "RDF Plugin for Euroscope:Radius:20" in lines
    assert "vSMR Vatsim UK:cpdlc_password:abc123" in lines
    assert lines[0] == "PLUGINS"
    assert lines[-1] == "END"


def test_settings_merge_falls_back_when_keys_repeat(snapshot_app):
    # Tag and symbology files repeat keys; collapsing them would lose records.
    base = "TAGFAMILY:A\nTAGFAMILY:B\nTAGFAMILY:C\n"
    local = base
    upstream = base.replace("TAGFAMILY:C", "TAGFAMILY:C2")

    _, data = snapshot_app.apply("Data/Settings/Tags.txt", base, local, upstream)

    assert _prf_lines(data) == ["TAGFAMILY:A", "TAGFAMILY:B", "TAGFAMILY:C2"]


def test_generic_merge_keeps_both_end_of_file_appends(updater_module):
    base = "line1\nline2\n"
    local = base + "user-setting\n"
    upstream = base + "release-setting\n"

    merged, had_conflict = updater_module.UpdaterApp._merge_text_three_way(
        base, local, upstream
    )

    assert had_conflict is False
    assert merged.strip().split("\n") == ["line1", "line2", "release-setting", "user-setting"]


def test_user_owned_navdata_is_preserved_once_imported(snapshot_app):
    base = "AAA\t1.0\t2.0\n"
    local = "AAA\t9.9\t9.9\nBBB\t3.0\t4.0\n"  # replaced by a GNG import
    upstream = "AAA\t1.5\t2.5\n"

    changed, data = snapshot_app.apply("Data/Datafiles/isec.txt", base, local, upstream)

    assert changed is False
    assert data.decode("utf-8") == local


def test_user_owned_navdata_still_updates_when_untouched(snapshot_app):
    base = "AAA\t1.0\t2.0\n"
    upstream = "AAA\t1.5\t2.5\n"

    changed, data = snapshot_app.apply("Data/Datafiles/isec.txt", base, base, upstream)

    assert changed is True
    assert data.decode("utf-8") == upstream


def test_cpdlc_code_file_is_never_overwritten(snapshot_app):
    changed, data = snapshot_app.apply(
        "Data/Plugin/TopSky_NODE/TopSkyCPDLChoppieCode.txt", "", "myhoppiecode", ""
    )

    assert changed is False
    assert data == b"myhoppiecode"


def test_new_airac_sector_file_carries_forward_colours(snapshot_app):
    sector = pathlib.Path(snapshot_app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True)
    (sector / "UK_2026_07.sct").write_text(
        "#define coast 32896\n#define land 1777181\n", encoding="utf-8"
    )

    _, data = snapshot_app.apply(
        "Data/Sector/UK_2026_08.sct",
        base_text=None,
        local_text=None,
        upstream_text="#define coast 9076039\n#define land 3947580\n",
    )

    assert data.decode("utf-8").splitlines() == ["#define coast 32896", "#define land 1777181"]


def test_new_airac_ese_reapplies_controller_initials(snapshot_app):
    pathlib.Path(snapshot_app.base_dir, "controller_pack_config.json").write_text(
        '{"initials": "JD"}', encoding="utf-8"
    )

    _, data = snapshot_app.apply(
        "Data/Sector/UK_2026_08.ese",
        base_text=None,
        local_text=None,
        upstream_text="POSITION:EGLL_TWR:EXAMPLE:118.500\n",
    )

    assert data.decode("utf-8") == "POSITION:EGLL_TWR:JD:118.500\n"


def test_clean_merge_reports_no_conflict(snapshot_app):
    # Release changed the sector line, user appended credentials: fully mergeable.
    conflicts = []
    local = PACK_PRF + CONFIGURED_TAIL
    upstream = PACK_PRF.replace("UK_2026_07.sct", "UK_2026_08.sct")

    snapshot_app.apply("a.prf", PACK_PRF, local, upstream, conflicts=conflicts)

    assert conflicts == []


def test_lost_customisation_reports_conflict(snapshot_app):
    # Both sides changed the same pack-owned setting; the user's value is dropped.
    conflicts = []
    local = PACK_PRF.replace("Heathrow_Alias.txt", "My_Alias.txt")
    upstream = PACK_PRF.replace("Heathrow_Alias.txt", "New_Alias.txt")

    snapshot_app.apply("a.prf", PACK_PRF, local, upstream, conflicts=conflicts)

    assert conflicts == ["a.prf"]


def test_binary_conflict_reports_conflict(snapshot_app):
    conflicts = []
    snapshot_app.apply(
        "Data/Plugin/thing.dll",
        base_text=b"\x00base",
        local_text=b"\x00local edit",
        upstream_text=b"\x00upstream edit",
        conflicts=conflicts,
    )

    assert conflicts == ["Data/Plugin/thing.dll"]


def test_new_file_over_local_content_reports_conflict(snapshot_app):
    conflicts = []
    snapshot_app.apply(
        "a.prf", base_text=None, local_text="mine\n", upstream_text="theirs\n",
        conflicts=conflicts,
    )

    assert conflicts == ["a.prf"]


def test_superseded_sector_files_are_removed(snapshot_app):
    sector = pathlib.Path(snapshot_app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True)
    for name in (
        "UK_2026_07.sct", "UK_2026_07.ese", "UK_2026_07.rwy",
        "UK_2026_08.sct", "UK_2026_08.ese", "UK_2026_08.rwy",
        "Falkland.sct", "pack_version.txt",
    ):
        (sector / name).write_bytes(b"x")

    removed = snapshot_app.remove_superseded_sector_files()

    assert removed == 3
    assert sorted(p.name for p in sector.iterdir()) == [
        "Falkland.sct", "UK_2026_08.ese", "UK_2026_08.rwy", "UK_2026_08.sct",
        "pack_version.txt",
    ]


def test_superseded_cleanup_compares_airac_numerically(snapshot_app):
    # UK_2026_9 must not be treated as newer than UK_2026_10.
    sector = pathlib.Path(snapshot_app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True)
    (sector / "UK_2026_9.sct").write_bytes(b"x")
    (sector / "UK_2026_10.sct").write_bytes(b"x")

    assert snapshot_app.remove_superseded_sector_files() == 1
    assert [p.name for p in sector.iterdir()] == ["UK_2026_10.sct"]


def test_superseded_cleanup_keeps_a_single_cycle(snapshot_app):
    sector = pathlib.Path(snapshot_app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True)
    (sector / "UK_2026_08.sct").write_bytes(b"x")

    assert snapshot_app.remove_superseded_sector_files() == 0
    assert (sector / "UK_2026_08.sct").exists()


ASR_WITH_STALE_SECTOR = """DisplayTypeName:Standard ES radar screen
SECTORFILE:UK\\Data\\Sector\\UK_2026_07.sct
SECTORTITLE:UK_2026_07.sct
WINDOWAREA:-1.000000:50.000000:1.000000:52.000000
Airports:EGCC:symbol
PLUGIN:RDF Plugin for Euroscope:Radius:20
PLUGIN:UK Controller Plugin:HistoryTrailColour:255,130,20
PLUGIN:UK Controller Plugin:SelectedMinStack:tma.LTMA;tma.MTMA
PLUGIN:vSMR Vatsim UK:ActiveProfile:Gatwick (Realistic)
PLUGIN:vSMR Vatsim UK:SRW1Rotation:218
"""


def _make_asr(app, rel, text):
    path = pathlib.Path(app.base_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _make_sector(app, *names):
    sector = pathlib.Path(app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True, exist_ok=True)
    for n in names:
        (sector / n).write_bytes(b"x")


def test_asr_sector_lines_repointed_but_plugin_settings_untouched(snapshot_app):
    _make_sector(snapshot_app, "UK_2026_08.sct")
    path = _make_asr(snapshot_app, "Data/ASR/Manchester/Manchester SMR.asr",
                     ASR_WITH_STALE_SECTOR)

    assert snapshot_app.retarget_asr_sector_references() == 1

    result = path.read_text(encoding="utf-8")
    assert "SECTORFILE:UK\\Data\\Sector\\UK_2026_08.sct" in result
    assert "SECTORTITLE:UK_2026_08.sct" in result
    assert "UK_2026_07" not in result

    # Everything the user owns must survive verbatim.
    for line in ASR_WITH_STALE_SECTOR.split("\n"):
        if line.startswith(("PLUGIN:", "WINDOWAREA:", "Airports:", "DisplayTypeName:")):
            assert line in result


def test_asr_retarget_leaves_non_airac_sectors_alone(snapshot_app):
    _make_sector(snapshot_app, "UK_2026_08.sct")
    text = (
        "SECTORFILE:UK\\Data\\Sector\\Gibraltar LXGB.sct\n"
        "SECTORTITLE:Gibraltar LXGB.sct\n"
    )
    path = _make_asr(snapshot_app, "Data/ASR/Gibraltar/Gibraltar Radar.asr", text)

    assert snapshot_app.retarget_asr_sector_references() == 0
    assert path.read_text(encoding="utf-8") == text


def test_asr_retarget_is_a_no_op_when_already_current(snapshot_app):
    _make_sector(snapshot_app, "UK_2026_08.sct")
    text = "SECTORFILE:UK\\Data\\Sector\\UK_2026_08.sct\nSECTORTITLE:UK_2026_08.sct\n"
    _make_asr(snapshot_app, "Data/ASR/a.asr", text)

    assert snapshot_app.retarget_asr_sector_references() == 0


def test_asr_retarget_preserves_line_endings(snapshot_app):
    _make_sector(snapshot_app, "UK_2026_08.sct")
    path = _make_asr(snapshot_app, "Data/ASR/a.asr",
                     ASR_WITH_STALE_SECTOR.replace("\n", "\r\n"))

    snapshot_app.retarget_asr_sector_references()

    data = path.read_bytes()
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")


def test_asr_retarget_does_nothing_without_a_sector_file(snapshot_app):
    path = _make_asr(snapshot_app, "Data/ASR/a.asr", ASR_WITH_STALE_SECTOR)

    assert snapshot_app.retarget_asr_sector_references() == 0
    assert path.read_text(encoding="utf-8") == ASR_WITH_STALE_SECTOR


def test_current_airac_sector_file_picks_newest_cycle(snapshot_app):
    _make_sector(snapshot_app, "UK_2026_9.sct", "UK_2026_10.sct", "Falkland.sct")

    assert snapshot_app.current_airac_sector_file() == "UK_2026_10.sct"


ASR_BASE = """DisplayTypeName:Standard ES radar screen
SHOWC:1
SHOWSB:1
BELOW:0
ABOVE:280
LEADER:5
SHOWLEADER:1
TURNLEADER:0
HISTORY_DOTS:2
SIMULATION_MODE:4
DISABLEPANNING:0
DISABLEZOOMING:0
DisplayRotation:0.00000
TAGFAMILY:AC
WINDOWAREA:53.336625:-2.344675:53.374419:-2.227211
Airports:EGCC:symbol
PLUGIN:vSMR Vatsim UK:SRW1Rotation:218
"""


def test_asr_customised_display_settings_beat_the_release(snapshot_app):
    # User retuned their view; the release retuned the same lines.
    local = (ASR_BASE
             .replace("HISTORY_DOTS:2", "HISTORY_DOTS:6")
             .replace("WINDOWAREA:53.336625:-2.344675:53.374419:-2.227211",
                      "WINDOWAREA:51.0:-1.0:52.0:0.0")
             .replace("TAGFAMILY:AC", "TAGFAMILY:AC-Easy")
             .replace("DisplayRotation:0.00000", "DisplayRotation:180.00000"))
    upstream = (ASR_BASE
                .replace("HISTORY_DOTS:2", "HISTORY_DOTS:0")
                .replace("WINDOWAREA:53.336625:-2.344675:53.374419:-2.227211",
                         "WINDOWAREA:40.0:40.0:41.0:41.0")
                .replace("DisplayRotation:0.00000", "DisplayRotation:11.00000")
                .replace("Airports:EGCC:symbol", "Airports:EGCC:symbol\nAirports:EGLL:symbol"))

    conflicts = []
    _, data = snapshot_app.apply("Data/ASR/a.asr", ASR_BASE, local, upstream,
                                 conflicts=conflicts)
    result = data.decode("utf-8")

    assert conflicts == []
    assert "HISTORY_DOTS:6" in result
    assert "WINDOWAREA:51.0:-1.0:52.0:0.0" in result
    assert "TAGFAMILY:AC-Easy" in result
    assert "DisplayRotation:180.00000" in result
    # The release's unrelated map change still lands.
    assert "Airports:EGLL:symbol" in result


def test_asr_untouched_display_settings_follow_the_release(snapshot_app):
    # The user never changed these, so a release retune must still apply.
    upstream = ASR_BASE.replace("HISTORY_DOTS:2", "HISTORY_DOTS:5")

    _, data = snapshot_app.apply("Data/ASR/a.asr", ASR_BASE, ASR_BASE, upstream)

    assert "HISTORY_DOTS:5" in data.decode("utf-8")


def test_asr_pinning_does_not_touch_other_lines(snapshot_app):
    local = ASR_BASE.replace("LEADER:5", "LEADER:9")
    upstream = ASR_BASE.replace("PLUGIN:vSMR Vatsim UK:SRW1Rotation:218",
                                "PLUGIN:vSMR Vatsim UK:SRW1Rotation:90")

    _, data = snapshot_app.apply("Data/ASR/a.asr", ASR_BASE, local, upstream)
    result = data.decode("utf-8")

    assert "LEADER:9" in result
    # PLUGIN lines are not in the pinned set, so normal merge rules apply.
    assert "PLUGIN:vSMR Vatsim UK:SRW1Rotation:90" in result


def test_asr_pinning_only_applies_to_asr_files(snapshot_app):
    # The same key names in a non-ASR file must not be special-cased.
    base = "HISTORY_DOTS:2\n"
    local = "HISTORY_DOTS:6\n"
    upstream = "HISTORY_DOTS:0\n"

    conflicts = []
    _, data = snapshot_app.apply("Data/Other/thing.dat", base, local, upstream,
                                 conflicts=conflicts)

    assert data.decode("utf-8").strip() == "HISTORY_DOTS:0"
    assert conflicts == ["Data/Other/thing.dat"]


def _write_ese(app, name, text):
    sector = pathlib.Path(app.base_dir) / "Data" / "Sector"
    sector.mkdir(parents=True, exist_ok=True)
    (sector / name).write_bytes(text.encode("utf-8"))


def test_new_ese_reports_conflict_when_initials_cannot_be_recovered(snapshot_app):
    # Configurator was run once (old .ese has initials) but its options file is gone.
    _write_ese(snapshot_app, "UK_2026_07.ese", "POSITION:EGLL_TWR:DG:118.500\n")
    conflicts = []

    _, data = snapshot_app.apply(
        "Data/Sector/UK_2026_08.ese",
        base_text=None,
        local_text=None,
        upstream_text="POSITION:EGLL_TWR:EXAMPLE:118.500\n",
        conflicts=conflicts,
    )

    assert conflicts == ["Data/Sector/UK_2026_08.ese"]
    assert b"EXAMPLE" in data
    assert any("Could not recover controller initials" in m for m in snapshot_app.messages)


def test_new_ese_stays_quiet_for_a_never_configured_pack(snapshot_app):
    # The outgoing .ese still has the placeholder, so nothing is being lost.
    _write_ese(snapshot_app, "UK_2026_07.ese", "POSITION:EGLL_TWR:EXAMPLE:118.500\n")
    conflicts = []

    snapshot_app.apply(
        "Data/Sector/UK_2026_08.ese",
        base_text=None,
        local_text=None,
        upstream_text="POSITION:EGLL_TWR:EXAMPLE:118.500\n",
        conflicts=conflicts,
    )

    assert conflicts == []


def test_new_ese_stays_quiet_when_initials_are_recovered(snapshot_app):
    _write_ese(snapshot_app, "UK_2026_07.ese", "POSITION:EGLL_TWR:DG:118.500\n")
    pathlib.Path(snapshot_app.base_dir, "controller_pack_config.json").write_text(
        '{"initials": "DG"}', encoding="utf-8"
    )
    conflicts = []

    _, data = snapshot_app.apply(
        "Data/Sector/UK_2026_08.ese",
        base_text=None,
        local_text=None,
        upstream_text="POSITION:EGLL_TWR:EXAMPLE:118.500\n",
        conflicts=conflicts,
    )

    assert conflicts == []
    assert data == b"POSITION:EGLL_TWR:DG:118.500\n"


def test_is_pack_configured_detects_credentials(snapshot_app):
    base = pathlib.Path(snapshot_app.base_dir)
    (base / "a.prf").write_bytes(PACK_PRF.encode("utf-8"))

    assert snapshot_app.is_pack_configured() is False

    (base / "a.prf").write_bytes((PACK_PRF + CONFIGURED_TAIL).encode("utf-8"))

    assert snapshot_app.is_pack_configured() is True


def test_is_pack_configured_ignores_blank_certificate(snapshot_app):
    base = pathlib.Path(snapshot_app.base_dir)
    (base / "a.prf").write_bytes(
        (PACK_PRF + "LastSession\tcertificate\t\n").encode("utf-8")
    )

    assert snapshot_app.is_pack_configured() is False


def test_unconfigured_pack_is_prompted_even_without_conflicts(snapshot_app):
    snapshot_app.root = _DummyRoot()
    pathlib.Path(snapshot_app.base_dir, "a.prf").write_bytes(PACK_PRF.encode("utf-8"))

    assert snapshot_app.prompt_configurator_if_needed([]) is True
    assert any("has not been configured yet" in m for m in snapshot_app.messages)


def test_configured_pack_with_clean_merge_is_not_prompted(snapshot_app):
    snapshot_app.root = _DummyRoot()
    pathlib.Path(snapshot_app.base_dir, "a.prf").write_bytes(
        (PACK_PRF + CONFIGURED_TAIL).encode("utf-8")
    )

    assert snapshot_app.prompt_configurator_if_needed([]) is False
    assert snapshot_app.messages == []


def test_configured_pack_with_conflicts_is_prompted(snapshot_app):
    snapshot_app.root = _DummyRoot()
    pathlib.Path(snapshot_app.base_dir, "a.prf").write_bytes(
        (PACK_PRF + CONFIGURED_TAIL).encode("utf-8")
    )

    assert snapshot_app.prompt_configurator_if_needed(["a.prf"]) is True
    assert any("could not be merged" in m for m in snapshot_app.messages)


class _DummyRoot:
    def after(self, _delay, _callback):
        pass


def _run_full_update(app, tmp_path, monkeypatch, local_ver, latest_ver, sha):
    """Drive update_if_needed against local snapshots instead of GitHub."""
    from_uk = tmp_path / "from" / "UK"
    to_uk = tmp_path / "to" / "UK"
    from_uk.mkdir(parents=True, exist_ok=True)
    to_uk.mkdir(parents=True, exist_ok=True)

    (from_uk / "version.txt").write_bytes(local_ver.encode())
    (to_uk / "version.txt").write_bytes(latest_ver.encode())
    (from_uk / "a.prf").write_bytes(PACK_PRF.encode())
    (to_uk / "a.prf").write_bytes(
        PACK_PRF.replace("UK_2026_07.sct", "UK_2026_08.sct").encode()
    )

    pathlib.Path(app.base_dir).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(app.base_dir) / "version.txt").write_bytes(local_ver.encode())
    (pathlib.Path(app.base_dir) / "a.prf").write_bytes(
        (PACK_PRF + CONFIGURED_TAIL).encode()
    )

    app.root = _DummyRoot()
    monkeypatch.setattr(
        app, "get_latest_version",
        lambda: {"tag": latest_ver, "published_at": "2026-08-01T00:00:00Z",
                 "release_sha": sha},
    )

    # The real downloader hands back a fresh temp dir each call, and callers
    # delete it when done, so hand out a throwaway copy rather than the template.
    counter = itertools.count()

    def fake_download(tag):
        dest = tmp_path / f"dl{next(counter)}" / "UK"
        shutil.copytree(from_uk if tag == local_ver else to_uk, dest)
        return str(dest)

    monkeypatch.setattr(app, "download_release_snapshot_for_tag", fake_download)
    app.update_if_needed()


def test_update_writes_both_version_markers(snapshot_app, tmp_path, monkeypatch):
    _run_full_update(
        snapshot_app, tmp_path / "snap", monkeypatch, "2026_07", "2026_08", "abc123sha"
    )

    base = pathlib.Path(snapshot_app.base_dir)
    assert (base / "version.txt").read_text(encoding="utf-8") == "2026_08"
    assert (
        base / "Data" / "Sector" / "pack_version.txt"
    ).read_text(encoding="utf-8") == "abc123sha"
    # The AIRAC bump landed and the user's customisations came through with it.
    merged = (base / "a.prf").read_text(encoding="utf-8")
    assert "UK_2026_08.sct" in merged
    assert "LastSession\tpassword\ts3cret" in merged


def test_up_to_date_check_still_refreshes_markers(snapshot_app, tmp_path, monkeypatch):
    # Same tag on both sides: no files change, but the SHA marker must catch up.
    _run_full_update(
        snapshot_app, tmp_path / "snap", monkeypatch, "2026_08", "2026_08", "newsha456"
    )

    base = pathlib.Path(snapshot_app.base_dir)
    assert (
        base / "Data" / "Sector" / "pack_version.txt"
    ).read_text(encoding="utf-8") == "newsha456"
    assert any("pack_version.txt" in m for m in snapshot_app.messages)


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