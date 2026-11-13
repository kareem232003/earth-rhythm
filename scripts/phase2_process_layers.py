"""Phase 2: HDF5 Extraction, Radiometric/Geometric Alignment, Mask Generation, Speckle Filtering & ENL Verification.

Executes Phase 2 of the NISAR Surface Change Storyteller pipeline over Option A — Fayoum Oasis:
  1. Programmatically enforces Rule 7 & Rule 8 homogeneity across all 10 GCOV granules.
  2. Computes empirical Equivalent Number of Looks (ENL = mu^2 / sigma^2 in linear power)
     across homogeneous targets at three stages:
       - Stage 0: Native 10m x 10m GCOV
       - Stage 1: 40m x 40m (4x4 linear block-averaged) GCOV
       - Stage 2: 40m x 40m Adaptive Lee (3x3 LMMSE in linear power) & 3x3 Linear Boxcar
  3. Applies 3x3 Adaptive Lee filtering strictly in linear power (gamma0) across all 10 dates,
     then converts to decibels (dB = 10 * log10(gamma0)) and cross-pol ratio (HV/HH dB).
  4. Constructs and documents all geophysical/quality masks (`nodata_or_layover`, `low_snr_nesz`,
     `permanent_water`, `seasonal_water_margin`, `vegetated_agriculture`, `urban_settlement`,
     `stable_desert_reference`) and their exact pixel counts and area shares.
  5. Processes both exploratory L2_GUNW 12-day pairs with strict gamma >= 0.50 coherence masking,
     ionosphere phase screen subtraction, and reference point anchoring.
  6. Exports validated georeferenced GeoTIFFs with embedded Rule 3 & Rule 5 metadata tags,
     a consolidated processed HDF5 data cube, and `data/processed/phase2_processing_report.json`.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.nisar_pipeline.guards import (
    build_rule3_metadata,
    validate_series_homogeneity,
)
from src.nisar_pipeline.insar import process_gunw_pair
from src.nisar_pipeline.masks import build_aoi_landcover_masks
from src.nisar_pipeline.radiometry import (
    boxcar_filter_linear,
    compute_empirical_enl,
    lee_filter_linear,
    linear_to_db,
    log_ratio_db,
)

SUBSET_DIR = ROOT_DIR / "data" / "subsets"
MANIFEST_PATH = SUBSET_DIR / "phase1_manifest.json"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
MASK_TIF_DIR = PROCESSED_DIR / "masks"
GCOV_DB_TIF_DIR = PROCESSED_DIR / "gcov_filtered_db"
GUNW_LOS_TIF_DIR = PROCESSED_DIR / "gunw_los"
CUBE_H5_PATH = PROCESSED_DIR / "fayoum_gcov_10dates_40m_filtered.h5"
REPORT_PATH = PROCESSED_DIR / "phase2_processing_report.json"


def write_tagged_geotiff(
    filepath: Path,
    arr: np.ndarray,
    x_min: float,
    y_max: float,
    dx: float,
    dy: float,
    epsg: int,
    rule3_meta: dict[str, Any],
    nodata: float | int | None = None,
) -> None:
    """Write a georeferenced GeoTIFF with embedded Rule 3 & Rule 5 metadata tags."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    h, w = arr.shape
    transform = from_origin(x_min, y_max, abs(dx), abs(dy))
    profile = {
        "driver": "GTiff",
        "height": h,
        "width": w,
        "count": 1,
        "dtype": arr.dtype,
        "crs": CRS.from_epsg(epsg),
        "transform": transform,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "predictor": 3 if np.issubdtype(arr.dtype, np.floating) else 2,
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(filepath, "w", **profile) as dst:
        dst.write(arr, 1)
        str_tags = {k: str(v) for k, v in rule3_meta.items()}
        dst.update_tags(**str_tags)


def evaluate_enl_benchmarks(
    h5_sample_path: Path,
    hhhh_40m_raw: np.ndarray,
    hvhv_40m_raw: np.ndarray,
    hhhh_40m_lee: np.ndarray,
    hvhv_40m_lee: np.ndarray,
    hhhh_40m_box: np.ndarray,
    x_40m: np.ndarray,
    y_40m: np.ndarray,
) -> dict[str, Any]:
    """Compute empirical ENL across homogeneous targets at Stage 0 (10m), Stage 1 (40m), and Stage 2 (filtered)."""
    with h5py.File(h5_sample_path, "r") as hf:
        g_nat = hf["science/LSAR/GCOV/grids/frequencyA_native_10m"]
        hh_10m = g_nat["HHHH"][:]
        hv_10m = g_nat["HVHV"][:]
        x_10m = g_nat["xCoordinates"][:]
        y_10m = g_nat["yCoordinates"][:]

    # 1. Homogeneous Lake Qarun Open Water patch inside the 1024x1024 native 10m patch:
    #    UTM X: [268000, 270000], Y: [3259500, 3261500] (2 km x 2 km homogeneous water)
    w10_r = (y_10m >= 3259500.0) & (y_10m <= 3261500.0)
    w10_c = (x_10m >= 268000.0) & (x_10m <= 270000.0)
    w40_r = (y_40m >= 3259500.0) & (y_40m <= 3261500.0)
    w40_c = (x_40m >= 268000.0) & (x_40m <= 270000.0)

    # 2. Homogeneous Desert Margin inside the 10m native patch (North shore desert plateau):
    #    UTM X: [265500, 267000], Y: [3261200, 3262100] (used for both 10m and 40m apples-to-apples comparison)
    d10_r = (y_10m >= 3261200.0) & (y_10m <= 3262100.0)
    d10_c = (x_10m >= 265500.0) & (x_10m <= 267000.0)
    d40_r = (y_40m >= 3261200.0) & (y_40m <= 3262100.0)
    d40_c = (x_40m >= 265500.0) & (x_40m <= 267000.0)

    return {
        "homogeneous_water_patch_utm": [268000.0, 3259500.0, 270000.0, 3261500.0],
        "homogeneous_desert_patch_utm": [265500.0, 3261200.0, 267000.0, 3262100.0],
        "stage0_native_10m": {
            "water_HH": compute_empirical_enl(hh_10m[np.ix_(w10_r, w10_c)]),
            "water_HV": compute_empirical_enl(hv_10m[np.ix_(w10_r, w10_c)]),
            "desert_HH": compute_empirical_enl(hh_10m[np.ix_(d10_r, d10_c)]),
            "desert_HV": compute_empirical_enl(hv_10m[np.ix_(d10_r, d10_c)]),
        },
        "stage1_multilook_40m_raw": {
            "water_HH": compute_empirical_enl(hhhh_40m_raw[np.ix_(w40_r, w40_c)]),
            "water_HV": compute_empirical_enl(hvhv_40m_raw[np.ix_(w40_r, w40_c)]),
            "desert_HH": compute_empirical_enl(hhhh_40m_raw[np.ix_(d40_r, d40_c)]),
            "desert_HV": compute_empirical_enl(hvhv_40m_raw[np.ix_(d40_r, d40_c)]),
        },
        "stage2_filtered_40m_adaptive_lee_3x3": {
            "water_HH": compute_empirical_enl(hhhh_40m_lee[np.ix_(w40_r, w40_c)]),
            "water_HV": compute_empirical_enl(hvhv_40m_lee[np.ix_(w40_r, w40_c)]),
            "desert_HH": compute_empirical_enl(hhhh_40m_lee[np.ix_(d40_r, d40_c)]),
            "desert_HV": compute_empirical_enl(hvhv_40m_lee[np.ix_(d40_r, d40_c)]),
        },
        "stage2_filtered_40m_boxcar_3x3": {
            "water_HH": compute_empirical_enl(hhhh_40m_box[np.ix_(w40_r, w40_c)]),
            "desert_HH": compute_empirical_enl(hhhh_40m_box[np.ix_(d40_r, d40_c)]),
        },
    }


def main() -> None:
    """Execute Phase 2 layer validation, alignment, speckle filtering, masking, and GUNW evaluation."""
    t_start = time.time()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as mf:
        manifest = json.load(mf)

    gcov_records = manifest["gcov_subsets"]
    gunw_records = manifest["gunw_subsets"]

    # 1. Enforce Rule 7 & Rule 8 Series Homogeneity Guard
    print("[STEP 1] Validating Rule 7 & Rule 8 homogeneity across all 10 GCOV granules...")
    validate_series_homogeneity(gcov_records)
    print("  PASS: All 10 GCOV granules share identical Track (129), Frame (016), Ascending, CRID (P05023), Version (1.0.11), EPSG:32636, and (1560, 1968) grid.")

    # 2. Load 10-date linear-power GCOV stack and verify exact coordinate grid alignment
    t_count = len(gcov_records)
    h, w = gcov_records[0]["multilook_window_shape_40m"]
    epsg = int(gcov_records[0]["epsg"])
    utm_x_min, utm_y_min, utm_x_max, utm_y_max = gcov_records[0]["utm_bounds"]

    hhhh_raw_stack = np.empty((t_count, h, w), dtype=np.float32)
    hvhv_raw_stack = np.empty((t_count, h, w), dtype=np.float32)
    hhhh_lee_stack = np.empty((t_count, h, w), dtype=np.float32)
    hvhv_lee_stack = np.empty((t_count, h, w), dtype=np.float32)
    hhhh_db_stack = np.empty((t_count, h, w), dtype=np.float32)
    hvhv_db_stack = np.empty((t_count, h, w), dtype=np.float32)
    hv_hh_ratio_db_stack = np.empty((t_count, h, w), dtype=np.float32)
    mask_stack = np.empty((t_count, h, w), dtype=np.uint8)

    dates_iso: list[str] = []
    granule_ids: list[str] = []
    ref_x: np.ndarray | None = None
    ref_y: np.ndarray | None = None
    dx_40m = 40.0
    dy_40m = -40.0
    nesz_hh_median_lin = 0.00472
    nesz_hv_median_lin = 0.00353

    print("[STEP 2] Applying 3x3 Adaptive Lee speckle filter strictly in linear power (gamma0) across 10 dates...")
    enl_report: dict[str, Any] = {}
    exported_gcov_layers: list[dict[str, Any]] = []

    for idx, rec in enumerate(gcov_records):
        h5_path = ROOT_DIR / rec["files"]["h5_subset"]["path"]
        date_str = rec["date"]
        gid = rec["granule_id"]
        dates_iso.append(date_str)
        granule_ids.append(gid)

        with h5py.File(h5_path, "r") as hf:
            g = hf["science/LSAR/GCOV/grids/frequencyA"]
            hh_lin = g["HHHH"][:]
            hv_lin = g["HVHV"][:]
            msk = g["mask"][:]
            x_c = g["xCoordinates"][:]
            y_c = g["yCoordinates"][:]
            dx_40m = float(g["xCoordinateSpacing"][()])
            dy_40m = float(g["yCoordinateSpacing"][()])

            if ref_x is None:
                ref_x = x_c
                ref_y = y_c
                nesz_grp = hf["science/LSAR/GCOV/metadata/calibrationInformation/frequencyA/noiseEquivalentBackscatter"]
                nesz_hh_median_lin = float(np.nanmedian(nesz_grp["HH"][:]))
                nesz_hv_median_lin = float(np.nanmedian(nesz_grp["HV"][:]))
            else:
                if not (np.array_equal(ref_x, x_c) and np.array_equal(ref_y, y_c)):
                    raise ValueError(f"Coordinate grid mismatch on {date_str} ({gid})!")

        # Speckle filtering strictly in linear power (Rule 4)
        hh_lee = lee_filter_linear(hh_lin, window_size=3, enl_prior=25.0)
        hv_lee = lee_filter_linear(hv_lin, window_size=3, enl_prior=25.0)

        # Convert to dB ONLY after linear-power speckle filtering
        hh_db = linear_to_db(hh_lee)
        hv_db = linear_to_db(hv_lee)
        ratio_db = log_ratio_db(hh_lee, hv_lee)  # 10 * log10(HV / HH) = HV_dB - HH_dB

        hhhh_raw_stack[idx] = hh_lin
        hvhv_raw_stack[idx] = hv_lin
        hhhh_lee_stack[idx] = hh_lee
        hvhv_lee_stack[idx] = hv_lee
        hhhh_db_stack[idx] = hh_db
        hvhv_db_stack[idx] = hv_db
        hv_hh_ratio_db_stack[idx] = ratio_db
        mask_stack[idx] = msk

        # Compute multi-stage ENL benchmark on the reference acquisition (2026-10-21, idx == t_count - 1)
        if idx == t_count - 1 and ref_x is not None and ref_y is not None:
            hh_box = boxcar_filter_linear(hh_lin, window_size=3)
            enl_report = evaluate_enl_benchmarks(
                h5_sample_path=h5_path,
                hhhh_40m_raw=hh_lin,
                hvhv_40m_raw=hv_lin,
                hhhh_40m_lee=hh_lee,
                hvhv_40m_lee=hv_lee,
                hhhh_40m_box=hh_box,
                x_40m=ref_x,
                y_40m=ref_y,
            )

        # Export validated Rule-3 tagged dB GeoTIFFs for HH and HV
        date_compact = date_str.replace("-", "")
        hh_tif_path = GCOV_DB_TIF_DIR / f"NISAR_L2_GCOV_T129_F016_{date_compact}_HH_gamma0_dB_40m.tif"
        hv_tif_path = GCOV_DB_TIF_DIR / f"NISAR_L2_GCOV_T129_F016_{date_compact}_HV_gamma0_dB_40m.tif"

        meta_hh = build_rule3_metadata(
            product_type="NISAR_L2_GCOV_PROVISIONAL_V1",
            product_version=f"PROVISIONAL CRID {rec['crid']} / Ver {rec['product_version']} (PGE R05.02.3)",
            acquisition_date=rec["zero_doppler_start_time"],
            track=rec["track"],
            frame=rec["frame"],
            orbit_direction=rec["orbit_direction"],
            polarization="HH (HHHH gamma0)",
            units="dB (10*log10 gamma0)",
            crs=f"EPSG:{epsg}",
            source=f"NASA ASF DAAC | {gid}",
            epistemic_tag="OBSERVATION",
            extra={
                "speckle_filter": "4x4 linear block average (10m->40m) + 3x3 Adaptive Lee in linear power",
                "conversion_formula": "10 * log10(gamma0_linear_filtered)",
            },
        )
        meta_hv = build_rule3_metadata(
            product_type="NISAR_L2_GCOV_PROVISIONAL_V1",
            product_version=f"PROVISIONAL CRID {rec['crid']} / Ver {rec['product_version']} (PGE R05.02.3)",
            acquisition_date=rec["zero_doppler_start_time"],
            track=rec["track"],
            frame=rec["frame"],
            orbit_direction=rec["orbit_direction"],
            polarization="HV (HVHV gamma0)",
            units="dB (10*log10 gamma0)",
            crs=f"EPSG:{epsg}",
            source=f"NASA ASF DAAC | {gid}",
            epistemic_tag="OBSERVATION",
            extra={
                "speckle_filter": "4x4 linear block average (10m->40m) + 3x3 Adaptive Lee in linear power",
                "conversion_formula": "10 * log10(gamma0_linear_filtered)",
            },
        )
        write_tagged_geotiff(hh_tif_path, hh_db, utm_x_min, utm_y_max, dx_40m, dy_40m, epsg, meta_hh, nodata=np.nan)
        write_tagged_geotiff(hv_tif_path, hv_db, utm_x_min, utm_y_max, dx_40m, dy_40m, epsg, meta_hv, nodata=np.nan)

        exported_gcov_layers.append(
            {
                "date": date_str,
                "granule_id": gid,
                "hh_db_tif": str(hh_tif_path.relative_to(ROOT_DIR).as_posix()),
                "hv_db_tif": str(hv_tif_path.relative_to(ROOT_DIR).as_posix()),
                "rule3_metadata_hh": meta_hh,
                "rule3_metadata_hv": meta_hv,
            }
        )
        print(f"  Processed & tagged {date_str} ({gid})")

    assert ref_x is not None and ref_y is not None

    # 3. Build and document geophysical & quality masks across the 10-date stack
    print("[STEP 3] Generating and documenting geophysical & quality masks...")
    coh_grids = []
    for grec in gunw_records:
        gh5_p = ROOT_DIR / grec["files"]["h5_subset"]["path"]
        with h5py.File(gh5_p, "r") as ghf:
            coh_grids.append(
                ghf["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/coherenceMagnitude"][:]
            )
    mean_coh_80m = np.nanmean(np.stack(coh_grids, axis=0), axis=0)
    mean_coh_40m = np.repeat(np.repeat(mean_coh_80m, 2, axis=0), 2, axis=1)

    masks, mask_summary = build_aoi_landcover_masks(
        hhhh_stack_linear=hhhh_lee_stack,
        hvhv_stack_linear=hvhv_lee_stack,
        nisar_mask_stack=mask_stack,
        x_coords=ref_x,
        y_coords=ref_y,
        mean_coherence_40m=mean_coh_40m,
        nesz_hh_median_linear=nesz_hh_median_lin,
        nesz_hv_median_linear=nesz_hv_median_lin,
    )

    for m_name, m_arr in masks.items():
        m_path = MASK_TIF_DIR / f"fayoum_{m_name}_40m.tif"
        m_meta = build_rule3_metadata(
            product_type="NISAR_L2_GCOV_PROVISIONAL_V1 Derived Mask",
            product_version="PROVISIONAL CRID P05023 / Ver 1.0.11 (10-Date Stack)",
            acquisition_date="2026-06-23 to 2026-10-21 (10 epochs)",
            track=129,
            frame=16,
            orbit_direction="Ascending",
            polarization="Dual-Pol HH+HV (DHDH)",
            units="categorical mask (uint8)",
            crs=f"EPSG:{epsg}",
            source="NASA ASF DAAC | 10-Date Track 129 Frame 016 Stack",
            epistemic_tag="OBSERVATION",
            extra={"mask_name": m_name},
        )
        write_tagged_geotiff(m_path, m_arr, utm_x_min, utm_y_max, dx_40m, dy_40m, epsg, m_meta, nodata=None)

    for m_key, m_info in mask_summary["masks"].items():
        print(
            f"  Mask `{m_key}`: {m_info['pixel_count']:,} px ({m_info['pixel_share_pct']}% | {m_info['area_km2']} km^2)"
        )

    # 4. Save consolidated multi-temporal HDF5 cube for instant Phase 3 change detection & time-series queries
    print("[STEP 4] Writing consolidated multi-temporal calibrated HDF5 cube...")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with h5py.File(CUBE_H5_PATH, "w") as cf:
        cf.attrs["crs"] = f"EPSG:{epsg}"
        cf.attrs["utm_bounds"] = [utm_x_min, utm_y_min, utm_x_max, utm_y_max]
        cf.attrs["nesz_hh_median_db"] = round(float(10.0 * np.log10(nesz_hh_median_lin)), 2)
        cf.attrs["nesz_hv_median_db"] = round(float(10.0 * np.log10(nesz_hv_median_lin)), 2)
        cf.create_dataset("dates", data=np.array(dates_iso, dtype="S10"))
        cf.create_dataset("granule_ids", data=np.array(granule_ids, dtype="S95"))
        cf.create_dataset("xCoordinates", data=ref_x)
        cf.create_dataset("yCoordinates", data=ref_y)
        cf.create_dataset("HHHH_linear_filt", data=hhhh_lee_stack, compression="gzip", compression_opts=4, shuffle=True)
        cf.create_dataset("HVHV_linear_filt", data=hvhv_lee_stack, compression="gzip", compression_opts=4, shuffle=True)
        m_grp = cf.create_group("masks")
        for m_name, m_arr in masks.items():
            m_grp.create_dataset(m_name, data=m_arr, compression="gzip", compression_opts=4)

    # 5. Process exploratory L2_GUNW pairs & evaluate coherence by land-cover mask (Change Type B evaluation)
    print("[STEP 5] Processing exploratory L2_GUNW pairs & evaluating coherence by land-cover class...")
    # Downsample 40m land-cover masks to 80m GUNW grid (exact 2x2 block stride) for coherence stratification
    gunw_evaluations: list[dict[str, Any]] = []
    for grec in gunw_records:
        pair_str = grec["pair"]
        gid = grec["granule_id"]
        gh5_path = ROOT_DIR / grec["files"]["h5_subset"]["path"]
        with h5py.File(gh5_path, "r") as ghf:
            unw_grp = ghf["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"]
            hh_grp = unw_grp["HH"]
            unw_phase = hh_grp["unwrappedPhase"][:]
            coh_mag = hh_grp["coherenceMagnitude"][:]
            iono_phase = hh_grp["ionospherePhaseScreen"][:]
            conn_comp = hh_grp["connectedComponents"][:]
            gx = hh_grp["xCoordinates"][:]
            gy = hh_grp["yCoordinates"][:]
            gdx = float(hh_grp["xCoordinateSpacing"][()])
            gdy = float(hh_grp["yCoordinateSpacing"][()])
            cfreq = float(ghf["science/LSAR/GUNW/grids/frequencyA/centerFrequency"][()])

        los_m, los_stats = process_gunw_pair(
            unwrapped_phase_rad=unw_phase,
            coherence_mag=coh_mag,
            ionosphere_phase_rad=iono_phase,
            connected_components=conn_comp,
            x_coords=gx,
            y_coords=gy,
            center_frequency_hz=cfreq,
            coherence_threshold=0.50,
            ref_utm_xy=(292000.0, 3244000.0),
        )

        # Stratify coherence and LOS apparent displacement std across land-cover classes (at 80m resolution)
        class_80m = masks["composite_landcover_class"][::2, ::2]
        zone_coherence_breakdown = {}
        for cls_id, cls_name in [
            (4, "Urban_Settlement"),
            (5, "Stable_Consolidated_Desert"),
            (3, "Vegetated_Agriculture"),
            (2, "Seasonal_Water_Margin"),
            (1, "Permanent_Open_Water"),
            (6, "Low_SNR_Sand_Sheet"),
        ]:
            cmask = class_80m == cls_id
            c_vals = coh_mag[cmask & np.isfinite(coh_mag)]
            los_vals = los_m[cmask & np.isfinite(los_m)]
            zone_coherence_breakdown[cls_name] = {
                "pixel_count_80m": int(np.sum(cmask)),
                "median_coherence": round(float(np.median(c_vals)), 3) if c_vals.size > 0 else None,
                "pct_coherent_ge_0_5": round(float(np.mean(c_vals >= 0.50) * 100.0), 2) if c_vals.size > 0 else 0.0,
                "los_std_mm_over_coherent_pixels": round(float(np.std(los_vals) * 1000.0), 2)
                if los_vals.size > 10
                else None,
                "los_p05_p50_p95_mm": [round(float(x * 1000.0), 1) for x in np.percentile(los_vals, [5, 50, 95])]
                if los_vals.size > 10
                else None,
            }

        pair_compact = pair_str.replace("-", "")
        los_tif_path = GUNW_LOS_TIF_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_compact}_LOS_displacement_m_coh050_80m.tif"
        los_meta = build_rule3_metadata(
            product_type="NISAR_L2_GUNW_PROVISIONAL_V1 (Exploratory InSAR)",
            product_version=f"PROVISIONAL CRID {grec['crid']} / Ver {grec['product_version']} (PGE R05.02.3)",
            acquisition_date=pair_str,
            track=129,
            frame=16,
            orbit_direction="Ascending",
            polarization="HH (SH 40 MHz)",
            units="meters LOS",
            crs=f"EPSG:{epsg}",
            source=f"NASA ASF DAAC | {gid}",
            epistemic_tag="OBSERVATION",
            extra={
                "coherence_mask": "gamma >= 0.50 and connectedComponents > 0 (gamma < 0.50 masked to NaN: UNRELIABLE)",
                "reference_point_utm_32636": f"Easting {los_stats['reference_utm_easting_m']}m, Northing {los_stats['reference_utm_northing_m']}m (Fayoum Urban Core Benchmark)",
                "ionosphere_correction": "ionospherePhaseScreen subtracted prior to reference anchoring",
                "exploratory_warning": "12-day L-band phase variations (~10-25 mm std) are dominated by tropospheric water vapor and soil moisture dielectric phase, NOT tectonic/compaction subsidence rates.",
            },
        )
        write_tagged_geotiff(los_tif_path, los_m, utm_x_min, utm_y_max, gdx, gdy, epsg, los_meta, nodata=np.nan)

        gunw_evaluations.append(
            {
                "pair": pair_str,
                "granule_id": gid,
                "los_geotiff": str(los_tif_path.relative_to(ROOT_DIR).as_posix()),
                "rule3_metadata": los_meta,
                "overall_los_stats": los_stats,
                "landcover_coherence_breakdown": zone_coherence_breakdown,
            }
        )
        print(
            f"  Processed GUNW {pair_str}: Coherent >= 0.50 = {los_stats['valid_coherent_pixel_pct']}% | "
            f"Urban median gamma = {zone_coherence_breakdown['Urban_Settlement']['median_coherence']} | "
            f"Desert LOS std = {zone_coherence_breakdown['Stable_Consolidated_Desert']['los_std_mm_over_coherent_pixels']} mm"
        )

    report = {
        "phase": "Phase 2 — Radiometric/Geometric Alignment, Masking, Speckle Filtering & ENL Report",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "crs_validation": {
            "epsg": epsg,
            "crs_name": "WGS 84 / UTM zone 36N",
            "utm_bounds_m": [utm_x_min, utm_y_min, utm_x_max, utm_y_max],
            "grid_shape_40m": [h, w],
            "pixel_spacing_m": [dx_40m, dy_40m],
            "gunw_grid_shape_80m": [h // 2, w // 2],
            "gunw_pixel_spacing_m": [80.0, -80.0],
            "all_10_dates_co_registered_exact": True,
        },
        "radiometric_calibration": {
            "quantity": "Radiometrically Terrain-Corrected (RTC) Gamma-Nought (gamma0)",
            "filtering_domain": "Linear power (m^2/m^2) strictly prior to dB conversion",
            "db_conversion_formula": "10 * log10(gamma0_linear)",
            "nesz_hh_median_db": round(float(10.0 * np.log10(nesz_hh_median_lin)), 2),
            "nesz_hv_median_db": round(float(10.0 * np.log10(nesz_hv_median_lin)), 2),
        },
        "speckle_and_enl_verification": enl_report,
        "mask_documentation": mask_summary,
        "exported_gcov_layers_count": len(exported_gcov_layers),
        "exported_gcov_layers": exported_gcov_layers,
        "exploratory_gunw_evaluation": gunw_evaluations,
        "consolidated_cube_h5": str(CUBE_H5_PATH.relative_to(ROOT_DIR).as_posix()),
        "consolidated_cube_size_mb": round(CUBE_H5_PATH.stat().st_size / (1024 * 1024), 2),
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as rf:
        json.dump(report, rf, indent=2)

    print(f"\n=== PHASE 2 PROCESSING COMPLETE in {time.time() - t_start:.1f}s ===")
    print(f"Consolidated Cube: {CUBE_H5_PATH} ({report['consolidated_cube_size_mb']} MB)")
    print(f"Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
