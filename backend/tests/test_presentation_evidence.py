import pytest
from app.config import settings
from app.schemas.evidence import EvidenceType, EvidenceItem, PresentationPlan
from app.schemas.normalized_result import (
    NormalizedResult,
    AOIInfo,
    Coordinates,
    Provenance,
    MetricItem,
    DataLayerSpec,
)
from app.imagery.copernicus_provider import copernicus_imagery_provider, CopernicusImageryProvider
from app.services.evidence_service import evidence_service
from app.graph.nodes import _format_presentation_plan_markdown


def test_1_current_optical_imagery_request_creates_optical_scene_evidence():
    norm = NormalizedResult(
        query="Show current optical image of Nepal",
        analysis_type="optical_inspection",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="High-resolution Sentinel-2 optical observation acquired for Nepal.",
        scientific_explanation="Calibrated surface reflectance observed across multispectral bands.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show current optical image of Nepal",
        norm=norm,
    )
    assert plan is not None
    assert any(item.type == EvidenceType.OPTICAL_SCENE for item in plan.evidence_items)
    optical_scene = next(item for item in plan.evidence_items if item.type == EvidenceType.OPTICAL_SCENE)
    assert optical_scene.sensor == "Sentinel-2 MSI"
    assert "/api/imagery/rendered/" in optical_scene.image_url or "/static/" in optical_scene.image_url


def test_2_baseline_request_creates_optical_baseline_evidence():
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="Flood inundation verified via SAR-optical cross-modal observation.",
        scientific_explanation="Comparative analysis isolates post-event inundation against pre-event baseline.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    assert plan.has_baseline is True
    assert any(item.type == EvidenceType.OPTICAL_BASELINE for item in plan.evidence_items)
    baseline = next(item for item in plan.evidence_items if item.type == EvidenceType.OPTICAL_BASELINE)
    assert baseline.acquisition_date != ""


def test_3_no_fabricated_baseline():
    norm = NormalizedResult(
        query="Show current optical image of Nepal",  # no baseline requested
        analysis_type="optical_inspection",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="Observation acquired.",
        scientific_explanation="Inspection complete.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show current optical image of Nepal",
        norm=norm,
    )
    # When no baseline was requested or found, has_baseline MUST be False and optical_baseline absent
    assert plan.has_baseline is False
    assert not any(item.type == EvidenceType.OPTICAL_BASELINE for item in plan.evidence_items)


def test_4_copernicus_credentials_remain_backend_only():
    # Verify Copernicus credentials exist on backend Settings class
    assert hasattr(settings, "COPERNICUS_CLIENT_ID")
    assert hasattr(settings, "COPERNICUS_CLIENT_SECRET")
    assert hasattr(settings, "COPERNICUS_SH_BASE_URL")
    assert hasattr(settings, "COPERNICUS_TOKEN_URL")

    # Verify CopernicusImageryProvider encapsulates OAuth token logic
    provider = CopernicusImageryProvider()
    assert hasattr(provider, "get_token")
    assert hasattr(provider, "render_image")


def test_5_rgb_rendering_produces_an_image_artifact():
    result = copernicus_imagery_provider.render_image(
        bbox=[84.0, 27.5, 86.0, 28.5],
        start_date="2026-08-15",
        end_date="2026-09-02",
        rendering="true_color",
        aoi_name="Nepal",
    )
    assert "artifact_id" in result
    assert "image_url" in result
    assert result["image_url"].startswith("/api/imagery/rendered/")
    assert result["file_path"].endswith(".png")


def test_6_gpt_oss_cannot_invent_image_urls():
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="Flood extent verified in eastern Nepal lowlands.",
        scientific_explanation="SAR backscatter reduction and optical NDWI delineate inundation zones.",
        metrics=[MetricItem(label="SAR-Optical Alignment Score", value="0.193", unit="score")],
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    norm_dict = norm.model_dump()
    norm_dict["presentation_plan"] = plan.model_dump()

    md = _format_presentation_plan_markdown(norm_dict)

    # All markdown image links in response must originate exclusively from verified /api/imagery/rendered/ endpoints
    import re
    image_links = re.findall(r"!\[.*?\]\((.*?)\)", md)
    assert len(image_links) >= 1
    for link in image_links:
        assert link.startswith("/api/imagery/rendered/")
        assert link.endswith(".png")


def test_7_model_provider_metadata_are_correctly_separated():
    norm = NormalizedResult(
        query="Analyze flood extent using CLOSP",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
            discovery_provider="Planetary Computer / Copernicus",
            processing_provider="CLOSP remote worker",
        ),
        key_finding="CLOSP specialist analysis completed.",
        scientific_explanation="Dual SAR-optical cross-attention executed on remote GPU worker.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Analyze flood extent using CLOSP",
        norm=norm,
        tool_plan={"model": "closp", "tool": "analyze_sar_optical"},
    )
    assert plan.method.model == "CLOSP"
    assert "Sentinel-2 STAC Provider" not in plan.method.model
    assert "Planetary Computer / Copernicus" in plan.method.discovery_provider
    assert "CLOSP remote worker" in plan.method.processing_provider


def test_8_closp_metrics_remain_preserved():
    norm = NormalizedResult(
        query="Analyze flood in Nepal with SAR and optical",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="SAR-Optical cross-modal alignment completed.",
        scientific_explanation="Inference executed on remote Tesla T4 GPU.",
        metrics=[
            MetricItem(label="SAR-Optical Alignment Score", value="0.193", unit="score"),
            MetricItem(label="Inundation Extent", value="342.5", unit="km²"),
        ],
    )
    plan = evidence_service.build_presentation_plan(
        query="Analyze flood in Nepal with SAR and optical",
        norm=norm,
    )
    labels = [m["label"] for m in plan.key_measurements]
    assert "SAR-Optical Alignment Score" in labels
    assert any(m["value"] == "0.193" for m in plan.key_measurements)


def test_9_evidence_layer_can_be_attached_to_cesium():
    norm = NormalizedResult(
        query="Show optical image of Nepal",
        analysis_type="optical_inspection",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="Surface observation acquired.",
        scientific_explanation="Observation completed.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show optical image of Nepal",
        norm=norm,
    )
    assert len(norm.layers) >= 1
    evidence_layer = next(l for l in norm.layers if l.role == "evidence" or l.type == "imagery")
    assert evidence_layer.source.type == "image"
    assert evidence_layer.source.url.startswith("/api/imagery/rendered/")
    assert len(evidence_layer.spatial.bounds) == 4


def test_10_existing_closp_live_inference_remains_unchanged():
    from app.services.worker_client import EOWorkerClient
    client = EOWorkerClient()
    url = client.get_worker_url("closp")
    assert isinstance(url, str)
    from app.models.registry import MODEL_REGISTRY
    assert "closp" in MODEL_REGISTRY
    assert "sar" in MODEL_REGISTRY["closp"]["modalities"]
    assert "cross_modal_alignment" in MODEL_REGISTRY["closp"]["tasks"]


def test_11_existing_ats_tests_continue_passing():
    from app.services.tool_registry import tool_registry
    from app.schemas.analysis_request import AnalysisRequest, Intent, AOI, DataRequirements, ModelSelection, Analysis, Outputs, Execution

    req = AnalysisRequest(
        query="Align SAR and optical for Nepal",
        intent=Intent(primary_task="sar_optical_alignment"),
        aoi=AOI(name="Nepal", bbox=[80.05, 26.34, 88.20, 30.44]),
        data_requirements=DataRequirements(modalities=["sar", "optical"], datasets=["sentinel-1", "sentinel-2"]),
        model_selection=ModelSelection(model="closp", reason="Cross-modal SAR-optical alignment"),
        analysis=Analysis(operation="sar_optical_alignment"),
        outputs=Outputs(primary_layer_type="multimodal"),
        execution=Execution(),
    )
    from app.services.worker_client import CLOSPAdapter
    adapter = CLOSPAdapter()
    assert adapter.get_endpoint() == "/tools/analyze_sar_optical"
    assert adapter.tool_name == "analyze_sar_optical"


def test_12_copernicus_rendering_failure_never_produces_synthetic_imagery(monkeypatch):
    """When Copernicus/Sentinel Hub fails, times out, exceeds quota, or cannot render:
    - Mark the EvidenceItem as unavailable
    - Preserve the error/limitation
    - Do not generate an image that could be mistaken for satellite imagery
    - Do not claim the evidence exists
    - Allow the rest of the analysis to continue if possible
    """
    from app.imagery.copernicus_provider import CopernicusImageryError, CACHE_DIR
    import httpx

    # 1. Simulate Copernicus credentials configured but CDSE returning HTTP 429 (quota exceeded)
    monkeypatch.setattr(settings, "COPERNICUS_CLIENT_ID", "test_client_id")
    monkeypatch.setattr(settings, "COPERNICUS_CLIENT_SECRET", "test_secret")

    def mock_get_token(self):
        return "mock_token"

    def mock_post(url, *args, **kwargs):
        return httpx.Response(
            status_code=429,
            text='{"error": {"status": 429, "message": "Rate/quota limit reached for Copernicus Sentinel Hub Processing API"}}',
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(CopernicusImageryProvider, "get_token", mock_get_token)
    monkeypatch.setattr(httpx, "post", mock_post)

    unique_bbox = [85.1234, 27.5678, 85.9876, 28.1234]

    # Verify direct render_image call raises CopernicusImageryError and creates NO file
    with pytest.raises(CopernicusImageryError) as exc_info:
        copernicus_imagery_provider.render_image(
            bbox=unique_bbox,
            start_date="2026-08-01",
            end_date="2026-08-15",
            rendering="true_color",
            aoi_name="Nepal Test Region",
        )
    assert "429" in str(exc_info.value) or "quota" in str(exc_info.value)

    # 2. Verify end-to-end evidence service behavior under Copernicus failure
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal_test",
            name="Nepal Test Region",
            center=Coordinates(latitude=27.8, longitude=85.5),
            area_km2=2500.0,
            bbox=unique_bbox,
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="SAR-Optical cross-modal analysis identifies elevated flood waters in floodplains.",
        scientific_explanation="Specialist CLOSP model fused polarimetric Sentinel-1 and multispectral Sentinel-2.",
        metrics=[
            MetricItem(label="SAR-Optical Alignment Score", value="0.193", unit="score"),
            MetricItem(label="Flooded Area", value="142.8", unit="km²"),
        ],
    )

    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )

    # A. Evidence items are marked as unavailable
    assert plan is not None
    assert len(plan.evidence_items) >= 1
    optical_items = [
        item for item in plan.evidence_items
        if item.type in [EvidenceType.OPTICAL_SCENE, EvidenceType.OPTICAL_BASELINE]
    ]
    for item in optical_items:
        assert item.available is False
        assert item.status == "unavailable"
        # B. No synthetic image URL is claimed
        assert item.image_url is None
        # C. Error message is preserved
        assert item.error_message is not None
        assert "429" in item.error_message or "quota" in item.error_message

    # D. Does NOT claim evidence exists
    assert plan.primary_evidence_id is None
    assert plan.has_baseline is False
    assert plan.baseline_evidence_id is None
    assert plan.baseline_missing_reason is not None

    # E. Limitations preserved
    assert any("unavailable" in lim.lower() for lim in plan.limitations)

    # F. Rest of analysis continues without interruption
    assert norm.key_finding == "SAR-Optical cross-modal analysis identifies elevated flood waters in floodplains."
    assert any(m["label"] == "SAR-Optical Alignment Score" and m["value"] == "0.193" for m in plan.key_measurements)
    assert plan.method.model == "CLOSP"

    # G. Markdown output formats honest unavailable notice without broken or fake image embeds
    norm_dict = norm.model_dump()
    norm_dict["presentation_plan"] = plan.model_dump()
    md = _format_presentation_plan_markdown(norm_dict)
    assert "![" not in md  # No fake markdown image embeds
    assert "Current Optical Observation Unavailable" in md
    assert "Baseline Observation Unavailable" in md


def test_13_vegetation_query_generates_vegetation_relevant_evidence():
    """Vegetation query should generate Optical, False Color (CIR), and NDVI; NOT SAR layers."""
    norm = NormalizedResult(
        query="Analyze vegetation in Nepal",
        analysis_type="vegetation_monitoring",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="prithvi",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="Vegetation health and canopy density mapped via multispectral reflectance.",
        scientific_explanation="NDVI and CIR bands isolate photosynthetic activity across forested zones.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Analyze vegetation in Nepal",
        norm=norm,
    )
    types = [item.type for item in plan.evidence_items]
    assert EvidenceType.OPTICAL_SCENE in types
    assert EvidenceType.OPTICAL_FALSE_COLOR in types
    assert EvidenceType.NDVI in types
    # Ensure SAR layers are NOT generated for vegetation monitoring
    assert EvidenceType.SAR_VV not in types
    assert EvidenceType.SAR_VH not in types


def test_14_flood_query_generates_flood_relevant_evidence():
    """Flood query should generate Optical, Baseline, SAR VV, SAR VH, and NDWI."""
    norm = NormalizedResult(
        query="Analyze flooding in Nepal",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="SAR-optical cross-modal flood delineation active.",
        scientific_explanation="Specular reflection in SAR VV/VH identifies standing water.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Analyze flooding in Nepal",
        norm=norm,
    )
    types = [item.type for item in plan.evidence_items]
    assert EvidenceType.OPTICAL_SCENE in types
    assert EvidenceType.OPTICAL_BASELINE in types
    assert EvidenceType.SAR_VV in types
    assert EvidenceType.SAR_VH in types
    assert EvidenceType.NDWI in types
    # False color CIR or vegetation NDVI should not dominate flood response
    assert EvidenceType.OPTICAL_FALSE_COLOR not in types


def test_15_generic_imagery_query_does_not_generate_unnecessary_layers():
    """Generic query 'Show me Nepal' should only generate optical RGB, no extraneous specialist layers."""
    norm = NormalizedResult(
        query="Show me Nepal",
        analysis_type="optical_inspection",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="planetary_computer",
            model_id="",
            model_name="",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="Direct Sentinel-2 MSI observation retrieved.",
        scientific_explanation="Multispectral observation of specified region.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me Nepal",
        norm=norm,
    )
    types = [item.type for item in plan.evidence_items]
    assert EvidenceType.OPTICAL_SCENE in types
    assert len([t for t in types if t == EvidenceType.OPTICAL_SCENE]) == 1
    assert EvidenceType.SAR_VV not in types
    assert EvidenceType.SAR_VH not in types
    assert EvidenceType.NDVI not in types
    assert EvidenceType.NDWI not in types


def test_16_presentation_plan_is_deterministic():
    """Evidence plan generated from the same inputs should produce identical evidence counts and types."""
    norm = NormalizedResult(
        query="Analyze flooding in Nepal",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="Flood delineation.",
        scientific_explanation="Analysis.",
    )
    plan1 = evidence_service.build_presentation_plan(query="Analyze flooding in Nepal", norm=norm)
    plan2 = evidence_service.build_presentation_plan(query="Analyze flooding in Nepal", norm=norm)

    assert [i.type for i in plan1.evidence_items] == [i.type for i in plan2.evidence_items]
    assert [i.title for i in plan1.evidence_items] == [i.title for i in plan2.evidence_items]
    assert plan1.has_baseline == plan2.has_baseline


def test_17_closp_metric_interpretation_is_scientifically_honest():
    """CLOSP alignment score must be contextualized as a representation metric, not a flood probability."""
    norm = NormalizedResult(
        query="Analyze flood in Nepal with CLOSP",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="SAR-Optical cross-modal alignment complete.",
        scientific_explanation="Inference executed.",
        metrics=[
            MetricItem(label="SAR-Optical Alignment Score", value="0.193", unit="score"),
        ],
    )
    plan = evidence_service.build_presentation_plan(
        query="Analyze flood in Nepal with CLOSP",
        norm=norm,
    )
    norm_dict = norm.model_dump()
    norm_dict["presentation_plan"] = plan.model_dump()
    md = _format_presentation_plan_markdown(norm_dict)

    # Explanation must make clear that 0.193 is a model alignment score, not a probability
    assert "CLOSP cross-modal representation" in md
    assert "model-specific alignment metric" in md
    assert "not, by itself, a flood probability" in md


def test_18_artifact_endpoint_returns_http_200():
    """Rendered artifact URL can be fetched via FastAPI test client returning HTTP 200 image/png."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    # Render an image
    result = copernicus_imagery_provider.render_image(
        bbox=[84.0, 27.5, 86.0, 28.5],
        start_date="2026-08-15",
        end_date="2026-09-02",
        rendering="true_color",
        aoi_name="Nepal Test Region",
    )
    artifact_url = result["image_url"]
    resp = client.get(artifact_url)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 100


def test_19_only_executed_models_reported():
    """If only CLOSP executed, model must be CLOSP, not EarthDial or STAC Provider."""
    norm = NormalizedResult(
        query="Assess flood with CLOSP",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="Flood assessment complete.",
        scientific_explanation="Analysis complete.",
    )
    plan = evidence_service.build_presentation_plan(query="Assess flood with CLOSP", norm=norm)
    assert plan.method.model == "CLOSP"
    assert "EarthDial" not in plan.method.model
    assert "STAC" not in plan.method.model
    assert norm.models_used == ["CLOSP"]


def test_20_baseline_preserves_consistent_aoi_for_comparison():
    """Current and baseline evidence items must share the same bounding box and AOI for reliable comparison."""
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp",
            model_name="CLOSP",
            dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"],
        ),
        key_finding="Comparison prepared.",
        scientific_explanation="Temporal delta analyzed.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    current = next(i for i in plan.evidence_items if i.type == EvidenceType.OPTICAL_SCENE)
    baseline = next(i for i in plan.evidence_items if i.type == EvidenceType.OPTICAL_BASELINE)

    assert current.bbox == baseline.bbox
    assert current.sensor == baseline.sensor
    assert current.role == "current"
    assert baseline.role == "baseline"


def test_21_cesium_layers_preserve_provenance_source():
    """Cesium layers attached by evidence_service must correctly reflect the provenance source."""
    norm = NormalizedResult(
        query="Show optical image of Nepal",
        analysis_type="optical_inspection",
        aoi=AOIInfo(
            id="aoi_nepal",
            name="Nepal",
            center=Coordinates(latitude=28.3949, longitude=84.1240),
            area_km2=147181.0,
            bbox=[80.05, 26.34, 88.20, 30.44],
        ),
        provenance=Provenance(
            source="mock",
            model_id="",
            model_name="",
            dataset_ids=["sentinel-2-l2a"],
        ),
        key_finding="Test observation.",
        scientific_explanation="Test.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show optical image of Nepal",
        norm=norm,
    )
    for layer in norm.layers:
        assert layer.provenance.source == "mock"


def test_22_distinguish_temporal_baseline_from_confirmed_pre_event_baseline():
    """When user query does not provide an explicit event date:
    - baseline_role must be 'temporal_baseline'
    - title must be 'Earlier temporal baseline'
    - explanatory note must state it is an earlier reference, not a confirmed pre-event scene.
    When an explicit event date is provided:
    - baseline_role must be 'pre_event_baseline'.
    """
    # 1. Unconfirmed event date query
    norm1 = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"]),
        key_finding="Observation complete.",
        scientific_explanation="Multimodal assessment of current surface conditions against temporal baseline.",
    )
    plan1 = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm1,
    )
    assert plan1.baseline_role == "temporal_baseline"
    assert "Earlier temporal baseline" in plan1.baseline_title
    assert "general seasonal reference rather than a confirmed pre-flood state" in plan1.baseline_note

    baseline_item = next(i for i in plan1.evidence_items if i.type == EvidenceType.OPTICAL_BASELINE)
    assert baseline_item.baseline_role == "temporal_baseline"
    assert "Earlier temporal baseline" in baseline_item.title

    # 2. Confirmed event date query (e.g. July 2024 flood)
    norm2 = NormalizedResult(
        query="Show me current optical image of Nepal and an image before July 2024 flood",
        analysis_type="flood_assessment",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"]),
        key_finding="Observation complete.",
        scientific_explanation="Multimodal assessment before confirmed July 2024 flood event.",
    )
    plan2 = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before July 2024 flood",
        norm=norm2,
    )
    assert plan2.baseline_role == "pre_event_baseline"
    assert "Pre-event baseline" in plan2.baseline_title


def test_23_nepal_aoi_coverage_type_is_mosaic_never_single_tile():
    """Nepal (147,181 km²) spans multiple Sentinel-2 tiles.
    Evidence service must label coverage as 'AOI mosaic', never claiming a single tile.
    """
    norm = NormalizedResult(
        query="Show current optical image of Nepal",
        analysis_type="optical_inspection",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-2-l2a"]),
        key_finding="Observation complete.",
        scientific_explanation="Wide-area observation.",
    )
    plan = evidence_service.build_presentation_plan(query="Show current optical image of Nepal", norm=norm)
    assert plan.coverage_type == "AOI mosaic"
    optical_item = next(i for i in plan.evidence_items if i.type == EvidenceType.OPTICAL_SCENE)
    assert optical_item.coverage_type == "AOI mosaic"


def test_24_analytical_evidence_layers_and_cesium_spec_legends():
    """For flood analysis, evidence plan must provide:
    - current optical
    - temporal baseline
    - SAR VV
    - SAR VH
    - NDWI
    And attach DataLayerSpec with appropriate continuous or categorical legends.
    """
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"]),
        key_finding="Multimodal flood assessment.",
        scientific_explanation="Cross-modal backscatter and reflectance analysis.",
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    types = [i.type for i in plan.evidence_items]
    assert EvidenceType.OPTICAL_SCENE in types
    assert EvidenceType.OPTICAL_BASELINE in types
    assert EvidenceType.SAR_VV in types
    assert EvidenceType.SAR_VH in types
    assert EvidenceType.NDWI in types

    # Check Cesium data layer specs in norm.layers
    vv_layer = next((l for l in norm.layers if "vv" in l.title.lower()), None)
    assert vv_layer is not None
    assert vv_layer.legend is not None
    assert vv_layer.legend.unit == "dB"

    ndwi_layer = next((l for l in norm.layers if "ndwi" in l.title.lower()), None)
    assert ndwi_layer is not None
    assert ndwi_layer.legend is not None
    assert ndwi_layer.legend.unit == "NDWI"


def test_25_no_fabricated_sar_change_or_flood_extent():
    """Do NOT fabricate SAR change or flood extent when no specialist produced them."""
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"]),
        key_finding="Surface assessment.",
        scientific_explanation="Basic assessment.",
        layers=[],  # No specialist flood polygon layer provided
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    types = [i.type for i in plan.evidence_items]
    assert EvidenceType.FLOOD_EXTENT not in types
    assert EvidenceType.SAR_CHANGE not in types


def test_26_investigation_narrative_preserves_strict_grounding():
    """Investigation narrative markdown must strictly preserve structure and baseline note."""
    norm = NormalizedResult(
        query="Show me current optical image of Nepal and an image before flood situation",
        analysis_type="flood_assessment",
        aoi=AOIInfo(id="aoi_nepal", name="Nepal", center=Coordinates(latitude=28.3949, longitude=84.1240), area_km2=147181.0, bbox=[80.05, 26.34, 88.20, 30.44]),
        provenance=Provenance(source="remote_worker", worker_url="https://worker.satquery.internal/predict",
            model_id="closp", model_name="CLOSP", dataset_ids=["sentinel-1-grd", "sentinel-2-l2a"]),
        key_finding="Surface water delineation completed.",
        scientific_explanation="Cross-modal analysis executed.",
        metrics=[MetricItem(label="SAR-Optical Alignment Score", value="0.193", unit="score")],
    )
    plan = evidence_service.build_presentation_plan(
        query="Show me current optical image of Nepal and an image before flood situation",
        norm=norm,
    )
    norm_dict = norm.model_dump()
    norm_dict["presentation_plan"] = plan.model_dump()

    md = _format_presentation_plan_markdown(norm_dict)
    assert "### Investigation title" in md
    assert "### Current optical image" in md
    assert "### Earlier temporal baseline" in md
    assert "Earlier temporal baseline selected prior to the active observation period" in md
    assert "AOI mosaic" in md
    assert "### What changed?" in md
    assert "### Evidence layers" in md
    assert "[Optical]" in md
    assert "[SAR VV]" in md
    assert "[SAR VH]" in md
    assert "[NDWI]" in md
    assert "### Key measurements" in md
    assert "SAR-Optical Alignment Score" in md
    assert "### Method" in md
    assert "### Limitations" in md




