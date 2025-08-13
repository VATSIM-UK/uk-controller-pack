#!/usr/bin/env python3
import json, os, sys
p = os.environ.get("GEOJSON_OUT", "data/airspace.geojson")
try:
    with open(p, "r", encoding="utf-8") as f:
        fc = json.load(f)
except Exception as e:
    print(f"❌ Failed to read JSON {p}: {e}", file=sys.stderr); sys.exit(1)

if fc.get("type") != "FeatureCollection":
    print("❌ Not a FeatureCollection", file=sys.stderr); sys.exit(1)
feats = fc.get("features", [])
if not isinstance(feats, list):
    print("❌ features is not a list", file=sys.stderr); sys.exit(1)

bad = 0
for i, ft in enumerate(feats):
    geom = ft.get("geometry", {})
    if geom.get("type") != "Polygon":
        print(f"❌ feature[{i}] geometry not Polygon", file=sys.stderr); bad += 1; continue
    rings = geom.get("coordinates")
    # enforce single exterior ring (no holes)
    if not rings or not isinstance(rings, list) or len(rings) != 1:
        print(f"❌ feature[{i}] must have exactly one ring", file=sys.stderr); bad += 1; continue
    ring = rings[0]
    if not ring or ring[0] != ring[-1]:
        print(f"❌ feature[{i}] ring not closed", file=sys.stderr); bad += 1

if bad:
    print(f"❌ Validation failed: {bad} issue(s).", file=sys.stderr); sys.exit(1)
print(f"✅ Validation OK: {len(feats)} feature(s).")
