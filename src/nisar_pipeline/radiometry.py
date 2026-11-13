"""Radiometric Calibration, Speckle Filtering, and ENL Verification (Rule 4 & Science Req 1-3).

All spatial averaging and speckle filtering routines operate STRICTLY in linear power
(gamma0, m^2/m^2) and reject decibel (dB) inputs, which can contain negative values.
Conversion to dB (`10 * log10(power)`) is performed exclusively after linear filtering
or when computing log-ratio change maps (`10 * log10(P2 / P1)`).
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter


def assert_linear_power(power_arr: np.ndarray, allow_nan: bool = True) -> None:
    """Verify an array represents non-negative linear power and not decibels (Rule 4)."""
    valid = power_arr[np.isfinite(power_arr)] if allow_nan else power_arr.ravel()
    if valid.size == 0:
        raise ValueError("Linear power array contains no finite values.")
    # In dB, typical SAR backscatter values span [-30, +5]; in linear power they are >= 0.
    if np.any(valid < 0.0):
        min_val = float(np.min(valid))
        raise ValueError(
            f"Rule 4 Violation: Negative values detected (min={min_val:.4f}) in linear power operation. "
            "Did you pass decibel (dB) values into a linear-power function?"
        )


def linear_to_db(power_arr: np.ndarray, min_power: float = 1e-10) -> np.ndarray:
    """Convert linear backscatter power (gamma0) to decibels: 10 * log10(power).

    Zeros, non-positive values, and NaNs are mapped to NaN.
    """
    assert_linear_power(power_arr, allow_nan=True)
    out = np.full(power_arr.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(power_arr) & (power_arr > 0.0)
    clipped = np.maximum(power_arr[valid], min_power)
    out[valid] = (10.0 * np.log10(clipped)).astype(np.float32)
    return out


def db_to_linear(db_arr: np.ndarray) -> np.ndarray:
    """Convert decibel (dB) backscatter values back to linear power: 10^(dB / 10)."""
    out = np.full(db_arr.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(db_arr)
    out[valid] = np.power(10.0, db_arr[valid] / 10.0).astype(np.float32)
    return out


def log_ratio_db(power_t1: np.ndarray, power_t2: np.ndarray) -> np.ndarray:
    """Compute log-ratio backscatter change in dB from two linear power arrays: 10 * log10(P2 / P1)."""
    assert_linear_power(power_t1, allow_nan=True)
    assert_linear_power(power_t2, allow_nan=True)
    if power_t1.shape != power_t2.shape:
        raise ValueError(f"Shape mismatch in log_ratio_db: {power_t1.shape} vs {power_t2.shape}")
    out = np.full(power_t1.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(power_t1) & (power_t1 > 0.0) & np.isfinite(power_t2) & (power_t2 > 0.0)
    out[valid] = (10.0 * np.log10(power_t2[valid] / power_t1[valid])).astype(np.float32)
    return out


def boxcar_filter_linear(power_arr: np.ndarray, window_size: int = 3) -> np.ndarray:
    """Apply a NaN-aware spatial boxcar filter strictly in linear power (gamma0)."""
    if window_size < 1 or window_size % 2 == 0:
        raise ValueError(f"window_size must be a positive odd integer, got {window_size}.")
    assert_linear_power(power_arr, allow_nan=True)

    valid = np.isfinite(power_arr) & (power_arr > 0.0)
    clean = np.where(valid, power_arr, 0.0).astype(np.float64)
    w_arr = valid.astype(np.float64)

    mean_p = uniform_filter(clean, size=window_size, mode="nearest")
    mean_w = uniform_filter(w_arr, size=window_size, mode="nearest")

    with np.errstate(divide="ignore", invalid="ignore"):
        filt = np.where((mean_w > 0.0) & valid, mean_p / mean_w, np.nan).astype(np.float32)
    return filt


def lee_filter_linear(
    power_arr: np.ndarray,
    window_size: int = 3,
    enl_prior: float = 32.0,
) -> np.ndarray:
    """Apply an adaptive Minimum Mean Square Error (Lee) speckle filter in linear power.

    Formula (in linear intensity/power I):
      I_filt = I_mean + W * (I - I_mean)
      where W = max(0, (Var(I) - Var_speckle) / (Var(I) + eps))
      and Var_speckle = (I_mean^2) / enl_prior.

    Over homogeneous distributed targets (Var(I) <= Var_speckle), W -> 0 and the filter
    smooths speckle to the local linear mean. Over sharp boundaries or point scatterers
    (Var(I) >> Var_speckle), W -> 1 and edge sharpness is preserved.
    """
    if window_size < 1 or window_size % 2 == 0:
        raise ValueError(f"window_size must be a positive odd integer, got {window_size}.")
    if enl_prior <= 0.0:
        raise ValueError(f"enl_prior must be positive, got {enl_prior}.")
    assert_linear_power(power_arr, allow_nan=True)

    valid = np.isfinite(power_arr) & (power_arr > 0.0)
    clean = np.where(valid, power_arr, 0.0).astype(np.float64)
    w_arr = valid.astype(np.float64)

    sum_p = uniform_filter(clean, size=window_size, mode="nearest")
    sum_p2 = uniform_filter(clean * clean, size=window_size, mode="nearest")
    sum_w = uniform_filter(w_arr, size=window_size, mode="nearest")

    with np.errstate(divide="ignore", invalid="ignore"):
        local_mean = np.where(sum_w > 0.0, sum_p / sum_w, np.nan)
        local_sq_mean = np.where(sum_w > 0.0, sum_p2 / sum_w, np.nan)
        local_var = np.maximum(0.0, local_sq_mean - local_mean * local_mean)

        speckle_var = (local_mean * local_mean) / float(enl_prior)
        weight = np.clip((local_var - speckle_var) / np.maximum(local_var, 1e-20), 0.0, 1.0)
        filt = local_mean + weight * (clean - local_mean)

    return np.where(valid, filt, np.nan).astype(np.float32)


def compute_empirical_enl(power_patch: np.ndarray) -> dict[str, float]:
    """Compute empirical Equivalent Number of Looks (ENL = mu^2 / sigma^2) in linear power.

    Also computes the theoretical single-date standard deviation in dB:
      sigma_dB = 10 * log10(1 + 1/sqrt(ENL)) ~ 4.3429 / sqrt(ENL)
    and two-date log-ratio standard deviation in dB:
      sigma_diff_dB = sqrt(2) * sigma_dB.
    """
    assert_linear_power(power_patch, allow_nan=True)
    valid = power_patch[np.isfinite(power_patch) & (power_patch > 0.0)].astype(np.float64)
    if valid.size < 16:
        raise ValueError(f"Need at least 16 valid pixels to estimate ENL, got {valid.size}.")
    mu = float(np.mean(valid))
    sigma = float(np.std(valid, ddof=1))
    if sigma <= 0.0:
        raise ValueError("Zero variance encountered in ENL patch.")
    enl = (mu * mu) / (sigma * sigma)
    sigma_db = float(4.3429448190325175 / np.sqrt(enl))
    sigma_diff_db = float(np.sqrt(2.0) * sigma_db)
    return {
        "pixel_count": int(valid.size),
        "mean_linear": round(mu, 6),
        "std_linear": round(sigma, 6),
        "enl": round(float(enl), 2),
        "single_date_speckle_std_db": round(sigma_db, 3),
        "two_date_diff_speckle_std_db": round(sigma_diff_db, 3),
    }

