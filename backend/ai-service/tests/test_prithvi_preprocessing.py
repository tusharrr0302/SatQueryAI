"""
tests/test_prithvi_preprocessing.py
─────────────────────────────────────────────────────────────────────────────
Tests for the Prithvi-EO-2.0-300M preprocessing layer (Step 3A).

These tests verify the complete:
    MultiTemporalInput
         |
    prithvi_preprocessing.preprocess_multitemporal()
         |
    PrithviPreprocessingResult: shape (4, 6, 224, 224), dtype float32

All tests use synthetic NumPy arrays injected via BandAssetLoader.register().
No real satellite imagery, no downloads, no GPU required.

Band naming convention:
    Field names are Sentinel-2 native identifiers (B02, B03, B04, B08A, B11, B12).
    The Prithvi/HLS channel order is enforced by PRITHVI_BAND_ORDER.
    Normalisation constants are the official HLS pretraining statistics.

Run with:
    cd ai-service
    pytest tests/test_prithvi_preprocessing.py -v
"""
from __future__ import annotations

import pytest
import numpy as np

from app.schemas.requests import (
    MultiTemporalInput,
    TemporalFrame,
    SpectralBands,
)
from app.services.prithvi_preprocessing import (
    BandAssetLoader,
    PrithviPreprocessingError,
    PrithviPreprocessingResult,
    PRITHVI_BAND_ORDER,
    PRITHVI_MODEL_BANDS,
    S2_TO_PRITHVI_BAND_MAP,
    PRITHVI_N_FRAMES,
    PRITHVI_SPATIAL_SIZE,
    PRITHVI_TARGET_RESOLUTION_M,
    _PRITHVI_MEAN,
    _PRITHVI_STD,
    preprocess_multitemporal,
    _crop_or_pad,
    _resample_to_target,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

# Six distinct constant values -- one per band, in PRITHVI_BAND_ORDER
# B02=100, B03=200, B04=300, B08A=400, B11=500, B12=600
BAND_CONSTANTS = {
    "B02":  100.0,
    "B03":  200.0,
    "B04":  300.0,
    "B08A": 400.0,
    "B11":  500.0,
    "B12":  600.0,
}

# Fixed spatial size for synthetic arrays (matching target to avoid resampling)
H = PRITHVI_SPATIAL_SIZE
W = PRITHVI_SPATIAL_SIZE

# Date strings for 4 frames, already chronological
DATES_CHRONOLOGICAL = [
    "2020-06-15",
    "2021-06-15",
    "2022-06-15",
    "2024-06-15",
]


def _make_loader_and_mti(
    dates: list[str] | None = None,
    band_constants: dict[str, float] | None = None,
    h: int = H,
    w: int = W,
    missing_band: str | None = None,
) -> tuple[BandAssetLoader, MultiTemporalInput]:
    """
    Build a BandAssetLoader + MultiTemporalInput for testing.

    Each band gets a synthetic (h, w) array filled with its constant value.
    URLs follow the pattern: "mock://frame/{date}/{band}.tif"

    Args:
        dates:         List of exactly 4 ISO date strings.
        band_constants: Map of band name -> fill value.
        h, w:          Spatial dimensions of synthetic arrays.
        missing_band:  If set, omit this band from ALL frames (simulate missing).
    """
    if dates is None:
        dates = DATES_CHRONOLOGICAL
    if band_constants is None:
        band_constants = BAND_CONSTANTS

    loader = BandAssetLoader()
    frames: list[TemporalFrame] = []

    for date in dates:
        band_urls: dict[str, str] = {}
        for band_name in PRITHVI_BAND_ORDER:
            if band_name == missing_band:
                continue  # intentionally omit
            url = f"mock://frame/{date}/{band_name}.tif"
            arr = np.full((h, w), band_constants[band_name], dtype=np.float32)
            loader.register(url, arr)
            band_urls[band_name] = url

        frame = TemporalFrame(
            acquisition_date=date,
            bands=SpectralBands(**band_urls),
        )
        frames.append(frame)

    mti = MultiTemporalInput(
        frames=frames,
        bbox=[77.5, 29.0, 80.5, 31.5],
        query="Test multitemporal input",
    )
    return loader, mti


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Output shape
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputShape:
    """The preprocessor must produce exactly (4, 6, 224, 224)."""

    def test_shape_is_4_6_224_224(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.array.shape == (4, 6, 224, 224), (
            f"Expected shape (4, 6, 224, 224), got {result.array.shape}"
        )

    def test_result_shape_attribute_matches_array(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.shape == result.array.shape

    def test_shape_tuple_values(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        T, C, H_out, W_out = result.shape
        assert T == 4
        assert C == 6
        assert H_out == 224
        assert W_out == 224


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — dtype
# ─────────────────────────────────────────────────────────────────────────────

class TestDtype:
    """The final array must be float32."""

    def test_dtype_is_float32(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.array.dtype == np.float32, (
            f"Expected float32, got {result.array.dtype}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Band ordering
# ─────────────────────────────────────────────────────────────────────────────

class TestBandOrdering:
    """
    Each channel must correspond to the correct Sentinel-2 band.

    The test assigns a UNIQUE constant value to each band:
        B02=100, B03=200, B04=300, B08A=400, B11=500, B12=600

    After normalization, channel i should be consistent with the constant
    value that was assigned to band PRITHVI_BAND_ORDER[i].

    We verify by reversing normalization for a pixel and comparing to the
    expected per-band constant.
    """

    def test_channel_order_is_correct(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)

        for ch_idx, band_name in enumerate(PRITHVI_BAND_ORDER):
            expected_raw = BAND_CONSTANTS[band_name]
            mean = float(_PRITHVI_MEAN[ch_idx])
            std = float(_PRITHVI_STD[ch_idx])
            expected_norm = (expected_raw - mean) / std

            # Every pixel in this channel of frame 0 should be ~expected_norm
            actual = float(result.array[0, ch_idx, 0, 0])
            assert abs(actual - expected_norm) < 1e-4, (
                f"Channel {ch_idx} ({band_name}): "
                f"expected normalised value {expected_norm:.6f}, "
                f"got {actual:.6f}. "
                "Possible band ordering error."
            )

    def test_band_order_attribute_matches_constant(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.band_order == PRITHVI_BAND_ORDER


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Temporal ordering
# ─────────────────────────────────────────────────────────────────────────────

class TestTemporalOrdering:
    """
    Frames must be ordered oldest -> newest regardless of input order.

    Strategy: assign a different fill value to each date so we can detect
    which frame appears in which temporal slot after preprocessing.

    Frame values:
        2020 -> all-bands fill = 1000
        2021 -> all-bands fill = 2000
        2022 -> all-bands fill = 3000
        2024 -> all-bands fill = 4000

    We check that frame 0 has the smallest value, frame 3 the largest.
    """

    def _make_temporal_loader_mti(self) -> tuple[BandAssetLoader, MultiTemporalInput]:
        """Create a loader where each frame has a distinctive fill value."""
        dates_to_fill = {
            "2020-06-15": 1000.0,
            "2021-06-15": 2000.0,
            "2022-06-15": 3000.0,
            "2024-06-15": 4000.0,
        }

        loader = BandAssetLoader()
        # Provide frames in REVERSE order to ensure sorting is tested
        reversed_dates = list(reversed(list(dates_to_fill.keys())))
        frames: list[TemporalFrame] = []

        for date in reversed_dates:
            fill = dates_to_fill[date]
            band_urls: dict[str, str] = {}
            for band_name in PRITHVI_BAND_ORDER:
                url = f"mock://temporal/{date}/{band_name}.tif"
                arr = np.full((H, W), fill, dtype=np.float32)
                loader.register(url, arr)
                band_urls[band_name] = url
            frames.append(TemporalFrame(
                acquisition_date=date,
                bands=SpectralBands(**band_urls),
            ))

        mti = MultiTemporalInput(
            frames=frames,
            bbox=[77.5, 29.0, 80.5, 31.5],
            query="Temporal order test",
        )
        return loader, mti

    def test_frames_sorted_oldest_to_newest(self):
        loader, mti = self._make_temporal_loader_mti()
        result = preprocess_multitemporal(mti, loader=loader)

        # Check that frame_dates are in chronological order
        dates = result.frame_dates
        assert dates == sorted(dates), (
            f"frame_dates not sorted: {dates}"
        )

    def test_frame_dates_attribute_is_chronological(self):
        loader, mti = self._make_temporal_loader_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        expected_dates = sorted([
            "2020-06-15", "2021-06-15", "2022-06-15", "2024-06-15"
        ])
        assert result.frame_dates == expected_dates

    def test_temporal_values_are_monotonically_increasing(self):
        """
        The raw (pre-norm) fill value increases frame by frame.
        After normalisation the order must still be preserved because
        mean/std are constant across frames.
        """
        loader, mti = self._make_temporal_loader_mti()
        result = preprocess_multitemporal(mti, loader=loader)

        # Compare mean value of channel 0 across frames
        ch0_means = [float(result.array[t, 0, :, :].mean()) for t in range(4)]
        for i in range(3):
            assert ch0_means[i] < ch0_means[i + 1], (
                f"Temporal order broken: frame {i} mean ({ch0_means[i]:.4f}) >= "
                f"frame {i+1} mean ({ch0_means[i+1]:.4f})"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalisation:
    """
    Verify the Prithvi normalisation: (pixel - mean) / std per channel.

    For a synthetic pixel with value == mean, the normalised output must be 0.
    """

    def _make_mean_mti(self) -> tuple[BandAssetLoader, MultiTemporalInput]:
        """Create frames where each band is filled with its own mean value."""
        mean_constants = {
            "B02":  float(_PRITHVI_MEAN[0]),  # 1087
            "B03":  float(_PRITHVI_MEAN[1]),  # 1342
            "B04":  float(_PRITHVI_MEAN[2]),  # 1433
            "B08A": float(_PRITHVI_MEAN[3]),  # 2734
            "B11":  float(_PRITHVI_MEAN[4]),  # 1958
            "B12":  float(_PRITHVI_MEAN[5]),  # 1363
        }
        return _make_loader_and_mti(band_constants=mean_constants)

    def test_pixel_at_mean_normalises_to_zero(self):
        """B02 pixel value = 1087 (mean) must normalise to 0."""
        loader, mti = self._make_mean_mti()
        result = preprocess_multitemporal(mti, loader=loader)

        # Channel 0 = B02, mean=1087 -> (1087 - 1087) / 2248 = 0
        b02_values = result.array[:, 0, :, :]  # all frames, B02 channel
        np.testing.assert_allclose(
            b02_values, 0.0, atol=1e-5,
            err_msg="B02 pixels at mean value must normalise to 0"
        )

    def test_pixel_at_mean_normalises_to_zero_all_channels(self):
        """All channels at mean value must normalise to 0."""
        loader, mti = self._make_mean_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        np.testing.assert_allclose(
            result.array, 0.0, atol=1e-5,
            err_msg="All channels at mean must normalise to 0"
        )

    def test_normalisation_formula(self):
        """
        Verify the formula: normalised = (raw - mean) / std.
        Use B02 raw value = 1087 + 2248 = 3335 -> expected = (3335-1087)/2248 = 1.0
        """
        test_value = float(_PRITHVI_MEAN[0]) + float(_PRITHVI_STD[0])  # 1087+2248=3335
        custom_constants = dict(BAND_CONSTANTS)
        custom_constants["B02"] = test_value

        loader, mti = _make_loader_and_mti(band_constants=custom_constants)
        result = preprocess_multitemporal(mti, loader=loader)

        b02_norm = float(result.array[0, 0, 0, 0])
        assert abs(b02_norm - 1.0) < 1e-4, (
            f"Expected normalised B02 = 1.0, got {b02_norm:.6f}"
        )

    def test_b11_normalisation(self):
        """
        B11 (channel 4): raw=1958 (mean), std=1242.
        At raw=1958+1242=3200, normalised should be 1.0.
        """
        test_value = float(_PRITHVI_MEAN[4]) + float(_PRITHVI_STD[4])
        custom_constants = dict(BAND_CONSTANTS)
        custom_constants["B11"] = test_value

        loader, mti = _make_loader_and_mti(band_constants=custom_constants)
        result = preprocess_multitemporal(mti, loader=loader)

        b11_norm = float(result.array[0, 4, 0, 0])  # channel 4 = B11
        assert abs(b11_norm - 1.0) < 1e-4, (
            f"Expected normalised B11 = 1.0, got {b11_norm:.6f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Missing band
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingBand:
    """Preprocessing must reject frames with missing required bands."""

    def test_missing_b02_raises_error(self):
        loader, mti = _make_loader_and_mti(missing_band="B02")
        with pytest.raises(PrithviPreprocessingError, match="B02"):
            preprocess_multitemporal(mti, loader=loader)

    def test_missing_b08a_raises_error(self):
        loader, mti = _make_loader_and_mti(missing_band="B08A")
        with pytest.raises(PrithviPreprocessingError, match="B08A"):
            preprocess_multitemporal(mti, loader=loader)

    def test_missing_b12_raises_error(self):
        loader, mti = _make_loader_and_mti(missing_band="B12")
        with pytest.raises(PrithviPreprocessingError, match="B12"):
            preprocess_multitemporal(mti, loader=loader)

    def test_error_is_prithvi_preprocessing_error(self):
        """Ensure the exception type is correct (not a generic ValueError)."""
        loader, mti = _make_loader_and_mti(missing_band="B04")
        with pytest.raises(PrithviPreprocessingError):
            preprocess_multitemporal(mti, loader=loader)

    def test_missing_band_error_mentions_frame_index(self):
        """Error message should identify which frame has the missing band."""
        loader, mti = _make_loader_and_mti(missing_band="B11")
        with pytest.raises(PrithviPreprocessingError, match="Frame 0"):
            preprocess_multitemporal(mti, loader=loader)


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Wrong frame count
# ─────────────────────────────────────────────────────────────────────────────

class TestWrongFrameCount:
    """
    MultiTemporalInput enforces exactly 4 frames at the Pydantic level.
    We test that the preprocessor also rejects correctly if somehow bypassed.
    """

    def _mti_with_n_frames(self, n: int) -> tuple[BandAssetLoader, MultiTemporalInput]:
        """Build a loader + MTI with n frames (valid date strings)."""
        all_dates = [
            "2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01",
        ]
        return _make_loader_and_mti(dates=all_dates[:n])

    def test_pydantic_rejects_3_frames(self):
        """MultiTemporalInput itself must reject fewer than 4 frames."""
        with pytest.raises(Exception):
            _, _ = self._mti_with_n_frames(3)

    def test_pydantic_rejects_5_frames(self):
        """MultiTemporalInput itself must reject more than 4 frames."""
        with pytest.raises(Exception):
            _, _ = self._mti_with_n_frames(5)

    def test_preprocessor_rejects_wrong_count_directly(self):
        """
        Even if somehow called with wrong count (bypassing Pydantic),
        the preprocessor must raise PrithviPreprocessingError.
        """
        loader, mti = _make_loader_and_mti()
        # Manually alter frames list to 3 elements (bypass Pydantic)
        mti_dict = mti.model_dump()
        mti_dict["frames"] = mti_dict["frames"][:3]

        # Re-construct via model_construct to bypass validation
        bad_mti = MultiTemporalInput.model_construct(**mti_dict)
        bad_mti.frames = mti.frames[:3]  # type: ignore[assignment]

        with pytest.raises(PrithviPreprocessingError, match="exactly 4"):
            preprocess_multitemporal(bad_mti, loader=loader)


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Spatial alignment (resampling)
# ─────────────────────────────────────────────────────────────────────────────

class TestSpatialAlignment:
    """
    Bands with different input sizes must all be resampled to 224x224.
    The preprocessor should still produce (4, 6, 224, 224).
    """

    def test_different_band_sizes_yield_correct_output_shape(self):
        """
        Some bands at 128x128 (20m equivalent), others at 256x256 (10m equivalent).
        Output must still be (4, 6, 224, 224).
        """
        loader = BandAssetLoader()
        frames: list[TemporalFrame] = []

        for date in DATES_CHRONOLOGICAL:
            band_urls: dict[str, str] = {}
            for band_name in PRITHVI_BAND_ORDER:
                # 10m bands (B02, B03, B04): 256x256
                # 20m bands (B08A, B11, B12): 128x128
                if band_name in ("B02", "B03", "B04"):
                    h_band, w_band = 256, 256
                else:
                    h_band, w_band = 128, 128

                url = f"mock://spatial/{date}/{band_name}.tif"
                arr = np.full(
                    (h_band, w_band),
                    BAND_CONSTANTS[band_name],
                    dtype=np.float32,
                )
                loader.register(url, arr)
                band_urls[band_name] = url

            frames.append(TemporalFrame(
                acquisition_date=date,
                bands=SpectralBands(**band_urls),
            ))

        mti = MultiTemporalInput(
            frames=frames,
            bbox=[77.5, 29.0, 80.5, 31.5],
            query="Spatial alignment test",
        )
        result = preprocess_multitemporal(mti, loader=loader)

        assert result.array.shape == (4, 6, 224, 224), (
            f"Expected (4,6,224,224) after resampling, got {result.array.shape}"
        )

    def test_resampling_occurred_flag_set(self):
        """resampling_occurred must be True when input bands differ from target size."""
        loader = BandAssetLoader()
        frames: list[TemporalFrame] = []
        for date in DATES_CHRONOLOGICAL:
            band_urls: dict[str, str] = {}
            for band_name in PRITHVI_BAND_ORDER:
                url = f"mock://resample/{date}/{band_name}.tif"
                arr = np.full((100, 100), BAND_CONSTANTS[band_name], dtype=np.float32)
                loader.register(url, arr)
                band_urls[band_name] = url
            frames.append(TemporalFrame(
                acquisition_date=date,
                bands=SpectralBands(**band_urls),
            ))

        mti = MultiTemporalInput(
            frames=frames,
            bbox=[77.5, 29.0, 80.5, 31.5],
            query="Resampling flag test",
        )
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.resampling_occurred is True

    def test_no_resampling_when_already_224(self):
        """resampling_occurred must be False when bands are already 224x224."""
        loader, mti = _make_loader_and_mti(h=224, w=224)
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.resampling_occurred is False

    def test_helper_crop_larger_array(self):
        """_crop_or_pad: larger input must be centrally cropped to target."""
        arr = np.arange(300 * 300, dtype=np.float32).reshape(300, 300)
        out = _crop_or_pad(arr, 224, 224)
        assert out.shape == (224, 224)

    def test_helper_pad_smaller_array(self):
        """_crop_or_pad: smaller input must be zero-padded to target."""
        arr = np.ones((100, 100), dtype=np.float32)
        out = _crop_or_pad(arr, 224, 224)
        assert out.shape == (224, 224)
        # Corners should be zero-padded
        assert out[0, 0] == 0.0

    def test_helper_resample_zooms_correctly(self):
        """_resample_to_target: output shape matches (target_h, target_w)."""
        arr = np.ones((128, 128), dtype=np.float32)
        out = _resample_to_target(arr, 224, 224)
        assert out.shape == (224, 224)

    def test_helper_no_op_when_already_correct_size(self):
        """_resample_to_target: returns same object when dimensions already match."""
        arr = np.ones((224, 224), dtype=np.float32)
        out = _resample_to_target(arr, 224, 224)
        assert out is arr  # should be the exact same object


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — Non-finite data
# ─────────────────────────────────────────────────────────────────────────────

class TestNonFiniteData:
    """Preprocessing must reject arrays containing NaN or Inf."""

    def _make_nan_mti(self, bad_value: float) -> tuple[BandAssetLoader, MultiTemporalInput]:
        """Create a loader where B02 in frame 0 has one bad pixel."""
        loader = BandAssetLoader()
        frames: list[TemporalFrame] = []

        for i, date in enumerate(DATES_CHRONOLOGICAL):
            band_urls: dict[str, str] = {}
            for band_name in PRITHVI_BAND_ORDER:
                url = f"mock://nonfinite/{date}/{band_name}.tif"
                arr = np.full((H, W), BAND_CONSTANTS[band_name], dtype=np.float32)
                # Inject bad value into B02 of frame 0 only
                if i == 0 and band_name == "B02":
                    arr[50, 50] = bad_value
                loader.register(url, arr)
                band_urls[band_name] = url

            frames.append(TemporalFrame(
                acquisition_date=date,
                bands=SpectralBands(**band_urls),
            ))

        mti = MultiTemporalInput(
            frames=frames,
            bbox=[77.5, 29.0, 80.5, 31.5],
            query="Non-finite test",
        )
        return loader, mti

    def test_nan_raises_preprocessing_error(self):
        loader, mti = self._make_nan_mti(float("nan"))
        with pytest.raises(PrithviPreprocessingError):
            preprocess_multitemporal(mti, loader=loader)

    def test_inf_raises_preprocessing_error(self):
        loader, mti = self._make_nan_mti(float("inf"))
        with pytest.raises(PrithviPreprocessingError):
            preprocess_multitemporal(mti, loader=loader)

    def test_negative_inf_raises_preprocessing_error(self):
        loader, mti = self._make_nan_mti(float("-inf"))
        with pytest.raises(PrithviPreprocessingError):
            preprocess_multitemporal(mti, loader=loader)

    def test_error_mentions_non_finite(self):
        loader, mti = self._make_nan_mti(float("nan"))
        with pytest.raises(PrithviPreprocessingError, match="non-finite"):
            preprocess_multitemporal(mti, loader=loader)


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 — MultiTemporalInput compatibility (full pipeline)
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiTemporalInputCompatibility:
    """
    Verify the complete pipeline:
        MultiTemporalInput (from Step 2 mock acquisition)
             |
        preprocess_multitemporal()
             |
        (4, 6, 224, 224) float32 array
    """

    def test_full_pipeline_from_step2_acquisition(self):
        """
        Simulate what Step 2 acquisition produces and pass it through the
        preprocessor.  Uses the same URL patterns as the mock acquisition layer.
        """
        from app.tools.fetch_multitemporal_sentinel2 import FetchMultitemporalSentinel2Tool
        from app.schemas.requests import MultiTemporalInput

        # --- Step 2: acquire 4 frames via mock tool --------------------------
        tool = FetchMultitemporalSentinel2Tool()
        result = tool.execute({
            "bbox": [77.5, 29.0, 80.5, 31.5],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None, f"Step 2 acquisition failed: {result.error}"
        mti = MultiTemporalInput(**result.artifacts[0])

        # --- Step 3A: prepare a loader for mock:// URLs ----------------------
        loader = BandAssetLoader()
        for frame in mti.frames:
            for band_name in PRITHVI_BAND_ORDER:
                url = getattr(frame.bands, band_name)
                assert url is not None, f"Missing band {band_name} in Step 2 output"
                assert url.startswith("mock://")
                # Register a synthetic array for each mock URL
                arr = np.full(
                    (H, W),
                    BAND_CONSTANTS[band_name],
                    dtype=np.float32,
                )
                loader.register(url, arr)

        # --- Preprocess -------------------------------------------------------
        pp_result = preprocess_multitemporal(mti, loader=loader)

        assert pp_result.array.shape == (4, 6, 224, 224)
        assert pp_result.array.dtype == np.float32

    def test_result_summary_is_json_serializable(self):
        """PrithviPreprocessingResult.summary() must return a plain dict."""
        import json
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        summary = result.summary()
        # Must not raise
        serialized = json.dumps(summary)
        assert '"shape"' in serialized
        assert '"band_order"' in serialized
        assert '"frame_dates"' in serialized

    def test_resolution_metadata(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.resolution_m == PRITHVI_TARGET_RESOLUTION_M

    def test_spatial_size_metadata(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.spatial_size == PRITHVI_SPATIAL_SIZE

    def test_band_order_is_prithvi_band_order(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(mti, loader=loader)
        assert result.band_order == PRITHVI_BAND_ORDER

    def test_no_model_loading_occurs(self):
        """
        Sanity check: preprocessing must not import TerraTorch, Transformers,
        or attempt to load model weights.
        """
        import sys
        loader, mti = _make_loader_and_mti()
        preprocess_multitemporal(mti, loader=loader)
        for forbidden in ("torch", "transformers", "terratorch", "timm"):
            assert forbidden not in sys.modules, (
                f"Module '{forbidden}' was unexpectedly imported during preprocessing."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Step 3A.1 Tests: Band Mapping, Spatial Resolution vs Model Size, Geospatial Resampling
# ─────────────────────────────────────────────────────────────────────────────

class TestStep3A1BandMappingAndSemantics:
    """
    Test A: Verify the Sentinel-2 native -> Prithvi/HLS channel mapping:
        channel 0 -> S2 B02  -> Prithvi B02
        channel 1 -> S2 B03  -> Prithvi B03
        channel 2 -> S2 B04  -> Prithvi B04
        channel 3 -> S2 B08A -> Prithvi B05
        channel 4 -> S2 B11  -> Prithvi B06
        channel 5 -> S2 B12  -> Prithvi B07
    """

    def test_s2_to_prithvi_band_mapping(self):
        assert PRITHVI_MODEL_BANDS == ["B02", "B03", "B04", "B05", "B06", "B07"]
        assert S2_TO_PRITHVI_BAND_MAP["B02"] == "B02"
        assert S2_TO_PRITHVI_BAND_MAP["B03"] == "B03"
        assert S2_TO_PRITHVI_BAND_MAP["B04"] == "B04"
        assert S2_TO_PRITHVI_BAND_MAP["B08A"] == "B05"
        assert S2_TO_PRITHVI_BAND_MAP["B11"] == "B06"
        assert S2_TO_PRITHVI_BAND_MAP["B12"] == "B07"

    def test_channel_indices_match_prithvi_bands(self):
        for idx, s2_band in enumerate(PRITHVI_BAND_ORDER):
            expected_model_band = PRITHVI_MODEL_BANDS[idx]
            assert S2_TO_PRITHVI_BAND_MAP[s2_band] == expected_model_band


class TestStep3A1ModelSizeVsResolution:
    """
    Test B: Verify that target ground sampling distance (resolution_m = 30.0)
    and model spatial input dimensions (spatial_size = 224) are distinct properties.
    """

    def test_resolution_and_spatial_size_are_distinct(self):
        loader, mti = _make_loader_and_mti()
        result = preprocess_multitemporal(
            mti,
            loader=loader,
            target_h=224,
            target_w=224,
            target_resolution_m=30.0,
        )
        assert result.resolution_m == 30.0
        assert result.spatial_size == 224
        assert result.shape[2:] == (224, 224)

        # Verify custom resolution and custom model dimensions are decoupled
        custom_result = preprocess_multitemporal(
            mti,
            loader=loader,
            target_h=112,
            target_w=112,
            target_resolution_m=15.0,
        )
        assert custom_result.resolution_m == 15.0
        assert custom_result.spatial_size == 112
        assert custom_result.shape[2:] == (112, 112)


class TestStep3A1GeospatialResampling:
    """
    Test C: Real geospatial resampling to 30 m grid using rasterio & affine metadata.
    Create a small synthetic raster with actual raster metadata:
    CRS ('EPSG:32632'), transform (10 m native resolution).
    Verify preprocessing places it onto a 30 m grid using geospatial resampling.
    """

    def test_geospatial_resampling_to_30m_grid(self):
        from affine import Affine

        loader = BandAssetLoader()
        # 10 m resolution transform: origin at (500000, 4000000), 10m pixel size
        # 300x300 pixels at 10m = 3000m x 3000m
        crs_str = "EPSG:32632"
        native_res = 10.0
        h_10m, w_10m = 300, 300
        transform_10m = Affine.translation(500000, 4000000) @ Affine.scale(native_res, -native_res)

        frames: list[TemporalFrame] = []
        for date in DATES_CHRONOLOGICAL:
            band_urls: dict[str, str] = {}
            for band_name in PRITHVI_BAND_ORDER:
                url = f"mock://geo/{date}/{band_name}.tif"
                arr = np.full((h_10m, w_10m), BAND_CONSTANTS[band_name], dtype=np.float32)
                loader.register(
                    url,
                    arr,
                    crs=crs_str,
                    transform=transform_10m,
                    resolution=native_res,
                )
                band_urls[band_name] = url
            frames.append(TemporalFrame(acquisition_date=date, bands=SpectralBands(**band_urls)))

        mti = MultiTemporalInput(
            frames=frames,
            bbox=[77.5, 29.0, 80.5, 31.5],
            query="Geospatial test",
        )

        result = preprocess_multitemporal(mti, loader=loader)
        assert result.crs == crs_str
        assert result.transform is not None
        assert result.resolution_m == 30.0
        assert result.spatial_size == 224
        assert result.shape == (4, 6, 224, 224)
        assert result.array.dtype == np.float32


class TestStep3A1SpatialCropAndPad:
    """
    Test D & E: Verify central crop (Test D) and spatial padding (Test E)
    after obtaining the 30 m grid.
    """

    def test_spatial_crop_larger_grid_to_224(self):
        """Test D: If 30 m grid is larger than 224x224 (e.g. 300x300), central crop produces 224x224."""
        arr = np.arange(300 * 300, dtype=np.float32).reshape(300, 300)
        cropped = _crop_or_pad(arr, 224, 224)
        assert cropped.shape == (224, 224)
        # Verify central crop indices: (300 - 224) // 2 = 38
        assert cropped[0, 0] == arr[38, 38]

    def test_spatial_padding_smaller_grid_to_224(self):
        """Test E: If 30 m grid is smaller than 224x224 (e.g. 100x100), deterministic padding produces 224x224."""
        arr = np.ones((100, 100), dtype=np.float32)
        padded = _crop_or_pad(arr, 224, 224)
        assert padded.shape == (224, 224)
        # Pad margins: (224 - 100) // 2 = 62 on top/left
        assert padded[0, 0] == 0.0
        assert padded[61, 61] == 0.0
        assert padded[62, 62] == 1.0
        assert padded[161, 161] == 1.0
        assert padded[162, 162] == 0.0

