"""Phase 1: Authenticated HTTP Windowed Range-Read Extraction for NISAR L2 GCOV & GUNW.

Extracts spatially aligned subsets over Option A — Fayoum Oasis (Track 129, Frame 016,
Ascending, CRID P05023 / PGE R05.02.3) using NASA Earthdata authenticated HTTP range
requests (`earthaccess` + `h5py` chunk offset tables) without downloading full 6.35 GB
granules.

Outputs (< 500 MB total):
  - `data/subsets/gcov/*.h5`: Self-contained HDF5 subsets for all 10 GCOV dates containing:
      * Full-AOI 40m (4x4 linear-power multilooked) grids (`HHHH`, `HVHV`, `mask`, `numberOfLooks`)
      * Native 10m (1024x1024 un-multilooked) reference window (`grids/frequencyA_native_10m/*`)
      * Calibration (`noiseEquivalentBackscatter`) & `/science/LSAR/identification` metadata
  - `data/subsets/gcov_tif/*.tif`: Compressed GeoTIFFs (`HHHH`, `HVHV`, `mask`) for all 10 dates
  - `data/subsets/gunw/*.h5` & `data/subsets/gunw_tif/*.tif`: 2 exploratory L2_GUNW pairs
    (`unwrappedPhase`, `coherenceMagnitude`, `ionospherePhaseScreen`, `connectedComponents`, `mask`)
  - `data/subsets/phase1_manifest.json`: Complete provenance, SHA256 checksums, dimensions, and stats.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dotenv
import earthaccess
import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from requests.adapters import HTTPAdapter

# Fixed UTM Zone 36N (EPSG:32636) bounding box covering Fayoum Oasis:
# Retains Lake Qarun, Upper & Lower Wadi El Rayan Lakes, central irrigated agriculture,
# Fayoum urban core, and surrounding hyper-arid desert margins.
# Exact multiple of 10m (GCOV native), 40m (GCOV 4x4 linear multilook), and 80m (GUNW native).
EPSG_CODE = 32636
UTM_X_MIN = 237280.0
UTM_X_MAX = 316000.0  # Span = 78,720 m -> 7872 px @ 10m, 1968 px @ 40m, 984 px @ 80m
UTM_Y_MIN = 3215040.0
UTM_Y_MAX = 3277440.0  # Span = 62,400 m -> 6240 px @ 10m, 1560 px @ 40m, 780 px @ 80m

# Native 10m full-resolution reference sub-window (1024 x 1024 pixels = 10.24 km x 10.24 km)
# Spans the southern shore of Lake Qarun, adjacent irrigated cropland, and northern desert edge.
NATIVE_PATCH_X_MIN = 265000.0
NATIVE_PATCH_X_MAX = 275240.0  # 1024 px @ 10m
NATIVE_PATCH_Y_MIN = 3252000.0
NATIVE_PATCH_Y_MAX = 3262240.0  # 1024 px @ 10m

MULTILOOK_FACTOR = 4  # 4x4 linear-power block average (10m -> 40m)

ROOT_DIR = Path(__file__).resolve().parent.parent
SUBSET_DIR = ROOT_DIR / "data" / "subsets"
GCOV_H5_DIR = SUBSET_DIR / "gcov"
GCOV_TIF_DIR = SUBSET_DIR / "gcov_tif"
GUNW_H5_DIR = SUBSET_DIR / "gunw"
GUNW_TIF_DIR = SUBSET_DIR / "gunw_tif"
MANIFEST_PATH = SUBSET_DIR / "phase1_manifest.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hex digest of a local file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def decode_h5_scalar(val: Any) -> Any:
    """Convert HDF5 scalar or byte string into native Python JSON-serializable value."""
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, np.ndarray):
        if val.ndim == 0:
            return decode_h5_scalar(val.item())
        return [decode_h5_scalar(x) for x in val.tolist()]
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


def unshuffle_and_decompress(
    raw_bytes: bytes,
    dtype: np.dtype,
    chunk_shape: tuple[int, int],
    shuffle: bool = True,
) -> np.ndarray:
    """Decompress a gzip-compressed HDF5 chunk and reverse HDF5 byte-shuffle."""
    decomp = zlib.decompress(raw_bytes)
    itemsize = dtype.itemsize
    if shuffle and itemsize > 1:
        arr_u8 = np.frombuffer(decomp, dtype=np.uint8)
        unshuffled = arr_u8.reshape(itemsize, -1).T.copy()
        return unshuffled.view(dtype).reshape(chunk_shape)
    return np.frombuffer(decomp, dtype=dtype).copy().reshape(chunk_shape)


def fetch_byte_range_with_retry(
    session: Any,
    signed_url: str,
    start_byte: int,
    end_byte: int,
    max_retries: int = 4,
) -> bytes:
    """Fetch an inclusive byte range [start_byte, end_byte] over HTTPS with retry."""
    headers = {"Range": f"bytes={start_byte}-{end_byte}"}
    for attempt in range(max_retries):
        try:
            resp = session.get(signed_url, headers=headers, timeout=60)
            if resp.status_code in (200, 206):
                return resp.content
            raise RuntimeError(f"HTTP {resp.status_code} for range {start_byte}-{end_byte}")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("Unreachable")


def read_window_via_coalesced_chunks(
    ds: h5py.Dataset,
    session: Any,
    signed_url: str,
    r0: int,
    r1: int,
    c0: int,
    c1: int,
    max_workers: int = 12,
) -> np.ndarray:
    """Read a 2D slice [r0:r1, c0:c1] from a chunked remote HDF5 dataset using parallel row-range reads."""
    chunk_h, chunk_w = ds.chunks
    dtype = ds.dtype
    shuffle = bool(ds.shuffle)
    out_h = r1 - r0
    out_w = c1 - c0
    out = np.empty((out_h, out_w), dtype=dtype)

    r_chunk_starts = list(range((r0 // chunk_h) * chunk_h, ((r1 - 1) // chunk_h + 1) * chunk_h, chunk_h))
    c_chunk_starts = list(range((c0 // chunk_w) * chunk_w, ((c1 - 1) // chunk_w + 1) * chunk_w, chunk_w))

    # Build chunk metadata table per chunk-row (fast in-memory B-tree lookup)
    row_specs = []
    for rc in r_chunk_starts:
        c_infos = []
        for cc in c_chunk_starts:
            info = ds.id.get_chunk_info_by_coord((rc, cc))
            c_infos.append((cc, info.byte_offset, info.size, info.filter_mask))
        # Group into contiguous or near-contiguous spans (gap <= 512 KB)
        spans = []
        cur_span = [c_infos[0]]
        for item in c_infos[1:]:
            prev_end = cur_span[-1][1] + cur_span[-1][2]
            if 0 <= (item[1] - prev_end) <= 524288:
                cur_span.append(item)
            else:
                spans.append(cur_span)
                cur_span = [item]
        spans.append(cur_span)
        for sp in spans:
            row_specs.append((rc, sp))

    def _process_span(rc: int, span: list[tuple[int, int, int, int]]) -> list[tuple[int, int, np.ndarray]]:
        span_start = span[0][1]
        span_end = span[-1][1] + span[-1][2] - 1
        buf = fetch_byte_range_with_retry(session, signed_url, span_start, span_end)
        decoded_chunks = []
        for cc, boff, bsize, _ in span:
            rel_start = boff - span_start
            raw_chunk = buf[rel_start : rel_start + bsize]
            arr_chunk = unshuffle_and_decompress(raw_chunk, dtype, (chunk_h, chunk_w), shuffle=shuffle)
            decoded_chunks.append((rc, cc, arr_chunk))
        return decoded_chunks

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_process_span, rc, sp) for rc, sp in row_specs]
        for fut in as_completed(futures):
            for rc, cc, arr_chunk in fut.result():
                # Intersection of chunk [rc:rc+chunk_h, cc:cc+chunk_w] with target [r0:r1, c0:c1]
                sr0 = max(r0, rc)
                sr1 = min(r1, rc + chunk_h)
                sc0 = max(c0, cc)
                sc1 = min(c1, cc + chunk_w)
                out[sr0 - r0 : sr1 - r0, sc0 - c0 : sc1 - c0] = arr_chunk[
                    sr0 - rc : sr1 - rc, sc0 - cc : sc1 - cc
                ]

    return out


def multilook_linear_block_average(
    power_arr: np.ndarray,
    mask_arr: np.ndarray,
    factor: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Perform mask-aware block averaging strictly in linear power (gamma0).

    Valid pixels require:
      - `np.isfinite(power_arr)` and `power_arr > 0`
      - `mask_arr > 0` and `mask_arr != 255` (valid subswath indicator, not radar shadow/layover/fill)
    Returns:
      - `ml_power`: float32 array of shape (H//factor, W//factor) with NaN where no valid pixels exist
      - `valid_fraction`: float32 array in [0, 1] giving fraction of valid native pixels per block
    """
    h, w = power_arr.shape
    nh, nw = h // factor, w // factor
    trimmed_p = power_arr[: nh * factor, : nw * factor]
    trimmed_m = mask_arr[: nh * factor, : nw * factor]

    # NISAR GCOV mask convention: 1..N = valid subswath ID; 0 or 255 = invalid/fill; >10 = shadow/layover
    valid = np.isfinite(trimmed_p) & (trimmed_p > 0.0) & (trimmed_m >= 1) & (trimmed_m < 10)
    p_clean = np.where(valid, trimmed_p, 0.0).astype(np.float64)

    p_blocks = p_clean.reshape(nh, factor, nw, factor)
    v_blocks = valid.reshape(nh, factor, nw, factor)

    v_count = v_blocks.sum(axis=(1, 3))
    p_sum = p_blocks.sum(axis=(1, 3))

    with np.errstate(divide="ignore", invalid="ignore"):
        ml_power = np.where(v_count > 0, p_sum / v_count, np.nan).astype(np.float32)
    valid_frac = (v_count / float(factor * factor)).astype(np.float32)
    return ml_power, valid_frac


def multilook_mask(mask_arr: np.ndarray, valid_frac: np.ndarray, factor: int = 4) -> np.ndarray:
    """Downsample uint8 mask array conservatively to match multilooked grid."""
    h, w = mask_arr.shape
    nh, nw = h // factor, w // factor
    trimmed_m = mask_arr[: nh * factor, : nw * factor]
    m_blocks = trimmed_m.reshape(nh, factor, nw, factor)
    # Take max valid subswath if valid_frac >= 0.5, else 0 (invalid)
    center_m = m_blocks[:, factor // 2, :, factor // 2]
    return np.where(valid_frac >= 0.5, np.where((center_m >= 1) & (center_m < 10), center_m, 1), 0).astype(
        np.uint8
    )


def write_geotiff(
    filepath: Path,
    arr: np.ndarray,
    x_min: float,
    y_max: float,
    dx: float,
    dy: float,
    epsg: int = EPSG_CODE,
    nodata: float | int | None = None,
) -> None:
    """Write a 2D array to a compressed Cloud-Optimized/tiled GeoTIFF."""
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


def compute_sample_stats(hhhh: np.ndarray, hvhv: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    """Compute linear and dB summary statistics over valid pixels for QA verification."""
    valid = np.isfinite(hhhh) & (hhhh > 0) & np.isfinite(hvhv) & (hvhv > 0) & (mask >= 1) & (mask < 10)
    valid_pct = float(np.mean(valid) * 100.0)
    hh_val = hhhh[valid]
    hv_val = hvhv[valid]
    hh_db = 10.0 * np.log10(hh_val)
    hv_db = 10.0 * np.log10(hv_val)
    return {
        "valid_pixel_pct": round(valid_pct, 2),
        "valid_pixel_count": int(np.sum(valid)),
        "hhhh_linear_p05_p50_p95": [round(float(x), 6) for x in np.percentile(hh_val, [5, 50, 95])],
        "hvhv_linear_p05_p50_p95": [round(float(x), 6) for x in np.percentile(hv_val, [5, 50, 95])],
        "hhhh_db_p05_p50_p95": [round(float(x), 2) for x in np.percentile(hh_db, [5, 50, 95])],
        "hvhv_db_p05_p50_p95": [round(float(x), 2) for x in np.percentile(hv_db, [5, 50, 95])],
        "hv_hh_ratio_db_median": round(float(np.median(hv_db - hh_db)), 2),
    }


def extract_gcov_granule(granule: Any, session: Any, f_obj: Any = None) -> dict[str, Any]:
    """Extract and cache a single NISAR L2 GCOV granule subset via HTTP range reads."""
    granule_id = granule["umm"]["GranuleUR"]
    data_url = granule.data_links()[0]
    acq_date = granule_id.split("_")[11][:8]
    date_iso = f"{acq_date[:4]}-{acq_date[4:6]}-{acq_date[6:8]}"

    out_h5_path = GCOV_H5_DIR / f"NISAR_L2_GCOV_T129_F016_{acq_date}_subset.h5"
    tif_hh_path = GCOV_TIF_DIR / f"NISAR_L2_GCOV_T129_F016_{acq_date}_HHHH_40m.tif"
    tif_hv_path = GCOV_TIF_DIR / f"NISAR_L2_GCOV_T129_F016_{acq_date}_HVHV_40m.tif"
    tif_mask_path = GCOV_TIF_DIR / f"NISAR_L2_GCOV_T129_F016_{acq_date}_mask_40m.tif"

    if out_h5_path.exists() and tif_hh_path.exists() and tif_hv_path.exists() and tif_mask_path.exists():
        print(f"[SKIP/CACHED] {date_iso} ({granule_id}) already extracted.", flush=True)
        with h5py.File(out_h5_path, "r") as hf:
            g = hf["science/LSAR/GCOV/grids/frequencyA"]
            hhhh_ml = g["HHHH"][:]
            hvhv_ml = g["HVHV"][:]
            mask_ml = g["mask"][:]
            ident = {k: decode_h5_scalar(v[()]) for k, v in hf["science/LSAR/identification"].items()}
        stats = compute_sample_stats(hhhh_ml, hvhv_ml, mask_ml)
        return {
            "product_type": "L2_GCOV",
            "date": date_iso,
            "granule_id": granule_id,
            "source_url": data_url,
            "crid": ident.get("compositeReleaseId", "P05023"),
            "product_version": ident.get("productVersion", "R05.02.3"),
            "zero_doppler_start_time": ident.get("zeroDopplerStartTime", ""),
            "zero_doppler_end_time": ident.get("zeroDopplerEndTime", ""),
            "track": int(ident.get("trackNumber", 129)),
            "frame": int(ident.get("frameNumber", 16)),
            "orbit_direction": ident.get("orbitPassDirection", "Ascending"),
            "epsg": EPSG_CODE,
            "utm_bounds": [UTM_X_MIN, UTM_Y_MIN, UTM_X_MAX, UTM_Y_MAX],
            "native_window_shape_10m": [6240, 7872],
            "multilook_window_shape_40m": list(hhhh_ml.shape),
            "native_reference_patch_shape_10m": [1024, 1024],
            "files": {
                "h5_subset": {
                    "path": str(out_h5_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(out_h5_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(out_h5_path),
                },
                "hhhh_tif": {
                    "path": str(tif_hh_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_hh_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_hh_path),
                },
                "hvhv_tif": {
                    "path": str(tif_hv_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_hv_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_hv_path),
                },
                "mask_tif": {
                    "path": str(tif_mask_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_mask_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_mask_path),
                },
            },
            "sample_stats": stats,
        }

    t0 = time.time()
    print(f"[EXTRACTING GCOV] {date_iso} -> {granule_id} ...", flush=True)

    # Resolve pre-signed S3 URL for fast parallel range requests
    r_init = session.get(data_url, headers={"Range": "bytes=0-1023"}, timeout=60)
    signed_url = r_init.url

    if f_obj is None:
        f_obj = earthaccess.open([granule])[0]
    with h5py.File(f_obj, "r") as h5:
        g = h5["science/LSAR/GCOV/grids/frequencyA"]
        x_coords = g["xCoordinates"][:]
        y_coords = g["yCoordinates"][:]
        dx = float(g["xCoordinateSpacing"][()])
        dy = float(g["yCoordinateSpacing"][()])
        epsg = int(g["projection"][()])

        # Compute exact index window matching [UTM_X_MIN, UTM_X_MAX] and [UTM_Y_MIN, UTM_Y_MAX]
        c0 = int(np.searchsorted(x_coords, UTM_X_MIN + abs(dx) * 0.5 - 1.0))
        c1 = c0 + int(round((UTM_X_MAX - UTM_X_MIN) / abs(dx)))
        r0 = int(np.searchsorted(-y_coords, -(UTM_Y_MAX - abs(dy) * 0.5 + 1.0)))
        r1 = r0 + int(round((UTM_Y_MAX - UTM_Y_MIN) / abs(dy)))

        print(f"  Window indices: rows [{r0}:{r1}] ({r1-r0}), cols [{c0}:{c1}] ({c1-c0})", flush=True)

        t_hh = time.time()
        hhhh_10m = read_window_via_coalesced_chunks(g["HHHH"], session, signed_url, r0, r1, c0, c1, max_workers=20)
        print(f"  Read HHHH {hhhh_10m.shape} in {time.time() - t_hh:.1f}s", flush=True)

        t_hv = time.time()
        hvhv_10m = read_window_via_coalesced_chunks(g["HVHV"], session, signed_url, r0, r1, c0, c1, max_workers=20)
        print(f"  Read HVHV {hvhv_10m.shape} in {time.time() - t_hv:.1f}s", flush=True)

        t_m = time.time()
        mask_10m = read_window_via_coalesced_chunks(g["mask"], session, signed_url, r0, r1, c0, c1, max_workers=20)
        print(f"  Read mask {mask_10m.shape} in {time.time() - t_m:.1f}s", flush=True)

        # Extract 1024x1024 native 10m reference patch from the already-loaded memory arrays
        pc0 = int(round((NATIVE_PATCH_X_MIN - UTM_X_MIN) / abs(dx)))
        pc1 = pc0 + 1024
        pr0 = int(round((UTM_Y_MAX - NATIVE_PATCH_Y_MAX) / abs(dy)))
        pr1 = pr0 + 1024
        hhhh_patch_10m = hhhh_10m[pr0:pr1, pc0:pc1].copy()
        hvhv_patch_10m = hvhv_10m[pr0:pr1, pc0:pc1].copy()
        mask_patch_10m = mask_10m[pr0:pr1, pc0:pc1].copy()
        x_patch_10m = x_coords[c0 + pc0 : c0 + pc1].copy()
        y_patch_10m = y_coords[r0 + pr0 : r0 + pr1].copy()

        # Perform 4x4 linear-power block averaging (10m -> 40m) across full Fayoum AOI
        hhhh_40m, valid_frac_hh = multilook_linear_block_average(hhhh_10m, mask_10m, factor=MULTILOOK_FACTOR)
        hvhv_40m, valid_frac_hv = multilook_linear_block_average(hvhv_10m, mask_10m, factor=MULTILOOK_FACTOR)
        valid_frac = np.minimum(valid_frac_hh, valid_frac_hv)
        mask_40m = multilook_mask(mask_10m, valid_frac, factor=MULTILOOK_FACTOR)

        # Compute 40m pixel-center coordinates
        x_win_10m = x_coords[c0:c1]
        y_win_10m = y_coords[r0:r1]
        x_40m = x_win_10m.reshape(-1, MULTILOOK_FACTOR).mean(axis=1)
        y_40m = y_win_10m.reshape(-1, MULTILOOK_FACTOR).mean(axis=1)
        dx_40m = dx * MULTILOOK_FACTOR
        dy_40m = dy * MULTILOOK_FACTOR

        # Read identification metadata and calibration NESZ grids
        ident_group = h5["science/LSAR/identification"]
        ident_dict = {
            k: ident_group[k][()]
            for k in [
                "granuleId",
                "compositeReleaseId",
                "productVersion",
                "productSpecificationVersion",
                "trackNumber",
                "frameNumber",
                "absoluteOrbitNumber",
                "orbitPassDirection",
                "lookDirection",
                "zeroDopplerStartTime",
                "zeroDopplerEndTime",
                "radarBand",
                "isFullFrame",
                "isGeocoded",
            ]
            if k in ident_group
        }

        nesz_group = h5["science/LSAR/GCOV/metadata/calibrationInformation/frequencyA/noiseEquivalentBackscatter"]
        nesz_hh = nesz_group["HH"][:]
        nesz_hv = nesz_group["HV"][:]
        nesz_x = nesz_group["xCoordinates"][:]
        nesz_y = nesz_group["yCoordinates"][:]

    # Save local HDF5 subset mirroring NISAR schema
    GCOV_H5_DIR.mkdir(parents=True, exist_ok=True)
    with h5py.File(out_h5_path, "w") as out_h5:
        id_grp = out_h5.create_group("science/LSAR/identification")
        for k, v in ident_dict.items():
            id_grp.create_dataset(k, data=v)

        grd = out_h5.create_group("science/LSAR/GCOV/grids/frequencyA")
        grd.create_dataset("HHHH", data=hhhh_40m, compression="gzip", compression_opts=4, shuffle=True)
        grd.create_dataset("HVHV", data=hvhv_40m, compression="gzip", compression_opts=4, shuffle=True)
        grd.create_dataset("mask", data=mask_40m, compression="gzip", compression_opts=4, shuffle=True)
        grd.create_dataset("validFraction", data=valid_frac, compression="gzip", compression_opts=4, shuffle=True)
        grd.create_dataset("xCoordinates", data=x_40m)
        grd.create_dataset("yCoordinates", data=y_40m)
        grd.create_dataset("xCoordinateSpacing", data=np.float64(dx_40m))
        grd.create_dataset("yCoordinateSpacing", data=np.float64(dy_40m))
        grd.create_dataset("projection", data=np.uint32(epsg))

        # Native 10m reference patch
        grd_nat = out_h5.create_group("science/LSAR/GCOV/grids/frequencyA_native_10m")
        grd_nat.create_dataset("HHHH", data=hhhh_patch_10m, compression="gzip", compression_opts=4, shuffle=True)
        grd_nat.create_dataset("HVHV", data=hvhv_patch_10m, compression="gzip", compression_opts=4, shuffle=True)
        grd_nat.create_dataset("mask", data=mask_patch_10m, compression="gzip", compression_opts=4, shuffle=True)
        grd_nat.create_dataset("xCoordinates", data=x_patch_10m)
        grd_nat.create_dataset("yCoordinates", data=y_patch_10m)
        grd_nat.create_dataset("xCoordinateSpacing", data=np.float64(dx))
        grd_nat.create_dataset("yCoordinateSpacing", data=np.float64(dy))
        grd_nat.create_dataset("projection", data=np.uint32(epsg))

        # NESZ calibration LUT
        cal_grp = out_h5.create_group(
            "science/LSAR/GCOV/metadata/calibrationInformation/frequencyA/noiseEquivalentBackscatter"
        )
        cal_grp.create_dataset("HH", data=nesz_hh, compression="gzip", compression_opts=4)
        cal_grp.create_dataset("HV", data=nesz_hv, compression="gzip", compression_opts=4)
        cal_grp.create_dataset("xCoordinates", data=nesz_x)
        cal_grp.create_dataset("yCoordinates", data=nesz_y)

    # Write compressed GeoTIFFs
    write_geotiff(tif_hh_path, hhhh_40m, UTM_X_MIN, UTM_Y_MAX, dx_40m, dy_40m, epsg, nodata=np.nan)
    write_geotiff(tif_hv_path, hvhv_40m, UTM_X_MIN, UTM_Y_MAX, dx_40m, dy_40m, epsg, nodata=np.nan)
    write_geotiff(tif_mask_path, mask_40m, UTM_X_MIN, UTM_Y_MAX, dx_40m, dy_40m, epsg, nodata=0)

    stats = compute_sample_stats(hhhh_40m, hvhv_40m, mask_40m)
    ident_clean = {k: decode_h5_scalar(v) for k, v in ident_dict.items()}
    print(
        f"  Completed {date_iso} in {time.time() - t0:.1f}s | H5: {out_h5_path.stat().st_size / 1e6:.1f} MB | "
        f"Valid: {stats['valid_pixel_pct']}%"
    )

    return {
        "product_type": "L2_GCOV",
        "date": date_iso,
        "granule_id": granule_id,
        "source_url": data_url,
        "crid": ident_clean.get("compositeReleaseId", "P05023"),
        "product_version": ident_clean.get("productVersion", "R05.02.3"),
        "zero_doppler_start_time": ident_clean.get("zeroDopplerStartTime", ""),
        "zero_doppler_end_time": ident_clean.get("zeroDopplerEndTime", ""),
        "track": int(ident_clean.get("trackNumber", 129)),
        "frame": int(ident_clean.get("frameNumber", 16)),
        "orbit_direction": ident_clean.get("orbitPassDirection", "Ascending"),
        "epsg": epsg,
        "utm_bounds": [UTM_X_MIN, UTM_Y_MIN, UTM_X_MAX, UTM_Y_MAX],
        "native_window_shape_10m": list(hhhh_10m.shape),
        "multilook_window_shape_40m": list(hhhh_40m.shape),
        "native_reference_patch_shape_10m": list(hhhh_patch_10m.shape),
        "files": {
            "h5_subset": {
                "path": str(out_h5_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(out_h5_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(out_h5_path),
            },
            "hhhh_tif": {
                "path": str(tif_hh_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_hh_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_hh_path),
            },
            "hvhv_tif": {
                "path": str(tif_hv_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_hv_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_hv_path),
            },
            "mask_tif": {
                "path": str(tif_mask_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_mask_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_mask_path),
            },
        },
        "sample_stats": stats,
    }


def extract_gunw_granule(granule: Any) -> dict[str, Any]:
    """Extract and cache an exploratory NISAR L2 GUNW granule subset at native 80m spacing."""
    granule_id = granule["umm"]["GranuleUR"]
    data_url = granule.data_links()[0]
    parts = granule_id.split("_")
    ref_date = parts[11][:8]
    sec_date = parts[13][:8]
    pair_key = f"{ref_date}_{sec_date}"
    pair_iso = f"{ref_date[:4]}-{ref_date[4:6]}-{ref_date[6:8]}_to_{sec_date[:4]}-{sec_date[4:6]}-{sec_date[6:8]}"

    out_h5_path = GUNW_H5_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_key}_subset.h5"
    tif_unw_path = GUNW_TIF_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_key}_unwrappedPhase_80m.tif"
    tif_coh_path = GUNW_TIF_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_key}_coherenceMagnitude_80m.tif"
    tif_iono_path = GUNW_TIF_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_key}_ionospherePhaseScreen_80m.tif"

    if out_h5_path.exists() and tif_unw_path.exists() and tif_coh_path.exists() and tif_iono_path.exists():
        print(f"[SKIP/CACHED GUNW] {pair_iso} ({granule_id}) already extracted.", flush=True)
        with h5py.File(out_h5_path, "r") as hf:
            unw_grp = hf["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"]
            hh_grp = unw_grp["HH"]
            unw_phase = hh_grp["unwrappedPhase"][:]
            coh_mag = hh_grp["coherenceMagnitude"][:]
            conn_comp = hh_grp["connectedComponents"][:]
            epsg = int(hh_grp["projection"][()])
            center_freq = float(hf["science/LSAR/GUNW/grids/frequencyA/centerFrequency"][()])
            ident_clean = {k: decode_h5_scalar(v[()]) for k, v in hf["science/LSAR/identification"].items()}
        valid_coh = coh_mag[np.isfinite(coh_mag) & (coh_mag > 0)]
        valid_unw = np.isfinite(unw_phase) & (conn_comp > 0)
        high_coh_pct = float(np.mean(coh_mag >= 0.5) * 100.0)
        return {
            "product_type": "L2_GUNW",
            "pair": pair_iso,
            "granule_id": granule_id,
            "source_url": data_url,
            "crid": ident_clean.get("compositeReleaseId", "P05023"),
            "product_version": ident_clean.get("productVersion", "1.0.11"),
            "reference_start_time": ident_clean.get("referenceZeroDopplerStartTime", ""),
            "secondary_start_time": ident_clean.get("secondaryZeroDopplerStartTime", ""),
            "center_frequency_hz": center_freq,
            "radar_wavelength_m": round(299792458.0 / center_freq, 6),
            "epsg": epsg,
            "utm_bounds": [UTM_X_MIN, UTM_Y_MIN, UTM_X_MAX, UTM_Y_MAX],
            "window_shape_80m": list(unw_phase.shape),
            "files": {
                "h5_subset": {
                    "path": str(out_h5_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(out_h5_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(out_h5_path),
                },
                "unwrapped_phase_tif": {
                    "path": str(tif_unw_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_unw_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_unw_path),
                },
                "coherence_tif": {
                    "path": str(tif_coh_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_coh_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_coh_path),
                },
                "ionosphere_tif": {
                    "path": str(tif_iono_path.relative_to(ROOT_DIR).as_posix()),
                    "size_mb": round(tif_iono_path.stat().st_size / (1024 * 1024), 2),
                    "sha256": compute_sha256(tif_iono_path),
                },
            },
            "coherence_stats": {
                "coherence_p05_p50_p95": [round(float(x), 3) for x in np.percentile(valid_coh, [5, 50, 95])],
                "pct_pixels_coherence_ge_0_5": round(high_coh_pct, 2),
                "pct_pixels_valid_unwrapped": round(float(np.mean(valid_unw) * 100.0), 2),
            },
        }

    t0 = time.time()
    print(f"[EXTRACTING GUNW] {pair_iso} -> {granule_id} ...")

    f_obj = earthaccess.open([granule])[0]
    with h5py.File(f_obj, "r") as h5:
        unw_grp = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"]
        hh_grp = unw_grp["HH"]
        x_coords = hh_grp["xCoordinates"][:]
        y_coords = hh_grp["yCoordinates"][:]
        dx = float(hh_grp["xCoordinateSpacing"][()])
        dy = float(hh_grp["yCoordinateSpacing"][()])
        epsg = int(hh_grp["projection"][()])
        center_freq = float(h5["science/LSAR/GUNW/grids/frequencyA/centerFrequency"][()])

        c0 = int(np.searchsorted(x_coords, UTM_X_MIN + abs(dx) * 0.5 - 1.0))
        c1 = c0 + int(round((UTM_X_MAX - UTM_X_MIN) / abs(dx)))
        r0 = int(np.searchsorted(-y_coords, -(UTM_Y_MAX - abs(dy) * 0.5 + 1.0)))
        r1 = r0 + int(round((UTM_Y_MAX - UTM_Y_MIN) / abs(dy)))

        unw_phase = hh_grp["unwrappedPhase"][r0:r1, c0:c1]
        coh_mag = hh_grp["coherenceMagnitude"][r0:r1, c0:c1]
        iono_phase = hh_grp["ionospherePhaseScreen"][r0:r1, c0:c1]
        conn_comp = hh_grp["connectedComponents"][r0:r1, c0:c1]
        mask_arr = unw_grp["mask"][r0:r1, c0:c1]
        x_sub = x_coords[c0:c1]
        y_sub = y_coords[r0:r1]

        ident_group = h5["science/LSAR/identification"]
        ident_dict = {
            k: ident_group[k][()]
            for k in [
                "granuleId",
                "compositeReleaseId",
                "productVersion",
                "trackNumber",
                "frameNumber",
                "orbitPassDirection",
                "lookDirection",
                "referenceZeroDopplerStartTime",
                "secondaryZeroDopplerStartTime",
            ]
            if k in ident_group
        }

    GUNW_H5_DIR.mkdir(parents=True, exist_ok=True)
    with h5py.File(out_h5_path, "w") as out_h5:
        id_grp = out_h5.create_group("science/LSAR/identification")
        for k, v in ident_dict.items():
            id_grp.create_dataset(k, data=v)
        out_h5.create_dataset("science/LSAR/GUNW/grids/frequencyA/centerFrequency", data=np.float64(center_freq))
        unw_out = out_h5.create_group("science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram")
        unw_out.create_dataset("mask", data=mask_arr, compression="gzip", compression_opts=4)
        hh_out = unw_out.create_group("HH")
        hh_out.create_dataset("unwrappedPhase", data=unw_phase, compression="gzip", compression_opts=4, shuffle=True)
        hh_out.create_dataset("coherenceMagnitude", data=coh_mag, compression="gzip", compression_opts=4, shuffle=True)
        hh_out.create_dataset(
            "ionospherePhaseScreen", data=iono_phase, compression="gzip", compression_opts=4, shuffle=True
        )
        hh_out.create_dataset("connectedComponents", data=conn_comp, compression="gzip", compression_opts=4)
        hh_out.create_dataset("xCoordinates", data=x_sub)
        hh_out.create_dataset("yCoordinates", data=y_sub)
        hh_out.create_dataset("xCoordinateSpacing", data=np.float64(dx))
        hh_out.create_dataset("yCoordinateSpacing", data=np.float64(dy))
        hh_out.create_dataset("projection", data=np.uint32(epsg))

    write_geotiff(tif_unw_path, unw_phase, UTM_X_MIN, UTM_Y_MAX, dx, dy, epsg, nodata=np.nan)
    write_geotiff(tif_coh_path, coh_mag, UTM_X_MIN, UTM_Y_MAX, dx, dy, epsg, nodata=np.nan)
    write_geotiff(tif_iono_path, iono_phase, UTM_X_MIN, UTM_Y_MAX, dx, dy, epsg, nodata=np.nan)

    valid_coh = coh_mag[np.isfinite(coh_mag) & (coh_mag > 0)]
    valid_unw = np.isfinite(unw_phase) & (conn_comp > 0)
    high_coh_pct = float(np.mean(coh_mag >= 0.5) * 100.0)
    ident_clean = {k: decode_h5_scalar(v) for k, v in ident_dict.items()}

    print(
        f"  Completed GUNW {pair_iso} in {time.time() - t0:.1f}s | Coherence >= 0.5: {high_coh_pct:.1f}% | "
        f"Median gamma: {float(np.median(valid_coh)):.3f}"
    )

    return {
        "product_type": "L2_GUNW",
        "pair": pair_iso,
        "granule_id": granule_id,
        "source_url": data_url,
        "crid": ident_clean.get("compositeReleaseId", "P05023"),
        "product_version": ident_clean.get("productVersion", "R05.02.3"),
        "reference_start_time": ident_clean.get("referenceZeroDopplerStartTime", ""),
        "secondary_start_time": ident_clean.get("secondaryZeroDopplerStartTime", ""),
        "center_frequency_hz": center_freq,
        "radar_wavelength_m": round(299792458.0 / center_freq, 6),
        "epsg": epsg,
        "utm_bounds": [UTM_X_MIN, UTM_Y_MIN, UTM_X_MAX, UTM_Y_MAX],
        "window_shape_80m": list(unw_phase.shape),
        "files": {
            "h5_subset": {
                "path": str(out_h5_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(out_h5_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(out_h5_path),
            },
            "unwrapped_phase_tif": {
                "path": str(tif_unw_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_unw_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_unw_path),
            },
            "coherence_tif": {
                "path": str(tif_coh_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_coh_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_coh_path),
            },
            "ionosphere_tif": {
                "path": str(tif_iono_path.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(tif_iono_path.stat().st_size / (1024 * 1024), 2),
                "sha256": compute_sha256(tif_iono_path),
            },
        },
        "coherence_stats": {
            "coherence_p05_p50_p95": [round(float(x), 3) for x in np.percentile(valid_coh, [5, 50, 95])],
            "pct_pixels_coherence_ge_0_5": round(high_coh_pct, 2),
            "pct_pixels_valid_unwrapped": round(float(np.mean(valid_unw) * 100.0), 2),
        },
    }


def main() -> None:
    """Execute Phase 1 windowed extraction for all 10 GCOV dates and 2 GUNW pairs."""
    dotenv.load_dotenv(ROOT_DIR / ".env")
    earthaccess.login(strategy="environment")
    session = earthaccess.get_requests_https_session()
    adapter = HTTPAdapter(pool_connections=32, pool_maxsize=64)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 1. Search all 10 homogeneous GCOV granules for Track 129, Frame 016, DHDH 4005, P05023
    gcov_granules = earthaccess.search_data(
        short_name="NISAR_L2_GCOV_PROVISIONAL_V1",
        granule_name="*_129_A_016_4005_DHDH_*_P05023_*",
    )
    gcov_granules = sorted(
        gcov_granules,
        key=lambda g: g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"],
    )
    print(f"Found {len(gcov_granules)} homogeneous L2_GCOV granules for Track 129 / Frame 016.", flush=True)

    # Batch-open uncached granules in one call to avoid repeated earthaccess.open overhead
    uncached_indices = []
    uncached_granules = []
    for idx, gran in enumerate(gcov_granules):
        gid = gran["umm"]["GranuleUR"]
        acq_date = gid.split("_")[11][:8]
        if not (GCOV_H5_DIR / f"NISAR_L2_GCOV_T129_F016_{acq_date}_subset.h5").exists():
            uncached_indices.append(idx)
            uncached_granules.append(gran)

    opened_map = {}
    if uncached_granules:
        print(f"Batch-opening {len(uncached_granules)} uncached GCOV granules via earthaccess...", flush=True)
        opened_files = earthaccess.open(uncached_granules)
        for idx, f_obj in zip(uncached_indices, opened_files):
            opened_map[idx] = f_obj

    gcov_records = []
    for idx, gran in enumerate(gcov_granules):
        rec = extract_gcov_granule(gran, session, f_obj=opened_map.get(idx))
        gcov_records.append(rec)

    # 2. Search GUNW pairs for Track 129, Frame 016, 4000 SH, P05023 and select 2 pairs:
    #    - Summer vegetation growth pair: 2026-07-05 -> 2026-07-17 (cycle 024 -> 025)
    #    - Latest autumn pair: 2026-10-09 -> 2026-10-21 (cycle 032 -> 033)
    gunw_granules = earthaccess.search_data(
        short_name="NISAR_L2_GUNW_PROVISIONAL_V1",
        granule_name="*_129_A_016_*_4000_SH_*_P05023_*",
    )
    gunw_granules = sorted(
        gunw_granules,
        key=lambda g: g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"],
    )
    target_gunw = [
        g
        for g in gunw_granules
        if ("20260705" in g["umm"]["GranuleUR"] and "20260717" in g["umm"]["GranuleUR"])
        or ("20261009" in g["umm"]["GranuleUR"] and "20261021" in g["umm"]["GranuleUR"])
    ]
    print(f"Found {len(target_gunw)} target exploratory L2_GUNW granules.")

    gunw_records = []
    for gran in target_gunw:
        rec = extract_gunw_granule(gran)
        gunw_records.append(rec)

    # Compute total local disk usage
    all_files = list(SUBSET_DIR.rglob("*.*"))
    total_bytes = sum(f.stat().st_size for f in all_files if f.is_file() and f.name != "phase1_manifest.json")
    total_mb = round(total_bytes / (1024 * 1024), 2)

    manifest = {
        "phase": "Phase 1 — NISAR Real Data Windowed Subset Manifest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "aoi_name": "Option A — Fayoum Oasis (Lake Qarun, Wadi El Rayan, Irrigated Agriculture, Urban Core, Desert Reference)",
        "geographic_bbox_wgs84": [30.30, 29.05, 31.10, 29.60],
        "utm_epsg": EPSG_CODE,
        "utm_bounds_m": [UTM_X_MIN, UTM_Y_MIN, UTM_X_MAX, UTM_Y_MAX],
        "gcov_native_spacing_m": [10.0, -10.0],
        "gcov_multilook_spacing_m": [40.0, -40.0],
        "gcov_multilook_method": "Mask-aware 4x4 block average strictly in linear power (gamma0)",
        "native_reference_patch_utm_bounds_m": [
            NATIVE_PATCH_X_MIN,
            NATIVE_PATCH_Y_MIN,
            NATIVE_PATCH_X_MAX,
            NATIVE_PATCH_Y_MAX,
        ],
        "total_local_subset_size_mb": total_mb,
        "size_gate_limit_mb": 500.0,
        "passes_500mb_gate": bool(total_mb < 500.0),
        "gcov_count": len(gcov_records),
        "gunw_count": len(gunw_records),
        "gcov_subsets": gcov_records,
        "gunw_subsets": gunw_records,
    }

    SUBSET_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"\n=== PHASE 1 EXTRACTION COMPLETE ===")
    print(f"Total Local Subset Disk Footprint: {total_mb:.2f} MB (< 500 MB gate: {total_mb < 500.0})")
    print(f"Manifest written to: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

