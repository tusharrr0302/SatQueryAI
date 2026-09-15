from typing import List, Optional

from pydantic import BaseModel, Field


class TemporalScope(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    comparison_strategy: Optional[str] = None

    class Config:
        extra = "forbid"


class Intent(BaseModel):
    primary_task: str
    domain: Optional[str] = None
    question_type: Optional[str] = None
    spatial_scope: Optional[str] = None
    temporal_scope: Optional[TemporalScope] = None

    class Config:
        extra = "forbid"


class AOI(BaseModel):
    type: str
    name: Optional[str] = None
    country: Optional[str] = None

    class Config:
        extra = "forbid"


class DataRequirements(BaseModel):
    modalities: List[str]
    datasets: List[str]
    temporal_resolution: Optional[str]
    cloud_constraint: Optional[str]
    spatial_resolution: Optional[str]

    class Config:
        extra = "forbid"


class ModelSelection(BaseModel):
    model: str
    reason: str

    class Config:
        extra = "forbid"


class ComparisonPeriod(BaseModel):
    label: str
    start: str
    end: str

    class Config:
        extra = "forbid"


class Analysis(BaseModel):
    operation: str
    comparison_periods: List[ComparisonPeriod] = Field(
        default_factory=list
    )
    target_classes: List[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class Outputs(BaseModel):
    visualizations: List[str]
    metrics: List[str]
    explanation: bool
    confidence: bool

    class Config:
        extra = "forbid"


class Execution(BaseModel):
    priority: str = "accuracy"
    allow_mock_fallback: bool = True

    class Config:
        extra = "forbid"


class AnalysisRequest(BaseModel):
    query: str
    intent: Intent
    aoi: AOI
    data_requirements: DataRequirements
    model_selection: ModelSelection
    analysis: Analysis
    outputs: Outputs
    execution: Execution

    class Config:
        extra = "forbid"