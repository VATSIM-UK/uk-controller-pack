#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import sys
import traceback

# Match tokens like N057.17.30.423 or W004.48.01.020
DMS_RE = re.compile(r'^([NSEW])(\d{1,3})\.(\d{1,2})\.(\d{1,2}(?:\.\d+)?)$')

def dms_to_decimal(token: str) -> float:
    """Convert DMS tokens to decimal degrees."""
    m = DMS_RE.match(token.strip())
    if not m:
        raise ValueError(f"Invalid coordinate format: {token}")
    hemi, d, mnt, sec = m.groups()
    deg = int(d)
    minutes = int(mnt)
    seconds = float(sec)
    val = deg + minutes / 60.0 + seconds / 3600.0
    if hemi in ('S', 'W'):
        val = -val
    return val

def parse_coord_pair(lat_token: str, lon_token: str) -> List[float]:
    """Return coordinate in [lon, lat] order for GeoJSON."""
    return [dms_to_decimal(lon_token), dms_to_decimal(lat_token)]

def fl_value(s: str) -> int:
    """Convert FL or SFC/UNL to numeric value."""
    s = s.strip().upper()
    if s in ('SFC', 'GND'):
        return 0
    if s in ('UNL', 'UNLIMITED'):
        return 999
    return int(s)

def parse_area_file(path: Path, fallback_type: str) -> Dict[str, Any]:
    """Parse a single TopSky area file and return its data."""
    name = None
    a_type = None
    lowerFL = None
    upperFL = None
    coords: List[List[float]] = []

    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith(';'):
                    continue

                if line.startswith('AREA:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        name = parts[-1].strip()

                elif line.startswith('CATEGORY:'):
                    _, val = line.split(':', 1)
                    a_type = val.strip()

                elif line.startswith('LIMITS:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        lowerFL = fl_value(parts[1])
                        upperFL = fl_value(parts[2])

                elif line.startswith('COORD:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        coords.append(parse_coord_pair(parts[1].strip(), parts[2].strip()))
    except Exception as e:
        print(f"⚠️ Error parsing {path}: {e}", file=sys.stderr)
        traceback.print_exc()

    if not name:
        name = path.stem
    if a_type is None:
        a_type = fallback_type
    if lowerFL is None:
        lowerFL = 0
    if upperFL is None:
        upperFL = 999

    # Ensure valid GeoJSON polygon (closed ring)
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    return {
        "name": name,
        "type": a_type,
        "lowerFL": lowerFL,
        "upperFL": upperFL,
        "coords": coords,
        "sourceFile": str(path)
    }

def collect_files(input_dirs: List[str]) -> List[Path]:
    """Collect all .txt files from the given input directories."""
    files: List[Path] = []
    for d in input_dirs:
        p = Path(d)
        if not p.exists():
            print(f"⚠️ Skipping missing directory: {p}", file=sys.stderr)
            continue
        files.extend(sorted(p.rglob('*.txt')))
    return files

def main():
    parser = argparse.ArgumentParser(description="Compile TopSky Areas (AARA/Danger/Training) into one GeoJSON.")
    parser.add_argument('--input-dir', action='append', required=True,
                        help='Input directory; provide multiple times.')
    parser.add_argument('--output', required=True, help='Output GeoJSON path.')
    parser.add_argument('--debug', action='store_true', help='Enable verbose debug output.')
    args = parser.parse_args()

    features: List[Dict[str, Any]] = []
    input_files = collect_files(args.input_dir)

    if args.debug:
        print(f"🗂 Found {len(input_files)} input files.")

    for file_path in input_files:
        fallback_type = file_path.parent.name  # e.g., AARA, Danger, Training
        area = parse_area_file(file_path, fallback_type)

        if not area['coords']:
            if args.debug:
                print(f"⏩ Skipping {file_path} (no coords)")
            continue

        features.append({
            "type": "Feature",
            "properties": {
                "name": area["name"],
                "type": area["type"],
                "lowerFL": area["lowerFL"],
                "upperFL": area["upperFL"],
                "sourceFile": area["sourceFile"]
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [area["coords"]]
            }
        })

    fc = {"type": "FeatureCollection", "features": features}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        print(f"✅ GeoJSON written: {out_path} ({len(features)} features)")
    except Exception as e:
        print(f"❌ Failed to write GeoJSON: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
