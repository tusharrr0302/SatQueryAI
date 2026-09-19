"""
SatQuery AI — Multi-Asset Spatial & Spectral Relationship Analyzer
Evaluates spatial intersection, temporal pairing, and multimodal compatibility
between two uploaded Earth observation datasets.
"""
from __future__ import annotations
from typing import List, Optional
from app.schemas.data_asset import DataProfile, AssetRelationship


def _compute_bbox_iou(box1: List[float], box2: List[float]) -> float:
    """Calculates Intersection over Union (IoU) of two [minx, miny, maxx, maxy] boxes."""
    if not box1 or not box2 or len(box1) < 4 or len(box2) < 4:
        return 0.0

    ixmin = max(box1[0], box2[0])
    iymin = max(box1[1], box2[1])
    ixmax = min(box1[2], box2[2])
    iymax = min(box1[3], box2[3])

    iw = max(0.0, ixmax - ixmin)
    ih = max(0.0, iymax - iymin)
    intersection = iw * ih

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0
    return intersection / union


class DataRelationshipAnalyzer:
    """Analyzes compatibility and workflows between two DataProfiles."""

    @staticmethod
    def analyze(profile_a: DataProfile, profile_b: DataProfile) -> AssetRelationship:
        # Check spatial overlap
        iou = _compute_bbox_iou(profile_a.bounds or [], profile_b.bounds or [])
        spatial_overlap = iou > 0.05

        if not spatial_overlap:
            return AssetRelationship(
                relationship_type="spatial_disjoint",
                asset_a_id=profile_a.asset_id,
                asset_b_id=profile_b.asset_id,
                compatible=False,
                summary=f"No significant geographic overlap detected between {profile_a.filename} and {profile_b.filename}.",
                possible_analyses=[],
                limitations=["Images cover different geographical areas; bi-temporal change detection not feasible."],
            )

        # Check CRS compatibility
        crs_compatible = profile_a.crs == profile_b.crs if profile_a.crs and profile_b.crs else False

        # Multimodal: Optical + SAR
        is_optical_sar = (
            (profile_a.modality in ["optical", "multispectral"] and profile_b.modality == "sar") or
            (profile_b.modality in ["optical", "multispectral"] and profile_a.modality == "sar")
        )
        if is_optical_sar:
            return AssetRelationship(
                relationship_type="multimodal_pair",
                asset_a_id=profile_a.asset_id,
                asset_b_id=profile_b.asset_id,
                compatible=True,
                summary=f"Multimodal pair identified: {profile_a.filename} and {profile_b.filename} provide complementary Optical and Synthetic Aperture Radar (SAR) telemetry.",
                possible_analyses=[
                    "Optical-SAR Joint Built-up Classification",
                    "All-Weather Inundation & Flood Extent Verification",
                    "Surface Roughness vs. Vegetative Reflectance Fusion",
                ],
                limitations=[] if crs_compatible else ["Datasets use different coordinate reference systems; spatial reprojection required before pixel-wise fusion."],
            )

        # Temporal Pair (both optical / multispectral)
        possible_analyses = [
            "Bi-temporal Change Detection (NDVI Difference)",
            "Impervious Urban Footprint Expansion Mapping",
            "Longitudinal Land-Cover Transition Matrix",
            "Side-by-side Synchronized Swipe Inspection",
        ]
        limitations = []
        if not crs_compatible:
            limitations.append(f"CRS mismatch: {profile_a.crs} vs {profile_b.crs}. Reprojection advised.")

        return AssetRelationship(
            relationship_type="temporal_pair",
            asset_a_id=profile_a.asset_id,
            asset_b_id=profile_b.asset_id,
            compatible=True,
            summary=f"Temporal pair identified with {iou * 100:.1f}% spatial overlap across {profile_a.filename} and {profile_b.filename}.",
            possible_analyses=possible_analyses,
            limitations=limitations,
        )
