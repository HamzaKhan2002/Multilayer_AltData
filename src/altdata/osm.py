"""OpenStreetMap storage-tank registry through the Overpass API. Data: (c) OpenStreetMap contributors, ODbL."""
from __future__ import annotations

import math
import time

import requests
from pyproj import Transformer
from shapely.geometry import Polygon

MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
UA = {"User-Agent": "multilayer-altdata-research/0.1 (non-commercial research)"}


def query(q: str, rounds: int = 2) -> dict:
    last = None
    for r in range(rounds):
        for url in MIRRORS:
            try:
                resp = requests.post(url, data={"data": q}, headers=UA, timeout=75)
                if resp.status_code == 200:
                    return resp.json()
                last = f"{url} -> HTTP {resp.status_code}"
            except requests.RequestException as e:
                last = f"{url} -> {type(e).__name__}"
        time.sleep(5 * (r + 1))
    raise RuntimeError(f"Overpass unavailable ({last})")


def storage_tanks(bbox) -> list[dict]:
    """Tanks tagged man_made=storage_tank inside bbox (lon_min, lat_min, lon_max, lat_max), with an equivalent diameter
    from the polygon area (UTM zone 14N, valid for central Oklahoma)."""
    w, s, e, n = bbox
    q = f'[out:json][timeout:60];(way["man_made"="storage_tank"]({s},{w},{n},{e});node["man_made"="storage_tank"]({s},{w},{n},{e}););out geom;'
    data = query(q)
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32614", always_xy=True)
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        if el["type"] == "way" and len(el.get("geometry", [])) >= 4:
            pts = [to_utm.transform(g["lon"], g["lat"]) for g in el["geometry"]]
            poly = Polygon(pts)
            if not poly.is_valid or poly.area <= 0:
                continue
            lon = sum(g["lon"] for g in el["geometry"]) / len(el["geometry"])
            lat = sum(g["lat"] for g in el["geometry"]) / len(el["geometry"])
            out.append({"osm_id": f"way/{el['id']}", "lat": lat, "lon": lon, "diameter_m": 2 * math.sqrt(poly.area / math.pi),
                        "area_m2": poly.area, "content": tags.get("content", ""), "operator": tags.get("operator", ""),
                        "roof": tags.get("roof:shape", tags.get("roof", ""))})
        elif el["type"] == "node":
            out.append({"osm_id": f"node/{el['id']}", "lat": el["lat"], "lon": el["lon"], "diameter_m": float("nan"),
                        "area_m2": float("nan"), "content": tags.get("content", ""), "operator": tags.get("operator", ""),
                        "roof": tags.get("roof:shape", tags.get("roof", ""))})
    return out
