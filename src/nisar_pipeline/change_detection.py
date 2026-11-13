"""Change Detection, Statistical Noise Threshold Derivation, and Polarization Disagreement Analysis.

Implements Science Requirements 2, 3, 5, 6 of NASA Space Apps 2026 "Dancing with the SARs":
  - Log-ratio change metric in dB (`10 * log10(P2 / P1)`) computed from linear-power filtered gamma0
  - Statistically justified change thresholds derived from BOTH:
      (a) Stage-2 empirical ENL speckle theory (`3 * sqrt(2) * 4.3429 / sqrt(ENL)`)
      (b) Empirical multi-temporal noise distribution across all 218,705 pixels (`349.93 km^2`)
          of the Stable Consolidated Desert Reference mask (`3 * sigma_desert` and 99th percentile)
  - Dual-polarization (`HH` vs `HV`) change regime classification, explicitly isolating where
    `HH` and `HV` agree vs. where they disagree.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .radiometry import log_ratio_db

RANDOM_SEED = 42


def derive_change_thresholds(
    hhhh_stack_linear: np.ndarray,
    hvhv_stack_linear: np.ndarray,
    stable_desert_mask: np.ndarray,
    enl_hh: float = 152.74,
    enl_hv: float = 444.01,
) -> dict[str, Any]:
    """Derive statistically justified dB change thresholds from speckle theory and stable desert pixels.

    Computes:
      1. Theoretical 3-sigma two-date speckle threshold:
         `tau_speckle = 3 * sqrt(2) * (4.342945 / sqrt(ENL))`
      2. Empirical distribution of 12-day consecutive log-ratio differences (`10 * log10(P_{t+1} / P_t)`)
         and full-span log-ratio differences over `stable_desert_mask > 0` (`N = 218,705` pixels):
         - Robust MAD-based sigma: `sigma_mad = 1.4826 * median(|d - median(d)|)`
         - Sample standard deviation `sigma_std`
         - 95th and 99th percentiles of `|d - median(d)|` (zero-centered radiometric drift removed
           and uncentered raw values both reported)
      3. Adopts the conservative threshold:
         `tau_final = max(tau_speckle_3sigma, 3.0 * sigma_mad_empirical, p99_centered_empirical)`
         rounded to 2 decimal places.
    """
    desert_bool = stable_desert_mask > 0
    n_desert = int(np.sum(desert_bool))
    if n_desert < 100:
        raise ValueError(f"Insufficient stable desert reference pixels ({n_desert}) to derive threshold.")

    t_count = hhhh_stack_linear.shape[0]

    # Collect consecutive 12-day differences over stable desert reference pixels
    hh_diffs_12d = []
    hv_diffs_12d = []
    for t in range(t_count - 1):
        d_hh = log_ratio_db(hhhh_stack_linear[t], hhhh_stack_linear[t + 1])[desert_bool]
        d_hv = log_ratio_db(hvhv_stack_linear[t], hvhv_stack_linear[t + 1])[desert_bool]
        hh_diffs_12d.append(d_hh[np.isfinite(d_hh)])
        hv_diffs_12d.append(d_hv[np.isfinite(d_hv)])

    all_hh_12d = np.concatenate(hh_diffs_12d)
    all_hv_12d = np.concatenate(hv_diffs_12d)

    # Full seasonal span (t=0 to t=-1) over stable desert reference pixels
    hh_span = log_ratio_db(hhhh_stack_linear[0], hhhh_stack_linear[-1])[desert_bool]
    hv_span = log_ratio_db(hvhv_stack_linear[0], hvhv_stack_linear[-1])[desert_bool]
    hh_span = hh_span[np.isfinite(hh_span)]
    hv_span = hv_span[np.isfinite(hv_span)]

    def _stats_for_channel(diffs_12d: np.ndarray, diffs_span: np.ndarray, enl_val: float) -> dict[str, Any]:
        # Theoretical speckle noise
        sigma_1date_speckle = 4.3429448190325175 / np.sqrt(float(enl_val))
        sigma_2date_speckle = np.sqrt(2.0) * sigma_1date_speckle
        tau_speckle_3sigma = 3.0 * sigma_2date_speckle

        # Empirical 12-day consecutive stats over stable desert
        med_12d = float(np.median(diffs_12d))
        mad_12d = float(np.median(np.abs(diffs_12d - med_12d)))
        sigma_mad_12d = 1.4826 * mad_12d
        sigma_std_12d = float(np.std(diffs_12d, ddof=1))
        p95_abs_raw = float(np.percentile(np.abs(diffs_12d), 95))
        p99_abs_raw = float(np.percentile(np.abs(diffs_12d), 99))
        p99_abs_centered = float(np.percentile(np.abs(diffs_12d - med_12d), 99))

        # Empirical full-span (4-month) stats over stable desert
        med_span = float(np.median(diffs_span))
        mad_span = float(np.median(np.abs(diffs_span - med_span)))
        sigma_mad_span = 1.4826 * mad_span
        sigma_std_span = float(np.std(diffs_span, ddof=1))
        p99_span_raw = float(np.percentile(np.abs(diffs_span), 99))

        # Conservative threshold: max of theoretical 3-sigma speckle, empirical 3-sigma (12d & span), and raw P99
        tau_recommended = float(
            max(
                tau_speckle_3sigma,
                3.0 * sigma_mad_12d,
                3.0 * sigma_mad_span,
                p99_abs_raw,
            )
        )
        return {
            "stable_desert_pixel_count": n_desert,
            "consecutive_pair_samples": int(diffs_12d.size),
            "theoretical_enl": round(float(enl_val), 2),
            "theoretical_two_date_speckle_std_db": round(float(sigma_2date_speckle), 3),
            "theoretical_3sigma_speckle_threshold_db": round(float(tau_speckle_3sigma), 2),
            "empirical_12day_median_drift_db": round(med_12d, 3),
            "empirical_12day_robust_sigma_mad_db": round(sigma_mad_12d, 3),
            "empirical_12day_sample_std_db": round(sigma_std_12d, 3),
            "empirical_12day_3sigma_mad_db": round(3.0 * sigma_mad_12d, 2),
            "empirical_12day_p95_abs_db": round(p95_abs_raw, 2),
            "empirical_12day_p99_abs_db": round(p99_abs_raw, 2),
            "empirical_12day_p99_centered_db": round(p99_abs_centered, 2),
            "empirical_full_span_median_drift_db": round(med_span, 3),
            "empirical_full_span_robust_sigma_mad_db": round(sigma_mad_span, 3),
            "empirical_full_span_sample_std_db": round(sigma_std_span, 3),
            "empirical_full_span_3sigma_mad_db": round(3.0 * sigma_mad_span, 2),
            "empirical_full_span_p99_abs_db": round(p99_span_raw, 2),
            "recommended_threshold_db": round(tau_recommended, 2),
        }

    hh_thresh_info = _stats_for_channel(all_hh_12d, hh_span, enl_hh)
    hv_thresh_info = _stats_for_channel(all_hv_12d, hv_span, enl_hv)

    return {
        "random_seed": RANDOM_SEED,
        "derivation_method": (
            "Conservative maximum of (1) 3-sigma theoretical two-date speckle noise from Stage-2 ENL, "
            "(2) 3 * robust MAD sigma across N=218,705 stable consolidated desert pixels (12-day and 4-month span), "
            "and (3) 99th percentile of |delta_dB| over stable desert pixels."
        ),
        "HH": hh_thresh_info,
        "HV": hv_thresh_info,
    }


def classify_dual_pol_change(
    delta_hh_db: np.ndarray,
    delta_hv_db: np.ndarray,
    tau_hh_db: float,
    tau_hv_db: float,
    valid_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Classify dual-polarization log-ratio changes into 7 physical/statistical regimes.

    Classes (uint8):
      0 = No Statistically Significant Change (|dHH| < tau_HH and |dHV| < tau_HV)
      1 = Canopy Volume Growth (+HV >= +tau_HV, with dHH > -tau_HH)
      2 = Canopy Harvest / Clearance (-HV <= -tau_HV, with dHH < +tau_HH)
      3 = Surface Wetting / Roughness Increase (+HH >= +tau_HH, |dHV| < tau_HV)
      4 = Surface Drying / Specular Inundation (-HH <= -tau_HH, |dHV| < tau_HV)
      5 = Polarization Disagreement Type I: +HH Surge (>= +tau_HH) with -HV Drop (<= -tau_HV)
          (e.g., crop harvest followed by flood irrigation or wet rough plowing)
      6 = Polarization Disagreement Type II: -HH Drop (<= -tau_HH) with +HV Surge (>= +tau_HV)
          (e.g., emergent canopy growth attenuating surface return)
      255 = Invalid / NoData / Masked Low-SNR Sand Sheet
    """
    if delta_hh_db.shape != delta_hv_db.shape:
        raise ValueError("Shape mismatch between delta_hh_db and delta_hv_db.")

    h, w = delta_hh_db.shape
    valid = np.isfinite(delta_hh_db) & np.isfinite(delta_hv_db)
    if valid_mask is not None:
        valid = valid & (valid_mask > 0)

    cls = np.full((h, w), 255, dtype=np.uint8)
    cls[valid] = 0

    hh_up = valid & (delta_hh_db >= tau_hh_db)
    hh_dn = valid & (delta_hh_db <= -tau_hh_db)
    hh_flat = valid & (np.abs(delta_hh_db) < tau_hh_db)

    hv_up = valid & (delta_hv_db >= tau_hv_db)
    hv_dn = valid & (delta_hv_db <= -tau_hv_db)
    hv_flat = valid & (np.abs(delta_hv_db) < tau_hv_db)

    # Concordant or single-channel changes
    cls[hv_up & (~hh_dn)] = 1  # Canopy Volume Growth (+HV)
    cls[hv_dn & (~hh_up)] = 2  # Canopy Harvest / Clearance (-HV)
    cls[hh_up & hv_flat] = 3   # Surface Wetting / Roughness Increase (+HH only)
    cls[hh_dn & hv_flat] = 4   # Surface Drying / Specular Inundation (-HH only)

    # Explicit opposite-sign polarization disagreements
    cls[hh_up & hv_dn] = 5     # Disagreement I: +HH & -HV
    cls[hh_dn & hv_up] = 6     # Disagreement II: -HH & +HV

    n_valid = int(np.sum(valid))
    px_km2 = (40.0 * 40.0) / 1e6

    labels = {
        0: ("No_Significant_Change", f"|dHH| < {tau_hh_db} dB and |dHV| < {tau_hv_db} dB"),
        1: ("Canopy_Volume_Growth_HV_Up", f"dHV >= +{tau_hv_db} dB (vegetation volume increase)"),
        2: ("Canopy_Harvest_Senescence_HV_Down", f"dHV <= -{tau_hv_db} dB (vegetation volume loss)"),
        3: ("Surface_Wetting_or_Tillage_HH_Up_Only", f"dHH >= +{tau_hh_db} dB with |dHV| < {tau_hv_db} dB"),
        4: ("Surface_Drying_or_Inundation_HH_Down_Only", f"dHH <= -{tau_hh_db} dB with |dHV| < {tau_hv_db} dB"),
        5: ("Polarization_Disagreement_HH_Up_HV_Down", f"dHH >= +{tau_hh_db} dB AND dHV <= -{tau_hv_db} dB"),
        6: ("Polarization_Disagreement_HH_Down_HV_Up", f"dHH <= -{tau_hh_db} dB AND dHV >= +{tau_hv_db} dB"),
    }

    breakdown = {}
    for code, (name, desc) in labels.items():
        cnt = int(np.sum(cls == code))
        breakdown[name] = {
            "class_code": code,
            "pixel_count": cnt,
            "pct_of_valid_aoi": round((cnt / max(n_valid, 1)) * 100.0, 2),
            "area_km2": round(cnt * px_km2, 2),
            "rule": desc,
        }

    # Total polarization disagreement (opposite signs OR single-channel change where the other channel is flat)
    opposite_sign_cnt = int(np.sum((cls == 5) | (cls == 6)))
    single_channel_only_cnt = int(np.sum((cls == 3) | (cls == 4)))
    hv_only_cnt = int(np.sum(((cls == 1) | (cls == 2)) & hh_flat))

    summary = {
        "valid_evaluated_pixels": n_valid,
        "valid_evaluated_area_km2": round(n_valid * px_km2, 2),
        "tau_hh_db": tau_hh_db,
        "tau_hv_db": tau_hv_db,
        "regime_breakdown": breakdown,
        "polarization_disagreement_summary": {
            "opposite_sign_disagreement_pixels": opposite_sign_cnt,
            "opposite_sign_disagreement_area_km2": round(opposite_sign_cnt * px_km2, 2),
            "opposite_sign_disagreement_pct": round((opposite_sign_cnt / max(n_valid, 1)) * 100.0, 2),
            "hh_only_change_hv_stable_pixels": single_channel_only_cnt,
            "hh_only_change_hv_stable_area_km2": round(single_channel_only_cnt * px_km2, 2),
            "hv_only_change_hh_stable_pixels": hv_only_cnt,
            "hv_only_change_hh_stable_area_km2": round(hv_only_cnt * px_km2, 2),
        },
    }
    return cls, summary

