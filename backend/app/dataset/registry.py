"""
SatQuery AI — Authoritative Earth Observation Dataset Registry
Extensible, metadata-rich multi-mission satellite and Copernicus service catalog.
Maintains backward compatibility for DATASET_REGISTRY dictionary access while providing typed models.
"""
from typing import Any, Dict, List, Optional
from app.schemas.data_catalog import DatasetMetadata

# Canonical Dataset Specifications
_CATALOG_ITEMS: List[Dict[str, Any]] = [
    {
        "dataset_id": "sentinel-2-l2a",
        "name": "Sentinel-2 Level-2A (MSI)",
        "provider": "Copernicus / ESA",
        "mission": "Sentinel-2",
        "sensor": "MultiSpectral Instrument (MSI)",
        "platform": "Sentinel-2A / Sentinel-2B",
        "modality": "optical",
        "spatial_resolution": "10m (B02, B03, B04, B08), 20m (Red Edge, SWIR), 60m (Atmospheric)",
        "temporal_resolution": "5 days at equator (2-3 days at mid-latitudes)",
        "coverage": "Global land surface and coastal waters (-56°S to +84°N)",
        "available_dates": "2015-06-23 to Present",
        "temporal_coverage": "2015 - Present",
        "bands": ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"],
        "products": [
            "true_color", "false_color_infrared", "false_color_urban", "ndvi", "ndwi", "ndbi", "ndsi", "red_edge", "custom_band_composite"
        ],
        "supported_analyses": [
            "vegetation", "temporal_change", "built_up", "water_index", "chlorophyll", "drought", "canopy_disturbance"
        ],
        "available_visualizations": [
            "raster", "time_series", "composite", "change_detection"
        ],
        "access_method": "Copernicus Data Space Ecosystem (CDSE) OData / Planetary Computer STAC",
        "processing_method": "Sen2Cor Bottom-Of-Atmosphere (BOA) Surface Reflectance with terrain correction",
        "provenance": "European Space Agency (ESA) Copernicus Programme",
        "limitations": "Cloud, haze, and heavy aerosol attenuation; no observations through dense optical overcast.",
        "description": "High-resolution multispectral imaging mission by Copernicus for land observation, agriculture, disaster mapping, and climate analysis.",
        "aliases": ["sentinel-2", "sentinel 2", "s2", "s2a", "s2b", "optical", "multispectral", "msi", "ndvi", "nir", "swir", "vegetation", "canopy", "red edge", "chlorophyll", "surface reflectance"],
        "capabilities": [
            "NDVI vegetation health & canopy loss",
            "NDWI water boundary and inundation detection",
            "Urban expansion and impervious built-up tracking",
            "High-resolution multispectral surface reflectance"
        ],
        "tasks": ["single_image", "temporal_change", "vegetation", "built_up", "water_index"],
    },
    {
        "dataset_id": "sentinel-1-grd",
        "name": "Sentinel-1 C-SAR Ground Range Detected (GRD)",
        "provider": "Copernicus / ESA",
        "mission": "Sentinel-1",
        "sensor": "C-band Synthetic Aperture Radar (C-SAR, 5.405 GHz)",
        "platform": "Sentinel-1A / Sentinel-1C",
        "modality": "sar",
        "spatial_resolution": "10m (Interferometric Wide Swath - IW Mode)",
        "temporal_resolution": "6-12 days repeat cycle",
        "coverage": "Global systematic land, ocean, and Arctic monitoring",
        "available_dates": "2014-10-03 to Present",
        "temporal_coverage": "2014 - Present",
        "bands": ["VV", "VH", "HH", "HV"],
        "products": [
            "sar_amplitude_vv", "sar_amplitude_vh", "sar_false_color_ratio", "flood_inundation_extent", "water_mask"
        ],
        "supported_analyses": [
            "flood", "inundation", "soil_moisture", "structural_roughness", "maritime_vessel_detection", "monsoon_monitoring"
        ],
        "available_visualizations": [
            "raster", "polygon", "composite"
        ],
        "access_method": "CDSE STAC / OData API / Planetary Computer STAC",
        "processing_method": "Radiometrically Terrain Corrected (RTC) backscatter using Copernicus DEM GLO-30",
        "provenance": "European Space Agency (ESA) Copernicus Sentinel Programme",
        "limitations": "Geometric radar distortion in extreme mountainous topography (layover and shadow).",
        "description": "C-band synthetic aperture radar imaging mission providing continuous all-weather, day-and-night observation regardless of cloud cover.",
        "aliases": ["sentinel-1", "sentinel 1", "s1", "s1a", "s1c", "sar", "c-sar", "radar", "microwave", "vv", "vh", "hh", "hv", "flood", "inundation", "backscatter", "rtc"],
        "capabilities": [
            "All-weather / cloud-penetrating imagery",
            "Day-and-night surface structural analysis",
            "Flood inundation mapping",
            "Urban structure and surface roughness detection"
        ],
        "tasks": ["single_image", "temporal_change", "built_up", "flood", "sar"],
    },
    {
        "dataset_id": "sentinel-5p-tropomi",
        "name": "Sentinel-5P TROPOMI Atmospheric Chemistry",
        "provider": "Copernicus / ESA / KNMI",
        "mission": "Sentinel-5 Precursor",
        "sensor": "Tropospheric Monitoring Instrument (TROPOMI)",
        "platform": "Sentinel-5P",
        "modality": "atmospheric",
        "spatial_resolution": "3.5km x 5.5km (Near-nadir GSD)",
        "temporal_resolution": "Daily global revisit (~13:30 local solar time)",
        "coverage": "Global daily continuous atmospheric coverage",
        "available_dates": "2018-04-30 to Present",
        "temporal_coverage": "2018 - Present",
        "bands": ["UV", "UVIS", "NIR", "SWIR"],
        "products": [
            "no2_tropospheric_column", "co_total_column", "so2_total_column", "ch4_methane_mixing_ratio", "uv_aerosol_index", "o3_ozone_profile"
        ],
        "supported_analyses": [
            "air_quality", "emissions_tracking", "industrial_pollution", "wildfire_smoke", "methane_plumes"
        ],
        "available_visualizations": [
            "heatmap", "raster", "time_series"
        ],
        "access_method": "CDSE Sentinel-5P Open Access Hub / Planetary Computer",
        "processing_method": "Differential Optical Absorption Spectroscopy (DOAS) with air-mass factor corrections",
        "provenance": "Copernicus Atmosphere Monitoring Service (CAMS) / KNMI / ESA",
        "limitations": "Coarse spatial resolution unsuitable for local street-canyon mapping; cloud-top interference.",
        "description": "High-sensitivity atmospheric composition mission mapping global air quality, greenhouse gases, and trace pollutants daily.",
        "aliases": ["sentinel-5p", "sentinel 5p", "s5p", "tropomi", "atmospheric", "air quality", "pollution", "no2", "nitrogen dioxide", "co", "carbon monoxide", "so2", "sulfur dioxide", "ch4", "methane", "aerosol", "ozone", "o3", "emissions"],
        "capabilities": [
            "Tropospheric NO2 pollution column concentration mapping",
            "Industrial and volcanic SO2 anomaly detection",
            "Daily wildfire smoke and aerosol plume tracking",
            "Urban air quality trend evaluation"
        ],
        "tasks": ["air_quality", "pollution", "atmospheric", "emissions", "heatmap"],
    },
    {
        "dataset_id": "copernicus-dem-glo30",
        "name": "Copernicus Global DEM (GLO-30)",
        "provider": "Copernicus / Airbus",
        "mission": "Copernicus Contributing Missions",
        "sensor": "TanDEM-X InSAR X-band SAR Interferometry",
        "platform": "TerraSAR-X / TanDEM-X",
        "modality": "dem",
        "spatial_resolution": "30m (GLO-30) / 90m (GLO-90)",
        "temporal_resolution": "Static authoritative topographic baseline (2020 edition)",
        "coverage": "Global terrestrial landmass (including high-latitude polar regions)",
        "available_dates": "2020-Present (Static Surface)",
        "temporal_coverage": "Static 2020 Baseline",
        "bands": ["ELEVATION"],
        "products": [
            "continuous_elevation_mesh", "hillshade_relief", "slope_aspect_gradient", "elevation_contours"
        ],
        "supported_analyses": [
            "elevation", "topography", "3d_surface", "hydrological_modeling", "slope_instability", "viewshed"
        ],
        "available_visualizations": [
            "3d_surface", "elevation_profile", "raster"
        ],
        "access_method": "Copernicus Data Space Ecosystem / AWS S3 Open Data / Planetary Computer",
        "processing_method": "Interferometric SAR DEM editing with waterbody flattening and void filling",
        "provenance": "European Space Agency / German Aerospace Center (DLR) / Airbus",
        "limitations": "Digital Surface Model (DSM) includes tree canopy heights and building tops rather than bare Earth (DTM).",
        "description": "State-of-the-art global Digital Surface Model providing accurate world-wide elevation data for 3D geospatial modeling.",
        "aliases": ["copernicus-dem", "copernicus dem", "cop-dem", "dem", "glo-30", "glo30", "glo-90", "elevation", "terrain", "topography", "altitude", "height", "dsm", "surface model", "tandem-x", "terrasar-x", "slope", "aspect", "3d"],
        "capabilities": [
            "3D continuous terrain surface mesh extrusion",
            "Topographic cross-sectional elevation profiles",
            "Slope and aspect terrain analysis",
            "Flood inundation basin water-level simulation"
        ],
        "tasks": ["elevation", "slope_analysis", "flood", "3d_surface"],
    },
    {
        "dataset_id": "copernicus-land-cover-100m",
        "name": "Copernicus Global Land Cover (CLMS)",
        "provider": "Copernicus Land Monitoring Service",
        "mission": "Copernicus Services",
        "sensor": "PROBA-V / Sentinel-2 Ensemble",
        "platform": "PROBA-V / Sentinel-2",
        "modality": "land_cover",
        "spatial_resolution": "100m (Global) / 10m (CORINE / European Subsets)",
        "temporal_resolution": "Annual epochs (2015 - 2024)",
        "coverage": "Global terrestrial landmass",
        "available_dates": "2015-01-01 to 2024-12-31",
        "temporal_coverage": "2015 - 2024",
        "bands": ["DISCRETE_CLASSIFICATION", "FOREST_FRACTION", "BUILTUP_FRACTION", "WATER_FRACTION", "CROPLAND_FRACTION"],
        "products": [
            "discrete_land_cover_map", "fractional_tree_cover", "fractional_builtup", "fractional_water"
        ],
        "supported_analyses": [
            "land_cover", "urban_expansion", "deforestation", "cropland_conversion", "habitat_fragmentation"
        ],
        "available_visualizations": [
            "raster", "polygon", "time_series"
        ],
        "access_method": "Copernicus Land Monitoring Service / Planetary Computer",
        "processing_method": "Machine learning ensemble supervised classification with ground validation points",
        "provenance": "Copernicus Land Monitoring Service (CLMS) / VITO",
        "limitations": "100m resolution averages micro-urban patches and small agricultural fields.",
        "description": "Annual global land cover mapping delivering 23 discrete thematic classification categories and fractional layers.",
        "aliases": ["clms", "copernicus land cover", "land cover", "lulc", "land use", "clms-100m", "proba-v", "forest", "urban fraction", "cropland", "deforestation", "thematic classification"],
        "capabilities": [
            "Thematic land-cover classification with standardized FAO-LCCS legend",
            "Longitudinal urban sprawl and land-use transition quantification",
            "Forest canopy density fractional monitoring",
            "Global surface water permanence delineation"
        ],
        "tasks": ["land_cover", "urban", "vegetation", "temporal_change"],
    },
    {
        "dataset_id": "copernicus-surface-soil-moisture",
        "name": "Copernicus Surface Soil Moisture (SSM)",
        "provider": "Copernicus Land Monitoring Service",
        "mission": "Copernicus Services / Metop ASCAT / Sentinel-1",
        "sensor": "Active Microwave Scatterometer / C-SAR",
        "platform": "Metop / Sentinel-1",
        "modality": "soil",
        "spatial_resolution": "1km (Sentinel-1 SSM High-Res) / 12.5km (ASCAT Global)",
        "temporal_resolution": "Daily to 3-day revisit",
        "coverage": "Global terrestrial agricultural and bare soils",
        "available_dates": "2015-01-01 to Present",
        "temporal_coverage": "2015 - Present",
        "bands": ["SURFACE_SOIL_MOISTURE", "SSM_NOISE", "FROZEN_PROBABILITY"],
        "products": [
            "volumetric_soil_moisture", "drought_severity_anomaly", "saturation_degree"
        ],
        "supported_analyses": [
            "soil_moisture", "drought", "irrigation_efficiency", "agricultural_risk", "landslide_predisposition"
        ],
        "available_visualizations": [
            "raster", "time_series", "heatmap"
        ],
        "access_method": "Copernicus Land Monitoring Service / EUMETSAT",
        "processing_method": "Change detection backscatter modeling over top 5cm soil layer",
        "provenance": "TU Wien / Copernicus Global Land Service",
        "limitations": "Only samples topmost 0-5cm of soil; high uncertainty in dense forest canopy or snow/ice.",
        "description": "Satellite-derived relative degree of saturation for topsoil, key for agricultural monitoring and hydrological modeling.",
        "aliases": ["ssm", "soil moisture", "copernicus soil moisture", "surface moisture", "ascat", "topsoil", "hydrology", "drought index", "soil saturation", "metop"],
        "capabilities": [
            "Volumetric topsoil water saturation quantification (%)",
            "Agricultural drought anomaly identification",
            "Pre-monsoon soil moisture depletion monitoring"
        ],
        "tasks": ["soil_moisture", "agriculture", "drought"],
    },
    {
        "dataset_id": "copernicus-marine-water-quality",
        "name": "Copernicus Marine & Inland Water Quality",
        "provider": "Copernicus Marine Service (CMEMS)",
        "mission": "Sentinel-3 / Sentinel-2 Multi-mission",
        "sensor": "Ocean and Land Colour Instrument (OLCI) / MSI",
        "platform": "Sentinel-3A/B & Sentinel-2",
        "modality": "water",
        "spatial_resolution": "300m (OLCI Coastal) / 10m-20m (MSI High-Res Inland Lakes)",
        "temporal_resolution": "1 to 2 days repeat",
        "coverage": "Global oceans, coastal zones, and large inland waterbodies",
        "available_dates": "2016-04-25 to Present",
        "temporal_coverage": "2016 - Present",
        "bands": ["CHLOROPHYLL_A", "TURBIDITY", "TOTAL_SUSPENDED_MATTER", "WATER_TEMPERATURE"],
        "products": [
            "chlorophyll_a_concentration", "turbidity_neph", "total_suspended_matter", "lake_surface_temperature"
        ],
        "supported_analyses": [
            "water_quality", "eutrophication", "algal_blooms", "sediment_plumes", "coastal_turbidity"
        ],
        "available_visualizations": [
            "raster", "time_series", "heatmap"
        ],
        "access_method": "Copernicus Marine Data Store / CDSE",
        "processing_method": "Neural network atmospheric correction and bio-optical ocean color inversion",
        "provenance": "Copernicus Marine Environment Monitoring Service (CMEMS)",
        "limitations": "Susceptible to sun glint, bottom reflection in ultra-shallow waters, and cloud gaps.",
        "description": "High-frequency coastal and inland water bio-optical telemetry measuring turbidity, chlorophyll, and sediment load.",
        "aliases": ["cmems", "marine water quality", "water quality", "turbidity", "chlorophyll-a", "algae", "algal bloom", "lake quality", "suspended matter", "tsm", "eutrophication", "ocean color"],
        "capabilities": [
            "Chlorophyll-a phytoplankton bloom quantification",
            "Turbidity (FNU/NTU) and total suspended sediment plume tracking",
            "Inland lake eutrophication and water safety surveillance"
        ],
        "tasks": ["water_quality", "coastal", "ocean_marine"],
    },
    {
        "dataset_id": "sentinel-3-olci",
        "name": "Sentinel-3 Ocean and Land Colour Instrument (OLCI)",
        "provider": "Copernicus / ESA",
        "mission": "Sentinel-3",
        "sensor": "Ocean and Land Colour Instrument (OLCI, 21 bands)",
        "platform": "Sentinel-3A / Sentinel-3B",
        "modality": "optical",
        "spatial_resolution": "300m Full Resolution (FR)",
        "temporal_resolution": "Less than 2 days global revisit",
        "coverage": "Global land and oceans",
        "available_dates": "2016-02-16 to Present",
        "temporal_coverage": "2016 - Present",
        "bands": ["Oa01", "Oa02", "Oa03", "Oa04", "Oa05", "Oa06", "Oa07", "Oa08", "Oa09", "Oa10", "Oa11", "Oa12", "Oa17", "Oa21"],
        "products": ["true_color_olci", "terrestrial_chlorophyll_index", "integrated_water_vapor", "red_edge_position"],
        "supported_analyses": ["chlorophyll", "vegetation_health", "large_scale_phenology", "ocean_color"],
        "available_visualizations": ["raster", "time_series"],
        "access_method": "CDSE STAC / OData",
        "processing_method": "Rayleigh and aerosol atmospheric correction with smile effect calibration",
        "provenance": "ESA / EUMETSAT Copernicus",
        "limitations": "300m spatial resolution limits urban-scale analysis.",
        "description": "Global daily optical spectrometer tracking terrestrial greenness, chlorophyll dynamics, and marine color.",
        "aliases": ["sentinel-3", "sentinel 3", "s3", "olci", "ocean color", "chlorophyll", "phenology", "terrestrial chlorophyll", "s3a", "s3b"],
        "capabilities": ["Large-scale phenological canopy tracking", "Terrestrial chlorophyll index"],
        "tasks": ["vegetation", "chlorophyll", "ocean_marine"],
    },
    {
        "dataset_id": "landsat-8-9-c2",
        "name": "Landsat 8/9 Collection 2 (OLI-2/TIRS-2)",
        "provider": "USGS / NASA",
        "mission": "Landsat",
        "sensor": "Operational Land Imager (OLI) / Thermal Infrared Sensor (TIRS)",
        "platform": "Landsat 8 / Landsat 9",
        "modality": "multispectral",
        "spatial_resolution": "15m panchromatic, 30m multispectral, 100m thermal",
        "temporal_resolution": "8 days with combined constellation",
        "coverage": "Global terrestrial land surface",
        "available_dates": "2013-02-11 to Present (Archive from 1972)",
        "temporal_coverage": "1972 - Present",
        "bands": ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B10", "B11"],
        "products": ["true_color", "false_color", "ndvi", "land_surface_temperature", "ndbi"],
        "supported_analyses": ["thermal", "vegetation", "urban", "longitudinal_change"],
        "available_visualizations": ["raster", "time_series"],
        "access_method": "USGS EarthExplorer / Planetary Computer / AWS S3",
        "processing_method": "LaSRC / single-channel thermal surface temperature algorithm",
        "provenance": "USGS / NASA",
        "limitations": "Lower revisit frequency than Sentinel-2.",
        "description": "The longest continuous space-based record of Earth's land surface, critical for climate, agriculture, and 50-year retrospective analysis.",
        "aliases": ["landsat", "landsat 8", "landsat 9", "landsat-8", "landsat-9", "l8", "l9", "oli", "tirs", "thermal", "lst", "surface temperature", "usgs", "archive", "longitudinal"],
        "capabilities": ["Land surface temperature (LST)", "Multi-decadal longitudinal change detection"],
        "tasks": ["thermal", "vegetation", "urban", "temporal_change"],
    },
    {
        "dataset_id": "cartosat-3-vhr",
        "name": "Cartosat-3 Very High Resolution Optical",
        "provider": "ISRO",
        "mission": "Cartosat",
        "sensor": "Panchromatic & Multispectral Camera",
        "platform": "Cartosat-3",
        "modality": "optical",
        "spatial_resolution": "0.28m (Panchromatic), 1.12m (4-band Multispectral)",
        "temporal_resolution": "Sub-weekly on targeted steering",
        "coverage": "Indian subcontinent and global targets on demand",
        "available_dates": "2019-11-27 to Present",
        "temporal_coverage": "2019 - Present",
        "bands": ["PAN", "BLUE", "GREEN", "RED", "NIR"],
        "products": ["pan_sharpened_true_color", "cadastral_delineation", "building_footprints"],
        "supported_analyses": ["high_res_vqa", "cadastral", "urban_planning", "infrastructure"],
        "available_visualizations": ["raster", "polygon"],
        "access_method": "ISRO Bhoonidhi / National Remote Sensing Centre (NRSC)",
        "processing_method": "Ortho-rectified high precision photogrammetric processing",
        "provenance": "ISRO / Government of India",
        "limitations": "Proprietary commercial/governmental tasking access restrictions.",
        "description": "Indian Space Research Organisation high-resolution Earth observation satellite series dedicated to cartographic and urban intelligence.",
        "aliases": ["cartosat", "cartosat-3", "cartosat 3", "isro optical", "vhr", "sub-meter", "very high resolution", "bhoonidhi", "cadastral", "nrsc"],
        "capabilities": ["Sub-meter building footprint extraction", "Cadastral boundary mapping"],
        "tasks": ["high_res_vqa", "cadastral", "urban_planning", "infrastructure"],
    },
    {
        "dataset_id": "risat-1a-sar",
        "name": "RISAT-1A (EOS-04) Polarimetric C-band SAR",
        "provider": "ISRO",
        "mission": "RISAT",
        "sensor": "C-band Synthetic Aperture Radar (5.35 GHz)",
        "platform": "EOS-04",
        "modality": "sar",
        "spatial_resolution": "1m (High Res Spotlight) to 50m (ScanSAR)",
        "temporal_resolution": "25-day repeat with steering",
        "coverage": "Indian landmass and regional maritime corridors",
        "available_dates": "2022-02-14 to Present",
        "temporal_coverage": "2022 - Present",
        "bands": ["HH", "HV", "VV", "VH", "RH", "RV"],
        "products": ["sar_intensity", "polarimetric_decomposition", "flood_inundation"],
        "supported_analyses": ["sar", "flood", "monsoon_agriculture", "soil_moisture"],
        "available_visualizations": ["raster", "polygon"],
        "access_method": "ISRO Bhoonidhi",
        "processing_method": "Range-Doppler terrain correction with SAR polarimetric decomposition",
        "provenance": "ISRO / NRSC",
        "limitations": "Targeted coverage cycles rather than open continuous global broadcast.",
        "description": "ISRO radar imaging satellite carrying an active C-band Synthetic Aperture Radar providing repeat observation in all weather conditions.",
        "aliases": ["risat", "risat-1a", "risat 1a", "eos-04", "eos04", "isro sar", "c-band sar", "isro radar", "bhoonidhi", "radar"],
        "capabilities": ["Monsoon-season agricultural crop classification", "All-weather flood mapping"],
        "tasks": ["sar", "flood", "monsoon_agriculture", "soil_moisture"],
    },
    {
        "dataset_id": "planetscope",
        "name": "PlanetScope SuperDove",
        "provider": "Planet Labs",
        "mission": "PlanetScope",
        "sensor": "PSB.SD 8-band VNIR",
        "platform": "Dove Constellation",
        "modality": "optical",
        "spatial_resolution": "3.0m - 3.7m",
        "temporal_resolution": "Daily global revisit",
        "coverage": "Global terrestrial landmass",
        "available_dates": "2016-01-01 to Present",
        "temporal_coverage": "2016 - Present",
        "bands": ["Coastal Blue", "Blue", "Green I", "Green", "Yellow", "Red", "Red Edge", "NIR"],
        "products": ["daily_surface_reflectance", "ndvi_3m", "true_color_3m"],
        "supported_analyses": ["high_res_vqa", "daily_monitoring", "micro_agriculture"],
        "available_visualizations": ["raster", "time_series"],
        "access_method": "Planet API",
        "processing_method": "Harmonized Planet surface reflectance",
        "provenance": "Planet Labs Inc.",
        "limitations": "Commercial API authorization key required.",
        "description": "Constellation of over 200 Dove satellites capturing the entire Earth's landmass daily at 3-meter spatial resolution.",
        "aliases": ["planet", "planetscope", "superdove", "dove", "planet labs", "daily 3m", "daily optical", "high cadence"],
        "capabilities": ["Daily global cadenced imaging", "Micro-plot agricultural tracking"],
        "tasks": ["single_image", "temporal_change", "high_res_vqa", "infrastructure"],
    },
    {
        "dataset_id": "user-asset-raster",
        "name": "User-Uploaded Raster Asset",
        "provider": "Private User Workspace",
        "mission": "User Ingestion",
        "sensor": "Custom Ingested Sensor",
        "platform": "User Uploaded",
        "modality": "custom",
        "spatial_resolution": "Native file pixel GSD",
        "temporal_resolution": "File acquisition epoch",
        "coverage": "Local AOI extent defined by GeoTIFF bounding box",
        "available_dates": "File timestamp",
        "temporal_coverage": "Acquisition date",
        "bands": ["USER_BANDS"],
        "products": ["true_color", "band_inspection", "ndvi_computed"],
        "supported_analyses": ["data_inspection", "spectral_indices", "spatial_delineation"],
        "available_visualizations": ["raster", "histogram", "polygon"],
        "access_method": "Local File System / Storage Bucket",
        "processing_method": "Rasterio GDAL geospatial extraction with dynamic radiometric normalization",
        "provenance": "User Asset File",
        "limitations": "Limited to bounds and spectral bands physically present in uploaded GeoTIFF file.",
        "description": "Locally uploaded GeoTIFF raster dataset indexed in user workspace.",
        "aliases": ["user asset", "uploaded raster", "geotiff", "custom file", "custom raster", "local asset", "my data"],
        "capabilities": ["Native pixel inspection", "Private spatial layer rendering"],
        "tasks": ["data_inspection", "user_asset"],
        "is_user_asset": True,
    },
]

# Primary dataset map keyed by canonical dataset_id
_DATASET_STORE: Dict[str, DatasetMetadata] = {
    item["dataset_id"]: DatasetMetadata(**item) for item in _CATALOG_ITEMS
}

# Aliases mapping legacy shorthand IDs to canonical dataset entries
_DATASET_ALIASES: Dict[str, str] = {
    "sentinel-2": "sentinel-2-l2a",
    "sentinel-1": "sentinel-1-grd",
    "sentinel-5p": "sentinel-5p-tropomi",
    "sentinel-5p-l2": "sentinel-5p-tropomi",
    "copernicus-dem": "copernicus-dem-glo30",
    "copernicus-dem-30m": "copernicus-dem-glo30",
    "dem": "copernicus-dem-glo30",
    "copernicus-land-cover": "copernicus-land-cover-100m",
    "copernicus-soil-moisture": "copernicus-surface-soil-moisture",
    "copernicus-soil-moisture-1km": "copernicus-surface-soil-moisture",
    "landsat": "landsat-8-9-c2",
    "landsat-8-9-c2l2": "landsat-8-9-c2",
    "cartosat": "cartosat-3-vhr",
    "cartosat-3-pan-mx": "cartosat-3-vhr",
    "risat": "risat-1a-sar",
    "planetscope-psb-sd": "planetscope",
    "user-asset": "user-asset-raster",
}

# The canonical backward-compatible dictionary for existing codebase callers
DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {}
for canonical_id, meta in _DATASET_STORE.items():
    d = meta.model_dump()
    DATASET_REGISTRY[canonical_id] = d

# Populate legacy shorthand keys pointing to their canonical data
for alias, canonical_id in _DATASET_ALIASES.items():
    if canonical_id in _DATASET_STORE and alias not in DATASET_REGISTRY:
        DATASET_REGISTRY[alias] = _DATASET_STORE[canonical_id].model_dump()


def resolve_canonical_dataset_id(dataset_id: str) -> str:
    """Normalize aliases (e.g. 'sentinel-2') to canonical IDs ('sentinel-2-l2a')."""
    d_low = dataset_id.lower().strip()
    return _DATASET_ALIASES.get(d_low, d_low)


def get_dataset(dataset_id: str) -> Optional[DatasetMetadata]:
    """Retrieve typed DatasetMetadata by ID or alias."""
    cid = resolve_canonical_dataset_id(dataset_id)
    return _DATASET_STORE.get(cid)


def list_datasets(modality: Optional[str] = None, provider: Optional[str] = None) -> List[DatasetMetadata]:
    """List all registered datasets with optional filtering."""
    results = list(_DATASET_STORE.values())
    if modality:
        results = [d for d in results if d.modality.lower() == modality.lower()]
    if provider:
        results = [d for d in results if provider.lower() in d.provider.lower()]
    return results


get_all_datasets = list_datasets


# Search term synonyms and expansions for satellite queries
_SEARCH_SYNONYMS: Dict[str, List[str]] = {
    "s2": ["sentinel-2", "msi", "optical"],
    "s1": ["sentinel-1", "sar", "c-band", "radar"],
    "s5p": ["sentinel-5p", "tropomi", "atmospheric", "no2"],
    "radar": ["sar", "c-sar", "sentinel-1", "risat"],
    "optical": ["sentinel-2", "landsat", "planetscope", "modis"],
    "multispectral": ["sentinel-2", "landsat", "modis"],
    "nir": ["near-infrared", "b08", "sentinel-2", "landsat"],
    "swir": ["short-wave infrared", "b11", "b12", "sentinel-2", "landsat"],
    "dem": ["copernicus-dem", "elevation", "topography", "glo-30", "cartosat"],
    "terrain": ["copernicus-dem", "elevation", "glo-30", "topography"],
    "elevation": ["copernicus-dem", "glo-30", "cartosat"],
    "vegetation": ["sentinel-2", "ndvi", "landsat", "modis", "canopy"],
    "ndvi": ["sentinel-2", "vegetation", "landsat", "modis"],
    "flood": ["sentinel-1", "sar", "water", "ndwi", "inundation"],
    "water": ["ndwi", "sentinel-2", "sentinel-1", "marine", "ocean"],
    "change": ["sentinel-2", "sentinel-1", "prithvi", "temporal"],
    "air": ["sentinel-5p", "tropomi", "atmospheric", "air quality"],
    "pollution": ["sentinel-5p", "tropomi", "no2", "so2"],
    "no2": ["sentinel-5p", "tropomi", "tropospheric"],
    "copernicus": ["sentinel-1", "sentinel-2", "sentinel-5p", "dem", "clms", "cmems"],
}


def search_datasets(query: str) -> List[DatasetMetadata]:
    """
    Search datasets across names, missions, sensors, bands, products, supported analyses, and capabilities.
    Includes EO domain synonym and alias expansion.
    """
    q_low = query.lower().strip()
    if not q_low:
        return list(_DATASET_STORE.values())

    # Collect search tokens and expanded synonyms
    tokens = set(q_low.split())
    for token in list(tokens):
        if token in _SEARCH_SYNONYMS:
            tokens.update(_SEARCH_SYNONYMS[token])

    matches = []
    for d in _DATASET_STORE.values():
        text_corpus = (
            f"{d.dataset_id} {d.name} {d.provider} {d.mission} {d.sensor} {d.platform} "
            f"{d.modality} {d.description or ''} {' '.join(d.capabilities or [])} "
            f"{' '.join(d.products)} {' '.join(d.supported_analyses)} {' '.join(d.bands)}"
        ).lower()

        # Score matching
        if any(term in text_corpus for term in tokens):
            matches.append(d)

    return matches


def register_dataset(meta: DatasetMetadata) -> None:
    """Dynamically register a new dataset (e.g. from user uploads or external WMS)."""
    _DATASET_STORE[meta.dataset_id] = meta
    DATASET_REGISTRY[meta.dataset_id] = meta.model_dump()