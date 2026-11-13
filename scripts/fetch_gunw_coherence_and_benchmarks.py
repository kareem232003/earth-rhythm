"""Extract all 9 T129_F016 GUNW coherences (Option 1) & NASA authoritative benchmarks (Option 2).

Fetches cleanly windowed / lightweight layers aligned to the project's exact 40 m EPSG:32636 grid
(1560 x 1968, bounds [237280, 3215040, 316000, 3277440]):
  - Option 1 (Pure NISAR SAR): All 9 consecutive T129_F016 Ascending L2_GUNW `coherenceMagnitude`
    arrays (`80 m`, saved to `data/processed/gunw_coherence/`) instead of only 2 pairs.
  - Option 2 (Authoritative NASA Benchmarks, strictly separated in `data/benchmarks/` per Rule 2):
      1. `NISAR_WATERMASK` v0.5.0 (30 m -> 40 m Fayoum grid, ~0.15 MB source tiles)
      2. `NISAR_DEM` v1.2 (Modified Copernicus 30 m DEM -> 40 m Fayoum grid)
      3. `OPERA_L3_DSWX-HLS_V1` B01_WTR (30 m Dynamic Surface Water eXtent for matched dates
         2026-07-06 [+1d], 2026-08-10 [0d exact], and 2026-09-15/16 [0/+1d])
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import earthaccess
import h5py
import numpy as np
import rasterio
from dotenv import load_dotenv
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.phase1_extract_subsets import (
    EPSG_CODE,
    UTM_X_MAX,
    UTM_X_MIN,
    UTM_Y_MAX,
    UTM_Y_MIN,
    compute_sha256,
    decode_h5_scalar,
    write_geotiff,
)

AOI_BBOX_WGS84 = (30.3, 29.1, 31.1, 29.6)
GRID_H = 1560
GRID_W = 1968
GRID_RES_M = 40.0
TARGET_CRS = CRS.from_epsg(EPSG_CODE)
TARGET_TRANSFORM = from_origin(UTM_X_MIN, UTM_Y_MAX, GRID_RES_M, GRID_RES_M)

GUNW_COH_DIR = ROOT_DIR / "data" / "processed" / "gunw_coherence"
BENCH_DIR = ROOT_DIR / "data" / "benchmarks"


def write_40m_aligned_geotiff(
    out_path: Path,
    arr: np.ndarray,
    nodata: float | int | None,
    tags: dict[str, str],
) -> dict[str, Any]:
    """Write a 40 m (1560 x 1968) EPSG:32636 benchmark GeoTIFF with provenance tags."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": arr.dtype,
        "crs": TARGET_CRS,
        "transform": TARGET_TRANSFORM,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "predictor": 3 if np.issubdtype(arr.dtype, np.floating) else 2,
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(**tags)
    return {
        "path": str(out_path.relative_to(ROOT_DIR).as_posix()),
        "size_mb": round(out_path.stat().st_size / (1024 * 1024), 3),
        "sha256": compute_sha256(out_path),
    }


def warp_files_mosaic_to_40m(
    src_paths: list[Path],
    dtype: Any,
    fill_value: float | int,
    resampling: Resampling,
    valid_fn: Any | None = None,
) -> np.ndarray:
    """Warp and mosaic source GeoTIFF tiles onto the exact 40 m Fayoum grid."""
    out = np.full((GRID_H, GRID_W), fill_value, dtype=dtype)
    for sp in src_paths:
        tmp = np.full((GRID_H, GRID_W), fill_value, dtype=dtype)
        with rasterio.open(sp, "r") as src:
            src_nodata = src.nodata if src.nodata is not None else fill_value
            reproject(
                source=rasterio.band(src, 1),
                destination=tmp,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src_nodata,
                dst_transform=TARGET_TRANSFORM,
                dst_crs=TARGET_CRS,
                dst_nodata=fill_value,
                resampling=resampling,
            )
        if valid_fn is not None:
            fill_mask = (~valid_fn(out)) & valid_fn(tmp)
        else:
            fill_mask = (out == fill_value) & (tmp != fill_value)
        out[fill_mask] = tmp[fill_mask]
    return out


def extract_all_9_t129_gunw_coherences() -> dict[str, Any]:
    """Extract 80 m coherenceMagnitude windows for all 9 Ascending T129_F016 GUNW pairs."""
    GUNW_COH_DIR.mkdir(parents=True, exist_ok=True)
    results = earthaccess.search_data(
        short_name="NISAR_L2_GUNW_PROVISIONAL_V1",
        bounding_box=AOI_BBOX_WGS84,
        temporal=("2026-06-20", "2026-10-25"),
        count=50,
    )
    t129 = sorted(
        [g for g in results if "_129_A_016_" in g["umm"]["GranuleUR"] and "_P05023_" in g["umm"]["GranuleUR"]],
        key=lambda g: g["umm"]["GranuleUR"],
    )
    if len(t129) != 9:
        raise RuntimeError(f"Expected 9 homogeneous T129_F016 P05023 GUNW pairs, found {len(t129)}")

    records: list[dict[str, Any]] = []
    for gran in t129:
        gid = gran["umm"]["GranuleUR"]
        parts = gid.split("_")
        ref_date, sec_date = parts[11][:8], parts[13][:8]
        pair_key = f"{ref_date}_{sec_date}"
        pair_iso = f"{ref_date[:4]}-{ref_date[4:6]}-{ref_date[6:8]}_to_{sec_date[:4]}-{sec_date[4:6]}-{sec_date[6:8]}"
        out_tif = GUNW_COH_DIR / f"NISAR_L2_GUNW_T129_F016_{pair_key}_coherenceMagnitude_80m.tif"

        existing_sub_tif = ROOT_DIR / "data" / "subsets" / "gunw_tif" / out_tif.name
        if not out_tif.exists() and existing_sub_tif.exists():
            shutil.copy2(existing_sub_tif, out_tif)

        if out_tif.exists():
            with rasterio.open(out_tif, "r") as s:
                coh_arr = s.read(1).astype(np.float32)
            print(f"[CACHED COH] {pair_iso} -> {out_tif.name} ({coh_arr.shape})", flush=True)
        else:
            t0 = time.time()
            print(f"[EXTRACT COH] {pair_iso} -> {gid} ...", flush=True)
            fobj = earthaccess.open([gran])[0]
            try:
                with h5py.File(fobj, "r") as h5:
                    hh_grp = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"]
                    x_coords = hh_grp["xCoordinates"][:]
                    y_coords = hh_grp["yCoordinates"][:]
                    dx = float(hh_grp["xCoordinateSpacing"][()])
                    dy = float(hh_grp["yCoordinateSpacing"][()])
                    epsg = int(hh_grp["projection"][()])
                    c0 = int(np.searchsorted(x_coords, UTM_X_MIN + abs(dx) * 0.5 - 1.0))
                    c1 = c0 + int(round((UTM_X_MAX - UTM_X_MIN) / abs(dx)))
                    r0 = int(np.searchsorted(-y_coords, -(UTM_Y_MAX - abs(dy) * 0.5 + 1.0)))
                    r1 = r0 + int(round((UTM_Y_MAX - UTM_Y_MIN) / abs(dy)))
                    coh_arr = hh_grp["coherenceMagnitude"][r0:r1, c0:c1].astype(np.float32)
                    crid = decode_h5_scalar(h5["science/LSAR/identification/compositeReleaseId"][()])
            finally:
                fobj.close()
            if crid != "P05023":
                raise RuntimeError(f"CRID mismatch on {gid}: expected P05023, got {crid}")
            write_geotiff(out_tif, coh_arr, UTM_X_MIN, UTM_Y_MAX, dx, dy, epsg, nodata=np.nan)
            print(f"  Saved {out_tif.name} in {time.time() - t0:.1f}s", flush=True)

        fin = coh_arr[np.isfinite(coh_arr) & (coh_arr > 0)]
        records.append(
            {
                "pair": pair_iso,
                "granule_id": gid,
                "source_url": gran.data_links()[0],
                "path": str(out_tif.relative_to(ROOT_DIR).as_posix()),
                "size_mb": round(out_tif.stat().st_size / (1024 * 1024), 3),
                "sha256": compute_sha256(out_tif),
                "coherence_median": round(float(np.median(fin)), 4),
            }
        )

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "track": 129,
        "frame": 16,
        "orbit_direction": "Ascending",
        "crid": "P05023",
        "pair_count": len(records),
        "pairs": records,
    }
    (GUNW_COH_DIR / "coherence_9pair_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def fetch_nasa_benchmarks() -> dict[str, Any]:
    """Fetch NISAR_WATERMASK, NISAR_DEM, and matched-date OPERA_L3_DSWX-HLS_V1 onto 40 m grid."""
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    bench_meta: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule2_notice": (
            "External ancillary and benchmark datasets strictly separated from primary NISAR GCOV observations (Rule 2)."
        ),
        "datasets": {},
    }

    with tempfile.TemporaryDirectory(prefix="fayoum_bench_") as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. NISAR_WATERMASK (v0.5.0, ~0.15 MB total)
        wm_out = BENCH_DIR / "nisar_watermask_40m_fayoum.tif"
        wm_grans = [
            g
            for g in earthaccess.search_data(short_name="NISAR_WATERMASK", bounding_box=AOI_BBOX_WGS84, count=10)
            if g["umm"]["GranuleUR"].endswith("-tif")
        ]
        wm_dir = tmp_path / "watermask"
        wm_files = [Path(p) for p in earthaccess.download(wm_grans, str(wm_dir))]
        wm_arr = warp_files_mosaic_to_40m(
            wm_files,
            dtype=np.uint8,
            fill_value=255,
            resampling=Resampling.nearest,
            valid_fn=lambda a: a != 255,
        )
        wm_info = write_40m_aligned_geotiff(
            wm_out,
            wm_arr,
            nodata=255,
            tags={
                "source": "NASA NISAR_WATERMASK v0.5.0 (Ancillary Water Mask - Rule 2 Benchmark)",
                "granules": ",".join(g["umm"]["GranuleUR"] for g in wm_grans),
                "crs": f"EPSG:{EPSG_CODE}",
            },
        )
        bench_meta["datasets"]["nisar_watermask"] = {
            **wm_info,
            "granule_ids": [g["umm"]["GranuleUR"] for g in wm_grans],
            "water_pixel_count": int(np.sum(wm_arr == 1)),
            "unique_values": [int(x) for x in np.unique(wm_arr)],
        }
        print(f"[BENCH] Saved {wm_out.name}: water_px={int(np.sum(wm_arr == 1))}", flush=True)

        # 2. NISAR_DEM (Modified Copernicus DEM 30 m)
        dem_out = BENCH_DIR / "nisar_dem_40m_fayoum.tif"
        dem_grans = [
            g
            for g in earthaccess.search_data(short_name="NISAR_DEM", bounding_box=AOI_BBOX_WGS84, count=10)
            if g["umm"]["GranuleUR"].endswith("-tif")
        ]
        dem_dir = tmp_path / "dem"
        dem_files = [Path(p) for p in earthaccess.download(dem_grans, str(dem_dir))]
        dem_arr = warp_files_mosaic_to_40m(
            dem_files,
            dtype=np.float32,
            fill_value=-9999.0,
            resampling=Resampling.bilinear,
            valid_fn=lambda a: np.isfinite(a) & (a > -500.0),
        )
        dem_info = write_40m_aligned_geotiff(
            dem_out,
            dem_arr,
            nodata=-9999.0,
            tags={
                "source": "NASA NISAR_DEM v1.2 (Modified Copernicus 30m DEM - Rule 2 Benchmark)",
                "granules": ",".join(g["umm"]["GranuleUR"] for g in dem_grans),
                "units": "meters",
                "crs": f"EPSG:{EPSG_CODE}",
            },
        )
        valid_dem = dem_arr[dem_arr > -500.0]
        bench_meta["datasets"]["nisar_dem"] = {
            **dem_info,
            "granule_ids": [g["umm"]["GranuleUR"] for g in dem_grans],
            "elevation_min_m": round(float(np.min(valid_dem)), 2),
            "elevation_median_m": round(float(np.median(valid_dem)), 2),
            "elevation_max_m": round(float(np.max(valid_dem)), 2),
        }
        print(
            f"[BENCH] Saved {dem_out.name}: min={float(np.min(valid_dem)):.1f}m, max={float(np.max(valid_dem)):.1f}m",
            flush=True,
        )

        # 3. OPERA_L3_DSWX-HLS_V1 B01_WTR matched to NISAR overpass dates
        dswx_windows = [
            ("2026-07-05", ("2026-07-05", "2026-07-07")),
            ("2026-08-10", ("2026-08-10", "2026-08-10")),
            ("2026-09-15", ("2026-09-15", "2026-09-16")),
        ]
        dswx_records: list[dict[str, Any]] = []
        session = earthaccess.get_requests_https_session()
        for nisar_date, temporal_rng in dswx_windows:
            grans = earthaccess.search_data(
                short_name="OPERA_L3_DSWX-HLS_V1",
                bounding_box=AOI_BBOX_WGS84,
                temporal=temporal_rng,
                count=20,
            )
            wtr_dir = tmp_path / f"dswx_{nisar_date}"
            wtr_dir.mkdir(parents=True, exist_ok=True)
            local_wtr_files: list[Path] = []
            used_urs: list[str] = []
            for g in grans:
                ur = g["umm"]["GranuleUR"]
                wtr_urls = [u for u in g.data_links() if u.endswith("_B01_WTR.tif")]
                if not wtr_urls:
                    continue
                dst_tile = wtr_dir / wtr_urls[0].split("/")[-1]
                if not dst_tile.exists():
                    resp = session.get(wtr_urls[0], timeout=90)
                    resp.raise_for_status()
                    dst_tile.write_bytes(resp.content)
                local_wtr_files.append(dst_tile)
                used_urs.append(ur)

            wtr_arr = warp_files_mosaic_to_40m(
                local_wtr_files,
                dtype=np.uint8,
                fill_value=255,
                resampling=Resampling.nearest,
                # Treat 0 (not water), 1 (open water), 2 (partial surface water) as clear observed classes
                valid_fn=lambda a: a <= 2,
            )
            dc = nisar_date.replace("-", "")
            out_wtr = BENCH_DIR / f"opera_dswx_hls_match_{dc}_40m_fayoum.tif"
            info = write_40m_aligned_geotiff(
                out_wtr,
                wtr_arr,
                nodata=255,
                tags={
                    "source": "NASA JPL OPERA_L3_DSWX-HLS_V1 B01_WTR (Rule 2 Optical/HLS Water Benchmark)",
                    "matched_nisar_date": nisar_date,
                    "source_granules": ",".join(used_urs),
                    "legend": "0=Not Water, 1=Open Water, 2=Partial Surface Water, 252-255=Cloud/Mask/Fill",
                },
            )
            clear_px = int(np.sum(wtr_arr <= 2))
            open_wtr_px = int(np.sum(wtr_arr == 1))
            part_wtr_px = int(np.sum(wtr_arr == 2))
            print(
                f"[BENCH] Saved {out_wtr.name}: clear={clear_px}/{GRID_H*GRID_W} "
                f"({clear_px/(GRID_H*GRID_W)*100:.1f}%), open_water={open_wtr_px}, partial={part_wtr_px}",
                flush=True,
            )
            dswx_records.append(
                {
                    **info,
                    "matched_nisar_date": nisar_date,
                    "opera_window": list(temporal_rng),
                    "granule_ids": used_urs,
                    "clear_pixel_count": clear_px,
                    "clear_coverage_pct": round(clear_px / (GRID_H * GRID_W) * 100.0, 2),
                    "open_water_pixel_count": open_wtr_px,
                    "partial_water_pixel_count": part_wtr_px,
                }
            )
        bench_meta["datasets"]["opera_dswx_hls"] = dswx_records

    (BENCH_DIR / "benchmark_manifest.json").write_text(json.dumps(bench_meta, indent=2), encoding="utf-8")
    return bench_meta


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    auth = earthaccess.login(strategy="environment")
    if not getattr(auth, "authenticated", False):
        raise RuntimeError("Earthdata login failed — check .env credentials.")
    print("=== Step 1: Extracting all 9 T129_F016 GUNW coherences (Option 1) ===")
    extract_all_9_t129_gunw_coherences()
    print("\n=== Step 2: Fetching NASA benchmark datasets (Option 2) ===")
    fetch_nasa_benchmarks()
    print("\nAll Option 1 coherences and Option 2 benchmarks saved cleanly.")


if __name__ == "__main__":
    main()

