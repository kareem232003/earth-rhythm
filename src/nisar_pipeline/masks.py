"""Geophysical & Quality Mask Generation for Fayoum Oasis AOI (Science Requirement 4).

Constructs and documents pixel-level masks across the 1560 x 1968 (40m) grid:
  1. `valid_data_mask`: Valid radar observation across all 10 dates (no NoData / layover / shadow)
  2. `low_snr_nesz_mask`: Pixels within +3 dB of the sensor NESZ floor (eolian sand sheets / calm water)
  3. `permanent_water_mask`: Persistent open water (Lake Qarun & Wadi El Rayan Lakes)
  4. `seasonal_water_margin_mask`: Dynamic shoreline / flooded basin margins & fish-farm / canal wetlands
  5. `vegetated_agriculture_mask`: Irrigated cropland & orchard floor exhibiting volume scattering
  6. `urban_settlement_mask`: Persistent high-backscatter double-bounce built-up cores
  7. `stable_desert_reference_mask`: Consolidated desert plateau pixels outside the oasis used as
     the empirical radiometric stability / noise-floor reference.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def build_aoi_landcover_masks(
    hhhh_stack_linear: np.ndarray,
    hvhv_stack_linear: np.ndarray,
    nisar_mask_stack: np.ndarray,
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    mean_coherence_40m: np.ndarray | None = None,
    nesz_hh_median_linear: float = 0.00472,  # -23.26 dB
    nesz_hv_median_linear: float = 0.00353,  # -24.52 dB
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Build multi-temporal geophysical and quality masks from the 10-date linear-power stack.

    Args:
        hhhh_stack_linear: float32 array of shape (T, H, W) in linear power (gamma0).
        hvhv_stack_linear: float32 array of shape (T, H, W) in linear power (gamma0).
        nisar_mask_stack: uint8 array of shape (T, H, W) from NISAR L2 GCOV `mask`.
        x_coords: 1D float64 array of length W (UTM Easting, EPSG:32636).
        y_coords: 1D float64 array of length H (UTM Northing, EPSG:32636).
        mean_coherence_40m: Optional 2D float32 array (H, W) of mean L2_GUNW coherence magnitude
            used to physically separate decorrelated open water from radar-smooth desert sand sheets.
        nesz_hh_median_linear: Median HH Noise Equivalent Gamma Zero in linear units.
        nesz_hv_median_linear: Median HV Noise Equivalent Gamma Zero in linear units.

    Returns:
        Tuple of:
          - `masks`: dictionary of boolean / uint8 2D arrays of shape (H, W)
          - `mask_summary`: documented pixel counts and area shares (%) for every mask.
    """
    t_count, h, w = hhhh_stack_linear.shape
    total_pixels = int(h * w)

    # 1. Valid radar observation mask (1..9 in NISAR mask, finite positive power across all T dates)
    valid_per_date = (
        np.isfinite(hhhh_stack_linear)
        & (hhhh_stack_linear > 0.0)
        & np.isfinite(hvhv_stack_linear)
        & (hvhv_stack_linear > 0.0)
        & (nisar_mask_stack >= 1)
        & (nisar_mask_stack < 10)
    )
    valid_all_dates = np.all(valid_per_date, axis=0)
    nodata_or_layover_mask = ~valid_all_dates

    # Multi-temporal summary statistics computed strictly in linear power first, then converted to dB
    mean_hh_lin = np.nanmean(hhhh_stack_linear, axis=0)
    mean_hv_lin = np.nanmean(hvhv_stack_linear, axis=0)
    min_hh_lin = np.nanmin(hhhh_stack_linear, axis=0)
    max_hh_lin = np.nanmax(hhhh_stack_linear, axis=0)
    max_hv_lin = np.nanmax(hvhv_stack_linear, axis=0)

    mean_hh_db = 10.0 * np.log10(np.maximum(mean_hh_lin, 1e-10))
    mean_hv_db = 10.0 * np.log10(np.maximum(mean_hv_lin, 1e-10))
    min_hh_db = 10.0 * np.log10(np.maximum(min_hh_lin, 1e-10))
    max_hh_db = 10.0 * np.log10(np.maximum(max_hh_lin, 1e-10))
    max_hv_db = 10.0 * np.log10(np.maximum(max_hv_lin, 1e-10))

    # Temporal standard deviation of dB across the 10 dates
    hh_db_stack = 10.0 * np.log10(np.maximum(hhhh_stack_linear, 1e-10))
    hv_db_stack = 10.0 * np.log10(np.maximum(hvhv_stack_linear, 1e-10))
    std_hh_db = np.nanstd(hh_db_stack, axis=0)

    xx, yy = np.meshgrid(x_coords, y_coords)
    # Hydrographic depressions: Lake Qarun basin, Upper & Lower Wadi El Rayan basins, and Fayoum depression floor
    hydro_basin = (
        ((xx >= 248000.0) & (xx <= 292000.0) & (yy >= 3254000.0) & (yy <= 3268500.0))
        | ((xx >= 244000.0) & (xx <= 259500.0) & (yy >= 3215040.0) & (yy <= 3236500.0))
        | ((xx >= 258000.0) & (xx <= 312000.0) & (yy >= 3228000.0) & (yy <= 3260000.0))
    )

    # 2. Low-SNR / Thermal Noise Floor Mask (mean power within +3 dB = 2.0x of NESZ in either channel)
    low_snr_nesz_mask = valid_all_dates & (
        (mean_hh_lin < 2.0 * nesz_hh_median_linear) | (mean_hv_lin < 2.0 * nesz_hv_median_linear)
    )

    # 3. Permanent Open Water Mask:
    #    In L-band SAR (24 cm), dry eolian sand sheets also exhibit low specular backscatter.
    #    True open water (Lake Qarun & Wadi El Rayan Lakes) is physically distinguished by:
    #      - Specular low backscatter (HH < -14.0 dB & HV < -19.5 dB in >= 8/10 dates)
    #      - Complete L-band interferometric decorrelation (mean GUNW coherence < 0.15)
    #      - Location within the Fayoum / Qarun / Wadi El Rayan hydrographic depressions.
    water_epoch_count = np.sum((hh_db_stack < -14.0) & (hv_db_stack < -19.5), axis=0)
    if mean_coherence_40m is not None:
        permanent_water_mask = (
            valid_all_dates & hydro_basin & (water_epoch_count >= 8) & (mean_coherence_40m < 0.15)
        )
    else:
        permanent_water_mask = valid_all_dates & hydro_basin & (water_epoch_count >= 8)

    # 4. Seasonal Water / Dynamic Shoreline / Fish-Pond & Canal Inundation Candidate Mask:
    #    Within the hydrographic depression, exhibits water-like low backscatter on >= 1 date
    #    (min_hh_db < -14.0 dB) with strong temporal dynamic range (max_hh_db - min_hh_db >= 2.5 dB).
    seasonal_water_margin_mask = (
        valid_all_dates
        & hydro_basin
        & (~permanent_water_mask)
        & (min_hh_db < -14.0)
        & ((max_hh_db - min_hh_db) >= 2.5)
    )

    # 5. Urban / Persistent Built-Up Settlement Mask:
    #    Strong persistent dihedral double-bounce (mean HH > -5.5 dB, temporal std_hh_db < 1.2 dB)
    urban_settlement_mask = (
        valid_all_dates
        & (~permanent_water_mask)
        & (mean_hh_db > -5.5)
        & (mean_hv_db > -13.5)
        & (std_hh_db < 1.2)
    )

    # 6. Vegetated Agriculture Mask:
    #    Significant L-band cross-pol volume scattering (max HV > -17.5 dB, i.e. > 7 dB above HV NESZ)
    #    and not permanent water or urban core.
    vegetated_agriculture_mask = (
        valid_all_dates
        & (~permanent_water_mask)
        & (~urban_settlement_mask)
        & (max_hv_db > -17.5)
        & (mean_hh_db > -13.5)
    )

    # 7. Stable Consolidated Desert Reference Mask:
    #    Located on the hyper-arid desert margins outside the irrigated oasis and lakes,
    #    above the +3 dB NESZ floor, non-water, non-vegetated (max_hv_db <= -17.5 dB),
    #    and high InSAR coherence (mean_coherence >= 0.50 if available).
    desert_geographic_zone = (~hydro_basin) | (yy >= 3266000.0) | (xx <= 250000.0) | (yy <= 3224000.0)
    coh_cond = (mean_coherence_40m >= 0.50) if mean_coherence_40m is not None else np.ones((h, w), dtype=bool)
    stable_desert_reference_mask = (
        valid_all_dates
        & desert_geographic_zone
        & coh_cond
        & (~low_snr_nesz_mask)
        & (~permanent_water_mask)
        & (~seasonal_water_margin_mask)
        & (~vegetated_agriculture_mask)
        & (mean_hh_db >= -16.5)
        & (mean_hh_db <= -8.0)
        & (max_hv_db <= -17.5)
    )

    # Composite categorical classification map (uint8):
    # 0 = NoData/Layover, 1 = Permanent Water, 2 = Seasonal Water/Shoreline,
    # 3 = Vegetated Agriculture, 4 = Urban Settlement, 5 = Stable Consolidated Desert,
    # 6 = Low-SNR Sand Sheet / Bare Arid Transition
    composite_class = np.full((h, w), 6, dtype=np.uint8)
    composite_class[nodata_or_layover_mask] = 0
    composite_class[stable_desert_reference_mask] = 5
    composite_class[vegetated_agriculture_mask] = 3
    composite_class[seasonal_water_margin_mask] = 2
    composite_class[urban_settlement_mask] = 4
    composite_class[permanent_water_mask] = 1

    masks = {
        "valid_all_dates_mask": valid_all_dates.astype(np.uint8),
        "nodata_or_layover_mask": nodata_or_layover_mask.astype(np.uint8),
        "low_snr_nesz_mask": low_snr_nesz_mask.astype(np.uint8),
        "permanent_water_mask": permanent_water_mask.astype(np.uint8),
        "seasonal_water_margin_mask": seasonal_water_margin_mask.astype(np.uint8),
        "vegetated_agriculture_mask": vegetated_agriculture_mask.astype(np.uint8),
        "urban_settlement_mask": urban_settlement_mask.astype(np.uint8),
        "stable_desert_reference_mask": stable_desert_reference_mask.astype(np.uint8),
        "composite_landcover_class": composite_class,
    }

    pixel_area_km2 = (40.0 * 40.0) / 1e6  # 0.0016 km^2 per 40m pixel

    def _stat(bmask: np.ndarray, desc: str) -> dict[str, Any]:
        cnt = int(np.sum(bmask > 0))
        return {
            "pixel_count": cnt,
            "pixel_share_pct": round((cnt / total_pixels) * 100.0, 2),
            "area_km2": round(cnt * pixel_area_km2, 2),
            "description": desc,
        }

    summary = {
        "total_grid_pixels": total_pixels,
        "total_grid_area_km2": round(total_pixels * pixel_area_km2, 2),
        "masks": {
            "valid_all_dates_mask": _stat(
                masks["valid_all_dates_mask"],
                "Valid radar observations across all 10 dates (NISAR mask in 1..9, finite positive gamma0)",
            ),
            "nodata_or_layover_mask": _stat(
                masks["nodata_or_layover_mask"],
                "NoData (0/255) or radar layover/shadow (>=10) in any of the 10 acquisitions",
            ),
            "low_snr_nesz_mask": _stat(
                masks["low_snr_nesz_mask"],
                "Low-SNR pixels within +3 dB of sensor NESZ floor (HH < -20.25 dB or HV < -21.51 dB; loose sand sheets & calm water)",
            ),
            "permanent_water_mask": _stat(
                masks["permanent_water_mask"],
                "Permanent open water (Lake Qarun & Wadi El Rayan Lakes; HH < -14.5 dB & HV < -19.5 dB in >= 8/10 dates)",
            ),
            "seasonal_water_margin_mask": _stat(
                masks["seasonal_water_margin_mask"],
                "Dynamic shoreline, fish-pond, and basin inundation margins (min HH < -14.0 dB with >= 2.5 dB HH range)",
            ),
            "vegetated_agriculture_mask": _stat(
                masks["vegetated_agriculture_mask"],
                "Irrigated cropland and orchards exhibiting L-band volume scattering (max HV > -17.5 dB, mean HH > -13.5 dB)",
            ),
            "urban_settlement_mask": _stat(
                masks["urban_settlement_mask"],
                "Persistent dihedral double-bounce urban/built-up cores (mean HH > -5.5 dB, temporal std < 1.2 dB)",
            ),
            "stable_desert_reference_mask": _stat(
                masks["stable_desert_reference_mask"],
                "Consolidated hyper-arid desert plateau reference pixels outside oasis used for empirical noise/threshold calibration",
            ),
        },
    }
    return masks, summary
