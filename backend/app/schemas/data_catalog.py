"""
SatQuery AI — Earth Observation Data Catalog & Layer Schemas
Canonical Pydantic models for datasets, visualization layers, requirements plans, and custom expressions.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetMetadata(BaseModel):
    dataset_id: str
    name: str
    provider: str
    mission: str
    sensor: str
    platform: str
    modality: str
    spatial_resolution: str
    temporal_resolution: str
    coverage: str
    available_dates: str
    bands: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    supported_analyses: List[str] = Field(default_factory=list)
    available_visualizations: List[str] = Field(default_factory=list)
    access_method: str
    processing_method: str
    provenance: str
    limitations: str
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None
    tasks: Optional[List[str]] = None
    temporal_coverage: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    is_user_asset: bool = False


class LayerDefinition(BaseModel):
    layer_id: str
    dataset_id: str
    name: str
    category: str
    visualization_type: str
    required_bands: List[str] = Field(default_factory=list)
    units: str = ""
    temporal: bool = True
    spatial: bool = True
    supports_cesium: bool = True
    supports_analysis: bool = True
    legend: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    limitations: str = ""
    custom_expression: Optional[Dict[str, Any]] = None
    role: Optional[str] = "primary_analysis"


class DataRequirementPlan(BaseModel):
    question: str
    phenomenon: str
    modality: List[str] = Field(default_factory=lambda: ["optical"])
    temporal: bool = True
    spatial: bool = True
    resolution: str = "medium"
    cloud_constraint: Optional[str] = "max_20_percent"
    preferred_provider: Optional[str] = None
    location: Optional[str] = None
    temporal_scope: Optional[Dict[str, str]] = None
    primary_domain: Optional[str] = None
    user_intent: Optional[str] = None
    analysis_requirements: List[str] = Field(default_factory=list)
    supporting_requirements: List[str] = Field(default_factory=list)
    recommended_data_modalities: List[str] = Field(default_factory=list)


class CustomVisualizationSpec(BaseModel):
    type: str  # "band_composite" | "index"
    bands: Optional[Dict[str, str]] = None
    formula: Optional[str] = None
    output_range: Optional[List[float]] = None
    color_map: Optional[str] = None
