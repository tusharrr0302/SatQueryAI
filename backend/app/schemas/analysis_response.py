from typing import List, Optional

from pydantic import BaseModel


class TimeSeriesMetric(BaseModel):
    date: str
    metric_name: str
    value: float


class AnalysisResponse(BaseModel):
    before_image_url: Optional[str] = None
    after_image_url: Optional[str] = None
    aoi_bbox: List[float]
    time_series: List[TimeSeriesMetric]