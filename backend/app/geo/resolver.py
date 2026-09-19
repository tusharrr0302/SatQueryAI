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


def resolve_aoi(name: str) -> AOIInfo:
    """Resolve ``name`` using Nominatim, with policy-compliant caching/rate limiting."""
    global _LAST_REQUEST
    query = (name or "").strip()
    if not query:
        raise AOIResolutionError("AOI name is required")

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
        raise AOIResolutionError(f"Nominatim returned no AOI for '{query}'")

    place = places[0]
    try:
        lat = float(place["lat"])
        lon = float(place["lon"])
        south, north, west, east = (float(value) for value in place["boundingbox"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AOIResolutionError(f"Nominatim returned an invalid AOI for '{query}'") from exc

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
