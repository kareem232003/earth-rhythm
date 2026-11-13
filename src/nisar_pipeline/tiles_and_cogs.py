"""Cloud-Optimized GeoTIFF (COG) Generation and Web-Ready EPSG:4326 RGBA Overlay Rendering.

Implements Phase 4 of Earth Rhythm AI:
  - Converts all Phase 2 and Phase 3 EPSG:32636 GeoTIFFs into internally tiled (256x256),
    DEFLATE-compressed Cloud-Optimized GeoTIFFs (COGs) with multi-scale overview pyramids
    ([2, 4, 8]) while preserving 100% of Rule 3 and Rule 5 metadata tags.
  - Reprojects EPSG:32636 rasters onto an exact EPSG:4326 (WGS84 lon/lat) grid so that
    MapLibre GL JS image overlays align accurately with WGS84 web basemaps without UTM skew.
  - Applies perceptually uniform scientific colormaps (Viridis, Diverging Blue-White-Red,
    Plasma, Categorical Dual-Pol Regime & Land-Cover palettes, and False-Color Dual-Pol RGB
    composites) and writes lossless 4-band RGBA PNGs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import NotGeoreferencedWarning
from rasterio.warp import calculate_default_transform, reproject

from .guards import MANDATORY_RULE3_FIELDS

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def convert_geotiff_to_cog(
    src_path: Path,
    dst_cog_path: Path,
    overview_factors: tuple[int, ...] = (2, 4, 8),
) -> dict[str, Any]:
    """Convert an existing Rule-3 tagged GeoTIFF into a tiled Cloud-Optimized GeoTIFF with overviews."""
    dst_cog_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path, "r") as src:
        profile = src.profile.copy()
        tags = src.tags()
        data = src.read(1)
        is_int = np.issubdtype(data.dtype, np.integer)

    # Validate Rule 3 tags are present before writing COG
    missing = [f for f in MANDATORY_RULE3_FIELDS if f not in tags or not str(tags[f]).strip()]
    if missing:
        raise ValueError(f"Source GeoTIFF {src_path.name} is missing Rule 3 tags: {missing}")

    cog_profile = profile.copy()
    cog_profile.update(
        driver="GTiff",
        tiled=True,
        blockxsize=256,
        blockysize=256,
        compress="deflate",
        predictor=2 if is_int else 3,
    )

    resampling_mode = Resampling.nearest if is_int else Resampling.average

    with rasterio.open(dst_cog_path, "w", **cog_profile) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags)
        dst.build_overviews(list(overview_factors), resampling_mode)
        dst.update_tags(ns="rio_overview", resampling=resampling_mode.value)

    # Verify COG structure
    with rasterio.open(dst_cog_path, "r") as chk:
        is_tiled = bool(chk.is_tiled)
        block_shapes = chk.block_shapes
        overviews = chk.overviews(1)
        chk_tags = chk.tags()

    if not is_tiled or not overviews:
        raise RuntimeError(f"Failed COG validation on {dst_cog_path}: is_tiled={is_tiled}, overviews={overviews}")

    size_bytes = dst_cog_path.stat().st_size
    return {
        "cog_path": str(dst_cog_path),
        "is_tiled": is_tiled,
        "block_shape": list(block_shapes[0]) if block_shapes else [256, 256],
        "overview_factors": list(overviews),
        "dtype": str(data.dtype),
        "shape": [int(data.shape[0]), int(data.shape[1])],
        "size_bytes": int(size_bytes),
        "size_mb": round(size_bytes / (1024 * 1024), 3),
        "sha256": compute_sha256(dst_cog_path),
        "rule3_metadata": chk_tags,
    }


def _interpolate_colormap(norm_val: np.ndarray, stops: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    """Interpolate normalized [0, 1] array onto RGB color stops -> (H, W, 3) uint8."""
    v = np.clip(norm_val, 0.0, 1.0)
    xs = np.array([s[0] for s in stops], dtype=np.float64)
    rs = np.array([s[1][0] for s in stops], dtype=np.float64)
    gs = np.array([s[1][1] for s in stops], dtype=np.float64)
    bs = np.array([s[1][2] for s in stops], dtype=np.float64)

    r = np.interp(v, xs, rs).astype(np.uint8)
    g = np.interp(v, xs, gs).astype(np.uint8)
    b = np.interp(v, xs, bs).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


# Perceptually uniform scientific colormaps
COLORMAPS: dict[str, list[tuple[float, tuple[int, int, int]]]] = {
    # Viridis (for HH and HV backscatter dB)
    "viridis": [
        (0.00, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.50, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.00, (253, 231, 37)),
    ],
    # Diverging Blue -> Slate/Neutral -> Amber/Gold/Red (for dB log-ratio change)
    "diverging_change": [
        (0.00, (5, 48, 97)),      # Strong negative (-dB)
        (0.25, (67, 147, 195)),   # Moderate negative
        (0.50, (240, 240, 240)),  # Zero change
        (0.75, (244, 165, 130)),  # Moderate positive
        (1.00, (178, 24, 43)),    # Strong positive (+dB)
    ],
    # Diverging Brown -> White -> Emerald Green (for HV canopy change / depolarization)
    "diverging_canopy": [
        (0.00, (140, 81, 10)),    # Strong canopy loss (-HV)
        (0.25, (216, 179, 101)),  # Moderate loss
        (0.50, (245, 245, 245)),  # Stable
        (0.75, (90, 180, 172)),   # Moderate canopy gain
        (1.00, (1, 102, 94)),     # Strong canopy growth (+HV)
    ],
    # Plasma (for 10-date seasonal dynamic range max_t - min_t)
    "plasma": [
        (0.00, (13, 8, 135)),
        (0.25, (126, 3, 168)),
        (0.50, (204, 71, 120)),
        (0.75, (248, 149, 64)),
        (1.00, (240, 249, 33)),
    ],
    # Coolwarm (for exploratory GUNW LOS phase screen in meters)
    "coolwarm": [
        (0.00, (59, 76, 192)),
        (0.25, (141, 176, 254)),
        (0.50, (247, 247, 247)),
        (0.75, (244, 154, 123)),
        (1.00, (180, 4, 38)),
    ],
}

# Categorical palette for 7-class Dual-Pol Change Regime (RGBA uint8)
DUAL_POL_REGIME_PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (40, 48, 60, 75),      # 0: No Significant Change (semi-transparent dark slate)
    1: (16, 185, 129, 235),   # 1: Canopy Volume Growth (+HV >= +2.03 dB) -> Emerald Green
    2: (245, 158, 11, 235),   # 2: Canopy Harvest / Clearance (-HV <= -2.03 dB) -> Amber Orange
    3: (59, 130, 246, 235),   # 3: Surface Wetting / Roughness (+HH >= +2.73 dB only) -> Cobalt Blue
    4: (168, 85, 247, 235),   # 4: Surface Drying / Specular Inundation (-HH <= -2.73 dB only) -> Purple
    5: (239, 68, 68, 255),    # 5: Disagreement Type I (+HH Surge & -HV Drop) -> Vivid Crimson
    6: (6, 182, 212, 255),    # 6: Disagreement Type II (-HH Drop & +HV Surge) -> Vivid Cyan
    255: (0, 0, 0, 0),        # 255: Masked / NoData
}

# Categorical palette for Phase 2 Composite Land-Cover Class (RGBA uint8)
LANDCOVER_CLASS_PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 0),          # 0: NoData
    1: (14, 116, 144, 235),   # 1: Permanent Open Water (Lake Qarun & Wadi El Rayan) -> Deep Teal Blue
    2: (56, 189, 248, 235),   # 2: Seasonal Water Margin -> Sky Blue
    3: (34, 197, 94, 215),    # 3: Vegetated Agriculture -> Oasis Green
    4: (239, 68, 68, 245),    # 4: Urban Settlement -> Bright Red
    5: (217, 119, 6, 195),    # 5: Stable Consolidated Limestone Desert Reference -> Ochre Gold
    6: (148, 163, 184, 110),  # 6: Low-SNR Eolian Sand Sheet -> Muted Warm Grey
}


def reproject_array_to_wgs84(
    arr: np.ndarray,
    src_transform: rasterio.Affine,
    src_crs: str,
    src_bounds: tuple[float, float, float, float],
    src_nodata: float | int | None,
    is_categorical: bool = False,
) -> tuple[np.ndarray, rasterio.Affine, tuple[float, float, float, float]]:
    """Reproject a 2D array from EPSG:32636 to EPSG:4326 (WGS84)."""
    h, w = arr.shape
    dst_crs = "EPSG:4326"
    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, dst_crs, w, h, *src_bounds
    )

    if is_categorical:
        fill_val = int(src_nodata) if src_nodata is not None else 255
        dst_arr = np.full((dst_h, dst_w), fill_val, dtype=arr.dtype)
        reproject(
            source=arr,
            destination=dst_arr,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=fill_val,
            dst_nodata=fill_val,
            resampling=Resampling.nearest,
        )
    else:
        dst_arr = np.full((dst_h, dst_w), np.nan, dtype=np.float32)
        reproject(
            source=arr.astype(np.float32),
            destination=dst_arr,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    west = float(dst_transform.c)
    north = float(dst_transform.f)
    east = float(west + dst_w * dst_transform.a)
    south = float(north + dst_h * dst_transform.e)
    return dst_arr, dst_transform, (west, south, east, north)


def write_rgba_png(out_png_path: Path, rgba: np.ndarray) -> dict[str, Any]:
    """Write a (H, W, 4) uint8 RGBA array to a lossless PNG via rasterio."""
    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    h, w, c = rgba.shape
    assert c == 4 and rgba.dtype == np.uint8
    with rasterio.Env(GDAL_PAM_ENABLED="NO"):
        with rasterio.open(
            out_png_path,
            "w",
            driver="PNG",
            height=h,
            width=w,
            count=4,
            dtype=np.uint8,
        ) as dst:
            for band_idx in range(4):
                dst.write(rgba[:, :, band_idx], band_idx + 1)

    size_bytes = out_png_path.stat().st_size
    return {
        "png_path": str(out_png_path),
        "width": int(w),
        "height": int(h),
        "size_bytes": int(size_bytes),
        "size_kb": round(size_bytes / 1024.0, 1),
        "sha256": compute_sha256(out_png_path),
    }


def render_continuous_wgs84_png(
    src_tif_path: Path,
    out_png_path: Path,
    vmin: float,
    vmax: float,
    cmap_name: str,
    transparent_within_abs: float | None = None,
    alpha_valid: int = 230,
) -> dict[str, Any]:
    """Reproject a continuous EPSG:32636 GeoTIFF to EPSG:4326 and render as an RGBA PNG."""
    with rasterio.open(src_tif_path, "r") as src:
        arr = src.read(1).astype(np.float32)
        src_transform = src.transform
        src_crs = str(src.crs)
        src_bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        tags = src.tags()

    wgs_arr, _, wgs_bounds = reproject_array_to_wgs84(
        arr, src_transform, src_crs, src_bounds, src_nodata=np.nan, is_categorical=False
    )

    valid = np.isfinite(wgs_arr)
    norm = (wgs_arr - vmin) / max(vmax - vmin, 1e-6)
    rgb = _interpolate_colormap(np.where(valid, norm, 0.0), COLORMAPS[cmap_name])

    alpha = np.where(valid, alpha_valid, 0).astype(np.uint8)
    if transparent_within_abs is not None:
        sub_thresh = valid & (np.abs(wgs_arr) < float(transparent_within_abs))
        alpha[sub_thresh] = 0

    rgba = np.dstack([rgb, alpha])
    png_info = write_rgba_png(out_png_path, rgba)
    west, south, east, north = wgs_bounds
    png_info.update(
        {
            "wgs84_bounds": [round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
            "maplibre_coordinates": [
                [round(west, 6), round(north, 6)],
                [round(east, 6), round(north, 6)],
                [round(east, 6), round(south, 6)],
                [round(west, 6), round(south, 6)],
            ],
            "vmin": vmin,
            "vmax": vmax,
            "colormap": cmap_name,
            "transparent_within_abs": transparent_within_abs,
            "rule3_metadata": tags,
        }
    )
    return png_info


def render_categorical_wgs84_png(
    src_tif_path: Path,
    out_png_path: Path,
    palette: dict[int, tuple[int, int, int, int]],
    binary_color: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """Reproject a categorical/mask EPSG:32636 GeoTIFF to EPSG:4326 and render as an RGBA PNG."""
    with rasterio.open(src_tif_path, "r") as src:
        arr = src.read(1)
        src_transform = src.transform
        src_crs = str(src.crs)
        src_bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        src_nodata = src.nodata
        tags = src.tags()

    wgs_arr, _, wgs_bounds = reproject_array_to_wgs84(
        arr, src_transform, src_crs, src_bounds, src_nodata=src_nodata, is_categorical=True
    )

    h, w = wgs_arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    if binary_color is not None:
        mask_bool = (wgs_arr > 0) & (wgs_arr != 255)
        rgba[mask_bool] = np.array(binary_color, dtype=np.uint8)
    else:
        for code, color in palette.items():
            rgba[wgs_arr == code] = np.array(color, dtype=np.uint8)

    png_info = write_rgba_png(out_png_path, rgba)
    west, south, east, north = wgs_bounds
    png_info.update(
        {
            "wgs84_bounds": [round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
            "maplibre_coordinates": [
                [round(west, 6), round(north, 6)],
                [round(east, 6), round(north, 6)],
                [round(east, 6), round(south, 6)],
                [round(west, 6), round(south, 6)],
            ],
            "rule3_metadata": tags,
        }
    )
    return png_info


def render_dual_pol_rgb_composite_wgs84_png(
    hh_tif_path: Path,
    hv_tif_path: Path,
    out_png_path: Path,
    rule3_meta: dict[str, str],
) -> dict[str, Any]:
    """Render a False-Color Dual-Polarization SAR Composite (R=HH dB, G=HV dB, B=HH-HV dB) in EPSG:4326."""
    with rasterio.open(hh_tif_path, "r") as s_hh, rasterio.open(hv_tif_path, "r") as s_hv:
        hh_db = s_hh.read(1).astype(np.float32)
        hv_db = s_hv.read(1).astype(np.float32)
        src_transform = s_hh.transform
        src_crs = str(s_hh.crs)
        src_bounds = (s_hh.bounds.left, s_hh.bounds.bottom, s_hh.bounds.right, s_hh.bounds.top)

    wgs_hh, _, wgs_bounds = reproject_array_to_wgs84(
        hh_db, src_transform, src_crs, src_bounds, src_nodata=np.nan, is_categorical=False
    )
    wgs_hv, _, _ = reproject_array_to_wgs84(
        hv_db, src_transform, src_crs, src_bounds, src_nodata=np.nan, is_categorical=False
    )

    valid = np.isfinite(wgs_hh) & np.isfinite(wgs_hv)
    diff_db = wgs_hh - wgs_hv

    # Stretch: R = HH [-22, -2] dB, G = HV [-24, -8] dB, B = (HH - HV) [2, 12] dB
    r = np.clip(np.nan_to_num((wgs_hh - (-22.0)) / 20.0, nan=0.0), 0.0, 1.0)
    g = np.clip(np.nan_to_num((wgs_hv - (-24.0)) / 16.0, nan=0.0), 0.0, 1.0)
    b = np.clip(np.nan_to_num((diff_db - 2.0) / 10.0, nan=0.0), 0.0, 1.0)

    rgba = np.zeros((wgs_hh.shape[0], wgs_hh.shape[1], 4), dtype=np.uint8)
    rgba[:, :, 0] = np.where(valid, (r * 255.0).astype(np.uint8), 0)
    rgba[:, :, 1] = np.where(valid, (g * 255.0).astype(np.uint8), 0)
    rgba[:, :, 2] = np.where(valid, (b * 255.0).astype(np.uint8), 0)
    rgba[:, :, 3] = np.where(valid, 235, 0)

    png_info = write_rgba_png(out_png_path, rgba)
    west, south, east, north = wgs_bounds
    png_info.update(
        {
            "wgs84_bounds": [round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
            "maplibre_coordinates": [
                [round(west, 6), round(north, 6)],
                [round(east, 6), round(north, 6)],
                [round(east, 6), round(south, 6)],
                [round(west, 6), round(south, 6)],
            ],
            "composite_recipe": "R: HH [-22, -2 dB] | G: HV [-24, -8 dB] | B: HH-HV [2, 12 dB]",
            "rule3_metadata": rule3_meta,
        }
    )
    return png_info

