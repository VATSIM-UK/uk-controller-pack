import json
import os
from pathlib import Path
import subprocess
import sys


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "validate_geojson.py"


def test_validate_geojson_success(tmp_path):
    geojson_path = tmp_path / "ok.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_script_path())],
        env={**os.environ, "GEOJSON_OUT": str(geojson_path), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0
    assert "Validation OK" in result.stdout


def test_validate_geojson_failure_for_open_ring(tmp_path):
    geojson_path = tmp_path / "bad.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_script_path())],
        env={**os.environ, "GEOJSON_OUT": str(geojson_path), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode != 0
    assert "ring not closed" in result.stderr
