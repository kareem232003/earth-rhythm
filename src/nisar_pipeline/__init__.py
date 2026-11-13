"""NISAR Surface Change Storyteller — Core Scientific Processing Package.

Provides strictly validated, unit-safe SAR radiometric, masking, speckle-filtering,
and exploratory InSAR processing routines adhering to NASA Space Apps 2026
"Dancing with the SARs" scientific guardrails.
"""

from .change_detection import classify_dual_pol_change, derive_change_thresholds
from .guards import build_rule3_metadata, validate_granule_pair_compatibility, validate_series_homogeneity
from .insar import compute_los_displacement_m, process_gunw_pair
from .masks import build_aoi_landcover_masks
from .radiometry import (
    boxcar_filter_linear,
    compute_empirical_enl,
    lee_filter_linear,
    linear_to_db,
    db_to_linear,
    log_ratio_db,
)
from .tiles_and_cogs import (
    convert_geotiff_to_cog,
    render_categorical_wgs84_png,
    render_continuous_wgs84_png,
    render_dual_pol_rgb_composite_wgs84_png,
)

__all__ = [
    "classify_dual_pol_change",
    "derive_change_thresholds",
    "build_rule3_metadata",
    "validate_granule_pair_compatibility",
    "validate_series_homogeneity",
    "compute_los_displacement_m",
    "process_gunw_pair",
    "build_aoi_landcover_masks",
    "boxcar_filter_linear",
    "compute_empirical_enl",
    "lee_filter_linear",
    "linear_to_db",
    "db_to_linear",
    "log_ratio_db",
    "convert_geotiff_to_cog",
    "render_categorical_wgs84_png",
    "render_continuous_wgs84_png",
    "render_dual_pol_rgb_composite_wgs84_png",
]

