"""Automated Scientific Invariant & Pipeline Verification Test Suite (Phase 6).

Covers all mandatory test invariants specified in `Project.md` and `dev_rules.md`:
  1. Linear-power averaging vs. dB averaging inequality (Rule 4 / Jensen's inequality)
     and strict rejection of dB (negative) inputs in linear-power functions.
  2. Log-ratio equivalence: 10*log10(P2 / P1) == dB(P2) - dB(P1) within tolerance.
  3. Zero, negative, NaN, and fill-value handling before log10 (zero runtime warnings).
  4. Speckle filter (3x3 Adaptive Lee & Boxcar) increases ENL on a synthetic homogeneous
     speckled patch while preserving mean linear power within tolerance.
  5. CRS, grid transform, track/frame, orbit direction, and product version/CRID mismatch
     guards (Rules 7 & 8) raise ValueError.
  6. GUNW unwrapped phase to LOS displacement conversion matches -(lambda / 4*pi) * dphi
     and strictly masks coherence < 0.50 or connected_components == 0 to NaN.
  7. Every exported layer in `data/web_tiles/layer_catalog.json` and `data/cogs/`
     contains all mandatory Rule 3 & Rule 5 metadata fields.
  8. Dual-pol change regime classification partitions 100% of valid pixels and FastAPI
     inspector validates bounds and returns calibrated 10-date series.

Note per Rule 1: Any synthetic arrays used solely for mathematical invariant testing in
this file are explicitly labelled `synthetic_` and seeded with `SEED = 42`.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nisar_pipeline.api_server import api_catalog, api_echo_providers, api_health, api_inspect, api_story
from nisar_pipeline.change_detection import classify_dual_pol_change, derive_change_thresholds
from nisar_pipeline.echo_assistant import detect_provider_from_key, query_echo_llm
from nisar_pipeline.guards import (
    MANDATORY_RULE3_FIELDS,
    build_rule3_metadata,
    validate_granule_pair_compatibility,
    validate_series_homogeneity,
)
from nisar_pipeline.insar import SPEED_OF_LIGHT_M_S, compute_los_displacement_m
from nisar_pipeline.radiometry import (
    assert_linear_power,
    boxcar_filter_linear,
    compute_empirical_enl,
    db_to_linear,
    lee_filter_linear,
    linear_to_db,
    log_ratio_db,
)

SEED = 42


def test_invariant_1_linear_vs_db_averaging_and_guard() -> None:
    """Invariant 1: Averaging in linear power then converting to dB != averaging in dB (Rule 4)."""
    rng = np.random.default_rng(SEED)
    # Explicitly labelled synthetic 4-look Gamma-distributed linear power patch (mean = 0.05 m^2/m^2)
    synthetic_looks = 4.0
    synthetic_mean_power = 0.05
    synthetic_linear_patch = rng.gamma(
        shape=synthetic_looks,
        scale=synthetic_mean_power / synthetic_looks,
        size=(128, 128),
    ).astype(np.float32)

    # Correct physical order: average in linear power, then convert to dB
    mean_linear_then_db = float(linear_to_db(np.array([np.mean(synthetic_linear_patch)], dtype=np.float32))[0])

    # Incorrect order: convert each pixel to dB first, then average in dB
    mean_of_db = float(np.mean(linear_to_db(synthetic_linear_patch)))

    # By Jensen's inequality for concave log10, E[10*log10(P)] < 10*log10(E[P])
    assert mean_linear_then_db > mean_of_db, "Linear-first dB must strictly exceed dB-averaged value."
    bias_db = mean_linear_then_db - mean_of_db
    assert bias_db > 0.45, f"Expected substantial positive Jensen bias (>0.45 dB for L=4), got {bias_db:.4f} dB"

    # Verify round-trip linear -> dB -> linear
    reconstructed_linear = db_to_linear(linear_to_db(synthetic_linear_patch))
    np.testing.assert_allclose(reconstructed_linear, synthetic_linear_patch, rtol=1e-5, atol=1e-7)

    # Verify Rule 4 guard rejects negative (dB) arrays passed into linear-power routines
    synthetic_db_array = np.array([[-18.5, -12.3], [-22.1, -9.4]], dtype=np.float32)
    with pytest.raises(ValueError, match="Rule 4 Violation"):
        assert_linear_power(synthetic_db_array)
    with pytest.raises(ValueError, match="Rule 4 Violation"):
        lee_filter_linear(synthetic_db_array)
    with pytest.raises(ValueError, match="Rule 4 Violation"):
        boxcar_filter_linear(synthetic_db_array)


def test_invariant_2_log_ratio_db_equivalence() -> None:
    """Invariant 2: Log-ratio in dB equals 10*log10(P2 / P1) == dB(P2) - dB(P1) within tolerance."""
    rng = np.random.default_rng(SEED)
    synthetic_p1 = rng.uniform(0.002, 0.25, size=(64, 64)).astype(np.float32)
    synthetic_p2 = rng.uniform(0.002, 0.25, size=(64, 64)).astype(np.float32)

    delta_via_log_ratio = log_ratio_db(synthetic_p1, synthetic_p2)
    delta_via_db_diff = linear_to_db(synthetic_p2) - linear_to_db(synthetic_p1)
    delta_exact_formula = (10.0 * np.log10(synthetic_p2 / synthetic_p1)).astype(np.float32)

    np.testing.assert_allclose(delta_via_log_ratio, delta_via_db_diff, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(delta_via_log_ratio, delta_exact_formula, rtol=1e-6, atol=1e-6)


def test_invariant_3_zero_negative_nan_fill_handling_without_warnings() -> None:
    """Invariant 3: Zeros, NaNs, and masked fill values map to NaN before log10 without warnings."""
    # Array containing valid positive power, exact zero, and NaN
    synthetic_power = np.array(
        [
            [0.0, 0.01, np.nan],
            [0.10, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        db_out = linear_to_db(synthetic_power)
        ratio_out = log_ratio_db(synthetic_power, synthetic_power[::-1, ::-1])

    assert len(caught_warnings) == 0, f"Unexpected runtime warnings during log10: {caught_warnings}"

    # Zeros and NaNs must become NaN, never -inf
    assert np.isnan(db_out[0, 0])
    assert np.isnan(db_out[0, 2])
    assert np.isnan(db_out[1, 1])
    assert np.all(np.isfinite(db_out[[0, 1, 1], [1, 0, 2]]))
    assert pytest.approx(float(db_out[0, 1]), abs=1e-5) == -20.0
    assert pytest.approx(float(db_out[1, 0]), abs=1e-5) == -10.0
    assert pytest.approx(float(db_out[1, 2]), abs=1e-5) == 0.0

    # In ratio_out, any pixel where P1==0, P2==0, or NaN must be NaN
    assert not np.any(np.isinf(ratio_out))
    assert np.isnan(ratio_out[0, 0])

    # Unmasked negative fill value (-9999.0) must trigger the Rule 4 negative-power guard
    synthetic_unmasked_fill = np.array([[0.05, -9999.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="Rule 4 Violation"):
        linear_to_db(synthetic_unmasked_fill)


def test_invariant_4_speckle_filter_increases_enl_and_preserves_mean_power() -> None:
    """Invariant 4: 3x3 Adaptive Lee & Boxcar filters increase ENL while preserving mean linear power."""
    rng = np.random.default_rng(SEED)
    # Synthetic homogeneous distributed target with prior ENL = 32 looks and mean = 0.04 m^2/m^2
    enl_prior = 32.0
    true_mean = 0.04
    synthetic_homogeneous_patch = rng.gamma(
        shape=enl_prior,
        scale=true_mean / enl_prior,
        size=(200, 200),
    ).astype(np.float32)

    raw_stats = compute_empirical_enl(synthetic_homogeneous_patch)
    lee_filtered = lee_filter_linear(synthetic_homogeneous_patch, window_size=3, enl_prior=enl_prior)
    box_filtered = boxcar_filter_linear(synthetic_homogeneous_patch, window_size=3)

    lee_stats = compute_empirical_enl(lee_filtered)
    box_stats = compute_empirical_enl(box_filtered)

    # ENL must increase substantially after 3x3 filtering
    assert lee_stats["enl"] > raw_stats["enl"] * 2.5, (
        f"Lee filter failed to increase ENL sufficiently: {raw_stats['enl']} -> {lee_stats['enl']}"
    )
    assert box_stats["enl"] > raw_stats["enl"] * 4.0, (
        f"Boxcar filter failed to increase ENL sufficiently: {raw_stats['enl']} -> {box_stats['enl']}"
    )

    # Mean linear power must be preserved within 0.2%
    assert pytest.approx(lee_stats["mean_linear"], rel=2e-3) == raw_stats["mean_linear"]
    assert pytest.approx(box_stats["mean_linear"], rel=2e-3) == raw_stats["mean_linear"]

    # Two-date speckle std in dB must decrease correspondingly
    assert lee_stats["two_date_diff_speckle_std_db"] < raw_stats["two_date_diff_speckle_std_db"]


def test_invariant_5_crs_grid_geometry_and_version_mismatch_guards() -> None:
    """Invariant 5: CRS, affine grid, orbit geometry, and CRID/version mismatches raise ValueError."""
    base_rec = {
        "granule_id": "NISAR_L2_PR_GCOV_013_129_A_016_4005_DHDH_A_20260623_P05023_001",
        "product_type": "L2_GCOV",
        "crid": "P05023",
        "product_version": "PROVISIONAL R05.02.3",
        "track": 129,
        "frame": 16,
        "orbit_direction": "Ascending",
        "epsg": 32636,
        "utm_bounds": [240160.0, 3214560.0, 318880.0, 3276960.0],
        "multilook_window_shape_40m": [1560, 1968],
    }

    # Identical geometry/version passes cleanly
    rec_valid_t2 = dict(
        base_rec,
        granule_id="NISAR_L2_PR_GCOV_014_129_A_016_4005_DHDH_A_20260810_P05023_001",
    )
    validate_granule_pair_compatibility(base_rec, rec_valid_t2)
    validate_series_homogeneity([base_rec, rec_valid_t2])

    # 1. CRS mismatch (EPSG:32636 vs EPSG:32635)
    with pytest.raises(ValueError, match="CRS EPSG Code"):
        validate_granule_pair_compatibility(base_rec, dict(rec_valid_t2, epsg=32635))

    # 2. Affine / UTM bounding box mismatch
    with pytest.raises(ValueError, match="UTM Bounding Box"):
        validate_granule_pair_compatibility(
            base_rec,
            dict(rec_valid_t2, utm_bounds=[240200.0, 3214560.0, 318880.0, 3276960.0]),
        )

    # 3. Pixel grid shape mismatch
    with pytest.raises(ValueError, match="Grid Dimensions"):
        validate_granule_pair_compatibility(
            base_rec,
            dict(rec_valid_t2, multilook_window_shape_40m=[1560, 1960]),
        )

    # 4. Product maturity / CRID mismatch (Rule 7: BETA B04010 vs PROVISIONAL P05023)
    with pytest.raises(ValueError, match="CRID"):
        validate_granule_pair_compatibility(base_rec, dict(rec_valid_t2, crid="B04010"))

    # 5. Relative orbit track or pass direction mismatch (Rule 8)
    with pytest.raises(ValueError, match="Relative Orbit Track"):
        validate_granule_pair_compatibility(base_rec, dict(rec_valid_t2, track=56))
    with pytest.raises(ValueError, match="Orbit Pass Direction"):
        validate_granule_pair_compatibility(base_rec, dict(rec_valid_t2, orbit_direction="Descending"))

    # 6. Array shape mismatch in log_ratio_db
    with pytest.raises(ValueError, match="Shape mismatch"):
        log_ratio_db(np.ones((10, 10), dtype=np.float32), np.ones((10, 12), dtype=np.float32))


def test_invariant_6_gunw_phase_to_los_conversion_and_coherence_mask() -> None:
    """Invariant 6: GUNW phase-to-LOS matches -(lambda / 4*pi) * dphi and masks gamma < 0.50."""
    # Test with nominal NISAR L-band frequency 1.2575 GHz (lambda ~ 0.238403545 m)
    wavelength_m = SPEED_OF_LIGHT_M_S / 1.2575e9
    assert pytest.approx(wavelength_m, rel=1e-6) == 0.238403545

    h, w = 20, 20
    # Reference patch around (10, 10) has unwrapped phase = 0.0 rad and ionosphere = 0.0 rad
    synthetic_unwrapped_phase = np.zeros((h, w), dtype=np.float32)
    synthetic_ionosphere = np.zeros((h, w), dtype=np.float32)
    synthetic_coherence = np.full((h, w), 0.85, dtype=np.float32)
    synthetic_conn_comp = np.ones((h, w), dtype=np.uint8)

    # Set pixel (2, 2) to +4*pi radians -> expected LOS displacement = -wavelength_m
    synthetic_unwrapped_phase[2, 2] = float(4.0 * np.pi)
    # Set pixel (3, 3) to +pi radians with +0.2*pi ionosphere -> net +0.8*pi rad
    synthetic_unwrapped_phase[3, 3] = float(np.pi)
    synthetic_ionosphere[3, 3] = float(0.2 * np.pi)
    # Set row 0 to low coherence (< 0.50) and row 1 to connected_components == 0
    synthetic_coherence[0, :] = 0.32
    synthetic_conn_comp[1, :] = 0

    los_m, stats = compute_los_displacement_m(
        unwrapped_phase_rad=synthetic_unwrapped_phase,
        coherence_mag=synthetic_coherence,
        ionosphere_phase_rad=synthetic_ionosphere,
        connected_components=synthetic_conn_comp,
        wavelength_m=wavelength_m,
        coherence_threshold=0.50,
        ref_row_col=(10, 10),
        ref_window_halfwidth=1,
    )

    # Reference pixel must have 0.0 m LOS displacement
    assert pytest.approx(float(los_m[10, 10]), abs=1e-7) == 0.0
    # Pixel (2, 2) with dphi = +4*pi must equal -wavelength_m
    assert pytest.approx(float(los_m[2, 2]), rel=1e-5) == -wavelength_m
    # Pixel (3, 3) with net dphi = +0.8*pi must equal -(wavelength_m / (4*pi)) * (0.8*pi) = -0.2 * wavelength_m
    assert pytest.approx(float(los_m[3, 3]), rel=1e-5) == -0.2 * wavelength_m

    # Low coherence (< 0.50) and connected_components == 0 must be strictly masked to NaN
    assert np.all(np.isnan(los_m[0, :]))
    assert np.all(np.isnan(los_m[1, :]))
    assert stats["valid_coherent_pixel_count"] == (h - 2) * w


def test_invariant_7_exported_catalog_and_cogs_have_all_rule3_and_rule5_metadata() -> None:
    """Invariant 7: Every exported layer in layer_catalog.json and data/cogs/ has all Rule 3 & Rule 5 fields."""
    catalog_path = PROJECT_ROOT / "data" / "web_tiles" / "layer_catalog.json"
    assert catalog_path.exists(), "Master layer_catalog.json is missing."
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    layers = catalog.get("overlays", [])
    assert len(layers) == 59, f"Expected 59 web overlay layers in catalog, found {len(layers)}"

    for layer in layers:
        layer_id = layer.get("layer_id")
        r3 = layer.get("rule3_metadata", {})
        for field in MANDATORY_RULE3_FIELDS:
            assert field in r3 and str(r3[field]).strip() != "", (
                f"Layer `{layer_id}` is missing mandatory Rule 3 field `{field}`"
            )
        # Also verify overlay PNG exists on disk
        png_rel = layer["url"].lstrip("/")
        png_path = PROJECT_ROOT / "data" / "web_tiles" / png_rel.replace("tiles/", "", 1)
        assert png_path.exists(), f"Overlay PNG missing on disk for `{layer_id}`: {png_path}"

    # Verify all 45 Cloud-Optimized GeoTIFFs on disk have 256x256 tiling, overviews, and Rule 3 tags
    cog_files = sorted((PROJECT_ROOT / "data" / "cogs").rglob("*.tif"))
    assert len(cog_files) == 45, f"Expected 45 COGs in data/cogs/, found {len(cog_files)}"
    for cog_path in cog_files:
        with rasterio.open(cog_path) as src:
            assert src.profile.get("tiled") is True, f"COG `{cog_path.name}` is not internally tiled."
            assert src.block_shapes[0] == (256, 256), f"Unexpected block shape in `{cog_path.name}`"
            assert src.overviews(1) == [2, 4, 8], f"Missing [2, 4, 8] overviews in `{cog_path.name}`"
            tags = src.tags()
            for field in MANDATORY_RULE3_FIELDS:
                assert field in tags and str(tags[field]).strip() != "", (
                    f"COG `{cog_path.name}` missing Rule 3 GDAL tag `{field}`"
                )

    # Verify build_rule3_metadata rejects invalid epistemic tags or missing fields
    with pytest.raises(ValueError, match="Invalid epistemic_tag"):
        build_rule3_metadata(
            product_type="L2_GCOV",
            product_version="PROVISIONAL R05.02.3",
            acquisition_date="2026-08-10",
            track=129,
            frame=16,
            orbit_direction="Ascending",
            polarization="HH",
            units="dB (10*log10 gamma0)",
            crs="EPSG:32636",
            source="ASF DAAC",
            epistemic_tag="FORECAST_SCORE",
        )


def test_invariant_8_dual_pol_regime_partition_and_fastapi_inspector() -> None:
    """Invariant 8: Dual-pol regime classification sums to 100% of valid pixels & API validates bounds."""
    synthetic_dhh = np.array(
        [
            [0.5, 4.2, -3.8, 3.5],
            [0.2, 1.0, 4.1, -3.9],
        ],
        dtype=np.float32,
    )
    synthetic_dhv = np.array(
        [
            [-0.4, 3.1, -2.9, -2.8],
            [2.9, -2.5, 0.3, -0.2],
        ],
        dtype=np.float32,
    )
    valid_mask = np.ones_like(synthetic_dhh, dtype=bool)
    regime_map, summary = classify_dual_pol_change(
        delta_hh_db=synthetic_dhh,
        delta_hv_db=synthetic_dhv,
        tau_hh_db=2.73,
        tau_hv_db=2.03,
        valid_mask=valid_mask,
    )
    assert summary["valid_evaluated_pixels"] == 8
    total_classified = sum(v["pixel_count"] for v in summary["regime_breakdown"].values())
    assert total_classified == summary["valid_evaluated_pixels"]
    # Verify specific regimes (0..6):
    # (0, 0) -> Within noise (0), (0, 1) -> Canopy growth (1), (0, 2) -> Canopy harvest (2),
    # (0, 3) -> Opposite-Sign Disagreement Type I (+HH & -HV = 5),
    # (1, 2) -> Surface Wetting (+HH only = 3), (1, 3) -> Surface Drying (-HH only = 4)
    assert int(regime_map[0, 0]) == 0
    assert int(regime_map[0, 1]) == 1
    assert int(regime_map[0, 2]) == 2
    assert int(regime_map[0, 3]) == 5
    assert int(regime_map[1, 2]) == 3
    assert int(regime_map[1, 3]) == 4

    # Verify FastAPI endpoints and out-of-bounds error handling
    health = api_health()
    assert health["status"] == "ok"
    assert health["cube_shape_t_y_x"] == [10, 1560, 1968]

    cat = api_catalog()
    assert cat["overlay_count"] == 59

    story = api_story()
    assert "phase3_change_and_timeseries" in story

    # Valid coordinate inside Fayoum Oasis returns 10 dates
    insp = api_inspect(lon=30.9806, lat=29.3201, utm_x=None, utm_y=None, window_px=5)
    assert insp["sampling"]["temporal_sample_count_N_dates"] == 10
    assert len(insp["timeseries"]) == 10

    # Out-of-bounds coordinate raises HTTPException(400)
    with pytest.raises(HTTPException) as exc_info:
        api_inspect(lon=35.0, lat=31.0, utm_x=None, utm_y=None, window_px=5)
    assert exc_info.value.status_code == 400


def test_invariant_9_echo_ai_helper_providers_and_no_fabricated_fallback() -> None:
    """Invariant 9: Echo AI Helper exposes multi-provider catalog, auto-detects key prefixes, and never fabricates."""
    prov_resp = api_echo_providers()
    prov_ids = [p["id"] for p in prov_resp["providers"]]
    for expected in ("gemini", "groq", "openrouter", "openai", "anthropic", "deepseek", "mistral", "ollama"):
        assert expected in prov_ids

    # Key prefix auto-detection
    assert detect_provider_from_key("AIzaSyDummyKey123", "openai") == "gemini"
    assert detect_provider_from_key("gsk_DummyGroqKey123", "gemini") == "groq"
    assert detect_provider_from_key("sk-or-v1-DummyKey", "gemini") == "openrouter"
    assert detect_provider_from_key("sk-ant-api03-Dummy", "openai") == "anthropic"

    # Rule 1 (No Fabricated Fallbacks): when no key is available, returns explicit is_error=True, needs_api_key=True
    if not prov_resp["env_configured_providers"]:
        res = query_echo_llm(
            provider="gemini",
            model="gemini-2.5-flash",
            api_key="",
            messages=[{"role": "user", "content": "What is displayed on the map?"}],
            ui_context={"map_mode": "single", "active_layer_title": "NISAR Dual-Pol RGB Composite"},
        )
        assert res["is_error"] is True
        assert res["needs_api_key"] is True

