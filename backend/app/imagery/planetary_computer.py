"""Sentinel-2 imagery access through Microsoft Planetary Computer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from app.config import settings

COLLECTION = "sentinel-2-l2a"
CLOUD_LIMIT = 20.0


class ImageryError(RuntimeError):
    """Raised when the public catalog cannot provide usable imagery."""


@dataclass
class SceneData:
    item_id: str
    date: str
    red: Any
    green: Any
    blue: Any
    nir: Any
    profile: dict[str, Any]
    cloud_cover: float
    true_color_path: Path
    pixel_area_km2: float = 0.0001


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            try:
                return date(int(value), 1, 1)
            except ValueError:
                return default


def resolve_periods(start: str | None, end: str | None) -> tuple[date, date, date, date]:
    today = date.today()
    end_date = _parse_date(end, today)
    start_date = _parse_date(start, end_date - timedelta(days=365 * 2))
    if start_date >= end_date:
        raise ImageryError("Temporal scope start must precede temporal scope end")
    span = max(30, (end_date - start_date).days // 6)
    return start_date, end_date, start_date + timedelta(days=span), end_date - timedelta(days=span)


def _search_items(bbox: list[float], start: date, end: date) -> list[Any]:
    try:
        import planetary_computer
        from pystac_client import Client
    except ImportError as exc:
        raise ImageryError("Install pystac-client and planetary-computer to fetch imagery") from exc

    try:
        catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
        search = catalog.search(
            collections=[COLLECTION],
            bbox=bbox,
            datetime=f"{start.isoformat()}/{end.isoformat()}",
            query={"eo:cloud_cover": {"lt": CLOUD_LIMIT}},
            max_items=500,
        )
        items = list(search.items())
    except Exception as exc:
        raise ImageryError(f"Planetary Computer STAC search failed: {exc}") from exc
    if not items:
        raise ImageryError(f"No Sentinel-2 scene with cloud cover below {CLOUD_LIMIT:g}% in {start} to {end}")
    return items


def _pick(items: Iterable[Any], target: date) -> Any:
    return min(
        items,
        key=lambda item: (
            float(item.properties.get("eo:cloud_cover", 100.0)),
            abs((item.datetime.date() - target).days),
        ),
    )


def _read_scene(item: Any, bbox: list[float], output_dir: Path, label: str, include_rgb: bool = True) -> SceneData:
    try:
        import planetary_computer
        import numpy as np
        import rasterio
        from PIL import Image
        from rasterio.windows import from_bounds
        from rasterio.warp import transform_bounds
    except ImportError as exc:
        raise ImageryError("Install rasterio, numpy, Pillow, and planetary-computer to read imagery") from exc

    assets = item.assets
    required = {"B04": "red", "B08": "nir"}
    if include_rgb:
        required.update({"B02": "blue", "B03": "green"})
    if any(key not in assets for key in required):
        raise ImageryError(f"Scene {item.id} does not contain required Sentinel-2 assets")

    bands: dict[str, Any] = {}
    profile: dict[str, Any] | None = None
    for key, name in required.items():
        href = planetary_computer.sign(assets[key].href)
        try:
            with rasterio.open(href) as src:
                window = from_bounds(*transform_bounds("EPSG:4326", src.crs, *bbox), transform=src.transform)
                window = window.round_offsets().round_lengths()
                target_width = min(int(window.width), 512)
                target_height = min(int(window.height), 512)
                with rasterio.Env(GDAL_CACHEMAX=64, CPL_VSIL_CURL_CACHE_SIZE=0):
                    data = src.read(
                        1,
                        window=window,
                        out_shape=(1, target_height, target_width),
                        resampling=rasterio.enums.Resampling.bilinear,
                        masked=True,
                    ).astype("float32")
                if profile is None:
                    profile = src.profile.copy()
                    transform = src.window_transform(window)
                    transform = transform * transform.scale(
                        window.width / target_width,
                        window.height / target_height,
                    )
                    profile.update(
                        width=data.shape[1], height=data.shape[0],
                        transform=transform, count=1, dtype="float32",
                    )
                bands[name] = data.filled(np.nan)
        except Exception as exc:
            raise ImageryError(f"Failed to download {key} for scene {item.id}: {exc}") from exc

    if profile is None:
        raise ImageryError(f"Scene {item.id} returned no raster data")

    output_dir.mkdir(parents=True, exist_ok=True)
    valid = np.isfinite(bands["red"]) & np.isfinite(bands["green"]) & np.isfinite(bands["blue"]) if include_rgb else np.isfinite(bands["red"]) & np.isfinite(bands["nir"])
    if not valid.any():
        raise ImageryError(f"Scene {item.id} has no valid pixels inside the AOI")
    png_path = output_dir / f"{label}-{item.id}.png"
    if include_rgb:
        rgb = np.stack([bands["red"], bands["green"], bands["blue"]])
        lo, hi = np.nanpercentile(rgb[:, valid], [2, 98])
        stretched = np.clip((rgb - lo) / max(hi - lo, 1), 0, 1)
        stretched[:, ~valid] = 0
        Image.fromarray((np.moveaxis(stretched, 0, -1) * 255).astype("uint8"), "RGB").save(png_path)
    transform = profile["transform"]
    pixel_area_km2 = abs(transform.a * transform.e - transform.b * transform.d) / 1_000_000
    return SceneData(
        item_id=item.id,
        date=item.datetime.date().isoformat(),
        red=bands["red"], green=bands.get("green", bands["red"]), blue=bands.get("blue", bands["red"]), nir=bands["nir"],
        profile=profile,
        cloud_cover=float(item.properties.get("eo:cloud_cover", 0.0)),
        true_color_path=png_path,
        pixel_area_km2=pixel_area_km2,
    )


def fetch_before_after_and_series(
    bbox: list[float], start: str | None, end: str | None, output_dir: str,
) -> tuple[SceneData, SceneData, list[SceneData]]:
    start_date, end_date, before_end, after_start = resolve_periods(start, end)
    all_items = _search_items(bbox, start_date, end_date)
    unique: dict[str, Any] = {item.id: item for item in all_items}
    chosen = sorted(unique.values(), key=lambda item: item.datetime)
    if not chosen:
        raise ImageryError(f"No usable Sentinel-2 scenes in {start_date} to {end_date}")
    # Select the best available observations nearest each requested endpoint.
    # A narrow sub-window can be empty even when valid scenes exist nearby.
    before_item = _pick(chosen, start_date)
    after_item = _pick(chosen, end_date)
    selected = chosen[-3:]
    out = Path(output_dir)
    before = _read_scene(before_item, bbox, out, "before")
    after = _read_scene(after_item, bbox, out, "after")
    loaded = {before.item_id: before, after.item_id: after}
    series = []
    for item in selected:
        if item.id in loaded:
            series.append(loaded[item.id])
        else:
            series.append(_read_scene(item, bbox, out, "series", include_rgb=False))
    return before, after, series
