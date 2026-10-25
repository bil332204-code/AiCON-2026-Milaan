#!/usr/bin/env python3
"""Stdlib-only size budget and actual disk-byte reporting for the static app."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1] / "milaan/frontend/dist"
assets = [
    "app.js", "scene.js", "cinematic.js", "engine.js", "backend-ui.js",
    "styles.css", "cinematic.css", "phase1.css", "guide.js",
]
sizes = {name: (root / name).stat().st_size for name in assets}
total = sum(sizes.values())
print(json.dumps({"assets_bytes": sizes, "combined_uncompressed_bytes": total}, sort_keys=True))
if total > 350_000:
    raise SystemExit("Static JS/CSS budget exceeded 350000 uncompressed bytes")
