"""Real AOI resolution through OpenStreetMap Nominatim."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from app.schemas.normalized_result import AOIInfo, Coordinates

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SatQueryAI/1.0 (remote-sensing research; contact project owner)"
_CACHE_PATH = Path("/tmp/satquery-nominatim-cache.json")
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_RATE_LOCK = Lock()
_LAST_REQUEST = 0.0


class AOIResolutionError(RuntimeError):
    """Raised when Nominatim cannot resolve an AOI."""


def _bbox_polygon(bbox: list[float]) -> list[list[float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return [
        [min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat],
        [min_lon, max_lat], [min_lon, min_lat],
    ]


def _load_cache() -> dict[str, Any]:
    try:
        if time.time() - _CACHE_PATH.stat().st_mtime < _CACHE_TTL_SECONDS:
            return json.loads(_CACHE_PATH.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache))
    except OSError:
        pass


CANONICAL_AOI_REGISTRY: dict[str, dict[str, Any]] = {
    "kashmir": {
        "id": "aoi_canonical_kashmir",
        "name": "Kashmir",
        "country": "India",
        "center": {"latitude": 34.0837, "longitude": 74.7973},
        "area_km2": 15200.0,
        "bbox": [73.80, 33.20, 75.80, 34.90],
        "polygon": _bbox_polygon([73.80, 33.20, 75.80, 34.90]),
    },
    "kashmir valley": {
        "id": "aoi_canonical_kashmir_valley",
        "name": "Kashmir Valley",
        "country": "India",
        "center": {"latitude": 34.15, "longitude": 74.85},
        "area_km2": 15500.0,
        "bbox": [74.00, 33.50, 75.60, 34.60],
        "polygon": _bbox_polygon([74.00, 33.50, 75.60, 34.60]),
    },
    "srinagar": {
        "id": "aoi_canonical_srinagar",
        "name": "Srinagar",
        "country": "India",
        "center": {"latitude": 34.0837, "longitude": 74.7973},
        "area_km2": 294.0,
        "bbox": [74.70, 34.00, 74.92, 34.15],
        "polygon": _bbox_polygon([74.70, 34.00, 74.92, 34.15]),
    },
    "jammu and kashmir": {
        "id": "aoi_canonical_jammu_kashmir",
        "name": "Jammu & Kashmir",
        "country": "India",
        "center": {"latitude": 33.7782, "longitude": 76.5762},
        "area_km2": 42241.0,
        "bbox": [73.75, 32.28, 77.80, 35.50],
        "polygon": _bbox_polygon([73.75, 32.28, 77.80, 35.50]),
    },
    "jammu & kashmir": {
        "id": "aoi_canonical_jammu_kashmir",
        "name": "Jammu & Kashmir",
        "country": "India",
        "center": {"latitude": 33.7782, "longitude": 76.5762},
        "area_km2": 42241.0,
        "bbox": [73.75, 32.28, 77.80, 35.50],
        "polygon": _bbox_polygon([73.75, 32.28, 77.80, 35.50]),
    },
    "delhi": {
        "id": "aoi_canonical_delhi",
        "name": "Delhi",
        "country": "India",
        "center": {"latitude": 28.6139, "longitude": 77.2090},
        "area_km2": 1484.0,
        "bbox": [76.84, 28.40, 77.35, 28.88],
        "polygon": _bbox_polygon([76.84, 28.40, 77.35, 28.88]),
    },
    "mumbai": {
        "id": "aoi_canonical_mumbai",
        "name": "Mumbai",
        "country": "India",
        "center": {"latitude": 19.0760, "longitude": 72.8777},
        "area_km2": 603.4,
        "bbox": [72.77, 18.89, 73.00, 19.27],
        "polygon": _bbox_polygon([72.77, 18.89, 73.00, 19.27]),
    },
    "bengaluru": {
        "id": "aoi_canonical_bengaluru",
        "name": "Bengaluru",
        "country": "India",
        "center": {"latitude": 12.9716, "longitude": 77.5946},
        "area_km2": 741.0,
        "bbox": [77.45, 12.83, 77.75, 13.14],
        "polygon": _bbox_polygon([77.45, 12.83, 77.75, 13.14]),
    },
    "bangalore": {
        "id": "aoi_canonical_bengaluru",
        "name": "Bengaluru",
        "country": "India",
        "center": {"latitude": 12.9716, "longitude": 77.5946},
        "area_km2": 741.0,
        "bbox": [77.45, 12.83, 77.75, 13.14],
        "polygon": _bbox_polygon([77.45, 12.83, 77.75, 13.14]),
    },
    "chennai": {
        "id": "aoi_canonical_chennai",
        "name": "Chennai",
        "country": "India",
        "center": {"latitude": 13.0827, "longitude": 80.2707},
        "area_km2": 426.0,
        "bbox": [80.14, 12.92, 80.35, 13.24],
        "polygon": _bbox_polygon([80.14, 12.92, 80.35, 13.24]),
    },
    "kolkata": {
        "id": "aoi_canonical_kolkata",
        "name": "Kolkata",
        "country": "India",
        "center": {"latitude": 22.5726, "longitude": 88.3639},
        "area_km2": 206.1,
        "bbox": [88.24, 22.45, 88.48, 22.66],
        "polygon": _bbox_polygon([88.24, 22.45, 88.48, 22.66]),
    },
    "hyderabad": {
        "id": "aoi_canonical_hyderabad",
        "name": "Hyderabad",
        "country": "India",
        "center": {"latitude": 17.3850, "longitude": 78.4867},
        "area_km2": 650.0,
        "bbox": [78.30, 17.25, 78.60, 17.55],
        "polygon": _bbox_polygon([78.30, 17.25, 78.60, 17.55]),
    },
    "pune": {
        "id": "aoi_canonical_pune",
        "name": "Pune",
        "country": "India",
        "center": {"latitude": 18.5204, "longitude": 73.8567},
        "area_km2": 331.3,
        "bbox": [73.72, 18.42, 73.98, 18.62],
        "polygon": _bbox_polygon([73.72, 18.42, 73.98, 18.62]),
    },
    "uttarakhand": {
        "id": "aoi_canonical_uttarakhand",
        "name": "Uttarakhand",
        "country": "India",
        "center": {"latitude": 30.0668, "longitude": 79.0193},
        "area_km2": 53483.0,
        "bbox": [77.57, 28.72, 81.04, 31.46],
        "polygon": _bbox_polygon([77.57, 28.72, 81.04, 31.46]),
    },
    "derna": {
        "id": "aoi_canonical_derna",
        "name": "Derna",
        "country": "Libya",
        "center": {"latitude": 32.7670, "longitude": 22.6367},
        "area_km2": 45.0,
        "bbox": [22.58, 32.72, 22.70, 32.82],
        "polygon": _bbox_polygon([22.58, 32.72, 22.70, 32.82]),
    },
    "leh": {
        "id": "aoi_canonical_leh",
        "name": "Leh Ladakh",
        "country": "India",
        "center": {"latitude": 34.1526, "longitude": 77.5771},
        "area_km2": 45110.0,
        "bbox": [76.50, 33.50, 78.80, 35.00],
        "polygon": _bbox_polygon([76.50, 33.50, 78.80, 35.00]),
    },
    "ladakh": {
        "id": "aoi_canonical_ladakh",
        "name": "Ladakh",
        "country": "India",
        "center": {"latitude": 34.1526, "longitude": 77.5771},
        "area_km2": 59146.0,
        "bbox": [75.50, 32.50, 79.50, 35.80],
        "polygon": _bbox_polygon([75.50, 32.50, 79.50, 35.80]),
    },
    "kathmandu": {
        "id": "aoi_canonical_kathmandu",
        "name": "Kathmandu",
        "country": "Nepal",
        "center": {"latitude": 27.7172, "longitude": 85.3240},
        "area_km2": 49.45,
        "bbox": [85.28, 27.67, 85.38, 27.75],
        "polygon": _bbox_polygon([85.28, 27.67, 85.38, 27.75]),
    },
    "nepal": {
        "id": "aoi_canonical_nepal",
        "name": "Nepal",
        "country": "Nepal",
        "center": {"latitude": 28.3949, "longitude": 84.1240},
        "area_km2": 147181.0,
        "bbox": [80.05, 26.34, 88.20, 30.45],
        "polygon": _bbox_polygon([80.05, 26.34, 88.20, 30.45]),
    }
}


def resolve_aoi(name: str) -> AOIInfo:
    """Resolve ``name`` using canonical gazetteer or Nominatim, with policy-compliant caching/rate limiting."""
    global _LAST_REQUEST
    query = (name or "").strip()
    if not query:
        raise AOIResolutionError("A valid location name is required for geocoding.")

    # 1. Check Canonical Gazetteer First
    clean_k = query.casefold().replace(", india", "").replace(", libya", "").strip()
    if clean_k in CANONICAL_AOI_REGISTRY:
        return AOIInfo.model_validate(CANONICAL_AOI_REGISTRY[clean_k])

    # Guard: never send natural language conversational sentences to Nominatim
    words = query.split()
    conversational_prefixes = (
        "so is it", "why", "what is", "what dataset", "which dataset",
        "how come", "how does", "is it", "explain", "tell me", "show it",
        "show on", "compare", "can you", "what does"
    )
    if len(words) > 5 or any(query.lower().startswith(p) for p in conversational_prefixes):
        raise AOIResolutionError(f"I couldn't identify a location in '{query}'. Please provide a recognized place or administrative boundary.")

    cache = _load_cache()
    cached = cache.get(query.casefold())
    if cached:
        return AOIInfo.model_validate(cached)

    with _RATE_LOCK:
        wait = 1.0 - (time.monotonic() - _LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        try:
            response = httpx.get(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1},
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
                timeout=20.0,
            )
            _LAST_REQUEST = time.monotonic()
            response.raise_for_status()
            places = response.json()
        except httpx.HTTPError as exc:
            raise AOIResolutionError(f"Nominatim request failed: {exc}") from exc

    if not places:
        raise AOIResolutionError(f"I couldn't identify the location '{query}'. Please provide a recognized place or administrative boundary.")

    place = places[0]
    try:
        lat = float(place["lat"])
        lon = float(place["lon"])
        south, north, west, east = (float(value) for value in place["boundingbox"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AOIResolutionError(f"I couldn't identify valid coordinates for '{query}'. Please provide a recognized place or administrative boundary.") from exc

    bbox = [west, south, east, north]
    lat_km = abs(north - south) * 111.32
    lon_km = abs(east - west) * 111.32 * max(0.01, abs(math.cos(math.radians(lat))))
    result = AOIInfo(
        id=f"aoi_nominatim_{abs(hash(query))}",
        name=place.get("display_name", query).split(",")[0],
        country=place.get("address", {}).get("country"),
        center=Coordinates(latitude=lat, longitude=lon),
        area_km2=round(lat_km * lon_km, 3),
        bbox=bbox,
        polygon=_bbox_polygon(bbox),
    )
    cache[query.casefold()] = result.model_dump()
    _save_cache(cache)
    return result
