"""
app/services/satellite_data.py
─────────────────────────────────────────────────────────────────────────────
Satellite data acquisition service.

This module abstracts three satellite data providers behind a single interface:

  ┌──────────────────────────────────────────────────────────────────────────┐
  │  SatelliteDataService (facade)                                           │
  │    ├── CopernicusProvider  → Sentinel-1 (SAR), Sentinel-2 (optical)     │
  │    ├── USGSProvider        → Landsat 8 / Landsat 9                       │
  │    └── NASACMRProvider     → VIIRS, MODIS                                │
  └──────────────────────────────────────────────────────────────────────────┘

DATA APIs USED (no STAC):
  Copernicus: OData API
    Catalogue: https://catalogue.dataspace.copernicus.eu/odata/v1
    Auth:      OAuth2 token from identity.dataspace.copernicus.eu (CDSE)

  USGS M2M:  JSON API
    Endpoint:  https://m2m.cr.usgs.gov/api/api/json/stable/
    Auth:      username + application token → session API key

  NASA CMR:  REST search API
    Endpoint:  https://cmr.earthdata.nasa.gov/search
    Auth:      None required for public collections

MOCK MODE:
  When model_mode="mock", all provider calls return synthetic SatelliteDataset
  objects with realistic structure but fake product IDs / URLs.
  No real API credentials are required in mock mode.

REAL MODE NOTES:
  - Copernicus: register at https://dataspace.copernicus.eu (free)
  - USGS:       register at https://ers.cr.usgs.gov/register (free)
  - NASA CMR:   no registration required for most public collections

  Asset URLs returned by real providers are direct download links (may require
  auth headers for Copernicus) or S3-style signed URLs for USGS.
"""

import json
from typing import Any, Optional
from datetime import datetime, timedelta
import httpx
from loguru import logger

from app.config import settings
from app.schemas.satellite import SatelliteDataset, SatelliteAsset
from app.schemas.requests import (
    FetchSentinel1Input,
    FetchSentinel2Input,
    FetchLandsatInput,
    FetchViirsModisInput,
    FetchMultitemporalSentinel2Input,
)


# ─────────────────────────────────────────────────────────────────────────────
# Copernicus Data Space Ecosystem (Sentinel-1, Sentinel-2)
# OData API: https://catalogue.dataspace.copernicus.eu/odata/v1
# ─────────────────────────────────────────────────────────────────────────────

class CopernicusProvider:
    """
    Accesses Sentinel-1 and Sentinel-2 data via the Copernicus Data Space
    Ecosystem (CDSE) OData API.

    API docs: https://documentation.dataspace.copernicus.eu/APIs/OData.html
    """

    ODATA_BASE = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    TOKEN_URL = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
        "/protocol/openid-connect/token"
    )

    def _get_access_token(self) -> str:
        """
        Obtain an OAuth2 Bearer token from CDSE.
        Token is valid for ~10 minutes.
        """
        if not settings.copernicus_user or not settings.copernicus_password:
            raise RuntimeError(
                "Copernicus credentials not configured. "
                "Set COPERNICUS_USER and COPERNICUS_PASSWORD in .env."
            )

        logger.debug("CopernicusProvider: fetching access token")
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                self.TOKEN_URL,
                data={
                    "client_id": "cdse-public",
                    "grant_type": "password",
                    "username": settings.copernicus_user,
                    "password": settings.copernicus_password,
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    def _bbox_to_wkt(self, bbox: list[float]) -> str:
        """Convert [minx, miny, maxx, maxy] bbox to WKT POLYGON string."""
        minx, miny, maxx, maxy = bbox
        return (
            f"POLYGON(({minx} {miny},{maxx} {miny},"
            f"{maxx} {maxy},{minx} {maxy},{minx} {miny}))"
        )

    def fetch_sentinel1(self, params: FetchSentinel1Input) -> list[SatelliteDataset]:
        """
        Query the CDSE OData API for Sentinel-1 GRD/SLC products.

        Returns:
            List of normalized SatelliteDataset objects (up to params.max_results)
        """
        logger.info(
            f"CopernicusProvider.fetch_sentinel1 | bbox={params.bbox} | "
            f"{params.start_date} → {params.end_date} | product={params.product_type}"
        )

        token = self._get_access_token()
        wkt = self._bbox_to_wkt(params.bbox)

        # Build the OData filter string
        # Sentinel-1 collection on CDSE is "SENTINEL-1"
        odata_filter = (
            f"Collection/Name eq 'SENTINEL-1' and "
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and "
            f"att/OData.CSC.StringAttribute/Value eq '{params.product_type}') and "
            f"ContentDate/Start ge {params.start_date}T00:00:00.000Z and "
            f"ContentDate/Start lt {params.end_date}T23:59:59.999Z and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')"
        )

        if params.polarization:
            odata_filter += (
                f" and Attributes/OData.CSC.StringAttribute/any("
                f"att:att/Name eq 'polarisationChannels' and "
                f"att/OData.CSC.StringAttribute/Value eq '{params.polarization}')"
            )

        if params.orbit_direction:
            odata_filter += (
                f" and Attributes/OData.CSC.StringAttribute/any("
                f"att:att/Name eq 'orbitDirection' and "
                f"att/OData.CSC.StringAttribute/Value eq '{params.orbit_direction}')"
            )

        url = f"{self.ODATA_BASE}/Products"
        query_params = {
            "$filter": odata_filter,
            "$top": params.max_results,
            "$orderby": "ContentDate/Start desc",
        }

        logger.debug(f"CopernicusProvider OData query: {url} | filter={odata_filter}")

        with httpx.Client(
            timeout=60.0,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            response = client.get(url, params=query_params)
            response.raise_for_status()
            data = response.json()

        products = data.get("value", [])
        logger.info(f"CopernicusProvider: found {len(products)} Sentinel-1 products")

        results = []
        for product in products:
            dataset = self._normalize_sentinel1(product, params)
            results.append(dataset)

        return results

    def _normalize_sentinel1(
        self, product: dict[str, Any], params: FetchSentinel1Input
    ) -> SatelliteDataset:
        """Normalize a CDSE OData Sentinel-1 product record to SatelliteDataset."""
        product_id = product.get("Name", "")
        product_uuid = product.get("Id", "")
        acquisition_time = product.get("ContentDate", {}).get("Start", "")

        # Footprint geometry comes as GeoJSON-like structure
        geo = product.get("Footprint", "") or product.get("GeoFootprint", {})

        download_url = f"{self.ODATA_BASE}/Products({product_uuid})/$value"

        return SatelliteDataset(
            source="sentinel-1",
            product_id=product_id,
            sensor="sar",
            platform="Sentinel-1",
            acquisition_time=acquisition_time,
            bbox=params.bbox,
            crs="EPSG:4326",
            bands=[params.polarization or "VV"],
            assets=[
                SatelliteAsset(
                    band=params.polarization or "VV",
                    url=download_url,
                    format="SAFE",
                )
            ],
            cloud_cover_pct=None,  # SAR is cloud-independent
            metadata={
                "product_uuid": product_uuid,
                "product_type": params.product_type,
                "orbit_direction": params.orbit_direction,
                "odata_record": product,
            },
            mode="real",
        )

    def fetch_sentinel2(self, params: FetchSentinel2Input) -> list[SatelliteDataset]:
        """
        Query the CDSE OData API for Sentinel-2 MSI products.

        Returns:
            List of normalized SatelliteDataset objects
        """
        logger.info(
            f"CopernicusProvider.fetch_sentinel2 | bbox={params.bbox} | "
            f"{params.start_date} → {params.end_date} | "
            f"cloud≤{params.max_cloud_cover}%"
        )

        token = self._get_access_token()
        wkt = self._bbox_to_wkt(params.bbox)

        # Map product_type to CDSE collection attribute
        product_type_map = {
            "S2MSI2A": "S2MSI2A",
            "S2MSI1C": "S2MSI1C",
        }
        cdse_product_type = product_type_map.get(params.product_type, "S2MSI2A")

        odata_filter = (
            f"Collection/Name eq 'SENTINEL-2' and "
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and "
            f"att/OData.CSC.StringAttribute/Value eq '{cdse_product_type}') and "
            f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and "
            f"att/OData.CSC.DoubleAttribute/Value le {params.max_cloud_cover}) and "
            f"ContentDate/Start ge {params.start_date}T00:00:00.000Z and "
            f"ContentDate/Start lt {params.end_date}T23:59:59.999Z and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')"
        )

        url = f"{self.ODATA_BASE}/Products"
        query_params = {
            "$filter": odata_filter,
            "$top": params.max_results,
            "$orderby": "ContentDate/Start desc",
        }

        logger.debug(f"CopernicusProvider Sentinel-2 query: {odata_filter}")

        with httpx.Client(
            timeout=60.0,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            response = client.get(url, params=query_params)
            response.raise_for_status()
            data = response.json()

        products = data.get("value", [])
        logger.info(f"CopernicusProvider: found {len(products)} Sentinel-2 products")

        results = []
        for product in products:
            dataset = self._normalize_sentinel2(product, params)
            results.append(dataset)

        return results

    def _normalize_sentinel2(
        self, product: dict[str, Any], params: FetchSentinel2Input
    ) -> SatelliteDataset:
        """Normalize a CDSE Sentinel-2 product record to SatelliteDataset."""
        product_id = product.get("Name", "")
        product_uuid = product.get("Id", "")
        acquisition_time = product.get("ContentDate", {}).get("Start", "")

        # Extract cloud cover from attributes
        attrs = product.get("Attributes", []) or []
        cloud_cover = None
        for attr in attrs:
            if attr.get("Name") == "cloudCover":
                cloud_cover = attr.get("Value")
                break

        download_url = f"{self.ODATA_BASE}/Products({product_uuid})/$value"

        # Standard Sentinel-2 L2A bands
        all_bands = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"]
        selected_bands = params.bands if params.bands else all_bands

        assets = [
            SatelliteAsset(band=band, url=download_url, format="SAFE")
            for band in selected_bands
        ]

        return SatelliteDataset(
            source="sentinel-2",
            product_id=product_id,
            sensor="optical",
            platform="Sentinel-2",
            acquisition_time=acquisition_time,
            bbox=params.bbox,
            crs="EPSG:4326",
            bands=selected_bands,
            assets=assets,
            cloud_cover_pct=cloud_cover,
            metadata={
                "product_uuid": product_uuid,
                "product_type": params.product_type,
                "odata_record": product,
            },
            mode="real",
        )


# ─────────────────────────────────────────────────────────────────────────────
# USGS M2M API (Landsat 8/9)
# Endpoint: https://m2m.cr.usgs.gov/api/api/json/stable/
# Docs: https://m2m.cr.usgs.gov/api/docs/json/
# ─────────────────────────────────────────────────────────────────────────────

class USGSProvider:
    """
    Accesses Landsat 8 / Landsat 9 data via the USGS Machine-to-Machine (M2M)
    JSON API.

    Authentication flow:
      1. POST /login-token with username + token → get apiKey
      2. Use apiKey in all subsequent requests via X-Auth-Token header
      3. POST /logout to release the session
    """

    M2M_BASE = "https://m2m.cr.usgs.gov/api/api/json/stable"

    def _get_api_key(self) -> str:
        """
        Login to USGS M2M and obtain a session API key.
        Uses application token authentication (recommended over password auth).
        """
        if not settings.usgs_username or not settings.usgs_token:
            raise RuntimeError(
                "USGS credentials not configured. "
                "Set USGS_USERNAME and USGS_TOKEN in .env."
            )

        logger.debug("USGSProvider: logging in to M2M API")
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.M2M_BASE}/login-token",
                json={
                    "username": settings.usgs_username,
                    "token": settings.usgs_token,
                },
            )
            response.raise_for_status()
            result = response.json()
            api_key = result.get("data")
            if not api_key:
                raise RuntimeError(
                    f"USGS M2M login failed: {result.get('errorMessage', 'unknown error')}"
                )
            return api_key

    def _logout(self, api_key: str) -> None:
        """Release the USGS M2M session."""
        try:
            with httpx.Client(timeout=15.0) as client:
                client.post(
                    f"{self.M2M_BASE}/logout",
                    headers={"X-Auth-Token": api_key},
                )
        except Exception as e:
            logger.warning(f"USGSProvider: logout failed (non-critical): {e}")

    def fetch_landsat(self, params: FetchLandsatInput) -> list[SatelliteDataset]:
        """
        Search for Landsat scenes via USGS M2M scene-search.

        Returns:
            List of normalized SatelliteDataset objects
        """
        logger.info(
            f"USGSProvider.fetch_landsat | bbox={params.bbox} | "
            f"{params.start_date} → {params.end_date} | "
            f"dataset={params.platform} | cloud≤{params.max_cloud_cover}%"
        )

        api_key = self._get_api_key()

        try:
            minx, miny, maxx, maxy = params.bbox

            search_body = {
                "datasetName": params.platform,
                "temporalFilter": {
                    "start": params.start_date,
                    "end": params.end_date,
                },
                "spatialFilter": {
                    "filterType": "mbr",
                    "lowerLeft": {"latitude": miny, "longitude": minx},
                    "upperRight": {"latitude": maxy, "longitude": maxx},
                },
                "cloudCoverFilter": {
                    "max": params.max_cloud_cover,
                    "includeUnknown": False,
                },
                "maxResults": params.max_results,
                "startingNumber": 1,
                "sortOrder": "DESC",
            }

            logger.debug(f"USGSProvider scene-search: {json.dumps(search_body)}")

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.M2M_BASE}/scene-search",
                    json=search_body,
                    headers={"X-Auth-Token": api_key},
                )
                response.raise_for_status()
                data = response.json()

            if data.get("errorCode"):
                raise RuntimeError(
                    f"USGS M2M scene-search error: {data['errorCode']} — "
                    f"{data.get('errorMessage', '')}"
                )

            scenes = (data.get("data") or {}).get("results", [])
            logger.info(f"USGSProvider: found {len(scenes)} Landsat scenes")

            results = []
            for scene in scenes:
                dataset = self._normalize_landsat(scene, params)
                results.append(dataset)

            return results

        finally:
            self._logout(api_key)

    def _normalize_landsat(
        self, scene: dict[str, Any], params: FetchLandsatInput
    ) -> SatelliteDataset:
        """Normalize a USGS M2M scene record to SatelliteDataset."""
        entity_id = scene.get("entityId", "")
        display_id = scene.get("displayId", "")
        acquired = scene.get("temporalCoverage", {}).get("startDate", "")
        cloud_cover = scene.get("cloudCover")

        # Determine platform from dataset name
        platform = "Landsat-9" if "ot" in params.platform else "Landsat-7"

        # Landsat Collection 2 Level-2 standard bands
        bands = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7", "ST_B10"]

        # Build a placeholder download URL — real download requires
        # the download-request and download-retrieve M2M endpoints
        download_url = f"https://earthexplorer.usgs.gov/order/process?node=EE&entityIds={entity_id}"

        assets = [
            SatelliteAsset(band=band, url=download_url, format="GeoTIFF")
            for band in bands
        ]

        spatial = scene.get("spatialCoverage", {})
        min_lon = spatial.get("west", params.bbox[0])
        min_lat = spatial.get("south", params.bbox[1])
        max_lon = spatial.get("east", params.bbox[2])
        max_lat = spatial.get("north", params.bbox[3])

        return SatelliteDataset(
            source=params.platform.replace("_", "-"),
            product_id=display_id,
            sensor="optical",
            platform=platform,
            acquisition_time=acquired,
            bbox=[min_lon, min_lat, max_lon, max_lat],
            crs="EPSG:4326",
            bands=bands,
            assets=assets,
            cloud_cover_pct=cloud_cover,
            metadata={
                "entity_id": entity_id,
                "dataset_name": params.platform,
                "usgs_record": scene,
            },
            mode="real",
        )


# ─────────────────────────────────────────────────────────────────────────────
# NASA CMR (VIIRS, MODIS)
# Endpoint: https://cmr.earthdata.nasa.gov/search
# Docs: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
# ─────────────────────────────────────────────────────────────────────────────

class NASACMRProvider:
    """
    Accesses VIIRS and MODIS granule data via the NASA Common Metadata
    Repository (CMR) REST search API.

    No authentication required for public collections.
    """

    def fetch_viirs_modis(self, params: FetchViirsModisInput) -> list[SatelliteDataset]:
        """
        Search for VIIRS/MODIS granules via NASA CMR.

        Returns:
            List of normalized SatelliteDataset objects
        """
        logger.info(
            f"NASACMRProvider.fetch_viirs_modis | bbox={params.bbox} | "
            f"{params.start_date} → {params.end_date} | "
            f"collection={params.collection}"
        )

        minx, miny, maxx, maxy = params.bbox
        bounding_box = f"{minx},{miny},{maxx},{maxy}"

        query_params = {
            "short_name": params.collection,
            "temporal": f"{params.start_date}T00:00:00Z,{params.end_date}T23:59:59Z",
            "bounding_box": bounding_box,
            "page_size": params.max_results,
            "sort_key": "-start_date",
        }

        search_url = f"{settings.nasa_cmr_base_url}/granules.json"
        logger.debug(f"NASACMRProvider CMR query: {search_url} | params={query_params}")

        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                search_url,
                params=query_params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        granules = data.get("feed", {}).get("entry", [])
        logger.info(f"NASACMRProvider: found {len(granules)} {params.collection} granules")

        results = []
        for granule in granules:
            dataset = self._normalize_granule(granule, params)
            results.append(dataset)

        return results

    def _normalize_granule(
        self, granule: dict[str, Any], params: FetchViirsModisInput
    ) -> SatelliteDataset:
        """Normalize a NASA CMR granule record to SatelliteDataset."""
        granule_id = granule.get("id", "")
        title = granule.get("title", "")
        time_start = granule.get("time_start", "")

        # Extract bounding box from granule spatial information
        boxes = granule.get("boxes", [])
        if boxes:
            # CMR boxes format: "south west north east"
            parts = boxes[0].split()
            if len(parts) == 4:
                s, w, n, e = [float(p) for p in parts]
                bbox = [w, s, e, n]
            else:
                bbox = params.bbox
        else:
            bbox = params.bbox

        # Extract download URLs from links
        links = granule.get("links", [])
        download_urls = [
            lnk["href"] for lnk in links
            if lnk.get("rel", "").endswith("/data#")
            and not lnk.get("inherited", False)
        ]

        # Standard VIIRS/MODIS bands (varies by product — use generic)
        sensor = params.sensor.lower()
        if sensor == "viirs":
            bands = ["I1", "I2", "I3", "M1", "M2", "M3", "M4", "M5", "M7", "M10"]
        else:
            bands = ["Band1", "Band2", "Band3", "Band4", "Band7"]

        assets = [
            SatelliteAsset(band="composite", url=url, format="HDF4")
            for url in download_urls[:5]  # limit to first 5 links
        ]

        return SatelliteDataset(
            source=sensor,
            product_id=title or granule_id,
            sensor="optical",
            platform=params.sensor,
            acquisition_time=time_start,
            bbox=bbox,
            crs="EPSG:4326",
            bands=bands,
            assets=assets,
            cloud_cover_pct=None,
            metadata={
                "granule_id": granule_id,
                "collection": params.collection,
                "cmr_record": granule,
            },
            mode="real",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Mock Providers
# ─────────────────────────────────────────────────────────────────────────────

class MockSatelliteDataService:
    """
    Returns realistic but synthetic SatelliteDataset objects.
    Used when model_mode="mock" — no real API calls are made.
    Implements the same interface as the real providers.
    """

    def fetch_sentinel1(self, params: FetchSentinel1Input) -> list[SatelliteDataset]:
        logger.debug(f"[MockSatellite] fetch_sentinel1 | bbox={params.bbox}")
        return [
            SatelliteDataset(
                source="sentinel-1",
                product_id=f"S1A_IW_GRDH_1SDV_{params.start_date.replace('-', '')}T053842_MOCK",
                sensor="sar",
                platform="Sentinel-1A",
                acquisition_time=f"{params.start_date}T05:38:42Z",
                bbox=params.bbox,
                crs="EPSG:4326",
                bands=[params.polarization or "VV", "VH"],
                assets=[
                    SatelliteAsset(band="VV", url="https://mock-cdse.example.com/s1-vv.tif", format="GeoTIFF"),
                    SatelliteAsset(band="VH", url="https://mock-cdse.example.com/s1-vh.tif", format="GeoTIFF"),
                ],
                cloud_cover_pct=None,
                metadata={"product_type": params.product_type, "mock": True},
                mode="mock",
            )
        ]

    def fetch_sentinel2(self, params: FetchSentinel2Input) -> list[SatelliteDataset]:
        logger.debug(f"[MockSatellite] fetch_sentinel2 | bbox={params.bbox}")
        bands = params.bands or ["B02", "B03", "B04", "B08", "B8A", "B11", "B12"]
        return [
            SatelliteDataset(
                source="sentinel-2",
                product_id=f"S2A_MSIL2A_{params.start_date.replace('-', '')}T053649_N0510_MOCK",
                sensor="optical",
                platform="Sentinel-2A",
                acquisition_time=f"{params.start_date}T05:36:49Z",
                bbox=params.bbox,
                crs="EPSG:4326",
                bands=bands,
                assets=[
                    SatelliteAsset(
                        band=b,
                        url=f"https://mock-cdse.example.com/s2-{b.lower()}.tif",
                        format="GeoTIFF",
                        resolution_m=10.0 if b in ("B02", "B03", "B04", "B08") else 20.0,
                    )
                    for b in bands
                ],
                cloud_cover_pct=4.2,
                metadata={"product_type": params.product_type, "mock": True},
                mode="mock",
            )
        ]

    def fetch_landsat(self, params: FetchLandsatInput) -> list[SatelliteDataset]:
        logger.debug(f"[MockSatellite] fetch_landsat | bbox={params.bbox}")
        bands = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7", "ST_B10"]
        return [
            SatelliteDataset(
                source="landsat-ot-c2-l2",
                product_id=f"LC09_L2SP_146040_{params.start_date.replace('-', '')}_MOCK",
                sensor="optical",
                platform="Landsat-9",
                acquisition_time=f"{params.start_date}T05:00:00Z",
                bbox=params.bbox,
                crs="EPSG:4326",
                bands=bands,
                assets=[
                    SatelliteAsset(
                        band=b,
                        url=f"https://mock-usgs.example.com/landsat-{b.lower()}.tif",
                        format="GeoTIFF",
                        resolution_m=30.0,
                    )
                    for b in bands
                ],
                cloud_cover_pct=8.1,
                metadata={"dataset": params.platform, "mock": True},
                mode="mock",
            )
        ]

    def fetch_viirs_modis(self, params: FetchViirsModisInput) -> list[SatelliteDataset]:
        logger.debug(f"[MockSatellite] fetch_viirs_modis | bbox={params.bbox}")
        return [
            SatelliteDataset(
                source=params.sensor.lower(),
                product_id=f"VNP09GA.A{params.start_date.replace('-', '').replace('-', '')}.h26v06.001.MOCK",
                sensor="optical",
                platform=params.sensor,
                acquisition_time=f"{params.start_date}T10:30:00Z",
                bbox=params.bbox,
                crs="EPSG:4326",
                bands=["I1", "I2", "I3", "M1", "M7"],
                assets=[
                    SatelliteAsset(
                        band="I1",
                        url="https://mock-nasa.example.com/viirs-i1.h5",
                        format="HDF5",
                        resolution_m=375.0,
                    )
                ],
                cloud_cover_pct=None,
                metadata={"collection": params.collection, "mock": True},
                mode="mock",
            )
        ]

    def fetch_multitemporal_sentinel2(
        self, params: FetchMultitemporalSentinel2Input
    ) -> list[SatelliteDataset]:
        """
        Return exactly 4 mock Sentinel-2 observations spread evenly across
        [start_date, end_date], ordered oldest → newest.

        Band naming follows Sentinel-2 native identifiers.
        The six bands here are the HLS subset required by the Prithvi pipeline:

            S2 B02  → HLS slot B01  (Blue,        490 nm, 10 m)
            S2 B03  → HLS slot B02  (Green,       560 nm, 10 m)
            S2 B04  → HLS slot B03  (Red,         665 nm, 10 m)
            S2 B08A → HLS slot B04  (Narrow NIR,  865 nm, 20 m)
            S2 B11  → HLS slot B05  (SWIR-1,     1610 nm, 20 m)
            S2 B12  → HLS slot B06  (SWIR-2,     2190 nm, 20 m)

        mock:// URLs signal unambiguously that these are not real download links.
        """
        logger.debug(
            f"[MockSatellite] fetch_multitemporal_sentinel2 | bbox={params.bbox} | "
            f"{params.start_date} → {params.end_date}"
        )

        # ── Distribute 4 acquisition dates across the requested window ─────────
        # Simple approach: divide the interval into 4 equal thirds and pick the
        # midpoint of each sub-interval, giving 4 well-spaced observations.
        start = datetime.strptime(params.start_date, "%Y-%m-%d")
        end   = datetime.strptime(params.end_date,   "%Y-%m-%d")
        total_days = (end - start).days

        # Guard: if window is very narrow (<4 days), fall back to daily spacing
        if total_days < 3:
            step = timedelta(days=1)
            acquisition_dates = [start + step * i for i in range(4)]
        else:
            segment = total_days / 4
            acquisition_dates = [
                start + timedelta(days=segment * i + segment / 2)
                for i in range(4)
            ]

        # The six HLS-required Sentinel-2 bands with their native resolutions
        HLS_BANDS = [
            ("B02",  10.0),
            ("B03",  10.0),
            ("B04",  10.0),
            ("B08A", 20.0),
            ("B11",  20.0),
            ("B12",  20.0),
        ]

        datasets: list[SatelliteDataset] = []
        for i, acq_dt in enumerate(acquisition_dates):
            date_str = acq_dt.strftime("%Y%m%d")
            acq_ts   = acq_dt.strftime("%Y-%m-%dT10:30:00Z")
            product_id = (
                f"S2A_MSIL2A_{date_str}T103000_N0510_R005_MOCK_FRAME{i+1:02d}"
            )

            assets = [
                SatelliteAsset(
                    band=band,
                    url=(
                        f"mock://sentinel2/{date_str}/"
                        f"{params.product_type}/{band}.tif"
                    ),
                    format="GeoTIFF",
                    resolution_m=res,
                )
                for band, res in HLS_BANDS
            ]

            datasets.append(
                SatelliteDataset(
                    source="sentinel-2",
                    product_id=product_id,
                    sensor="optical",
                    platform="Sentinel-2A",
                    acquisition_time=acq_ts,
                    bbox=params.bbox,
                    crs="EPSG:4326",
                    bands=[b for b, _ in HLS_BANDS],
                    assets=assets,
                    cloud_cover_pct=round(2.0 + i * 1.5, 1),  # plausible mock values
                    metadata={
                        "product_type": params.product_type,
                        "frame_index": i,
                        "hls_band_mapping": {
                            "B02":  "HLS_B01",
                            "B03":  "HLS_B02",
                            "B04":  "HLS_B03",
                            "B08A": "HLS_B04",
                            "B11":  "HLS_B05",
                            "B12":  "HLS_B06",
                        },
                        "mock": True,
                    },
                    mode="mock",
                )
            )

        # Guarantee oldest → newest order (already true for mock, but be explicit)
        datasets.sort(key=lambda d: d.acquisition_time)
        logger.debug(
            f"[MockSatellite] fetch_multitemporal_sentinel2 → "
            f"{len(datasets)} frames: "
            f"{[d.acquisition_time for d in datasets]}"
        )
        return datasets


# ─────────────────────────────────────────────────────────────────────────────
# Service Facade
# ─────────────────────────────────────────────────────────────────────────────

class SatelliteDataService:
    """
    The main satellite data service used by acquisition tools.

    Delegates to the appropriate provider (real or mock) based on model_mode.
    The tools only need to know about this class — not the individual providers.
    """

    def __init__(self) -> None:
        if settings.model_mode == "real":
            self._copernicus = CopernicusProvider()
            self._usgs = USGSProvider()
            self._nasa_cmr = NASACMRProvider()
            self._mock = None
            logger.info("SatelliteDataService: real mode (Copernicus + USGS + NASA CMR)")
        else:
            self._copernicus = None
            self._usgs = None
            self._nasa_cmr = None
            self._mock = MockSatelliteDataService()
            logger.info("SatelliteDataService: mock mode — no real API calls")

    def fetch_sentinel1(self, params: FetchSentinel1Input) -> list[SatelliteDataset]:
        if self._mock:
            return self._mock.fetch_sentinel1(params)
        return self._copernicus.fetch_sentinel1(params)

    def fetch_sentinel2(self, params: FetchSentinel2Input) -> list[SatelliteDataset]:
        if self._mock:
            return self._mock.fetch_sentinel2(params)
        return self._copernicus.fetch_sentinel2(params)

    def fetch_landsat(self, params: FetchLandsatInput) -> list[SatelliteDataset]:
        if self._mock:
            return self._mock.fetch_landsat(params)
        return self._usgs.fetch_landsat(params)

    def fetch_viirs_modis(self, params: FetchViirsModisInput) -> list[SatelliteDataset]:
        if self._mock:
            return self._mock.fetch_viirs_modis(params)
        return self._nasa_cmr.fetch_viirs_modis(params)

    def fetch_multitemporal_sentinel2(
        self, params: FetchMultitemporalSentinel2Input
    ) -> list[SatelliteDataset]:
        """
        Acquire exactly 4 Sentinel-2 observations for the Prithvi pipeline.

        Mock mode: returns deterministic synthetic frames with mock:// URLs.
        Real mode: not yet implemented — raises NotImplementedError to prevent
                   silent failures. Implement via CopernicusProvider when ready.
        """
        if self._mock:
            return self._mock.fetch_multitemporal_sentinel2(params)
        raise NotImplementedError(
            "Real multitemporal Sentinel-2 acquisition is not yet implemented. "
            "Use MODEL_MODE=mock for development."
        )


# Module-level singleton — created once at import time
satellite_service = SatelliteDataService()
