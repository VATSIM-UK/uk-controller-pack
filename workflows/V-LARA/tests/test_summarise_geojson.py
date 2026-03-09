import json
import os
from pathlib import Path
import subprocess
import sys


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "summarise_geojson.py"


def test_summarise_geojson_outputs_feature_count_and_bbox(tmp_path):
    geojson_path = tmp_path / "summary.geojson"
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
    assert "## Airspace GeoJSON" in result.stdout
    assert "- Features: **1**" in result.stdout
    assert "- BBox: [0.00000, 0.00000, 1.00000, 1.00000]" in result.stdout
