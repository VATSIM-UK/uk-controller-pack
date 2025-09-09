#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import sys
import traceback
import math

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

# --- circle support helpers ---
EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles

def _to_rad(d): return d * math.pi / 180.0
def _to_deg(r): return r * 180.0 / math.pi

def _dest_point(lat_deg: float, lon_deg: float, bearing_deg: float, dist_nm: float):
    """Forward geodesic on a sphere (distance in NM, coords in deg)."""
    lat1 = _to_rad(lat_deg); lon1 = _to_rad(lon_deg)
    brg = _to_rad(bearing_deg); ang = dist_nm / EARTH_RADIUS_NM
    sin1, cos1 = math.sin(lat1), math.cos(lat1)
    sin_ang, cos_ang = math.sin(ang), math.cos(ang)
    sin2 = sin1 * cos_ang + cos1 * sin_ang * math.cos(brg)
    lat2 = math.asin(sin2)
    y = math.sin(brg) * sin_ang * cos1
    x = cos_ang - sin1 * sin2
    lon2 = lon1 + math.atan2(y, x)
    lon2 = (lon2 + math.pi) % (2 * math.pi) - math.pi
    return _to_deg(lat2), _to_deg(lon2)

def _parse_latlon_token(token: str, is_lat: bool):
    """Try decimal first; otherwise fall back to DMS (TopSkyAreas format)."""
    try:
        return float(token)
    except ValueError:
        return dms_to_decimal(token)

def _circle_ring(center_lat, center_lon, radius_nm, spacing_deg):
    if not (0.1 <= radius_nm <= 9999.9):
        raise ValueError(f"Radius out of bounds: {radius_nm}")
    if not (0.1 <= spacing_deg <= 120.0):
        raise ValueError(f"Spacing out of bounds: {spacing_deg}")
    n = max(3, int(math.ceil(360.0 / spacing_deg)))
    step = 360.0 / n
    ring = []
    b = 0.0
    for _ in range(n):
        lat, lon = _dest_point(center_lat, center_lon, b, radius_nm)
        ring.append([lon, lat])
        b += step
    ring.append(ring[0])
    return ring

def parse_circle_line(line: str):
    # CIRCLE:Lat:Lon:Radius:Spacing
    parts = [p.strip() for p in line.split(':')]
    if len(parts) != 5 or parts[0].upper() != 'CIRCLE':
        raise ValueError(f"Invalid CIRCLE line: {line}")
    lat = _parse_latlon_token(parts[1], True)
    lon = _parse_latlon_token(parts[2], False)
    radius_nm = float(parts[3]); spacing_deg = float(parts[4])
    return _circle_ring(lat, lon, radius_nm, spacing_deg)
# --- end circle support ---

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
    circle_coords: List[List[float]] = []
    saw_coords = False
    saw_circle = False
    activePermanent = False

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
                    if saw_circle:
                        raise ValueError(f"{path}: mixed CIRCLE and COORD not allowed")
                    parts = line.split(':')
                    if len(parts) >= 3:
                        coords.append(parse_coord_pair(parts[1].strip(), parts[2].strip()))
                        saw_coords = True

                elif line.startswith('CIRCLE:'):
                    if saw_coords:
                        raise ValueError(f"{path}: mixed COORD and CIRCLE not allowed")
                    circle_coords = parse_circle_line(line)
                    saw_circle = True

                elif line.startswith('ACTIVE:'):
                    parts = line.split(':', 1)
                    if len(parts) == 2 and parts[1].strip() == '1':
                        activePermanent = True

    except Exception as e:
        print(f"⚠️ Error parsing {path}: {e}", file=sys.stderr)
        traceback.print_exc()

    if saw_circle:
        final_coords = circle_coords
    else:
        final_coords = coords
        if final_coords and final_coords[0] != final_coords[-1]:
            final_coords.append(final_coords[0])

    return {
        "name": name or path.stem,
        "type": a_type or fallback_type,
        "lowerFL": lowerFL if lowerFL is not None else 0,
        "upperFL": upperFL if upperFL is not None else 999,
        "coords": final_coords,
        "activePermanent": activePermanent,
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

        if area.get('activePermanent'):
            if args.debug:
                print(f"⏩ Skipping {file_path} (permanently active)")
            continue

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
