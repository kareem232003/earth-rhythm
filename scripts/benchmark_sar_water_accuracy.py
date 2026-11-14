"""Quantitative Benchmark Comparison of Pure-SAR and DEM-Assisted Water Classification.

Evaluates 4 progressive classification stages over Fayoum Oasis (1560 x 1968, 40 m EPSG:32636):
  - v1 (Phase 2 Baseline): Rectangular hydro-basin gated `composite_landcover_class == 1`
  - v2 (2-GUNW + Blind Fill): Prior 2-pair L2_GUNW coherence + blind `binary_fill_holes`
  - v3 (Pure NISAR Option 1 - Production): All 9 T129_F016 L2_GUNW coherences + wind-wave
    std(HH) shore extension + coherence/area-aware island preservation (`compute_pure_sar_water_mask`)
  - v4 (Option 2 Ancillary Fusion - Benchmark Exploratory): v3 refined by `NISAR_DEM`
    Lake Qarun basin elevation constraints (Rule 2 strictly separated external DEM fusion)

Benchmarked strictly against authoritative NASA Earthdata ground-truth products:
  1. JPL `OPERA_L3_DSWX-HLS_V1` (30 m optical HLS surface water for 2026-07-05, 2026-08-10 [0d exact], 2026-09-15)
  2. NASA `NISAR_WATERMASK` v0.5.0 (inland surface water mask, codes >= 101)
  3. NASA `NISAR_DEM` v1.2 (Modified Copernicus 30 m elevation profile on El-Qarn Island vs Lake Qarun)
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

import h5py
import numpy as np
import rasterio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nisar_pipeline.tiles_and_cogs import compute_pure_sar_water_mask

SEED = 42
PIXEL_AREA_KM2 = (40.0 * 40.0) / 1_000_000.0

DATA_DIR = PROJECT_ROOT / "data"
CUBE_H5_PATH = DATA_DIR / "processed" / "fayoum_gcov_10dates_40m_filtered.h5"
MANIFEST_PATH = DATA_DIR / "subsets" / "phase1_manifest.json"
GUNW_9_DIR = DATA_DIR / "processed" / "gunw_coherence"
BENCH_DIR = DATA_DIR / "benchmarks"
REPORT_PATH = DATA_DIR / "processed" / "sar_water_benchmark_report.json"


def _load_mean_coherence_40m(coh_paths: list[Path], shape: tuple[int, int]) -> np.ndarray:
    """Replicate 80 m GUNW coherence GeoTIFFs to exact 40 m grid and average finite looks."""
    if not coh_paths:
        raise FileNotFoundError("No GUNW coherence GeoTIFFs found for benchmark evaluation.")
    coh_sum = np.zeros(shape, dtype=np.float32)
    coh_cnt = np.zeros(shape, dtype=np.int32)
    for cp in coh_paths:
        with rasterio.open(cp, "r") as src:
            c80 = src.read(1).astype(np.float32)
        c40 = np.repeat(np.repeat(c80, 2, axis=0), 2, axis=1)
        if c40.shape != shape:
            raise ValueError(f"Coherence grid shape mismatch on {cp.name}: {c40.shape} != {shape}")
        fin = np.isfinite(c40)
        coh_sum += np.where(fin, c40, 0.0)
        coh_cnt += fin.astype(np.int32)
    return np.where(coh_cnt > 0, coh_sum / np.maximum(coh_cnt, 1), 1.0)


def compute_binary_confusion_metrics(
    pred: np.ndarray,
    truth: np.ndarray,
    valid: np.ndarray,
) -> dict[str, Any]:
    """Compute exact confusion matrix, IoU, F1, precision, recall, OA, and Cohen's Kappa."""
    p = np.asarray(pred, dtype=bool)
    t = np.asarray(truth, dtype=bool)
    v = np.asarray(valid, dtype=bool)

    valid_n = int(np.sum(v))
    if valid_n <= 0:
        raise AssertionError("Sanity check failed: empty valid evaluation mask.")
    unique_pred = set(np.unique(p[v]).tolist())
    if unique_pred != {False, True}:
        raise AssertionError(f"Sanity check failed: degenerate predictions {unique_pred}")

    tp = int(np.sum(p & t & v))
    fp = int(np.sum(p & (~t) & v))
    fn = int(np.sum((~p) & t & v))
    tn = int(np.sum((~p) & (~t) & v))

    # Strict Sanity-Bound Assertions
    assert tp + fp + fn + tn == valid_n, f"Confusion sum mismatch: {tp+fp+fn+tn} != {valid_n}"

    iou = tp / max(tp + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (2.0 * tp) / max(2 * tp + fp + fn, 1)
    oa = (tp + tn) / valid_n

    p_yes_pred = (tp + fp) / valid_n
    p_yes_true = (tp + fn) / valid_n
    p_no_pred = (tn + fn) / valid_n
    p_no_true = (tn + fp) / valid_n
    pe = p_yes_pred * p_yes_true + p_no_pred * p_no_true
    kappa = (oa - pe) / max(1.0 - pe, 1e-12)

    for metric_name, val in (
        ("iou", iou),
        ("precision", precision),
        ("recall", recall),
        ("f1", f1),
        ("overall_accuracy", oa),
    ):
        assert np.isfinite(val) and 0.0 <= val <= 1.0, f"Out-of-bounds {metric_name}: {val}"
    assert np.isfinite(kappa) and -1.0 <= kappa <= 1.0, f"Out-of-bounds kappa: {kappa}"

    return {
        "valid_pixels": valid_n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "predicted_water_pixels": tp + fp,
        "predicted_water_area_km2": round((tp + fp) * PIXEL_AREA_KM2, 3),
        "truth_water_pixels": tp + fn,
        "truth_water_area_km2": round((tp + fn) * PIXEL_AREA_KM2, 3),
        "iou": round(float(iou), 4),
        "f1": round(float(f1), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "overall_accuracy": round(float(oa), 4),
        "cohens_kappa": round(float(kappa), 4),
    }


def compute_el_qarn_island_mask(
    dswx07: np.ndarray,
    dswx08: np.ndarray,
    dswx09: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
) -> np.ndarray:
    """Isolate El-Qarn Island dry land footprint inside Lake Qarun from consensus OPERA land."""
    from scipy.ndimage import label as nd_label

    ic0 = int(np.argmin(np.abs(xs - 270202.0)))
    ir0 = int(np.argmin(np.abs(ys - 3263662.0)))
    roi = np.zeros(dswx08.shape, dtype=bool)
    roi[max(0, ir0 - 45) : min(dswx08.shape[0], ir0 + 45), max(0, ic0 - 55) : min(dswx08.shape[1], ic0 + 55)] = True
    cand_dry = roi & (dswx07 == 0) & (dswx08 == 0) & (dswx09 == 0)
    ilbl, _ = nd_label(cand_dry)
    cid = int(ilbl[ir0, ic0])
    if cid <= 0:
        raise RuntimeError("Failed to seed El-Qarn Island dry footprint in OPERA consensus mask.")
    return ilbl == cid


def main() -> None:
    """Execute reproducible benchmark evaluation and export structured JSON report."""
    np.random.seed(SEED)
    random.seed(SEED)

    # 1. Load primary NISAR calibrated GCOV cube & baseline mask
    with h5py.File(CUBE_H5_PATH, "r") as h5:
        hh_lin = h5["HHHH_linear_filt"][:]
        hv_lin = h5["HVHV_linear_filt"][:]
        xs = h5["xCoordinates"][:]
        ys = h5["yCoordinates"][:]
        lc = h5["masks/composite_landcover_class"][:]

    shape = hh_lin.shape[1:]
    hh_db_all = 10.0 * np.log10(np.maximum(hh_lin, 1e-6))
    hv_db_all = 10.0 * np.log10(np.maximum(hv_lin, 1e-6))

    # 2. Load 2-pair vs 9-pair GUNW coherences
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    coh2_paths = [
        PROJECT_ROOT / item["files"]["coherence_tif"]["path"]
        for item in manifest["gunw_subsets"]
    ]
    coh9_paths = sorted(GUNW_9_DIR.glob("*_coherenceMagnitude_80m.tif"))
    if len(coh9_paths) != 9:
        raise RuntimeError(f"Expected 9 coherence rasters in {GUNW_9_DIR}, found {len(coh9_paths)}")

    mean_coh_2 = _load_mean_coherence_40m(coh2_paths, shape)
    mean_coh_9 = _load_mean_coherence_40m(coh9_paths, shape)

    # 3. Load NASA benchmark products
    with rasterio.open(BENCH_DIR / "nisar_watermask_40m_fayoum.tif", "r") as s:
        nisar_wm = s.read(1)
    with rasterio.open(BENCH_DIR / "nisar_dem_40m_fayoum.tif", "r") as s:
        nisar_dem = s.read(1)
    with rasterio.open(BENCH_DIR / "opera_dswx_hls_match_20260705_40m_fayoum.tif", "r") as s:
        dswx07 = s.read(1)
    with rasterio.open(BENCH_DIR / "opera_dswx_hls_match_20260810_40m_fayoum.tif", "r") as s:
        dswx08 = s.read(1)
    with rasterio.open(BENCH_DIR / "opera_dswx_hls_match_20260915_40m_fayoum.tif", "r") as s:
        dswx09 = s.read(1)

    # 4. Generate all 4 candidate classification masks deterministically
    mask_v1 = lc == 1
    mask_v2 = compute_pure_sar_water_mask(hh_db_all, hv_db_all, mean_coh_2, xs, ys, mode="v2_blind_fill")
    mask_v3 = compute_pure_sar_water_mask(hh_db_all, hv_db_all, mean_coh_9, xs, ys, mode="v3_coh_island")

    # Option 2 Exploratory Hybrid: Pure NISAR v3 + Rule 2 NISAR_DEM Lake Qarun elevation gate
    y_grid = np.broadcast_to(ys[:, None], shape)
    x_grid = np.broadcast_to(xs[None, :], shape)
    qarun_box = (y_grid > 3255000.0) & (x_grid > 248000.0) & (x_grid < 292000.0)
    dem_valid = nisar_dem > -500.0
    mask_v4 = (mask_v3 & (~(qarun_box & dem_valid & (nisar_dem > -27.8)))) | (
        qarun_box & dem_valid & (nisar_dem <= -28.4) & (mean_coh_9 < 0.25) & (hv_db_all.mean(axis=0) < -19.0)
    )

    models = {
        "v1_baseline_lc1": {
            "label": "v1 Baseline (Phase 2 lc == 1, Rectangular Box-Gated)",
            "data_source": "Pure NISAR (2 GUNW pairs + synthetic basin boxes)",
            "mask": mask_v1,
        },
        "v2_2gunw_blind_fill": {
            "label": "v2 Intermediate (2-Pair GUNW + Blind binary_fill_holes)",
            "data_source": "Pure NISAR (2 GUNW pairs)",
            "mask": mask_v2,
        },
        "v3_pure_nisar_9gunw": {
            "label": "v3 Pure NISAR Upgrade (Option 1: 9-Pair GUNW + Wave stdHH + Island Preservation)",
            "data_source": "100% Pure NISAR (10-Date GCOV + 9-Pair GUNW Coherence)",
            "mask": mask_v3,
        },
        "v4_option2_dem_fusion": {
            "label": "v4 Exploratory Hybrid (Option 2: v3 + NISAR_DEM Basin Gate)",
            "data_source": "NISAR GCOV/GUNW + Rule 2 Ancillary NASA NISAR_DEM v1.2",
            "mask": mask_v4,
        },
    }

    # 5. Authoritative benchmark targets
    valid_op_all = (dswx07 <= 2) & (dswx08 <= 2) & (dswx09 <= 2)
    op_open_consensus = (dswx07 == 1) & (dswx08 == 1) & (dswx09 == 1)
    wm_inland_water = nisar_wm >= 101
    wm_valid = nisar_wm != 255
    el_qarn_island = compute_el_qarn_island_mask(dswx07, dswx08, dswx09, xs, ys)

    # DEM physical profile verification (Lake Qarun open water vs El-Qarn Island)
    qarun_water_dem = nisar_dem[qarun_box & op_open_consensus & dem_valid]
    island_dem = nisar_dem[el_qarn_island & dem_valid]
    dem_profile = {
        "el_qarn_island_pixels": int(np.sum(el_qarn_island)),
        "el_qarn_island_area_km2": round(float(np.sum(el_qarn_island) * PIXEL_AREA_KM2), 3),
        "el_qarn_island_dem_m": {
            "min": round(float(np.min(island_dem)), 2),
            "p25": round(float(np.percentile(island_dem, 25)), 2),
            "median": round(float(np.median(island_dem)), 2),
            "p75": round(float(np.percentile(island_dem, 75)), 2),
            "max": round(float(np.max(island_dem)), 2),
        },
        "lake_qarun_water_dem_m": {
            "p10": round(float(np.percentile(qarun_water_dem, 10)), 2),
            "median": round(float(np.median(qarun_water_dem)), 2),
            "p90": round(float(np.percentile(qarun_water_dem, 90)), 2),
        },
    }

    # 6. Run benchmarks across all 4 classifiers
    results: dict[str, Any] = {}
    date_rasters = {
        "2026-07-05": dswx07,
        "2026-08-10": dswx08,
        "2026-09-15": dswx09,
    }

    for key, spec in models.items():
        m = spec["mask"]
        qarn_fp = int(np.sum(m & el_qarn_island))
        qarn_tot = int(np.sum(el_qarn_island))

        per_date_opera: dict[str, Any] = {}
        for dt_str, dr in date_rasters.items():
            per_date_opera[dt_str] = {
                "open_water_only": compute_binary_confusion_metrics(m, dr == 1, dr <= 2),
                "open_plus_partial_water": compute_binary_confusion_metrics(
                    m, (dr == 1) | (dr == 2), dr <= 2
                ),
            }

        results[key] = {
            "label": spec["label"],
            "data_source": spec["data_source"],
            "el_qarn_island_verification": {
                "island_total_pixels": qarn_tot,
                "island_area_km2": round(qarn_tot * PIXEL_AREA_KM2, 3),
                "false_water_pixels": qarn_fp,
                "false_water_area_km2": round(qarn_fp * PIXEL_AREA_KM2, 3),
                "false_water_rate_pct": round((qarn_fp / qarn_tot) * 100.0, 2),
                "island_correctly_excluded_pct": round(((qarn_tot - qarn_fp) / qarn_tot) * 100.0, 2),
            },
            "vs_opera_dswx_consensus_open_water": compute_binary_confusion_metrics(
                m, op_open_consensus, valid_op_all
            ),
            "vs_nisar_watermask_v050": compute_binary_confusion_metrics(
                m, wm_inland_water, wm_valid
            ),
            "vs_opera_dswx_matched_dates": per_date_opera,
        }

    # Computed best-model summary (strictly computed, never hardcoded)
    pure_sar_keys = ["v1_baseline_lc1", "v2_2gunw_blind_fill", "v3_pure_nisar_9gunw"]
    best_pure_key = max(
        pure_sar_keys,
        key=lambda k: results[k]["vs_opera_dswx_consensus_open_water"]["iou"],
    )
    best_overall_key = max(
        results.keys(),
        key=lambda k: results[k]["vs_opera_dswx_consensus_open_water"]["iou"],
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": SEED,
        "grid": {"height": int(shape[0]), "width": int(shape[1]), "pixel_spacing_m": 40.0},
        "benchmarks": {
            "opera_dswx_hls_v1": {
                "product": "NASA JPL OPERA_L3_DSWX-HLS_V1 (B01_WTR)",
                "matched_dates": ["2026-07-05", "2026-08-10", "2026-09-15"],
                "consensus_valid_pixels": int(np.sum(valid_op_all)),
                "consensus_open_water_pixels": int(np.sum(op_open_consensus & valid_op_all)),
            },
            "nisar_watermask_v050": {
                "product": "NASA NISAR_WATERMASK v0.5.0",
                "inland_water_pixels": int(np.sum(wm_inland_water)),
            },
            "nisar_dem_v12_profile": dem_profile,
        },
        "models": results,
        "computed_comparison_summary": {
            "best_pure_nisar_model": best_pure_key,
            "best_pure_nisar_iou_vs_opera": results[best_pure_key]["vs_opera_dswx_consensus_open_water"]["iou"],
            "best_overall_model": best_overall_key,
            "best_overall_iou_vs_opera": results[best_overall_key]["vs_opera_dswx_consensus_open_water"]["iou"],
            "iou_gain_v3_over_v1": round(
                results["v3_pure_nisar_9gunw"]["vs_opera_dswx_consensus_open_water"]["iou"]
                - results["v1_baseline_lc1"]["vs_opera_dswx_consensus_open_water"]["iou"],
                4,
            ),
            "iou_gain_v3_over_v2": round(
                results["v3_pure_nisar_9gunw"]["vs_opera_dswx_consensus_open_water"]["iou"]
                - results["v2_2gunw_blind_fill"]["vs_opera_dswx_consensus_open_water"]["iou"],
                4,
            ),
            "el_qarn_false_water_reduction_v2_to_v3_pct_pts": round(
                results["v2_2gunw_blind_fill"]["el_qarn_island_verification"]["false_water_rate_pct"]
                - results["v3_pure_nisar_9gunw"]["el_qarn_island_verification"]["false_water_rate_pct"],
                2,
            ),
        },
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Compute-then-narrate raw benchmark printout
    print("=== RAW BENCHMARK RESULTS (SEED = 42) ===")
    print(f"El-Qarn Island (OPERA consensus land, N={dem_profile['el_qarn_island_pixels']} px = {dem_profile['el_qarn_island_area_km2']} km2): DEM={dem_profile['el_qarn_island_dem_m']}")
    print(f"Lake Qarun Water DEM (m): {dem_profile['lake_qarun_water_dem_m']}\n")
    for k, r in results.items():
        op = r["vs_opera_dswx_consensus_open_water"]
        wm_m = r["vs_nisar_watermask_v050"]
        iq = r["el_qarn_island_verification"]
        print(
            f"{k:22s} | IoU_OP={op['iou']:.4f} F1={op['f1']:.4f} P={op['precision']:.4f} R={op['recall']:.4f} "
            f"Kappa={op['cohens_kappa']:.4f} | IoU_WM={wm_m['iou']:.4f} | "
            f"ElQarn_FalseWtr={iq['false_water_pixels']}/{iq['island_total_pixels']} ({iq['false_water_rate_pct']:.2f}%)"
        )
    print("\nComputed Summary:", json.dumps(report["computed_comparison_summary"], indent=2))
    print(f"Saved report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()

