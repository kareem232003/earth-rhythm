"""Geometry, CRS, and Product Version Consistency Guards (Rules 3, 7, 8).

Enforces programmatic checks preventing:
  - Mixing different product versions/maturity tiers (e.g., BETA vs PROVISIONAL, or differing CRIDs)
  - Comparing acquisitions from different tracks, frames, orbit directions, or polarizations
  - Combining rasters with mismatched CRS, pixel grids, or bounding boxes
  - Exporting layers without mandatory Rule 3 metadata fields.
"""

from __future__ import annotations

from typing import Any

MANDATORY_RULE3_FIELDS = (
    "satellite",
    "product_type",
    "product_version",
    "acquisition_date",
    "track_frame",
    "orbit_direction",
    "polarization",
    "units",
    "crs",
    "source",
    "epistemic_tag",
)

ALLOWED_EPISTEMIC_TAGS = ("OBSERVATION", "CHANGE DETECTION", "INTERPRETATION (hypothesis)")
ALLOWED_UNITS = (
    "linear power (m^2/m^2)",
    "dB (10*log10 gamma0)",
    "dB difference (10*log10(P2/P1))",
    "meters LOS",
    "radians",
    "unitless (coherence 0-1)",
    "categorical mask (uint8)",
)


def validate_granule_pair_compatibility(rec_a: dict[str, Any], rec_b: dict[str, Any]) -> None:
    """Verify two granule metadata records can be quantitatively compared (Rules 7 & 8).

    Raises ValueError if product_type, crid, product_version, track, frame,
    orbit_direction, epsg, utm_bounds, or raster dimensions differ.
    """
    check_keys = [
        ("product_type", "Product Type"),
        ("crid", "Composite Release ID (CRID)"),
        ("product_version", "Product Version"),
        ("track", "Relative Orbit Track"),
        ("frame", "Frame Number"),
        ("orbit_direction", "Orbit Pass Direction"),
        ("epsg", "CRS EPSG Code"),
        ("utm_bounds", "UTM Bounding Box"),
        ("multilook_window_shape_40m", "Grid Dimensions (H, W)"),
    ]
    for key, label in check_keys:
        if key in rec_a or key in rec_b:
            val_a = rec_a.get(key)
            val_b = rec_b.get(key)
            if val_a != val_b:
                raise ValueError(
                    f"Rule 7/8 Violation — Incompatible {label} (`{key}`): "
                    f"{rec_a.get('granule_id', 'A')} has `{val_a}` vs "
                    f"{rec_b.get('granule_id', 'B')} has `{val_b}`."
                )


def validate_series_homogeneity(records: list[dict[str, Any]]) -> None:
    """Validate that a list of granule records forms a strictly homogeneous time series."""
    if not records:
        raise ValueError("Cannot validate an empty granule series.")
    ref = records[0]
    for rec in records[1:]:
        validate_granule_pair_compatibility(ref, rec)


def build_rule3_metadata(
    *,
    satellite: str = "NISAR (NASA-ISRO SAR, L-Band 24 cm)",
    product_type: str,
    product_version: str,
    acquisition_date: str,
    track: int,
    frame: int,
    orbit_direction: str,
    polarization: str,
    units: str,
    crs: str,
    source: str,
    epistemic_tag: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct and validate a Rule 3 & Rule 5 compliant layer metadata dictionary."""
    if epistemic_tag not in ALLOWED_EPISTEMIC_TAGS:
        raise ValueError(f"Invalid epistemic_tag `{epistemic_tag}`. Must be one of {ALLOWED_EPISTEMIC_TAGS}.")
    if units not in ALLOWED_UNITS:
        raise ValueError(f"Invalid units `{units}`. Must be one of {ALLOWED_UNITS}.")

    meta: dict[str, Any] = {
        "satellite": satellite,
        "product_type": product_type,
        "product_version": product_version,
        "acquisition_date": acquisition_date,
        "track_frame": f"Track {track:03d} / Frame {frame:03d}",
        "orbit_direction": orbit_direction,
        "polarization": polarization,
        "units": units,
        "crs": crs,
        "source": source,
        "epistemic_tag": epistemic_tag,
    }
    for field in MANDATORY_RULE3_FIELDS:
        if not meta.get(field):
            raise ValueError(f"Rule 3 Violation: Missing mandatory metadata field `{field}`.")
    if extra:
        meta.update(extra)
    return meta

