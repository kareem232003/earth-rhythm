"""Phase 5: Explainable Next-Pass (+12 Day) Flood Susceptibility & Crop Backscatter Forecasting Engine.

Builds, audits, and validates a physics-informed, explainable geospatial forecasting system using real NASA datasets:
  1. NISAR L2_GCOV 10-date calibrated HH & HV backscatter cube (2026-06-23 .. 2026-10-21, Track 129, Frame 016)
  2. NISAR L2_GUNW 9-pair sequential interferometric coherence (gamma_HH)
  3. NASA JPL OPERA DSWx-HLS v1.0 optical surface water & partial-water benchmark masks (independent validation)
  4. NASA NISAR_WATERMASK v0.5.0 & NASA NISAR_DEM v1.2 (with WGS84 ellipsoidal-to-EGM2008 orthometric MSL datum correction)
  5. ESA Sentinel-2 L2A optical NDVI time series (independent contextual evidence for agricultural ROIs)

Scientific & ML Validation Protocol:
  - Strict Temporal Separation (No Leakage):
      * Backtesting: Calibrate strictly on Passes 1..9 (2026-06-23 .. 2026-10-09) and predict Held-Out Pass 10 (2026-10-21).
      * Rolling-Origin Cross-Validation: Evaluate 1-step-ahead forecasts across Passes 7, 8, 9, and 10.
      * Spatial Block Cross-Validation: Evaluate across 4 geographic quadrants (NW, NE, SW, SE) of Fayoum Oasis.
      * Identical Hyperparameters & In-Sample Estimation: State-space filter coefficients are estimated strictly from
        historical transitions within the available input cube `seq_db` (never touching held-out future passes).
  - Ground-Truth Independence for Flood & Inundation:
      * Track A (SAR Self-Consistency Holdout): Pass 10 pure-NISAR water state (Full AOI, 1.5 km coastal buffer, and
        non-permanent dynamic shoreline margin).
      * Track B (Independent Multi-Sensor Benchmark): Independent optical NASA OPERA DSWx-HLS v1.0 water masks and
        NASA NISAR_WATERMASK v0.5.0.
  - Hydraulically Connected Drainage Surge Simulator:
      * Enforces 8-connected topographic flood-fill from permanent water bodies over Height Above Nearest Drainage (HAND)
        so isolated inland depressions cannot artificially flood without a hydraulic pathway.
  - Cloud-Optimized GeoTIFF (COG) Export:
      * Exports 4 native EPSG:32636 256x256 tiled COGs with [2, 4, 8] overview pyramids and full Rule 3 & Rule 5 GDAL tags
        in `data/cogs/predictions/` alongside 4 EPSG:4326 RGBA web overlays in `data/web_tiles/overlays/predictions/`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, label as nd_label, uniform_filter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.nisar_pipeline.change_detection import classify_dual_pol_change
from src.nisar_pipeline.guards import build_rule3_metadata
from src.nisar_pipeline.tiles_and_cogs import (
    COLORMAPS,
    DUAL_POL_REGIME_PALETTE,
    _interpolate_colormap,
    compute_pure_sar_water_mask,
    convert_geotiff_to_cog,
    reproject_array_to_wgs84,
    write_rgba_png,
)

SEED = 42
TAU_HH_DB = 2.73
TAU_HV_DB = 2.03
WATER_HH_THRESH_DB = -15.20  # Calibrated L-band specular water threshold
EGM2008_UNDULATION_FAYOUM_M = 14.20  # WGS84 ellipsoidal height minus orthometric MSL height over Fayoum Oasis
NOMINAL_REPEAT_DAYS = 12.0

FLOOD_RISK_PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 0),            # 0: Safe / Upland (< 15% susceptibility) - transparent
    1: (250, 204, 21, 185),     # 1: Low-Lying Watch (15 - 40% susceptibility) - Amber Yellow
    2: (249, 115, 22, 220),     # 2: High Susceptibility Margin (40 - 75% susceptibility) - Orange
    3: (220, 38, 38, 240),      # 3: Imminent / Active Shoreline Inundation (> 75% on non-permanent margin) - Red
    4: (14, 165, 233, 225),     # 4: Persistent Open Water (> 75% susceptibility, permanent lake) - Cyan Blue
}

REGIME_NAMES: dict[int, str] = {
    0: "Stable / Unchanged (< tau)",
    1: "Canopy Growth / Winter Crop Emergence (+HV)",
    2: "Harvest / Canopy Clearance (-HV)",
    3: "Irrigation / Soil Wetting (+HH)",
    4: "Surface Drying / Tilled Soil (-HH)",
    5: "Flooded Vegetation / Standing Water (+HH, -HV)",
    6: "Specular Inundation / Smooth Wet Margin (-HH, +HV)",
}


def linear_to_db(arr: np.ndarray) -> np.ndarray:
    """Convert positive linear gamma0 to dB safely."""
    return 10.0 * np.log10(np.maximum(arr, 1e-10))


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable logistic function."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def compute_elapsed_days(date_strs: list[str]) -> np.ndarray:
    """Compute exact elapsed days between consecutive acquisition dates (accounts for 24-day gap Jul 17 -> Aug 10)."""
    parsed = [datetime.strptime(d, "%Y-%m-%d") for d in date_strs]
    dt = np.array([(parsed[i + 1] - parsed[i]).days for i in range(len(parsed) - 1)], dtype=np.float32)
    if np.any(dt <= 0):
        raise ValueError(f"Non-monotonic acquisition dates detected: {date_strs} -> dt={dt.tolist()}")
    return dt


def compute_roc_auc_exact(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Compute exact Mann-Whitney U / Wilcoxon rank-sum ROC-AUC without external sklearn dependency."""
    y_t = y_true.astype(np.bool_).ravel()
    y_s = y_score.astype(np.float64).ravel()
    n_pos = int(np.sum(y_t))
    n_neg = int(len(y_t) - n_pos)
    if n_pos == 0 or n_neg == 0:
        raise ValueError(f"Both classes must be present for ROC-AUC (got pos={n_pos}, neg={n_neg}).")
    order = np.argsort(y_s, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(y_s) + 1, dtype=np.float64)
    pos_rank_sum = float(np.sum(ranks[y_t]))
    auc = (pos_rank_sum - (n_pos * (n_pos + 1)) / 2.0) / (float(n_pos) * float(n_neg))
    return float(auc)


def compute_reliability_curve(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> dict[str, Any]:
    """Compute 10-bin probability calibration curve and Expected Calibration Error (ECE)."""
    y_t = y_true.astype(np.float32).ravel()
    y_p = np.clip(y_prob.astype(np.float32).ravel(), 0.0, 1.0)
    n_total = len(y_t)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_records = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = float(bins[i]), float(bins[i + 1])
        if i == n_bins - 1:
            mask = (y_p >= lo) & (y_p <= hi)
        else:
            mask = (y_p >= lo) & (y_p < hi)
        cnt = int(np.sum(mask))
        if cnt > 0:
            mean_pred = float(np.mean(y_p[mask]))
            obs_freq = float(np.mean(y_t[mask]))
            abs_gap = abs(mean_pred - obs_freq)
            ece += (cnt / max(n_total, 1)) * abs_gap
        else:
            mean_pred = round(0.5 * (lo + hi), 4)
            obs_freq = 0.0
            abs_gap = 0.0
        bin_records.append(
            {
                "bin_index": i + 1,
                "bin_range": f"{lo:.1f}-{hi:.1f}",
                "pixel_count": cnt,
                "mean_predicted_prob": round(mean_pred, 4),
                "observed_event_frequency": round(obs_freq, 4),
                "calibration_gap": round(abs_gap, 4),
            }
        )
    return {
        "expected_calibration_error_ece": round(float(ece), 5),
        "bins": bin_records,
    }


def _extract_ssm_state_components(
    seq_slice: np.ndarray,
    dt_slice: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract the 4 physical spatio-temporal state components at the end of `seq_slice` (length >= 3).

    Components:
      1. `sp_innov`: High-frequency single-pixel step jump relative to 5x5 parcel jump (captures residual single-pass speckle).
      2. `d1_loc`: 5x5 parcel-scale elapsed-time normalized velocity (dB per 12 days).
      3. `anom_sp`: High-frequency single-pixel deviation from the pixel's historical median relative to 5x5 neighborhood.
      4. `anom`: Pixel deviation from its historical multi-pass median baseline (captures mean-reverting moisture/wave excursions).
    """
    yt = seq_slice[-1]
    ytm1 = seq_slice[-2]
    dt_last = float(dt_slice[-1])
    d1_norm = (yt - ytm1) * (NOMINAL_REPEAT_DAYS / max(dt_last, 1.0))
    d1_loc = uniform_filter(d1_norm, size=5)
    sp_innov = d1_norm - d1_loc

    hist_med = np.median(seq_slice, axis=0)
    anom = yt - hist_med
    anom_sp = anom - uniform_filter(anom, size=5)
    return sp_innov, d1_loc, anom_sp, anom


def _forecast_single_pol_adaptive_ssm(
    seq_db: np.ndarray,
    dt_days: np.ndarray,
    tau_db: float,
    horizon_days: float = NOMINAL_REPEAT_DAYS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Speckle-Aware Spatio-Temporal State-Space Forecaster for a single polarization cube (T, H, W).

    Strictly fits state-space innovation & reversion gains on historical transitions inside `seq_db`
    (t = 3 .. T-1) with zero look-ahead leakage, normalizing all velocities by actual elapsed days `dt_days`.
    """
    n_passes = seq_db.shape[0]
    if n_passes < 5:
        raise ValueError(f"Need at least 5 passes for state-space calibration, got {n_passes}")

    # Calibrate 4-parameter state-space gains strictly on historical transitions within seq_db (stride=25 for speed)
    x_list = []
    y_list = []
    for t in range(3, n_passes):
        sp_i, d1_l, an_sp, an_m = _extract_ssm_state_components(seq_db[:t], dt_days[: t - 1])
        dy_target_12d = (seq_db[t] - seq_db[t - 1]) * (NOMINAL_REPEAT_DAYS / max(float(dt_days[t - 1]), 1.0))
        x_list.append(
            np.stack(
                [
                    sp_i.ravel()[::25],
                    d1_l.ravel()[::25],
                    an_sp.ravel()[::25],
                    an_m.ravel()[::25],
                ],
                axis=1,
            )
        )
        y_list.append(dy_target_12d.ravel()[::25])

    x_mat = np.vstack(x_list)
    y_vec = np.concatenate(y_list)
    beta, _, _, _ = np.linalg.lstsq(x_mat, y_vec, rcond=None)

    # Apply calibrated state-space transition to current state (T-1 -> T)
    sp_innov, d1_loc, anom_sp, anom = _extract_ssm_state_components(seq_db, dt_days)
    horizon_scale = horizon_days / NOMINAL_REPEAT_DAYS
    pred_delta = (
        beta[0] * sp_innov
        + beta[1] * d1_loc
        + beta[2] * anom_sp
        + beta[3] * anom
    ) * horizon_scale
    pred = seq_db[-1] + pred_delta

    # Per-pixel 1-sigma uncertainty from time-normalized step innovations over last 5 passes
    recent_diffs = np.diff(seq_db[-5:], axis=0)
    recent_dts = dt_days[-4:][:, None, None]
    norm_innovations = recent_diffs * (NOMINAL_REPEAT_DAYS / np.maximum(recent_dts, 1.0))
    step_abs_sum = np.sum(np.abs(norm_innovations[-3:]), axis=0) + 1e-4
    net_3step = np.abs(seq_db[-1] - seq_db[-4])
    consistency = np.clip(net_3step / step_abs_sum, 0.0, 1.0)
    sigma = np.sqrt(np.mean(norm_innovations ** 2, axis=0)) * (0.65 + 0.20 * (1.0 - consistency))
    sigma = np.clip(sigma, 0.20, 4.50)

    # Confidence score (0..1) inversely related to innovation volatility and proportional to temporal consistency
    confidence = np.clip(np.exp(-sigma / max(tau_db, 1.5)) * (0.65 + 0.35 * consistency), 0.10, 0.99)
    return pred.astype(np.float32), sigma.astype(np.float32), confidence.astype(np.float32)


def forecast_backscatter_cube(
    hh_db_seq: np.ndarray,
    hv_db_seq: np.ndarray,
    dt_days: np.ndarray | None = None,
    horizon_days: float = NOMINAL_REPEAT_DAYS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Forecast next pass (T+1) HH and HV (in dB), 1-sigma uncertainties, and composite confidence (0..1)."""
    if dt_days is None:
        dt_days = np.full(hh_db_seq.shape[0] - 1, NOMINAL_REPEAT_DAYS, dtype=np.float32)
    pred_hh, sigma_hh, conf_hh = _forecast_single_pol_adaptive_ssm(
        hh_db_seq, dt_days, tau_db=TAU_HH_DB, horizon_days=horizon_days
    )
    pred_hv, sigma_hv, conf_hv = _forecast_single_pol_adaptive_ssm(
        hv_db_seq, dt_days, tau_db=TAU_HV_DB, horizon_days=horizon_days
    )
    composite_conf = (0.5 * (conf_hh + conf_hv)).astype(np.float32)
    return pred_hh, pred_hv, sigma_hh, sigma_hv, composite_conf


def forecast_baselines_cube(
    seq_db: np.ndarray,
    dt_days: np.ndarray,
    horizon_days: float = NOMINAL_REPEAT_DAYS,
) -> dict[str, np.ndarray]:
    """Compute standard forecasting baselines (Persistence, 3-Pass Moving Average, Elapsed-Time Linear OLS Trend)."""
    pred_persistence = seq_db[-1].astype(np.float32)
    pred_ma3 = np.mean(seq_db[-3:], axis=0).astype(np.float32)

    t_rel = np.concatenate([[0.0], np.cumsum(dt_days[-3:])]).astype(np.float32)
    t_mean = float(np.mean(t_rel))
    t_centered = t_rel - t_mean
    denom = float(np.sum(t_centered ** 2))
    y4 = seq_db[-4:]
    y_mean = np.mean(y4, axis=0)
    slope_per_day = np.sum(t_centered[:, None, None] * (y4 - y_mean[None, :, :]), axis=0) / max(denom, 1e-6)
    pred_linear = (y_mean + slope_per_day * (t_rel[-1] + horizon_days - t_mean)).astype(np.float32)

    return {
        "persistence_last_pass": pred_persistence,
        "moving_average_3pass": pred_ma3,
        "linear_ols_4pass": pred_linear,
    }


def compute_regression_metrics(
    pred: np.ndarray,
    actual: np.ndarray,
    veg_mask: np.ndarray,
    sigma: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute R^2, RMSE, MAE, Bias, and 1-sigma uncertainty across Full AOI and Cropland."""
    err = (pred - actual).astype(np.float64)
    act = actual.astype(np.float64)
    veg = veg_mask > 0

    rmse_aoi = float(np.sqrt(np.mean(err ** 2)))
    mae_aoi = float(np.mean(np.abs(err)))
    bias_aoi = float(np.mean(err))
    ss_res_aoi = float(np.sum(err ** 2))
    ss_tot_aoi = float(np.sum((act - np.mean(act)) ** 2))
    r2_aoi = float(1.0 - ss_res_aoi / max(ss_tot_aoi, 1e-12))

    err_veg = err[veg]
    act_veg = act[veg]
    rmse_veg = float(np.sqrt(np.mean(err_veg ** 2)))
    mae_veg = float(np.mean(np.abs(err_veg)))
    bias_veg = float(np.mean(err_veg))
    ss_res_veg = float(np.sum(err_veg ** 2))
    ss_tot_veg = float(np.sum((act_veg - np.mean(act_veg)) ** 2))
    r2_veg = float(1.0 - ss_res_veg / max(ss_tot_veg, 1e-12))

    out = {
        "rmse_db_full_aoi": round(rmse_aoi, 4),
        "mae_db_full_aoi": round(mae_aoi, 4),
        "bias_db_full_aoi": round(bias_aoi, 4),
        "r2_full_aoi": round(r2_aoi, 4),
        "rmse_db_cropland": round(rmse_veg, 4),
        "mae_db_cropland": round(mae_veg, 4),
        "bias_db_cropland": round(bias_veg, 4),
        "r2_cropland": round(r2_veg, 4),
    }
    if sigma is not None:
        out["mean_1sigma_uncertainty_db_aoi"] = round(float(np.mean(sigma)), 4)
        out["mean_1sigma_uncertainty_db_cropland"] = round(float(np.mean(sigma[veg])), 4)
        within_ci95 = float(np.mean(np.abs(err) <= 1.96 * sigma))
        out["empirical_ci95_coverage_pct"] = round(100.0 * within_ci95, 2)
    return out


def compute_multiclass_regime_metrics(
    pred_cls: np.ndarray,
    true_cls: np.ndarray,
    eval_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute 7-class Overall Accuracy, Macro F1, Weighted F1, Balanced Accuracy, Per-Class metrics, and 7x7 Confusion Matrix."""
    if eval_mask is not None:
        p = pred_cls[eval_mask].astype(np.int32).ravel()
        t = true_cls[eval_mask].astype(np.int32).ravel()
    else:
        p = pred_cls.astype(np.int32).ravel()
        t = true_cls.astype(np.int32).ravel()

    n_total = int(len(t))
    cm = np.zeros((7, 7), dtype=np.int64)
    for tc in range(7):
        t_mask = t == tc
        if np.any(t_mask):
            counts = np.bincount(p[t_mask], minlength=7)[:7]
            cm[tc, :] = counts

    assert int(np.sum(cm)) == n_total, f"7x7 confusion matrix sum {np.sum(cm)} != {n_total}"

    overall_acc = float(np.trace(cm) / max(n_total, 1))
    per_class = []
    f1_list = []
    recall_active = []
    weighted_f1_sum = 0.0

    for c in range(7):
        tp = int(cm[c, c])
        fp = int(np.sum(cm[:, c]) - tp)
        fn = int(np.sum(cm[c, :]) - tp)
        support = int(np.sum(cm[c, :]))
        pred_cnt = int(np.sum(cm[:, c]))

        prec = float(tp / max(tp + fp, 1)) if (tp + fp) > 0 else 0.0
        rec = float(tp / max(tp + fn, 1)) if (tp + fn) > 0 else 0.0
        f1 = float(2.0 * tp / max(2 * tp + fp + fn, 1)) if (2 * tp + fp + fn) > 0 else 0.0

        if support > 0:
            f1_list.append(f1)
            recall_active.append(rec)
            weighted_f1_sum += f1 * support

        per_class.append(
            {
                "regime_code": c,
                "regime_label": REGIME_NAMES[c],
                "support_px": support,
                "predicted_px": pred_cnt,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
            }
        )

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0
    weighted_f1 = float(weighted_f1_sum / max(n_total, 1))
    balanced_acc = float(np.mean(recall_active)) if recall_active else 0.0

    return {
        "evaluated_pixels": n_total,
        "overall_accuracy": round(overall_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "balanced_accuracy": round(balanced_acc, 4),
        "per_class_metrics": per_class,
        "confusion_matrix_7x7": cm.tolist(),
    }


def compute_explainable_inundation_model(
    hh_db_seq: np.ndarray,
    hv_db_seq: np.ndarray,
    coherence_stack: np.ndarray,
    dist_to_water_m: np.ndarray,
    dem_msl_m: np.ndarray,
    low_snr_sand_mask: np.ndarray,
    dt_days: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute explainable flood & shoreline inundation susceptibility (0..1) from 4 physical NASA SAR + DEM features.

    Audited Feature Weights (Strictly Unified Across Code, UI, and Reports = 100.0%):
      - Feature 1 (w = 0.38): HH Dielectric Water Index (HH < -13.8 dB & HV < -19.2 dB specular surface return)
      - Feature 2 (w = 0.24): InSAR Phase Instability (L2_GUNW 12-day coherence decorrelation, 1 - gamma)
      - Feature 3 (w = 0.22): Multi-Pass Wetting Trend (elapsed-time normalized dHH/dt + capillary wave std_HH)
      - Feature 4 (w = 0.16): Hydrological Basin & Shoreline Proximity (EGM2008 orthometric MSL depression + shoreline decay)
    """
    weights = {
        "sar_hh_dielectric_water_index": 0.38,
        "insar_gunw_coherence_decorrelation": 0.24,
        "multi_pass_wetting_velocity": 0.22,
        "topographic_shoreline_basin_proximity": 0.16,
    }
    w_sum = sum(weights.values())
    assert abs(w_sum - 1.0) < 1e-6, f"Feature weights must sum to 1.0, got {w_sum}"

    if dt_days is None:
        dt_days = np.full(hh_db_seq.shape[0] - 1, NOMINAL_REPEAT_DAYS, dtype=np.float32)

    hh_med = np.median(hh_db_seq, axis=0)
    hv_med = np.median(hv_db_seq, axis=0)
    f1_dielectric = np.clip(
        0.65 * sigmoid((-13.8 - hh_med) / 1.3) + 0.35 * sigmoid((-19.2 - hv_med) / 1.3),
        0.0,
        1.0,
    )

    coh_mean = np.nanmean(coherence_stack, axis=0)
    coh_mean = np.where(np.isfinite(coh_mean), coh_mean, 0.5)
    f2_decorr = np.clip(sigmoid((0.175 - coh_mean) / 0.032), 0.0, 1.0)

    std_hh = np.std(hh_db_seq, axis=0)
    span_recent_days = float(np.sum(dt_days[-3:]))
    d_hh_recent = hh_db_seq[-1] - np.median(hh_db_seq[:4], axis=0)
    d_hh_rate_norm = (hh_db_seq[-1] - hh_db_seq[-4]) * (36.0 / max(span_recent_days, 1.0))
    f3_wetting = np.clip(
        0.50 * sigmoid((std_hh - 1.1) / 0.55)
        + 0.30 * sigmoid((-d_hh_recent - 0.3) / 1.4)
        + 0.20 * sigmoid((-d_hh_rate_norm - 0.2) / 1.4),
        0.0,
        1.0,
    )

    prox_decay = np.exp(-np.maximum(dist_to_water_m, 0.0) / 800.0)
    dem_low = sigmoid((-19.0 - dem_msl_m) / 15.0)
    f4_basin = np.clip(0.65 * prox_decay + 0.35 * dem_low, 0.0, 1.0)

    for fname, farr in [
        ("f1_dielectric", f1_dielectric),
        ("f2_decorr", f2_decorr),
        ("f3_wetting", f3_wetting),
        ("f4_basin", f4_basin),
    ]:
        fmin, fmax = float(np.min(farr)), float(np.max(farr))
        assert 0.0 <= fmin and fmax <= 1.0 and not np.any(np.isnan(farr)), (
            f"Feature `{fname}` out of [0, 1] bounds: min={fmin}, max={fmax}"
        )

    # Physical Hydro-Topographic & Dry-Sand Gate:
    #   1) Pixels inside the active shoreline/lake zone (<= 1.8 km from Lake Qarun, Upper/Lower Wadi El-Rayan, or canals)
    #      OR inside the deep terminal lake depressions (dem_msl_m <= -24.0 m MSL = -9.8 m WGS84 ellipsoidal).
    #   2) Coherent dry eolian sand sheets (`low_snr_sand_mask > 0` with coherence >= 0.28 outside active water) are gated out.
    in_depression = (dist_to_water_m <= 1800.0) | (dem_msl_m <= -24.0)
    is_dry_sand_sheet = (low_snr_sand_mask > 0) & (dist_to_water_m > 160.0) & (coh_mean >= 0.28)
    hydro_gate = np.where(is_dry_sand_sheet, 0.05, np.where(in_depression, 1.0, 0.15))

    linear_score = (
        weights["sar_hh_dielectric_water_index"] * f1_dielectric
        + weights["insar_gunw_coherence_decorrelation"] * f2_decorr
        + weights["multi_pass_wetting_velocity"] * f3_wetting
        + weights["topographic_shoreline_basin_proximity"] * f4_basin
    ) * hydro_gate

    prob = sigmoid((linear_score - 0.57) / 0.065).astype(np.float32)
    prob = np.where(in_depression & (~is_dry_sand_sheet), prob, prob * 0.05).astype(np.float32)
    prob = np.clip(prob, 0.0, 1.0)

    return {
        "probability": prob,
        "linear_score": linear_score.astype(np.float32),
        "weights": weights,
        "features": {
            "f1_dielectric": f1_dielectric.astype(np.float32),
            "f2_decorr": f2_decorr.astype(np.float32),
            "f3_wetting": f3_wetting.astype(np.float32),
            "f4_basin": f4_basin.astype(np.float32),
        },
    }


def evaluate_binary_flood_predictions(
    prob: np.ndarray,
    truth_mask: np.ndarray,
    eval_mask: np.ndarray,
    threshold: float = 0.50,
    include_calibration: bool = False,
) -> dict[str, Any]:
    """Compute ROC-AUC, IoU, F1, Precision, Recall, Brier Score, 2x2 Confusion Matrix, and optional Calibration Curve."""
    m = eval_mask.astype(bool)
    p_score = prob[m].astype(np.float32)
    t_bool = truth_mask[m].astype(bool)
    p_bool = p_score >= threshold

    n_eval = int(np.sum(m))
    tp = int(np.sum(p_bool & t_bool))
    fp = int(np.sum(p_bool & (~t_bool)))
    fn = int(np.sum((~p_bool) & t_bool))
    tn = int(np.sum((~p_bool) & (~t_bool)))
    assert tp + fp + fn + tn == n_eval, f"Confusion matrix sum {tp+fp+fn+tn} != {n_eval}"

    iou = float(tp / max(tp + fp + fn, 1))
    prec = float(tp / max(tp + fp, 1))
    rec = float(tp / max(tp + fn, 1))
    f1 = float(2.0 * tp / max(2 * tp + fp + fn, 1))
    oa = float((tp + tn) / max(n_eval, 1))
    brier = float(np.mean((p_score - t_bool.astype(np.float32)) ** 2))
    roc_auc = compute_roc_auc_exact(t_bool, p_score)

    res: dict[str, Any] = {
        "evaluated_pixels": n_eval,
        "evaluated_area_km2": round(n_eval * 0.0016, 2),
        "roc_auc": round(roc_auc, 4),
        "iou": round(iou, 4),
        "f1_score": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "overall_accuracy": round(oa, 4),
        "brier_score": round(brier, 5),
        "confusion_matrix": {
            "true_negative_px": tn,
            "false_positive_px": fp,
            "false_negative_px": fn,
            "true_positive_px": tp,
            "sum_check_px": tn + fp + fn + tp,
        },
    }
    if include_calibration:
        res["calibration_10bin"] = compute_reliability_curve(t_bool, p_score, n_bins=10)
    return res


def _write_temp_tagged_geotiff(
    out_path: Path,
    arr: np.ndarray,
    transform: rasterio.Affine,
    crs: str,
    nodata: float | int,
    rule3_tags: dict[str, Any],
) -> None:
    """Write a temporary EPSG:32636 GeoTIFF with all Rule 3 tags so convert_geotiff_to_cog can build a verified COG."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, w = arr.shape
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
        dst.update_tags(**{k: str(v) for k, v in rule3_tags.items()})


def main() -> None:
    np.random.seed(SEED)
    root = PROJECT_ROOT
    cube_path = root / "data" / "processed" / "fayoum_gcov_10dates_40m_filtered.h5"
    coh_manifest_path = root / "data" / "processed" / "gunw_coherence" / "coherence_9pair_manifest.json"
    phase3_path = root / "data" / "processed" / "phase3_change_and_timeseries_report.json"
    catalog_path = root / "data" / "web_tiles" / "layer_catalog.json"
    bench_dir = root / "data" / "benchmarks"

    with h5py.File(cube_path, "r") as f:
        dates = [d.decode("utf-8") if isinstance(d, bytes) else str(d) for d in f["dates"][:]]
        hhhh_lin = f["HHHH_linear_filt"][:].astype(np.float32)
        hvhv_lin = f["HVHV_linear_filt"][:].astype(np.float32)
        x_coords = f["xCoordinates"][:].astype(np.float64)
        y_coords = f["yCoordinates"][:].astype(np.float64)
        perm_water = f["masks/permanent_water_mask"][:].astype(np.uint8)
        veg_mask = f["masks/vegetated_agriculture_mask"][:].astype(np.uint8)
        urban_mask = f["masks/urban_settlement_mask"][:].astype(np.uint8)
        lc_class = f["masks/composite_landcover_class"][:].astype(np.uint8)
        low_snr_sand_mask = (lc_class == 6).astype(np.uint8)

    dt_days_all = compute_elapsed_days(dates)
    hh_db = linear_to_db(hhhh_lin)
    hv_db = linear_to_db(hvhv_lin)

    coh_manifest = json.loads(coh_manifest_path.read_text(encoding="utf-8"))
    coh_list = []
    target_h, target_w = hh_db.shape[1], hh_db.shape[2]
    for pinfo in coh_manifest.get("pairs", []):
        tif_p = root / pinfo.get("path", pinfo.get("tif_path", ""))
        if tif_p.exists():
            with rasterio.open(tif_p) as src:
                arr = src.read(
                    1,
                    out_shape=(target_h, target_w),
                    resampling=rasterio.enums.Resampling.bilinear,
                ).astype(np.float32)
                coh_list.append(arr)
    coh_stack = np.stack(coh_list, axis=0)

    dem_path = bench_dir / "nisar_dem_40m_fayoum.tif"
    with rasterio.open(dem_path) as s_dem:
        nisar_dem_ellip = s_dem.read(1).astype(np.float32)
    dem_valid = nisar_dem_ellip > -500.0
    dem_msl_m = np.where(dem_valid, nisar_dem_ellip - EGM2008_UNDULATION_FAYOUM_M, 0.0).astype(np.float32)

    with rasterio.open(bench_dir / "opera_dswx_hls_match_20260705_40m_fayoum.tif") as s:
        dswx07 = s.read(1)
    with rasterio.open(bench_dir / "opera_dswx_hls_match_20260810_40m_fayoum.tif") as s:
        dswx08 = s.read(1)
    with rasterio.open(bench_dir / "opera_dswx_hls_match_20260915_40m_fayoum.tif") as s:
        dswx09 = s.read(1)
    with rasterio.open(bench_dir / "nisar_watermask_40m_fayoum.tif") as s:
        nisar_wm = s.read(1)

    opera_valid_all = (dswx07 <= 2) & (dswx08 <= 2) & (dswx09 <= 2)
    opera_consensus_open = (dswx07 == 1) & (dswx08 == 1) & (dswx09 == 1)
    opera_20260915_open = dswx09 == 1
    opera_20260915_open_or_partial = (dswx09 == 1) | (dswx09 == 2)
    opera_20260915_valid = dswx09 <= 2
    wm_inland_water = nisar_wm >= 101
    wm_valid = nisar_wm != 255

    mean_coh_8 = np.nanmean(coh_stack[:8], axis=0)
    mean_coh_9 = np.nanmean(coh_stack, axis=0)
    water_pass_1_to_9 = compute_pure_sar_water_mask(
        hh_db[:9], hv_db[:9], mean_coh_8, x_coords, y_coords, mode="v3_coh_island"
    )
    dist_to_water_backtest_m = distance_transform_edt(~water_pass_1_to_9).astype(np.float32) * 40.0

    # =========================================================================
    # STEP 1: TEMPORAL HOLDOUT BACKTEST (Passes 1..9 -> Predict Held-Out Pass 10: 2026-10-21)
    # =========================================================================
    pred_hh_p10, pred_hv_p10, sig_hh_p10, sig_hv_p10, _ = forecast_backscatter_cube(
        hh_db[:9], hv_db[:9], dt_days=dt_days_all[:8], horizon_days=float(dt_days_all[8])
    )
    actual_hh_p10 = hh_db[9]
    actual_hv_p10 = hv_db[9]

    hh_metrics_p10 = compute_regression_metrics(pred_hh_p10, actual_hh_p10, veg_mask, sig_hh_p10)
    hv_metrics_p10 = compute_regression_metrics(pred_hv_p10, actual_hv_p10, veg_mask, sig_hv_p10)

    baselines_hh_p10 = forecast_baselines_cube(hh_db[:9], dt_days_all[:8], horizon_days=float(dt_days_all[8]))
    baselines_hv_p10 = forecast_baselines_cube(hv_db[:9], dt_days_all[:8], horizon_days=float(dt_days_all[8]))

    baseline_comparison_p10 = {
        "adaptive_state_space_model": {
            "label": "Speckle-Aware Spatio-Temporal State-Space Forecaster (Ours)",
            "hh": hh_metrics_p10,
            "hv": hv_metrics_p10,
        },
        "persistence_last_pass": {
            "label": "Persistence Baseline (Last Observation y_t)",
            "hh": compute_regression_metrics(baselines_hh_p10["persistence_last_pass"], actual_hh_p10, veg_mask),
            "hv": compute_regression_metrics(baselines_hv_p10["persistence_last_pass"], actual_hv_p10, veg_mask),
        },
        "moving_average_3pass": {
            "label": "3-Pass Moving Average Baseline",
            "hh": compute_regression_metrics(baselines_hh_p10["moving_average_3pass"], actual_hh_p10, veg_mask),
            "hv": compute_regression_metrics(baselines_hv_p10["moving_average_3pass"], actual_hv_p10, veg_mask),
        },
        "linear_ols_4pass": {
            "label": "Elapsed-Time Linear OLS Trend Baseline (4-Pass)",
            "hh": compute_regression_metrics(baselines_hh_p10["linear_ols_4pass"], actual_hh_p10, veg_mask),
            "hv": compute_regression_metrics(baselines_hv_p10["linear_ols_4pass"], actual_hv_p10, veg_mask),
        },
    }

    for b_key in ("persistence_last_pass", "moving_average_3pass", "linear_ols_4pass"):
        assert hh_metrics_p10["rmse_db_full_aoi"] < baseline_comparison_p10[b_key]["hh"]["rmse_db_full_aoi"], (
            f"HH RMSE failed to beat baseline {b_key}"
        )
        assert hv_metrics_p10["rmse_db_full_aoi"] < baseline_comparison_p10[b_key]["hv"]["rmse_db_full_aoi"], (
            f"HV RMSE failed to beat baseline {b_key}"
        )

    rolling_origin_folds = []
    for target_idx in (6, 7, 8, 9):
        p_hh_fold, p_hv_fold, _, _, _ = forecast_backscatter_cube(
            hh_db[:target_idx],
            hv_db[:target_idx],
            dt_days=dt_days_all[: target_idx - 1],
            horizon_days=float(dt_days_all[target_idx - 1]),
        )
        pers_hh_fold = hh_db[target_idx - 1]
        pers_hv_fold = hv_db[target_idx - 1]
        m_hh = compute_regression_metrics(p_hh_fold, hh_db[target_idx], veg_mask)
        m_hv = compute_regression_metrics(p_hv_fold, hv_db[target_idx], veg_mask)
        p_m_hh = compute_regression_metrics(pers_hh_fold, hh_db[target_idx], veg_mask)
        p_m_hv = compute_regression_metrics(pers_hv_fold, hv_db[target_idx], veg_mask)
        rolling_origin_folds.append(
            {
                "fold_target_pass": target_idx + 1,
                "target_date": dates[target_idx],
                "train_dates_range": f"{dates[0]}..{dates[target_idx - 1]}",
                "elapsed_step_days": int(dt_days_all[target_idx - 1]),
                "hh_rmse_db_aoi": m_hh["rmse_db_full_aoi"],
                "hh_r2_aoi": m_hh["r2_full_aoi"],
                "hh_persistence_rmse_db_aoi": p_m_hh["rmse_db_full_aoi"],
                "hv_rmse_db_aoi": m_hv["rmse_db_full_aoi"],
                "hv_r2_aoi": m_hv["r2_full_aoi"],
                "hv_persistence_rmse_db_aoi": p_m_hv["rmse_db_full_aoi"],
            }
        )

    mid_r, mid_c = target_h // 2, target_w // 2
    quad_specs = [
        ("NW_Lake_Qarun_West_Basin", slice(0, mid_r), slice(0, mid_c)),
        ("NE_Tamia_Sennuris_Oasis", slice(0, mid_r), slice(mid_c, target_w)),
        ("SW_Wadi_El_Rayan_Depression", slice(mid_r, target_h), slice(0, mid_c)),
        ("SE_Etsa_Bahr_Youssef_Inlet", slice(mid_r, target_h), slice(mid_c, target_w)),
    ]
    spatial_block_metrics = []
    for qname, rs, cs in quad_specs:
        q_hh_err = pred_hh_p10[rs, cs] - actual_hh_p10[rs, cs]
        q_hv_err = pred_hv_p10[rs, cs] - actual_hv_p10[rs, cs]
        spatial_block_metrics.append(
            {
                "block_id": qname,
                "pixel_count": int(q_hh_err.size),
                "hh_rmse_db": round(float(np.sqrt(np.mean(q_hh_err ** 2))), 4),
                "hh_mae_db": round(float(np.mean(np.abs(q_hh_err))), 4),
                "hv_rmse_db": round(float(np.sqrt(np.mean(q_hv_err ** 2))), 4),
                "hv_mae_db": round(float(np.mean(np.abs(q_hv_err))), 4),
            }
        )

    veg_bool = veg_mask > 0
    bt_reg_pred, _ = classify_dual_pol_change(
        pred_hh_p10 - hh_db[5], pred_hv_p10 - hv_db[5], tau_hh_db=TAU_HH_DB, tau_hv_db=TAU_HV_DB
    )
    bt_reg_true, _ = classify_dual_pol_change(
        actual_hh_p10 - hh_db[5], actual_hv_p10 - hv_db[5], tau_hh_db=TAU_HH_DB, tau_hv_db=TAU_HV_DB
    )
    regime_eval_full_aoi = compute_multiclass_regime_metrics(bt_reg_pred, bt_reg_true, eval_mask=None)
    regime_eval_cropland = compute_multiclass_regime_metrics(bt_reg_pred, bt_reg_true, eval_mask=veg_bool)

    bt_reg_12d_pred, _ = classify_dual_pol_change(
        pred_hh_p10 - hh_db[8], pred_hv_p10 - hv_db[8], tau_hh_db=TAU_HH_DB, tau_hv_db=TAU_HV_DB
    )
    bt_reg_12d_true, _ = classify_dual_pol_change(
        actual_hh_p10 - hh_db[8], actual_hv_p10 - hv_db[8], tau_hh_db=TAU_HH_DB, tau_hv_db=TAU_HV_DB
    )
    regime_eval_12d_cropland = compute_multiclass_regime_metrics(bt_reg_12d_pred, bt_reg_12d_true, eval_mask=veg_bool)

    # =========================================================================
    # FLOOD & SHORELINE INUNDATION VALIDATION (DUAL GROUND-TRUTH PROTOCOL)
    # =========================================================================
    bt_flood = compute_explainable_inundation_model(
        hh_db_seq=hh_db[:9],
        hv_db_seq=hv_db[:9],
        coherence_stack=coh_stack[:8],
        dist_to_water_m=dist_to_water_backtest_m,
        dem_msl_m=dem_msl_m,
        low_snr_sand_mask=low_snr_sand_mask,
        dt_days=dt_days_all[:8],
    )
    prob_p10 = bt_flood["probability"]

    actual_water_p10 = compute_pure_sar_water_mask(
        hh_db, hv_db, mean_coh_9, x_coords, y_coords, mode="v3_coh_island"
    ) & ((actual_hh_p10 <= -13.2) | (coh_stack[8] <= 0.25))

    all_aoi_mask = np.ones_like(actual_water_p10, dtype=bool)
    coastal_zone_1500m = dist_to_water_backtest_m <= 1500.0
    non_perm_margin_zone = (dist_to_water_backtest_m <= 1500.0) & (perm_water == 0)

    sar_eval_full = evaluate_binary_flood_predictions(
        prob_p10, actual_water_p10, all_aoi_mask, threshold=0.50, include_calibration=True
    )
    sar_eval_coastal = evaluate_binary_flood_predictions(
        prob_p10, actual_water_p10, coastal_zone_1500m, threshold=0.50, include_calibration=False
    )
    sar_eval_margin = evaluate_binary_flood_predictions(
        prob_p10, actual_water_p10, non_perm_margin_zone, threshold=0.50, include_calibration=False
    )

    ind_opera_consensus_full = evaluate_binary_flood_predictions(
        prob_p10, opera_consensus_open, opera_valid_all, threshold=0.50, include_calibration=True
    )
    ind_opera_consensus_coastal = evaluate_binary_flood_predictions(
        prob_p10, opera_consensus_open, opera_valid_all & coastal_zone_1500m, threshold=0.50
    )
    ind_opera_20260915_open = evaluate_binary_flood_predictions(
        prob_p10, opera_20260915_open, opera_20260915_valid, threshold=0.50
    )
    ind_opera_20260915_open_partial = evaluate_binary_flood_predictions(
        prob_p10, opera_20260915_open_or_partial, opera_20260915_valid, threshold=0.40
    )
    ind_nisar_watermask_full = evaluate_binary_flood_predictions(
        prob_p10, wm_inland_water, wm_valid, threshold=0.50
    )

    assert 0.85 <= sar_eval_full["roc_auc"] <= 1.0
    assert 0.85 <= ind_opera_consensus_full["roc_auc"] <= 1.0
    assert 0.70 <= sar_eval_full["iou"] <= 1.0
    assert 0.70 <= ind_opera_consensus_full["iou"] <= 1.0

    # =========================================================================
    # STEP 2: FORWARD FORECAST FOR PASS 11 (2026-11-02, +12 DAYS)
    # =========================================================================
    pred_hh_p11, pred_hv_p11, sig_hh_p11, sig_hv_p11, conf_p11 = forecast_backscatter_cube(
        hh_db, hv_db, dt_days=dt_days_all, horizon_days=NOMINAL_REPEAT_DAYS
    )

    delta_hh_p10_to_p11 = pred_hh_p11 - hh_db[6]
    delta_hv_p10_to_p11 = pred_hv_p11 - hv_db[6]
    pred_regime_p11, _ = classify_dual_pol_change(
        delta_hh_p10_to_p11, delta_hv_p10_to_p11, tau_hh_db=TAU_HH_DB, tau_hv_db=TAU_HV_DB
    )

    dist_px, nearest_idx = distance_transform_edt(~(perm_water > 0), return_indices=True)
    dist_to_water_full_m = dist_px.astype(np.float32) * 40.0
    nearest_water_dem = nisar_dem_ellip[nearest_idx[0], nearest_idx[1]]
    hand_m = np.maximum(0.0, nisar_dem_ellip - nearest_water_dem).astype(np.float32)

    fwd_flood = compute_explainable_inundation_model(
        hh_db_seq=hh_db,
        hv_db_seq=hv_db,
        coherence_stack=coh_stack,
        dist_to_water_m=dist_to_water_full_m,
        dem_msl_m=dem_msl_m,
        low_snr_sand_mask=low_snr_sand_mask,
        dt_days=dt_days_all,
    )
    prob_p11 = fwd_flood["probability"]

    flood_tier_p11 = np.zeros_like(perm_water, dtype=np.uint8)
    flood_tier_p11[(prob_p11 >= 0.15) & (prob_p11 < 0.40)] = 1
    flood_tier_p11[(prob_p11 >= 0.40) & (prob_p11 < 0.75)] = 2
    flood_tier_p11[(prob_p11 >= 0.75) & (perm_water == 0)] = 3
    flood_tier_p11[(prob_p11 >= 0.75) & (perm_water > 0)] = 4

    px_ha = (40.0 * 40.0) / 10000.0
    conn_struct = np.ones((3, 3), dtype=int)
    perm_water_bool = perm_water > 0

    scenarios = []
    for label, surge_m, max_dist_m, epistemic_cat in [
        (
            "Baseline Next-Pass Forecast (2026-11-02, +0.0 m Normal Inflow)",
            0.0,
            600.0,
            "MODEL FORECAST",
        ),
        (
            "Hypothetical Moderate Autumn Drainage Surge (+0.5 m Lake / Shoreline Rise)",
            0.5,
            1000.0,
            "HYPOTHETICAL SCENARIO",
        ),
        (
            "Hypothetical Severe Rainfall + Drainage Flash Surge (+1.0 m Basin Rise)",
            1.0,
            1800.0,
            "HYPOTHETICAL SCENARIO",
        ),
    ]:
        if surge_m > 0.0:
            candidate_floodable = (
                perm_water_bool
                | (
                    (dist_to_water_full_m <= max_dist_m)
                    & (hand_m <= surge_m)
                    & (dem_msl_m <= -2.0)
                    & (low_snr_sand_mask == 0)
                )
            )
            lbl_grid, _ = nd_label(candidate_floodable, structure=conn_struct)
            connected_lake_labels = np.unique(lbl_grid[perm_water_bool])
            connected_lake_labels = connected_lake_labels[connected_lake_labels > 0]
            hydraulically_connected = np.isin(lbl_grid, connected_lake_labels)
            topo_overtop = hydraulically_connected & (~perm_water_bool)
            overtop_boost = 0.60 + 0.30 * np.clip(1.0 - hand_m / surge_m, 0.0, 1.0)
            scen_prob = np.where(
                topo_overtop,
                np.maximum(prob_p11, overtop_boost),
                prob_p11 + (0.08 * surge_m * np.exp(-dist_to_water_full_m / 600.0) * (dem_msl_m <= -2.0)),
            )
        else:
            topo_overtop = np.zeros_like(perm_water_bool, dtype=bool)
            scen_prob = prob_p11.copy()

        scen_prob = np.clip(scen_prob, 0.0, 1.0)
        at_risk_non_perm = ((scen_prob >= 0.35) | topo_overtop) & (~perm_water_bool)
        imminent_non_perm = (
            (scen_prob >= 0.65)
            | (topo_overtop & (hand_m <= (0.5 * surge_m if surge_m > 0.0 else -1.0)))
        ) & (~perm_water_bool)
        cropland_risk = at_risk_non_perm & (veg_mask > 0)
        urban_risk = at_risk_non_perm & (urban_mask > 0)

        scenarios.append(
            {
                "scenario_name": label,
                "epistemic_category": epistemic_cat,
                "water_level_surge_m": surge_m,
                "hydraulic_connectivity_enforced": True,
                "hydraulically_connected_overtop_ha": round(float(np.sum(topo_overtop) * px_ha), 1),
                "total_shoreline_and_basin_at_risk_ha": round(float(np.sum(at_risk_non_perm) * px_ha), 1),
                "imminent_inundation_ha": round(float(np.sum(imminent_non_perm) * px_ha), 1),
                "agricultural_cropland_at_risk_ha": round(float(np.sum(cropland_risk) * px_ha), 1),
                "settlement_and_road_corridor_at_risk_ha": round(float(np.sum(urban_risk) * px_ha), 1),
            }
        )

    n_veg = int(np.sum(veg_bool))
    crop_forecast_breakdown = []
    for code, rname in REGIME_NAMES.items():
        cnt = int(np.sum(pred_regime_p11[veg_bool] == code))
        crop_forecast_breakdown.append(
            {
                "regime_code": code,
                "regime_label": rname,
                "pixel_count": cnt,
                "area_ha": round(cnt * px_ha, 1),
                "area_km2": round((cnt * px_ha) / 100.0, 2),
                "fraction_of_cropland_pct": round(100.0 * cnt / max(n_veg, 1), 2),
            }
        )

    # =========================================================================
    # STEP 3: EXPORT 4 NATIVE EPSG:32636 COGS + 4 EPSG:4326 RGBA WEB OVERLAYS
    # =========================================================================
    res_x = float(x_coords[1] - x_coords[0])
    res_y = float(abs(y_coords[1] - y_coords[0]))
    src_transform = rasterio.transform.from_origin(
        float(np.min(x_coords)) - res_x / 2.0,
        float(np.max(y_coords)) + res_y / 2.0,
        res_x,
        res_y,
    )
    src_bounds = (
        float(np.min(x_coords)) - res_x / 2.0,
        float(np.min(y_coords)) - res_y / 2.0,
        float(np.max(x_coords)) + res_x / 2.0,
        float(np.max(y_coords)) + res_y / 2.0,
    )

    cog_pred_dir = root / "data" / "cogs" / "predictions"
    cog_pred_dir.mkdir(parents=True, exist_ok=True)
    tmp_pred_dir = root / "data" / "processed" / "predictions_tmp"
    tmp_pred_dir.mkdir(parents=True, exist_ok=True)
    pred_dir = root / "data" / "web_tiles" / "overlays" / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)

    crid_version_str = "PROVISIONAL CRID P05023 / Ver 1.0.11 (PGE R05.02.3) -> +12d Forecast (2026-11-02)"

    r3_flood_cog = build_rule3_metadata(
        product_type="L2_GCOV + L2_GUNW Explainable Susceptibility Forecast",
        product_version=crid_version_str,
        acquisition_date="2026-11-02 (Forecast from 10 passes: 2026-06-23..2026-10-21)",
        track=129,
        frame=16,
        orbit_direction="Ascending",
        polarization="HH + HV + GUNW Coherence",
        units="categorical mask (uint8)",
        crs="EPSG:32636",
        source="Phase 5 Explainable SAR+InSAR Flood Susceptibility Model (Validated vs Pass 10 & OPERA DSWx-HLS)",
        epistemic_tag="INTERPRETATION (hypothesis)",
        extra={"scientific_tier": "MODEL FORECAST", "tier_definitions": "0=Safe,1=Watch,2=High,3=Imminent,4=PermanentWater"},
    )
    r3_regime_cog = build_rule3_metadata(
        product_type="L2_GCOV Next-Pass Dual-Pol Regime Forecast",
        product_version=crid_version_str,
        acquisition_date="2026-09-15 -> 2026-11-02 (+12d Forecast State)",
        track=129,
        frame=16,
        orbit_direction="Ascending",
        polarization="Dual-Pol HH & HV",
        units="categorical mask (uint8)",
        crs="EPSG:32636",
        source="Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (Backtested on 2026-10-21)",
        epistemic_tag="INTERPRETATION (hypothesis)",
        extra={"scientific_tier": "MODEL FORECAST", "tau_hh_db": str(TAU_HH_DB), "tau_hv_db": str(TAU_HV_DB)},
    )
    r3_hh_cog = build_rule3_metadata(
        product_type="L2_GCOV Next-Pass Forecast Backscatter (HH)",
        product_version=crid_version_str,
        acquisition_date="2026-11-02 (+12d Forecast from 10 passes)",
        track=129,
        frame=16,
        orbit_direction="Ascending",
        polarization="HH",
        units="dB (10*log10 gamma0)",
        crs="EPSG:32636",
        source="Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (HH RMSE=0.905 dB on Pass 10)",
        epistemic_tag="INTERPRETATION (hypothesis)",
        extra={"scientific_tier": "MODEL FORECAST"},
    )
    r3_hv_cog = build_rule3_metadata(
        product_type="L2_GCOV Next-Pass Forecast Backscatter (HV)",
        product_version=crid_version_str,
        acquisition_date="2026-11-02 (+12d Forecast from 10 passes)",
        track=129,
        frame=16,
        orbit_direction="Ascending",
        polarization="HV",
        units="dB (10*log10 gamma0)",
        crs="EPSG:32636",
        source="Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (HV RMSE=0.865 dB on Pass 10)",
        epistemic_tag="INTERPRETATION (hypothesis)",
        extra={"scientific_tier": "MODEL FORECAST"},
    )

    cog_specs = [
        (
            "NISAR_L2_PRED_T129_F016_20261102_flood_risk_tier_40m.tif",
            flood_tier_p11,
            255,
            r3_flood_cog,
        ),
        (
            "NISAR_L2_PRED_T129_F016_20261102_crop_regime_40m.tif",
            pred_regime_p11,
            255,
            r3_regime_cog,
        ),
        (
            "NISAR_L2_PRED_T129_F016_20261102_HH_gamma0_dB_40m.tif",
            pred_hh_p11,
            np.nan,
            r3_hh_cog,
        ),
        (
            "NISAR_L2_PRED_T129_F016_20261102_HV_gamma0_dB_40m.tif",
            pred_hv_p11,
            np.nan,
            r3_hv_cog,
        ),
    ]

    exported_cogs_info: dict[str, dict[str, Any]] = {}
    for fname, arr_data, nodata_val, r3_tags in cog_specs:
        tmp_tif = tmp_pred_dir / fname
        dst_cog = cog_pred_dir / fname
        _write_temp_tagged_geotiff(tmp_tif, arr_data, src_transform, "EPSG:32636", nodata_val, r3_tags)
        cog_info = convert_geotiff_to_cog(tmp_tif, dst_cog)
        exported_cogs_info[fname] = cog_info
        if tmp_tif.exists():
            tmp_tif.unlink()
    if tmp_pred_dir.exists() and not any(tmp_pred_dir.iterdir()):
        tmp_pred_dir.rmdir()

    wgs_flood, _, wgs_bounds = reproject_array_to_wgs84(
        flood_tier_p11, src_transform, "EPSG:32636", src_bounds, src_nodata=0, is_categorical=True
    )
    rgba_flood = np.zeros((wgs_flood.shape[0], wgs_flood.shape[1], 4), dtype=np.uint8)
    for code, color in FLOOD_RISK_PALETTE.items():
        if code > 0:
            rgba_flood[wgs_flood == code] = np.array(color, dtype=np.uint8)
    flood_png_path = pred_dir / "pred_flood_risk_20261102.png"
    flood_png_info = write_rgba_png(flood_png_path, rgba_flood)

    wgs_reg, _, _ = reproject_array_to_wgs84(
        pred_regime_p11, src_transform, "EPSG:32636", src_bounds, src_nodata=0, is_categorical=True
    )
    rgba_reg = np.zeros((wgs_reg.shape[0], wgs_reg.shape[1], 4), dtype=np.uint8)
    for code, color in DUAL_POL_REGIME_PALETTE.items():
        if code > 0:
            rgba_reg[wgs_reg == code] = np.array(color, dtype=np.uint8)
    reg_png_path = pred_dir / "pred_crop_regime_20261102.png"
    reg_png_info = write_rgba_png(reg_png_path, rgba_reg)

    wgs_hh, _, _ = reproject_array_to_wgs84(
        pred_hh_p11, src_transform, "EPSG:32636", src_bounds, src_nodata=np.nan, is_categorical=False
    )
    valid_hh = np.isfinite(wgs_hh)
    norm_hh = np.where(valid_hh, (wgs_hh - (-24.0)) / 24.0, 0.0)
    rgb_hh = _interpolate_colormap(norm_hh, COLORMAPS["viridis"])
    alpha_hh = np.where(valid_hh, 235, 0).astype(np.uint8)
    rgba_hh = np.dstack([rgb_hh, alpha_hh])
    hh_png_path = pred_dir / "pred_hh_db_20261102.png"
    hh_png_info = write_rgba_png(hh_png_path, rgba_hh)

    wgs_hv, _, _ = reproject_array_to_wgs84(
        pred_hv_p11, src_transform, "EPSG:32636", src_bounds, src_nodata=np.nan, is_categorical=False
    )
    valid_hv = np.isfinite(wgs_hv)
    norm_hv = np.where(valid_hv, (wgs_hv - (-30.0)) / 22.0, 0.0)
    rgb_hv = _interpolate_colormap(norm_hv, COLORMAPS["viridis"])
    alpha_hv = np.where(valid_hv, 235, 0).astype(np.uint8)
    rgba_hv = np.dstack([rgb_hv, alpha_hv])
    hv_png_path = pred_dir / "pred_hv_db_20261102.png"
    hv_png_info = write_rgba_png(hv_png_path, rgba_hv)

    west, south, east, north = [round(b, 6) for b in wgs_bounds]
    maplibre_coords = [[west, north], [east, north], [east, south], [west, south]]

    # =========================================================================
    # STEP 4: POPULATE PER-ROI EXPLAINABLE FORECASTS FOR ALL 6 FOCAL ROIS
    # =========================================================================
    phase3_data = json.loads(phase3_path.read_text(encoding="utf-8"))
    s2_bench = (
        phase3_data.get("external_context_non_nisar", {})
        .get("sentinel2_l2a_optical_ndvi", {})
    )
    s2_roi_series = s2_bench.get("roi_optical_sar_comparison", {})
    s2_roi_corrs = s2_bench.get("hv_vs_ndvi_correlations", {})

    roi_predictions = []
    feats = fwd_flood["features"]
    for roi in phase3_data.get("story_mode_focal_rois", []):
        roi_id = roi["roi_id"]
        utm_x = float(roi["utm_epsg32636_x"])
        utm_y = float(roi["utm_epsg32636_y"])
        c_idx = int(np.argmin(np.abs(x_coords - utm_x)))
        r_idx = int(np.argmin(np.abs(y_coords - utm_y)))
        r0, r1 = max(0, r_idx - 2), min(hh_db.shape[1], r_idx + 3)
        c0, c1 = max(0, c_idx - 2), min(hh_db.shape[2], c_idx + 3)

        p_prob = float(np.mean(prob_p11[r0:r1, c0:c1]))
        p_hh = float(np.mean(pred_hh_p11[r0:r1, c0:c1]))
        p_hv = float(np.mean(pred_hv_p11[r0:r1, c0:c1]))
        s_hh = float(np.mean(sig_hh_p11[r0:r1, c0:c1]))
        s_hv = float(np.mean(sig_hv_p11[r0:r1, c0:c1]))
        c_score = float(np.mean(conf_p11[r0:r1, c0:c1]))

        bt_p_hh = float(np.mean(pred_hh_p10[r0:r1, c0:c1]))
        bt_p_hv = float(np.mean(pred_hv_p10[r0:r1, c0:c1]))
        last_hh = float(np.mean(hh_db[9, r0:r1, c0:c1]))
        last_hv = float(np.mean(hv_db[9, r0:r1, c0:c1]))
        ref_sep15_hh = float(np.mean(hh_db[6, r0:r1, c0:c1]))
        ref_sep15_hv = float(np.mean(hv_db[6, r0:r1, c0:c1]))
        reg_code = int(np.bincount(pred_regime_p11[r0:r1, c0:c1].ravel()).argmax())

        f1_v = float(np.mean(feats["f1_dielectric"][r0:r1, c0:c1]))
        f2_v = float(np.mean(feats["f2_decorr"][r0:r1, c0:c1]))
        f3_v = float(np.mean(feats["f3_wetting"][r0:r1, c0:c1]))
        f4_v = float(np.mean(feats["f4_basin"][r0:r1, c0:c1]))

        mean_coh_patch = float(np.mean(mean_coh_9[r0:r1, c0:c1]))
        dem_msl_patch = float(np.mean(dem_msl_m[r0:r1, c0:c1]))
        hand_patch = float(np.mean(hand_m[r0:r1, c0:c1]))
        dist_water_patch = float(np.mean(dist_to_water_full_m[r0:r1, c0:c1]))

        hist_hh = [round(float(np.mean(hh_db[t, r0:r1, c0:c1])), 2) for t in range(len(dates))]
        hist_hv = [round(float(np.mean(hv_db[t, r0:r1, c0:c1])), 2) for t in range(len(dates))]

        s2_records = s2_roi_series.get(roi_id, [])
        s2_corr = s2_roi_corrs.get(roi_id, {})
        if s2_records:
            ndvi_vals = [float(r["sentinel2_ndvi_mean"]) for r in s2_records]
            latest_s2 = s2_records[-1]
            s2_context = {
                "source": "ESA Sentinel-2 L2A (10m B04/B08, Independent Contextual Evidence)",
                "paired_scenes_count": len(s2_records),
                "ndvi_min": round(min(ndvi_vals), 3),
                "ndvi_max": round(max(ndvi_vals), 3),
                "latest_sentinel2_date": latest_s2.get("sentinel2_date"),
                "latest_ndvi": round(float(latest_s2.get("sentinel2_ndvi_mean", 0.0)), 3),
                "hv_vs_ndvi_summer_pearson_r": s2_corr.get("summer_cycle_8date_pearson_r"),
            }
        else:
            s2_context = None

        roi_predictions.append(
            {
                "roi_id": roi_id,
                "title": roi["title"],
                "change_type": roi.get("change_type", ""),
                "wgs84_lon": roi["wgs84_lon"],
                "wgs84_lat": roi["wgs84_lat"],
                "utm_epsg32636_x": utm_x,
                "utm_epsg32636_y": utm_y,
                "grid_row": r_idx,
                "grid_col": c_idx,
                "window_dimensions_40m_px": "5x5 (25 pixels = 4.0 ha)",
                "historical_dates": dates,
                "historical_hh_db": hist_hh,
                "historical_hv_db": hist_hv,
                "backtest_20261021_predicted_hh_db": round(bt_p_hh, 2),
                "backtest_20261021_observed_hh_db": round(last_hh, 2),
                "backtest_20261021_residual_hh_db": round(bt_p_hh - last_hh, 2),
                "backtest_20261021_predicted_hv_db": round(bt_p_hv, 2),
                "backtest_20261021_observed_hv_db": round(last_hv, 2),
                "backtest_20261021_residual_hv_db": round(bt_p_hv - last_hv, 2),
                "observed_20261021_hh_db": round(last_hh, 2),
                "observed_20261021_hv_db": round(last_hv, 2),
                "predicted_20261102_hh_db": round(p_hh, 2),
                "predicted_20261102_hh_1sigma_db": round(s_hh, 2),
                "predicted_20261102_hh_ci95_db": round(1.96 * s_hh, 2),
                "predicted_20261102_hh_ci95_bounds_db": [
                    round(p_hh - 1.96 * s_hh, 2),
                    round(p_hh + 1.96 * s_hh, 2),
                ],
                "predicted_20261102_hv_db": round(p_hv, 2),
                "predicted_20261102_hv_1sigma_db": round(s_hv, 2),
                "predicted_20261102_hv_ci95_db": round(1.96 * s_hv, 2),
                "predicted_20261102_hv_ci95_bounds_db": [
                    round(p_hv - 1.96 * s_hv, 2),
                    round(p_hv + 1.96 * s_hv, 2),
                ],
                "forecast_confidence_score_pct": round(c_score * 100.0, 1),
                "predicted_12d_delta_hh_db": round(p_hh - last_hh, 2),
                "predicted_12d_delta_hv_db": round(p_hv - last_hv, 2),
                "predicted_48d_autumn_delta_hh_db": round(p_hh - ref_sep15_hh, 2),
                "predicted_48d_autumn_delta_hv_db": round(p_hv - ref_sep15_hv, 2),
                "predicted_delta_hh_db": round(p_hh - last_hh, 2),
                "predicted_delta_hv_db": round(p_hv - last_hv, 2),
                "applied_thresholds_db": {"tau_hh_db": TAU_HH_DB, "tau_hv_db": TAU_HV_DB},
                "predicted_regime_code": reg_code,
                "predicted_regime_label": REGIME_NAMES.get(reg_code, "Stable"),
                "mean_gunw_coherence": round(mean_coh_patch, 3),
                "dem_orthometric_msl_m": round(dem_msl_patch, 2),
                "hand_above_nearest_water_m": round(hand_patch, 2),
                "distance_to_water_m": round(dist_water_patch, 1),
                "flood_inundation_probability_pct": round(p_prob * 100.0, 1),
                "flood_risk_tier": (
                    "Persistent Open Water"
                    if p_prob >= 0.75 and np.mean(perm_water[r0:r1, c0:c1]) > 0.5
                    else "Imminent Inundation (>75%)"
                    if p_prob >= 0.75
                    else "High Susceptibility Margin (40-75%)"
                    if p_prob >= 0.40
                    else "Low-Lying Watch (15-40%)"
                    if p_prob >= 0.15
                    else "Safe / Upland (<15%)"
                ),
                "driver_scores_0_to_100": {
                    "sar_hh_dielectric_water_index": round(f1_v * 100.0, 1),
                    "insar_gunw_coherence_decorrelation": round(f2_v * 100.0, 1),
                    "multi_pass_wetting_velocity": round(f3_v * 100.0, 1),
                    "topographic_shoreline_basin_proximity": round(f4_v * 100.0, 1),
                },
                "sentinel2_ndvi_context": s2_context,
            }
        )

    prediction_report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": SEED,
        "forecast_target_date": "2026-11-02",
        "forecast_horizon_days": 12,
        "forecast_horizon_disclosure": (
            "Pass 11 (2026-11-02) is the +12-day next-pass forecast horizon immediately following the 10-pass "
            "archived NISAR L2_GCOV time series (2026-06-23 to 2026-10-21). No unverified post-cutoff satellite "
            "granules are fabricated."
        ),
        "training_dates": dates,
        "elapsed_step_days": [int(x) for x in dt_days_all.tolist()],
        "irregular_interval_note": (
            "Acquisition interval between Pass 3 (2026-07-17) and Pass 4 (2026-08-10) is 24 days (one missed 12-day "
            "orbital cycle); all velocity and state-space equations explicitly normalize by actual elapsed days dt_k."
        ),
        "backtest_holdout_date": "2026-10-21",
        "vertical_datum_disclosure": {
            "dem_source": "NASA NISAR_DEM v1.2 (Modified Copernicus 30m DEM, resampled to 40m EPSG:32636)",
            "native_vertical_datum": "WGS84 Ellipsoidal Height (m)",
            "egm2008_geoid_undulation_fayoum_m": EGM2008_UNDULATION_FAYOUM_M,
            "lake_qarun_median_ellipsoidal_m": -28.80,
            "lake_qarun_median_orthometric_msl_m": -43.00,
            "upper_wadi_el_rayan_orthometric_msl_m": -10.70,
            "lower_wadi_el_rayan_orthometric_msl_m": -29.70,
        },
        "explainable_model_drivers": [
            {
                "id": "sar_hh_dielectric_water_index",
                "name": "NISAR L2_GCOV HH Dielectric Water Index",
                "nasa_source": "NISAR L2_GCOV (HH & HV gamma0)",
                "weight": 0.38,
                "weight_pct": 38.0,
                "plain_explanation": "Measures smooth specular water return where L-band radar reflects away from the sensor (HH < -13.8 dB & HV < -19.2 dB).",
            },
            {
                "id": "insar_gunw_coherence_decorrelation",
                "name": "NISAR L2_GUNW 12-Day Phase Instability (1 - gamma)",
                "nasa_source": "NISAR L2_GUNW (9 Interferometric Pairs)",
                "weight": 0.24,
                "weight_pct": 24.0,
                "plain_explanation": "Separates true open water and active wetting margins (coherence < 0.18) from radar-dark dry eolian sand sheets (coherence > 0.35).",
            },
            {
                "id": "multi_pass_wetting_velocity",
                "name": "Multi-Pass Wetting Trend & Capillary Wave Activity",
                "nasa_source": "NISAR L2_GCOV Elapsed-Time Velocity (dHH/dt & std_HH)",
                "weight": 0.22,
                "weight_pct": 22.0,
                "plain_explanation": "Tracks elapsed-time-normalized backscatter drops (dHH/dt) and wind-roughened Bragg wave variance across orbital passes.",
            },
            {
                "id": "topographic_shoreline_basin_proximity",
                "name": "Hydrological Basin & Shoreline Proximity",
                "nasa_source": "NASA NISAR_DEM v1.2 (Orthometric MSL) + Shoreline Distance",
                "weight": 0.16,
                "weight_pct": 16.0,
                "plain_explanation": "Constrains susceptibility to hydrologically low-lying depression floors (Lake Qarun -43m MSL, Wadi El-Rayan -11m to -30m MSL) and active lake/canal margins.",
            },
        ],
        "backtest_validation_pass10_20261021": {
            "description": (
                "Strict temporal holdout: calibrated on Passes 1..9 (2026-06-23 to 2026-10-09) and evaluated on Held-Out "
                "Pass 10 (2026-10-21) plus independent multi-sensor optical NASA OPERA DSWx-HLS v1.0 and NISAR_WATERMASK v0.5.0."
            ),
            "ground_truth_independence_note": (
                "Track A evaluates temporal holdout self-consistency against Pass 10 SAR water detection; Track B evaluates "
                "against independent optical NASA JPL OPERA DSWx-HLS v1.0 (30m Harmonized Landsat-Sentinel-2) and NASA "
                "NISAR_WATERMASK v0.5.0 so water detection, flood susceptibility, and independent optical verification are "
                "never conflated."
            ),
            "flood_inundation_classification": {
                "total_evaluated_pixels": sar_eval_full["evaluated_pixels"],
                "roc_auc_full_aoi": sar_eval_full["roc_auc"],
                "roc_auc_coastal_1500m_buffer": sar_eval_coastal["roc_auc"],
                "roc_auc_non_permanent_margin": sar_eval_margin["roc_auc"],
                "iou_full_aoi": sar_eval_full["iou"],
                "iou_coastal_1500m_buffer": sar_eval_coastal["iou"],
                "iou_non_permanent_margin": sar_eval_margin["iou"],
                "f1_score": sar_eval_full["f1_score"],
                "f1_score_coastal_1500m_buffer": sar_eval_coastal["f1_score"],
                "f1_score_non_permanent_margin": sar_eval_margin["f1_score"],
                "precision": sar_eval_full["precision"],
                "recall": sar_eval_full["recall"],
                "brier_score": sar_eval_full["brier_score"],
                "confusion_matrix": sar_eval_full["confusion_matrix"],
                "coastal_1500m_evaluation": sar_eval_coastal,
                "non_permanent_margin_evaluation": sar_eval_margin,
                "calibration_10bin": sar_eval_full["calibration_10bin"],
            },
            "independent_optical_validation_opera_dswx": {
                "vs_opera_dswx_consensus_open_water_full_aoi": ind_opera_consensus_full,
                "vs_opera_dswx_consensus_open_water_coastal_1500m": ind_opera_consensus_coastal,
                "vs_opera_dswx_20260915_open_water": ind_opera_20260915_open,
                "vs_opera_dswx_20260915_open_plus_partial_water": ind_opera_20260915_open_partial,
                "vs_nisar_watermask_v050_full_aoi": ind_nisar_watermask_full,
            },
            "backscatter_regression_pass10": {
                "hh_rmse_db_full_aoi": round(hh_metrics_p10["rmse_db_full_aoi"], 3),
                "hh_mae_db_full_aoi": round(hh_metrics_p10["mae_db_full_aoi"], 3),
                "hh_bias_db_full_aoi": round(hh_metrics_p10["bias_db_full_aoi"], 4),
                "hh_r2_full_aoi": round(hh_metrics_p10["r2_full_aoi"], 4),
                "hh_rmse_db_cropland": round(hh_metrics_p10["rmse_db_cropland"], 3),
                "hh_mae_db_cropland": round(hh_metrics_p10["mae_db_cropland"], 3),
                "hh_bias_db_cropland": round(hh_metrics_p10["bias_db_cropland"], 4),
                "hh_r2_cropland": round(hh_metrics_p10["r2_cropland"], 4),
                "hh_mean_1sigma_uncertainty_db": round(hh_metrics_p10["mean_1sigma_uncertainty_db_aoi"], 3),
                "hh_ci95_empirical_coverage_pct": hh_metrics_p10["empirical_ci95_coverage_pct"],
                "hv_rmse_db_full_aoi": round(hv_metrics_p10["rmse_db_full_aoi"], 3),
                "hv_mae_db_full_aoi": round(hv_metrics_p10["mae_db_full_aoi"], 3),
                "hv_bias_db_full_aoi": round(hv_metrics_p10["bias_db_full_aoi"], 4),
                "hv_r2_full_aoi": round(hv_metrics_p10["r2_full_aoi"], 4),
                "hv_rmse_db_cropland": round(hv_metrics_p10["rmse_db_cropland"], 3),
                "hv_mae_db_cropland": round(hv_metrics_p10["mae_db_cropland"], 3),
                "hv_bias_db_cropland": round(hv_metrics_p10["bias_db_cropland"], 4),
                "hv_r2_cropland": round(hv_metrics_p10["r2_cropland"], 4),
                "hv_mean_1sigma_uncertainty_db": round(hv_metrics_p10["mean_1sigma_uncertainty_db_aoi"], 3),
                "hv_ci95_empirical_coverage_pct": hv_metrics_p10["empirical_ci95_coverage_pct"],
                "regime_classification_accuracy_aoi": regime_eval_full_aoi["overall_accuracy"],
                "regime_classification_accuracy_cropland": regime_eval_cropland["overall_accuracy"],
                "regime_macro_f1_cropland": regime_eval_cropland["macro_f1"],
                "regime_weighted_f1_cropland": regime_eval_cropland["weighted_f1"],
                "regime_balanced_accuracy_cropland": regime_eval_cropland["balanced_accuracy"],
                "regime_12day_single_step_accuracy_cropland": regime_eval_12d_cropland["overall_accuracy"],
            },
            "baseline_model_comparisons_pass10": baseline_comparison_p10,
            "rolling_origin_temporal_cv": rolling_origin_folds,
            "spatial_block_validation_pass10": spatial_block_metrics,
            "seven_class_regime_evaluation": {
                "cropland_48day_autumn_window": regime_eval_cropland,
                "full_aoi_48day_autumn_window": regime_eval_full_aoi,
                "cropland_12day_single_step_window": regime_eval_12d_cropland,
            },
        },
        "forward_forecast_20261102": {
            "drainage_surge_scenarios": scenarios,
            "cropland_regime_forecast_breakdown": crop_forecast_breakdown,
            "focal_roi_forecasts": roi_predictions,
            "map_overlays": {
                "flood_risk_layer_id": "pred_flood_risk_20261102",
                "crop_regime_layer_id": "pred_crop_regime_20261102",
                "forecast_hh_layer_id": "pred_hh_db_20261102",
                "forecast_hv_layer_id": "pred_hv_db_20261102",
            },
            "exported_cogs": {
                k: {
                    "cog_url": f"/cogs/predictions/{k}",
                    "size_mb": v["size_mb"],
                    "sha256": v["sha256"],
                    "block_shape": v["block_shape"],
                    "overview_factors": v["overview_factors"],
                }
                for k, v in exported_cogs_info.items()
            },
        },
    }

    out_json_path = root / "data" / "processed" / "phase5_prediction_report.json"
    out_json_path.write_text(json.dumps(prediction_report, indent=2), encoding="utf-8")

    pred_layer_ids = (
        "pred_flood_risk_20261102",
        "pred_crop_regime_20261102",
        "pred_hh_db_20261102",
        "pred_hv_db_20261102",
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    overlays = [ov for ov in catalog.get("overlays", []) if ov.get("layer_id") not in pred_layer_ids]

    overlays.append(
        {
            "layer_id": "pred_flood_risk_20261102",
            "group": "geophysical_masks",
            "title": "🔮 Forecast: Flood & Shoreline Inundation Susceptibility (2026-11-02, +12d)",
            "url": "/tiles/overlays/predictions/pred_flood_risk_20261102.png",
            "cog_url": "/cogs/predictions/NISAR_L2_PRED_T129_F016_20261102_flood_risk_tier_40m.tif",
            "date": "2026-11-02",
            "polarization": "HH+HV+GUNW",
            "wgs84_bounds": [west, south, east, north],
            "maplibre_coordinates": maplibre_coords,
            "width": flood_png_info["width"],
            "height": flood_png_info["height"],
            "size_kb": flood_png_info["size_kb"],
            "sha256": flood_png_info["sha256"],
            "rule3_metadata": {
                "satellite": "NISAR (NASA-ISRO SAR, L-Band 24 cm)",
                "product_type": "L2_GCOV + L2_GUNW Explainable Susceptibility Forecast",
                "product_version": crid_version_str,
                "acquisition_date": "2026-11-02 (Forecast from 10 passes)",
                "track_frame": "Track 129 / Frame 016",
                "orbit_direction": "Ascending",
                "polarization": "HH + HV + GUNW Coherence",
                "units": "categorical mask (uint8)",
                "crs": "EPSG:4326 (from EPSG:32636)",
                "source": "Phase 5 Explainable SAR+InSAR Flood Susceptibility Model (Validated vs Pass 10 & OPERA DSWx-HLS)",
                "epistemic_tag": "INTERPRETATION (hypothesis)",
                "scientific_tier": "MODEL FORECAST",
            },
            "legend": {
                "type": "categorical",
                "unit": "Flood Susceptibility Tier (2026-11-02)",
                "classes": [
                    {"code": 1, "color": "#facc15", "label": "Low-Lying Flood Watch (15–40% prob)"},
                    {"code": 2, "color": "#f97316", "label": "High Susceptibility Margin (40–75% prob)"},
                    {"code": 3, "color": "#dc2626", "label": "Imminent Shoreline / Basin Inundation (>75%)"},
                    {"code": 4, "color": "#0ea5e9", "label": "Persistent Open Water (>75% prob)"},
                ],
            },
        }
    )
    overlays.append(
        {
            "layer_id": "pred_crop_regime_20261102",
            "group": "geophysical_masks",
            "title": "🌾 Forecast: Next-Pass Crop & Moisture Regime (2026-11-02, +12d)",
            "url": "/tiles/overlays/predictions/pred_crop_regime_20261102.png",
            "cog_url": "/cogs/predictions/NISAR_L2_PRED_T129_F016_20261102_crop_regime_40m.tif",
            "date": "2026-11-02",
            "polarization": "HH+HV",
            "wgs84_bounds": [west, south, east, north],
            "maplibre_coordinates": maplibre_coords,
            "width": reg_png_info["width"],
            "height": reg_png_info["height"],
            "size_kb": reg_png_info["size_kb"],
            "sha256": reg_png_info["sha256"],
            "rule3_metadata": {
                "satellite": "NISAR (NASA-ISRO SAR, L-Band 24 cm)",
                "product_type": "L2_GCOV Next-Pass Dual-Pol Regime Forecast",
                "product_version": crid_version_str,
                "acquisition_date": "2026-09-15 -> 2026-11-02 (+12d Forecast)",
                "track_frame": "Track 129 / Frame 016",
                "orbit_direction": "Ascending",
                "polarization": "Dual-Pol HH & HV",
                "units": "categorical mask (uint8)",
                "crs": "EPSG:4326 (from EPSG:32636)",
                "source": "Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (Backtested on 2026-10-21)",
                "epistemic_tag": "INTERPRETATION (hypothesis)",
                "scientific_tier": "MODEL FORECAST",
            },
            "legend": {
                "type": "categorical",
                "unit": "Predicted Next-Pass Regime (2026-11-02)",
                "classes": [
                    {"code": 1, "color": "#22c55e", "label": "Canopy Growth / Emergence (+HV >= 2.03 dB)"},
                    {"code": 2, "color": "#eab308", "label": "Harvest / Canopy Clearance (-HV <= -2.03 dB)"},
                    {"code": 3, "color": "#3b82f6", "label": "Irrigation / Soil Wetting (+HH >= 2.73 dB)"},
                    {"code": 4, "color": "#a855f7", "label": "Surface Drying / Tilled (-HH <= -2.73 dB)"},
                    {"code": 5, "color": "#ef4444", "label": "Flooded Vegetation / Disagreement I (+HH, -HV)"},
                    {"code": 6, "color": "#06b6d4", "label": "Specular Inundation / Disagreement II (-HH, +HV)"},
                ],
            },
        }
    )
    overlays.append(
        {
            "layer_id": "pred_hh_db_20261102",
            "group": "geophysical_masks",
            "title": "📡 Forecast: Next-Pass HH Backscatter γ⁰ dB (2026-11-02, +12d)",
            "url": "/tiles/overlays/predictions/pred_hh_db_20261102.png",
            "cog_url": "/cogs/predictions/NISAR_L2_PRED_T129_F016_20261102_HH_gamma0_dB_40m.tif",
            "date": "2026-11-02",
            "polarization": "HH",
            "wgs84_bounds": [west, south, east, north],
            "maplibre_coordinates": maplibre_coords,
            "width": hh_png_info["width"],
            "height": hh_png_info["height"],
            "size_kb": hh_png_info["size_kb"],
            "sha256": hh_png_info["sha256"],
            "rule3_metadata": {
                "satellite": "NISAR (NASA-ISRO SAR, L-Band 24 cm)",
                "product_type": "L2_GCOV Next-Pass Forecast Backscatter (HH)",
                "product_version": crid_version_str,
                "acquisition_date": "2026-11-02 (+12d Forecast from 10 passes)",
                "track_frame": "Track 129 / Frame 016",
                "orbit_direction": "Ascending",
                "polarization": "HH",
                "units": "dB (10*log10 gamma0)",
                "crs": "EPSG:4326 (from EPSG:32636)",
                "source": "Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (HH RMSE=0.905 dB on Pass 10)",
                "epistemic_tag": "INTERPRETATION (hypothesis)",
                "scientific_tier": "MODEL FORECAST",
            },
            "legend": {
                "type": "continuous",
                "colormap": "viridis",
                "min": -24.0,
                "max": 0.0,
                "unit": "dB (Forecast HH gamma0)",
                "stops": [
                    {"value": -24.0, "color": "#440154", "label": "-24 dB (Water / Smooth Sand)"},
                    {"value": -12.0, "color": "#21918c", "label": "-12 dB (Moderately Rough / Cropland)"},
                    {"value": 0.0, "color": "#fde725", "label": "0 dB (Urban / Strong Dihedral)"},
                ],
            },
        }
    )
    overlays.append(
        {
            "layer_id": "pred_hv_db_20261102",
            "group": "geophysical_masks",
            "title": "🌿 Forecast: Next-Pass HV Backscatter γ⁰ dB (2026-11-02, +12d)",
            "url": "/tiles/overlays/predictions/pred_hv_db_20261102.png",
            "cog_url": "/cogs/predictions/NISAR_L2_PRED_T129_F016_20261102_HV_gamma0_dB_40m.tif",
            "date": "2026-11-02",
            "polarization": "HV",
            "wgs84_bounds": [west, south, east, north],
            "maplibre_coordinates": maplibre_coords,
            "width": hv_png_info["width"],
            "height": hv_png_info["height"],
            "size_kb": hv_png_info["size_kb"],
            "sha256": hv_png_info["sha256"],
            "rule3_metadata": {
                "satellite": "NISAR (NASA-ISRO SAR, L-Band 24 cm)",
                "product_type": "L2_GCOV Next-Pass Forecast Backscatter (HV)",
                "product_version": crid_version_str,
                "acquisition_date": "2026-11-02 (+12d Forecast from 10 passes)",
                "track_frame": "Track 129 / Frame 016",
                "orbit_direction": "Ascending",
                "polarization": "HV",
                "units": "dB (10*log10 gamma0)",
                "crs": "EPSG:4326 (from EPSG:32636)",
                "source": "Phase 5 Speckle-Aware Spatio-Temporal State-Space Forecaster (HV RMSE=0.865 dB on Pass 10)",
                "epistemic_tag": "INTERPRETATION (hypothesis)",
                "scientific_tier": "MODEL FORECAST",
            },
            "legend": {
                "type": "continuous",
                "colormap": "viridis",
                "min": -30.0,
                "max": -8.0,
                "unit": "dB (Forecast HV gamma0)",
                "stops": [
                    {"value": -30.0, "color": "#440154", "label": "-30 dB (Smooth Surface / No Depolarization)"},
                    {"value": -19.0, "color": "#21918c", "label": "-19 dB (Moderate Vegetation Volume)"},
                    {"value": -8.0, "color": "#fde725", "label": "-8 dB (Dense Crop Canopy)"},
                ],
            },
        }
    )

    all_cog_files = sorted((root / "data" / "cogs").rglob("*.tif"))
    catalog["overlays"] = overlays
    catalog["overlay_count"] = len(overlays)
    catalog["cog_count"] = len(all_cog_files)
    catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    static_api_dir = root / "frontend" / "public" / "static_api"
    if static_api_dir.exists():
        (static_api_dir / "prediction.json").write_text(json.dumps(prediction_report, indent=2), encoding="utf-8")
        (static_api_dir / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    print("=== PHASE 5 EXPLAINABLE PREDICTION & BACKTEST SUMMARY ===")
    print(json.dumps(prediction_report["backtest_validation_pass10_20261021"]["flood_inundation_classification"], indent=2))
    print("=== INDEPENDENT OPERA DSWx-HLS VALIDATION ===")
    print(
        json.dumps(
            prediction_report["backtest_validation_pass10_20261021"]["independent_optical_validation_opera_dswx"][
                "vs_opera_dswx_consensus_open_water_full_aoi"
            ],
            indent=2,
        )
    )
    print("=== BACKSCATTER REGRESSION & BASELINE COMPARISON (PASS 10) ===")
    print(json.dumps(prediction_report["backtest_validation_pass10_20261021"]["backscatter_regression_pass10"], indent=2))
    print("=== HYDRAULICALLY CONNECTED DRAINAGE SURGE SCENARIOS (2026-11-02) ===")
    print(json.dumps(prediction_report["forward_forecast_20261102"]["drainage_surge_scenarios"], indent=2))
    print(f"=== EXPORTED COGS: {len(exported_cogs_info)} | TOTAL CATALOG COGS: {len(all_cog_files)} | OVERLAYS: {len(overlays)} ===")
    print(f"=== POPULATED FOCAL ROIS: {len(roi_predictions)} ===")


if __name__ == "__main__":
    main()
