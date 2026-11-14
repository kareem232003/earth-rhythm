# SCIENTIFIC AUDIT REPORT — EARTH RHYTHM (NASA SPACE APPS 2026)

**Project:** EARTH RHYTHM — NISAR L-Band Surface Change Storyteller  
**Study Area:** Fayoum Oasis, Lake Qarun & Wadi El-Rayan, Egypt (`EPSG:32636` UTM Zone 36N, `1,560 × 1,968` at 40 m = `3,070,080` pixels = `4,912.13 km²`)  
**Audit Date:** 2026-11-14  
**Random Seed:** `SEED = 42`  

---

## 1. Executive Summary of the Audit

In accordance with Phases 1 through 4 of the Master Scientific & Engineering Audit, we inspected every preprocessing script, HDF5 data cube (`fayoum_gcov_10dates_40m_filtered.h5` and `fayoum_gunw_9pairs_40m.h5`), benchmark dataset (`NASA JPL OPERA_L3_DSWX-HLS_V1`, `NASA NISAR_DEM v1.2`, `NASA NISAR_WATERMASK v0.5.0`, `ESA Sentinel-2 L2A`), and the two-engine prediction pipeline (`scripts/phase5_explainable_prediction.py`).

### Key Bugs & Scientific Weaknesses Identified and Resolved

1. **Bug Fix — Forecast Layer Native COG Download & CRID Metadata:**
   - **Prior Issue:** In `data/web_tiles/layer_catalog.json`, the forecast layers (`pred_flood_risk_20261102` and `pred_crop_regime_20261102`) had `"cog_url"` pointing to `.png` files under `/tiles/overlays/predictions/...png` instead of actual Cloud-Optimized GeoTIFFs (`.tif`), and their `rule3_metadata.product_version` displayed `CRID R00500` instead of the cube's actual `PROVISIONAL CRID P05023 / Ver 1.0.11 (PGE R05.02.3)`.
   - **Correction:** Exported 4 real `EPSG:32636` `256 × 256` tiled Cloud-Optimized GeoTIFFs with `[2, 4, 8]` internal overviews and full Rule 3 & Rule 5 GDAL tags in `data/cogs/predictions/` (`49` total COGs verified by `test_invariant_7`), updated all 4 forecast layer `cog_url` entries to `/cogs/predictions/*.tif`, and aligned `product_version` to `PROVISIONAL CRID P05023 / Ver 1.0.11 (PGE R05.02.3) -> +12d Forecast (2026-11-02)`.

2. **Phase 2.1 — Flood Susceptibility Feature Weights, Vertical Datum & Eolian Sand Separation:**
   - **Prior Issue:** The code and documentation had a slight weight discrepancy (`0.38, 0.26, 0.20, 0.16` vs. `0.38, 0.24, 0.22, 0.16`). Furthermore, `NASA NISAR_DEM v1.2` is referenced to the **WGS84 ellipsoid**, where the EGM2008 geoid undulation over Fayoum is $N_{\text{geoid}} \approx +14.20\text{ m}$ (meaning Lake Qarun is at $-28.80\text{ m}$ WGS84 ellipsoidal height = $-43.00\text{ m}$ orthometric MSL height). In addition, `masks/low_snr_nesz_mask` (`HV < -22 dB`) was active over specular open water, whereas `masks/composite_landcover_class == 6` (`Low-SNR Eolian Sand Sheet`) cleanly isolates dry desert sand sheets.
   - **Correction:** Standardized the feature weights to $w = (0.38, 0.24, 0.22, 0.16)$ ($\sum w_i = 1.00$), verified all 4 normalized features $f_1, f_2, f_3, f_4 \in [0, 1]$, applied the explicit $-14.20\text{ m}$ EGM2008 geoid correction (`dem_msl_m = dem_ellipsoidal_m - 14.20`), and gated out dry eolian sand sheets (`composite_landcover_class == 6`) and upland desert plateaus (`HAND > 8.0 m`).

3. **Phase 2.1 — Ground-Truth Independence (Separating Self-Consistency from Independent Optical Validation):**
   - **Prior Issue:** The previous flood evaluation scored predictions only against a Pass 10 SAR-derived water mask (`compute_pure_sar_water_mask`), which shares SAR backscatter and InSAR coherence physics with the predictor.
   - **Correction:** Implemented **Dual Ground-Truth Flood Validation**:
     - **Track B (Independent Multi-Sensor Optical & Reference Validation):** Evaluated directly against independent 30 m Harmonized Landsat-Sentinel-2 **NASA JPL OPERA DSWx-HLS v1.0** (`OPERA_L3_DSWX-HLS_T36RTT_20260705`, `20260810`, `20260915`) and **NASA NISAR_WATERMASK v0.5.0**.
     - **Track A (Temporal Holdout SAR Self-Consistency):** Evaluated on Held-Out Pass 10 (`2026-10-21`) across the Full AOI (`3,070,080` px), the `1.5 km` Coastal Buffer (`352,299` px), and the **Non-Permanent Dynamic Shoreline Margin** (`182,178` px, excluding permanent lake interiors).

4. **Phase 2.2 — Hydraulically Connected HAND Drainage Surge Simulator:**
   - **Prior Issue:** The surge simulator previously tested `hand_m <= surge_m` and `dist_to_water <= 1200 m` without verifying topological hydraulic connectivity to permanent water bodies, and did not separate model forecasts from hypothetical scenarios.
   - **Correction:** Implemented 8-connected component flood-fill (`scipy.ndimage.label`) seeded strictly from permanent water bodies (`Lake Qarun` and `Wadi El-Rayan`) across floodable pixels (`hand_m <= surge_m`), safeguarded zero-surge (`+0.0 m`) division, and labeled `+0.0 m` as `MODEL FORECAST` vs. `+0.5 m` and `+1.0 m` as `HYPOTHETICAL SCENARIO`.

5. **Phase 2.3 & Phase 4 — Irregular Acquisition Interval ($\Delta t = 24\text{ d}$) & Beating Persistence Baseline:**
   - **Prior Issue:** The 10 NISAR passes include a **24-day gap** between Pass 3 (`2026-07-17`) and Pass 4 (`2026-08-10`) due to one missed 12-day orbital cycle. Treating all steps as equal 12-day intervals biased velocity estimates by $2\times$ across that gap. Additionally, the earlier single-pixel velocity filter had higher Pass 10 RMSE (`1.030 dB` HH, `0.952 dB` HV) than a simple Persistence baseline (`0.964 dB` HH, `0.902 dB` HV) because consecutive SAR innovations exhibit negative lag-1 autocorrelation ($r \approx -0.35$ for HH, $-0.22$ for HV) from residual speckle and transient moisture fluctuations.
   - **Correction:** Designed and implemented the **Speckle-Aware Spatio-Temporal State-Space Forecaster**, which normalizes every step by actual elapsed days $\Delta t_k \in \{12, 12, 24, 12, 12, 12, 12, 12, 12\}$, decomposes pixel-scale speckle innovations (`sp_innov`) from 5×5 parcel-scale trends (`d1_loc`) and historical median anomalies (`anom_sp`, `anom`), and fits state-space gains strictly inside the training window (`Passes 1..9` for backtest; `Passes 1..10` for forward forecast). This reduces Held-Out Pass 10 RMSE to **`0.903 dB` (HH)** and **`0.857 dB` (HV)**, outperforming Persistence, 3-Pass Moving Average, and Linear OLS Trend across all 4 rolling-origin temporal CV folds.

---

## 2. Summary of Verified Recalculated Metrics

| Metric Category | Metric Name | Previous Claim | Audited & Recalculated Value | Reference / Scope |
|---|---|---:|---:|---|
| **Flood Validation (Track B — Independent)** | ROC-AUC (vs. OPERA DSWx-HLS) | *Not reported* | **99.37%** (`0.9937`) | Full AOI (`N = 3,063,660` px) |
| **Flood Validation (Track B — Independent)** | Coastal 1.5 km IoU (vs. OPERA) | *Not reported* | **88.20%** (`0.8820`) | Coastal 1.5 km (`N = 349,228` px) |
| **Flood Validation (Track B — Independent)** | Full AOI IoU / F1 (vs. OPERA) | *Not reported* | **79.03%** / **0.8828** | Precision `81.74%`, Recall `95.97%` |
| **Flood Validation (Track B — Independent)** | Brier Score / ECE (vs. OPERA) | *Not reported* | **0.01251** / **0.01200** | 10-bin calibration curve |
| **Flood Validation (Track A — SAR Holdout)** | Coastal 1.5 km ROC-AUC | `99.76%` | **99.76%** (`0.9976`) | Coastal 1.5 km (`N = 352,299` px) |
| **Flood Validation (Track A — SAR Holdout)** | Coastal 1.5 km IoU / F1 | `88.71%` | **87.51%** / **0.9334** | After sand-sheet & datum fix |
| **Flood Validation (Track A — SAR Holdout)** | Dynamic Shoreline Margin IoU | *Not reported* | **66.29%** (`F1 = 0.7973`) | Non-permanent water (`N = 182,178` px) |
| **Backscatter Forecast (Pass 10 Holdout)** | HH RMSE / MAE / Bias (Full AOI) | `1.030 dB` | **0.903 dB** / **0.606 dB** / **-0.126 dB** | Beats Persistence (`0.964 dB`) |
| **Backscatter Forecast (Pass 10 Holdout)** | HV RMSE / MAE / Bias (Full AOI) | `0.952 dB` | **0.857 dB** / **0.539 dB** / **+0.044 dB** | Beats Persistence (`0.902 dB`) |
| **Backscatter Forecast (Pass 10 Holdout)** | HH $R^2$ / HV $R^2$ (Full AOI) | `0.9539` / `0.8989` | **0.9646** / **0.9181** | Full AOI (`N = 3,070,080` px) |
| **Backscatter Forecast (Pass 10 Holdout)** | HH / HV Cropland RMSE | `1.391` / `1.448 dB` | **1.222 dB** / **1.269 dB** | Cropland (`N = 1,208,974` px) |
| **7-Class Dual-Pol Regime (Pass 10 Holdout)** | Cropland Overall Accuracy (48d) | `78.12%` | **80.38%** (`0.8038`) | Weighted F1 `0.7945`, Macro F1 `0.4786` |
| **7-Class Dual-Pol Regime (Pass 10 Holdout)** | Full AOI Overall Accuracy (48d) | `89.84%` | **90.89%** (`0.9089`) | Weighted F1 `0.9007`, Macro F1 `0.4833` |
| **7-Class Dual-Pol Regime (Pass 10 Holdout)** | Cropland 12-Day Single-Step OA | *Not reported* | **86.53%** (`0.8653`) | Single 12-day step (`Oct 09 -> Oct 21`) |
