import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "ASR-Updater.py"
    spec = importlib.util.spec_from_file_location("asr_updater_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


asr_updater = _load_module()


def test_parse_fix_name():
    assert asr_updater.parse_fix_name("BEGID N056.30.00.000 W014.00.00.000") == "BEGID"
    assert asr_updater.parse_fix_name("invalid") is None


def test_is_valid_uk_fix():
    assert asr_updater.is_valid_uk_fix("BEGID", {"OTHER"}) is True
    assert asr_updater.is_valid_uk_fix("BEGI1", set()) is False
    assert asr_updater.is_valid_uk_fix("LONGER", set()) is False
    assert asr_updater.is_valid_uk_fix("BEGID", {"BEGID"}) is False


def test_build_final_fixes(monkeypatch):
    monkeypatch.setattr(asr_updater, "UK_FILE_LIST", ["FIXES_UK.txt"])
    monkeypatch.setattr(asr_updater, "NON_UK_FILE_LIST", ["FIXES_France.txt"])
    monkeypatch.setattr(asr_updater, "BASE_UK_URL", "https://uk/")
    monkeypatch.setattr(asr_updater, "BASE_NON_UK_URL", "https://nonuk/")
    monkeypatch.setattr(asr_updater, "URL_FIXES_EXCLUDE", "https://exclude")
    monkeypatch.setattr(asr_updater, "URL_FIXES_INCLUDE", "https://include")

    lines_for_url = {
        "https://exclude": ["SKIPR"],
        "https://include": ["PARIS"],
        "https://uk/FIXES_UK.txt": [
            "BEGID N056.30.00.000 W014.00.00.000",
            "SKIPR N056.30.00.000 W014.00.00.000",
            "; COMMENT",
        ],
        "https://nonuk/FIXES_France.txt": [
            "PARIS N050.00.00.000 E002.00.00.000",
            "LYONN N050.00.00.000 E002.00.00.000",
        ],
    }

    monkeypatch.setattr(
        asr_updater,
        "get_uncommented_lines",
        lambda url: lines_for_url[url],
    )

    assert asr_updater.build_final_fixes() == ["BEGID", "PARIS"]


def test_update_asr_files_replaces_fixes_block(tmp_path):
    root = tmp_path / "UK" / "Data" / "ASR"
    root.mkdir(parents=True)

    asr_two = root / "sector2.asr"
    asr_four = root / "sector4.asr"
    ground_file = root / "ground2.asr"
    unhandled = root / "sector1.asr"

    asr_two.write_text("Header\nFixes:OLD:name\nFixes:OLD:symbol\nTail\n", encoding="utf-8")
    asr_four.write_text("Fixes:OLD:name\nFixes:OLD:symbol\n", encoding="utf-8")
    ground_file.write_text("Fixes:SHOULD:stay\n", encoding="utf-8")
    unhandled.write_text("Fixes:UNCHANGED\n", encoding="utf-8")

    asr_updater.update_asr_files(["ABCDE"], asr_root=str(root))

    assert asr_two.read_text(encoding="utf-8") == "Header\nFixes:ABCDE:symbol\nTail\n"
    assert asr_four.read_text(encoding="utf-8") == "Fixes:ABCDE:name\nFixes:ABCDE:symbol\n"
    assert ground_file.read_text(encoding="utf-8") == "Fixes:SHOULD:stay\n"
    assert unhandled.read_text(encoding="utf-8") == "Fixes:UNCHANGED\n"
