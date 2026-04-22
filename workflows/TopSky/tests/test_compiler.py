import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "compiler.py"
    spec = importlib.util.spec_from_file_location("topsky_compiler_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


compiler = _load_module()


def _slash(path: Path) -> str:
    return path.as_posix().rstrip("/") + "/"


def test_import_file_index_ignores_comments_and_invalid_entries(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    index_dir = shared / "Areas"
    index_dir.mkdir(parents=True)
    index_file = index_dir / ".Index.txt"
    index_file.write_text(
        "A.txt\n"
        "B.txt // comment\n"
        "// Full line comment\n"
        "INVALID_ENTRY\n"
        "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(compiler, "Shared_Path", _slash(shared))
    files = compiler.ImportFileIndex("Areas/")

    assert files == ["A.txt", "B.txt"]


def test_construct_writes_output_and_copies_to_all_profiles(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    i_tec = tmp_path / "iTEC"
    nerc = tmp_path / "NERC"
    node = tmp_path / "NODE"
    nova = tmp_path / "NOVA"
    mil = tmp_path / "MIL"

    for folder in [shared / "Maps", i_tec, nerc, node, nova, mil]:
        folder.mkdir(parents=True, exist_ok=True)

    (shared / "Maps" / "first.txt").write_text("UTC(E) DST(S) DST(E)\n", encoding="utf-8")

    monkeypatch.setattr(compiler, "Shared_Path", _slash(shared))
    monkeypatch.setattr(compiler, "iTEC_Path", _slash(i_tec))
    monkeypatch.setattr(compiler, "NERC_Path", _slash(nerc))
    monkeypatch.setattr(compiler, "NODE_Path", _slash(node))
    monkeypatch.setattr(compiler, "NOVA_Path", _slash(nova))
    monkeypatch.setattr(compiler, "MIL_Path", _slash(mil))

    original_apply_daylight_savings = compiler.ApplyDaylightSavings

    def _apply_to_constructed_output(filename: str):
        output_name = Path(filename).name
        return original_apply_daylight_savings(str(i_tec / output_name))

    monkeypatch.setattr(compiler, "ApplyDaylightSavings", _apply_to_constructed_output)

    compiler.Construct("Maps/", ["first.txt"], "TopSkyMaps.txt")

    for target in [i_tec, nerc, node, nova, mil]:
        out = target / "TopSkyMaps.txt"
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert compiler.DaylightSavingsTimeStart in text
        assert compiler.DaylightSavingsTimeEnd in text


def test_change_mil_danger_area_definition(tmp_path, monkeypatch):
    mil = tmp_path / "MIL"
    mil.mkdir(parents=True)
    areas_file = mil / "TopSkyAreas.txt"
    areas_file.write_text(
        "SOMETHING\nCATEGORYDEF:DANGER:a:b:1:c\nOTHER\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(compiler, "MIL_Path", _slash(mil))

    compiler.ChangeMilDangerAreaDefinition()

    updated = areas_file.read_text(encoding="utf-8")
    assert "CATEGORYDEF:DANGER:a:b:50:c" in updated
