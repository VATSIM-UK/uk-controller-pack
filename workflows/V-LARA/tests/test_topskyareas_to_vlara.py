import importlib.util
import json
from pathlib import Path
import sys


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "topskyareas_to_vlara.py"
    spec = importlib.util.spec_from_file_location("topskyareas_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


topskyareas = _load_module()


def test_dms_to_decimal_and_parse_coord_pair():
    assert round(topskyareas.dms_to_decimal("N057.30.00.0"), 4) == 57.5
    assert round(topskyareas.dms_to_decimal("W001.30.00.0"), 4) == -1.5
    assert topskyareas.parse_coord_pair("N057.00.00.0", "W001.00.00.0") == [-1.0, 57.0]


def test_parse_circle_line_returns_closed_ring():
    ring = topskyareas.parse_circle_line("CIRCLE:N57.00.00.0:W1.00.00.0:10:90")
    assert len(ring) >= 4
    assert ring[0] == ring[-1]


def test_parse_area_file_with_coords(tmp_path):
    area_file = tmp_path / "area.txt"
    area_file.write_text(
        "AREA:XX:Sample Area\n"
        "CATEGORY:Danger\n"
        "LIMITS:SFC:120\n"
        "COORD:N057.00.00.0:W001.00.00.0\n"
        "COORD:N058.00.00.0:W001.00.00.0\n"
        "COORD:N058.00.00.0:W002.00.00.0\n",
        encoding="utf-8",
    )

    parsed = topskyareas.parse_area_file(area_file, "Fallback")

    assert parsed["name"] == "Sample Area"
    assert parsed["type"] == "Danger"
    assert parsed["lowerFL"] == 0
    assert parsed["upperFL"] == 120
    assert parsed["coords"][0] == parsed["coords"][-1]


def test_collect_files_and_main(tmp_path, monkeypatch):
    input_dir = tmp_path / "AARA"
    input_dir.mkdir(parents=True)
    (input_dir / "one.txt").write_text(
        "AREA:XX:Area One\n"
        "LIMITS:SFC:100\n"
        "COORD:N057.00.00.0:W001.00.00.0\n"
        "COORD:N058.00.00.0:W001.00.00.0\n"
        "COORD:N058.00.00.0:W002.00.00.0\n",
        encoding="utf-8",
    )

    output_file = tmp_path / "out" / "airspace.geojson"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "topskyareas_to_vlara.py",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_file),
        ],
    )

    topskyareas.main()

    result = json.loads(output_file.read_text(encoding="utf-8"))
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
