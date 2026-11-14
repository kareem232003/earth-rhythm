# CHANGELOG — EARTH RHYTHM (NASA SPACE APPS 2026)

## [v2.0.0] — 2026-11-14 — Master Scientific Audit, Forecasting Upgrade & Native COG Release

### Bug Fixes
- **Native Forecast Cloud-Optimized GeoTIFFs (`.tif`):** Fixed the Rule 3 Metadata download bug where forecast layers downloaded `.png` web overlays instead of `.tif` rasters. Generated 4 native `EPSG:32636` `256 × 256` tiled Cloud-Optimized GeoTIFFs with `[2, 4, 8]` internal overviews and full Rule 3 & Rule 5 GDAL metadata tags in `data/cogs/predictions/`:
  - `NISAR_L2_PRED_T129_F016_20261102_flood_risk_tier_40m.tif`
  - `NISAR_L2_PRED_T129_F016_20261102_crop_regime_40m.tif`
  - `NISAR_L2_PRED_T129_F016_20261102_HH_gamma0_dB_40m.tif`
  - `NISAR_L2_PRED_T129_F016_20261102_HV_gamma0_dB_40m.tif`
- **CRID & Product Version Provenance:** Corrected `rule3_metadata.product_version` on all forecast layers from `CRID R00500` to `PROVISIONAL CRID P05023 / Ver 1.0.11 (PGE R05.02.3) -> +12d Forecast (2026-11-02)`.
- **Populated All 6 Focal Story ROIs (`focal_roi_forecasts`):** Fixed the empty `focal_roi_forecasts` array and populated full 10-pass historical trajectories, Pass 10 holdout backtest residuals, Pass 11 (`2026-11-02`) forecasts with `±95% CI` bounds, driver scores, orthometric DEM/HAND, and paired **ESA Sentinel-2 L2A NDVI** context for all 6 Story Mode ROIs.

### Scientific & Machine Learning Enhancements (Phases 2–4)
- **Vertical Datum Geoid Correction (`NISAR_DEM v1.2`):** Applied the explicit $-14.20\text{ m}$ EGM2008 geoid undulation over Fayoum Oasis to convert native WGS84 ellipsoidal heights (`-28.8 m` on Lake Qarun) to orthometric Mean Sea Level (`-43.0 m MSL` on Lake Qarun; `-10.7 m` and `-29.7 m MSL` on Upper and Lower Wadi El-Rayan).
- **Eolian Sand Sheet Exclusion (`composite_landcover_class == 6`):** Replaced the raw `HV < -22 dB` NESZ mask in the flood gate (which triggered on specular open water) with Phase 2's coherence-verified `Low-SNR Eolian Sand Sheet` class (`class 6`).
- **Hydraulically Connected HAND Surge Simulator:** Enforced 8-connected topological path continuity (`scipy.ndimage.label`) from permanent water bodies for `+0.0 m` (`MODEL FORECAST`), `+0.5 m` (`HYPOTHETICAL SCENARIO`), and `+1.0 m` (`HYPOTHETICAL SCENARIO`) drainage surge scenarios, with safe zero-surge handling.
- **Dual Ground-Truth Flood Validation:** Added **Track B (Independent Multi-Sensor Optical Validation vs. NASA JPL OPERA DSWx-HLS v1.0 & NISAR_WATERMASK v0.5.0)** alongside **Track A (Pass 10 SAR Holdout Self-Consistency: Full AOI, Coastal 1.5 km Buffer, and Non-Permanent Dynamic Shoreline Margin)** and 10-bin probability calibration curves (`ECE = 0.0120` vs. OPERA).
- **Speckle-Aware Spatio-Temporal State-Space Forecaster:** Accounted for the irregular 24-day acquisition gap (`2026-07-17` $\to$ `2026-08-10`) and negative lag-1 SAR speckle innovation autocorrelation, reducing Held-Out Pass 10 RMSE to **`0.903 dB` (HH)** and **`0.857 dB` (HV)** and beating Persistence, 3-Pass Moving Average, and Linear OLS Trend baselines across all 4 rolling-origin CV folds.
- **Full 7-Class Regime Validation:** Computed Overall Accuracy (`80.38%` Cropland, `90.89%` Full AOI), Weighted F1 (`0.7945`), Macro F1 (`0.4786`), Balanced Accuracy (`43.54%`), per-class Precision/Recall/F1, and full $7\times 7$ confusion matrices.

### Frontend UI/UX & Documentation (Phases 5–9)
- Upgraded `PredictionPanel.tsx` with 4 interactive forecast map layer buttons, epistemic badges, hydraulically connected surge table, 6-ROI forecast trajectory fan chart (`±95% CI`) with Sentinel-2 NDVI context, Dual Flood Validation tabs (`OPERA DSWx-HLS` vs. `Pass 10 Holdout`), 10-bin calibration bar chart, Baseline & Rolling-Origin CV tables, 7-class per-regime scorecard + expandable $7\times 7$ confusion matrix, and direct `.tif` COG download cards.
- Added `SCIENTIFIC_AUDIT_REPORT.md`, `MODEL_VALIDATION_REPORT.md`, `DATA_PROVENANCE.md`, `MODEL_LIMITATIONS.md`, and `CHANGELOG.md`.
