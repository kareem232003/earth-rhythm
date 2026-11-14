# EARTH RHYTHM — NISAR Surface Change Storyteller

**NASA Space Apps Challenge 2026 — *"Dancing with the SARs"***

An end-to-end L-band Synthetic Aperture Radar (SAR) scientific pipeline and interactive web observatory built on **10 real NASA-ISRO SAR (`NISAR`) `L2_GCOV` dual-polarization (`HH` + `HV`) acquisitions** and **9 consecutive Track `129` / Frame `016` `L2_GUNW` interferometric coherence pairs** (`2026-06-23` through `2026-10-21`, Ascending, `PROVISIONAL CRID P05023`) over the **Fayoum Oasis, Lake Qarun, El-Qarn Island, Wadi El Rayan, and Western Desert, Egypt**.

---

## 1. Scientific Question & Core Discoveries

> **How does dual-polarization L-band radar (wavelength `~24 cm`, `1.239 GHz`) separate crop canopy volume dynamics (`HV`) from bare-soil moisture, flood irrigation, building double-bounce, and wind-driven water wave roughness (`HH`) across an arid Nile-fed agricultural basin — and how can pure multi-temporal SAR + InSAR coherence resolve shoreline & island ambiguities without optical contamination?**

### Key Quantitative Findings (`N = 10` Dates, `4,912.69 km²` Valid AOI)
| Phenomenon / Discovery | Quantitative Metric (Computed from Calibrated `EPSG:32636` Stack) | Physical Mechanism & Epistemic Tag |
| :--- | :--- | :--- |
| **Empirical Change Thresholds (`Rule 4`)** | **`tau_HH = 2.73 dB`**, **`tau_HV = 2.03 dB`** (`N = 218,705` stable desert pixels = `349.93 km²`; `1,968,345` 12-day pairs) | Exceeds both theoretical Stage-2 speckle (`3σ_speckle = 1.49 dB HH / 0.87 dB HV`) and empirical desert `3σ_MAD` (`CHANGE DETECTION`) |
| **Summer Crop Canopy Growth (`Jun 23 -> Aug 10`)** | **`763.88 km²`** (`39.49%` of oasis cropland) exhibits `+dHV >= +2.03 dB` (`+4.04 dB` at `ROI_01`; paired `Sentinel-2 NDVI` `r = 0.93, p = 0.0009`) | L-band cross-pol (`HV`) depolarizes inside thickening maize, sorghum, cotton, and rice stems (`INTERPRETATION`) |
| **Late-Summer Harvest vs. Autumn Emergence (`Aug 10 -> Oct 21`)** | **`594.83 km²`** (`30.75%` of cropland) harvested (`-dHV <= -2.03 dB`) vs. **`174.17 km²`** (`9.00%`) newly planted autumn crops (`+10.77 dB HV` surge at `ROI_02`) | Bimodal crop calendar transition between summer harvest and autumn wheat/clover/vegetable planting (`CHANGE DETECTION`) |
| **When `HH` and `HV` Disagree (`ROI_03`)** | **`1.71 km²`** (`1,068 px`) Opposite-Sign Type I (`+HH >= +2.73 dB` & `-HV <= -2.03 dB`) + **`439.03 km²`** Single-Channel Disagreement (`ROI_03`: `dHV = -4.67 dB` while `dHH = +4.98 dB`) | Harvest removes canopy (`-HV`) while post-harvest flood irrigation on bare ridges spikes soil dielectric & surface scatter (`+HH`) (`INTERPRETATION`) |
| **Lake Qarun Specular Water vs. Wind Waves (`ROI_05`)** | `HV` pinned at **`-24.89 dB`** (`1.22 dB` range near `NESZ`), while `HH` swings by **`11.17 dB`** (`-23.16 dB` on Sep 27 at `3.05 m/s` wind vs. `-11.99 dB` on Oct 09 at `4.95 m/s` wind) | First-order Bragg resonant scattering from capillary waves strongly excites co-pol `HH` without depolarizing `HV` (`OBSERVATION` + `INTERPRETATION`) |
| **Pure-SAR Lake & Island Separation (`Option 1 + Option 2 Benchmarks`)** | Pure NISAR `v3` (`10 GCOV` + `9 GUNW`) reaches **`IoU = 0.9243` (`99.19%` precision)** vs. JPL `OPERA DSWx-HLS` and cuts false water on **El-Qarn Island (`2.20 km²`)** by **`99.2` percentage points** (`100.00% -> 0.80%`) | Combining 9-pair InSAR decorrelation (`coh < 0.145`), wind-wave bay variability (`std_HH > 0.75 dB`), and coherence/area-aware hole preservation stops blind hole-filling from erasing islands (`OBSERVATION` + `CHANGE DETECTION`) |
| **External Rainfall Independence (`Rule 2`)** | **`0.15 mm`** total cumulative rainfall across 133 days (`2026-06-15` to `2026-10-25`, `NASA POWER`; `0.00 mm` on all 10 NISAR overpasses) | Confirms 100% of observed soil moisture and inundation changes originate from **Bahr Youssef** Nile canal irrigation (`OBSERVATION`) |

---

## 2. Latest Major Capabilities & Scientific Upgrades

### 0. Plain-Language UI, Progressive Disclosure, Dashboards & Guide (`D-012` + `D-014`)
New to radar? The app pairs plain-language explanations with full technical traceability (nothing removed, only progressively disclosed):
- **Simplified Header & Map Controls (`D-014`):** Concise mission header with **Data details** and **Map settings** popovers, friendly map-mode chips (`One date`, `Compare two`, `What changed`, `Land types & extras`) retaining technical names as sub-labels/tooltips, compact 10-pass date stepper, short focal-spot buttons, collapsible **What am I looking at?** reading guide, and a minimizable map legend (preserving the `L2_GUNW` Rule 4/6 disclaimer).
- **5 Streamlined Workbench Tabs:** **Story** (`6` guided chapters with plain-language cards + collapsible science & Rule 5 statements), **This spot** (live Pixel Inspector + plain-language delta bars & expandable exact table), **Overview** (`DashboardsPanel` with 5 basin-scale views), **Forecast** (`PredictionPanel`), and **Help & data** (`How to read the app` Guide & glossary, `Layer data sheet` Rule 3 metadata, and `Methods & limits`).

### A. Decoupled Physical Scattering Composite (`HH / HV / Water+Wind`)
Legacy false-color radar composites (`R = HH`, `G = HV`, `B = HH - HV`) tinted both wind-roughened water and dry bare soil purple because `HH` fed both Red and Blue simultaneously. Our production **Physical Scattering Map** ([src/nisar_pipeline/tiles_and_cogs.py](src/nisar_pipeline/tiles_and_cogs.py)) decouples scattering physics into intuitive, non-overlapping visual channels directly from calibrated **100% NISAR SAR** bands:
- **Lush Green (`HV` Canopy Volume, `-18.8` to `-11.5 dB`):** Irrigated crops, orchards, and dense vegetation volume depolarization.
- **Vivid Red (`HH` Corner Double-Bounce, `-6.8` to `+0.5 dB`):** Fayoum City buildings, towns, and concrete infrastructure.
- **Deep Blue -> Cyan (Open Water & Bragg Ripples):** Calm specular water (`Deep Blue`) smoothly shifting to wind-roughened capillary wave backscatter (`Bright Cyan-Blue`).
- **Warm Sand / Tan (`HH` Surface Backscatter, `-21.8` to `-8.8 dB`, low `HV`):** Harvested fallow soil, limestone desert plateau, sand sheets, and dry lake islands.

### B. Option 1 (Pure SAR Island Fix) & Option 2 (Authoritative NASA Benchmarks)
To eliminate water-vs-smooth-desert ambiguity and fix an interior **El-Qarn Island (`Geziret El Qarn`)** misclassification inside Lake Qarun without contaminating the primary map with optical or DEM pixels:
1. **Option 1 (Pure NISAR Upgrade — Production Default, `compute_pure_sar_water_mask`):**
   - Stacked all **9 consecutive Track 129 / Frame 016 `L2_GUNW` 80 m coherence arrays** (`2026-06-23` through `2026-10-21`) instead of 2 pairs ([scripts/fetch_gunw_coherence_and_benchmarks.py](scripts/fetch_gunw_coherence_and_benchmarks.py)).
   - Combines persistent dark radar water (`>= 6/10` dates with `HH < -13.5 dB`, `HV < -19.0 dB`) with InSAR decorrelation (`coherence < 0.145`) **or** coastal wind-wave roughness variability (`coherence < 0.25` and `std(HH) > 0.75 dB`).
   - Replaced blind `binary_fill_holes` with **coherence- & area-aware hole filtering**: interior holes with `area >= 40 px` or `median coherence >= 0.22` remain dry ground (preserving **El-Qarn Island**, desert spits, and aquaculture dikes).
2. **Option 2 (Independent NASA Multi-Source Benchmark — Rule 2 Strictly Separated):**
   - Benchmarked all 4 progressive pipeline versions (`SEED = 42`) via [scripts/benchmark_sar_water_accuracy.py](scripts/benchmark_sar_water_accuracy.py) against JPL **`OPERA_L3_DSWX-HLS_V1`** (`2026-07-05`, exact `0d` `2026-08-10`, `2026-09-15`; `99.8%–100.0%` cloud-free), NASA **`NISAR_WATERMASK` v0.5.0**, and NASA **`NISAR_DEM` v1.2** (which confirms El-Qarn Island rises to **`+15.03 m`** — over **`43 m`** above Lake Qarun's `-28.80 m` water surface).

| Pipeline Stage | Source Data | IoU vs. `OPERA DSWx` | Precision / Recall | `IoU` vs. `NISAR_WM` | El-Qarn Island False Water (`N = 1,375 px`) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`v1` Baseline (`lc == 1`)** | 2 `GUNW` pairs + basin boxes | `0.6910` | `82.92% / 80.57%` | `0.6824` | `31 / 1,375` (`2.25%`) |
| **`v2` Intermediate** | 2 `GUNW` pairs + blind hole-fill | `0.9029` | `98.40% / 91.63%` | `0.8918` | `1,375 / 1,375` (**`100.00%` error**) |
| **`v3` Pure NISAR (Production)** | **10 `GCOV` + 9 `GUNW` + Wave `stdHH` + Island Guard** | **`0.9243`** | **`99.19% / 93.13%`** | **`0.9095`** | **`11 / 1,375` (`0.80%`, `99.20%` preserved)** |
| **`v4` Option 2 Exploratory Fusion** | `v3` + Rule 2 `NISAR_DEM` basin gate | `0.9373` | `98.20% / 95.37%` | `0.9209` | `6 / 1,375` (`0.44%`) |

### C. Echo AI Guide (`Echo`)
Built an integrated context-aware AI assistant ([src/nisar_pipeline/echo_assistant.py](src/nisar_pipeline/echo_assistant.py), [frontend/src/components/EchoHelper.tsx](frontend/src/components/EchoHelper.tsx)) supporting Gemini, Groq, OpenRouter, OpenAI, Anthropic, DeepSeek, Mistral, and local Ollama:
- Active connection testing (`/api/echo/test` ping before chat readiness confirmation).
- Live model discovery (`/api/echo/models`) and automatic on-the-go fallback cascades (e.g., handling deprecated Gemini 2.5 Flash -> Gemini 3.8/2.5/2.0 candidates automatically).
- Explicit non-fabrication guard (`is_error: true`, `needs_api_key: true`) when no valid API key is supplied.

### D. Phase 5 Explainable Flood & Next-Pass (`2026-11-02`) Forecaster (`D-013` & `D-015` Scientific Audit)
Implemented in [scripts/phase5_explainable_prediction.py](scripts/phase5_explainable_prediction.py), served via `/api/prediction`, and visualized in the **Forecast** tab ([frontend/src/components/PredictionPanel.tsx](frontend/src/components/PredictionPanel.tsx)):
- **Dual Ground-Truth Flood Validation (`Passes 1..9: 2026-06-23..2026-10-09` → Held-Out `Pass 10: 2026-10-21`, `SEED = 42`):**
  - **Track B (Independent Multi-Sensor Optical Validation vs. `NASA JPL OPERA_L3_DSWX-HLS_V1` & `NISAR_WATERMASK v0.5.0`):** `ROC-AUC = 0.9937` (Full AOI, `N = 3,063,660` px) / `0.9911` (`1.5 km` coastal buffer), **`Coastal IoU = 0.8820`** (`F1 = 0.9373`), **`Full AOI IoU = 0.7903`** (`F1 = 0.8828`, `Precision = 81.74%`, `Recall = 95.97%`), `Brier Score = 0.01251`, and 10-bin `ECE = 0.01200`.
  - **Track A (Pass 10 SAR Holdout Self-Consistency):** `ROC-AUC = 0.9998` (Full AOI) / `0.9976` (`1.5 km` coastal buffer) / `0.9957` (non-permanent shoreline margin), `Coastal IoU = 0.8751` (`F1 = 0.9334`), `Full AOI IoU = 0.7936` (`F1 = 0.8849`), `Dynamic Margin IoU = 0.6629`, and `Brier Score = 0.01167`.
- **Speckle-Aware Spatio-Temporal State-Space Forecaster & 7-Class Regime Validation:**
  - Normalizes all velocities by actual elapsed days ($\Delta t = 24\text{ d}$ between `2026-07-17` and `2026-08-10`; $12\text{ d}$ elsewhere) and beats Persistence, 3-Pass Moving Average, and Linear OLS Trend across all 4 rolling-origin temporal CV folds (`Passes 7, 8, 9, 10`).
  - Held-Out Pass 10 (`2026-10-21`): **`HH RMSE = 0.903 dB`** (`MAE = 0.606 dB`, `R² = 0.9646`, Cropland `RMSE = 1.222 dB`; vs. Persistence `0.964 dB`) and **`HV RMSE = 0.857 dB`** (`MAE = 0.539 dB`, `R² = 0.9181`, Cropland `RMSE = 1.269 dB`; vs. Persistence `0.902 dB`).
  - **7-Class Dual-Pol Regime Accuracy:** **`90.89%` Full AOI OA** (`Weighted F1 = 0.9007`, `Macro F1 = 0.4833`), **`80.38%` Cropland 48-Day OA** (`Weighted F1 = 0.7945`, `Macro F1 = 0.4786`, `Balanced Accuracy = 43.54%`), and **`86.53%` Cropland 12-Day Single-Step OA**.
- **Forward Forecast (`Pass 11: 2026-11-02`, `+12 Days`) & Native COGs:**
  - Exports **4 native `EPSG:32636` Cloud-Optimized GeoTIFFs (`.tif`)** in `data/cogs/predictions/` (`49` total COGs) and **4 `EPSG:4326` RGBA web overlays** (`pred_flood_risk_20261102`, `pred_crop_regime_20261102`, `pred_hh_db_20261102`, `pred_hv_db_20261102`, bringing the catalog to **`63` overlays**).
  - Enforces **8-connected hydraulic path continuity** over EGM2008 geoid-corrected orthometric `NISAR_DEM v1.2` (`Lake Qarun = -43.0 m MSL`) for drainage surge scenarios (`+0.0 m MODEL FORECAST`: `17,927.0 ha` at risk; `+0.5 m HYPOTHETICAL SCENARIO`: `2,585.4 ha` connected overtop, `19,180.0 ha` total risk, `215.0 ha` cropland; `+1.0 m HYPOTHETICAL SCENARIO`: `3,255.0 ha` connected overtop, `20,210.7 ha` total risk, `591.2 ha` cropland), plus populated 10-pass + Pass 11 (`±95% CI`) trajectories and Sentinel-2 NDVI context for all **6 focal Story ROIs**.

### E. Hybrid FastAPI + Serverless Static Cloud Hosting (`D-013`)
- **Containerized Full-Stack Server ([Dockerfile](Dockerfile)):** Runs Uvicorn + FastAPI on port `7860` (`python:3.14-slim`) serving the compiled React SPA, full-resolution `40 m` HDF5 cube inspection, `49` COGs, `63` overlays, and Echo AI endpoints.
- **Serverless Static Fallback ([frontend/src/staticBackend.ts](frontend/src/staticBackend.ts)):** Automatically falls back to `frontend/public/static_api/` JSON manifests and a compact `3x` binary cube (`cube_3x.bin`) when deployed without a Python backend (live demo on Hugging Face Spaces: `https://huggingface.co/spaces/kareem232003/earth-rhythm`).

---

## 3. Quick Start

### Prerequisites
- Python `3.11+` virtual environment `.venv` (`fastapi`, `uvicorn`, `h5py`, `rasterio`, `numpy`, `scipy`, `requests`, `earthaccess`, `python-dotenv`, `pytest`)
- Node.js `20+` and `npm` to compile the React + TypeScript frontend (`frontend/dist/` is excluded from git via `.gitignore`)

### 1. Build the Frontend & Launch the Observatory (`http://127.0.0.1:8000`)
```powershell
npm --prefix frontend install
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn nisar_pipeline.api_server:app --app-dir src --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser. The FastAPI server exposes:
- **`GET /`** — Compiled React + TypeScript + MapLibre GL JS Observatory (`frontend/dist/`)
- **`GET /api/health`** — Server readiness, loaded `10 x 1560 x 1968` calibrated linear-power cube, and catalog counts (`49` COGs, `63` overlays)
- **`GET /api/catalog`** — Master **Rule 3 & Rule 5** layer catalog ([data/web_tiles/layer_catalog.json](data/web_tiles/layer_catalog.json))
- **`GET /api/story`** — Complete Phase 2 + Phase 3 + Phase 4 scientific report payload
- **`GET /api/benchmark`** — Live Option 1 & Option 2 benchmark comparison JSON ([data/processed/sar_water_benchmark_report.json](data/processed/sar_water_benchmark_report.json)) rendered in **Help & data → Methods & limits**
- **`GET /api/prediction`** — Phase 5 explainable flood & next-pass (`2026-11-02`) forecast and Pass 10 backtest JSON ([data/processed/phase5_prediction_report.json](data/processed/phase5_prediction_report.json)) rendered in the **Forecast** tab
- **`GET /api/inspect?lon=30.9806&lat=29.3201&window_px=5`** — Real-time on-the-fly 10-date pixel/patch inspector (`~26 ms`)
- **`GET /api/echo/providers` & `POST /api/echo/{models,test,chat}`** — Echo AI provider discovery, connectivity ping, and context-grounded Q&A
- **`GET /tiles/overlays/...`** & **`GET /cogs/...`** — `63` `EPSG:4326` RGBA PNG map overlays & `49` Cloud-Optimized GeoTIFFs (`EPSG:32636`)

### 2. Re-run Benchmarks, Phase 5 Forecasts & Automated Scientific Invariant Tests (`pytest`)
```powershell
# Optional (requires NASA Earthdata credentials in .env): refresh 9 GUNW coherences & NASA benchmark GeoTIFFs
.\.venv\Scripts\python.exe scripts/fetch_gunw_coherence_and_benchmarks.py

# Recompute water & El-Qarn Island benchmark report
.\.venv\Scripts\python.exe scripts/benchmark_sar_water_accuracy.py

# Recompute Phase 5 explainable flood & next-pass crop forecast + Pass 10 backtest
.\.venv\Scripts\python.exe scripts/phase5_explainable_prediction.py

# Run all 11 automated scientific invariant unit tests
.\.venv\Scripts\python.exe -m pytest -v tests/test_nisar_invariants.py
```

### 3. Containerized Deployment (Docker / Hugging Face Spaces)
```powershell
npm --prefix frontend run build
docker build -t earth-rhythm .
docker run -p 7860:7860 earth-rhythm
```

---

## 4. Real NISAR & NASA Benchmark Datasets Used

All primary granules were accessed via authenticated NASA Earthdata / ASF DAAC HTTPS windowed range-reading ([scripts/phase1_extract_subsets.py](scripts/phase1_extract_subsets.py) and [scripts/fetch_gunw_coherence_and_benchmarks.py](scripts/fetch_gunw_coherence_and_benchmarks.py)), keeping local disk usage (`~1.56 GB` across subsets, COGs, PNGs, coherences, and benchmarks) far below the `5 GB` budget vs. `> 650 GB` of raw full scenes. Every primary NISAR granule shares **Track `129`**, **Frame `016`**, **Ascending**, **`PROVISIONAL CRID P05023` (`PGE R05.02.3`, Version `1.0.11`)**, and **`EPSG:32636`**:

| # | Acquisition Date / Span (UTC) | Product Type | Official NASA / ASF Granule ID | Pol / Grid | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `2026-06-23T03:15:46Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_013_129_A_016_4005_DHDH_A_20260623T031546_20260623T031621_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 2 | `2026-07-05T03:15:46Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_014_129_A_016_4005_DHDH_A_20260705T031546_20260705T031621_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 3 | `2026-07-17T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_015_129_A_016_4005_DHDH_A_20260717T031547_20260717T031621_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 4 | `2026-08-10T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_017_129_A_016_4005_DHDH_A_20260810T031547_20260810T031622_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 5 | `2026-08-22T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_018_129_A_016_4005_DHDH_A_20260822T031547_20260822T031622_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 6 | `2026-09-03T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_019_129_A_016_4005_DHDH_A_20260903T031548_20260903T031623_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 7 | `2026-09-15T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_020_129_A_016_4005_DHDH_A_20260915T031548_20260915T031623_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 8 | `2026-09-27T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_021_129_A_016_4005_DHDH_A_20260927T031548_20260927T031623_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 9 | `2026-10-09T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_022_129_A_016_4005_DHDH_A_20261009T031548_20261009T031623_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 10 | `2026-10-21T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_023_129_A_016_4005_DHDH_A_20261021T031548_20261021T031623_P05023_N_F_J_001` | `HH + HV` (`40 m`) | Primary calibrated stack |
| 11–19 | `2026-06-23 -> 2026-10-21` (all 9 pairs) | `L2_GUNW` | `NISAR_L2_PR_GUNW_{023..032}_129_A_016_{024..033}_4000_SH_*_P05023_N_F_J_001` | `HH` (`80 m`) | 2 exploratory Phase 1 LOS subsets + all **9** `coherenceMagnitude` rasters |
| Rule 2 | `2026-07-05`, `08-10`, `09-15` & static | External Benchmarks | `OPERA_L3_DSWX-HLS_V1`, `NISAR_WATERMASK v0.5.0`, `NISAR_DEM v1.2`, `NASA POWER`, `Sentinel-2 L2A` | `30 m` -> `40 m` | Strictly separated external cross-validation & Option 2 benchmark |

> Checksums, HDF5 paths, and benchmark manifests live in [`data/subsets/phase1_manifest.json`](data/subsets/phase1_manifest.json), [`data/processed/gunw_coherence/coherence_9pair_manifest.json`](data/processed/gunw_coherence/coherence_9pair_manifest.json), [`data/benchmarks/benchmark_manifest.json`](data/benchmarks/benchmark_manifest.json), and [`DECISIONS.md`](DECISIONS.md).

---

## 5. Repository Architecture

```text
Earth Rhythm AI/
├── Dockerfile                                 # FastAPI + built React SPA container (port 7860)
├── .dockerignore                              # Excludes raw HDF5/cache & node_modules from image
├── src/nisar_pipeline/
│   ├── guards.py                              # Rules 3, 5, 7, 8 version/geometry/CRS/metadata guards
│   ├── radiometry.py                          # Linear-power Lee & boxcar filtering, ENL, dB & log-ratio math
│   ├── masks.py                               # Multi-temporal water, desert, cropland, urban & NESZ masks
│   ├── insar.py                               # L2_GUNW unwrapped phase -> LOS displacement & gamma >= 0.50 mask
│   ├── change_detection.py                    # Threshold derivation (tau_HH=2.73, tau_HV=2.03 dB) & 7-class regimes
│   ├── tiles_and_cogs.py                      # Pure-SAR v3 lake/island classifier, 45 COGs & 59 base overlays
│   ├── echo_assistant.py                      # Multi-provider Echo AI guide, model discovery & fallback cascades
│   └── api_server.py                          # FastAPI backend (/catalog, /story, /benchmark, /prediction, /inspect, /echo/*)
├── scripts/
│   ├── phase0_audit.py                        # Phase 0: Environment & NASA CMR / ASF archive audit
│   ├── phase1_extract_subsets.py              # Phase 1: Authenticated HTTP range-read HDF5 subsetting
│   ├── phase2_process_layers.py               # Phase 2: Linear-power Lee filtering, ENL & masks
│   ├── phase3_change_analysis.py              # Phase 3: Log-ratio change maps, ROIs & external context
│   ├── phase4_build_cogs_and_tiles.py         # Phase 4: 45 COGs + 59 base overlays + layer_catalog.json
│   ├── phase5_explainable_prediction.py       # Phase 5: Flood/crop forecast (+2 overlays -> 61) & Pass 10 backtest
│   ├── fetch_gunw_coherence_and_benchmarks.py # Option 1/2: 9 GUNW coherences + NASA benchmark layers
│   ├── benchmark_sar_water_accuracy.py        # Quantitative v1-v4 vs OPERA DSWx / NISAR_WM / DEM report
│   └── generate_functions_md.py               # Automated AST docstring mapper -> functions.md
├── frontend/                                  # React 18 + TypeScript + Vite + MapLibre GL JS SPA
│   ├── public/static_api/                     # Serverless static fallback JSONs & 3x cube (cube_3x.bin)
│   └── src/
│       ├── plainLanguage.ts                   # Plain-language map/chapter/glossary copy (D-012)
│       ├── staticBackend.ts                   # Hybrid client-side tensor inspector & static JSON fallback (D-013)
│       ├── storySteps.ts                      # 6-chapter guided narrative with camera flyTo & radar physics
│       ├── types.ts                           # TypeScript interfaces for Rule 3/5 catalog, Story & Inspector
│       ├── uiLabels.ts                        # Friendly UI labels paired with original technical names (D-014)
│       └── components/
│           ├── NisarMap.tsx                   # Synchronized map canvas + swipe curtain + minimizable legend
│           ├── TimeSeriesChart.tsx            # Multi-temporal HH/HV/IQR/NESZ + Sentinel-2 NDVI SVG chart
│           ├── PlainReadouts.tsx              # Map guide, Story & Inspector plain-language cards (D-012)
│           ├── DashboardsPanel.tsx            # 5-view interactive basin dashboards (D-012)
│           ├── PredictionPanel.tsx            # Phase 5 Explainable Flood & Next-Pass Forecast UI (D-013)
│           ├── GuidePanel.tsx                 # 3-minute reading path, Rule 5 explainer & searchable glossary
│           ├── Disclosure.tsx                 # Collapsible progressive-disclosure wrapper (D-014)
│           ├── BenchmarkCard.tsx              # Live /api/benchmark validation card inside Methods & limits
│           └── EchoHelper.tsx                 # Echo AI companion chat panel, provider setup & active ping
└── tests/
    └── test_nisar_invariants.py               # 11 automated scientific invariant unit tests (pytest)
```

---

## 6. Honest Scientific Accounting: What Works & Explicit Limitations (`Rule 5 & Rule 6`)

### What Works & Is Verified
- **100% Real Calibrated NISAR Production Map:** All `10 L2_GCOV` passes and all `9 L2_GUNW` coherence arrays are real `PROVISIONAL CRID P05023` NISAR observations over Fayoum Oasis; external datasets remain strictly separated under **Rule 2**.
- **Strict Linear-Power Radiometry (`Rule 4`):** All `10 m -> 40 m` multilooking and `3x3` Adaptive Lee filtering occur strictly in linear `gamma0` (`m²/m²`), increasing `ENL` from `4.90` (`10 m`) -> `41.15–45.14` (`40 m`) -> `152.74–481.20` (`40 m` Lee) with `< 0.08%` mean power drift.
- **Full Rule 3, Rule 5 & QA Provenance:** All `63` overlays, `49` downloadable COGs, Phase 5 prediction report, and quantitative benchmarks pass all **11** automated tests in `pytest -v tests/test_nisar_invariants.py`. See also [`SCIENTIFIC_AUDIT_REPORT.md`](SCIENTIFIC_AUDIT_REPORT.md), [`MODEL_VALIDATION_REPORT.md`](MODEL_VALIDATION_REPORT.md), [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md), [`MODEL_LIMITATIONS.md`](MODEL_LIMITATIONS.md), and [`CHANGELOG.md`](CHANGELOG.md).

### Explicit Limitations & What We Cannot Conclude (`Rule 6`)
1. **Backscatter Is Not Ground Subsidence (`Rule 4`):** `gamma0` (`L2_GCOV`) changes track dielectric moisture and 3D canopy/surface roughness changes, never vertical land deformation.
2. **Single-Pair L-Band `L2_GUNW` Tropospheric Ramp:** Although `66.85%` of the basin keeps 12-day L-band coherence `gamma >= 0.50`, single 12-day interferograms contain `24.1–29.5 mm` (`8.80–18.78 mm` $1\sigma$ on stable desert bedrock) of regional tropospheric water-vapor phase gradients between Lake Qarun (`-28.8 m` WGS84 ellipsoidal / `-43.0 m` orthometric MSL) and the surrounding plateau. Sub-centimeter ground subsidence cannot be claimed without an SBAS/PS-InSAR stack of `>= 20–30` passes.
3. **Crop Species & Gravimetric Soil Moisture (`m³/m³`):** Dual-pol SAR separates **canopy volume growth (`+HV`)** from **bare-soil wetting/tillage (`+HH`)**, but cannot classify exact crop species or yield absolute volumetric soil moisture without in-situ calibration.
4. **Low-SNR Sand-Sheet Zones (`11.21%` of AOI):** Smooth quartz sand sheets where backscatter falls within `+3 dB` of `NESZ` (`-23.3 dB HH`, `-24.5 dB HV`) remain explicitly masked (`composite_landcover_class == 6`) and excluded from quantitative soil-moisture and flood susceptibility claims.
5. **Phase 5 Forecast Scope:** Flood susceptibility validation is reported transparently across both **Track B (Independent NASA OPERA DSWx-HLS v1.0 & NISAR_WATERMASK v0.5.0)** and **Track A (Pass 10 SAR Holdout Self-Consistency)**, and the `+0.5 m` and `+1.0 m` hydraulically connected `HAND` surge scenarios are explicitly labeled as `HYPOTHETICAL SCENARIO` hydrostatic routing rather than hydrodynamic flood forecasts.
