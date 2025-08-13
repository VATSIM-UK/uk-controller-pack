#!/usr/bin/env python3
import json, os, math
p = os.environ.get("GEOJSON_OUT", "data/airspace.geojson")
with open(p, "r", encoding="utf-8") as f:
    fc = json.load(f)

n = len(fc.get("features", []))
minx = miny = math.inf
maxx = maxy = -math.inf
for ft in fc.get("features", []):
    coords = ft.get("geometry", {}).get("coordinates", [])
    if not coords:
        continue
    for x, y in coords[0]:
        minx = min(minx, x); miny = min(miny, y)
        maxx = max(maxx, x); maxy = max(maxy, y)

print("## Airspace GeoJSON")
print(f"- File: `{p}`")
print(f"- Features: **{n}**")
if math.isfinite(minx):
    print(f"- BBox: [{minx:.5f}, {miny:.5f}, {maxx:.5f}, {maxy:.5f}]")
