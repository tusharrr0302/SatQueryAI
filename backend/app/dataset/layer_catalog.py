"""
SatQuery AI — Authoritative Earth Observation Layer Catalog
Defines the many-to-one relationship between Visualization Layers and Datasets (DATASET ≠ LAYER).
"""
from typing import Any, Dict, List, Optional
from app.schemas.data_catalog import LayerDefinition
from app.dataset.registry import resolve_canonical_dataset_id

_STATIC_LAYER_DEFINITIONS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 1. SENTINEL-2 MSI LEVEL-2A LAYERS
    # --------------------------------------------------------------------------
    {
        "layer_id": "sentinel2_rgb",
        "dataset_id": "sentinel-2-l2a",
        "name": "Sentinel-2 True Color (RGB)",
        "category": "optical_reference",
        "visualization_type": "raster",
        "required_bands": ["B04", "B03", "B02"],
        "units": "Reflectance",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {
            "type": "rgb",
            "title": "Natural Color Surface Reflectance",
            "channels": {"Red": "Band 4 (665 nm)", "Green": "Band 3 (560 nm)", "Blue": "Band 2 (490 nm)"},
        },
        "description": "True-color natural optical surface reflectance image matching human visual perception at 10m spatial resolution.",
        "limitations": "Subject to cloud obstruction, cloud shadows, and haze attenuation.",
        "role": "reference",
    },
    {
        "layer_id": "sentinel2_ndvi",
        "dataset_id": "sentinel-2-l2a",
        "name": "Normalized Difference Vegetation Index (NDVI)",
        "category": "vegetation",
        "visualization_type": "raster",
        "required_bands": ["B08", "B04"],
        "units": "NDVI",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Vegetation Vigor & Density",
            "min": -1.0,
            "max": 1.0,
            "color_scale": "RdYlGn",
            "stops": [
                {"value": -0.2, "color": "#0284c7", "label": "Water / Bare Surface"},
                {"value": 0.1, "color": "#facc15", "label": "Sparse Vegetation"},
                {"value": 0.4, "color": "#84cc16", "label": "Moderate Canopy"},
                {"value": 0.8, "color": "#15803d", "label": "Dense Healthy Canopy"},
            ],
        },
        "description": "Standardized biophysical vegetation index computed from Sentinel-2 NIR (B08) and Red (B04) bands quantifying photosynthetic biomass density.",
        "limitations": "Saturates in high-density tropical rainforest canopies; sensitive to soil background in arid regions.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel2_false_color_nir",
        "dataset_id": "sentinel-2-l2a",
        "name": "Color Infrared (CIR / False Color)",
        "category": "vegetation",
        "visualization_type": "raster",
        "required_bands": ["B08", "B04", "B03"],
        "units": "Reflectance",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {
            "type": "rgb",
            "title": "False Color Infrared (B08, B04, B03)",
            "channels": {"Red": "NIR Band 8", "Green": "Red Band 4", "Blue": "Green Band 3"},
        },
        "description": "Traditional color infrared composite rendering healthy green vegetation in vivid shades of red for rapid health differentiation.",
        "limitations": "Non-intuitive for non-specialists due to red vegetation coloration.",
        "role": "reference",
    },
    {
        "layer_id": "sentinel2_ndwi",
        "dataset_id": "sentinel-2-l2a",
        "name": "Normalized Difference Water Index (NDWI)",
        "category": "water",
        "visualization_type": "raster",
        "required_bands": ["B03", "B08"],
        "units": "NDWI",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Surface Water Delineation",
            "min": -1.0,
            "max": 1.0,
            "color_scale": "Blues",
            "stops": [
                {"value": -0.5, "color": "#d4d4d8", "label": "Non-water"},
                {"value": 0.0, "color": "#38bdf8", "label": "Moist Soil / Wetland"},
                {"value": 0.5, "color": "#1d4ed8", "label": "Open Waterbody"},
            ],
        },
        "description": "Calculates normalized green-NIR reflectance ratio (B03-B08)/(B03+B08) to enhance open water features and suppress terrestrial vegetation.",
        "limitations": "Urban shadow confusion in high-rise districts can produce false positive water boundaries.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel2_ndbi",
        "dataset_id": "sentinel-2-l2a",
        "name": "Normalized Difference Built-up Index (NDBI)",
        "category": "urban",
        "visualization_type": "raster",
        "required_bands": ["B11", "B08"],
        "units": "NDBI",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Impervious Surface & Built-Up Density",
            "min": -1.0,
            "max": 1.0,
            "color_scale": "Oranges",
            "stops": [
                {"value": -0.4, "color": "#15803d", "label": "Vegetation / Water"},
                {"value": 0.0, "color": "#fed7aa", "label": "Suburban / Soil"},
                {"value": 0.4, "color": "#c2410c", "label": "Dense Impervious Urban"},
            ],
        },
        "description": "Emphasizes man-made concrete and asphalt built-up structures via SWIR (B11) and NIR (B08) band ratio.",
        "limitations": "Bare dry soils and rocky arid terrain exhibit similar SWIR reflectance to urban surfaces.",
        "role": "comparison",
    },
    {
        "layer_id": "sentinel2_swir_urban",
        "dataset_id": "sentinel-2-l2a",
        "name": "Shortwave Infrared Urban Composite (B12, B11, B04)",
        "category": "urban",
        "visualization_type": "raster",
        "required_bands": ["B12", "B11", "B04"],
        "units": "Reflectance",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {
            "type": "rgb",
            "title": "SWIR Urban Penetration Composite",
            "channels": {"Red": "SWIR-2 B12", "Green": "SWIR-1 B11", "Blue": "Red B04"},
        },
        "description": "Atmospheric-penetrating composite mapping urban structures, burned zones, and moisture gradations.",
        "limitations": "20m native resolution in SWIR bands compared to 10m visible.",
        "role": "reference",
    },
    {
        "layer_id": "sentinel2_bitemporal_diff",
        "dataset_id": "sentinel-2-l2a",
        "name": "Bi-Temporal Surface Difference (Change Extent)",
        "category": "change_detection",
        "visualization_type": "raster",
        "required_bands": ["B04", "B08"],
        "units": "Delta Reflectance / Index",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Surface Change Magnitude",
            "min": -1.0,
            "max": 1.0,
            "color_scale": "RdBu",
        },
        "description": "Multi-temporal pixel-wise differential raster highlighting surface alterations between acquisition epochs.",
        "limitations": "Seasonal phenology and illumination differences can induce false change signals.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel2_red_edge",
        "dataset_id": "sentinel-2-l2a",
        "name": "Chlorophyll Red Edge Position",
        "category": "vegetation",
        "visualization_type": "raster",
        "required_bands": ["B05", "B06", "B07"],
        "units": "index",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Canopy Nitrogen & Chlorophyll",
            "color_scale": "Viridis",
        },
        "description": "Narrow Sentinel-2 red-edge spectral bands specifically sensitive to early-stage plant stress before canopy necrosis occurs.",
        "limitations": "Sensitive to micro-atmospheric aerosols.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel2_custom_composite",
        "dataset_id": "sentinel-2-l2a",
        "name": "Sentinel-2 Custom Band Composite",
        "category": "custom",
        "visualization_type": "composite",
        "required_bands": ["B04", "B03", "B02"],
        "units": "Reflectance",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {"type": "rgb", "title": "Custom Normalized Band Composite"},
        "description": "Dynamic user or AI specified RGB band assignment for specialized multi-spectral feature isolation.",
        "limitations": "Requires valid optical band selection from Sentinel-2 MSI catalogue.",
        "role": "reference",
    },

    # --------------------------------------------------------------------------
    # 2. SENTINEL-1 C-SAR GRD LAYERS
    # --------------------------------------------------------------------------
    {
        "layer_id": "sentinel1_sar_amplitude",
        "dataset_id": "sentinel-1-grd",
        "name": "Sentinel-1 RTC SAR Amplitude (VV)",
        "category": "sar",
        "visualization_type": "raster",
        "required_bands": ["VV"],
        "units": "dB",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {
            "type": "continuous",
            "title": "Calibrated Radar Backscatter (dB)",
            "min": -25.0,
            "max": 0.0,
            "color_scale": "Greys",
            "stops": [
                {"value": -25.0, "color": "#000000", "label": "Specular Water Reflection (Dark)"},
                {"value": -12.0, "color": "#71717a", "label": "Agricultural / Soil Volume"},
                {"value": 0.0, "color": "#ffffff", "label": "Corner Double-Bounce Urban"},
            ],
        },
        "description": "Radiometrically terrain corrected C-band SAR backscatter power mapping surface roughness, moisture, and structural double-bounce.",
        "limitations": "Inherent radar speckle noise; foreshortening on steep mountain terrain.",
        "role": "reference",
    },
    {
        "layer_id": "sentinel1_flood_inundation",
        "dataset_id": "sentinel-1-grd",
        "name": "SAR Flood Inundation Extent",
        "category": "flood",
        "visualization_type": "polygon",
        "required_bands": ["VV", "VH"],
        "units": "km²",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "categorical",
            "title": "Confirmed Water Inundation",
            "items": [
                {"label": "Submerged Flood Zone", "color": "#2563eb", "value": "Severe Backscatter Drop"},
                {"label": "Historical Normal Water", "color": "#0284c7", "value": "Baseline River/Lake"},
            ],
        },
        "description": "Thresholded bitemporal change detection over calibrated C-band SAR backscatter isolating sudden specular reflection surfaces caused by open flooding.",
        "limitations": "Smooth asphalt runways or calm sand plains can mimic low radar returns.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel1_polarimetric_ratio",
        "dataset_id": "sentinel-1-grd",
        "name": "SAR Polarimetric Ratio (VH/VV)",
        "category": "sar",
        "visualization_type": "raster",
        "required_bands": ["VV", "VH"],
        "units": "ratio",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {"type": "continuous", "title": "Volume vs Surface Scattering", "color_scale": "Spectral"},
        "description": "Cross-to-co-polarization backscatter ratio highlighting volume scattering in crop canopies and mangrove forests.",
        "limitations": "Low signal-to-noise ratio in calm waterbodies.",
        "role": "comparison",
    },

    # --------------------------------------------------------------------------
    # 3. SENTINEL-5P TROPOMI ATMOSPHERIC LAYERS
    # --------------------------------------------------------------------------
    {
        "layer_id": "sentinel5p_no2_density",
        "dataset_id": "sentinel-5p-tropomi",
        "name": "Tropospheric NO2 Column Number Density",
        "category": "atmospheric",
        "visualization_type": "heatmap",
        "required_bands": ["NO2"],
        "units": "μmol/m²",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "NO2 Concentration (μmol/m²)",
            "min": 0.0,
            "max": 250.0,
            "color_scale": "Turbo",
            "stops": [
                {"value": 10.0, "color": "#38bdf8", "label": "Clean Rural Baseline"},
                {"value": 80.0, "color": "#facc15", "label": "Moderate Urban Activity"},
                {"value": 180.0, "color": "#ef4444", "label": "High Thermal/Traffic Pollution"},
            ],
        },
        "description": "Daily total tropospheric vertical column density of nitrogen dioxide (NO2), marking vehicular traffic, thermal power stations, and industrial hotspots.",
        "limitations": "Regional scale (3.5x5.5km pixel); high cloud cover masks surface visibility.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "sentinel5p_co_density",
        "dataset_id": "sentinel-5p-tropomi",
        "name": "Carbon Monoxide (CO) Column Concentration",
        "category": "atmospheric",
        "visualization_type": "heatmap",
        "required_bands": ["CO"],
        "units": "mmol/m²",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {"type": "continuous", "title": "CO Column Density", "color_scale": "Inferno"},
        "description": "Atmospheric carbon monoxide concentration tracking biomass burning, crop residue fires, and large combustion emissions.",
        "limitations": "Longer atmospheric lifetime causes regional atmospheric diffusion.",
        "role": "comparison",
    },
    {
        "layer_id": "sentinel5p_aerosol_index",
        "dataset_id": "sentinel-5p-tropomi",
        "name": "Ultraviolet Aerosol Index (UVAI)",
        "category": "atmospheric",
        "visualization_type": "raster",
        "required_bands": ["UVAI"],
        "units": "index",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {"type": "continuous", "title": "Absorbing Aerosols (Smoke / Dust)", "color_scale": "YlOrRd"},
        "description": "Detects presence of elevated UV-absorbing aerosols including wildfire smoke plumes, volcanic ash, and desert dust storms.",
        "limitations": "Qualitative index rather than absolute particulate matter (PM2.5) concentration.",
        "role": "primary_analysis",
    },

    # --------------------------------------------------------------------------
    # 4. COPERNICUS DEM GLO-30 LAYERS
    # --------------------------------------------------------------------------
    {
        "layer_id": "copernicus_dem_surface",
        "dataset_id": "copernicus-dem-glo30",
        "name": "3D Continuous Elevation Surface Mesh",
        "category": "elevation",
        "visualization_type": "3d_surface",
        "required_bands": ["ELEVATION"],
        "units": "m",
        "temporal": False,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Orthometric Elevation (EGM2008)",
            "unit": "m",
            "color_scale": "Terrain",
            "stops": [
                {"value": 0.0, "color": "#0ea5e9", "label": "Sea Level / Basin"},
                {"value": 500.0, "color": "#22c55e", "label": "Plateau / Foothills"},
                {"value": 1500.0, "color": "#eab308", "label": "Mid-elevation Ridges"},
                {"value": 3500.0, "color": "#f8fafc", "label": "High Mountain Summits"},
            ],
        },
        "description": "Continuous 3D digital surface model terrain heightfield derived from TanDEM-X InSAR radar missions providing accurate elevation geometry.",
        "limitations": "DSM captures forest canopies and structural heights above bare Earth surface.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "copernicus_dem_hillshade",
        "dataset_id": "copernicus-dem-glo30",
        "name": "Topographic Shaded Relief (Hillshade)",
        "category": "elevation",
        "visualization_type": "raster",
        "required_bands": ["ELEVATION"],
        "units": "illumination",
        "temporal": False,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": False,
        "legend": {"type": "continuous", "title": "Topographic Relief Illumination", "color_scale": "Greys"},
        "description": "Hypothetical solar illumination hillshade rendering landscape contours, canyons, and ridge structures.",
        "limitations": "Monochrome visual aid without direct quantitative metric output.",
        "role": "reference",
    },

    # --------------------------------------------------------------------------
    # 5. COPERNICUS LAND COVER (CLMS 100M) LAYERS
    # --------------------------------------------------------------------------
    {
        "layer_id": "copernicus_landcover_discrete",
        "dataset_id": "copernicus-land-cover-100m",
        "name": "Copernicus Discrete Land Cover Classification",
        "category": "land_cover",
        "visualization_type": "raster",
        "required_bands": ["DISCRETE_CLASSIFICATION"],
        "units": "class_code",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "categorical",
            "title": "FAO-LCCS Thematic Land Classes",
            "items": [
                {"label": "Closed Forest (Canopy >70%)", "color": "#006400", "value": "111"},
                {"label": "Open Forest (Canopy 15-70%)", "color": "#228b22", "value": "121"},
                {"label": "Shrubland", "color": "#8b7355", "value": "20"},
                {"label": "Herbaceous Grassland", "color": "#ccbb44", "value": "30"},
                {"label": "Cropland / Agriculture", "color": "#ffff64", "value": "40"},
                {"label": "Built-up Impervious Surface", "color": "#ff0000", "value": "50"},
                {"label": "Bare Ground / Sparsely Vegetated", "color": "#b4b4b4", "value": "60"},
                {"label": "Permanent Inland Waterbody", "color": "#0064c8", "value": "80"},
                {"label": "Herbaceous Wetland", "color": "#00a0c8", "value": "90"},
            ],
        },
        "description": "Global discrete land cover classification mapping 23 biophysical thematic surface classes according to UN FAO Land Cover Classification System (LCCS).",
        "limitations": "100m pixel size aggregates fragmented urban patches and narrow riparian corridors.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "copernicus_landcover_forest_fraction",
        "dataset_id": "copernicus-land-cover-100m",
        "name": "Fractional Tree Canopy Cover",
        "category": "vegetation",
        "visualization_type": "raster",
        "required_bands": ["FOREST_FRACTION"],
        "units": "%",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {"type": "continuous", "title": "Tree Cover Density (%)", "min": 0.0, "max": 100.0, "color_scale": "Greens"},
        "description": "Continuous percentage estimate (0-100%) of tree canopy cover density within each 100m pixel.",
        "limitations": "Annual aggregate product; does not capture within-year seasonal phenology.",
        "role": "comparison",
    },

    # --------------------------------------------------------------------------
    # 6. COPERNICUS SURFACE SOIL MOISTURE
    # --------------------------------------------------------------------------
    {
        "layer_id": "copernicus_soil_moisture_index",
        "dataset_id": "copernicus-surface-soil-moisture",
        "name": "Surface Soil Moisture Saturation Degree",
        "category": "soil",
        "visualization_type": "raster",
        "required_bands": ["SURFACE_SOIL_MOISTURE"],
        "units": "%",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Topsoil Water Saturation (%)",
            "min": 0.0,
            "max": 100.0,
            "color_scale": "BrBG",
            "stops": [
                {"value": 10.0, "color": "#a16207", "label": "Severe Agricultural Drought"},
                {"value": 45.0, "color": "#fef08a", "label": "Normal Field Moisture"},
                {"value": 90.0, "color": "#0284c7", "label": "Field Capacity / Saturated"},
            ],
        },
        "description": "Relative degree of water saturation in top 5 cm soil layer derived from Sentinel-1 and ASCAT scatterometer microwave radar.",
        "limitations": "Only samples topmost 5 cm soil layer; high uncertainty over dense tropical forest canopy.",
        "role": "primary_analysis",
    },

    # --------------------------------------------------------------------------
    # 7. COPERNICUS MARINE WATER QUALITY
    # --------------------------------------------------------------------------
    {
        "layer_id": "copernicus_water_turbidity",
        "dataset_id": "copernicus-marine-water-quality",
        "name": "Water Turbidity & Suspended Particulate Matter",
        "category": "water",
        "visualization_type": "raster",
        "required_bands": ["TURBIDITY"],
        "units": "FNU",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {
            "type": "continuous",
            "title": "Turbidity Index (FNU)",
            "min": 0.0,
            "max": 50.0,
            "color_scale": "YlOrBr",
            "stops": [
                {"value": 1.0, "color": "#0284c7", "label": "Clear / Low Sediment"},
                {"value": 15.0, "color": "#facc15", "label": "Moderate Coastal Turbidity"},
                {"value": 45.0, "color": "#78350f", "label": "High Sediment Discharge"},
            ],
        },
        "description": "Satellite-derived water clarity and total suspended sediment concentration measuring river plume runoff and coastal dredging impacts.",
        "limitations": "Ultra-shallow waters with sandy seabed reflection can distort turbidity estimation.",
        "role": "primary_analysis",
    },
    {
        "layer_id": "copernicus_water_chlorophyll",
        "dataset_id": "copernicus-marine-water-quality",
        "name": "Inland / Coastal Chlorophyll-a Biomass",
        "category": "water",
        "visualization_type": "raster",
        "required_bands": ["CHLOROPHYLL_A"],
        "units": "mg/m³",
        "temporal": True,
        "spatial": True,
        "supports_cesium": True,
        "supports_analysis": True,
        "legend": {"type": "continuous", "title": "Chlorophyll-a (mg/m³)", "color_scale": "Viridis"},
        "description": "Quantification of phytoplankton algal biomass in marine and inland water bodies for eutrophication monitoring.",
        "limitations": "Cloud cover and atmospheric sun glint.",
        "role": "comparison",
    },
]

# Primary layer store keyed by layer_id
_LAYER_STORE: Dict[str, LayerDefinition] = {
    item["layer_id"]: LayerDefinition(**item) for item in _STATIC_LAYER_DEFINITIONS
}


def get_layer_definition(layer_id: str) -> Optional[LayerDefinition]:
    """Retrieve typed LayerDefinition by layer_id."""
    return _LAYER_STORE.get(layer_id)


def list_layers_for_dataset(dataset_id: str) -> List[LayerDefinition]:
    """Return all visualization layers exposed by a specific dataset."""
    cid = resolve_canonical_dataset_id(dataset_id)
    return [l for l in _LAYER_STORE.values() if l.dataset_id == cid]


def search_layer_catalog(query: str = "", category: Optional[str] = None) -> List[LayerDefinition]:
    """Search layers across entire catalog by keyword and category."""
    q_low = query.lower().strip()
    results = list(_LAYER_STORE.values())

    if category:
        results = [l for l in results if l.category.lower() == category.lower()]

    if q_low:
        matched = []
        for l in results:
            corpus = f"{l.layer_id} {l.name} {l.category} {l.description} {l.units} {' '.join(l.required_bands)}".lower()
            if any(token in corpus for token in q_low.split()):
                matched.append(l)
        results = matched

    return results


def register_dynamic_layer(layer_def: LayerDefinition) -> None:
    """Dynamically add or override a layer definition (e.g. from user GeoTIFF)."""
    _LAYER_STORE[layer_def.layer_id] = layer_def


# Aliases for flexible import
get_layer = get_layer_definition
get_all_layers = lambda: list(_LAYER_STORE.values())
get_layers_for_dataset = list_layers_for_dataset
search_layers = search_layer_catalog
search_layers_by_category = lambda cat: [l for l in _LAYER_STORE.values() if l.category.lower() == cat.lower()]
register_layer = register_dynamic_layer
