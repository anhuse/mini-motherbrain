"""Norwegian municipality boundaries for the landing-page map.

The GeoJSON (simplified, ~1.2 MB) is fetched once into the data/ landing zone
and reused thereafter, mirroring how the Brreg bulk dump is handled. Norway is
the first geography; adapters for other Nordic countries can add their own
boundary files alongside this one.
"""

import json
from functools import lru_cache
from pathlib import Path

import httpx

from mini_motherbrain.config import settings

GEOJSON_URL = "https://raw.githubusercontent.com/robhop/fylker-og-kommuner/main/Kommuner-S.geojson"
FILENAME = "norway-municipalities.geojson"

# Brreg stores municipality names in upper case ("OSLO"); the GeoJSON carries
# mixed case ("Oslo"). Features are keyed on the upper-cased name so the two
# join directly. Two municipality names are duplicated across counties (Herøy,
# Våler); those features share one count, which is acceptable for the map.
FEATURE_KEY = "properties.join_key"


def _ensure_file() -> Path:
    target = settings.data_dir / "geo" / FILENAME
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(GEOJSON_URL, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    target.write_bytes(resp.content)
    return target


@lru_cache(maxsize=1)
def norway_municipalities() -> dict:
    """GeoJSON FeatureCollection with a `join_key` property matching Brreg's
    upper-cased municipality names. Cached for the process lifetime."""
    geojson = json.loads(_ensure_file().read_text(encoding="utf-8"))
    for feature in geojson["features"]:
        feature["properties"]["join_key"] = feature["properties"]["kommunenavn"].upper()
        _rewind(feature["geometry"])
    return geojson


def _rewind(geometry: dict) -> None:
    """Force clockwise exterior rings (and counterclockwise holes), in place.

    The source file follows RFC 7946 (counterclockwise exteriors), but Plotly's
    geo maps render through d3-geo, which uses spherical winding: a small
    counterclockwise polygon is read as 'everything on Earth except this
    municipality', so every shape floods the whole viewport.
    """
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return
    for rings in polygons:
        for i, ring in enumerate(rings):
            # Shoelace sum: negative means counterclockwise here. Exterior
            # rings (i == 0) must be clockwise, holes the opposite.
            area2 = sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
            clockwise = area2 > 0
            if (i == 0) != clockwise:
                ring.reverse()
