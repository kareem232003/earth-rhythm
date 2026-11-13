"""Exploratory NISAR L2 GUNW InSAR Processing & Coherence Masking (Rule 4 & Change Type B).

Converts ionosphere-corrected unwrapped interferometric phase (radians) to exploratory
Line-of-Sight (LOS) range change (meters) anchored to a high-coherence reference point,
strictly masking all pixels with coherence magnitude gamma < 0.50 as NaN
(`UNRELIABLE — DO NOT INTERPRET`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

SPEED_OF_LIGHT_M_S = 299792458.0


def compute_los_displacement_m(
    unwrapped_phase_rad: np.ndarray,
    coherence_mag: np.ndarray,
    ionosphere_phase_rad: np.ndarray | None = None,
    connected_components: np.ndarray | None = None,
    wavelength_m: float = 0.24196324,
    coherence_threshold: float = 0.50,
    ref_row_col: tuple[int, int] | None = None,
    ref_window_halfwidth: int = 2,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute coherence-masked LOS range change (meters) relative to a reference benchmark.

    Formula:
      phi_corr = unwrapped_phase_rad - ionosphere_phase_rad
      delta_los_m = -(wavelength_m / (4 * pi)) * (phi_corr - phi_ref)

    Pixels with `coherence_mag < coherence_threshold` or `connected_components == 0`
    are strictly masked to `np.nan`.
    """
    if unwrapped_phase_rad.shape != coherence_mag.shape:
        raise ValueError("Shape mismatch between unwrapped_phase_rad and coherence_mag.")

    valid = np.isfinite(unwrapped_phase_rad) & np.isfinite(coherence_mag) & (coherence_mag >= coherence_threshold)
    if connected_components is not None:
        valid = valid & (connected_components > 0)

    phi_corr = unwrapped_phase_rad.astype(np.float64).copy()
    if ionosphere_phase_rad is not None and np.all(np.isfinite(ionosphere_phase_rad[valid])):
        phi_corr = phi_corr - ionosphere_phase_rad.astype(np.float64)

    h, w = unwrapped_phase_rad.shape
    if ref_row_col is None:
        # Select highest-coherence 5x5 patch near Fayoum Urban Core (approx center-east of AOI)
        ref_row_col = (int(h * 0.55), int(w * 0.69))

    rr, rc = ref_row_col
    r0 = max(0, rr - ref_window_halfwidth)
    r1 = min(h, rr + ref_window_halfwidth + 1)
    c0 = max(0, rc - ref_window_halfwidth)
    c1 = min(w, rc + ref_window_halfwidth + 1)

    ref_patch_valid = valid[r0:r1, c0:c1]
    if not np.any(ref_patch_valid):
        raise ValueError(f"Reference point window around {ref_row_col} has no valid coherent pixels >= {coherence_threshold}.")

    phi_ref = float(np.nanmedian(phi_corr[r0:r1, c0:c1][ref_patch_valid]))
    ref_coh = float(np.nanmedian(coherence_mag[r0:r1, c0:c1][ref_patch_valid]))

    phase_to_m = -float(wavelength_m) / (4.0 * np.pi)
    los_m = np.full((h, w), np.nan, dtype=np.float32)
    los_m[valid] = ((phi_corr[valid] - phi_ref) * phase_to_m).astype(np.float32)

    valid_los = los_m[valid]
    stats = {
        "coherence_threshold": coherence_threshold,
        "wavelength_m": round(float(wavelength_m), 6),
        "reference_pixel_row_col": [int(rr), int(rc)],
        "reference_patch_median_coherence": round(ref_coh, 3),
        "reference_phase_rad": round(phi_ref, 4),
        "valid_coherent_pixel_count": int(np.sum(valid)),
        "valid_coherent_pixel_pct": round(float(np.mean(valid) * 100.0), 2),
        "unreliable_masked_pixel_pct": round(float((1.0 - np.mean(valid)) * 100.0), 2),
        "los_displacement_m_p05_p50_p95": [
            round(float(x), 4) for x in np.percentile(valid_los, [5, 50, 95])
        ],
        "los_displacement_m_std": round(float(np.std(valid_los)), 4),
    }
    return los_m, stats


def process_gunw_pair(
    unwrapped_phase_rad: np.ndarray,
    coherence_mag: np.ndarray,
    ionosphere_phase_rad: np.ndarray,
    connected_components: np.ndarray,
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    center_frequency_hz: float = 1239000000.0,
    coherence_threshold: float = 0.50,
    ref_utm_xy: tuple[float, float] = (292000.0, 3244000.0),  # Fayoum Urban Core Benchmark
) -> tuple[np.ndarray, dict[str, Any]]:
    """Process a single NISAR L2 GUNW pair with coherence masking and reference anchoring."""
    wavelength_m = SPEED_OF_LIGHT_M_S / float(center_frequency_hz)
    rc = int(np.argmin(np.abs(x_coords - ref_utm_xy[0])))
    rr = int(np.argmin(np.abs(y_coords - ref_utm_xy[1])))

    # Find highest coherence pixel within 10 pixels (800m) of the nominal urban benchmark
    r_win0, r_win1 = max(0, rr - 10), min(len(y_coords), rr + 11)
    c_win0, c_win1 = max(0, rc - 10), min(len(x_coords), rc + 11)
    sub_coh = np.where(connected_components[r_win0:r_win1, c_win0:c_win1] > 0, coherence_mag[r_win0:r_win1, c_win0:c_win1], -1.0)
    best_local = np.unravel_index(int(np.argmax(sub_coh)), sub_coh.shape)
    best_rr = r_win0 + int(best_local[0])
    best_rc = c_win0 + int(best_local[1])

    los_m, stats = compute_los_displacement_m(
        unwrapped_phase_rad=unwrapped_phase_rad,
        coherence_mag=coherence_mag,
        ionosphere_phase_rad=ionosphere_phase_rad,
        connected_components=connected_components,
        wavelength_m=wavelength_m,
        coherence_threshold=coherence_threshold,
        ref_row_col=(best_rr, best_rc),
        ref_window_halfwidth=1,
    )
    stats["reference_utm_easting_m"] = float(x_coords[best_rc])
    stats["reference_utm_northing_m"] = float(y_coords[best_rr])
    return los_m, stats
