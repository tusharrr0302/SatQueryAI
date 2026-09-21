from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# Canonical primary tasks controlled vocabulary
PrimaryTask = Literal[
    "single_image_vqa",
    "scene_description",
    "object_detection",
    "visual_grounding",
    "temporal_change_detection",
    "land_cover_change",
    "vegetation_analysis",
    "urban_change",
    "flood_analysis",
    "sar_optical_analysis",
    "multispectral_analysis",
    "image_comparison",
    "dataset_information",
    "location_information",
    "general_knowledge",
]


class TemporalScope(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    relative_period: Optional[str] = None  # e.g. "10_years", "5_years"
    resolution: Optional[str] = None  # e.g. "multi_temporal", "monthly", "annual"
    comparison_strategy: Optional[str] = None

    class Config:
        extra = "allow"


class Intent(BaseModel):
    primary_task: str
    domain: Optional[str] = "earth_observation"
    # Canonical response types:
    # "NEW_ANALYSIS", "FOLLOW_UP_ANALYSIS", "RESULT_EXPLANATION",
    # "PROVENANCE_QUESTION", "VISUALIZATION_REQUEST", "CONTEXTUAL_SPATIAL_REQUEST",
    # "GENERAL_KNOWLEDGE", "CLARIFICATION", "NEW_LOCATION_ANALYSIS"
    question_type: Optional[str] = None
    requires_geospatial_analysis: bool = True
    spatial_scope: Optional[str] = None
    temporal_scope: Optional[TemporalScope] = None
    ai_mode: Optional[str] = "auto"  # "auto" | "beginner" | "intermediate" | "advanced"

    # Clarification gate fields
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)

    # Architecture Hardening Pass: Structured Intent & Visualization Gate
    conversational_mode: Optional[str] = None  # "ANSWER" | "EARTH_ANALYSIS" | "FOLLOW_UP" | "CLARIFICATION"
    visualization_required: Optional[bool] = None
    visualization_reason: Optional[str] = None
    visualization_type: Optional[str] = None  # "NONE" | "RASTER" | "VECTOR" | "CHART" | "HYBRID"

    class Config:
        extra = "allow"


class AOI(BaseModel):
    type: str = "Polygon"
    name: Optional[str] = None
    country: Optional[str] = None
    action: Optional[str] = "none"  # "resolve_new", "new", "reuse", "none", "clarify"
    source: Optional[str] = "none"  # "explicit_user", "conversation_context", "uploaded_asset", "none"
    spatial_focus: Optional[str] = None  # e.g. "southern region"
    reason: Optional[str] = None
    bbox: Optional[List[float]] = None
    geometry: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class DataRequirements(BaseModel):
    modalities: List[str] = Field(default_factory=lambda: ["optical"])
    datasets: List[str] = Field(default_factory=list)
    temporal_resolution: Optional[str] = None
    cloud_constraint: Optional[str] = None
    spatial_resolution: Optional[str] = None

    class Config:
        extra = "allow"


class ModelSelection(BaseModel):
    model: str
    reason: str
    explicit_model: Optional[str] = None  # user requested override e.g. "prithvi-eo-2.0"

    class Config:
        extra = "allow"


class ComparisonPeriod(BaseModel):
    label: str
    start: Optional[str] = None
    end: Optional[str] = None

    class Config:
        extra = "allow"


class Analysis(BaseModel):
    operation: str
    comparison_periods: Optional[List[ComparisonPeriod]] = Field(default_factory=list)
    target_classes: Optional[List[str]] = Field(default_factory=list)

    class Config:
        extra = "allow"


class Outputs(BaseModel):
    visualizations: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    explanation: bool = True
    confidence: bool = True

    class Config:
        extra = "allow"


class Execution(BaseModel):
    priority: str = "accuracy"
    allow_mock_fallback: bool = True

    class Config:
        extra = "allow"


class AnalysisRequest(BaseModel):
    query: str
    intent: Intent
    aoi: AOI
    data_requirements: DataRequirements = Field(default_factory=DataRequirements)
    model_selection: ModelSelection = Field(
        default_factory=lambda: ModelSelection(model="prithvi-eo-2.0", reason="Default observation")
    )
    analysis: Analysis = Field(default_factory=lambda: Analysis(operation="observation"))
    outputs: Outputs = Field(default_factory=Outputs)
    execution: Execution = Field(default_factory=Execution)

    class Config:
        extra = "allow"


# ToolPlan is produced by ATS after capability matching (NOT inside AnalysisRequest)
class ToolPlan(BaseModel):
    tool: str  # "analyze_image" | "detect_change" | "analyze_multitemporal" | "analyze_sar_optical"
    model: str  # "earthdial-4b-ms" | "prithvi-eo-2.0" | "closp" | "terrafm" | "vista"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    requires_modalities: List[str] = Field(default_factory=list)
    status: str = "planned"  # "planned" | "needs_data" | "needs_clarification" | "rejected"
    missing_inputs: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"