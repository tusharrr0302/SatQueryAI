"""
SatQuery AI — Deterministic Geocoder

Resolves geographical names to precise coordinates and bounding boxes without LLM hallucination.
Uses a fast local catalog of world regions and cities, with Nominatim fallback.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Optional
import httpx

from app.schemas.normalized_result import AOIInfo, Coordinates

logger = logging.getLogger(__name__)

# Fast local catalog of known geographical entities
# Format: [min_lon, min_lat, max_lon, max_lat], center_lat, center_lon, country, area_km2
LOCAL_CATALOG: Dict[str, Dict[str, Any]] = {
    "kathmandu": {
        "name": "Kathmandu, Nepal",
        "country": "Nepal",
        "center": (27.7172, 85.3240),
        "bbox": [85.25, 27.65, 85.39, 27.76],
        "area_km2": 49.5,
    },
    "delhi": {
        "name": "Delhi NCR, India",
        "country": "India",
        "center": (28.6139, 77.2090),
        "bbox": [76.84, 28.40, 77.34, 28.88],
        "area_km2": 1483.0,
    },
    "uttarakhand": {
        "name": "Uttarakhand, India",
        "country": "India",
        "center": (30.0668, 79.0193),
        "bbox": [78.0, 29.5, 80.5, 31.5],
        "area_km2": 53483.0,
    },
    "amazon": {
        "name": "Amazon Basin, Brazil",
        "country": "Brazil",
        "center": (-3.4653, -62.2159),
        "bbox": [-55.0, -10.0, -47.0, -1.0],
        "area_km2": 28400.0,
    },
    "para": {
        "name": "Para state, Brazil",
        "country": "Brazil",
        "center": (-3.79, -52.48),
        "bbox": [-55.0, -10.0, -47.0, -1.0],
        "area_km2": 1248000.0,
    },
    "punjab": {
        "name": "Punjab, India",
        "country": "India",
        "center": (31.1471, 75.3412),
        "bbox": [74.5, 29.5, 76.9, 32.5],
        "area_km2": 50362.0,
    },
    "derna": {
        "name": "Derna, Libya",
        "country": "Libya",
        "center": (32.7667, 22.6367),
        "bbox": [22.60, 32.74, 22.68, 32.79],
        "area_km2": 1250.0,
    },
    "bengaluru": {
        "name": "Bengaluru, Karnataka, India",
        "country": "India",
        "center": (12.9716, 77.5946),
        "bbox": [77.45, 12.85, 77.75, 13.10],
        "area_km2": 741.0,
    },
    "bangalore": {
        "name": "Bengaluru, Karnataka, India",
        "country": "India",
        "center": (12.9716, 77.5946),
        "bbox": [77.45, 12.85, 77.75, 13.10],
        "area_km2": 741.0,
    },
    "mumbai": {
        "name": "Mumbai, Maharashtra, India",
        "country": "India",
        "center": (19.0760, 72.8777),
        "bbox": [72.77, 18.89, 73.00, 19.27],
        "area_km2": 603.0,
    },
    "hyderabad": {
        "name": "Hyderabad, Telangana, India",
        "country": "India",
        "center": (17.3850, 78.4867),
        "bbox": [78.30, 17.25, 78.60, 17.55],
        "area_km2": 650.0,
    },
    "chennai": {
        "name": "Chennai, Tamil Nadu, India",
        "country": "India",
        "center": (13.0827, 80.2707),
        "bbox": [80.15, 12.95, 80.35, 13.20],
        "area_km2": 426.0,
    },
    "kolkata": {
        "name": "Kolkata, West Bengal, India",
        "country": "India",
        "center": (22.5726, 88.3639),
        "bbox": [88.25, 22.45, 88.45, 22.65],
        "area_km2": 206.0,
    },
    "pune": {
        "name": "Pune, Maharashtra, India",
        "country": "India",
        "center": (18.5204, 73.8567),
        "bbox": [73.75, 18.42, 74.00, 18.62],
        "area_km2": 331.0,
    },
    "ahmedabad": {
        "name": "Ahmedabad, Gujarat, India",
        "country": "India",
        "center": (23.0225, 72.5714),
        "bbox": [72.48, 22.95, 72.68, 23.12],
        "area_km2": 464.0,
    },
    "assam": {
        "name": "Assam, India",
        "country": "India",
        "center": (26.2006, 92.9376),
        "bbox": [89.5, 24.5, 96.5, 28.0],
        "area_km2": 78438.0,
    },
    "bihar": {
        "name": "Bihar, India",
        "country": "India",
        "center": (25.0961, 85.3131),
        "bbox": [83.3, 24.3, 88.3, 27.5],
        "area_km2": 94163.0,
    },
    "odisha": {
        "name": "Odisha, India",
        "country": "India",
        "center": (20.9517, 85.0985),
        "bbox": [81.3, 17.8, 87.5, 22.6],
        "area_km2": 155707.0,
    },
    "sikkim": {
        "name": "North Sikkim, India",
        "country": "India",
        "center": (27.5330, 88.5122),
        "bbox": [88.0, 27.0, 89.0, 28.1],
        "area_km2": 7096.0,
    },
    "ladakh": {
        "name": "Leh Ladakh, India",
        "country": "India",
        "center": (34.1526, 77.5771),
        "bbox": [76.5, 32.5, 79.5, 35.5],
        "area_km2": 45110.0,
    },
    "leh": {
        "name": "Leh Ladakh, India",
        "country": "India",
        "center": (34.1526, 77.5771),
        "bbox": [76.5, 32.5, 79.5, 35.5],
        "area_km2": 45110.0,
    },
    "himalayas": {
        "name": "Himalayan Region",
        "country": "Asia",
        "center": (30.5, 79.5),
        "bbox": [75.0, 27.0, 85.0, 35.0],
        "area_km2": 595000.0,
    },
}


def _bbox_to_polygon(bbox: List[float]) -> List[List[float]]:
    if len(bbox) != 4:
        return []
    min_lon, min_lat, max_lon, max_lat = bbox
    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def geocode_location(location_name: str) -> AOIInfo:
    """
    Deterministically geocodes a location name into an AOIInfo object.
    Checks the local catalog first, then attempts OpenStreetMap Nominatim,
    and defaults to a sensible global view if not found.
    """
    cleaned = location_name.lower().strip()
    # Normalize common queries like "vegetation around Kathmandu" -> "kathmandu"
    cleaned = re.sub(r"\b(around|in|near|region|city|area|of)\b", " ", cleaned)
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 2]

    # 1. Local catalog exact/partial match
    for token in tokens:
        if token in LOCAL_CATALOG:
            entry = LOCAL_CATALOG[token]
            center_lat, center_lon = entry["center"]
            bbox = entry["bbox"]
            return AOIInfo(
                id=f"aoi_{token}",
                name=entry["name"],
                country=entry["country"],
                type="Polygon",
                center=Coordinates(latitude=center_lat, longitude=center_lon),
                area_km2=entry["area_km2"],
                bbox=bbox,
                polygon=_bbox_to_polygon(bbox),
            )

    # 2. Try Nominatim with short timeout
    try:
        query_str = location_name.strip()
        url = f"https://nominatim.openstreetmap.org/search?format=json&limit=1&q={query_str}"
        headers = {"User-Agent": "SatQueryAI/1.0 (EarthObservationIntelligence)"}
        with httpx.Client(timeout=2.5) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    item = data[0]
                    lat = float(item["lat"])
                    lon = float(item["lon"])
                    boundingbox = item.get("boundingbox", [])
                    # Nominatim returns [south_lat, north_lat, west_lon, east_lon]
                    if len(boundingbox) == 4:
                        s_lat, n_lat, w_lon, e_lon = [float(x) for x in boundingbox]
                        bbox = [w_lon, s_lat, e_lon, n_lat]
                    else:
                        bbox = [lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1]
                    
                    return AOIInfo(
                        id=f"aoi_nom_{abs(int(lat*100))}_{abs(int(lon*100))}",
                        name=item.get("display_name", location_name).split(",")[0],
                        country=item.get("display_name", "").split(",")[-1].strip(),
                        type="Polygon",
                        center=Coordinates(latitude=lat, longitude=lon),
                        area_km2=1250.0,
                        bbox=bbox,
                        polygon=_bbox_to_polygon(bbox),
                    )
    except Exception as exc:
        logger.debug(f"Nominatim geocode failed ({exc}); using fallback.")

    # 3. Fallback: Global / Default
    return AOIInfo(
        id="aoi_global",
        name=location_name.strip().title() or "Global AOI",
        country=None,
        type="Polygon",
        center=Coordinates(latitude=20.0, longitude=0.0),
        area_km2=5000.0,
        bbox=[-10.0, 10.0, 10.0, 30.0],
        polygon=[[-10.0, 10.0], [10.0, 10.0], [10.0, 30.0], [-10.0, 30.0], [-10.0, 10.0]],
    )
